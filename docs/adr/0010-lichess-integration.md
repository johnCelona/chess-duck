# ADR-0010 · Lichess integration

Status: Proposed · 2026-11-21 · Optional and off by default · Facts verified against the Lichess OpenAPI spec v2.0.180 on 2026-11-21

## Context

Spec section 8 wants: link a Lichess account, import the player's games to build a "mini-me" repertoire, save duck games to the player's account, and later use the opening explorer, tablebase and perhaps a bot account. CLAUDE.md rule 8 puts every external service behind a port, off by default, faked in tests, with tokens kept out of the repo, logs and client bundle.

## Feasibility (what the documentation actually says)

| Feature | Verdict | Facts |
| --- | --- | --- |
| Link account | **Feasible, no registration** | OAuth2 Authorization Code with PKCE (`S256` only) for public clients: "choose any unique client id", no secret. Authorize at `GET https://lichess.org/oauth`, exchange at `POST /api/token`, revoke with `DELETE /api/token` [1]. Tokens last about a year; **there are no refresh tokens** [1]. Lichess's source accepts `http://127.0.0.1` and `http://localhost` redirect URIs on any port, but that is implementation, not documented contract [2] |
| Identify the user | **No scope needed** | `GET /api/account` works with any token |
| Import my games | **Feasible without linking** | `GET /api/games/user/{username}` returns PGN or NDJSON; public games need no token. Throughput: 20 games/s anonymous, 30 with a token, 60 for one's own games. Filters include `since`, `until`, `max`, `perfType`, `color`, `rated`, `opening` [3] |
| Save duck games | **Feasible with caveats** | `POST /api/import` takes one PGN, needs no scope, and with a token the game is listed under the user's imported games. Documented limit: 200 per hour with a token; the server currently enforces about 10 per minute [4][5]. Imported games are public and unrated; identical PGNs are deduplicated server-side [5] |
| Save to a study | Feasible, heavier | `POST /api/study` then `POST /api/study/{id}/import-pgn`; needs `study:write`; 64 chapters per study; 30 new studies per day; studies can be private [6] |
| Opening explorer | Feasible, token required | `explorer.lichess.org`; every request needs a token (any scope) since March 2026; about 20 requests per minute [7] |
| Cloud eval, tablebase | Feasible, anonymous for now | "A few positions here and there"; Lichess has said the tablebase may also require a token later [7][8] |
| Bot account | Feasible, **irreversible** | `POST /api/bot/account/upgrade`, scope `bot:play`, only for an account that has never played a game; bots play challenge games only [9] |
| Puzzle data | Fine | CC0 (ADR-0009) |

General rules that bind any client: only one request at a time; on HTTP 429 wait at least a minute; every request must carry a `User-Agent` naming the application [1]. The terms of service prohibit "abuse of our APIs" and say nothing specific about importing engine-played games [10].

## Options

**Where OAuth runs.** In the browser client (token ends up in web storage and in the bundle's reach) or in the backend (token never leaves the local service).

**Where the token lives.** Database row; a file in the data directory; the operating system's credential store.

**How duck games reach Lichess.** `/api/import` per game; a study per duck; or manual PGN download.

## Decision

1. **A `LichessPort` Protocol in `services`**, with `FakeLichess` as the only adapter in M0. Setting `DG_LICHESS_ENABLED` is false by default; when false the routes report the integration as unavailable and nothing imports the HTTP adapter.

   ```python
   class LichessPort(Protocol):
       def authorization_url(self, state: str, code_challenge: str, redirect_uri: str, scopes: list[str]) -> str
       async def exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> Token
       async def account(self, token: Token) -> LichessAccount
       def export_games(self, username: str, query: GameQuery, token: Token | None) -> AsyncIterator[str]   # PGN
       async def import_game(self, pgn: str, token: Token | None) -> ImportedGame
       async def revoke(self, token: Token) -> None
   ```

2. **OAuth runs in the backend.** The client opens the authorize URL; Lichess redirects to `http://127.0.0.1:<port>/api/v1/integrations/lichess/callback`; the backend exchanges the code. This works identically for the web app and a Unity desktop app.
3. **Scopes: none.** Identity, game export and game import need no scope. `study:write` is requested only if and when study export is built, as a separate, explicit consent.
4. **Tokens go through a `SecretStore` port**: operating-system credential store first, a user-only file in the data directory as fallback. Tokens are never stored in SQLite, never returned by any API response, never logged (the logger redacts `Authorization` headers and token-shaped fields). The database stores only the link: Lichess user id, name, scopes, linked date, expected expiry.
5. **Unlink** calls `DELETE /api/token`, then deletes the local secret and the link row. If the revoke call fails, the local secret is still deleted and the user is told to revoke at lichess.org.
6. **Saving duck games uses `/api/import`, one explicit user action per game** ("Save to Lichess"), never automatic and never in bulk by default, because imported games are public. A local limiter keeps to at most 10 per minute, one request at a time, with a one-minute back-off on 429. **The always-available fallback is PGN download.**
7. **Importing games works without linking** (public games by username); linking only raises throughput. Imported PGN goes through the same size-capped, validated import path as any PGN file.
8. **A single outbound client** owns the `User-Agent`, the one-request-at-a-time rule and back-off, so no feature can break the rules by accident.
9. Token expiry (about a year, no refresh) is handled by treating a 401 as "link expired" and prompting to re-link.

## Consequences

- With zero scopes, a leaked token can read public data and add imports to the account; it cannot play, message or change settings. That keeps the blast radius small.
- Saving games is honest about its limits: public, unrated, rate-limited, one at a time.
- The redirect to `127.0.0.1` relies on behaviour seen in Lichess's source rather than a documented promise. If it stops working, the fallback is a personal access token pasted by the user into a backend form (never recommended for multi-user apps, acceptable for a single-user local one).
- Explorer and tablebase calls need a cache table and their own limiter when they are built.

## Not building yet

- The HTTP adapter, OAuth routes, secret-store implementations and any UI (M6). M0 ships the port, the fake, a contract test for the port, and the disabled-by-default setting.
- Study export, opening explorer, cloud eval, tablebase.
- Bot accounts: a later showpiece. It needs a fresh dedicated account and cannot be undone, so it will get its own ADR and John's explicit decision.

## Sources

1. Lichess API reference (OpenAPI v2.0.180): https://lichess.org/api
2. lila OAuth protocol source (redirect URI handling): https://github.com/lichess-org/lila/blob/master/modules/oauth/src/main/Protocol.scala
3. Export games of a user: https://github.com/lichess-org/api/blob/master/doc/specs/tags/games/api-games-user-username.yaml
4. Import one game: https://github.com/lichess-org/api/blob/master/doc/specs/tags/games/api-import.yaml
5. lila import limiter and importer source: https://github.com/lichess-org/lila/blob/master/modules/web/src/main/Limiters.scala and https://github.com/lichess-org/lila/blob/master/modules/game/src/main/Importer.scala
6. Study endpoints: https://github.com/lichess-org/api/tree/master/doc/specs/tags/studies
7. "The opening explorer now requires authentication": https://lichess.org/@/thibault/blog/the-opening-explorer-now-requires-authentication/FSWh9Zg3
8. Cloud eval: https://github.com/lichess-org/api/blob/master/doc/specs/tags/analysis/api-cloud-eval.yaml
9. Upgrade to bot account: https://github.com/lichess-org/api/blob/master/doc/specs/tags/bot/api-bot-account-upgrade.yaml
10. Lichess terms of service (modified 2026-08-01): https://lichess.org/terms-of-service
