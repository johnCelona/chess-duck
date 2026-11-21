import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import type { Duck } from '../api/client'
import { DuckSprite } from '../components/DuckSprite'

/** The active duck's name as a menu: every duck, then "+ Hatch a new egg" (design 03 §2.2). */
export function DuckSwitcher({
  ducks,
  active,
  onChoose,
}: {
  ducks: Duck[]
  active: Duck
  onChoose: (duckId: string) => void
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!open) return
    const close = (event: Event) => {
      if (event instanceof KeyboardEvent && event.key !== 'Escape') return
      if (event instanceof MouseEvent && root.current?.contains(event.target as Node)) return
      setOpen(false)
    }
    document.addEventListener('keydown', close)
    document.addEventListener('mousedown', close)
    return () => {
      document.removeEventListener('keydown', close)
      document.removeEventListener('mousedown', close)
    }
  }, [open])

  return (
    <div className="switcher" ref={root}>
      <button
        type="button"
        className="switcher-button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`${active.name}, switch duck`}
        onClick={() => setOpen((value) => !value)}
      >
        <h1>{active.name}</h1>
        <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <ul className="switcher-menu" role="menu" aria-label="Your ducks">
          {ducks.map((duck) => (
            <li key={duck.id} role="none">
              <button
                type="button"
                role="menuitemradio"
                aria-checked={duck.id === active.id}
                onClick={() => {
                  setOpen(false)
                  if (duck.id !== active.id) onChoose(duck.id)
                }}
              >
                <DuckSprite skin={duck.avatar.skin} size={28} />
                <span className="switcher-name">{duck.name}</span>
                <span className="switcher-level">Lv {duck.growth.level}</span>
              </button>
            </li>
          ))}
          <li role="none">
            <button type="button" role="menuitem" onClick={() => navigate('/hatch')}>
              + Hatch a new egg
            </button>
          </li>
        </ul>
      )}
    </div>
  )
}
