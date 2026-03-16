"""
ML Pipeline — implements the exact methodology from the paper:
1. Load player data per season from DB
2. Z-score normalization per position group
3. PCA (retain 90% variance) per position group
4. K-Means clustering with silhouette scoring
5. Hybrid cosine+Euclidean similarity (α=0.5)
6. Compute Player Uniqueness Index and Club Replaceability Index
7. Write results back to DB
"""
import os
import logging
import warnings
import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_similarity
from scipy.spatial.distance import cdist
from dotenv import load_dotenv

load_dotenv()
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://soccer:soccer123@localhost:5432/soccersolver")

# Columns used for ML features (exclude identity/economic/derived cols)
FEATURE_COLS = [
    "pace", "shooting", "passing", "dribbling", "defending", "physic",
    "attacking_crossing", "attacking_finishing", "attacking_heading_accuracy",
    "attacking_short_passing", "attacking_volleys",
    "skill_dribbling", "skill_curve", "skill_fk_accuracy",
    "skill_long_passing", "skill_ball_control",
    "movement_acceleration", "movement_sprint_speed", "movement_agility",
    "movement_reactions", "movement_balance",
    "power_shot_power", "power_jumping", "power_stamina",
    "power_strength", "power_long_shots",
    "mentality_aggression", "mentality_interceptions", "mentality_positioning",
    "mentality_vision", "mentality_penalties", "mentality_composure",
    "defending_marking_awareness", "defending_standing_tackle", "defending_sliding_tackle",
]

GK_FEATURE_COLS = [
    "goalkeeping_diving", "goalkeeping_handling", "goalkeeping_kicking",
    "goalkeeping_positioning", "goalkeeping_reflexes", "goalkeeping_speed",
    "movement_reactions", "power_strength",
]

# Position groups (matches paper Section 2.1)
POSITION_GROUPS = ["GK", "CB", "FB", "MID", "WIDE", "FWD"]


def get_features_for_group(group: str) -> list[str]:
    if group == "GK":
        return GK_FEATURE_COLS
    return FEATURE_COLS


def load_season_data(conn, season: str) -> pd.DataFrame:
    """Load all player stats for a season from DB."""
    sql = """
        SELECT
            sofifa_id, short_name, long_name, club_name, league_name,
            nationality_name, position_group, overall, age,
            value_eur, wage_eur, release_clause_eur,
            pace, shooting, passing, dribbling, defending, physic,
            attacking_crossing, attacking_finishing, attacking_heading_accuracy,
            attacking_short_passing, attacking_volleys,
            skill_dribbling, skill_curve, skill_fk_accuracy,
            skill_long_passing, skill_ball_control,
            movement_acceleration, movement_sprint_speed, movement_agility,
            movement_reactions, movement_balance,
            power_shot_power, power_jumping, power_stamina,
            power_strength, power_long_shots,
            mentality_aggression, mentality_interceptions, mentality_positioning,
            mentality_vision, mentality_penalties, mentality_composure,
            defending_marking_awareness, defending_standing_tackle, defending_sliding_tackle,
            goalkeeping_diving, goalkeeping_handling, goalkeeping_kicking,
            goalkeeping_positioning, goalkeeping_reflexes, goalkeeping_speed
        FROM player_season_stats
        WHERE season = %s
        ORDER BY sofifa_id
    """
    df = pd.read_sql(sql, conn, params=(season,))
    log.info(f"Loaded {len(df)} players for season {season}")
    return df


def hybrid_similarity(X: np.ndarray, alpha: float = 0.5) -> np.ndarray:
    """
    Compute pairwise hybrid similarity matrix.
    S_ij = 1 - [alpha * ||xi-xj|| / ||x||_2 + (1-alpha) * (1 - cos(xi, xj))]
    Returns similarity matrix scaled to [0,1].
    """
    n = X.shape[0]
    if n == 0:
        return np.array([])

    # Euclidean distance, normalized
    euclidean_dist = cdist(X, X, metric="euclidean")
    norm = np.linalg.norm(X)
    if norm > 0:
        euclidean_dist_normalized = euclidean_dist / norm
    else:
        euclidean_dist_normalized = euclidean_dist

    # Cosine similarity → distance
    cos_sim = cosine_similarity(X)
    cos_dist = 1 - cos_sim

    # Hybrid distance
    hybrid_dist = alpha * euclidean_dist_normalized + (1 - alpha) * cos_dist

    # Convert to similarity, clip to [0,1]
    sim = 1 - hybrid_dist
    sim = np.clip(sim, 0, 1)
    np.fill_diagonal(sim, 1.0)  # self-similarity = 1
    return sim


