import type { Key } from '@lichess-org/chessground/types'

/**
 * Where each piece may go, read straight from the server's list of legal moves. This is
 * grouping strings by their first two characters, not chess rules (CLAUDE.md rule 2).
 */
export function destinationsFrom(legalMoves: string[]): Map<Key, Key[]> {
  const dests = new Map<Key, Key[]>()
  for (const uci of legalMoves) {
    const from = uci.slice(0, 2) as Key
    const to = uci.slice(2, 4) as Key
    const list = dests.get(from) ?? []
    if (!list.includes(to)) list.push(to)
    dests.set(from, list)
  }
  return dests
}
