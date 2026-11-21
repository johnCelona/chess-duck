import { describe, expect, test, vi } from 'vitest'
import type { EventEnvelope } from '../api/client'
import {
  applyEvent,
  createPlayer,
  delayFor,
  emptyMatchView,
  formatClock,
  formatScore,
} from './playback'

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
      { ply: 1, color: 'white', san: 'e4', uci: 'e2e4', source: 'book', thinkMs: 1500 },
    ])
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
