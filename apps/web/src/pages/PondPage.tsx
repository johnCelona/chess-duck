import { useState } from 'react'
import { Link, Navigate } from 'react-router'
import { messageOf } from '../api/client'
import { usePond } from '../ducks/usePond'
import { AttributesBar } from '../pond/AttributesBar'
import { DuckSwitcher } from '../pond/DuckSwitcher'
import { TILES } from '../pond/tiles'
import { GameHeader } from './GameHeader'

/** The hub: the active duck's attributes, the duck switcher and four tiles (design 03 §2). */
export function PondPage() {
  const pond = usePond()
  const [actionError, setActionError] = useState('')
  const error = actionError || pond.error

  if (pond.loading) return <p role="status">Loading your pond…</p>
  if (!error && pond.ducks.length === 0) return <Navigate to="/hatch" replace />

  const choose = (duckId: string) => {
    setActionError('')
    pond.setActive(duckId).catch((reason: unknown) => setActionError(messageOf(reason)))
  }

  return (
    <div className="pond">
      <GameHeader />
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}
      {pond.news.length > 0 && (
        <div className="news" role="status">
          {pond.news.map((item, index) => (
            <span key={index}>{item}</span>
          ))}
          <button type="button" aria-label="Dismiss" onClick={pond.dismissNews}>
            ×
          </button>
        </div>
      )}
      {pond.active && (
        <AttributesBar
          duck={pond.active}
          switcher={<DuckSwitcher ducks={pond.ducks} active={pond.active} onChoose={choose} />}
        />
      )}
      <nav className="tiles" aria-label="Activities">
        {TILES.map((tile) => (
          <Link key={tile.id} className={`tile tile-${tile.id}`} to={tile.to}>
            <h2>{tile.title}</h2>
            <p>{tile.blurb}</p>
            {tile.soon && <span className="tile-soon">Coming soon</span>}
          </Link>
        ))}
      </nav>
    </div>
  )
}
