"""
Mock data generator — realistic player data for testing without scraping SoFIFA.

Generates 500 players × 3 seasons = 1500 rows, covering every column
in player_season_stats. Values use position-specific distributions that
match real FIFA data patterns (attackers have higher pace, CBs higher
strength, etc.).

Usage:
    python mock_data_generator.py            # 500 players, all 3 seasons
    python mock_data_generator.py --n 100    # quick test with 100 players
"""

import argparse
import logging
import os
import random

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://soccer:soccer123@localhost:5432/soccersolver",
)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

LEAGUES = {
    "Premier League": [
        "Manchester City", "Arsenal", "Liverpool", "Chelsea",
        "Manchester United", "Tottenham", "Newcastle", "Aston Villa",
        "Brighton", "Brentford",
    ],
    "La Liga": [
        "Real Madrid", "Barcelona", "Atletico Madrid", "Sevilla",
        "Real Betis", "Valencia", "Athletic Club", "Real Sociedad",
        "Villarreal", "Getafe",
    ],
    "Bundesliga": [
        "Bayern Munich", "Borussia Dortmund", "RB Leipzig", "Leverkusen",
        "Frankfurt", "Stuttgart", "Wolfsburg", "Freiburg",
        "Union Berlin", "Augsburg",
    ],
    "Serie A": [
        "Inter Milan", "AC Milan", "Juventus", "Napoli", "Roma",
        "Lazio", "Atalanta", "Fiorentina", "Torino", "Bologna",
    ],
    "Ligue 1": [
        "PSG", "Marseille", "Monaco", "Lille", "Lyon",
        "Nice", "Lens", "Rennes", "Toulouse", "Brest",
    ],
}

NATIONALITIES = [
    "Spanish", "French", "German", "Brazilian", "Argentine", "English",
    "Portuguese", "Italian", "Dutch", "Belgian", "Croatian", "Polish",
    "Senegalese", "Moroccan", "Nigerian", "Japanese", "Korean", "Colombian",
    "Uruguayan", "Mexican", "Ivorian", "Ghanaian", "Algerian", "Serbian",
]

POSITIONS = {
    "GK":   ["GK"],
    "CB":   ["CB"],
    "FB":   ["LB", "RB", "LWB", "RWB"],
    "MID":  ["CM", "CDM", "CAM"],
    "WIDE": ["LM", "RM", "LW", "RW"],
    "FWD":  ["ST", "CF"],
}

FIRST_NAMES = [
    "Liam", "Noah", "Oliver", "Elijah", "James", "Mateo", "Lucas", "Luca",
    "Santiago", "Gabriel", "Marco", "Carlos", "Diego", "Luis", "Andre",
    "Kai", "Theo", "Finn", "Jack", "Harry", "Jude", "Phil", "Declan",
    "Antoine", "Kylian", "Ousmane", "Riyad", "Sadio", "Mohamed", "Vinicius",
    "Rodrygo", "Federico", "Pedri", "Gavi", "Dani", "Xavi", "Ilkay",
    "Toni", "Joshua", "Leroy", "Thomas", "Kingsley", "Eduardo", "Rafael",
    "Bruno", "Ruben", "Bernardo", "Joao", "Erling", "Florian", "Jamal",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Silva", "Santos", "Ferreira",
    "Garcia", "Martinez", "Rodriguez", "Hernandez", "Lopez", "Gonzalez",
    "Mueller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer",
    "Rossi", "Ferrari", "Ricci", "Bianchi", "Romano", "Esposito",
    "Dupont", "Martin", "Bernard", "Thomas", "Robert", "Petit",
    "de Bruyne", "van Dijk", "Mane", "Diallo", "Kounde", "Mendes",
    "Dias", "Cancelo", "Fernandez", "Torres", "Ramos", "Pique",
    "Bellingham", "Saka", "Salah", "Mbappe", "Haaland", "Wirtz",
]

