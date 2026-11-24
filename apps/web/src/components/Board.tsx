import { Chessground } from '@lichess-org/chessground'
import type { Api } from '@lichess-org/chessground/api'
import type { Key } from '@lichess-org/chessground/types'
import { useEffect, useRef } from 'react'
import { destinationsFrom } from './boardMoves'
import '@lichess-org/chessground/assets/chessground.base.css'
import '@lichess-org/chessground/assets/chessground.brown.css'
import '@lichess-org/chessground/assets/chessground.cburnett.css'

type Props = {
  fen: string
  lastMove?: [string, string] | null
  check?: boolean
  orientation?: 'white' | 'black'
  /** Make the board playable: the server's legal moves for the side to move (UCI). */
  legalMoves?: string[]
  movableColor?: 'white' | 'black'
  /** Called with every legal UCI move from the dragged square to the dropped square:
   * one move normally, four for a promotion (the caller picks the piece). */
  onMove?: (candidates: string[]) => void
  /** Squares to highlight, by kind (`.mark-*` in App.css). */
  marks?: { square: string; kind: string }[]
  arrows?: { origin: string; target: string; kind: 'good' | 'bad' | 'info' }[]
  /** A new value redraws the position: a move the server refused snaps back. */
  resetKey?: unknown
}

const BRUSHES = { good: 'green', bad: 'red', info: 'blue' }

/**
 * Shows whatever position the server sent. When `legalMoves` and `onMove` are given, the
 * player can drag those moves (and only those); the server still judges every move.
 */
export function Board({
  fen,
  lastMove = null,
  check = false,
  orientation = 'white',
  legalMoves,
  movableColor,
  onMove,
  marks,
  arrows,
  resetKey,
}: Props) {
  const element = useRef<HTMLDivElement>(null)
  const board = useRef<Api | null>(null)
  const latest = useRef({ legalMoves, onMove })

  useEffect(() => {
    latest.current = { legalMoves, onMove }
  }, [legalMoves, onMove])

  // Chessground attaches its input listeners only when a board is created, so a board
  // that can ever be played is created interactive; `legalMoves` decides what may move.
  const interactive = !!onMove
  useEffect(() => {
    if (!element.current) return
    board.current = Chessground(element.current, {
      viewOnly: !interactive,
      coordinates: true,
      movable: { free: false, color: undefined },
      draggable: { enabled: interactive },
      selectable: { enabled: interactive },
    })
    return () => {
      board.current?.destroy()
      board.current = null
    }
  }, [interactive])

  const playable = interactive && !!legalMoves && legalMoves.length > 0
  useEffect(() => {
    board.current?.set({
      fen,
      orientation,
      lastMove: lastMove ? (lastMove as Key[]) : undefined,
      // The FEN says whose turn it is, so whose king is in check.
      check: check && (fen.split(' ')[1] === 'b' ? 'black' : 'white'),
      turnColor: movableColor,
      movable: {
        free: false,
        color: playable ? movableColor : undefined,
        dests: playable ? destinationsFrom(legalMoves ?? []) : new Map(),
        showDests: true,
        events: {
          after: (from, to) => {
            const candidates = (latest.current.legalMoves ?? []).filter((uci) =>
              uci.startsWith(`${from}${to}`),
            )
            if (candidates.length > 0) latest.current.onMove?.(candidates)
          },
        },
      },
    })
  }, [fen, lastMove, check, orientation, playable, legalMoves, movableColor, interactive, resetKey])

  useEffect(() => {
    const classes = new Map<Key, string>()
    for (const { square, kind } of marks ?? []) {
      const key = square as Key
      classes.set(key, `${classes.get(key) ?? ''} mark-${kind}`.trim())
    }
    board.current?.set({
      highlight: { custom: classes },
      drawable: {
        autoShapes: (arrows ?? []).map(({ origin, target, kind }) => ({
          orig: origin as Key,
          dest: target as Key,
          brush: BRUSHES[kind],
        })),
      },
    })
  }, [marks, arrows, interactive])

  return (
    <div className="board-frame">
      <div ref={element} className="board" data-testid="board" data-fen={fen} />
    </div>
  )
}
