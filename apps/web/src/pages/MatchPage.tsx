import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { api, messageOf, pgnUrl, unwrap, type Arena, type Match } from '../api/client'
import { subscribe, type Unsubscribe } from '../api/events'
import { useResource } from '../api/useResource'
import { Board } from '../components/Board'
import { DuckAvatar } from '../components/DuckAvatar'
import { ratingLabel } from '../ducks/format'
import {
  applyEvent,
  createPlayer,
  emptyMatchView,
  formatClock,
  formatScore,
  type GameView,
  type MatchView,
  type Player,
} from '../match/playback'

type PresetKey = 'bullet' | 'casual' | 'serious'

// The presets of spec 7.1. Numbers are placeholders until calibration (M3).
const PRESETS: Record<PresetKey, { label: string; limit: Arena['limit']; multiPV: number }> = {
  bullet: {
    label: 'Bullet 1+0 (virtual clock)',
    limit: {
      type: 'virtual-clock',
      timeControl: { baseSeconds: 60, incrementSeconds: 0 },
      virtualNps: 200000,
    },
    multiPV: 5,
  },
  casual: { label: 'Casual (50k nodes)', limit: { type: 'nodes', value: 50000 }, multiPV: 3 },
  serious: { label: 'Serious (500k nodes)', limit: { type: 'nodes', value: 500000 }, multiPV: 5 },
}

const SPEEDS = [
  { value: 1, label: '1×' },
  { value: 4, label: '4×' },
  { value: 0, label: 'Instant' },
]

function randomSeed(): number {
  return Math.floor(Math.random() * 2 ** 31)
}

async function loadSetup() {
  const [ducks, engines, recent] = await Promise.all([
    unwrap(api.GET('/api/v1/ducks')),
    unwrap(api.GET('/api/v1/engines')),
    unwrap(api.GET('/api/v1/matches', { params: { query: { limit: 10 } } })),
  ])
  return { ducks, engines: engines.filter((engine) => engine.status === 'installed'), recent }
}

