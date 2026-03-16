"""
SoFIFA Scraper — Playwright-based, fills every column in player_season_stats.

Architecture
============
  Phase 1  scrape_index_pages()    collects player URLs + basic list-page data
  Phase 2  scrape_player_detail()  visits each profile, extracts ALL fields
  Phase 3  upsert_player()         writes to DB with ON CONFLICT update

Responsible scraping
====================
  * 2-5 s random delay between detail requests
  * Cloudflare retry: up to 5 attempts with 10 s backoff
  * User-agent rotation
  * Resource blocking (images / fonts / media) for speed
  * Full scrape_log audit trail

Historical seasons
==================
  Pass a SoFIFA version ID (e.g. 240072 for EA FC 25).
  Current season: version_id=None (uses the live page).

Usage
=====
  python sofifa_scraper.py                                 # current, 5000 players
  python sofifa_scraper.py --season 2024/25 --version 240072
  python sofifa_scraper.py --season 2022/23 --version 220054 --max 1000
"""

import argparse
import asyncio
import logging
import os
import random
import re
from dataclasses import asdict, dataclass
from typing import Optional

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PWTimeout
from playwright.async_api import async_playwright

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://soccer:soccer123@localhost:5432/soccersolver",
)

BASE_URL = "https://sofifa.com"

# Known SoFIFA version IDs -- used as ?version=XXXXXX on historical pages
SEASON_VERSIONS: dict[str, Optional[int]] = {
    "2025/26": None,    # live / current -- no version param
    "2024/25": 240072,  # EA FC 25
    "2023/24": 230054,  # EA FC 24
    "2022/23": 220054,  # FIFA 23
    "2021/22": 210054,  # FIFA 22
}

USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model -- maps 1-to-1 with player_season_stats columns
# ---------------------------------------------------------------------------

@dataclass
class Player:
    # key
    sofifa_id: int = 0
    season: str = ""

    # identity
    short_name: Optional[str] = None
    long_name: Optional[str] = None
    player_positions: Optional[str] = None
    overall: Optional[int] = None
    potential: Optional[int] = None
    age: Optional[int] = None

    # club
    club_name: Optional[str] = None
    league_name: Optional[str] = None
    league_level: Optional[int] = None

    # nationality
    nationality_name: Optional[str] = None

    # physical / profile
    preferred_foot: Optional[str] = None
    weak_foot: Optional[int] = None
    skill_moves: Optional[int] = None
    international_reputation: Optional[int] = None
    work_rate: Optional[str] = None
    body_type: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None

    # economic
    value_eur: Optional[int] = None
    wage_eur: Optional[int] = None
    release_clause_eur: Optional[int] = None

    # FIFA card stats
    pace: Optional[int] = None
    shooting: Optional[int] = None
    passing: Optional[int] = None
    dribbling: Optional[int] = None
    defending: Optional[int] = None
    physic: Optional[int] = None

    # attacking
    attacking_crossing: Optional[int] = None
    attacking_finishing: Optional[int] = None
    attacking_heading_accuracy: Optional[int] = None
    attacking_short_passing: Optional[int] = None
    attacking_volleys: Optional[int] = None

    # skill
    skill_dribbling: Optional[int] = None
    skill_curve: Optional[int] = None
    skill_fk_accuracy: Optional[int] = None
    skill_long_passing: Optional[int] = None
    skill_ball_control: Optional[int] = None

    # movement
    movement_acceleration: Optional[int] = None
    movement_sprint_speed: Optional[int] = None
    movement_agility: Optional[int] = None
    movement_reactions: Optional[int] = None
    movement_balance: Optional[int] = None

    # power
    power_shot_power: Optional[int] = None
    power_jumping: Optional[int] = None
    power_stamina: Optional[int] = None
    power_strength: Optional[int] = None
    power_long_shots: Optional[int] = None

    # mentality
    mentality_aggression: Optional[int] = None
    mentality_interceptions: Optional[int] = None
    mentality_positioning: Optional[int] = None
    mentality_vision: Optional[int] = None
    mentality_penalties: Optional[int] = None
    mentality_composure: Optional[int] = None

    # defending
    defending_marking_awareness: Optional[int] = None
    defending_standing_tackle: Optional[int] = None
    defending_sliding_tackle: Optional[int] = None

    # goalkeeping
    goalkeeping_diving: Optional[int] = None
    goalkeeping_handling: Optional[int] = None
    goalkeeping_kicking: Optional[int] = None
    goalkeeping_positioning: Optional[int] = None
    goalkeeping_reflexes: Optional[int] = None
    goalkeeping_speed: Optional[int] = None

    # ML-derived (set here from positions; refined by pipeline)
    position_group: Optional[str] = None


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _money(text: str) -> Optional[int]:
    """'EUR 120M' / 'EUR45K' / '1.2M' => int euros."""
    if not text:
        return None
    text = re.sub(r"[€£$\s,]", "", text)
    try:
        if text.endswith("M"):
            return int(float(text[:-1]) * 1_000_000)
        if text.endswith("K"):
            return int(float(text[:-1]) * 1_000)
        return int(float(text))
    except ValueError:
        return None


