-- 0001: the tables the M0 walking skeleton uses (ADR-0004).
-- Forward-only. Never edit a migration that has shipped; add a new one.

CREATE TABLE profiles (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE ducks (
    id          TEXT PRIMARY KEY,
    profile_id  TEXT NOT NULL REFERENCES profiles (id),
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    origin      TEXT,
    doc_version INTEGER NOT NULL,
    doc         TEXT NOT NULL  -- avatar, growth, stats, care, principles, motifs
);
CREATE INDEX ducks_by_profile ON ducks (profile_id, created_at);

CREATE TABLE repertoire_entries (
    id           INTEGER PRIMARY KEY,
    duck_id      TEXT NOT NULL REFERENCES ducks (id) ON DELETE CASCADE,
    color        TEXT NOT NULL CHECK (color IN ('white', 'black')),
    position_key TEXT NOT NULL,
    move_uci     TEXT NOT NULL,
    weight       INTEGER NOT NULL DEFAULT 1,
    source       TEXT NOT NULL,
    lesson_id    TEXT,
    UNIQUE (duck_id, color, position_key, move_uci)
);

CREATE TABLE puzzle_memory (
    id           INTEGER PRIMARY KEY,
    duck_id      TEXT NOT NULL REFERENCES ducks (id) ON DELETE CASCADE,
    position_key TEXT NOT NULL,
    move_uci     TEXT NOT NULL,
    lesson_id    TEXT,
    UNIQUE (duck_id, position_key)
);

CREATE TABLE engine_profiles (
    id         INTEGER PRIMARY KEY,
    engine_id  TEXT NOT NULL,
    name       TEXT NOT NULL,
    doc        TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (engine_id, name)
);

CREATE TABLE rating_contexts (
    id         TEXT PRIMARY KEY,
    doc        TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE ratings (
    duck_id    TEXT NOT NULL REFERENCES ducks (id) ON DELETE CASCADE,
    context_id TEXT NOT NULL REFERENCES rating_contexts (id),
    kind       TEXT NOT NULL CHECK (kind IN ('game', 'puzzle')),
    value      REAL NOT NULL,
    deviation  REAL NOT NULL,
    volatility REAL NOT NULL,
    games      INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (duck_id, context_id, kind)
);

CREATE TABLE rating_history (
    id          INTEGER PRIMARY KEY,
    duck_id     TEXT NOT NULL REFERENCES ducks (id) ON DELETE CASCADE,
    context_id  TEXT NOT NULL,
    kind        TEXT NOT NULL,
    value       REAL NOT NULL,
    deviation   REAL NOT NULL,
    volatility  REAL NOT NULL,
    games       INTEGER NOT NULL,
    game_id     TEXT,
    recorded_at TEXT NOT NULL
);
CREATE INDEX rating_history_by_duck ON rating_history (duck_id, context_id, kind, id);

CREATE TABLE jobs (
    id           TEXT PRIMARY KEY,
    kind         TEXT NOT NULL,
    state        TEXT NOT NULL,
    params       TEXT NOT NULL,
    done         INTEGER NOT NULL DEFAULT 0,
    total        INTEGER NOT NULL DEFAULT 0,
    error_code   TEXT,
    error_detail TEXT,
    created_at   TEXT NOT NULL,
    started_at   TEXT,
    finished_at  TEXT
);

CREATE TABLE matches (
    id          TEXT PRIMARY KEY,
    profile_id  TEXT NOT NULL REFERENCES profiles (id),
    mode        TEXT NOT NULL,
    rated       INTEGER NOT NULL,
    state       TEXT NOT NULL,
    arena       TEXT NOT NULL,
    duck_ids    TEXT NOT NULL,
    scores      TEXT NOT NULL DEFAULT '{}',
    context_id  TEXT NOT NULL,
    job_id      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    finished_at TEXT
);
CREATE INDEX matches_by_profile ON matches (profile_id, created_at);

CREATE TABLE games (
    id             TEXT PRIMARY KEY,
    match_id       TEXT NOT NULL REFERENCES matches (id) ON DELETE CASCADE,
    idx            INTEGER NOT NULL,
    white_duck_id  TEXT NOT NULL,
    black_duck_id  TEXT NOT NULL,
    seed           INTEGER NOT NULL,
    initial_fen    TEXT NOT NULL,
    state          TEXT NOT NULL,
    white_clock_ms INTEGER,
    black_clock_ms INTEGER,
    result         TEXT,
    termination    TEXT,
    pgn            TEXT,
    started_at     TEXT NOT NULL,
    finished_at    TEXT,
    UNIQUE (match_id, idx)
);

CREATE TABLE moves (
    game_id   TEXT NOT NULL REFERENCES games (id) ON DELETE CASCADE,
    ply       INTEGER NOT NULL,
    color     TEXT NOT NULL,
    uci       TEXT NOT NULL,
    san       TEXT NOT NULL,
    source    TEXT NOT NULL,
    cp        INTEGER,
    mate      INTEGER,
    nodes     INTEGER NOT NULL,
    depth     INTEGER NOT NULL,
    think_ms  INTEGER NOT NULL,
    clock_ms  INTEGER,
    fen_after TEXT NOT NULL,
    event_seq INTEGER NOT NULL,  -- seq of this ply's MoveChosen event; candidate detail lives there
    PRIMARY KEY (game_id, ply)
);

CREATE TABLE events (
    cursor      INTEGER PRIMARY KEY AUTOINCREMENT,
    stream      TEXT NOT NULL,
    seq         INTEGER NOT NULL,
    type        TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    data        TEXT NOT NULL,
    UNIQUE (stream, seq)
);
