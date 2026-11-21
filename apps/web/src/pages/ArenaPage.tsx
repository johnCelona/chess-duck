import { useParams } from 'react-router'
import { api, unwrap } from '../api/client'
import { useResource } from '../api/useResource'
import { GameHeader } from './GameHeader'
import { MatchPage } from './MatchPage'

const loadProfile = () => unwrap(api.GET('/api/v1/profile'))

/** Duck vs duck from the Pond: the match flow with the active duck preselected as White. */
export function ArenaPage() {
  const { matchId = null } = useParams()
  const { data: profile } = useResource(loadProfile)
  return (
    <div className="arena">
      <GameHeader back={{ to: '/pond', label: 'Pond' }} />
      <MatchPage
        matchId={matchId}
        basePath="/arena"
        title="Arena"
        initialWhiteId={profile?.activeDuckId ?? null}
      />
    </div>
  )
}
