import { Link } from 'react-router'
import { APP_NAME } from '../brand'

/** The thin bar above game screens: the title link, an optional way back, and the Lab gear. */
export function GameHeader({ back }: { back?: { to: string; label: string } }) {
  return (
    <header className="game-header">
      <Link to="/" className="brand">
        {APP_NAME}
      </Link>
      {back && (
        <Link to={back.to} className="back">
          ← {back.label}
        </Link>
      )}
      <Link to="/minigame-tests" className="gear">
        Minigame tests
      </Link>
      <Link to="/lab" className="gear" aria-label="Lab: ducks, matches and engines" title="Lab">
        ⚙
      </Link>
    </header>
  )
}
