import { useCallback, useEffect, useRef, useState } from 'react'
import { api, unwrap, type Duck, type EventEnvelope } from '../api/client'
import { latestCursor, subscribe } from '../api/events'
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
  /** Short news about the active duck from events that just happened ("+25 XP"). */
  news: string[]
  dismissNews: () => void
}

/** Placeholder copy for XP and level-up news (John's to change). */
export function newsFor(event: EventEnvelope): string | null {
  if (event.type === 'XpGained') return `+${event.data.amount} XP`
  if (event.type === 'DuckLeveledUp') {
    return event.data.stageAdvanced
      ? `Level ${event.data.level}! Now a ${event.data.stage}.`
      : `Level ${event.data.level}!`
  }
  return null
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

  const [news, setNews] = useState<string[]>([])
  const stream = active?.stream
  useEffect(() => {
    if (!stream) return
    let unsubscribe: (() => void) | null = null
    let cancelled = false
    // Only what happens from now on: past events are already in the data we loaded.
    latestCursor([stream])
      .catch(() => 0)
      .then((after) => {
        if (cancelled) return
        unsubscribe = subscribe(
          [stream],
          (event) => {
            const item = newsFor(event)
            if (item) setNews((current) => [...current, item])
            reloadSoon()
          },
          { after },
        )
      })
    return () => {
      cancelled = true
      unsubscribe?.()
      if (timer.current) clearTimeout(timer.current)
      setNews([])
    }
  }, [stream, reloadSoon])

  const setActive = useCallback(
    async (duckId: string) => {
      await unwrap(api.PUT('/api/v1/profile/active-duck', { body: { duckId } }))
      reload()
    },
    [reload],
  )

  const dismissNews = useCallback(() => setNews([]), [])
  return { ducks, active, loading: data === null && !error, error, setActive, news, dismissNews }
}
