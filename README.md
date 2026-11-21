# Duck Gambit

Duck Gambit is a chess engine training game. This first slice provides a native
engine service and an Engines page; browser WebAssembly, ducks, arena play,
puzzles, accounts, and multiplayer are intentionally out of scope.

## Requirements

- Windows, macOS, or Linux
- Node.js and npm
- Python 3.12

## Run

```bash
npm install
npm run dev
```

In a second terminal:

```bash
cd backend
py run.py
```

Open `http://localhost:5173`, install Stockfish 19, then use **Test engine**.

Stockfish is GPL-3.0 licensed. Engine binaries are downloaded only from the
committed manifest and stored under `engines/installed/`.

## Test

```bash
npm test
npm run build
py -m pytest backend/tests
```
