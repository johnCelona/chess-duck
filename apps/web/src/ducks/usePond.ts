import { useCallback, useEffect, useRef } from 'react'
import { api, unwrap, type Duck } from '../api/client'
import { subscribe } from '../api/events'
import { useResource } from '../api/useResource'

async function loadPond() {
  const [profile, ducks] = await Promise.all([
    unwrap(api.GET('/api/v1/profile')),
    unwrap(api.GET('/api/v1/ducks')),
  ])
  return { profile, ducks }
}

export type Pond = {
  ducks: Duck[]
  active: Duck | null
  loading: boolean
  error: string
  setActive: (duckId: string) => Promise<void>
}

/**
 * The player's ducks and the active one (saved on the server, so it survives reloads and
 * is shared with any other client). Refetches when the active duck's event stream reports
 * a change, so anything that changes the duck (a rated game, later a minigame) shows up.
 */
export function usePond(): Pond {
  const { data, error, reload } = useResource(loadPond)
  const ducks = data?.ducks ?? []
  const active = ducks.find((duck) => duck.id === data?.profile.activeDuckId) ?? null

  // Coalesce bursts of events (a replayed stream, a finished match) into one refetch.
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reloadSoon = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(reload, 250)
  }, [reload])

  const stream = active?.stream
  useEffect(() => {
    if (!stream) return
    const unsubscribe = subscribe([stream], reloadSoon)
    return () => {
      unsubscribe()
      if (timer.current) clearTimeout(timer.current)
    }
  }, [stream, reloadSoon])

  const setActive = useCallback(
    async (duckId: string) => {
      await unwrap(api.PUT('/api/v1/profile/active-duck', { body: { duckId } }))
      reload()
    },
    [reload],
  )

  return { ducks, active, loading: data === null && !error, error, setActive }
}
