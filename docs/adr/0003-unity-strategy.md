# ADR-0003 · Unity front-end strategy

Status: Accepted: desktop sidecar first (John, 2026-11-21) · 2026-11-21 · Not legal advice

## Context

John is seriously considering a Unity client: a downloadable game with hatching, feeding and training animations and match playback. The core is a Python service that runs Stockfish (GPL-3.0) as a separate UCI process. Nothing is built for Unity in M0; this ADR decides the direction so that nothing built now blocks it.

Platform facts, checked against vendor documentation on 2026-11-21:

| Platform | Can it run a local backend and engine? |
| --- | --- |
| Windows, macOS, Linux | Yes. Under IL2CPP `System.Diagnostics.Process` is unsupported; Unity's manual says to use the Mono scripting backend where it is required on desktop [1]. A small native launcher is the alternative |
| WebGL | No. Single C# thread, no sockets, no processes; HTTP goes through the browser's Fetch and is subject to CORS [2] |
| iOS | No. App Store guideline 2.5.2 forbids downloading or executing code that changes functionality [3]; the FSF also holds that App Store terms conflict with the GPL [4] |
| Android | Not practically. Since Android 10, apps cannot `execve` files from their writable directory, and Play bans downloading executable code [5][6] |

## Options

- **A. Sidecar.** The Unity desktop app launches the packaged Python backend on localhost and talks to it over the same `/api/v1`. The backend launches Stockfish.
- **B. Hosted service.** Unity talks to a server we run. The only option for WebGL and mobile. Costs hosting, accounts, quotas, and engine CPU that we pay for.
- **C. Re-implement the core in C#** with a native engine plugin. Two implementations of the decision layer, ratings and scoring that must produce bit-identical results, forever. It would also pull the GPL question into the Unity code itself.

## Decision

**A for desktop, as the only Unity target for now. B is the documented path to WebGL and mobile and shares the same contract. C is rejected.**

Reasons: A reuses everything, works offline, costs nothing to run, and keeps one source of truth for game logic. Because the web client and a Unity client would speak the same contract, "hosted" later is a deployment change to the backend (ADR-0011 lists what must change), not a client rewrite.

**GPL boundary.** The backend is GPL-3.0+ regardless of Stockfish because it imports python-chess; the web client is GPL because of chessground (ADR-0013). The FSF describes programs that communicate over sockets, pipes or command lines as normally separate programs, unless the exchange is so intimate that they form one program, and notes this is ultimately for courts [7]. A Unity client that only speaks versioned HTTP/JSON to the backend fits the separate-programs description. So:

- No GPL code in the Unity project: no ports of chessground, python-chess or Stockfish code. The contract already makes this easy because the client needs no chess rules (ADR-0002).
- A desktop bundle that includes the backend sidecar conveys GPL software: ship the license text and the corresponding source (a public repo at the exact tag satisfies this), and say plainly in the credits that the game uses Stockfish. The ChessBase case was about hiding the origin and omitting source and license, not about process separation [8].
- Stockfish stays a separate process downloaded from the manifest on first run.

**What would change this decision:**

- John wants a browser-playable or mobile Unity build early: then B must be built first (accounts, hosting, engine budget per user), and it should be a decision about hosting, not about Unity.
- Sidecar packaging proves unshippable (antivirus false positives on the frozen Python binary, macOS notarization pain): fall back to B, or port only the *API host* while keeping Python for tools. Still not C.
- A hard requirement for a closed-source game with no source obligations anywhere in the bundle: get legal advice, then choose between B (nothing GPL is distributed to players) and replacing python-chess.

### Unity readiness checklist

Built in M0 (the test is that the web client already lives under the same constraints):

