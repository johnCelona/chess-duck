import type { ReactNode } from 'react'
import type { Duck } from '../api/client'
import { DuckSprite } from '../components/DuckSprite'
import { ratingLabel } from '../ducks/format'

const STATS = [
  ['calculation', 'Calculation'],
  ['memory', 'Memory'],
  ['aggression', 'Aggression'],
  ['solidity', 'Solidity'],
  ['creativity', 'Creativity'],
  ['speed', 'Speed'],
] as const

/**
 * The duck's attributes, straight from the API (design 03 §2.1). Nothing is computed
 * here except display arithmetic: the XP bar's fill and the stat points in use.
 */
export function AttributesBar({ duck, switcher }: { duck: Duck; switcher: ReactNode }) {
  const { growth, rating } = duck
  const used = Object.values(duck.stats).reduce((sum, value) => sum + value, 0)
  return (
    <section className="attributes" aria-label={`${duck.name}'s attributes`}>
      <DuckSprite skin={duck.avatar.skin} pose="idle" size={72} />
      <div className="attributes-main">
        {switcher}
        <p className="growth">
          Level {growth.level} <span className="stage">{growth.stage}</span>
        </p>
        <XpBar xp={growth.xp} next={growth.xpForNextLevel} />
      </div>
      <dl className="rating">
        <dt>Rating</dt>
        <dd>
          {ratingLabel(duck)}
          {rating.provisional && (
            <small title="Not enough rated games yet to be sure">Provisional</small>
          )}
        </dd>
        <dd className="rating-games">
          {rating.games} rated {rating.games === 1 ? 'game' : 'games'}
        </dd>
      </dl>
      <dl className="stat-list">
        {STATS.map(([key, label]) => (
          <div key={key}>
            <dt>{label}</dt>
            <dd>{duck.stats[key]}</dd>
          </div>
        ))}
        <div>
          <dt>Stat points</dt>
          <dd>
            {used} / {growth.statBudget}
          </dd>
        </div>
      </dl>
    </section>
  )
}

function XpBar({ xp, next }: { xp: number; next: number | null }) {
  if (next === null) return <p className="xp-label">{xp} XP · top level</p>
  return (
    <div className="xp">
      <progress max={next} value={Math.min(xp, next)} aria-label="Experience" />
      <span className="xp-label">
        {xp} / {next} XP
      </span>
    </div>
  )
}
