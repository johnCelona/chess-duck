import { useCallback, useEffect, useState } from 'react'
import { messageOf } from './client'

type Resource<T> = {
  data: T | null
  error: string
  /** Fetch again, keeping the current data on screen until the new data arrives. */
  reload: () => void
}

/**
 * Loads data when the component mounts and whenever `reload` is called.
 * `load` must be a stable function (define it at module level).
 */
export function useResource<T>(load: () => Promise<T>): Resource<T> {
  const [state, setState] = useState<{ data: T | null; error: string }>({ data: null, error: '' })
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let cancelled = false
    load().then(
      (data) => {
        if (!cancelled) setState({ data, error: '' })
      },
      (error: unknown) => {
        if (!cancelled) setState((current) => ({ ...current, error: messageOf(error) }))
      },
    )
    return () => {
      cancelled = true
    }
  }, [load, version])

  const reload = useCallback(() => setVersion((current) => current + 1), [])
  return { ...state, reload }
}
