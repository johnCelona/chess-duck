import { HashRouter, Navigate, Route, Routes, useParams } from 'react-router'
import './App.css'
import { ArenaPage } from './pages/ArenaPage'
import { ComingSoonPage } from './pages/ComingSoonPage'
import { DucksPage } from './pages/DucksPage'
import { EnginesPage } from './pages/EnginesPage'
import { HatchPage } from './pages/HatchPage'
import { LabLayout, LabMatchPage } from './pages/LabLayout'
import { NotFoundPage } from './pages/NotFoundPage'
import { PondPage } from './pages/PondPage'
import { TitlePage } from './pages/TitlePage'

/** Links from before the Lab existed (`#/match/mat_1`) keep working. */
function OldMatchLink() {
  const { matchId } = useParams()
  return <Navigate to={matchId ? `/lab/match/${matchId}` : '/lab/match'} replace />
}

/**
 * The player's journey (design 03): title → egg → Pond, with the Arena and the
 * placeholder tiles. The Lab keeps the developer screens. Hash routing keeps every
 * address working when the app is served as static files.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<TitlePage />} />
      <Route path="/hatch" element={<HatchPage />} />
      <Route path="/pond" element={<PondPage />} />
      <Route path="/pond/:tile" element={<ComingSoonPage />} />
      <Route path="/arena/:matchId?" element={<ArenaPage />} />
      <Route path="/lab" element={<LabLayout />}>
        <Route index element={<Navigate to="ducks" replace />} />
        <Route path="ducks" element={<DucksPage />} />
        <Route path="match/:matchId?" element={<LabMatchPage />} />
        <Route path="engines" element={<EnginesPage />} />
      </Route>
      <Route path="/ducks" element={<Navigate to="/lab/ducks" replace />} />
      <Route path="/match/:matchId?" element={<OldMatchLink />} />
      <Route path="/engines" element={<Navigate to="/lab/engines" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

function App() {
  return (
    <HashRouter>
      <div className="app-shell">
        <AppRoutes />
      </div>
    </HashRouter>
  )
}

export default App
