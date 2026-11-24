// Placeholder skins a player can pick when hatching. Which skins exist (ids and labels)
// comes from assets/manifest.json, shared with every client; the colours below are
// stand-ins until real art replaces DuckSprite. Names and look are John's (design 03 §6).
import manifest from '../../../../assets/manifest.json'

type Palette = {
  body: string
  wing: string
  line: string
  beak: string
  eye: string
  /** Draw a fine grid over the body (graph paper, blueprint). */
  grid?: string
}

export type Skin = Palette & { id: string; label: string }

const PALETTES: Record<string, Palette> = {
  classic: {
    body: '#f6c945',
    wing: '#e9b52c',
    line: '#8a6414',
    beak: '#f08a24',
    eye: '#1f2430',
  },
  'graph-paper': {
    body: '#f8fafc',
    wing: '#e2e8f0',
    line: '#64748b',
    beak: '#f59e0b',
    eye: '#1f2430',
    grid: '#93c5fd',
  },
  blueprint: {
    body: '#1e4fa3',
    wing: '#1a4590',
    line: '#dbeafe',
    beak: '#dbeafe',
    eye: '#dbeafe',
    grid: '#3b6fc4',
  },
  terminal: {
    body: '#0f1410',
    wing: '#162016',
    line: '#4ade80',
    beak: '#4ade80',
    eye: '#4ade80',
  },
  chalkboard: {
    body: '#2f4a3a',
    wing: '#29412f',
    line: '#f1f5f9',
    beak: '#fde68a',
    eye: '#f1f5f9',
  },
}

/** Every skin in the manifest, in its order; one without a palette is drawn as classic. */
export const SKINS: readonly Skin[] = manifest.skins.map((skin) => ({
  ...(PALETTES[skin.id] ?? PALETTES.classic),
  id: skin.id,
  label: skin.label,
}))

export const DEFAULT_SKIN = SKINS[0]

export const hasPalette = (id: string) => id in PALETTES

export function skinFor(id: string | null | undefined): Skin {
  return SKINS.find((skin) => skin.id === id) ?? DEFAULT_SKIN
}
