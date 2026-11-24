# Engine integration

Engines run as separate native processes in the Python backend, behind one `Engine` port (ADR-0007). Clients never send UCI and never see engine paths.

## The manifest

`backend/src/duckgambit/adapters/engines/manifest.json` is code-reviewed configuration and the only source of download URLs. Each engine has:

| Field | Meaning |
| --- | --- |
| `id` | Lowercase id used in the API (`^[a-z0-9][a-z0-9_-]{0,63}$`) |
| `name`, `version`, `license`, `homepage`, `sourceUrl` | Shown to players; `sourceUrl` points at the exact source for the GPL notice |
| `uciName` | What the engine must report as `id name` (prefix match); checked by the smoke test |
| `platforms` | One entry per `windows-x86_64`, `windows-arm64`, `linux-x86_64`, `linux-arm64`, `macos-universal` |

Each platform entry:

| Field | Meaning |
| --- | --- |
| `url` | Official release asset, `https://` only |
| `sha256` | Pinned digest of the archive. Verify it yourself against the downloaded file before committing |
| `sizeBytes` | Exact archive size; downloads larger than this are refused |
| `archive` | `zip` or `tar.gz` |
| `binary` | Path of the executable inside the archive |
| `keep` | License files kept beside the binary (everything else in the archive, such as source trees, is discarded) |

## Install flow

Download to a staging folder (streamed, size-capped, sha256 computed on the fly) → compare with the pin → extract member by member (no links, no absolute paths, no `..`) → copy the binary and `keep` files → **smoke test** (`uci`, `isready`, check `uciName`) → swap into `data/engines/<id>/<version>/` atomically. A failure at any step leaves the previous install untouched.

## Options

Only `Hash` is user-settable (diagnostics), clamped by the pool's total budget. Rated play always uses Threads 1, `UCI_ShowWDL` on, and never `Skill Level` or `UCI_Elo` (their randomness is time-seeded). Options that take paths or write files are never settable.

## Adding an engine

Add a manifest entry with every platform you can verify, run the installer test suite, install it locally, and run `uv run --project backend pytest backend/tests/real` adapted to it. A new engine is a new rating context (ADR-0006).
