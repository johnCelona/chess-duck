import { useCallback, useEffect, useRef, useState } from 'react'
import { api, messageOf, unwrap, type Schemas } from '../api/client'

export type MinigameRun = Schemas['MinigameRunOut']
export type MinigameAction = Schemas['MinigameActionIn']['type']

const FRAME_MS = 900

/** One run of a minigame test: sends what the player did, and plays the server's frames. */
export function useMinigame(kind: string) {
  const [run, setRun] = useState<MinigameRun | null>(null)
  const [frame, setFrame] = useState(0)
  const [error, setError] = useState('')
  const busy = useRef(false)

  const send = useCallback(async (request: () => Promise<MinigameRun>) => {
    if (busy.current) return
    busy.current = true
    setError('')
    try {
      const next = await request()
      setFrame(0)
      setRun(next)
    } catch (reason) {
      setError(messageOf(reason))
      // A refused move has already moved on the board: draw the position again.
      setRun((current) => current && { ...current })
    } finally {
      busy.current = false
    }
  }, [])

  const start = useCallback(
    (seed?: number) =>
      send(() => unwrap(api.POST('/api/v1/minigame-runs', { body: { kind, seed } }))),
    [kind, send],
  )

  const runId = run?.id
  const act = useCallback(
    (type: MinigameAction, value = '') => {
      if (!runId) return
      void send(() =>
        unwrap(
          api.POST('/api/v1/minigame-runs/{run_id}/actions', {
            params: { path: { run_id: runId } },
            body: { type, value },
          }),
        ),
      )
    },
    [runId, send],
  )

  // Step through the animation; past the last frame the real board shows.
  const playing = !!run && frame < run.frames.length
  useEffect(() => {
    if (!playing) return
    const timer = setTimeout(() => setFrame((now) => now + 1), FRAME_MS)
    return () => clearTimeout(timer)
  }, [playing, frame, run])

  return {
    run,
    error,
    start,
    act,
    frame: playing ? run.frames[frame] : null,
    skip: () => setFrame(Number.MAX_SAFE_INTEGER),
  }
}

/** Counts down on screen; the server measures the real time and has the last word. */
export function useCountdown(run: MinigameRun | null, onZero: () => void): number | null {
  const [left, setLeft] = useState<number | null>(null)
  const zero = useRef(onZero)
  useEffect(() => {
    zero.current = onZero
  }, [onZero])

  useEffect(() => {
    const remaining = run?.remainingMs ?? null
    if (remaining === null) return
    const began = Date.now()
    const tick = () => {
      const now = run?.phase === 'play' ? Math.max(0, remaining - (Date.now() - began)) : remaining
      setLeft(now)
      if (now === 0 && run?.phase === 'play') zero.current()
    }
    const timer = setInterval(tick, 200)
    return () => clearInterval(timer)
  }, [run])

  return run?.remainingMs == null ? null : (left ?? run.remainingMs)
}
