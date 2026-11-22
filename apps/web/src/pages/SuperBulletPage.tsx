import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { api, messageOf, unwrap, type Arena } from '../api/client'
import { useResource } from '../api/useResource'
import { DuckSprite } from '../components/DuckSprite'
import { ratingLabel } from '../ducks/format'
import { GameHeader } from './GameHeader'
import { MatchPage } from './MatchPage'

/** Thirty seconds each, no increment: at most a minute per game (John, 2026-11-21). */
const SUPER_BULLET_LIMIT: Arena['limit'] = {
  type: 'virtual-clock',
  timeControl: { baseSeconds: 30, incrementSeconds: 0 },
  virtualNps: 200000,
}
const BEST_OF = [3, 5, 7, 15] as const

async function loadSetup() {
  const [profile, ducks, challengers, engines] = await Promise.all([
    unwrap(api.GET('/api/v1/profile')),
    unwrap(api.GET('/api/v1/ducks')),
    unwrap(api.GET('/api/v1/challengers')),
    unwrap(api.GET('/api/v1/engines')),
  ])
  const installed = engines.filter((engine) => engine.status === 'installed')
  return { profile, ducks, challengers, engine: installed[0] ?? null }
}

function newSeed(): number {
  const [value] = crypto.getRandomValues(new Uint32Array(1))
  return value
}

/** `/arena/super-bullet` sets up a series; `/arena/super-bullet/:matchId` watches one. */
export function SuperBulletPage() {
  const { matchId } = useParams()
  return (
    <div className="super-bullet">
      <GameHeader back={{ to: '/arena', label: 'Arena' }} />
      {matchId ? (
        <MatchPage
          matchId={matchId}
          basePath="/arena/super-bullet"
          title="Super Bullet Arena"
          showSetup={false}
        />
      ) : (
        <SeriesSetup />
      )}
    </div>
  )
}

function SeriesSetup() {
  const navigate = useNavigate()
  const { data, error: loadError } = useResource(loadSetup)
  const [opponentId, setOpponentId] = useState<string | null>(null)
  const [bestOf, setBestOf] = useState<number>(5)
  const [busy, setBusy] = useState(false)
  const [actionError, setError] = useState('')
  const error = actionError || loadError

  if (!data) {
    return error ? (
      <div className="alert" role="alert">
        {error}
      </div>
    ) : (
      <p role="status">Loading the arena…</p>
    )
  }

  const you = data.ducks.find((duck) => duck.id === data.profile.activeDuckId) ?? null
  const yourOthers = data.ducks.filter((duck) => duck.id !== you?.id)
  const opponent = opponentId ?? data.challengers[0]?.duck.id ?? null

  const start = async () => {
    if (!you || !opponent || !data.engine) return
    setBusy(true)
    setError('')
    try {
      const match = await unwrap(
        api.POST('/api/v1/matches', {
          body: {
            duckIds: [you.id, opponent],
            arena: {
              engine: { id: data.engine.id, threads: 1, hashMb: 16 },
              limit: SUPER_BULLET_LIMIT,
              multiPV: 5,
              games: bestOf,
              seed: newSeed(),
              swapColors: true,
              equalEngine: false,
              maxPlies: 400,
            } as Arena,
            rated: true,
            series: { type: 'best-of', bestOf },
          },
        }),
      )
      navigate(`/arena/super-bullet/${match.id}`)
    } catch (requestError) {
      setError(messageOf(requestError))
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="super-bullet-title">
      <h1 id="super-bullet-title">Super Bullet Arena</h1>
      <p className="hint">Thirty seconds a game, no increment. A tied series ends in Armageddon.</p>
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}
      {!data.engine && (
        <p className="alert" role="alert">
          Install Stockfish in the Lab (Engines) before your duck can battle.
        </p>
      )}

      <div className="panel">
        <h2>Who plays</h2>
        <div className="who-plays" role="radiogroup" aria-label="Who plays">
          <label className="choice selected">
            <input type="radio" name="who" checked readOnly />
            {you ? (
              <>
                <DuckSprite skin={you.avatar.skin} size={36} /> {you.name} ({ratingLabel(you)})
              </>
            ) : (
              'Your duck'
            )}
          </label>
          <label className="choice" aria-disabled="true">
            <input type="radio" name="who" disabled />
            You play <small>Coming with Practice Pond</small>
          </label>
        </div>
      </div>

      <div className="panel">
        <h2>Challenger</h2>
        <div className="opponents" role="radiogroup" aria-label="Challenger">
          {data.challengers.map(({ duck, blurb, difficulty }) => (
            <label key={duck.id} className={duck.id === opponent ? 'choice selected' : 'choice'}>
              <input
                type="radio"
                name="opponent"
                value={duck.id}
                checked={duck.id === opponent}
                onChange={() => setOpponentId(duck.id)}
              />
              <DuckSprite skin={duck.avatar.skin} size={44} />
              <span className="opponent-text">
                <strong>{duck.name}</strong>
                <span className="difficulty" aria-label={`Difficulty ${difficulty}`}>
                  {'★'.repeat(difficulty)}
                </span>
                <small>
                  Level {duck.growth.level} · {ratingLabel(duck)} · {blurb}
                </small>
              </span>
            </label>
          ))}
          {yourOthers.length > 0 && <h3>Your other ducks</h3>}
          {yourOthers.map((duck) => (
            <label key={duck.id} className={duck.id === opponent ? 'choice selected' : 'choice'}>
              <input
                type="radio"
                name="opponent"
                value={duck.id}
                checked={duck.id === opponent}
                onChange={() => setOpponentId(duck.id)}
              />
              <DuckSprite skin={duck.avatar.skin} size={44} />
              <span className="opponent-text">
                <strong>{duck.name}</strong>
                <small>
                  Level {duck.growth.level} · {ratingLabel(duck)}
                </small>
              </span>
            </label>
          ))}
        </div>
      </div>

      <div className="panel">
        <h2>Series</h2>
        <div className="best-of" role="radiogroup" aria-label="Best of">
          {BEST_OF.map((n) => (
            <label key={n} className={n === bestOf ? 'choice selected' : 'choice'}>
              <input
                type="radio"
                name="best-of"
                value={n}
                checked={n === bestOf}
                onChange={() => setBestOf(n)}
              />
              Best of {n}
            </label>
          ))}
        </div>
        <div className="actions">
          <button
            type="button"
            className="primary big"
            disabled={busy || !you || !opponent || !data.engine}
            onClick={() => void start()}
          >
            Start the series
          </button>
        </div>
      </div>
    </section>
  )
}
