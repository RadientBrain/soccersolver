"""
SoccerSolver FastAPI backend.
All endpoints for player search, similarity, profiles, and analytics.
"""
from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://soccer:soccer123@localhost:5432/soccersolver")

app = FastAPI(title="SoccerSolver API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()


# ─── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ─── Meta ──────────────────────────────────────────────────────────────────────

@app.get("/api/seasons")
def get_seasons(conn=Depends(get_conn)):
    """List all available seasons."""
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT season FROM player_season_stats ORDER BY season DESC")
        return [r["season"] for r in cur.fetchall()]


@app.get("/api/leagues")
def get_leagues(season: str = "2025/26", conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT league_name FROM player_season_stats
            WHERE season = %s AND league_name IS NOT NULL
            ORDER BY league_name
        """, (season,))
        return [r["league_name"] for r in cur.fetchall()]


@app.get("/api/data-freshness")
def get_freshness(conn=Depends(get_conn)):
    """Return scrape log — last update times per season."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT season, status, completed_at, total_players, error_message
            FROM scrape_log
            ORDER BY season DESC, completed_at DESC
        """)
        return cur.fetchall()


# ─── Player Search ─────────────────────────────────────────────────────────────

@app.get("/api/players/search")
def search_players(
    q: str = Query(default="", description="Player name search"),
    season: str = Query(default="2025/26"),
    position: Optional[str] = None,
    league: Optional[str] = None,
    nationality: Optional[str] = None,
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    wage_max: Optional[int] = None,
    value_max: Optional[int] = None,
    release_clause_max: Optional[int] = None,
    overall_min: Optional[int] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    conn=Depends(get_conn),
):
    """
    Search players with advanced filters.
    Supports fuzzy name search + all paper's context filters.
    """
    conditions = ["season = %s"]
    params = [season]

    if q:
        conditions.append("""
            (short_name ILIKE %s OR long_name ILIKE %s
             OR to_tsvector('english', COALESCE(short_name,'') || ' ' || COALESCE(long_name,''))
                @@ plainto_tsquery('english', %s))
        """)
        params.extend([f"%{q}%", f"%{q}%", q])

    if position:
        conditions.append("(position_group = %s OR player_positions ILIKE %s)")
        params.extend([position, f"%{position}%"])
    if league:
        conditions.append("league_name ILIKE %s")
        params.append(f"%{league}%")
    if nationality:
        conditions.append("nationality_name ILIKE %s")
        params.append(f"%{nationality}%")
    if age_min is not None:
        conditions.append("age >= %s")
        params.append(age_min)
    if age_max is not None:
        conditions.append("age <= %s")
        params.append(age_max)
    if wage_max is not None:
        conditions.append("(wage_eur IS NULL OR wage_eur <= %s)")
        params.append(wage_max)
    if value_max is not None:
        conditions.append("(value_eur IS NULL OR value_eur <= %s)")
        params.append(value_max)
    if release_clause_max is not None:
        conditions.append("(release_clause_eur IS NULL OR release_clause_eur <= %s)")
        params.append(release_clause_max)
    if overall_min is not None:
        conditions.append("overall >= %s")
        params.append(overall_min)

    where = " AND ".join(conditions)

    # Count
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) as total FROM player_season_stats WHERE {where}", params)
        total = cur.fetchone()["total"]

    # Fetch
    params_with_limit = params + [limit, offset]
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT sofifa_id, short_name, long_name, player_positions, position_group,
                   overall, potential, age, club_name, league_name, nationality_name,
                   value_eur, wage_eur, release_clause_eur, uniqueness_index,
                   pace, shooting, passing, dribbling, defending, physic
            FROM player_season_stats
            WHERE {where}
            ORDER BY overall DESC NULLS LAST
            LIMIT %s OFFSET %s
        """, params_with_limit)
        players = cur.fetchall()

    return {"total": total, "players": players, "limit": limit, "offset": offset}


# ─── Player Profile ─────────────────────────────────────────────────────────────

@app.get("/api/players/{sofifa_id}")
def get_player(sofifa_id: int, season: str = "2025/26", conn=Depends(get_conn)):
    """Full player profile for a given season."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT * FROM player_season_stats
            WHERE sofifa_id = %s AND season = %s
        """, (sofifa_id, season))
        player = cur.fetchone()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


