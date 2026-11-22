-- 0005: games between the player and one of their ducks (Practice Pond, and "You play" in
-- Super Bullet Arena). ADR-0015: a human is a recorded input; these games are never rated.
-- Forward-only. Never edit a migration that has shipped; add a new one.
--
-- Kept apart from matches/games, whose rows name two ducks. The duck's moves replay
-- exactly from (seed, the stored human moves): elapsed_ms is the human's measured time.

CREATE TABLE sparring_series (
    id          TEXT PRIMARY KEY,
    profile_id  TEXT NOT NULL REFERENCES profiles (id),
    duck_id     TEXT NOT NULL REFERENCES ducks (id),
    engine_id   TEXT NOT NULL,
    best_of     INTEGER NOT NULL,
    seed        INTEGER NOT NULL,
    state       TEXT NOT NULL,          -- playing | decided
    created_at  TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE sparring_games (
    id              TEXT PRIMARY KEY,
    profile_id      TEXT NOT NULL REFERENCES profiles (id),
    duck_id         TEXT NOT NULL REFERENCES ducks (id),
    engine_id       TEXT NOT NULL,
    human_color     TEXT NOT NULL,      -- white | black
    time_control    TEXT,               -- JSON {base_ms, increment_ms}; NULL is untimed
    seed            INTEGER NOT NULL,
    initial_fen     TEXT NOT NULL,
    state           TEXT NOT NULL,      -- running | finished
    result          TEXT,
    termination     TEXT,
    white_clock_ms  INTEGER,
    black_clock_ms  INTEGER,
    turn_started_ms INTEGER,            -- epoch ms when the side to move started thinking
    series_id       TEXT REFERENCES sparring_series (id),
    series_index    INTEGER,
    created_at      TEXT NOT NULL,
    finished_at     TEXT
);
CREATE INDEX sparring_games_by_profile ON sparring_games (profile_id, created_at);
CREATE INDEX sparring_games_by_series ON sparring_games (series_id, series_index);

CREATE TABLE sparring_moves (
    game_id    TEXT NOT NULL REFERENCES sparring_games (id) ON DELETE CASCADE,
    ply        INTEGER NOT NULL,
    color      TEXT NOT NULL,
    by         TEXT NOT NULL,           -- human | duck
    uci        TEXT NOT NULL,
    san        TEXT NOT NULL,
    source     TEXT,                    -- the duck's decision source; NULL for the human
    elapsed_ms INTEGER NOT NULL,        -- human: measured; duck: virtual think time
    fen_after  TEXT NOT NULL,
    PRIMARY KEY (game_id, ply)
);
