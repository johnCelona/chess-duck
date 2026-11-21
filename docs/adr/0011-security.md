# ADR-0011 · Security model

Status: Accepted (John, 2026-11-21) · 2026-11-21

## Context

The service binds to 127.0.0.1, has no authentication, starts native processes, downloads executables and deletes directories. The realistic attackers are a hostile web page open in the same browser and other local software. Later the same backend may run as a sidecar next to a Unity game, or hosted.

### Defects found at commit `9daabb4` (to fix in Phase 2 group A, before features)

| # | Severity | Defect | Evidence |
| --- | --- | --- | --- |
| S1 | **High** | **Path traversal to recursive delete.** `engine_id` goes from the URL into filesystem paths unchecked. `DELETE /api/engines/%2e%2e` reaches `remove_engine("..")`, which deletes `backend/engines`; on Windows `..%5c..` resolves to `backend/` itself. The same id reaches profile reads and writes | Reproduced with the delete function stubbed: the handler received `'..'` and `'..\\..'` |
| S2 | Medium | **No Host or Origin check**, so DNS rebinding works: a page that rebinds its name to 127.0.0.1 is same-origin with the API. Combined with S1 this is remotely triggerable | A request with `Host: evil.example` was served |
| S3 | Medium | **Bodyless POSTs are cross-site triggerable** (`/install`, `/test`): any page can start an 80 MB download or burn CPU without a preflight | Code reading |
| S4 | Low | Profiles are stored without option validation; a saved profile on disk contains `Debug Log File`, `EvalFile`, `SyzygyPath` | File inspected |
| S5 | Low | `int(value)` on a non-number raises `TypeError`: a 500 instead of a 400 | Reproduced |
| S6 | Low | Installer: no smoke test although documented; `tarfile.extractall` without `filter="data"` (Python 3.12 default is no filter); whole archive read into memory; no size cap; no install lock; old install deleted before the new one is in place; on Windows, removing a running engine fails halfway | Code reading; tar default verified |
| S7 | Low | The absolute path of the engine binary is returned to the browser; exception text is returned in 400 responses | Code reading |
| S8 | Low | CORS allows credentials, all methods and all headers although the dev proxy makes the browser same-origin | Code reading |

## Decision

### Request boundary

1. **Bind to loopback only.** Binding elsewhere requires an explicit setting and turns on the token requirement.
2. **Host allowlist**: reject any request whose `Host` is not `127.0.0.1:<port>` or `localhost:<port>` (plus configured names). This defeats DNS rebinding.
3. **Origin check on every state-changing request**: if an `Origin` header is present it must be in the allowlist (the dev origin in development, nothing extra in production where the app is same-origin). CORS is off unless origins are configured.
4. **State-changing requests must be `application/json`** (or carry the launch token). That makes them non-simple, so browsers preflight them and the Origin rule applies.
5. **Optional launch token** (`DG_API_TOKEN`): when set, every `/api` request needs `Authorization: Bearer …`. The Unity sidecar launch always sets it. Compared in constant time, never logged.
6. **Typed identifiers.** Every id in a path or body matches `^[a-z0-9][a-z0-9_-]{0,63}$` at the schema level. Engine ids must also exist in the manifest. No handler builds a path from raw input.
7. **One path helper**, `safe_child(root, *parts)`, resolves and verifies containment; all data-directory access goes through it. Recursive deletes take a typed, validated id and re-verify the target is inside the data directory.
8. **Errors** use the problem format (ADR-0002) with stable codes; exception text and filesystem paths stay in the log.
9. **Input limits**: request body size cap; PGN, duck-file and FEN inputs validated and size-capped before parsing.

### Engines

10. **No raw UCI, ever.** The `Engine` port takes typed requests only. Because Stockfish 19 exits on malformed input, typed validation is also an availability measure.
11. **User-settable options: `Threads` and `Hash` only**, clamped to the advertised range and to server caps, and only for unrated analysis. MultiPV and limits are request fields with their own caps. `Skill Level`, `UCI_LimitStrength`, `UCI_Elo` and `UCI_ShowWDL` are set by the server (anchors and the Judge), not by users. Path-valued and file-writing options (`EvalFile`, `SyzygyPath`, `Debug Log File`, `NumaPolicy`) are server-controlled; the allowlist is the mechanism, and a test asserts that every string-typed option an engine advertises is rejected.
12. **Budgets are totals**: process count, Threads and Hash are capped across the pool (ADR-0007). Every search has a deadline; on deadline or error the process is killed.
13. **Subprocess hygiene**: no shell, argument vector only, working directory inside the data directory, minimal environment, standard streams piped, kill on shutdown. Windows Job Objects for orphan-proofing arrive with sidecar packaging (M7).

### Installer

14. Download only from the committed manifest, **https only**, with a size cap and streaming sha256.
15. Verify the hash, extract to a staging directory with member-by-member checks (no absolute paths, no `..`, no links, no special files; `filter="data"` for tar), then **smoke test** (`uci`, `isready`, check the reported name) and only then swap into place atomically. Keep the binary and license files; discard the bundled source tree.
16. One install at a time per engine; stop the engine before replacing or removing it.
17. Manifest entries are keyed by OS and architecture.

### Secrets and logs

18. Third-party tokens live behind `SecretStore` (ADR-0010), never in the database, logs, repo or any response. Logs are structured and redact authorization headers and token-like fields.

### If the service is ever hosted

Not a configuration switch. It needs: real accounts and sessions, per-user authorization on every resource, TLS, CSRF protection, per-user engine and job quotas with rate limits, engines in a sandbox or container, a multi-user database, abuse controls on installs (which would be disabled entirely), and a privacy policy for imported games. This list exists so nobody mistakes "bind to 0.0.0.0" for hosting.

## Consequences

- A local process running as the same user can still do anything the user can; the launch token raises the bar only slightly. That is inherent to local-first software and accepted.
- Requiring JSON on state-changing requests means even "do it" endpoints take an empty JSON object. Generated clients hide this.
- Removing `Skill Level` and `UCI_Elo` from the Engines form changes that page; the Test button keeps working.

## Not building yet

- Accounts, sessions, TLS, hosted hardening.
- OS-level sandboxing of engines.
- Token-bucket rate limits: locally, the job queue and single-flight installs bound abuse.
- Signature verification of engine downloads beyond the pinned sha256 (upstream publishes no signatures we can pin).
