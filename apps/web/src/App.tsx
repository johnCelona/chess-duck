import { useEffect, useState } from 'react'
import './App.css'
import { DucksPage } from './pages/DucksPage'
import { EnginesPage } from './pages/EnginesPage'
import { MatchPage } from './pages/MatchPage'

const PAGES = [
  { id: 'ducks', label: 'Ducks', render: () => <DucksPage /> },
  { id: 'match', label: 'Match', render: () => <MatchPage /> },
  { id: 'engines', label: 'Engines', render: () => <EnginesPage /> },
] as const

type PageId = (typeof PAGES)[number]['id']

function pageFromHash(): PageId {
  const id = window.location.hash.replace('#/', '')
  return PAGES.some((page) => page.id === id) ? (id as PageId) : 'ducks'
}

// Three pages do not need a router yet. The hash keeps the page across reloads;
// replace this with a real router when navigation grows (see docs/sessions).
function App() {
  const [pageId, setPageId] = useState<PageId>(pageFromHash)

  useEffect(() => {
    const onHashChange = () => setPageId(pageFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const page = PAGES.find((candidate) => candidate.id === pageId) ?? PAGES[0]

  return (
    <div className="app-shell">
      <header className="app-header">
        <p className="brand">Duck Gambit</p>
        <nav aria-label="Main">
          {PAGES.map((item) => (
            <a
              key={item.id}
              href={`#/${item.id}`}
              aria-current={item.id === pageId ? 'page' : undefined}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </header>
      <main>{page.render()}</main>
    </div>
  )
}

export default App
