import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { api, messageOf, unwrap } from '../api/client'
import { useResource } from '../api/useResource'
import { SparringGameView } from '../play/SparringGameView'
import { GameHeader } from './GameHeader'

/** Time controls on offer; untimed is the default (John, 2026-11-21). */
const TIME_CONTROLS = [
  { id: 'untimed', label: 'Untimed', control: null },
  { id: '30s', label: '30 seconds', control: { baseSeconds: 30, incrementSeconds: 0 } },
  { id: '1m', label: '1 minute', control: { baseSeconds: 60, incrementSeconds: 0 } },
  { id: '3m', label: '3 minutes', control: { baseSeconds: 180, incrementSeconds: 0 } },
  { id: '5m', label: '5 + 3', control: { baseSeconds: 300, incrementSeconds: 3 } },
  { id: '10m', label: '10 minutes', control: { baseSeconds: 600, incrementSeconds: 0 } },
] as const
const COLORS = ['white', 'random', 'black'] as const

async function loadSetup() {
  const [profile, ducks, challengers, engines, recent] = await Promise.all([
    unwrap(api.GET('/api/v1/profile')),
    unwrap(api.GET('/api/v1/ducks')),
    unwrap(api.GET('/api/v1/challengers')),
    unwrap(api.GET('/api/v1/engines')),
    unwrap(api.GET('/api/v1/sparring', { params: { query: { limit: 10 } } })),
  ])
  const engine = engines.find((candidate) => candidate.status === 'installed') ?? null
  const everyone = [...ducks, ...challengers.map((challenger) => challenger.duck)]
  return { profile, ducks, everyone, engine, recent }
}

/** `/pond/practice`: play your duck. `/pond/practice/:gameId`: the game itself. */
export function PracticePage() {
  const { gameId } = useParams()
  const { data } = useResource(loadSetup)
  const navigate = useNavigate()
  return (
    <section className="practice" aria-labelledby="practice-title">
      <GameHeader back={{ to: '/pond', label: 'Pond' }} />
      <h1 id="practice-title">Practice Pond</h1>
      {gameId ? (
        <>
          <SparringGameView key={gameId} gameId={gameId} ducks={data?.everyone ?? []} />
          <div className="actions">
            <button type="button" onClick={() => navigate('/pond/practice')}>
              New game
            </button>
          </div>
        </>
      ) : (
        <PracticeSetup />
      )}
    </section>
  )
}

function PracticeSetup() {
  const navigate = useNavigate()
  const { data, error: loadError } = useResource(loadSetup)
  const [color, setColor] = useState<(typeof COLORS)[number]>('white')
  const [timeId, setTimeId] = useState<string>('untimed')
  const [opponentId, setOpponentId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [actionError, setError] = useState('')
  const error = actionError || loadError

  if (!data) return <p role="status">Loading…</p>
  const opponent = opponentId ?? data.profile.activeDuckId ?? data.ducks[0]?.id ?? null
  const unfinished = data.recent.filter((game) => game.state === 'running')

  const start = async () => {
    if (!opponent || !data.engine) return
    setBusy(true)
    setError('')
    try {
      const control = TIME_CONTROLS.find((option) => option.id === timeId)?.control ?? null
      const game = await unwrap(
        api.POST('/api/v1/sparring', {
          body: {
            duckId: opponent,
            engineId: data.engine.id,
            humanColor: color,
            timeControl: control,
          },
        }),
      )
      navigate(`/pond/practice/${game.id}`)
    } catch (requestError) {
      setError(messageOf(requestError))
      setBusy(false)
    }
  }

  return (
    <>
      <p className="hint">Play your duck, or a challenger. Never rated; your duck still learns.</p>
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}
      {!data.engine && (
        <p className="alert" role="alert">
          Install Stockfish in the Lab (Engines) first.
        </p>
      )}
      {unfinished.length > 0 && (
        <div className="panel">
          <h2>Unfinished games</h2>
          <ul className="games">
            {unfinished.map((game) => (
              <li key={game.id}>
                Against {data.everyone.find((duck) => duck.id === game.duckId)?.name ?? 'a duck'} ·{' '}
                {game.moves.length} moves <Link to={`/pond/practice/${game.id}`}>Continue</Link>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="panel">
        <div className="field-grid">
          <label>
            Opponent
            <select value={opponent ?? ''} onChange={(e) => setOpponentId(e.target.value)}>
              {data.everyone.map((duck) => (
                <option key={duck.id} value={duck.id}>
                  {duck.name} (level {duck.growth.level})
                </option>
              ))}
            </select>
          </label>
          <label>
            Time control
            <select value={timeId} onChange={(e) => setTimeId(e.target.value)}>
              {TIME_CONTROLS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="best-of" role="radiogroup" aria-label="Your colour">
          {COLORS.map((option) => (
            <label key={option} className={option === color ? 'choice selected' : 'choice'}>
              <input
                type="radio"
                name="colour"
                value={option}
                checked={option === color}
                onChange={() => setColor(option)}
              />
              {option === 'random' ? 'Random' : `Play ${option}`}
            </label>
          ))}
        </div>
        <div className="actions">
          <button
            type="button"
            className="primary big"
            disabled={busy || !opponent || !data.engine}
            onClick={() => void start()}
          >
            Play
          </button>
        </div>
      </div>
    </>
  )
}
