import { Link } from 'react-router'
import { api, unwrap } from '../api/client'
import { useResource } from '../api/useResource'
import { GameHeader } from './GameHeader'

const loadMinigames = () => unwrap(api.GET('/api/v1/minigames'))

/** Playable sketches, kept apart from the Pond: nothing here changes a duck (ADR-0017). */
export function MinigameTestsPage() {
  const { data, error } = useResource(loadMinigames)
  return (
    <section aria-labelledby="minigame-tests-title">
      <GameHeader back={{ to: '/pond', label: 'Pond' }} />
      <h1 id="minigame-tests-title">Minigame tests</h1>
      <p className="hint">
        Rough sketches to play and judge. Nothing here is saved or changes a duck.
      </p>
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}
      <nav className="tiles" aria-label="Minigame tests">
        {data?.map((info) => (
          <Link key={info.id} className="tile" to={`/minigame-tests/${info.id}`}>
            <h2>{info.title}</h2>
            <p>{info.blurb}</p>
            <p className="hint">{info.teaches}</p>
          </Link>
        ))}
      </nav>
    </section>
  )
}