- [ ] Client needs zero chess rules: positions arrive as FEN, moves as events with SAN and flags, legal moves from the server.
- [ ] Every user-visible change is an event with a stable schema; no state can be learned only by diffing REST responses.
- [ ] `contracts/openapi.json` and `contracts/events.schema.json` are committed and drift-checked.
- [ ] Event schemas use a plain tagged union (`type` literal per variant). No `allOf` inheritance, no free-form maps in hot paths. C# generators handle these poorly.
- [ ] Streams have a pollable JSON twin, so a client without SSE support can still play back a match.
- [ ] Host, port, data directory, allowed origins and log destination come from environment settings; nothing is derived from the source tree.
- [ ] `GET /api/v1/health` reports version, contract version and readiness.
- [ ] An optional per-launch bearer token (`DG_API_TOKEN`) gates the API.
- [ ] The server shuts down cleanly on a signal and kills its engine processes.
- [ ] No reliance on the Vite proxy or on cookies.

Deferred to M7:

- [ ] Generate the C# client. OpenAPI Generator's `unityWebRequest` library is marked experimental and lacks `oneOf` support [9]; plan to generate models only and write the thin transport and the event dispatcher by hand. Decide between Newtonsoft and Unity's serializer; add `link.xml` for IL2CPP stripping.
- [ ] Prove the stream transport in Unity (SSE through `DownloadHandlerScript` on desktop; polling as fallback).
- [ ] Package the sidecar: PyInstaller one-folder mode (one-file mode unpacks to temp on every start and cannot be signed after the build [10]). Launch with a free port and a token, wait for health, tie its lifetime to the game with a Windows Job Object (`KILL_ON_JOB_CLOSE`, which also covers Stockfish [11]) and a parent-PID watchdog elsewhere.
- [ ] Code signing: Windows signing to reduce antivirus flags; macOS notarization of every executable in the bundle [12].
- [ ] Choose Mono or a native launcher for starting the sidecar.
- [ ] Shared art pipeline consumed by both clients (ADR-0013).

Rough download budget for a desktop build: Unity player about 70 MB, frozen backend 50 to 110 MB (estimate), Stockfish about 80 MB fetched on first run.

## Consequences

- Desktop first means no browser or phone build of the Unity game until hosting exists. The React client remains the zero-install way to play on one's own machine.
- The contract carries more data (SAN, flags, legal moves) than a rules-aware client would need. That is the price of thin clients and it is small.
- Two clients share one backend, so backend sessions never need to know which client is asking.

## Not building yet

- Any Unity project, C# code, sidecar packaging, installers or signing.
- Hosted mode, accounts, matchmaking.
- WebSocket transport (only if the Unity stream prototype in M7 fails on SSE and polling).

## Sources

1. Unity 6.6 manual, IL2CPP scripting restrictions: https://docs.unity.com/en-us/engine/6000.6/manual/programming-environment/scripting-backends/il2cpp/scripting-restrictions
2. Unity manual, Web networking and technical overview: https://docs.unity.com/en-us/engine/6000.0/manual/platform-specific/webgl/develop/networking
3. Apple App Store Review Guidelines 2.5.2: https://developer.apple.com/app-store/review/guidelines/
4. FSF on the App Store and the GPL: https://www.fsf.org/blogs/licensing/more-about-the-app-store-gpl-enforcement
5. Android 10 behaviour changes (execute from app home directory removed): https://developer.android.com/about/versions/10/behavior-changes-10
6. Google Play policy on downloading executable code: https://support.google.com/googleplay/android-developer/answer/9888379
7. GNU GPL FAQ, "mere aggregation" and "GPL in a proprietary system": https://www.gnu.org/licenses/gpl-faq.en.html#MereAggregation
8. Stockfish and ChessBase settlement: https://stockfishchess.org/blog/2022/chessbase-stockfish-agreement/
9. OpenAPI Generator C# generator (7.27.0): https://openapi-generator.tech/docs/generators/csharp/
10. PyInstaller operating modes and signing notes: https://pyinstaller.org/en/stable/operating-mode.html
11. Windows Job Objects: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
12. Apple, notarizing macOS software: https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
