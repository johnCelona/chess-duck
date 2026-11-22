import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, messageOf, pgnUrl, unwrap, type Arena, type Match } from '../api/client'
import { latestCursor, subscribe, type Unsubscribe } from '../api/events'
import { newsFor } from '../ducks/usePond'
import { useResource } from '../api/useResource'
import { Board } from '../components/Board'
import { DuckSprite } from '../components/DuckSprite'
import { ratingLabel } from '../ducks/format'
import { MoveList } from '../match/MoveList'
import { ThinkingPanel } from '../match/ThinkingPanel'
import {
  applyEvent,
  createPlayer,
  emptyMatchView,
  first,
  formatClock,
  positionAt,
  step,
  type Cursor,
  type MatchView,
  type Player,
  type Series,
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
  const [ducks, challengers, engines, recent] = await Promise.all([
    unwrap(api.GET('/api/v1/ducks')),
    unwrap(api.GET('/api/v1/challengers')),
    unwrap(api.GET('/api/v1/engines')),
    unwrap(api.GET('/api/v1/matches', { params: { query: { limit: 10 } } })),
  ])
  return {
    ducks,
    // Everyone who can appear in a match: your ducks and the house challengers.
    everyone: [...ducks, ...challengers.map((challenger) => challenger.duck)],
    engines: engines.filter((engine) => engine.status === 'installed'),
    recent,
  }
}

type MatchPageProps = {
  matchId: string | null
  /** Where this page lives: matches open at `${basePath}/${id}` (Arena or Lab). */
  basePath?: string
  title?: string
  /** Preselected White duck, e.g. the Pond's active duck. */
  initialWhiteId?: string | null
  /** Show the custom-match form and recent matches (false when only watching). */
  showSetup?: boolean
}

