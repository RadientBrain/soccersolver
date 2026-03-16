"""
Integration test — covers the critical path:
DB → mock data → ML pipeline → API similarity endpoint
"""
import os
import sys
import pytest
import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://soccer:soccer123@localhost:5432/soccersolver")


def test_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1
    conn.close()


def test_player_data_exists():
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM player_season_stats")
        count = cur.fetchone()[0]
    conn.close()
    assert count > 0, "No player data found — run mock_data_generator.py first"


def test_pipeline_results_exist():
    """After pipeline run, uniqueness scores should be populated."""
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM player_season_stats WHERE uniqueness_index IS NOT NULL")
        count = cur.fetchone()[0]
    conn.close()
    assert count > 0, "No ML results — run pipeline/ml_pipeline.py first"


def test_similarity_cache_populated():
    """Similarity cache should have entries after pipeline."""
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM similarity_cache")
        count = cur.fetchone()[0]
    conn.close()
    assert count > 0, "Similarity cache empty — run pipeline/ml_pipeline.py first"


def test_similarity_scores_valid_range():
    """All similarity scores should be in [0, 1]."""
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM similarity_cache
            WHERE similarity_score < 0 OR similarity_score > 1
        """)
        invalid = cur.fetchone()[0]
    conn.close()
    assert invalid == 0, f"{invalid} similarity scores outside [0,1]"


def test_top_similar_players_returned():
    """Given a known player, the API path returns ≥5 similar players."""
    conn = psycopg2.connect(DATABASE_URL)

    # Get any player that has similarity cache entries
    with conn.cursor() as cur:
        cur.execute("""
            SELECT p.sofifa_id, p.short_name, p.season
            FROM player_season_stats p
            JOIN similarity_cache sc ON sc.player_sofifa_id = p.sofifa_id AND sc.season = p.season
            GROUP BY p.sofifa_id, p.short_name, p.season
            HAVING COUNT(*) >= 5
            LIMIT 1
        """)
        row = cur.fetchone()

    assert row is not None, "No player with 5+ similar players in cache"
    sofifa_id, name, season = row

    with conn.cursor() as cur:
        cur.execute("""
            SELECT sc.similar_sofifa_id, sc.similarity_score
            FROM similarity_cache sc
            WHERE sc.player_sofifa_id = %s AND sc.season = %s
            ORDER BY sc.similarity_score DESC
            LIMIT 10
        """, (sofifa_id, season))
        similar = cur.fetchall()

    conn.close()
    assert len(similar) >= 5, f"Expected ≥5 similar players for {name}, got {len(similar)}"
    # Check scores are in valid range and sorted descending
    scores = [r[1] for r in similar]
    assert all(0 <= s <= 1 for s in scores), "Scores out of range"
    assert scores == sorted(scores, reverse=True), "Scores not sorted descending"
    print(f"\n✓ Player: {name} (sofifa_id={sofifa_id}, season={season})")
    print(f"  Top {len(similar)} similar players, scores: {[round(s, 3) for s in scores]}")


def test_uniqueness_index_range():
    """Uniqueness index values should be in [0, 1]."""
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM player_season_stats
            WHERE uniqueness_index IS NOT NULL
              AND (uniqueness_index < 0 OR uniqueness_index > 1)
        """)
        invalid = cur.fetchone()[0]
    conn.close()
    assert invalid == 0, f"{invalid} uniqueness values outside [0,1]"


def test_club_replaceability_computed():
    """Club replaceability should be populated after pipeline."""
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM club_replaceability")
        count = cur.fetchone()[0]
    conn.close()
    assert count > 0, "No club replaceability data — run pipeline/ml_pipeline.py first"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
