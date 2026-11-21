import { describe, expect, test, vi } from 'vitest'
import type { EventEnvelope } from '../api/client'
import {
  applyEvent,
  createPlayer,
  delayFor,
  emptyMatchView,
  first,
  formatClock,
  formatEval,
  formatScore,
  positionAt,
  step,
  type MatchView,
} from './playback'
import { AFTER_D4, twoGameEvents } from '../test/matchEvents'

const START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
const AFTER_E4 = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1'

let cursor = 0
function envelope<T extends EventEnvelope['type']>(
  type: T,
  data: Extract<EventEnvelope, { type: T }>['data'],
): EventEnvelope {
  cursor += 1
  return {
    cursor,
    seq: cursor,
    stream: 'match:mat_1',
    recordedAt: '2026-11-21T12:00:00Z',
    type,
    data,
  } as EventEnvelope
}

const gameStarted = () =>
  envelope('GameStarted', {
    matchId: 'mat_1',
    gameId: 'game_1',
    index: 0,
    whiteDuckId: 'duck_a',
    blackDuckId: 'duck_b',
    initialFen: START,
    whiteClockMs: 60000,
    blackClockMs: 60000,
  })

const moveChosen = (source: 'book' | 'engine' = 'engine') =>
  envelope('MoveChosen', {
    gameId: 'game_1',
    ply: 1,
    duckId: 'duck_a',
    color: 'white',
    fenBefore: START,
    move: 'e2e4',
    san: 'e4',
    source,
    candidates: [],
    reasons: [{ code: 'engine.top_choice', text: 'e4 scored best', params: {} }],
    thinkMs: 1500,
    nodesBudget: 300000,
    nodes: 300017,
    depth: 12,
  })

const moveMade = (thinkMs = 1500) =>
  envelope('MoveMade', {
    gameId: 'game_1',
    ply: 1,
    color: 'white',
    by: 'duck',
    duckId: 'duck_a',
    uci: 'e2e4',
    san: 'e4',
    fenAfter: AFTER_E4,
    capture: false,
    enPassant: false,
    check: false,
    checkmate: false,
    castle: null,
    promotion: null,
    thinkMs,
    whiteClockMs: 58480,
    blackClockMs: 60000,
  })

describe('applyEvent', () => {
  test('a started game shows the initial position and both clocks', () => {
    const view = applyEvent(emptyMatchView, gameStarted())

    expect(view.status).toBe('running')
    expect(view.games[0]).toMatchObject({ fen: START, turn: 'white', whiteClockMs: 60000 })
  })

  test('a move updates the board, the clocks and the move list from the event alone', () => {
    let view = applyEvent(emptyMatchView, gameStarted())
    view = applyEvent(view, moveChosen('book'))
    view = applyEvent(view, moveMade())

    const game = view.games[0]
    expect(game.fen).toBe(AFTER_E4)
    expect(game.lastMove).toEqual(['e2', 'e4'])
    expect(game.turn).toBe('black')
    expect(game.whiteClockMs).toBe(58480)
    expect(game.moves).toEqual([
      expect.objectContaining({
        ply: 1,
        color: 'white',
        san: 'e4',
        uci: 'e2e4',
        source: 'book',
        thinkMs: 1500,
        fenAfter: AFTER_E4,
        lastMove: ['e2', 'e4'],
        whiteClockMs: 58480,
      }),
    ])
    expect(game.moves[0].decision?.reasons[0].text).toBe('e4 scored best')
    expect(view.thinking?.reasons[0].text).toBe('e4 scored best')
  })

  test('the result and the final score come from the finishing events', () => {
    let view = applyEvent(emptyMatchView, gameStarted())
    view = applyEvent(
      view,
      envelope('GameFinished', {
        matchId: 'mat_1',
        gameId: 'game_1',
        result: '1-0',
        termination: 'checkmate',
        winnerDuckId: 'duck_a',
        plies: 33,
      }),
    )
    view = applyEvent(
      view,
      envelope('MatchFinished', {
        matchId: 'mat_1',
        scores: [
          { duckId: 'duck_a', points: 1 },
          { duckId: 'duck_b', points: 0 },
        ],
        winnerDuckId: 'duck_a',
      }),
    )

    expect(view.games[0].result).toBe('1-0')
    expect(view.status).toBe('finished')
    expect(view.scores).toEqual({ duck_a: 1, duck_b: 0 })
    expect(view.winnerDuckId).toBe('duck_a')
  })

  test('an event delivered twice after a reconnect is applied once', () => {
    const started = gameStarted()
    const made = moveMade()
    let view = applyEvent(emptyMatchView, started)
    view = applyEvent(view, made)
    view = applyEvent(view, made)

    expect(view.games[0].moves).toHaveLength(1)
  })

  test('unknown event types are ignored instead of breaking playback', () => {
    const future = { ...gameStarted(), type: 'DuckDanced', data: {} } as unknown as EventEnvelope

    expect(applyEvent(emptyMatchView, future).games).toEqual([])
  })

  test('a cancelled job is remembered so the screen can offer to resume', () => {
    const view = applyEvent(
      emptyMatchView,
      envelope('JobFinished', { jobId: 'job_1', state: 'cancelled', errorCode: null }),
    )

    expect(view.jobState).toBe('cancelled')
  })

  test('moves after a stop mean the match was resumed, so it shows as running again', () => {
    let view = applyEvent(emptyMatchView, gameStarted())
    view = applyEvent(
      view,
      envelope('JobFinished', { jobId: 'job_1', state: 'cancelled', errorCode: null }),
    )
    view = applyEvent(view, moveChosen())

    expect(view.jobState).toBeNull()
  })
})

