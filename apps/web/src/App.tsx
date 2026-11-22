import { HashRouter, Navigate, Route, Routes, useParams } from 'react-router'
import './App.css'
import { ArenaHubPage } from './pages/ArenaHubPage'
import { ArenaPage } from './pages/ArenaPage'
import { ComingSoonPage } from './pages/ComingSoonPage'
import { DucksPage } from './pages/DucksPage'
import { EnginesPage } from './pages/EnginesPage'
import { HatchPage } from './pages/HatchPage'
import { LabLayout, LabMatchPage } from './pages/LabLayout'
import { NotFoundPage } from './pages/NotFoundPage'
import { PondPage } from './pages/PondPage'
import { SuperBulletPage } from './pages/SuperBulletPage'
import { TitlePage } from './pages/TitlePage'

/** Custom matches moved under /arena/custom; older links keep working. */
function OldArenaLink() {
  const { matchId } = useParams()
  return <Navigate to={`/arena/custom/${matchId}`} replace />
}

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
      <Route path="/arena" element={<ArenaHubPage />} />
      <Route path="/arena/super-bullet/:matchId?" element={<SuperBulletPage />} />
      <Route path="/arena/custom/:matchId?" element={<ArenaPage />} />
      <Route path="/arena/:matchId" element={<OldArenaLink />} />
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