@app.get("/api/players/{sofifa_id}/history")
def get_player_history(sofifa_id: int, conn=Depends(get_conn)):
    """
    Player historical evolution across all seasons.
    Returns economic and performance data per season.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT season, overall, potential, age, club_name, league_name,
                   value_eur, wage_eur, release_clause_eur,
                   pace, shooting, passing, dribbling, defending, physic,
                   uniqueness_index, cluster_id,
                   pca_component_1, pca_component_2
            FROM player_season_stats
            WHERE sofifa_id = %s
            ORDER BY season ASC
        """, (sofifa_id,))
        history = cur.fetchall()

    if not history:
        raise HTTPException(status_code=404, detail="Player not found")
    return history


# ─── Similarity ────────────────────────────────────────────────────────────────

@app.get("/api/players/{sofifa_id}/similar")
def get_similar_players(
    sofifa_id: int,
    season: str = Query(default="2025/26"),
    top_n: int = Query(default=10, le=50),
    league: Optional[str] = None,
    nationality: Optional[str] = None,
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    wage_max: Optional[int] = None,
    value_max: Optional[int] = None,
    release_clause_max: Optional[int] = None,
    conn=Depends(get_conn),
):
    """
    Get top-N similar players with all context filters from the paper.
    Uses pre-computed similarity cache.
    """
    # Check player exists
    with conn.cursor() as cur:
        cur.execute("SELECT sofifa_id, short_name, position_group FROM player_season_stats WHERE sofifa_id = %s AND season = %s",
                    (sofifa_id, season))
        ref_player = cur.fetchone()
    if not ref_player:
        raise HTTPException(status_code=404, detail="Player not found for this season")

    # Build filter conditions on the similar player's stats
    filter_conditions = ["pss.season = %s"]
    filter_params = [season]

    if league:
        filter_conditions.append("pss.league_name ILIKE %s")
        filter_params.append(f"%{league}%")
    if nationality:
        filter_conditions.append("pss.nationality_name ILIKE %s")
        filter_params.append(f"%{nationality}%")
    if age_min is not None:
        filter_conditions.append("pss.age >= %s")
        filter_params.append(age_min)
    if age_max is not None:
        filter_conditions.append("pss.age <= %s")
        filter_params.append(age_max)
    if wage_max is not None:
        filter_conditions.append("(pss.wage_eur IS NULL OR pss.wage_eur <= %s)")
        filter_params.append(wage_max)
    if value_max is not None:
        filter_conditions.append("(pss.value_eur IS NULL OR pss.value_eur <= %s)")
        filter_params.append(value_max)
    if release_clause_max is not None:
        filter_conditions.append("(pss.release_clause_eur IS NULL OR pss.release_clause_eur <= %s)")
        filter_params.append(release_clause_max)

    filter_where = " AND ".join(filter_conditions)

    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT
                pss.sofifa_id, pss.short_name, pss.long_name,
                pss.player_positions, pss.position_group, pss.overall, pss.age,
                pss.club_name, pss.league_name, pss.nationality_name,
                pss.value_eur, pss.wage_eur, pss.release_clause_eur,
                pss.pace, pss.shooting, pss.passing, pss.dribbling, pss.defending, pss.physic,
                pss.uniqueness_index,
                sc.similarity_score,
                sc.rank_position
            FROM similarity_cache sc
            JOIN player_season_stats pss
                ON sc.similar_sofifa_id = pss.sofifa_id
            WHERE sc.player_sofifa_id = %s
              AND sc.season = %s
              AND {filter_where}
            ORDER BY sc.similarity_score DESC
            LIMIT %s
        """, [sofifa_id, season] + filter_params + [top_n])
        similar = cur.fetchall()

    return {
        "reference_player": ref_player,
        "season": season,
        "similar_players": similar,
        "filters_applied": {
            "league": league, "nationality": nationality,
            "age_min": age_min, "age_max": age_max,
            "wage_max": wage_max, "value_max": value_max,
            "release_clause_max": release_clause_max,
        }
    }


# ─── Uniqueness & Replaceability ───────────────────────────────────────────────

@app.get("/api/analytics/uniqueness")
def get_uniqueness_rankings(
    season: str = "2025/26",
    position_group: Optional[str] = None,
    league: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    conn=Depends(get_conn),
):
    """Top players by uniqueness index."""
    conditions = ["season = %s", "uniqueness_index IS NOT NULL"]
    params = [season]

    if position_group:
        conditions.append("position_group = %s")
        params.append(position_group)
    if league:
        conditions.append("league_name ILIKE %s")
        params.append(f"%{league}%")

    where = " AND ".join(conditions)
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT sofifa_id, short_name, position_group, overall, age,
                   club_name, league_name, nationality_name,
                   uniqueness_index, value_eur, wage_eur
            FROM player_season_stats
            WHERE {where}
            ORDER BY uniqueness_index DESC
            LIMIT %s
        """, params + [limit])
        return cur.fetchall()