export function MatchPage({
  matchId,
  basePath = '/lab/match',
  title = 'Match',
  initialWhiteId = null,
  showSetup = true,
}: MatchPageProps) {
  const navigate = useNavigate()
  const setup = useResource(loadSetup)
  const ducks = setup.data?.ducks ?? []
  const everyone = setup.data?.everyone ?? []
  const engines = setup.data?.engines ?? []
  const recent = setup.data?.recent ?? []

  const [chosenWhite, setWhiteId] = useState('')
  const [chosenBlack, setBlackId] = useState('')
  const [chosenEngine, setEngineId] = useState('')
  const preselected = ducks.find((duck) => duck.id === initialWhiteId)?.id
  const whiteId = chosenWhite || preselected || ducks[0]?.id || ''
  const blackId = chosenBlack || ducks.find((duck) => duck.id !== whiteId)?.id || ''
  const engineId = chosenEngine || engines[0]?.id || ''

  const [preset, setPreset] = useState<PresetKey>('bullet')
  const [games, setGames] = useState(1)
  const [seed, setSeed] = useState(randomSeed)
  const [match, setMatch] = useState<Match | null>(null)
  const [view, setView] = useState<MatchView>(emptyMatchView)
  // Which position is on screen; null follows the game live.
  const [cursor, setCursor] = useState<Cursor>(null)
  const viewRef = useRef(view)
  useEffect(() => {
    viewRef.current = view
  }, [view])
  const [speed, setSpeed] = useState(1)
  const [busy, setBusy] = useState(false)
  const [actionError, setError] = useState('')
  const error = actionError || setup.error
  const [news, setNews] = useState<{ duckId: string; text: string }[]>([])

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
    async (target: Match) => {
      stopWatching()
      setMatch(target)
      setView(emptyMatchView)
      setCursor(null)
      setNews([])
      // XP and level-ups land on each duck's stream when the match ends. Show only the ones
      // this match earns, in order after the final move; never old ones, never on a replay.
      const duckStreams = target.duckIds.map((id) => `duck:${id}`)
      const newsAfter =
        target.state === 'finished'
          ? Number.POSITIVE_INFINITY
          : await latestCursor(duckStreams).catch(() => Number.POSITIVE_INFINITY)
      const playback = createPlayer((event) => {
        setView((current) => applyEvent(current, event))
        if (event.type === 'MatchFinished') reloadSetup() // ratings changed
        const item = event.cursor > newsAfter ? newsFor(event) : null
        if (item && (event.type === 'XpGained' || event.type === 'DuckLeveledUp')) {
          const duckId = event.data.duckId
          setNews((current) => [...current, { duckId, text: item }])
        }
      }, speedRef.current)
      player.current = playback
      const streams = [target.stream, `job:${target.jobId}`, ...duckStreams]
      stream.current = subscribe(streams, (event) => {
        playback.push(event)
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
        if (!cancelled) void watch(found)
      },
      (requestError: unknown) => {
        if (!cancelled) setError(messageOf(requestError))
      },
    )
    return () => {
      cancelled = true
    }
  }, [matchId, watch])

  // Arrow keys step through the moves; Home and End jump to the start and to live.
  useEffect(() => {
    if (!match) return
    const onKey = (event: KeyboardEvent) => {
      const target = event.target
      const typing =
        target instanceof Element &&
        target.closest('input, select, textarea, [contenteditable="true"]') !== null
      if (typing) return
      if (event.altKey || event.ctrlKey || event.metaKey) return
      const moves: Record<string, (current: Cursor) => Cursor> = {
        ArrowLeft: (current) => step(viewRef.current, current, -1),
        ArrowRight: (current) => step(viewRef.current, current, 1),
        Home: () => first(viewRef.current),
        End: () => null,
      }
      const move = moves[event.key]
      if (!move) return
      event.preventDefault()
      setCursor(move)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [match])

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
      navigate(`${basePath}/${created.id}`)
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
    everyone.find((duck) => duck.id === id)?.name ?? 'Unknown duck'
  const duckSkin = (id: string | null | undefined) =>
    everyone.find((duck) => duck.id === id)?.avatar.skin
  const position = positionAt(view, cursor)
  const current = position?.game
  const atStart = !position || (position.gameIndex === 0 && position.ply === 0)
  const clockActive = (side: 'white' | 'black') =>
    !!position && !(position.live && current?.result) && position.turn === side
  const ready = ducks.length >= 2 && engines.length >= 1
  const stopped = view.jobState === 'cancelled' || view.jobState === 'interrupted'

  return (
    <section aria-labelledby="match-title">
      <h1 id="match-title">{title}</h1>
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}

      {showSetup && (
        <form className="panel match-form" onSubmit={start}>
          {!ready && (
            <p className="hint">
              A match needs two ducks and an installed engine. Hatch another egg from the Pond, and
              install Stockfish in the Lab (Engines).
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
      )}

      {match && (
        <div className="watch">
          <div className="watch-board">
            <PlayerBar
              name={duckName(current?.blackDuckId)}
              skin={duckSkin(current?.blackDuckId)}
              clockMs={position?.blackClockMs ?? null}
              active={clockActive('black')}
            />
            <Board
              fen={position?.fen ?? 'start'}
              lastMove={position?.lastMove}
              check={position?.check}
            />
            <PlayerBar
              name={duckName(current?.whiteDuckId)}
              skin={duckSkin(current?.whiteDuckId)}
              clockMs={position?.whiteClockMs ?? null}
              active={clockActive('white')}
            />
            <div className="navigation" role="group" aria-label="Move through the game">
              <button
                type="button"
                aria-label="First move"
                title="Start (Home)"
                disabled={atStart}
                onClick={() => setCursor(first(view))}
              >
                ⏮
              </button>
              <button
                type="button"
                aria-label="Previous move"
                title="Previous move (←)"
                disabled={atStart}
                onClick={() => setCursor((c) => step(view, c, -1))}
              >
                ◀
              </button>
              <span className="position-label" aria-live="polite">
                {positionLabel(position, view.games.length)}
              </span>
              <button
                type="button"
                aria-label="Next move"
                title="Next move (→)"
                disabled={!position || position.live}
                onClick={() => setCursor((c) => step(view, c, 1))}
              >
                ▶
              </button>
              <button
                type="button"
                aria-label="Latest move"
                title="Latest move, follow live (End)"
                disabled={!position || position.live}
                onClick={() => setCursor(null)}
              >
                ⏭
              </button>
            </div>
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
              {match.state !== 'finished' && view.status !== 'finished' && !stopped && (
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
            <div className="panel match-status" aria-live="polite">
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
              {view.series && <SeriesScore series={view.series} duckName={duckName} />}
              {news.length > 0 && (
                <p className="news" role="status">
                  {news.map((item, index) => (
                    <span key={index}>
                      {duckName(item.duckId)} {item.text}
                    </span>
                  ))}
                </p>
              )}
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

            <div className="panel">
              <h3>Moves</h3>
              {position ? (
                <MoveList
                  moves={position.game.moves}
                  selectedPly={position.ply}
                  onSelect={(ply) => setCursor({ gameIndex: position.gameIndex, ply })}
                />
              ) : (
                <p className="hint moves">No moves yet.</p>
              )}
            </div>

            <ThinkingPanel
              decision={position?.decision ?? null}
              duckName={duckName}
              emptyText={
                !position
                  ? 'Waiting for the first move…'
                  : position.ply === 0
                    ? 'Start position: no move has been played yet.'
                    : 'No explanation was recorded for this move.'
              }
            />
          </div>
        </div>
      )}

      {showSetup && recent.length > 0 && (
        <div className="panel">
          <h2>Recent matches</h2>
          <ul className="games">
            {recent.map((item) => (
              <li key={item.id}>
                {item.duckIds.map(duckName).join(' – ')} · {item.state}{' '}
                <Link to={`${basePath}/${item.id}`}>
                  {item.state === 'finished' ? 'Replay' : 'Watch'}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function SeriesScore({
  series,
  duckName,
}: {
  series: Series
  duckName: (id: string | null | undefined) => string
}) {
  const [first, second] = series.scores
  const points = (value: number) => (value % 1 === 0 ? String(value) : value.toFixed(1))
  return (
    <div className="series" aria-label="Series score">
      <p className="series-score">
        <span>{duckName(first?.duckId)}</span>
        <strong>
          {points(first?.points ?? 0)} – {points(second?.points ?? 0)}
        </strong>
        <span>{duckName(second?.duckId)}</span>
      </p>
      <p className="hint">
        Best of {series.bestOf}
        {series.state === 'decided' &&
          ` · ${duckName(series.winnerDuckId)} wins the series${
            series.decidedBy === 'armageddon' ? ' in Armageddon' : ''
          }`}
      </p>
      {series.state === 'armageddon' && (
        <p className="armageddon" role="status">
          Armageddon! {duckName(series.armageddonWhiteDuckId)} has White. A draw wins the series for
          Black.
        </p>
      )}
    </div>
  )
}

function positionLabel(position: ReturnType<typeof positionAt>, games: number): string {
  if (!position) return 'Waiting…'
  const game = games > 1 ? `Game ${position.gameIndex + 1} · ` : ''
  const ply = position.ply === 0 ? 'Start' : `Move ${position.ply} of ${position.totalPlies}`
  return `${game}${ply}${position.live ? ' · Live' : ''}`
}

function PlayerBar({
  name,
  skin,
  clockMs,
  active,
}: {
  name: string
  skin: string | undefined
  clockMs: number | null
  active: boolean
}) {
  return (
    <div className={`player-bar ${active ? 'active' : ''}`}>
      <DuckSprite skin={skin} size={32} />
      <span className="player-name">{name}</span>
      <span className="clock">{formatClock(clockMs)}</span>
    </div>
  )
}