BODY_TYPES = ["Normal", "Lean", "Stocky", "Unique"]
WORK_RATES = ["High/High", "High/Medium", "High/Low",
              "Medium/High", "Medium/Medium", "Medium/Low",
              "Low/High", "Low/Medium", "Low/Low"]
SEASONS = ["2022/23", "2023/24", "2025/26"]

# Positional stat profiles: (base, variance) for each card stat
#                          PAC   SHO   PAS   DRI   DEF   PHY
_CARD_PROFILES = {
    "GK":   [(50,10), (18, 6), (55,10), (33, 8), (28, 8), (65, 8)],
    "CB":   [(67,12), (44,10), (65,10), (58,10), (78, 6), (74, 7)],
    "FB":   [(78, 8), (54,10), (68,10), (65, 8), (68, 8), (70, 8)],
    "MID":  [(68,10), (64,10), (75, 7), (73, 8), (58, 9), (68, 8)],
    "WIDE": [(82, 7), (72, 8), (70, 8), (79, 6), (43,12), (62,10)],
    "FWD":  [(76, 8), (80, 6), (68, 9), (75, 7), (38,12), (70, 9)],
}

# Positional attribute profiles: (base_offset_from_overall, variance)
# offset is added to overall to get the base value for that attribute
_ATTR_PROFILES: dict[str, dict[str, tuple[int, int]]] = {
    "GK": {
        "goalkeeping_diving":          ( 0,  4),
        "goalkeeping_handling":        ( 0,  4),
        "goalkeeping_kicking":         (-4,  7),
        "goalkeeping_positioning":     ( 0,  4),
        "goalkeeping_reflexes":        ( 1,  4),
        "goalkeeping_speed":           (-12, 15),
        "movement_reactions":          (-3,  5),
        "power_strength":              (-8,  8),
        "mentality_composure":         (-5,  6),
        "attacking_short_passing":     (-15, 10),
        "movement_agility":            (-20, 12),
        "movement_balance":            (-20, 12),
        "skill_ball_control":          (-25, 12),
        "defending_standing_tackle":   (-30, 12),
        "defending_sliding_tackle":    (-30, 12),
        "defending_marking_awareness": (-35, 12),
        # outfield (very low for GK)
        "attacking_crossing":          (-40, 10),
        "attacking_finishing":         (-50,  8),
        "attacking_heading_accuracy":  (-20, 12),
        "attacking_volleys":           (-50,  8),
        "skill_dribbling":             (-40, 10),
        "skill_curve":                 (-40, 10),
        "skill_fk_accuracy":           (-40, 10),
        "skill_long_passing":          (-20, 10),
        "movement_acceleration":       (-25, 12),
        "movement_sprint_speed":       (-25, 12),
        "power_shot_power":            (-30, 10),
        "power_jumping":               (-20, 12),
        "power_stamina":               (-20, 12),
        "power_long_shots":            (-45, 10),
        "mentality_aggression":        (-20, 12),
        "mentality_interceptions":     (-25, 12),
        "mentality_positioning":       (-40, 10),
        "mentality_vision":            (-20, 12),
        "mentality_penalties":         (-40, 10),
    },
    "CB": {
        "defending_marking_awareness": ( 1,  4),
        "defending_standing_tackle":   ( 0,  4),
        "defending_sliding_tackle":    (-1,  5),
        "mentality_interceptions":     (-1,  4),
        "power_strength":              (-1,  5),
        "power_jumping":               (-2,  6),
        "attacking_heading_accuracy":  (-3,  6),
        "movement_reactions":          (-4,  6),
        "mentality_composure":         (-4,  6),
        "attacking_short_passing":     (-8,  8),
        "skill_ball_control":          (-10, 8),
        "skill_long_passing":          (-8,  8),
        "mentality_vision":            (-10, 8),
        "power_stamina":               (-8,  8),
        "movement_acceleration":       (-15, 10),
        "movement_sprint_speed":       (-12, 10),
        "movement_agility":            (-18, 10),
        "movement_balance":            (-18, 10),
        "mentality_aggression":        (-5,  8),
        "attacking_crossing":          (-20, 10),
        "attacking_finishing":         (-30, 10),
        "attacking_volleys":           (-30, 10),
        "skill_dribbling":             (-18, 10),
        "skill_curve":                 (-25, 10),
        "skill_fk_accuracy":           (-25, 10),
        "power_shot_power":            (-20, 10),
        "power_long_shots":            (-25, 10),
        "mentality_positioning":       (-20, 10),
        "mentality_penalties":         (-25, 10),
        "goalkeeping_diving":          (-50,  5),
        "goalkeeping_handling":        (-50,  5),
        "goalkeeping_kicking":         (-40,  8),
        "goalkeeping_positioning":     (-50,  5),
        "goalkeeping_reflexes":        (-50,  5),
        "goalkeeping_speed":           (-30, 10),
    },
    "FB": {
        "movement_acceleration":       ( 0,  5),
        "movement_sprint_speed":       ( 0,  5),
        "attacking_crossing":          (-2,  6),
        "defending_standing_tackle":   (-3,  5),
        "defending_marking_awareness": (-2,  5),
        "mentality_interceptions":     (-3,  5),
        "attacking_short_passing":     (-5,  7),
        "movement_reactions":          (-4,  6),
        "power_stamina":               (-4,  6),
        "movement_agility":            (-6,  7),
        "movement_balance":            (-8,  7),
        "skill_ball_control":          (-8,  7),
        "mentality_vision":            (-10, 8),
        "power_strength":              (-8,  8),
        "defending_sliding_tackle":    (-5,  6),
        "skill_dribbling":             (-10, 8),
        "mentality_composure":         (-8,  7),
        "mentality_aggression":        (-6,  7),
        "attacking_finishing":         (-25, 10),
        "attacking_volleys":           (-25, 10),
        "attacking_heading_accuracy":  (-15, 10),
        "skill_curve":                 (-20, 10),
        "skill_fk_accuracy":           (-20, 10),
        "skill_long_passing":          (-12, 8),
        "power_shot_power":            (-18, 10),
        "power_jumping":               (-15, 10),
        "power_long_shots":            (-22, 10),
        "mentality_positioning":       (-18, 10),
        "mentality_penalties":         (-22, 10),
        "goalkeeping_diving":          (-50,  5),
        "goalkeeping_handling":        (-50,  5),
        "goalkeeping_kicking":         (-40,  8),
        "goalkeeping_positioning":     (-50,  5),
        "goalkeeping_reflexes":        (-50,  5),
        "goalkeeping_speed":           (-30, 10),
    },
    "MID": {
        "mentality_vision":            ( 0,  5),
        "attacking_short_passing":     ( 0,  4),
        "skill_ball_control":          (-1,  5),
        "mentality_composure":         (-2,  5),
        "skill_long_passing":          (-2,  6),
        "movement_reactions":          (-3,  5),
        "power_stamina":               (-3,  6),
        "movement_agility":            (-5,  7),
        "movement_balance":            (-6,  7),
        "skill_dribbling":             (-5,  7),
        "mentality_interceptions":     (-8,  8),
        "defending_marking_awareness": (-10, 8),
        "defending_standing_tackle":   (-12, 8),
        "movement_acceleration":       (-10, 8),
        "movement_sprint_speed":       (-10, 8),
        "power_strength":              (-12, 8),
        "mentality_aggression":        (-8,  8),
        "attacking_crossing":          (-10, 8),
        "attacking_finishing":         (-15, 8),
        "attacking_volleys":           (-15, 8),
        "attacking_heading_accuracy":  (-15, 8),
        "skill_curve":                 (-12, 8),
        "skill_fk_accuracy":           (-12, 8),
        "power_shot_power":            (-12, 8),
        "power_jumping":               (-12, 8),
        "power_long_shots":            (-12, 8),
        "mentality_positioning":       (-8,  7),
        "mentality_penalties":         (-15, 8),
        "defending_sliding_tackle":    (-12, 8),
        "goalkeeping_diving":          (-50,  5),
        "goalkeeping_handling":        (-50,  5),
        "goalkeeping_kicking":         (-40,  8),
        "goalkeeping_positioning":     (-50,  5),
        "goalkeeping_reflexes":        (-50,  5),
        "goalkeeping_speed":           (-30, 10),
    },
    "WIDE": {
        "movement_acceleration":       ( 1,  4),
        "movement_sprint_speed":       ( 1,  4),
        "skill_dribbling":             ( 0,  4),
        "skill_ball_control":          (-1,  5),
        "attacking_crossing":          (-3,  6),
        "movement_agility":            (-2,  5),
        "movement_balance":            (-3,  6),
        "attacking_finishing":         (-5,  7),
        "movement_reactions":          (-4,  6),
        "mentality_composure":         (-4,  6),
        "skill_curve":                 (-5,  7),
        "power_stamina":               (-6,  7),
        "mentality_vision":            (-6,  7),
        "attacking_volleys":           (-10, 8),
        "attacking_short_passing":     (-8,  7),
        "skill_fk_accuracy":           (-8,  8),
        "power_shot_power":            (-8,  8),
        "power_long_shots":            (-10, 8),
        "mentality_positioning":       (-6,  7),
        "power_strength":              (-15, 10),
        "power_jumping":               (-15, 10),
        "defending_marking_awareness": (-30, 10),
        "defending_standing_tackle":   (-30, 10),
        "defending_sliding_tackle":    (-30, 10),
        "mentality_interceptions":     (-25, 10),
        "mentality_aggression":        (-10, 8),
        "attacking_heading_accuracy":  (-15, 10),
        "skill_long_passing":          (-12, 8),
        "mentality_penalties":         (-12, 8),
        "goalkeeping_diving":          (-50,  5),
        "goalkeeping_handling":        (-50,  5),
        "goalkeeping_kicking":         (-40,  8),
        "goalkeeping_positioning":     (-50,  5),
        "goalkeeping_reflexes":        (-50,  5),
        "goalkeeping_speed":           (-30, 10),
    },
    "FWD": {
        "attacking_finishing":         ( 0,  4),
        "mentality_positioning":       ( 0,  4),
        "mentality_composure":         (-2,  5),
        "movement_reactions":          (-3,  5),
        "attacking_heading_accuracy":  (-4,  7),
        "power_shot_power":            (-3,  6),
        "movement_acceleration":       (-5,  7),
        "movement_sprint_speed":       (-5,  7),
        "power_strength":              (-6,  8),
        "attacking_volleys":           (-5,  7),
        "skill_dribbling":             (-6,  7),
        "skill_ball_control":          (-7,  7),
        "movement_agility":            (-8,  8),
        "movement_balance":            (-8,  8),
        "power_long_shots":            (-8,  8),
        "power_jumping":               (-8,  8),
        "power_stamina":               (-8,  8),
        "attacking_short_passing":     (-12, 8),
        "attacking_crossing":          (-15, 8),
        "skill_curve":                 (-10, 8),
        "skill_fk_accuracy":           (-12, 8),
        "skill_long_passing":          (-15, 8),
        "mentality_vision":            (-12, 8),
        "mentality_aggression":        (-8,  8),
        "mentality_penalties":         (-8,  8),
        "defending_marking_awareness": (-38, 10),
        "defending_standing_tackle":   (-38, 10),
        "defending_sliding_tackle":    (-38, 10),
        "mentality_interceptions":     (-30, 10),
        "goalkeeping_diving":          (-50,  5),
        "goalkeeping_handling":        (-50,  5),
        "goalkeeping_kicking":         (-40,  8),
        "goalkeeping_positioning":     (-50,  5),
        "goalkeeping_reflexes":        (-50,  5),
        "goalkeeping_speed":           (-30, 10),
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp(v: int, lo: int = 1, hi: int = 99) -> int:
    return max(lo, min(hi, v))


def _rs(base: int, variance: int) -> int:
    return _clamp(base + random.randint(-variance, variance))


def _market_value(overall: int, age: int) -> int:
    """Estimate market value based on overall + age curve."""
    peak_factor = max(0.05, 1.0 - abs(age - 26) * 0.04)
    base = max(100_000, (overall - 55) ** 2.8 * 900 * peak_factor)
    return int(base * random.uniform(0.75, 1.35))


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------

# All 34 attribute field names (every non-GK specific one + GK specific)
_ALL_ATTRS = list(_ATTR_PROFILES["MID"].keys())

def generate_player(sofifa_id: int, season: str, seed_info: dict) -> dict:
    """
    Generate one realistic player row covering all 65 player_season_stats columns.
    seed_info contains stable attributes (name, pos_group, base_overall, league, etc.)
    that remain consistent across seasons for the same player.
    """
    random.seed(sofifa_id + hash(season) % 99991)

    pos_group = seed_info["pos_group"]
    league    = seed_info["league"]
    clubs     = LEAGUES[league]
    club      = seed_info["club"]

    # Season progression — young players improve, old ones decline
    season_idx = SEASONS.index(season)
    age_now = seed_info["base_age"] + season_idx
    ovr_delta = 0
    if age_now < 24:
        ovr_delta = season_idx * random.randint(1, 3)
    elif age_now > 30:
        ovr_delta = season_idx * random.randint(-2, 0)
    overall = _clamp(seed_info["base_overall"] + ovr_delta)

    potential = _clamp(overall + max(0, random.randint(0, max(0, 30 - age_now))))

    # Market value (grows with seasons for young players)
    value = _market_value(overall, age_now)
    season_mult = [0.82, 0.91, 1.0][season_idx]
    if age_now < 25:
        season_mult += season_idx * 0.06
    value = int(value * season_mult)
    wage  = max(500, int(value / 950 * random.uniform(0.85, 1.4)))
    release_clause = int(value * random.uniform(1.5, 2.5)) if overall > 70 else None

    # FIFA card stats from position profile
    card_bases = _CARD_PROFILES[pos_group]
    stat_names = ["pace", "shooting", "passing", "dribbling", "defending", "physic"]
    card_stats = {name: _rs(_clamp(base), var) for name, (base, var) in zip(stat_names, card_bases)}
    # Replace generic base with overall-relative base for realism
    # (card stats are roughly centered on overall for most positions)
    for i, name in enumerate(stat_names):
        raw_base, var = card_bases[i]
        # blend between fixed base and overall-centered
        blended_base = int(0.4 * raw_base + 0.6 * (overall + raw_base - 65))
        card_stats[name] = _rs(_clamp(blended_base), var)

    # Detailed attribute stats from position profile
    attr_profile = _ATTR_PROFILES[pos_group]
    attrs: dict[str, int] = {}
    for attr, (offset, var) in attr_profile.items():
        attrs[attr] = _rs(_clamp(overall + offset), var)

    # Any attributes not in the profile get a generic middle value
    for attr in _ALL_ATTRS:
        if attr not in attrs:
            attrs[attr] = _rs(55, 10)

    return {
        # Key
        "sofifa_id":                    sofifa_id,
        "season":                       season,

        # Identity
        "short_name":                   seed_info["name"],
        "long_name":                    seed_info["name"],
        "player_positions":             seed_info["positions"],
        "overall":                      overall,
        "potential":                    potential,
        "age":                          age_now,

        # Club
        "club_name":                    club,
        "league_name":                  league,
        "league_level":                 1,

        # Nationality
        "nationality_name":             seed_info["nationality"],

        # Physical / profile
        "preferred_foot":               seed_info["foot"],
        "weak_foot":                    random.randint(1, 5),
        "skill_moves":                  random.randint(1, 5),
        "international_reputation":     random.choices([1,2,3,4,5], weights=[45,25,15,10,5])[0],
        "work_rate":                    random.choice(WORK_RATES),
        "body_type":                    random.choice(BODY_TYPES),
        "height_cm":                    seed_info["height"],
        "weight_kg":                    seed_info["weight"],

        # Economic
        "value_eur":                    value,
        "wage_eur":                     wage,
        "release_clause_eur":           release_clause,

        # Card stats
        **card_stats,

        # Detailed attributes (34 cols)
        "attacking_crossing":           attrs["attacking_crossing"],
        "attacking_finishing":          attrs["attacking_finishing"],
        "attacking_heading_accuracy":   attrs["attacking_heading_accuracy"],
        "attacking_short_passing":      attrs["attacking_short_passing"],
        "attacking_volleys":            attrs["attacking_volleys"],
        "skill_dribbling":              attrs["skill_dribbling"],
        "skill_curve":                  attrs["skill_curve"],
        "skill_fk_accuracy":            attrs["skill_fk_accuracy"],
        "skill_long_passing":           attrs["skill_long_passing"],
        "skill_ball_control":           attrs["skill_ball_control"],
        "movement_acceleration":        attrs["movement_acceleration"],
        "movement_sprint_speed":        attrs["movement_sprint_speed"],
        "movement_agility":             attrs["movement_agility"],
        "movement_reactions":           attrs["movement_reactions"],
        "movement_balance":             attrs["movement_balance"],
        "power_shot_power":             attrs["power_shot_power"],
        "power_jumping":                attrs["power_jumping"],
        "power_stamina":                attrs["power_stamina"],
        "power_strength":               attrs["power_strength"],
        "power_long_shots":             attrs["power_long_shots"],
        "mentality_aggression":         attrs["mentality_aggression"],
        "mentality_interceptions":      attrs["mentality_interceptions"],
        "mentality_positioning":        attrs["mentality_positioning"],
        "mentality_vision":             attrs["mentality_vision"],
        "mentality_penalties":          attrs["mentality_penalties"],
        "mentality_composure":          attrs["mentality_composure"],
        "defending_marking_awareness":  attrs["defending_marking_awareness"],
        "defending_standing_tackle":    attrs["defending_standing_tackle"],
        "defending_sliding_tackle":     attrs["defending_sliding_tackle"],
        "goalkeeping_diving":           attrs["goalkeeping_diving"],
        "goalkeeping_handling":         attrs["goalkeeping_handling"],
        "goalkeeping_kicking":          attrs["goalkeeping_kicking"],
        "goalkeeping_positioning":      attrs["goalkeeping_positioning"],
        "goalkeeping_reflexes":         attrs["goalkeeping_reflexes"],
        "goalkeeping_speed":            attrs["goalkeeping_speed"],

        # ML-derived (set from positions; refined by pipeline later)
        "position_group":               pos_group,
    }


def create_player_pool(n: int) -> list[dict]:
    """
    Create a stable player pool: identity attributes that don't change
    across seasons (name, nationality, position, height, weight, foot).
    """
    pool = []
    pos_weights = [5, 15, 15, 25, 20, 20]  # GK CB FB MID WIDE FWD
    pos_groups = list(POSITIONS.keys())

    for i in range(n):
        pos_group = random.choices(pos_groups, weights=pos_weights)[0]
        pos = random.choice(POSITIONS[pos_group])
        league = random.choice(list(LEAGUES.keys()))
        club = random.choice(LEAGUES[league])

        # Height/weight by position
        if pos_group == "GK":
            height = random.randint(183, 198)
            weight = random.randint(78, 95)
        elif pos_group in ("CB", "FWD"):
            height = random.randint(175, 195)
            weight = random.randint(75, 92)
        elif pos_group == "WIDE":
            height = random.randint(165, 182)
            weight = random.randint(65, 80)
        else:
            height = random.randint(170, 190)
            weight = random.randint(68, 86)

        pool.append({
            "sofifa_id":    200_000 + i,
            "name":         f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            "pos_group":    pos_group,
            "positions":    pos,
            "nationality":  random.choice(NATIONALITIES),
            "league":       league,
            "club":         club,
            "base_overall": random.randint(58, 90),
            "base_age":     random.randint(17, 34),
            "height":       height,
            "weight":       weight,
            "foot":         random.choices(["Right", "Left"], weights=[75, 25])[0],
        })

    return pool


def generate_and_insert(n_players: int = 500) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    random.seed(42)
    pool = create_player_pool(n_players)

    # Verify schema columns before inserting
    sample = generate_player(pool[0]["sofifa_id"], SEASONS[0], pool[0])
    schema_cols = [
        "sofifa_id","season","short_name","long_name","player_positions",
        "overall","potential","age","club_name","league_name","league_level",
        "nationality_name","preferred_foot","weak_foot","skill_moves",
        "international_reputation","work_rate","body_type","height_cm","weight_kg",
        "value_eur","wage_eur","release_clause_eur",
        "pace","shooting","passing","dribbling","defending","physic",
        "attacking_crossing","attacking_finishing","attacking_heading_accuracy",
        "attacking_short_passing","attacking_volleys",
        "skill_dribbling","skill_curve","skill_fk_accuracy",
        "skill_long_passing","skill_ball_control",
        "movement_acceleration","movement_sprint_speed","movement_agility",
        "movement_reactions","movement_balance",
        "power_shot_power","power_jumping","power_stamina",
        "power_strength","power_long_shots",
        "mentality_aggression","mentality_interceptions","mentality_positioning",
        "mentality_vision","mentality_penalties","mentality_composure",
        "defending_marking_awareness","defending_standing_tackle","defending_sliding_tackle",
        "goalkeeping_diving","goalkeeping_handling","goalkeeping_kicking",
        "goalkeeping_positioning","goalkeeping_reflexes","goalkeeping_speed",
        "position_group",
    ]
    missing = [c for c in schema_cols if c not in sample]
    if missing:
        raise ValueError(f"generate_player() missing columns: {missing}")
    log.info("Schema check: all %d columns present", len(schema_cols))

    # Build upsert SQL
    cols = schema_cols
    col_names    = ", ".join(cols)
    placeholders = ", ".join(f"%({c})s" for c in cols)
    updates      = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in cols if c not in ("sofifa_id", "season")
    )
    upsert_sql = (
        f"INSERT INTO player_season_stats ({col_names}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT (sofifa_id, season) "
        f"DO UPDATE SET {updates}, scraped_at = NOW()"
    )

    total = 0
    for season in SEASONS:
        log.info("Generating season %s (%d players)…", season, n_players)
        rows = [generate_player(p["sofifa_id"], season, p) for p in pool]

        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, upsert_sql, rows, page_size=200)

            # Log the scrape as completed
            cur.execute("""
                INSERT INTO scrape_log (season, status, total_players, completed_at)
                VALUES (%s, 'completed', %s, NOW())
                ON CONFLICT DO NOTHING
            """, (season, n_players))

        conn.commit()
        total += len(rows)
        log.info("  → %d rows inserted/updated", len(rows))

    conn.close()
    log.info("Mock generation complete: %d total rows across %d seasons", total, len(SEASONS))


def main():
    parser = argparse.ArgumentParser(description="SoccerSolver mock data generator")
    parser.add_argument("--n", type=int, default=500, help="Number of players (default 500)")
    args = parser.parse_args()
    generate_and_insert(args.n)


if __name__ == "__main__":
    main()
