import { Chessground } from '@lichess-org/chessground'
import type { Api } from '@lichess-org/chessground/api'
import type { Key } from '@lichess-org/chessground/types'
import { useEffect, useRef } from 'react'
import '@lichess-org/chessground/assets/chessground.base.css'
import '@lichess-org/chessground/assets/chessground.brown.css'
import '@lichess-org/chessground/assets/chessground.cburnett.css'

type Props = {
  fen: string
  lastMove?: [string, string] | null
  check?: boolean
  orientation?: 'white' | 'black'
}

/**
 * A view-only board. It shows whatever position the server sent; it never works out
 * moves itself. When a board becomes interactive (lessons, sparring) the legal
 * destinations will also come from the server.
 */
export function Board({ fen, lastMove = null, check = false, orientation = 'white' }: Props) {
  const element = useRef<HTMLDivElement>(null)
  const board = useRef<Api | null>(null)

  useEffect(() => {
    if (!element.current) return
    board.current = Chessground(element.current, { viewOnly: true, coordinates: true })
    return () => {
      board.current?.destroy()
      board.current = null
    }
  }, [])

  useEffect(() => {
    board.current?.set({
      fen,
      orientation,
      lastMove: lastMove ? (lastMove as Key[]) : undefined,
      check,
    })
  }, [fen, lastMove, check, orientation])

  return (
    <div className="board-frame">
      <div ref={element} className="board" data-testid="board" data-fen={fen} />
    </div>
  )
}
