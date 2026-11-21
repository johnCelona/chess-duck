import { Link } from 'react-router'

/** The thin bar above game screens: the title link, an optional way back, and the Lab gear. */
export function GameHeader({ back }: { back?: { to: string; label: string } }) {
  return (
    <header className="game-header">
      <Link to="/" className="brand">
        Duck Gambit
      </Link>
      {back && (
        <Link to={back.to} className="back">
          ← {back.label}
        </Link>
      )}
      <Link to="/lab" className="gear" aria-label="Lab: ducks, matches and engines" title="Lab">
        ⚙
      </Link>
    </header>
  )
}
