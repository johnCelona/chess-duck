import { Link, useParams } from 'react-router'
import { tileFor } from '../pond/tiles'
import { GameHeader } from './GameHeader'
import { NotFoundPage } from './NotFoundPage'

/** Placeholder for a Pond tile that is not built yet. */
export function ComingSoonPage() {
  const tile = tileFor(useParams().tile)
  if (!tile?.soon) return <NotFoundPage />
  return (
    <section className="coming-soon" aria-labelledby="soon-title">
      <GameHeader back={{ to: '/pond', label: 'Pond' }} />
      <div className="panel">
        <h1 id="soon-title">{tile.title}</h1>
        <p>{tile.soon}</p>
        <p className="hint">Coming soon.</p>
        <Link className="button" to="/pond">
          Back to the pond
        </Link>
      </div>
    </section>
  )
}
