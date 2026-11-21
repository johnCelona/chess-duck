// Turns the match event stream into what the screen shows. This is presentation
// state only: the board position, clocks and results all come from the events.
// There are no chess rules here (CLAUDE.md rule 2).
import type { EventEnvelope, EventOf } from '../api/client'

export type Decision = EventOf<'MoveChosen'>['data']

export type MoveRow = {
  ply: number
  color: 'white' | 'black'
  san: string
  uci: string
  source: string
  thinkMs: number
  // Everything needed to show the position after this move again.
  fenAfter: string
  lastMove: [string, string]
  check: boolean
  whiteClockMs: number | null
  blackClockMs: number | null
  /** Why the duck chose this move (null if the decision event was not seen). */
  decision: Decision | null
}

export type GameView = {
  id: string
  index: number
  whiteDuckId: string
  blackDuckId: string
  initialFen: string
  initialWhiteClockMs: number | null
  initialBlackClockMs: number | null
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
  /** The latest decision, kept until its move arrives. */
  thinking: Decision | null
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
        initialFen: data.initialFen,
        initialWhiteClockMs: data.whiteClockMs,
        initialBlackClockMs: data.blackClockMs,
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
      const decision =
        view.thinking?.gameId === data.gameId && view.thinking.ply === data.ply
          ? view.thinking
          : null
      const lastMove: [string, string] = [data.uci.slice(0, 2), data.uci.slice(2, 4)]
      return {
        ...next,
        games: updateGame(view, data.gameId, (game) => ({
          ...game,
          fen: data.fenAfter,
          lastMove,
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
              source: decision?.source ?? 'engine',
              thinkMs: data.thinkMs,
              fenAfter: data.fenAfter,
              lastMove,
              check: data.check,
              whiteClockMs: data.whiteClockMs,
              blackClockMs: data.blackClockMs,
              decision,
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

// ----- Moving through a game ------------------------------------------------------

/**
 * Which position is on screen: a game and a ply (0 is the start position, n is after the
 * n-th move). `null` means "follow live": always the newest position.
 */
export type Cursor = { gameIndex: number; ply: number } | null

export type Position = {
  game: GameView
  gameIndex: number
  ply: number
  totalPlies: number
  live: boolean
  fen: string
  lastMove: [string, string] | null
  check: boolean
  turn: 'white' | 'black'
  whiteClockMs: number | null
  blackClockMs: number | null
  /** Why the move that led to this position was played (null at the start). */
  decision: Decision | null
  move: MoveRow | null
}

/** The position a cursor points at, or null before any game has started. */
export function positionAt(view: MatchView, cursor: Cursor): Position | null {
  if (view.games.length === 0) return null
  const live = cursor === null
  const gameIndex = live
    ? view.games.length - 1
    : Math.min(Math.max(cursor.gameIndex, 0), view.games.length - 1)
  const game = view.games[gameIndex]
  const totalPlies = game.moves.length
  const ply = live ? totalPlies : Math.min(Math.max(cursor.ply, 0), totalPlies)
  const move = ply > 0 ? game.moves[ply - 1] : null
  const fen = move ? move.fenAfter : game.initialFen
  return {
    game,
    gameIndex,
    ply,
    totalPlies,
    live,
    fen,
    lastMove: move ? move.lastMove : null,
    check: move ? move.check : false,
    turn: turnFromFen(fen),
    whiteClockMs: move ? move.whiteClockMs : game.initialWhiteClockMs,
    blackClockMs: move ? move.blackClockMs : game.initialBlackClockMs,
    decision: move ? move.decision : null,
    move,
  }
}

/** Every position in the match, in order: each game's start and each move after it. */
function allPositions(view: MatchView): { gameIndex: number; ply: number }[] {
  return view.games.flatMap((game, gameIndex) =>
    Array.from({ length: game.moves.length + 1 }, (_, ply) => ({ gameIndex, ply })),
  )
}

/**
 * Moves the cursor by `delta` plies, across game boundaries. Reaching the newest
 * position returns null, so the view follows the game live again.
 */
export function step(view: MatchView, cursor: Cursor, delta: number): Cursor {
  const positions = allPositions(view)
  if (positions.length === 0) return null
  const last = positions.length - 1
  const here =
    cursor === null
      ? last
      : positions.findIndex((p) => p.gameIndex === cursor.gameIndex && p.ply === cursor.ply)
  const target = Math.min(Math.max((here < 0 ? last : here) + delta, 0), last)
  return target === last ? null : positions[target]
}

/** The very first position of the match (game 1, start). */
export function first(view: MatchView): Cursor {
  return view.games.length > 0 ? { gameIndex: 0, ply: 0 } : null
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

/** Like formatScore, but spells out mates so `#3` is not mistaken for a ranking. */
export function formatEval(candidate: { cp: number | null; mate: number | null }): string {
  if (candidate.mate === null) return formatScore(candidate)
  if (candidate.mate > 0) return `Mate in ${candidate.mate}`
  return `Mated in ${-candidate.mate}`
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