def compute_uniqueness(sim_matrix: np.ndarray, k: int = 10) -> np.ndarray:
    """
    Uniqueness Index U_i = 1 - (1/k) * sum of k nearest neighbor similarities
    (Equation 2 from paper)
    """
    n = sim_matrix.shape[0]
    uniqueness = np.zeros(n)
    for i in range(n):
        # Exclude self (diagonal)
        row = sim_matrix[i].copy()
        row[i] = 0
        top_k = np.sort(row)[::-1][:k]
        uniqueness[i] = 1 - np.mean(top_k)
    return uniqueness


def find_optimal_k(X_pca: np.ndarray, k_range: range = range(3, 12)) -> int:
    """Find optimal k for K-Means using silhouette score."""
    if len(X_pca) < 10:
        return 3
    best_k, best_score = 3, -1
    for k in k_range:
        if k >= len(X_pca):
            break
        try:
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = km.fit_predict(X_pca)
            score = silhouette_score(X_pca, labels)
            if score > best_score:
                best_score = score
                best_k = k
        except Exception:
            pass
    log.info(f"  Optimal k={best_k} (silhouette={best_score:.3f})")
    return best_k


def run_pipeline_for_group(df_group: pd.DataFrame, group: str) -> pd.DataFrame:
    """Run PCA + KMeans + similarity for one positional group."""
    feat_cols = get_features_for_group(group)
    available = [c for c in feat_cols if c in df_group.columns]

    # Drop rows with too many nulls
    df_clean = df_group.dropna(subset=available, thresh=len(available) // 2).copy()
    if len(df_clean) < 5:
        log.warning(f"Group {group}: only {len(df_clean)} players, skipping")
        return df_group

    X = df_clean[available].fillna(df_clean[available].median())

    # Step 1: Z-score normalization
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Step 2: PCA (90% variance threshold)
    pca_full = PCA(random_state=42)
    pca_full.fit(X_scaled)
    cumvar = np.cumsum(pca_full.explained_variance_ratio_)
    n_components = max(2, int(np.searchsorted(cumvar, 0.90)) + 1)
    n_components = min(n_components, len(available) - 1, len(df_clean) - 1)

    pca = PCA(n_components=n_components, random_state=42)
    X_pca = pca.fit_transform(X_scaled)
    log.info(f"  Group {group}: {len(df_clean)} players, {n_components} PCA components "
             f"({cumvar[n_components-1]*100:.1f}% variance)")

    # Step 3: K-Means clustering
    optimal_k = find_optimal_k(X_pca)
    km = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
    cluster_labels = km.fit_predict(X_pca)

    # Step 4: Similarity matrix
    sim_matrix = hybrid_similarity(X_pca, alpha=0.5)

    # Step 5: Uniqueness
    uniqueness = compute_uniqueness(sim_matrix, k=min(10, len(df_clean) - 1))

    # Write back to dataframe
    df_clean = df_clean.copy()
    df_clean["cluster_id"] = cluster_labels
    df_clean["uniqueness_index"] = uniqueness
    df_clean["pca_component_1"] = X_pca[:, 0]
    df_clean["pca_component_2"] = X_pca[:, 1]
    df_clean["pca_component_3"] = X_pca[:, 2] if X_pca.shape[1] > 2 else 0.0

    # Store similarity matrix for top-N retrieval
    df_clean["_sim_matrix_idx"] = range(len(df_clean))
    df_clean["_sim_matrix"] = [sim_matrix[i] for i in range(len(df_clean))]

    return df_clean


def save_results_to_db(conn, df: pd.DataFrame, season: str):
    """Write PCA, cluster, and uniqueness results back to DB."""
    update_sql = """
        UPDATE player_season_stats
        SET cluster_id = %s,
            uniqueness_index = %s,
            pca_component_1 = %s,
            pca_component_2 = %s,
            pca_component_3 = %s
        WHERE sofifa_id = %s AND season = %s
    """
    rows = []
    for _, row in df.iterrows():
        if "cluster_id" not in row or pd.isna(row.get("cluster_id")):
            continue
        rows.append((
            int(row["cluster_id"]),
            float(row["uniqueness_index"]) if not pd.isna(row.get("uniqueness_index")) else None,
            float(row["pca_component_1"]) if not pd.isna(row.get("pca_component_1")) else None,
            float(row["pca_component_2"]) if not pd.isna(row.get("pca_component_2")) else None,
            float(row["pca_component_3", 0.0] if "pca_component_3" in row else 0.0),
            int(row["sofifa_id"]),
            season,
        ))

    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, update_sql, rows, page_size=200)
    conn.commit()
    log.info(f"  Saved ML results for {len(rows)} players")


