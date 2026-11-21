// Turns the match event stream into what the screen shows. This is presentation
// state only: the board position, clocks and results all come from the events.
// There are no chess rules here (CLAUDE.md rule 2).
import type { EventEnvelope, EventOf } from '../api/client'

export type MoveRow = {
  ply: number
  color: 'white' | 'black'
  san: string
  uci: string
  source: string
  thinkMs: number
}

export type GameView = {
  id: string
  index: number
  whiteDuckId: string
  blackDuckId: string
  fen: string
  lastMove: [string, string] | null
  check: boolean
  turn: 'white' | 'black'
  whiteClockMs: number | null
  blackClockMs: number | null
  moves: MoveRow[]
  result: string | null
  termination: string | null
}

export type MatchView = {
  status: 'waiting' | 'running' | 'finished'
  games: GameView[]
  thinking: EventOf<'MoveChosen'>['data'] | null
  scores: Record<string, number>
  winnerDuckId: string | null
  jobState: string | null
  lastCursor: number
}

export const emptyMatchView: MatchView = {
  status: 'waiting',
  games: [],
  thinking: null,
  scores: {},
  winnerDuckId: null,
  jobState: null,
  lastCursor: 0,
}

function turnFromFen(fen: string): 'white' | 'black' {
  return fen.split(' ')[1] === 'b' ? 'black' : 'white'
}

function updateGame(
  view: MatchView,
  gameId: string,
  change: (game: GameView) => GameView,
): GameView[] {
  return view.games.map((game) => (game.id === gameId ? change(game) : game))
}

/** Applies one event. Events already applied (by cursor) and unknown types are ignored. */
export function applyEvent(view: MatchView, event: EventEnvelope): MatchView {
  if (event.cursor <= view.lastCursor) return view
  const next = { ...view, lastCursor: event.cursor }
  switch (event.type) {
    case 'MatchStarted':
      return { ...next, status: 'running' }
    case 'GameStarted': {
      const data = event.data
      const game: GameView = {
        id: data.gameId,
        index: data.index,
        whiteDuckId: data.whiteDuckId,
        blackDuckId: data.blackDuckId,
        fen: data.initialFen,
        lastMove: null,
        check: false,
        turn: turnFromFen(data.initialFen),
        whiteClockMs: data.whiteClockMs,
        blackClockMs: data.blackClockMs,
        moves: [],
        result: null,
        termination: null,
      }
      return { ...next, status: 'running', thinking: null, games: [...view.games, game] }
    }
    case 'MoveChosen':
      // Moves after a stop mean the match was resumed: it is running again.
      return { ...next, thinking: event.data, jobState: null }
    case 'MoveMade': {
      const data = event.data
      return {
        ...next,
        games: updateGame(view, data.gameId, (game) => ({
          ...game,
          fen: data.fenAfter,
          lastMove: [data.uci.slice(0, 2), data.uci.slice(2, 4)],
          check: data.check,
          turn: turnFromFen(data.fenAfter),
          whiteClockMs: data.whiteClockMs,
          blackClockMs: data.blackClockMs,
          moves: [
            ...game.moves,
            {
              ply: data.ply,
              color: data.color,
              san: data.san,
              uci: data.uci,
              source: view.thinking?.ply === data.ply ? view.thinking.source : 'engine',
              thinkMs: data.thinkMs,
            },
          ],
        })),
      }
    }
    case 'GameFinished': {
      const data = event.data
      return {
        ...next,
        games: updateGame(view, data.gameId, (game) => ({
          ...game,
          result: data.result,
          termination: data.termination,
        })),
      }
    }
    case 'MatchFinished': {
      const scores = Object.fromEntries(event.data.scores.map((s) => [s.duckId, s.points]))
      return { ...next, status: 'finished', scores, winnerDuckId: event.data.winnerDuckId }
    }
    case 'JobFinished':
      return { ...next, jobState: event.data.state }
    default:
      return next
  }
}

/**
 * How long to hold an event on screen before the next one, in real milliseconds.
 * The server never waits; pacing a replay is the client's job (ADR-0007).
 */
export function delayFor(event: EventEnvelope, speed: number): number {
  if (speed <= 0 || event.type !== 'MoveMade') return 0
  const capped = Math.min(event.data.thinkMs, 3000)
  return Math.max(60, Math.round(capped / speed))
}

export function formatClock(ms: number | null): string {
  if (ms === null) return '–'
  const total = Math.max(0, ms)
  const minutes = Math.floor(total / 60000)
  const seconds = Math.floor((total % 60000) / 1000)
  const tenths = Math.floor((total % 1000) / 100)
  const base = `${minutes}:${String(seconds).padStart(2, '0')}`
  return total < 10000 ? `${base}.${tenths}` : base
}

export function formatScore(candidate: { cp: number | null; mate: number | null }): string {
  if (candidate.mate !== null) return `#${candidate.mate}`
  const pawns = (candidate.cp ?? 0) / 100
  return `${pawns >= 0 ? '+' : ''}${pawns.toFixed(2)}`
}

export type Player = {
  /** Queue an event for display. */
  push: (event: EventEnvelope) => void
  /** 0 shows everything at once; 1 is real time by the virtual clock; 4 is four times faster. */
  setSpeed: (speed: number) => void
  /** Drop anything queued and cancel the pending timer. */
  stop: () => void
}

/**
 * Plays queued events back at a watchable pace. Events arrive as fast as the server
 * computes them (it never waits), so pacing happens here, from each move's think time.
 */
export function createPlayer(show: (event: EventEnvelope) => void, initialSpeed = 1): Player {
  let queue: EventEnvelope[] = []
  let timer: ReturnType<typeof setTimeout> | null = null
  let speed = initialSpeed

  const pump = () => {
    timer = null
    while (queue.length > 0) {
      const event = queue.shift()!
      show(event)
      const delay = delayFor(event, speed)
      if (delay > 0) {
        timer = setTimeout(pump, delay)
        return
      }
    }
  }

  return {
    push(event) {
      queue.push(event)
      if (timer === null) pump()
    },
    setSpeed(next) {
      speed = next
      if (next === 0 && timer !== null) {
        clearTimeout(timer)
        pump()
      }
    },
    stop() {
      if (timer !== null) clearTimeout(timer)
      timer = null
      queue = []
    },
  }
}
