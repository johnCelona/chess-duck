import { Link, NavLink, Outlet, useParams } from 'react-router'
import { MatchPage } from './MatchPage'

const LAB_PAGES = [
  { to: '/lab/ducks', label: 'Ducks' },
  { to: '/lab/match', label: 'Match' },
  { to: '/lab/engines', label: 'Engines' },
] as const

/** The Lab: the developer screens (ducks, any match, engines), reachable from the gear. */
export function LabLayout() {
  return (
    <div className="lab">
      <header className="app-header">
        <p className="brand">
          <Link to="/">Duck Gambit</Link> · Lab
        </p>
        <nav aria-label="Lab">
          {LAB_PAGES.map((item) => (
            <NavLink key={item.to} to={item.to}>
              {item.label}
            </NavLink>
          ))}
          <Link to="/pond">Pond</Link>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  )
}

export function LabMatchPage() {
  const { matchId = null } = useParams()
  return <MatchPage matchId={matchId} basePath="/lab/match" />
}
