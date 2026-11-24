// Placeholder egg drawn in code; like DuckSprite it is a single art slot to swap later.
// `cracks` (0 to 3) adds crack lines; `open` splits the shell so the duck can pop out.
// Animations are CSS in App.css (`.egg`), off for players who ask for reduced motion.

const CRACKS = ['M24 30l5 4l-3 5l6 3', 'M40 26l-4 6l5 3l-2 6', 'M18 40l8-2l3 5l7-3l5 4l9-3']

export function Egg({
  cracks,
  open = false,
  size = 160,
}: {
  cracks: number
  open?: boolean
  size?: number
}) {
  return (
    <svg
      className={`egg ${open ? 'egg-open' : ''}`}
      width={size}
      height={size * 1.2}
      viewBox="0 0 64 77"
      aria-hidden="true"
    >
      <g className="egg-bottom">
        <path d="M6 44q0 30 26 31q26-1 26-31z" fill="#fbf4e4" stroke="#b8a888" />
        <circle cx="20" cy="58" r="2.5" fill="#e8dcc0" />
        <circle cx="44" cy="62" r="2" fill="#e8dcc0" />
      </g>
      <g className="egg-top">
        <path
          d="M6 44q2-42 26-42t26 42l-8 3l-6-4l-6 4l-6-4l-6 4l-6-4l-6 4z"
          fill="#fbf4e4"
          stroke="#b8a888"
        />
        <circle cx="38" cy="20" r="3" fill="#e8dcc0" />
        <circle cx="22" cy="28" r="2" fill="#e8dcc0" />
      </g>
      {CRACKS.slice(0, Math.max(0, Math.min(cracks, CRACKS.length))).map((d) => (
        <path key={d} className="egg-crack" d={d} fill="none" stroke="#6b5a3a" strokeWidth="1.2" />
      ))}
    </svg>
  )
}