def save_similarity_cache(conn, df_group: pd.DataFrame, season: str, top_n: int = 20):
    """Persist top-N similarity scores per player to the cache table."""
    if "_sim_matrix" not in df_group.columns:
        return

    rows = []
    sofifa_ids = df_group["sofifa_id"].values

    for i, (_, row) in enumerate(df_group.iterrows()):
        sim_row = row["_sim_matrix"]
        # Get top-N excluding self
        sim_copy = sim_row.copy()
        sim_copy[i] = 0
        top_indices = np.argsort(sim_copy)[::-1][:top_n]
        for rank, j in enumerate(top_indices, 1):
            rows.append((
                int(sofifa_ids[i]),
                season,
                int(sofifa_ids[j]),
                float(sim_copy[j]),
                rank,
            ))

    if not rows:
        return

    sql = """
        INSERT INTO similarity_cache (player_sofifa_id, season, similar_sofifa_id, similarity_score, rank_position, computed_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (player_sofifa_id, season, rank_position)
        DO UPDATE SET similar_sofifa_id = EXCLUDED.similar_sofifa_id,
                      similarity_score = EXCLUDED.similarity_score,
                      computed_at = NOW()
    """
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, rows, page_size=500)
    conn.commit()
    log.info(f"  Saved {len(rows)} similarity cache entries")


def compute_club_replaceability(conn, season: str):
    """
    Club Replaceability Index R_club = (1/N) * sum(1 - U_i)
    (Equation 3 from paper)
    """
    sql = """
        SELECT club_name, league_name,
               COUNT(*) as player_count,
               AVG(uniqueness_index) as avg_uniqueness,
               AVG(1 - uniqueness_index) as replaceability_index
        FROM player_season_stats
        WHERE season = %s AND uniqueness_index IS NOT NULL
        GROUP BY club_name, league_name
        HAVING COUNT(*) >= 5
    """
    df = pd.read_sql(sql, conn, params=(season,))

    if df.empty:
        return

    insert_sql = """
        INSERT INTO club_replaceability (club_name, league_name, season, avg_uniqueness, replaceability_index, player_count)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (club_name, season)
        DO UPDATE SET avg_uniqueness = EXCLUDED.avg_uniqueness,
                      replaceability_index = EXCLUDED.replaceability_index,
                      player_count = EXCLUDED.player_count,
                      computed_at = NOW()
    """
    rows = [(r.club_name, r.league_name, season, r.avg_uniqueness, r.replaceability_index, r.player_count)
            for r in df.itertuples()]
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, insert_sql, rows)
    conn.commit()
    log.info(f"  Computed replaceability for {len(rows)} clubs")


def run_pipeline(seasons: list[str] = None):
    """Run full ML pipeline for given seasons."""
    conn = psycopg2.connect(DATABASE_URL)

    if seasons is None:
        # Get all seasons in DB
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT season FROM player_season_stats ORDER BY season")
            seasons = [r[0] for r in cur.fetchall()]

    for season in seasons:
        log.info(f"=== Running pipeline for season {season} ===")
        df = load_season_data(conn, season)
        if df.empty:
            log.warning(f"No data for season {season}")
            continue

        all_results = []
        for group in POSITION_GROUPS:
            df_group = df[df["position_group"] == group].copy()
            if len(df_group) < 5:
                log.info(f"  Group {group}: {len(df_group)} players, skipping")
                continue
            log.info(f"  Processing group {group} ({len(df_group)} players)...")
            df_processed = run_pipeline_for_group(df_group, group)
            all_results.append(df_processed)

            # Save similarity cache per group
            if "_sim_matrix" in df_processed.columns:
                save_similarity_cache(conn, df_processed, season)

        if all_results:
            df_all = pd.concat(all_results, ignore_index=True)
            save_results_to_db(conn, df_all, season)
            compute_club_replaceability(conn, season)
            log.info(f"Pipeline complete for {season}: {len(df_all)} players processed")

    conn.close()
    log.info("All seasons complete.")


if __name__ == "__main__":
    import sys
    seasons = sys.argv[1:] if len(sys.argv) > 1 else None
    run_pipeline(seasons)
