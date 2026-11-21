import { Link, useNavigate } from 'react-router'
import { api, unwrap } from '../api/client'
import { useResource } from '../api/useResource'
import { DuckSprite } from '../components/DuckSprite'

const loadProfile = () => unwrap(api.GET('/api/v1/profile'))

/**
 * Play goes to the active duck, or straight to the egg on a first launch.
 * "Hatch a new egg" always adds a duck; nothing is ever replaced (design 03 §1).
 */
export function TitlePage() {
  const { data: profile, error } = useResource(loadProfile)
  const navigate = useNavigate()

  return (
    <section className="title-screen" aria-labelledby="title">
      {/* Slot for the logo animation (John's). */}
      <div className="title-art">
        <DuckSprite pose="idle" size={140} />
      </div>
      <h1 id="title" className="logo">
        Duck Gambit
      </h1>
      <p className="tagline">Raise a duck. Teach it chess. Get better together.</p>
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}
      <div className="title-actions">
        <button
          type="button"
          className="primary big"
          disabled={!profile}
          onClick={() => navigate(profile?.activeDuckId ? '/pond' : '/hatch')}
        >
          Play
        </button>
        <Link className="button big" to="/hatch">
          Hatch a new egg
        </Link>
      </div>
      <Link to="/lab" className="gear title-gear">
        ⚙ Lab
      </Link>
    </section>
  )
}
