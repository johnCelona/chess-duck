import { Link } from 'react-router'
import { DuckSprite } from '../components/DuckSprite'

export function NotFoundPage() {
  return (
    <section className="not-found" aria-labelledby="not-found-title">
      <DuckSprite pose="still" size={96} />
      <h1 id="not-found-title">This pond is empty</h1>
      <p>There is nothing at this address.</p>
      <Link className="button" to="/">
        Back to the title
      </Link>
    </section>
  )
}
