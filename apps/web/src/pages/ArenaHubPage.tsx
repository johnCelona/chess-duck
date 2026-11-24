import { Link } from 'react-router'
import { GameHeader } from './GameHeader'

/** The Arena tile: Super Bullet Arena series, or a custom match between any two ducks. */
export function ArenaHubPage() {
  return (
    <section className="arena-hub" aria-labelledby="arena-hub-title">
      <GameHeader back={{ to: '/pond', label: 'Pond' }} />
      <h1 id="arena-hub-title">Arena</h1>
      <nav className="tiles" aria-label="Arena modes">
        <Link className="tile tile-super-bullet" to="/arena/super-bullet">
          <h2>Super Bullet Arena</h2>
          <p>
            Thirty seconds a game. Send your duck against a challenger in a best of 3, 5, 7 or 15.
          </p>
        </Link>
        <Link className="tile" to="/arena/custom">
          <h2>Custom match</h2>
          <p>Any two of your ducks, any time control, any number of games.</p>
        </Link>
      </nav>
    </section>
  )
}