describe('pacing and formatting', () => {
  test('moves are held for their virtual think time, scaled by speed', () => {
    expect(delayFor(moveMade(1500), 1)).toBe(1500)
    expect(delayFor(moveMade(1500), 4)).toBe(375)
    expect(delayFor(moveMade(1500), 0)).toBe(0)
    expect(delayFor(moveMade(20000), 1)).toBe(3000)
    expect(delayFor(moveMade(10), 1)).toBe(60)
    expect(delayFor(moveChosen(), 1)).toBe(0)
  })

  test('clocks show tenths only under ten seconds', () => {
    expect(formatClock(58480)).toBe('0:58')
    expect(formatClock(9400)).toBe('0:09.4')
    expect(formatClock(125000)).toBe('2:05')
    expect(formatClock(null)).toBe('–')
  })

  test('scores read as pawns or mate', () => {
    expect(formatScore({ cp: 34, mate: null })).toBe('+0.34')
    expect(formatScore({ cp: -120, mate: null })).toBe('-1.20')
    expect(formatScore({ cp: null, mate: 3 })).toBe('#3')
  })
})

describe('createPlayer', () => {
  test('holds each move for its think time, then shows the next event', () => {
    vi.useFakeTimers()
    const shown: string[] = []
    const player = createPlayer((event) => shown.push(event.type), 1)

    player.push(gameStarted())
    player.push(moveMade(1000))
    player.push(moveMade(1000))
    expect(shown).toEqual(['GameStarted', 'MoveMade'])

    vi.advanceTimersByTime(999)
    expect(shown).toHaveLength(2)
    vi.advanceTimersByTime(1)
    expect(shown).toHaveLength(3)
    vi.useRealTimers()
  })

  test('switching to instant flushes everything that is waiting', () => {
    vi.useFakeTimers()
    const shown: string[] = []
    const player = createPlayer((event) => shown.push(event.type), 1)
    player.push(moveMade(3000))
    player.push(moveMade(3000))
    player.push(moveMade(3000))

    player.setSpeed(0)

    expect(shown).toHaveLength(3)
    vi.useRealTimers()
  })

  test('stopping drops queued events', () => {
    vi.useFakeTimers()
    const shown: string[] = []
    const player = createPlayer((event) => shown.push(event.type), 1)
    player.push(moveMade(1000))
    player.push(moveMade(1000))

    player.stop()
    vi.advanceTimersByTime(10000)

    expect(shown).toHaveLength(1)
    vi.useRealTimers()
  })
})

describe('moving through a match', () => {
  const twoGames = (): MatchView => twoGameEvents().reduce(applyEvent, emptyMatchView)

  test('following live shows the newest position and the decision behind it', () => {
    const position = positionAt(twoGames(), null)!

    expect(position).toMatchObject({ gameIndex: 1, ply: 1, totalPlies: 1, live: true })
    expect(position.fen).toBe(AFTER_D4)
    expect(position.lastMove).toEqual(['d2', 'd4'])
    expect(position.decision?.san).toBe('d4')
  })

  test('a past position shows its own board, clocks and decision', () => {
    const position = positionAt(twoGames(), { gameIndex: 0, ply: 1 })!

    expect(position.fen).toBe(AFTER_E4)
    expect(position.whiteClockMs).toBe(59000)
    expect(position.blackClockMs).toBe(60000)
    expect(position.turn).toBe('black')
    expect(position.decision?.reasons[0].text).toBe('e4 scored best')
    expect(position.live).toBe(false)
  })

  test('the start position has no move and no decision', () => {
    const position = positionAt(twoGames(), { gameIndex: 0, ply: 0 })!

    expect(position.fen).toBe(START)
    expect(position.lastMove).toBeNull()
    expect(position.decision).toBeNull()
    expect(position.whiteClockMs).toBe(60000)
  })

  test('stepping back from live walks through every position, across games', () => {
    const view = twoGames()
    const visited = []
    let cursor = step(view, null, -1)
    while (cursor !== null) {
      visited.push(`${cursor.gameIndex}:${cursor.ply}`)
      const next = step(view, cursor, -1)
      if (next !== null && next.gameIndex === cursor.gameIndex && next.ply === cursor.ply) break
      cursor = next
    }

    expect(visited).toEqual(['1:0', '0:2', '0:1', '0:0'])
  })

  test('stepping forward onto the newest position returns to live', () => {
    const view = twoGames()

    expect(step(view, { gameIndex: 1, ply: 0 }, 1)).toBeNull()
    expect(step(view, { gameIndex: 0, ply: 2 }, 1)).toEqual({ gameIndex: 1, ply: 0 })
    expect(step(view, null, 1)).toBeNull()
  })

  test('the first position is game 1 at the start; an empty match has none', () => {
    expect(first(twoGames())).toEqual({ gameIndex: 0, ply: 0 })
    expect(first(emptyMatchView)).toBeNull()
    expect(positionAt(emptyMatchView, null)).toBeNull()
  })

  test('a cursor past the end of a game is clamped to its last move', () => {
    expect(positionAt(twoGames(), { gameIndex: 0, ply: 99 })?.ply).toBe(2)
  })

  test('mates are spelled out in the thinking panel', () => {
    expect(formatEval({ cp: null, mate: 3 })).toBe('Mate in 3')
    expect(formatEval({ cp: null, mate: -2 })).toBe('Mated in 2')
    expect(formatEval({ cp: 27, mate: null })).toBe('+0.27')
  })
})