@app.get("/api/analytics/replaceability")
def get_club_replaceability(
    season: str = "2025/26",
    league: Optional[str] = None,
    conn=Depends(get_conn),
):
    """Club replaceability index rankings."""
    conditions = ["season = %s"]
    params = [season]

    if league:
        conditions.append("league_name ILIKE %s")
        params.append(f"%{league}%")

    where = " AND ".join(conditions)
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT club_name, league_name, replaceability_index, avg_uniqueness, player_count
            FROM club_replaceability
            WHERE {where}
            ORDER BY replaceability_index DESC
        """, params)
        return cur.fetchall()


@app.get("/api/analytics/position-uniqueness")
def get_position_uniqueness(season: str = "2025/26", conn=Depends(get_conn)):
    """Uniqueness stats per position group — matches paper Table 1."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                position_group,
                COUNT(*) as player_count,
                ROUND(AVG(uniqueness_index)::numeric, 4) as mean,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY uniqueness_index)::numeric, 4) as median,
                ROUND(STDDEV(uniqueness_index)::numeric, 4) as std_dev,
                ROUND(MIN(uniqueness_index)::numeric, 4) as min_val,
                ROUND(MAX(uniqueness_index)::numeric, 4) as max_val,
                ROUND(PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY uniqueness_index)::numeric, 4) as p10,
                ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY uniqueness_index)::numeric, 4) as p25,
                ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY uniqueness_index)::numeric, 4) as p75,
                ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY uniqueness_index)::numeric, 4) as p90
            FROM player_season_stats
            WHERE season = %s AND uniqueness_index IS NOT NULL
            GROUP BY position_group
            ORDER BY mean DESC
        """, (season,))
        return cur.fetchall()


@app.get("/api/analytics/temporal-uniqueness")
def get_temporal_uniqueness(conn=Depends(get_conn)):
    """Average uniqueness per position per season — matches paper Figure 4."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT season, position_group,
                   ROUND(AVG(uniqueness_index)::numeric, 4) as avg_uniqueness,
                   COUNT(*) as player_count
            FROM player_season_stats
            WHERE uniqueness_index IS NOT NULL
            GROUP BY season, position_group
            ORDER BY season, position_group
        """)
        return cur.fetchall()


@app.get("/api/clubs/{club_name}/players")
def get_club_players(club_name: str, season: str = "2025/26", conn=Depends(get_conn)):
    """All players for a club in a given season."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT sofifa_id, short_name, player_positions, position_group, overall, age,
                   value_eur, wage_eur, release_clause_eur, uniqueness_index,
                   pace, shooting, passing, dribbling, defending, physic
            FROM player_season_stats
            WHERE club_name ILIKE %s AND season = %s
            ORDER BY overall DESC
        """, (f"%{club_name}%", season))
        return cur.fetchall()
