import { useParams } from 'react-router'
import { api, unwrap } from '../api/client'
import { useResource } from '../api/useResource'
import { GameHeader } from './GameHeader'
import { MatchPage } from './MatchPage'

const loadProfile = () => unwrap(api.GET('/api/v1/profile'))

/** A custom match between any two ducks, with the active duck preselected as White. */
export function ArenaPage() {
  const { matchId = null } = useParams()
  const { data: profile } = useResource(loadProfile)
  return (
    <div className="arena">
      <GameHeader back={{ to: '/arena', label: 'Arena' }} />
      <MatchPage
        matchId={matchId}
        basePath="/arena/custom"
        title="Custom match"
        initialWhiteId={profile?.activeDuckId ?? null}
      />
    </div>
  )
}
