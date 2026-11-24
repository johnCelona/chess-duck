import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { api, unwrap, type Schemas } from '../api/client'
import { useResource } from '../api/useResource'
import { Board } from '../components/Board'
import { DuckSprite } from '../components/DuckSprite'
import { useCountdown, useMinigame, type MinigameRun } from '../minigames/useMinigame'
import { GameHeader } from './GameHeader'

const loadMinigames = () => unwrap(api.GET('/api/v1/minigames'))

/** Plays any minigame test. Everything shown, and every input, comes from the server. */
export function MinigamePage() {
  const { kind = '' } = useParams()
  return <Minigame key={kind} kind={kind} />
}

function Minigame({ kind }: { kind: string }) {
  const { data: all, error: listError } = useResource(loadMinigames)
  const { run, error, start, act, frame, skip } = useMinigame(kind)
  // A promotion question belongs to the position it was asked in.
  const [asked, setAsked] = useState<{ run: MinigameRun | null; moves: string[] } | null>(null)
  const left = useCountdown(run, () => act('timeout'))
  const info = all?.find((item) => item.id === kind)

  // Games with difficulties ask first; the others start at once.
  const [reopened, setReopened] = useState(false)
  const hasLevels = !!info && info.levels.length > 0
  const choosing = hasLevels && (reopened || (!run && !error))
  const startsAtOnce = !!info && !hasLevels
  useEffect(() => {
    if (startsAtOnce) void start()
  }, [startsAtOnce, start])

  const squares = (pair: { origin: string; target: string } | null): [string, string] | null =>
    pair && [pair.origin, pair.target]
  const promotion = asked && asked.run === run ? asked.moves : null
  const open = !!run && run.phase === 'play' && !frame && !promotion

  return (
    <section className="minigame" aria-labelledby="minigame-title">
      <GameHeader back={{ to: '/minigame-tests', label: 'Minigame tests' }} />
      <h1 id="minigame-title">{info?.title ?? 'Minigame'}</h1>
      {listError && (
        <div className="alert" role="alert">
          {listError}
        </div>
      )}
      {all && !info && <p className="empty">There is no such minigame.</p>}
      {error && (
        <div className="alert" role="alert">
          {error}{' '}
          <button type="button" onClick={() => void start(undefined, run?.level)}>
            Start again
          </button>
        </div>
      )}
      {choosing && (
        <DifficultyMenu
          levels={info?.levels ?? []}
          onChoose={(level) => {
            setReopened(false)
            void start(undefined, level)
          }}
          onCancel={run ? () => setReopened(false) : undefined}
        />
      )}
      {run && (
        <div className="watch">
          <Board
            fen={frame?.fen ?? run.board.fen}
            lastMove={squares(frame ? frame.lastMove : run.board.lastMove)}
            check={!frame && run.board.check}
            orientation={run.board.orientation}
            legalMoves={open ? run.moves : []}
            movableColor={run.board.orientation}
            coordinates={run.board.coordinates}
            onSquare={(square) => {
              if (open && run.squares.includes(square)) act('square', square)
            }}
            marks={frame ? [] : run.marks}
            arrows={frame ? [] : run.arrows}
            resetKey={run}
            onMove={(candidates) =>
              candidates.length > 1
                ? setAsked({ run, moves: candidates })
                : act('move', candidates[0])
            }
          />
          <div>
            <div className="panel">
              <p className="minigame-status">
                <span>
                  Round {run.round}/{run.rounds}
                </span>
                <span>Score {run.score}</span>
                {run.hearts !== null && (
                  <span aria-label={`${run.hearts} hearts`}>
                    {'♥'.repeat(run.hearts) || 'no hearts'}
                  </span>
                )}
                {left !== null && <span className="clock">{Math.ceil(left / 1000)}s</span>}
              </p>
              <p className="minigame-prompt">{run.prompt}</p>
              {run.notes.map((note) => (
                <p key={note} className="hint">
                  {note}
                </p>
              ))}
              <div className={`minigame-feedback ${run.feedback?.tone ?? ''}`} role="status">
                {frame ? (
                  frame.caption
                ) : run.phase === 'done' ? (
                  <strong>
                    {run.feedback?.text === 'Time!' && 'Time! '}Run over: {run.score} points.
                  </strong>
                ) : (
                  run.feedback?.text
                )}
              </div>
              <div className="actions">
                {hasLevels && (
                  <button type="button" onClick={() => setReopened(true)}>
                    Difficulty: {info.levels.find((level) => level.id === run.level)?.label}
                  </button>
                )}
                {frame && (
                  <button type="button" onClick={skip}>
                    Skip
                  </button>
                )}
                {promotion?.map((uci) => (
                  <button key={uci} type="button" onClick={() => act('move', uci)}>
                    Promote to {PIECES[uci[4]]}
                  </button>
                ))}
                {open &&
                  run.choices.map((choice) => (
                    <button
                      key={choice.id}
                      type="button"
                      title={choice.detail}
                      onClick={() => act('choice', choice.id)}
                    >
                      {choice.label}
                      {choice.detail && <small> {choice.detail}</small>}
                    </button>
                  ))}
                {open && run.canHint && (
                  <button type="button" onClick={() => act('hint')}>
                    Hint
                  </button>
                )}
                {!frame && run.phase === 'review' && (
                  <button type="button" className="primary" onClick={() => act('next')}>
                    Next
                  </button>
                )}
                {run.phase === 'done' && (
                  <>
                    <button
                      type="button"
                      className="primary"
                      onClick={() => void start(undefined, run.level)}
                    >
                      Play again
                    </button>
                    <button type="button" onClick={() => void start(run.seed, run.level)}>
                      Same puzzles again
                    </button>
                  </>
                )}
              </div>
              <DuckSprite
                pose={run.phase !== 'play' && run.feedback?.tone === 'good' ? 'celebrate' : 'idle'}
              />
            </div>
            {info && (
              <details className="panel" open>
                <summary>How to play</summary>
                <p>{info.howTo}</p>
                <p className="hint">Teaches: {info.teaches}</p>
                <p className="hint">Seed {run.seed}</p>
              </details>
            )}
          </div>
        </div>
      )}
    </section>
  )
}

function DifficultyMenu({
  levels,
  onChoose,
  onCancel,
}: {
  levels: Schemas['MinigameLevelOut'][]
  onChoose: (level: string) => void
  /** Back to the run in progress; without one, back to the list. */
  onCancel?: () => void
}) {
  return (
    <div className="menu-backdrop">
      <div className="panel menu" role="dialog" aria-modal="true" aria-labelledby="difficulty">
        <h2 id="difficulty">Choose a difficulty</h2>
        {levels.map((level, index) => (
          <button
            key={level.id}
            type="button"
            autoFocus={index === 0}
            onClick={() => onChoose(level.id)}
          >
            <strong>{level.label}</strong>
            <br />
            <small>{level.detail}</small>
          </button>
        ))}
        {onCancel ? (
          <button type="button" onClick={onCancel}>
            Keep playing
          </button>
        ) : (
          <Link className="button" to="/minigame-tests">
            Back
          </Link>
        )}
      </div>
    </div>
  )
}

const PIECES: Record<string, string> = { q: 'queen', r: 'rook', b: 'bishop', n: 'knight' }
