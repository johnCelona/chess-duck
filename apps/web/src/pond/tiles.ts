// The four tiles of the Pond (design 03 §2.3). Names and copy are placeholders (John's).
// Only the Arena works in the first slice; the others open a "coming soon" screen.

export type Tile = { id: string; title: string; blurb: string; to: string; soon?: string }

export const TILES: readonly Tile[] = [
  {
    id: 'dojo',
    title: 'Tactics Dojo',
    blurb: 'Drill forks, pins and mates together. Teach your duck the tactics it misses.',
    to: '/pond/dojo',
    soon: 'Motif drills and Candidate Showdown: several ducks, one position, and their top five moves side by side.',
  },
  {
    id: 'arena',
    title: 'Arena',
    blurb: 'Pick two of your ducks and watch them battle at one-minute bullet.',
    to: '/arena',
  },
  {
    id: 'practice',
    title: 'Practice Pond',
    blurb: 'Play your own duck on your own clock.',
    to: '/pond/practice',
    soon: 'Bullet against your duck, with you on a real clock and your duck thinking on its own.',
  },
  {
    id: 'school',
    title: 'Opening School',
    blurb: 'Teach your duck the openings you know. It only plays what it was taught.',
    to: '/pond/school',
    soon: 'Show your duck an opening move by move. Before each game it picks up to three of its openings to play.',
  },
]

export function tileFor(id: string | undefined): Tile | undefined {
  return TILES.find((tile) => tile.id === id)
}
