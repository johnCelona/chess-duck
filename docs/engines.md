# Engine integration

Native engines run as separate processes in the Python backend. The browser
only calls the Duck Gambit API and never receives UCI commands or engine paths.

## Add an engine

Add an entry to `backend/engines/manifest.json`:

- `id`, `name`, `version`, `license`, `homepage`, and `source_url`
- one platform entry under `platforms`
- the manifest download URL, verified SHA-256, archive type, and binary path

Only manifest URLs are accepted. User-provided URLs and paths are not supported.
Every downloaded archive is checksum-verified, extracted through a path
traversal guard, and smoke-tested before it is marked installed.

The generic UCI adapter reads advertised options at runtime. Backend validation
must allowlist every user-settable option and clamp it against both advertised
limits and server limits.
