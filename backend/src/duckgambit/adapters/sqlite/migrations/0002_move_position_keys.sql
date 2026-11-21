-- 0002: index moves by the position they were played from.
-- Forward-only. Never edit a migration that has shipped; add a new one.
--
-- position_key is domain.chessutil.position_key of the board BEFORE the move: the first
-- four FEN fields, en passant only when a capture is legal, no move counters. It is the
-- same key repertoire_entries and puzzle_memory use, so "what was played here" can be
-- joined against "what the duck was taught here".
--
-- Rows written before this migration are filled by a Python data step that replays each
-- game from games.initial_fen (adapters/sqlite/data_steps.py), in the same transaction.
-- A row stays NULL only when its game cannot be replayed (a corrupt stored move).

ALTER TABLE moves ADD COLUMN position_key TEXT;

-- "Which games reached this position, and what was played there": equality on the key,
-- then game_id so the join to games and a per-game ordering read the index in order.
CREATE INDEX moves_by_position ON moves (position_key, game_id);