def _height(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"(\d{2,3})\s*cm", text, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)'(\d+)", text)
    if m:
        return int(m.group(1)) * 30 + int(m.group(2)) * 3
    return None


def _weight(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"(\d+)\s*kg", text, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*lbs", text, re.I)
    if m:
        return round(int(m.group(1)) * 0.453592)
    return None


def _int(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None


def _stars(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"(\d)", text)
    if m:
        return int(m.group(1))
    count = text.count("★")
    return count if count > 0 else None


def _infer_group(positions: str) -> str:
    p = (positions or "").upper()
    if "GK" in p:
        return "GK"
    if "CB" in p:
        return "CB"
    if any(x in p for x in ("LB", "RB", "LWB", "RWB")):
        return "FB"
    if any(x in p for x in ("LM", "RM", "LW", "RW")):
        return "WIDE"
    if any(x in p for x in ("ST", "CF", "LF", "RF", "LS", "RS", "SS")):
        return "FWD"
    return "MID"


async def _delay(lo: float = 2.0, hi: float = 5.0):
    await asyncio.sleep(random.uniform(lo, hi))


# ---------------------------------------------------------------------------
# Navigation -- Cloudflare-aware
# ---------------------------------------------------------------------------

async def _goto(page: Page, url: str, retries: int = 5) -> bool:
    for attempt in range(1, retries + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            title = (await page.title()).lower()
            if "just a moment" in title or "cloudflare" in title:
                log.warning(
                    "Cloudflare challenge (attempt %d/%d) on %s", attempt, retries, url
                )
                await asyncio.sleep(10 * attempt)
                continue
            return True
        except PWTimeout:
            log.warning("Timeout (attempt %d/%d) on %s", attempt, retries, url)
            await asyncio.sleep(8 * attempt)
    log.error("Failed to load %s after %d attempts", url, retries)
    return False


async def _block(route, request):

    if request.resource_type in (
        "image",
        "media",
        "font",
        "stylesheet",
        "script"
    ):
        await route.abort()
    else:
        await route.continue_()


# ---------------------------------------------------------------------------
# Phase 1 -- index pages
# ---------------------------------------------------------------------------

async def scrape_index_pages(
    page: Page,
    season: str,
    version_id: Optional[int],
    max_players: int,
) -> list[dict]:
    """
    Collect player hrefs + everything available on the list page.
    List page gives us: sofifa_id, short_name, positions, nationality,
    age, overall, potential, club, league, value, wage, height, weight.
    """
    collected: list[dict] = []
    offset = 0

    while len(collected) < max_players:
        url = f"{BASE_URL}/players?offset={offset}"
        if version_id:
            url += f"&version={version_id}"

        log.info("Index  offset=%-5d  collected=%d", offset, len(collected))
        if not await _goto(page, url):
            break

        rows = await page.query_selector_all("table tbody tr")
        if not rows:
            log.info("No rows at offset %d -- done", offset)
            break

        for row in rows:
            if len(collected) >= max_players:
                break
            entry = await _parse_list_row(row)
            if entry:
                collected.append(entry)

        offset += 60
        await _delay(1.0, 2.5)

    log.info("Index phase done: %d player entries", len(collected))
    return collected


async def _parse_list_row(row) -> Optional[dict]:
    # Player ID from avatar img
    img = await row.query_selector("img.player-check")
    if not img:
        return None

    raw_id = await img.get_attribute("id")
    if not raw_id or not raw_id.isdigit():
        return None
    sofifa_id = int(raw_id)

    # Name link (has data-tooltip with full name, inner text is short name)
    link = await row.query_selector("a.tooltip[href*='/player/']")
    if not link:
        if not await row.query_selector("a[href*='/player/']"):
            return None
        link = await row.query_selector("a[href*='/player/']")
    if not link:
        return None

    href = await link.get_attribute("href")
    short_name = (
        (await link.get_attribute("data-tooltip")) or (await link.inner_text())
    ).strip()

    # Positions -- <a rel="nofollow"> > <span> tags inside td.col-name
    pos_spans = await row.query_selector_all("span.pos")

    positions_list = []
    for s in pos_spans:
        txt = (await s.inner_text()).strip()
        if txt:
            positions_list.append(txt)

    positions = ", ".join(positions_list) if positions_list else None

    # Nationality flag title
    nat_img = await row.query_selector("td.col-name img.flag, img[title]")
    nationality = (await nat_img.get_attribute("title")) if nat_img else None

    # Age
    ae = await row.query_selector("td[data-col='ae']")
    age = _int((await ae.inner_text()).strip()) if ae else None

    # Overall / Potential
    oa = await row.query_selector("td[data-col='oa'] em, td[data-col='oa'] span")
    overall = _int((await oa.inner_text()).strip()) if oa else None

    pt = await row.query_selector("td[data-col='pt'] em, td[data-col='pt'] span")
    potential = _int((await pt.inner_text()).strip()) if pt else None

    # Club
    club_el = await row.query_selector("a[href*='/team/']")
    club_name = (await club_el.inner_text()).strip() if club_el else None

    # League (sub-link below club)
    league_el = await row.query_selector("a[href*='/league/']")
    league_name = (await league_el.inner_text()).strip() if league_el else None

    # Value / Wage
    vl = await row.query_selector("td[data-col='vl']")
    wg = await row.query_selector("td[data-col='wg']")
    value_eur = _money((await vl.inner_text()).strip()) if vl else None
    wage_eur = _money((await wg.inner_text()).strip()) if wg else None

    # Height / Weight (abbreviated on list page)
    hi = await row.query_selector("td[data-col='hi']")
    wi = await row.query_selector("td[data-col='wi']")
    height_cm = _height((await hi.inner_text()).strip()) if hi else None
    weight_kg = _weight((await wi.inner_text()).strip()) if wi else None

    return {
        "sofifa_id": sofifa_id,
        "short_name": short_name,
        "player_positions": positions,
        "nationality_name": nationality,
        "age": age,
        "overall": overall,
        "potential": potential,
        "club_name": club_name,
        "league_name": league_name,
        "value_eur": value_eur,
        "wage_eur": wage_eur,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "href": href,
    }


# ---------------------------------------------------------------------------
# Phase 2 -- player detail page
# ---------------------------------------------------------------------------

# All 34 detailed skill attribute labels -> Player field names.
# Covers both current (EA FC 25/26) and historical label variants.
_ATTR_MAP: dict[str, str] = {
    # attacking
    "crossing":                 "attacking_crossing",
    "finishing":                "attacking_finishing",
    "heading accuracy":         "attacking_heading_accuracy",
    "short passing":            "attacking_short_passing",
    "volleys":                  "attacking_volleys",
    # skill
    "dribbling":                "skill_dribbling",
    "curve":                    "skill_curve",
    "fk accuracy":              "skill_fk_accuracy",
    "long passing":             "skill_long_passing",
    "ball control":             "skill_ball_control",
    # movement
    "acceleration":             "movement_acceleration",
    "sprint speed":             "movement_sprint_speed",
    "agility":                  "movement_agility",
    "reactions":                "movement_reactions",
    "balance":                  "movement_balance",
    # power
    "shot power":               "power_shot_power",
    "jumping":                  "power_jumping",
    "stamina":                  "power_stamina",
    "strength":                 "power_strength",
    "long shots":               "power_long_shots",
    # mentality
    "aggression":               "mentality_aggression",
    "interceptions":            "mentality_interceptions",
    "positioning":              "mentality_positioning",
    "att. pos.":                "mentality_positioning",  # alt label
    "att positioning":          "mentality_positioning",
    "vision":                   "mentality_vision",
    "penalties":                "mentality_penalties",
    "composure":                "mentality_composure",
    # defending
    "defensive awareness":      "defending_marking_awareness",
    "marking awareness":        "defending_marking_awareness",
    "marking":                  "defending_marking_awareness",  # old FIFA label
    "standing tackle":          "defending_standing_tackle",
    "sliding tackle":           "defending_sliding_tackle",
    # goalkeeping
    "gk diving":                "goalkeeping_diving",
    "gk handling":              "goalkeeping_handling",
    "gk kicking":               "goalkeeping_kicking",
    "gk positioning":           "goalkeeping_positioning",
    "gk reflexes":              "goalkeeping_reflexes",
    "gk speed":                 "goalkeeping_speed",
}

# Profile metadata labels -> Player field names
_META_MAP: dict[str, str] = {
    "preferred foot":           "preferred_foot",
    "weak foot":                "weak_foot",
    "skill moves":              "skill_moves",
    "international reputation": "international_reputation",
    "international rep.":       "international_reputation",
    "work rate":                "work_rate",
    "body type":                "body_type",
    "height":                   "height_cm",
    "weight":                   "weight_kg",
    "nationality":              "nationality_name",
    "club":                     "club_name",
    "league":                   "league_name",
    "league level":             "league_level",
    "age":                      "age",
    "value":                    "value_eur",
    "wage":                     "wage_eur",
    "release clause":           "release_clause_eur",
    "release_clause":           "release_clause_eur",
}

# Card stat label aliases -> Player field names
_CARD_MAP: dict[str, str] = {
    "pace": "pace",       "pac": "pace",
    "shooting": "shooting", "sho": "shooting",
    "passing": "passing",  "pas": "passing",
    "dribbling": "dribbling", "dri": "dribbling",
    "defending": "defending", "def": "defending",
    "physical": "physic",  "phy": "physic", "physic": "physic",
}


async def scrape_player_detail(
    page: Page,
    entry: dict,
    season: str,
    version_id: Optional[int],
) -> Player:
    p = Player(sofifa_id=entry["sofifa_id"], season=season)

    # seed with list-page data
    for key in (
        "short_name", "player_positions", "nationality_name", "age",
        "overall", "potential", "club_name", "league_name",
        "value_eur", "wage_eur", "height_cm", "weight_kg",
    ):
        setattr(p, key, entry.get(key))

    p.position_group = _infer_group(p.player_positions or "")

    href = entry["href"]
    url = BASE_URL + href
    if version_id:
        sep = "&" if "?" in href else "?"
        url += f"{sep}version={version_id}"

    if not await _goto(page, url):
        return p

    try:
        # 1. Header section: long name, positions, overall/potential
        await _parse_header(page, p)
        # 2. Metadata grid: foot, work rate, height, weight, etc.
        await _parse_metadata(page, p)
        # 3. Contract / financial: release clause, refined wage/value
        await _parse_financials(page, p)
        # 4. FIFA card stats (PAC/SHO/PAS/DRI/DEF/PHY)
        await _parse_card_stats(page, p)
        # 5. Detailed 34-attribute block
        await _parse_attributes(page, p)
    except Exception as exc:
        log.error("Detail error sofifa_id=%d: %s", p.sofifa_id, exc)

    return p


async def _parse_header(page: Page, p: Player):
    # Long name from <h1>
    h1 = await page.query_selector("h1")
    if h1:
        p.long_name = (await h1.inner_text()).strip()

    # Position badges (current SoFIFA: <span class="pos">ST</span>)
    pos_spans = await page.query_selector_all("span.pos, .player-tag")
    if pos_spans:
        positions = []
        for s in pos_spans:
            t = (await s.inner_text()).strip()
            if t and len(t) <= 4 and re.match(r"^[A-Z]+$", t):
                positions.append(t)
        if positions:
            p.player_positions = ", ".join(positions)
            p.position_group = _infer_group(p.player_positions)

    # Overall / Potential from big numeric displays
    # SoFIFA uses <span class="bp3-tag ...">XX</span> or similar
    score_containers = await page.query_selector_all(
        ".bp3-tag, .player-stats span, .score, [class*='rating']"
    )
    nums = []
    for el in score_containers:
        t = (await el.inner_text()).strip()
        if t.isdigit() and 40 <= int(t) <= 99:
            nums.append(int(t))
    if len(nums) >= 2 and p.overall is None:
        p.overall = nums[0]
        p.potential = nums[1]


async def _parse_metadata(page: Page, p: Player):
    """
    Parse the info grid (label/value pairs) that contains:
    preferred_foot, weak_foot, skill_moves, international_reputation,
    work_rate, body_type, height_cm, weight_kg, release_clause, etc.

    SoFIFA renders this as either:
      <label>Preferred Foot</label><span>Right</span>   (profile card)
      <dt>Height</dt><dd>185cm</dd>                      (definition list)
      <td class="col-lbl">Height</td><td>185cm</td>      (table)
    """
    # Strategy A: label -> next sibling
    for label_el in await page.query_selector_all(
        "label, dt, td.col-lbl, th"
    ):
        label_text = (await label_el.inner_text()).strip().lower()
        # get sibling value
        value_text = await page.evaluate(
            """el => {
                const sib = el.nextElementSibling;
                return sib ? sib.textContent.trim() : null;
            }""",
            label_el,
        )
        if value_text:
            _apply_meta(p, label_text, value_text)

    # Strategy B: scan all visible text for "Label : Value" patterns
    # Some SoFIFA sections use a colon-separated format
    raw_text = await page.evaluate(
        "() => document.body.innerText"
    )
    _scan_body_text(p, raw_text)


def _apply_meta(p: Player, label: str, value: str):
    """Map a label/value pair to the correct Player field."""
    if not value:
        return
    field = _META_MAP.get(label) or _META_MAP.get(label.rstrip(":").strip())
    if not field:
        return

    current = getattr(p, field, None)
    if current is not None:
        return  # don't overwrite already-set values

    if field in ("preferred_foot", "work_rate", "body_type", "nationality_name",
                 "club_name", "league_name"):
        setattr(p, field, value)
    elif field in ("weak_foot", "skill_moves", "international_reputation"):
        setattr(p, field, _stars(value))
    elif field == "height_cm":
        setattr(p, field, _height(value))
    elif field == "weight_kg":
        setattr(p, field, _weight(value))
    elif field in ("value_eur", "wage_eur", "release_clause_eur"):
        setattr(p, field, _money(value))
    elif field in ("age", "league_level"):
        setattr(p, field, _int(value))


def _scan_body_text(p: Player, body: str):
    """
    Scan raw body text for 'Label: value' patterns as a fallback.
    Especially useful for release clause and contract info.
    """
    patterns = {
        "release clause": "release_clause_eur",
        "value":          "value_eur",
        "wage":           "wage_eur",
    }
    for label, field in patterns.items():
        if getattr(p, field) is not None:
            continue
        m = re.search(
            rf"{re.escape(label)}\s*[:\-]?\s*([€£$][\d,.]+[MK]?)",
            body,
            re.I,
        )
        if m:
            setattr(p, field, _money(m.group(1)))


async def _parse_financials(page: Page, p: Player):
    """
    Dedicated pass for the contract/financial section.
    Release clause is ONLY on the detail page, not the list page.
    """
    # Try structured dl/dt/dd
    dts = await page.query_selector_all("dl dt, .contract dt, .player-contract dt")
    for dt in dts:
        label = (await dt.inner_text()).strip().lower()
        dd = await page.evaluate(
            "el => el.nextElementSibling ? el.nextElementSibling.textContent.trim() : null",
            dt,
        )
        if dd:
            _apply_meta(p, label, dd)

    # Also try any element containing EUR symbol near financial keywords
    fin_els = await page.query_selector_all(
        "[class*='contract'], [class*='financial'], [class*='wage'], [class*='value'], [class*='clause']"
    )
    for el in fin_els:
        text = (await el.inner_text()).strip()
        _scan_body_text(p, text)


async def _parse_card_stats(page: Page, p: Player):
    """
    Extract PAC / SHO / PAS / DRI / DEF / PHY card summary stats.
    SoFIFA renders these as text pairs: a label and a number.
    """
    # Use JS to find all adjacent (label, number) pairs matching card stat names
    results: dict = await page.evaluate(
        """
        () => {
            const found = {};
            const aliases = {
                pace: ['pace','pac'],
                shooting: ['shooting','sho'],
                passing: ['passing','pas'],
                dribbling: ['dribbling','dri'],
                defending: ['defending','def'],
                physic: ['physical','physic','phy']
            };
            const els = Array.from(document.querySelectorAll('span, div, em, li, td'));
            for (const el of els) {
                const t = el.textContent.trim().toLowerCase();
                for (const [field, names] of Object.entries(aliases)) {
                    if (names.includes(t)) {
                        // Look for a sibling or nearby number
                        const candidates = [
                            el.previousElementSibling,
                            el.nextElementSibling,
                            el.parentElement && el.parentElement.querySelector('em'),
                            el.parentElement && el.parentElement.querySelector('span'),
                        ];
                        for (const c of candidates) {
                            if (c && c !== el) {
                                const n = parseInt(c.textContent.trim());
                                if (!isNaN(n) && n >= 1 && n <= 99) {
                                    if (!found[field]) found[field] = n;
                                }
                            }
                        }
                    }
                }
            }
            return found;
        }
        """
    )
    for field, val in results.items():
        if getattr(p, field, None) is None:
            setattr(p, field, val)


async def _parse_attributes(page: Page, p: Player):
    """
    Extract all 34 detailed skill attributes from the ul.pl lists.
    SoFIFA HTML structure (confirmed across multiple working scrapers):

      <ul class="pl">
        <li>
          <span class="label p84">84</span>
          Crossing
        </li>
        ...
      </ul>

    We extract via JS for reliability and speed.
    """
    items: list[dict] = await page.evaluate(
        """
        () => {
            const results = [];
            // Primary: ul.pl > li  (the standard SoFIFA attribute list)
            document.querySelectorAll('ul.pl li').forEach(li => {
                const span = li.querySelector('span[class*="label"], span[class*="p"]');
                if (!span) return;
                const valStr = span.textContent.trim();
                const val = parseInt(valStr);
                if (isNaN(val) || val < 1 || val > 99) return;
                // Label is the li text minus the span text
                const label = li.textContent
                    .replace(valStr, '')
                    .trim()
                    .toLowerCase();
                if (label.length > 1) results.push({ label, value: val });
            });

            // Fallback: columns.mb-20 structure (older SoFIFA)
            if (results.length === 0) {
                document.querySelectorAll('.columns.mb-20 li').forEach(li => {
                    const span = li.querySelector('span');
                    if (!span) return;
                    const val = parseInt(span.textContent.trim());
                    if (isNaN(val) || val < 1 || val > 99) return;
                    const label = li.textContent
                        .replace(span.textContent, '')
                        .trim()
                        .toLowerCase();
                    if (label.length > 1) results.push({ label, value: val });
                });
            }

            // Fallback 2: table rows with (number, ..., label) pattern
            if (results.length === 0) {
                document.querySelectorAll('tr').forEach(tr => {
                    const tds = tr.querySelectorAll('td');
                    if (tds.length < 2) return;
                    const val = parseInt(tds[0].textContent.trim());
                    if (isNaN(val) || val < 1 || val > 99) return;
                    const label = tds[tds.length - 1].textContent.trim().toLowerCase();
                    if (label.length > 2) results.push({ label, value: val });
                });
            }

            return results;
        }
        """
    )

    for item in items:
        label = item["label"].strip()
        field = _ATTR_MAP.get(label)
        if field and getattr(p, field) is None:
            setattr(p, field, item["value"])


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------

def _build_upsert() -> str:
    cols = list(Player.__dataclass_fields__.keys())
    names = ", ".join(cols)
    placeholders = ", ".join(f"%({c})s" for c in cols)
    updates = ", ".join(
        f"{c} = EXCLUDED.{c}"
        for c in cols
        if c not in ("sofifa_id", "season")
    )
    return (
        f"INSERT INTO player_season_stats ({names})\n"
        f"VALUES ({placeholders})\n"
        f"ON CONFLICT (sofifa_id, season)\n"
        f"DO UPDATE SET {updates}, scraped_at = NOW()"
    )


_UPSERT = _build_upsert()


def upsert_player(conn, player: Player):
    with conn.cursor() as cur:
        cur.execute(_UPSERT, asdict(player))
    conn.commit()


def _log_start(conn, season: str, version_id: Optional[int]) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO scrape_log (season, sofifa_version, status) "
            "VALUES (%s, %s, 'running') RETURNING id",
            (season, version_id),
        )
        lid = cur.fetchone()[0]
    conn.commit()
    return lid


def _log_done(conn, lid: int, total: int):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE scrape_log SET status='completed', "
            "completed_at=NOW(), total_players=%s WHERE id=%s",
            (total, lid),
        )
    conn.commit()


def _log_fail(conn, lid: int, err: str):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE scrape_log SET status='failed', error_message=%s WHERE id=%s",
            (err, lid),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
async def run_scrape(season: str, version_id: Optional[int], max_players: int):
    conn = psycopg2.connect(DATABASE_URL)
    lid = _log_start(conn, season, version_id)

    saved = 0
    offset = 0

    try:
        async with async_playwright() as pw:

            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            ctx = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 900},
                locale="en-US",
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )

            await ctx.route("**/*", _block)

            page = await ctx.new_page()

            while saved < max_players:

                url = f"{BASE_URL}/players?offset={offset}"
                if version_id:
                    url += f"&version={version_id}"

                log.info("Index  offset=%-5d  saved=%d", offset, saved)

                if not await _goto(page, url):
                    break

                rows = await page.query_selector_all("table tbody tr")

                if not rows:
                    break

                # IMPORTANT: extract entries BEFORE navigation
                entries = []
                for row in rows:
                    entry = await _parse_list_row(row)
                    if entry:
                        entries.append(entry)

                with conn.cursor() as cur:

                    for entry in entries:

                        if saved >= max_players:
                            break

                        log.info(
                            "[%d] %-30s sofifa_id=%d",
                            saved + 1,
                            entry.get("short_name", "?"),
                            entry["sofifa_id"],
                        )

                        player = await scrape_player_detail(
                            page,
                            entry,
                            season,
                            version_id,
                        )

                        cur.execute(_UPSERT, asdict(player))
                        saved += 1

                        await _delay(2.0, 5.0)

                conn.commit()

                log.info("--- page committed: total saved=%d ---", saved)

                offset += 60

            await browser.close()

        _log_done(conn, lid, saved)

        log.info("Scrape complete -- %d players saved (season=%s)", saved, season)

    except Exception as exc:
        log.exception("Scrape aborted")
        _log_fail(conn, lid, str(exc))
        raise

    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="SoFIFA Playwright scraper")
    parser.add_argument(
        "--season", default="2025/26",
        help="Season label, e.g. '2025/26'",
    )
    parser.add_argument(
        "--version", type=int, default=None,
        help=(
            "SoFIFA version ID (e.g. 240072 for EA FC 25). "
            "Omit for the live current season."
        ),
    )
    parser.add_argument(
        "--max", type=int, default=5000, dest="max_players",
        help="Max players to scrape per run (default: 5000)",
    )
    args = parser.parse_args()

    version_id = args.version
    if version_id is None:
        version_id = SEASON_VERSIONS.get(args.season)

    log.info(
        "Starting -- season=%s  version=%s  max=%d",
        args.season, version_id, args.max_players,
    )
    asyncio.run(run_scrape(args.season, version_id, args.max_players))


if __name__ == "__main__":
    main()
