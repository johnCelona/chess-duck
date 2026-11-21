import { useState, type FormEvent } from 'react'
import { api, duckFileUrl, messageOf, unwrap } from '../api/client'
import { useResource } from '../api/useResource'
import { DuckAvatar } from '../components/DuckAvatar'
import { ratingLabel } from '../ducks/format'

const STAT_NAMES = [
  'calculation',
  'memory',
  'aggression',
  'solidity',
  'creativity',
  'speed',
] as const

const loadDucks = () => unwrap(api.GET('/api/v1/ducks'))

export function DucksPage() {
  const { data: ducks, error: loadError, reload } = useResource(loadDucks)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [actionError, setError] = useState('')
  const error = actionError || loadError

  const hatch = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await unwrap(api.POST('/api/v1/ducks', { body: { name } }))
      setName('')
      reload()
    } catch (requestError) {
      setError(messageOf(requestError))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="ducks-title">
      <h1 id="ducks-title">Ducks</h1>
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}

      <form className="panel hatch-form" onSubmit={hatch}>
        <label>
          Name your duck
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Sir Quackalot"
            maxLength={40}
            required
          />
        </label>
        <button className="primary" type="submit" disabled={busy || !name.trim()}>
          Hatch
        </button>
        <p className="hint">New ducks start at level 1 with an even stat spread.</p>
      </form>

      {ducks === null ? (
        <p role="status">Loading ducks…</p>
      ) : ducks.length === 0 ? (
        <p className="empty">No ducks yet. Hatch your first one above.</p>
      ) : (
        <ul className="duck-list">
          {ducks.map((duck) => (
            <li className="panel duck-card" key={duck.id}>
              <DuckAvatar name={duck.name} />
              <div className="duck-main">
                <h2>{duck.name}</h2>
                <p>
                  Level {duck.growth.level} {duck.growth.stage} ·{' '}
                  <span
                    title={
                      duck.rating.provisional
                        ? 'Provisional: not enough rated games yet'
                        : 'Measured from rated games'
                    }
                  >
                    Rating {ratingLabel(duck)}
                  </span>{' '}
                  · {duck.rating.games} rated {duck.rating.games === 1 ? 'game' : 'games'}
                </p>
                <dl className="stats">
                  {STAT_NAMES.map((stat) => (
                    <div key={stat}>
                      <dt>{stat}</dt>
                      <dd>{duck.stats[stat]}</dd>
                    </div>
                  ))}
                </dl>
              </div>
              <a className="button" href={duckFileUrl(duck.id)} download>
                Export
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
