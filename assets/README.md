# Assets

Art, animation and audio sources shared by every client (web now, Unity later). See ADR-0013.

**License.** Original Duck Gambit art and audio are not covered by the code's GPL license. Until John decides otherwise they are all rights reserved (`LICENSE.md` here). Third-party assets must be GPL-compatible or permissive and must be listed in `manifest.json`. No CC BY-NC, no unknown licenses.

## Layout and naming

```
assets/
  manifest.json                   one entry per asset: id, path, author, license, source
  ducks/<species>/<skin>/         idle.svg thinking.svg victory.svg sulk.svg portrait.svg
  pieces/<set>/                   wK.svg wQ.svg wR.svg wB.svg wN.svg wP.svg bK.svg ... bP.svg
  boards/<theme>/                 board.svg, or light.svg and dark.svg
  animations/<name>/source/       editor files
  animations/<name>/export/       sprite sheets or JSON
  audio/<name>.ogg
```

- Lowercase kebab-case for folders and files, except piece files, which use the conventional `wK` to `bP` names.
- SVG is the source of truth for vector art; square view box.
- Duck states are named after what they mean (`idle`, `thinking`, `victory`, `sulk`), and clients map semantic events to states (`MatchFinished` won → `victory`). The domain never names an animation.
- A duck's avatar is a set of ids (`species`, `skin`, `accessories`), never a file path. Clients resolve ids through `manifest.json`.

## Adding an asset

1. Put the file in the right folder.
2. Add an entry to `manifest.json`.
3. If it is third-party, add a row to `THIRD_PARTY_LICENSES.md` in the same commit.
