// Placeholder avatar drawn in code so no art asset is needed yet. John owns the real
// art (ADR-0013); swap this component for assets resolved through assets/manifest.json.

function hueFor(seed: string): number {
  let hash = 0
  for (const char of seed) hash = (hash * 31 + char.charCodeAt(0)) % 360
  return hash
}

export function DuckAvatar({ name, size = 56 }: { name: string; size?: number }) {
  const hue = hueFor(name)
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label={`${name}'s placeholder avatar`}
    >
      <circle cx="32" cy="32" r="30" fill={`hsl(${hue} 70% 90%)`} />
      <ellipse cx="30" cy="42" rx="18" ry="12" fill={`hsl(${hue} 65% 55%)`} />
      <circle cx="40" cy="24" r="10" fill={`hsl(${hue} 65% 55%)`} />
      <polygon points="48,24 60,27 48,30" fill="#f59e0b" />
      <circle cx="43" cy="21" r="1.8" fill="#172033" />
    </svg>
  )
}
