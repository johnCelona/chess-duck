import { useEffect, useRef } from 'react'
import type { MoveRow } from './playback'

/** A move as the list needs it; `source` (book, memory...) is marked, a human's has none. */
export type ListedMove = Pick<MoveRow, 'ply' | 'color' | 'san'> & { source?: string | null }

type Props = {
  moves: ListedMove[]
  /** The ply on screen (0 is the start position). */
  selectedPly: number
  onSelect: (ply: number) => void
}

/** The game's moves; click one to jump to it. The list scrolls itself, never the page. */
export function MoveList({ moves, selectedPly, onSelect }: Props) {
  const list = useRef<HTMLOListElement>(null)

  useEffect(() => {
    const container = list.current
    const item = container?.querySelector<HTMLElement>('[aria-current="true"]')
    if (!container || !item) return
    // Adjust only the list's own scroll position (scrollIntoView could scroll the page).
    const top = item.offsetTop
    const bottom = top + item.offsetHeight
    if (top < container.scrollTop) container.scrollTop = top
    else if (bottom > container.scrollTop + container.clientHeight)
      container.scrollTop = bottom - container.clientHeight
  }, [selectedPly, moves.length])

  return (
    <ol className="moves" ref={list}>
      {moves.map((move) => (
        <li key={move.ply} className={move.color}>
          {move.color === 'white' && <span className="number">{(move.ply + 1) / 2}.</span>}
          <button
            type="button"
            className="move"
            aria-current={move.ply === selectedPly ? 'true' : undefined}
            title={!move.source || move.source === 'engine' ? undefined : `from ${move.source}`}
            onClick={() => onSelect(move.ply)}
          >
            {move.san}
            {move.source && move.source !== 'engine' && <sup>{move.source[0]}</sup>}
          </button>
        </li>
      ))}
    </ol>
  )
}
