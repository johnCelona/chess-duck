import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { api, messageOf, unwrap } from '../api/client'
import { DuckSprite } from '../components/DuckSprite'
import { Egg } from '../components/Egg'
import { SKINS, DEFAULT_SKIN } from '../ducks/skins'
import { GameHeader } from './GameHeader'

export const TAPS_TO_HATCH = 3
/** How long the shell takes to split before the duck appears (matches App.css). */
export const HATCH_MS = 700
const EGG_KEY = 'duck-gambit.egg-seed'

/**
 * A new egg's seed: 53 random bits, exact in JSON. Kept for this tab so a reload
 * mid-hatch keeps the same egg; the server derives the starting stats from it.
 */
function eggSeed(): number {
  try {
    const kept = sessionStorage.getItem(EGG_KEY)
    if (kept !== null && /^\d+$/.test(kept)) return Number(kept)
  } catch {
    // Storage can be unavailable (private windows); a fresh egg is fine.
  }
  const [high, low] = crypto.getRandomValues(new Uint32Array(2))
  const seed = (high >>> 11) * 2 ** 32 + low
  try {
    sessionStorage.setItem(EGG_KEY, String(seed))
  } catch {
    // See above.
  }
  return seed
}

function forgetEgg() {
  try {
    sessionStorage.removeItem(EGG_KEY)
  } catch {
    // See eggSeed.
  }
}

function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

type Step = 'egg' | 'hatching' | 'hatched'

/** Egg → crack → the duck pops out → name it (design 03 §1). Never replaces a duck. */
export function HatchPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState<Step>('egg')
  const [taps, setTaps] = useState(0)
  const [seed, setSeed] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [skin, setSkin] = useState(DEFAULT_SKIN.id)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  // Kept so a retry after a failed second step never hatches a second duck.
  const [hatchedId, setHatchedId] = useState<string | null>(null)

  useEffect(() => {
    if (step !== 'hatching') return
    const timer = setTimeout(() => setStep('hatched'), prefersReducedMotion() ? 0 : HATCH_MS)
    return () => clearTimeout(timer)
  }, [step])

  const tap = () => {
    if (seed === null) setSeed(eggSeed())
    const next = taps + 1
    setTaps(next)
    if (next >= TAPS_TO_HATCH) setStep('hatching')
  }

  const welcome = async (event: FormEvent) => {
    event.preventDefault()
    if (seed === null) return
    setBusy(true)
    setError('')
    try {
      let duckId = hatchedId
      if (duckId === null) {
        const duck = await unwrap(
          api.POST('/api/v1/ducks', { body: { name, eggSeed: seed, avatar: { skin } } }),
        )
        duckId = duck.id
        setHatchedId(duckId)
      }
      await unwrap(api.PUT('/api/v1/profile/active-duck', { body: { duckId } }))
      forgetEgg()
      navigate('/pond')
    } catch (requestError) {
      setError(messageOf(requestError))
      setBusy(false)
    }
  }

  return (
    <section className="hatch" aria-labelledby="hatch-title">
      <GameHeader back={{ to: '/', label: 'Title' }} />
      <StorySlot />
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}

      {step !== 'hatched' ? (
        <>
          <h1 id="hatch-title">{step === 'egg' ? 'An egg!' : 'It’s hatching!'}</h1>
          <button
            type="button"
            className="egg-button"
            onClick={tap}
            disabled={step !== 'egg'}
            aria-label={`Tap the egg (${taps} of ${TAPS_TO_HATCH})`}
          >
            {/* The key restarts the wobble on every tap. */}
            <span key={taps} className={taps > 0 ? 'wobble' : ''}>
              <Egg cracks={taps} open={step === 'hatching'} />
            </span>
          </button>
          <p className="hint" aria-live="polite">
            {taps === 0
              ? 'Tap or click the egg.'
              : step === 'egg'
                ? 'Keep tapping…'
                : 'Here it comes!'}
          </p>
        </>
      ) : (
        <>
          <h1 id="hatch-title">Your duck hatched!</h1>
          <div className="reveal">
            <DuckSprite skin={skin} pose="emerge" size={160} label="Your new duck" />
          </div>
          <form className="panel name-form" onSubmit={welcome}>
            <label>
              Name your duck
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Sir Quackalot"
                maxLength={40}
                autoFocus
                required
              />
            </label>
            <fieldset className="skins">
              <legend>Color</legend>
              {SKINS.map((option) => (
                <label key={option.id} className={option.id === skin ? 'skin selected' : 'skin'}>
                  <input
                    type="radio"
                    name="skin"
                    value={option.id}
                    checked={option.id === skin}
                    onChange={() => setSkin(option.id)}
                  />
                  <DuckSprite skin={option.id} size={36} />
                  {option.label}
                </label>
              ))}
            </fieldset>
            <button className="primary" type="submit" disabled={busy || !name.trim()}>
              Welcome to the pond
            </button>
          </form>
        </>
      )}
    </section>
  )
}

/** Slot for the 3 to 5 skippable story panels (later; design 03 §1). Renders nothing yet. */
function StorySlot() {
  return null
}