export function MatchPage({ matchId }: { matchId: string | null }) {
  const setup = useResource(loadSetup)
  const ducks = setup.data?.ducks ?? []
  const engines = setup.data?.engines ?? []
  const recent = setup.data?.recent ?? []

  const [chosenWhite, setWhiteId] = useState('')
  const [chosenBlack, setBlackId] = useState('')
  const [chosenEngine, setEngineId] = useState('')
  const whiteId = chosenWhite || ducks[0]?.id || ''
  const blackId = chosenBlack || ducks[1]?.id || ''
  const engineId = chosenEngine || engines[0]?.id || ''

  const [preset, setPreset] = useState<PresetKey>('bullet')
  const [games, setGames] = useState(1)
  const [seed, setSeed] = useState(randomSeed)
  const [match, setMatch] = useState<Match | null>(null)
  const [view, setView] = useState<MatchView>(emptyMatchView)
  const [speed, setSpeed] = useState(1)
  const [busy, setBusy] = useState(false)
  const [actionError, setError] = useState('')
  const error = actionError || setup.error

  const player = useRef<Player | null>(null)
  const speedRef = useRef(1)
  const stream = useRef<Unsubscribe | null>(null)
  const reloadSetup = setup.reload

  const stopWatching = useCallback(() => {
    stream.current?.()
    stream.current = null
    player.current?.stop()
    player.current = null
  }, [])

  useEffect(() => stopWatching, [stopWatching])

  // Following a live match and replaying a finished one are the same thing:
  // read the match's event stream from the start.
  const watch = useCallback(
    (target: Match) => {
      stopWatching()
      setMatch(target)
      setView(emptyMatchView)
      const playback = createPlayer((event) => {
        setView((current) => applyEvent(current, event))
        if (event.type === 'MatchFinished') reloadSetup() // ratings changed
      }, speedRef.current)
      player.current = playback
      stream.current = subscribe([target.stream, `job:${target.jobId}`], (event) => {
        playback.push(event)
        // Nothing follows a finished job, so free the connection; playback carries on.
        if (event.type === 'JobFinished' && event.data.state === 'succeeded') {
          stream.current?.()
          stream.current = null
        }
      })
    },
    [stopWatching, reloadSetup],
  )

  // The address decides which match is on screen, so a link (or a reload) replays it.
  useEffect(() => {
    if (!matchId) return
    let cancelled = false
    unwrap(api.GET('/api/v1/matches/{match_id}', { params: { path: { match_id: matchId } } })).then(
      (found) => {
        if (!cancelled) watch(found)
      },
      (requestError: unknown) => {
        if (!cancelled) setError(messageOf(requestError))
      },
    )
    return () => {
      cancelled = true
    }
  }, [matchId, watch])

  const changeSpeed = (next: number) => {
    setSpeed(next)
    speedRef.current = next
    player.current?.setSpeed(next)
  }

  const start = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const chosen = PRESETS[preset]
      const created = await unwrap(
        api.POST('/api/v1/matches', {
          body: {
            duckIds: [whiteId, blackId],
            arena: {
              engine: { id: engineId, threads: 1, hashMb: 16 },
              limit: chosen.limit,
              multiPV: chosen.multiPV,
              games,
              seed,
              swapColors: true,
              equalEngine: false,
              maxPlies: 400,
            } as Arena,
            rated: true,
          },
        }),
      )
      window.location.hash = `#/match/${created.id}`
    } catch (requestError) {
      setError(messageOf(requestError))
    } finally {
      setBusy(false)
    }
  }

  const jobAction = async (action: 'cancel' | 'resume') => {
    if (!match) return
    setError('')
    try {
      if (action === 'cancel') {
        await unwrap(
          api.PUT('/api/v1/jobs/{job_id}/cancellation', {
            params: { path: { job_id: match.jobId } },
          }),
        )
      } else {
        const resumed = await unwrap(
          api.PUT('/api/v1/matches/{match_id}/resumption', {
            params: { path: { match_id: match.id } },
          }),
        )
        setView((current) => ({ ...current, jobState: null }))
        setMatch(resumed)
      }
    } catch (requestError) {
      setError(messageOf(requestError))
    }
  }

  const duckName = (id: string | null | undefined) =>
    ducks.find((duck) => duck.id === id)?.name ?? 'Unknown duck'
  const current: GameView | undefined = view.games[view.games.length - 1]
  const ready = ducks.length >= 2 && engines.length >= 1
  const stopped = view.jobState === 'cancelled' || view.jobState === 'interrupted'

  return (
    <section aria-labelledby="match-title">
      <h1 id="match-title">Match</h1>
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}

      <form className="panel match-form" onSubmit={start}>
        {!ready && (
          <p className="hint">
            A match needs two ducks and an installed engine. Hatch ducks on the Ducks page and
            install Stockfish on the Engines page.
          </p>
        )}
        <div className="field-grid">
          <label>
            White in game 1
            <select value={whiteId} onChange={(e) => setWhiteId(e.target.value)}>
              {ducks.map((duck) => (
                <option key={duck.id} value={duck.id}>
                  {duck.name} ({ratingLabel(duck)})
                </option>
              ))}
            </select>
          </label>
          <label>
            Black in game 1
            <select value={blackId} onChange={(e) => setBlackId(e.target.value)}>
              {ducks.map((duck) => (
                <option key={duck.id} value={duck.id}>
                  {duck.name} ({ratingLabel(duck)})
                </option>
              ))}
            </select>
          </label>
          <label>
            Engine (same for both ducks)
            <select value={engineId} onChange={(e) => setEngineId(e.target.value)}>
              {engines.map((engine) => (
                <option key={engine.id} value={engine.id}>
                  {engine.name} {engine.version}
                </option>
              ))}
            </select>
          </label>
          <label>
            Arena
            <select value={preset} onChange={(e) => setPreset(e.target.value as PresetKey)}>
              {Object.entries(PRESETS).map(([key, value]) => (
                <option key={key} value={key}>
                  {value.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Games
            <input
              type="number"
              min={1}
              max={20}
              value={games}
              onChange={(e) => setGames(Number(e.target.value))}
            />
          </label>
          <label>
            Seed
            <input
              type="number"
              min={0}
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
            />
          </label>
        </div>
        <div className="actions">
          <button type="button" onClick={() => setSeed(randomSeed())}>
            New seed
          </button>
          <button
            className="primary"
            type="submit"
            disabled={busy || !ready || whiteId === blackId}
          >
            Start match
          </button>
        </div>
        <p className="hint">
          The same ducks, arena and seed always produce the same games, on any computer.
        </p>
      </form>

      {match && (
        <div className="watch">
          <div className="watch-board">
            <PlayerBar
              name={duckName(current?.blackDuckId)}
              clockMs={current?.blackClockMs ?? null}
              active={!current?.result && current?.turn === 'black'}
            />
            <Board
              fen={current?.fen ?? 'start'}
              lastMove={current?.lastMove}
              check={current?.check}
            />
            <PlayerBar
              name={duckName(current?.whiteDuckId)}
              clockMs={current?.whiteClockMs ?? null}
              active={!current?.result && current?.turn === 'white'}
            />
            <div className="actions">
              <span className="speed" role="group" aria-label="Playback speed">
                {SPEEDS.map((option) => (
                  <button
                    key={option.label}
                    type="button"
                    className={speed === option.value ? 'selected' : ''}
                    aria-pressed={speed === option.value}
                    onClick={() => changeSpeed(option.value)}
                  >
                    {option.label}
                  </button>
                ))}
              </span>
              {view.status !== 'finished' && !stopped && (
                <button type="button" onClick={() => void jobAction('cancel')}>
                  Stop
                </button>
              )}
              {stopped && (
                <button type="button" onClick={() => void jobAction('resume')}>
                  Resume
                </button>
              )}
            </div>
          </div>

          <div className="watch-side">
            <div className="panel" aria-live="polite">
              <h2>
                {view.status === 'finished'
                  ? view.winnerDuckId
                    ? `${duckName(view.winnerDuckId)} wins the match`
                    : 'The match is drawn'
                  : stopped
                    ? 'Match stopped'
                    : view.status === 'waiting'
                      ? 'Waiting for the match to start…'
                      : `Game ${(current?.index ?? 0) + 1} of ${match.arena.games}`}
              </h2>
              <ul className="games">
                {view.games.map((game) => (
                  <li key={game.id}>
                    Game {game.index + 1}: {duckName(game.whiteDuckId)} –{' '}
                    {duckName(game.blackDuckId)}{' '}
                    {game.result ? (
                      <>
                        <strong>{game.result}</strong> ({game.termination?.replaceAll('_', ' ')}){' '}
                        <a href={pgnUrl(game.id)} download>
                          Download PGN
                        </a>
                      </>
                    ) : (
                      <em>in progress</em>
                    )}
                  </li>
                ))}
              </ul>
            </div>

            {current && (
              <div className="panel">
                <h3>Moves</h3>
                <ol className="moves">
                  {current.moves.map((move) => (
                    <li key={move.ply} className={move.color}>
                      {move.color === 'white' && (
                        <span className="number">{(move.ply + 1) / 2}.</span>
                      )}
                      <span title={move.source === 'engine' ? undefined : move.source}>
                        {move.san}
                        {move.source !== 'engine' && <sup>{move.source[0]}</sup>}
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {view.thinking && (
              <div className="panel thinking">
                <h3>
                  Why {duckName(view.thinking.duckId)} played {view.thinking.san}
                </h3>
                <ul className="reasons">
                  {view.thinking.reasons.map((reason, index) => (
                    <li key={`${reason.code}-${index}`}>{reason.text}</li>
                  ))}
                </ul>
                {view.thinking.candidates.length > 0 && (
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">Move</th>
                        <th scope="col">Engine</th>
                        <th scope="col">Style</th>
                        <th scope="col">Chance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {view.thinking.candidates.map((candidate) => (
                        <tr
                          key={candidate.move}
                          className={[
                            candidate.move === view.thinking?.move ? 'chosen' : '',
                            candidate.filtered ? 'filtered' : '',
                          ].join(' ')}
                        >
                          <th scope="row">{candidate.san}</th>
                          <td>{formatScore(candidate)}</td>
                          <td>
                            {candidate.adjustments.length === 0
                              ? '–'
                              : candidate.adjustments
                                  .map(
                                    (a) =>
                                      `${a.ruleId} ${a.deltaCp >= 0 ? '+' : ''}${(a.deltaCp / 100).toFixed(2)}`,
                                  )
                                  .join(', ')}
                          </td>
                          <td>
                            {candidate.filtered
                              ? 'ruled out'
                              : `${(candidate.probabilityPpm / 10000).toFixed(1)}%`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {recent.length > 0 && (
        <div className="panel">
          <h2>Recent matches</h2>
          <ul className="games">
            {recent.map((item) => (
              <li key={item.id}>
                {item.duckIds.map(duckName).join(' – ')} · {item.state}{' '}
                <a href={`#/match/${item.id}`}>{item.state === 'finished' ? 'Replay' : 'Watch'}</a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function PlayerBar({
  name,
  clockMs,
  active,
}: {
  name: string
  clockMs: number | null
  active: boolean
}) {
  return (
    <div className={`player-bar ${active ? 'active' : ''}`}>
      <DuckAvatar name={name} size={32} />
      <span className="player-name">{name}</span>
      <span className="clock">{formatClock(clockMs)}</span>
    </div>
  )
}
