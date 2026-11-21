// Builders for match events in tests. Each call gets the next cursor, like the server.
import type { EventEnvelope } from '../api/client'

export const START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
export const AFTER_E4 = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1'
export const AFTER_E5 = 'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2'
export const AFTER_D4 = 'rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1'

let cursor = 0

export function envelope<T extends EventEnvelope['type']>(
  type: T,
  data: Extract<EventEnvelope, { type: T }>['data'],
  stream = 'match:mat_1',
): EventEnvelope {
  cursor += 1
  return {
    cursor,
    seq: cursor,
    stream,
    recordedAt: '2026-11-21T12:00:00Z',
    type,
    data,
  } as EventEnvelope
}

export const started = (gameId: string, index: number) =>
  envelope('GameStarted', {
    matchId: 'mat_1',
    gameId,
    index,
    whiteDuckId: 'duck_a',
    blackDuckId: 'duck_b',
    initialFen: START,
    whiteClockMs: 60000,
    blackClockMs: 60000,
  })

/** A MoveChosen and its MoveMade, the way the runner records one ply. */
export function played(
  gameId: string,
  ply: number,
  uci: string,
  san: string,
  fenAfter: string,
): EventEnvelope[] {
  const color = ply % 2 === 1 ? 'white' : 'black'
  const duckId = color === 'white' ? 'duck_a' : 'duck_b'
  return [
    envelope('MoveChosen', {
      gameId,
      ply,
      duckId,
      color,
      fenBefore: START,
      move: uci,
      san,
      source: 'engine',
      candidates: [],
      reasons: [{ code: 'engine.top_choice', text: `${san} scored best`, params: {} }],
      thinkMs: 1000,
      nodesBudget: 200000,
      nodes: 200017,
      depth: 12,
    }),
    envelope('MoveMade', {
      gameId,
      ply,
      color,
      by: 'duck',
      duckId,
      uci,
      san,
      fenAfter,
      capture: false,
      enPassant: false,
      check: false,
      checkmate: false,
      castle: null,
      promotion: null,
      thinkMs: 1000,
      whiteClockMs: 60000 - 1000 * Math.ceil(ply / 2),
      blackClockMs: 60000 - 1000 * Math.floor(ply / 2),
    }),
  ]
}

/** Game 1: 1. e4 e5. Game 2: 1. d4. */
export function twoGameEvents(): EventEnvelope[] {
  return [
    envelope('MatchStarted', { matchId: 'mat_1' }),
    started('game_1', 0),
    ...played('game_1', 1, 'e2e4', 'e4', AFTER_E4),
    ...played('game_1', 2, 'e7e5', 'e5', AFTER_E5),
    started('game_2', 1),
    ...played('game_2', 1, 'd2d4', 'd4', AFTER_D4),
  ]
}
