import { useCallback, useEffect, useRef, useState } from 'react'
import { api, messageOf, unwrap, type EventOf, type Schemas } from '../api/client'
import { subscribe } from '../api/events'

export type SparringGame = Schemas['SparringGameOut']
export type Decision = EventOf<'MoveChosen'>['data']

/**
 * One game against a duck. The server holds the game: this hook fetches it, refetches
 * whenever its stream reports something (the duck's reply, the result), and sends moves.
 * It knows no chess: legal moves, the position and the clocks all come from the server.
 */
export function useSparringGame(gameId: string) {
  const [game, setGame] = useState<SparringGame | null>(null)
  const [fetchedAt, setFetchedAt] = useState(0)
  const [error, setError] = useState('')
  const [decisions, setDecisions] = useState<Map<number, Decision>>(new Map())
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const load = useCallback(async () => {
    try {
      const next = await unwrap(
        api.GET('/api/v1/sparring/{game_id}', { params: { path: { game_id: gameId } } }),
      )
      setGame(next)
      setFetchedAt(Date.now())
    } catch (requestError) {
      setError(messageOf(requestError))
    }
  }, [gameId])

  useEffect(() => {
    void load()
    const unsubscribe = subscribe([`sparring:${gameId}`], (event) => {
      // Decisions are kept for the "why" panel, shown once the game is over.
      if (event.type === 'MoveChosen') {
        const decision = event.data
        setDecisions((current) => new Map(current).set(decision.ply, decision))
      }
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => void load(), 50)
    })
    return () => {
      unsubscribe()
      if (timer.current) clearTimeout(timer.current)
    }
  }, [gameId, load])

  const act = useCallback(
    async (request: () => Promise<SparringGame>) => {
      setError('')
      try {
        setGame(await request())
        setFetchedAt(Date.now())
      } catch (requestError) {
        setError(messageOf(requestError))
        void load()
      }
    },
    [load],
  )
  const path = { params: { path: { game_id: gameId } } }
  const move = (uci: string) =>
    act(() => unwrap(api.POST('/api/v1/sparring/{game_id}/moves', { ...path, body: { uci } })))
  const resign = () => act(() => unwrap(api.PUT('/api/v1/sparring/{game_id}/resignation', path)))
  const claimTimeout = () =>
    act(() => unwrap(api.PUT('/api/v1/sparring/{game_id}/timeout-claim', path)))

  return { game, fetchedAt, error, decisions, move, resign, claimTimeout }
}
