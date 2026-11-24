-- 0003: remember which duck the player last chose (the hub's active duck, design 03 §2.2).
-- Forward-only. Never edit a migration that has shipped; add a new one.
--
-- Stored on the profile, not in a client, so the web app and a future Unity client agree.
-- NULL means "not chosen yet"; readers fall back to the oldest duck. Ducks are never
-- deleted today, but a reader still checks that the duck exists and belongs to the profile.

ALTER TABLE profiles ADD COLUMN active_duck_id TEXT REFERENCES ducks (id);
