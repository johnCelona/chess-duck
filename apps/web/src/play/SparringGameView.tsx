import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { Duck } from '../api/client'
import { Board } from '../components/Board'
import { DuckSprite } from '../components/DuckSprite'
import { MoveList } from '../match/MoveList'
import { ThinkingPanel } from '../match/ThinkingPanel'
import { formatClock } from '../match/playback'
import { useSparringGame, type SparringGame } from './useSparringGame'

const PROMOTIONS = [
  { piece: 'q', label: 'Queen' },
  { piece: 'r', label: 'Rook' },
  { piece: 'b', label: 'Bishop' },
  { piece: 'n', label: 'Knight' },
] as const

/** Ticks while `running`, so a clock can count down between server updates. */
function useNow(running: boolean): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!running) return
    const timer = setInterval(() => setNow(Date.now()), 100)
    return () => clearInterval(timer)
  }, [running])
  return now
}

function resultText(game: SparringGame, duckName: string): string {
  const how = game.termination?.replaceAll('_', ' ') ?? ''
  if (game.winner === 'human') return `You win (${how})`
  if (game.winner === 'duck') return `${duckName} wins (${how})`
  return `Draw (${how})`
}

/**
 * A live game against a duck: drag a move (or type it), the duck replies, the clocks
 * run if the game is timed. Afterwards, step through the moves with the "why" panel.
 */
export function SparringGameView({
  gameId,
  ducks,
  onFinished,
}: {
  gameId: string
  /** Ducks to find the opponent's name and look in (yours and the challengers). */
  ducks: Duck[]
  onFinished?: (game: SparringGame) => void
}) {
  const { game, fetchedAt, error, decisions, move, resign, claimTimeout } = useSparringGame(gameId)
  const [typed, setTyped] = useState('')
  const [promotion, setPromotion] = useState<string[] | null>(null)
  const [reviewPly, setReviewPly] = useState<number | null>(null)
  const claimed = useRef(false)
  const reported = useRef<string | null>(null)

  const timed = !!game?.timeControl
  const yourTurn = !!game && game.state === 'running' && game.legalMoves.length > 0
  const now = useNow(timed && yourTurn)
  const duck = ducks.find((candidate) => candidate.id === game?.duckId) ?? null
  const duckName = duck?.name ?? 'Your duck'

  const clock = (color: 'white' | 'black'): number | null => {
    if (!game) return null
    const value = color === 'white' ? game.whiteClockMs : game.blackClockMs
    if (value === null || !yourTurn || color !== game.humanColor) return value
    return Math.max(0, value - (now - fetchedAt))
  }
  const yourClock = game ? clock(game.humanColor) : null

  // Your flag fell on screen: ask the server to check and end the game.
  useEffect(() => {
    if (yourTurn && timed && yourClock === 0 && !claimed.current) {
      claimed.current = true
      void claimTimeout()
    }
  }, [yourTurn, timed, yourClock, claimTimeout])

  useEffect(() => {
    if (game?.state === 'finished' && reported.current !== game.id) {
      reported.current = game.id
      onFinished?.(game)
    }
  }, [game, onFinished])

  if (!game) {
    return error ? (
      <div className="alert" role="alert">
        {error}
      </div>
    ) : (
      <p role="status">Setting up the board…</p>
    )
  }

  const play = (candidates: string[]) => {
    if (candidates.length === 1) void move(candidates[0])
    else if (timed) void move(candidates.find((uci) => uci.endsWith('q')) ?? candidates[0])
    else setPromotion(candidates)
  }
  const playTyped = (event: FormEvent) => {
    event.preventDefault()
    const uci = typed.trim().toLowerCase()
    if (game.legalMoves.includes(uci)) {
      setTyped('')
      void move(uci)
    }
  }

  // After the game, the board can show any earlier position.
  const finished = game.state === 'finished'
  const shownPly = finished && reviewPly !== null ? reviewPly : game.moves.length
  const shown = shownPly > 0 ? game.moves[shownPly - 1] : null
  const fen = shown ? shown.fenAfter : game.initialFen
  const last = shown ? ([shown.uci.slice(0, 2), shown.uci.slice(2, 4)] as [string, string]) : null
  const duckColor = game.humanColor === 'white' ? 'black' : 'white'

  const status = finished
    ? resultText(game, duckName)
    : yourTurn
      ? 'Your move'
      : `${duckName} is thinking…`

  return (
    <div className="watch sparring">
      <div className="watch-board">
        <div className={`player-bar ${!finished && !yourTurn ? 'active' : ''}`}>
          <DuckSprite skin={duck?.avatar.skin} size={32} />
          <span className="player-name">{duckName}</span>
          {timed && <span className="clock">{formatClock(clock(duckColor))}</span>}
        </div>
        <Board
          fen={fen}
          lastMove={last}
          check={!shown || shownPly === game.moves.length ? game.check : false}
          orientation={game.humanColor}
          legalMoves={finished ? undefined : game.legalMoves}
          movableColor={game.humanColor}
          onMove={play}
        />
        <div className={`player-bar ${yourTurn ? 'active' : ''}`}>
          <span className="player-name">You</span>
          {timed && <span className="clock">{formatClock(yourClock)}</span>}
        </div>
        {promotion && (
          <div className="promotion" role="group" aria-label="Promote to">
            {PROMOTIONS.map(({ piece, label }) => (
              <button
                key={piece}
                type="button"
                onClick={() => {
                  setPromotion(null)
                  const uci = promotion.find((candidate) => candidate.endsWith(piece))
                  if (uci) void move(uci)
                }}
              >
                {label}
              </button>
            ))}
          </div>
        )}
        {!finished && (
          <form className="actions typed-move" onSubmit={playTyped}>
            <label>
              Type a move
              <input
                value={typed}
                onChange={(event) => setTyped(event.target.value)}
                placeholder="e2e4"
                disabled={!yourTurn}
                maxLength={5}
              />
            </label>
            <button type="submit" disabled={!yourTurn || !game.legalMoves.includes(typed.trim())}>
              Play
            </button>
            <button type="button" className="danger" onClick={() => void resign()}>
              Resign
            </button>
          </form>
        )}
      </div>

      <div className="watch-side">
        <div className="panel match-status" aria-live="polite">
          <h2>{status}</h2>
          <p className="hint">
            {timed
              ? `${game.timeControl!.baseSeconds}s + ${game.timeControl!.incrementSeconds}s · never rated`
              : 'Untimed · never rated'}
          </p>
          {error && (
            <div className="alert" role="alert">
              {error}
            </div>
          )}
        </div>
        <div className="panel">
          <h3>Moves</h3>
          {game.moves.length > 0 ? (
            <MoveList
              moves={game.moves.map((m) => ({
                ...m,
                source: m.by === 'duck' ? decisions.get(m.ply)?.source : null,
              }))}
              selectedPly={shownPly}
              onSelect={(ply) => finished && setReviewPly(ply)}
            />
          ) : (
            <p className="hint moves">No moves yet.</p>
          )}
        </div>
        {finished ? (
          <ThinkingPanel
            decision={shown ? (decisions.get(shown.ply) ?? null) : null}
            duckName={() => duckName}
            emptyText={
              shown?.by === 'human'
                ? 'Your move. Pick one of your duck’s moves to see why it played it.'
                : 'Pick one of your duck’s moves to see why it played it.'
            }
          />
        ) : (
          <section className="panel thinking" aria-label="Why the duck played its move">
            <h3>Why this move?</h3>
            <p className="hint">Your duck explains its moves after the game.</p>
          </section>
        )}
      </div>
    </div>
  )
}
