import { useEffect, useState } from 'react'
import './App.css'
import { DucksPage } from './pages/DucksPage'
import { EnginesPage } from './pages/EnginesPage'
import { MatchPage } from './pages/MatchPage'

const PAGES = [
  { id: 'ducks', label: 'Ducks' },
  { id: 'match', label: 'Match' },
  { id: 'engines', label: 'Engines' },
] as const

type PageId = (typeof PAGES)[number]['id']
type Route = { page: PageId; param: string | null }

/** `#/match/mat_123` is the match page watching (or replaying) that match. */
function routeFromHash(): Route {
  const [id, param] = window.location.hash.replace(/^#\/?/, '').split('/')
  const page = PAGES.some((candidate) => candidate.id === id) ? (id as PageId) : 'ducks'
  return { page, param: param || null }
}

// Three pages do not need a router yet. The hash keeps the page across reloads;
// replace this with a real router when navigation grows (see docs/sessions).
function App() {
  const [route, setRoute] = useState<Route>(routeFromHash)

  useEffect(() => {
    const onHashChange = () => setRoute(routeFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  return (
    <div className="app-shell">
      <header className="app-header">
        <p className="brand">Duck Gambit</p>
        <nav aria-label="Main">
          {PAGES.map((item) => (
            <a
              key={item.id}
              href={`#/${item.id}`}
              aria-current={item.id === route.page ? 'page' : undefined}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </header>
      <main>
        {route.page === 'ducks' && <DucksPage />}
        {route.page === 'match' && <MatchPage matchId={route.param} />}
        {route.page === 'engines' && <EnginesPage />}
      </main>
    </div>
  )
}

export default App
