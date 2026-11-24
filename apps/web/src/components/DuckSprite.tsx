// THE art slot for ducks: every screen draws a duck through this component and nothing
// else. It is a placeholder drawn in code; swapping in the real duck (John's artist, or a
// Unity build) means changing this file and assets/manifest.json only (design 03 §6).
// Poses are CSS animations in App.css (`.duck-sprite.pose-*`) and stop for players who
// ask for reduced motion.
import { skinFor } from '../ducks/skins'

export type DuckPose = 'idle' | 'emerge' | 'celebrate' | 'still'

export function DuckSprite({
  skin,
  pose = 'still',
  size = 56,
  label,
}: {
  skin?: string | null
  pose?: DuckPose
  size?: number
  /** Accessible name; omit for a decorative sprite next to a visible name. */
  label?: string
}) {
  const colors = skinFor(skin)
  const gridId = `duck-grid-${colors.id}`
  return (
    <svg
      className={`duck-sprite pose-${pose}`}
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      data-skin={colors.id}
    >
      {colors.grid && (
        <defs>
          <pattern id={gridId} width="4" height="4" patternUnits="userSpaceOnUse">
            <path d="M4 0H0V4" fill="none" stroke={colors.grid} strokeWidth="0.5" />
          </pattern>
        </defs>
      )}
      <g className="duck-body">
        <ellipse cx="30" cy="44" rx="20" ry="13" fill={colors.body} stroke={colors.line} />
        {colors.grid && <ellipse cx="30" cy="44" rx="20" ry="13" fill={`url(#${gridId})`} />}
        <path d="M18 42q10 10 22 0q-8 4-22 0z" fill={colors.wing} stroke={colors.line} />
        <circle cx="40" cy="24" r="11" fill={colors.body} stroke={colors.line} />
        {colors.grid && <circle cx="40" cy="24" r="11" fill={`url(#${gridId})`} />}
        <path d="M50 23l11 3l-11 4z" fill={colors.beak} stroke={colors.line} strokeWidth="0.75" />
        <circle cx="43" cy="21" r="2" fill={colors.eye} />
      </g>
    </svg>
  )
}
