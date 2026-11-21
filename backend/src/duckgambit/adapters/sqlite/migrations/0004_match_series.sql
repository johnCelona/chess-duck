-- 0004: a match can be a best-of series (Super Bullet Arena, design 03).
-- Forward-only. Never edit a migration that has shipped; add a new one.
--
-- JSON {"best_of": 5, "type": "best-of"} (domain.series.SeriesFormat), or NULL for a plain
-- match that plays exactly arena.games games, as every match before this one did.

ALTER TABLE matches ADD COLUMN series TEXT;
