-- Extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Players identity table
CREATE TABLE IF NOT EXISTS players (
    id           SERIAL PRIMARY KEY,
    sofifa_id    INTEGER UNIQUE NOT NULL,
    short_name   VARCHAR(100),
    long_name    VARCHAR(150),
    nationality  VARCHAR(100),
    dob          DATE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Main stats table (one row per player per season)
CREATE TABLE IF NOT EXISTS player_season_stats (
    sofifa_id                    INTEGER NOT NULL,
    season                       VARCHAR(10) NOT NULL,
    scraped_at                   TIMESTAMPTZ DEFAULT NOW(),

    -- identity
    short_name                   VARCHAR(100),
    long_name                    VARCHAR(150),
    player_positions             VARCHAR(50),
    overall                      INTEGER,
    potential                    INTEGER,
    age                          INTEGER,

    -- club
    club_name                    VARCHAR(150),
    league_name                  VARCHAR(150),
    league_level                 INTEGER,

    -- nationality
    nationality_name             VARCHAR(100),

    -- physical / profile
    preferred_foot               VARCHAR(10),
    weak_foot                    INTEGER,
    skill_moves                  INTEGER,
    international_reputation     INTEGER,
    work_rate                    VARCHAR(50),
    body_type                    VARCHAR(50),
    height_cm                    INTEGER,
    weight_kg                    INTEGER,

    -- economic (key differentiators vs MVP)
    value_eur                    BIGINT,
    wage_eur                     INTEGER,
    release_clause_eur           BIGINT,

    -- FIFA card stats
    pace                         INTEGER,
    shooting                     INTEGER,
    passing                      INTEGER,
    dribbling                    INTEGER,
    defending                    INTEGER,
    physic                       INTEGER,

    -- attacking
    attacking_crossing           INTEGER,
    attacking_finishing          INTEGER,
    attacking_heading_accuracy   INTEGER,
    attacking_short_passing      INTEGER,
    attacking_volleys            INTEGER,

    -- skill
    skill_dribbling              INTEGER,
    skill_curve                  INTEGER,
    skill_fk_accuracy            INTEGER,
    skill_long_passing           INTEGER,
    skill_ball_control           INTEGER,

    -- movement
    movement_acceleration        INTEGER,
    movement_sprint_speed        INTEGER,
    movement_agility             INTEGER,
    movement_reactions           INTEGER,
    movement_balance             INTEGER,

    -- power
    power_shot_power             INTEGER,
    power_jumping                INTEGER,
    power_stamina                INTEGER,
    power_strength               INTEGER,
    power_long_shots             INTEGER,

    -- mentality
    mentality_aggression         INTEGER,
    mentality_interceptions      INTEGER,
    mentality_positioning        INTEGER,
    mentality_vision             INTEGER,
    mentality_penalties          INTEGER,
    mentality_composure          INTEGER,

    -- defending
    defending_marking_awareness  INTEGER,
    defending_standing_tackle    INTEGER,
    defending_sliding_tackle     INTEGER,

    -- goalkeeping
    goalkeeping_diving           INTEGER,
    goalkeeping_handling         INTEGER,
    goalkeeping_kicking          INTEGER,
    goalkeeping_positioning      INTEGER,
    goalkeeping_reflexes         INTEGER,
    goalkeeping_speed            INTEGER,

    -- ML-derived (populated by pipeline)
    position_group               VARCHAR(20),
    pca_component_1              FLOAT,
    pca_component_2              FLOAT,
    pca_component_3              FLOAT,
    cluster_id                   INTEGER,
    uniqueness_index             FLOAT,

    PRIMARY KEY (sofifa_id, season)
);

-- Scrape audit log
CREATE TABLE IF NOT EXISTS scrape_log (
    id             SERIAL PRIMARY KEY,
    season         VARCHAR(10) NOT NULL,
    sofifa_version INTEGER,
    started_at     TIMESTAMPTZ DEFAULT NOW(),
    completed_at   TIMESTAMPTZ,
    total_players  INTEGER,
    status         VARCHAR(20) DEFAULT 'running',
    error_message  TEXT
);

-- Similarity cache
CREATE TABLE IF NOT EXISTS similarity_cache (
    player_sofifa_id  INTEGER NOT NULL,
    season            VARCHAR(10) NOT NULL,
    similar_sofifa_id INTEGER NOT NULL,
    similarity_score  FLOAT NOT NULL,
    rank_position     INTEGER NOT NULL,
    computed_at       TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (player_sofifa_id, season, rank_position)
);

-- Club replaceability index
CREATE TABLE IF NOT EXISTS club_replaceability (
    club_name           VARCHAR(150) NOT NULL,
    league_name         VARCHAR(150),
    season              VARCHAR(10) NOT NULL,
    avg_uniqueness      FLOAT,
    replaceability_index FLOAT,
    player_count        INTEGER,
    computed_at         TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (club_name, season)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_pss_season        ON player_season_stats (season);
CREATE INDEX IF NOT EXISTS idx_pss_position_group ON player_season_stats (position_group);
CREATE INDEX IF NOT EXISTS idx_pss_club          ON player_season_stats (club_name);
CREATE INDEX IF NOT EXISTS idx_pss_league        ON player_season_stats (league_name);
CREATE INDEX IF NOT EXISTS idx_pss_nationality   ON player_season_stats (nationality_name);
CREATE INDEX IF NOT EXISTS idx_pss_overall       ON player_season_stats (overall DESC);
CREATE INDEX IF NOT EXISTS idx_pss_value         ON player_season_stats (value_eur DESC NULLS LAST);

-- Full-text search on player name
CREATE INDEX IF NOT EXISTS idx_pss_name
ON player_season_stats
USING GIN (
    to_tsvector(
        'english',
        COALESCE(short_name, '') || ' ' || COALESCE(long_name, '')
    )
);
