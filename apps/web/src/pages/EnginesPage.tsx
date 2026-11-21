import { useEffect, useState } from 'react'
import { api, messageOf, unwrap, type Analysis, type EngineProfile } from '../api/client'
import { useResource } from '../api/useResource'
import { formatScore } from '../match/playback'

const DEFAULTS = { nodes: 100000, multiPV: 3, hashMb: 16 }
const loadEngines = () => unwrap(api.GET('/api/v1/engines'))

export function EnginesPage() {
  const { data: engines, error: loadError, reload } = useResource(loadEngines)
  const [chosenId, setSelectedId] = useState<string | null>(null)
  const selectedId = chosenId ?? engines?.[0]?.id ?? null
  const [settings, setSettings] = useState(DEFAULTS)
  const [profiles, setProfiles] = useState<EngineProfile[]>([])
  const [profileName, setProfileName] = useState('')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [actionError, setError] = useState('')
  const error = actionError || loadError

  const selected = engines?.find((engine) => engine.id === selectedId) ?? null
  const installed = selected?.status === 'installed'

  useEffect(() => {
    if (!selectedId || !installed) return
    let cancelled = false
    unwrap(
      api.GET('/api/v1/engines/{engine_id}/profiles', {
        params: { path: { engine_id: selectedId } },
      }),
    )
      .then((list) => {
        if (!cancelled) setProfiles(list)
      })
      .catch(() => {
        if (!cancelled) setProfiles([])
      })
    return () => {
      cancelled = true
    }
  }, [selectedId, installed])

  const act = async (label: string, action: () => Promise<void>) => {
    setBusy(label)
    setError('')
    try {
      await action()
    } catch (requestError) {
      setError(messageOf(requestError))
    } finally {
      setBusy(null)
    }
  }

  const path = { engine_id: selectedId ?? '' }

  const install = () =>
    act('Downloading and verifying…', async () => {
      await unwrap(api.PUT('/api/v1/engines/{engine_id}/installation', { params: { path } }))
      reload()
    })

  const remove = () =>
    act('Removing…', async () => {
      await unwrap(api.DELETE('/api/v1/engines/{engine_id}/installation', { params: { path } }))
      setAnalysis(null)
      reload()
    })

  const test = () =>
    act('Searching…', async () => {
      setAnalysis(null)
      setAnalysis(
        await unwrap(
          api.POST('/api/v1/engines/{engine_id}/analyses', { params: { path }, body: settings }),
        ),
      )
    })

  const saveProfile = () =>
    act('Saving…', async () => {
      await unwrap(
        api.PUT('/api/v1/engines/{engine_id}/profiles', {
          params: { path },
          body: { name: profileName, ...settings },
        }),
      )
      setProfileName('')
      setProfiles(
        await unwrap(api.GET('/api/v1/engines/{engine_id}/profiles', { params: { path } })),
      )
    })

  const number = (key: keyof typeof DEFAULTS) => ({
    type: 'number' as const,
    value: settings[key],
    onChange: (event: React.ChangeEvent<HTMLInputElement>) =>
      setSettings((current) => ({ ...current, [key]: Number(event.target.value) })),
  })

  return (
    <section aria-labelledby="engines-title">
      <h1 id="engines-title">Engines</h1>
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}
      {engines === null ? (
        <p role="status">Loading engines…</p>
      ) : (
        <div className="engine-layout">
          <div className="engine-list" aria-label="Available engines">
            {engines.map((engine) => (
              <button
                className={`engine-card ${selectedId === engine.id ? 'selected' : ''}`}
                key={engine.id}
                onClick={() => {
                  setSelectedId(engine.id)
                  setAnalysis(null)
                }}
                type="button"
              >
                <span>
                  <strong>{engine.name}</strong>
                  <small>
                    {engine.version} · {engine.license}
                  </small>
                </span>
                <span className={`status ${engine.status}`}>{engine.status.replace('_', ' ')}</span>
              </button>
            ))}
          </div>

          {selected && (
            <div className="panel">
              <div className="panel-heading">
                <div>
                  <h2>
                    {selected.name} {selected.version}
                  </h2>
                  <p>
                    Runs as a separate program.{' '}
                    <a href={selected.sourceUrl} target="_blank" rel="noreferrer">
                      {selected.name} is licensed under {selected.license}; get its source
                    </a>
                    .
                  </p>
                </div>
                {selected.status === 'not_installed' && (
                  <button className="primary" type="button" disabled={!!busy} onClick={install}>
                    Install
                  </button>
                )}
                {installed && (
                  <button className="danger" type="button" disabled={!!busy} onClick={remove}>
                    Remove
                  </button>
                )}
              </div>
              {selected.status === 'unavailable' && (
                <p className="hint">No download is available for this computer.</p>
              )}
              {busy && <p role="status">{busy}</p>}

              {installed && (
                <>
                  <div className="field-grid">
                    <label>
                      Nodes
                      <input min={1} max={5000000} {...number('nodes')} />
                    </label>
                    <label>
                      Lines
                      <input min={1} max={10} {...number('multiPV')} />
                    </label>
                    <label>
                      Hash (MB)
                      <input min={1} max={1024} {...number('hashMb')} />
                    </label>
                  </div>
                  <p className="hint">
                    Searches are limited by nodes, so the same settings give the same answer on any
                    computer.
                  </p>
                  <div className="actions">
                    <button type="button" disabled={!!busy} onClick={() => setSettings(DEFAULTS)}>
                      Reset to defaults
                    </button>
                    <button className="primary" type="button" disabled={!!busy} onClick={test}>
                      Test engine
                    </button>
                  </div>

                  <div className="profile-row">
                    {profiles.length > 0 && (
                      <label>
                        Load profile
                        <select
                          defaultValue=""
                          onChange={(event) => {
                            const profile = profiles.find((p) => p.name === event.target.value)
                            if (profile)
                              setSettings({
                                nodes: profile.nodes,
                                multiPV: profile.multiPV,
                                hashMb: profile.hashMb,
                              })
                          }}
                        >
                          <option value="" disabled>
                            Choose profile
                          </option>
                          {profiles.map((profile) => (
                            <option key={profile.name} value={profile.name}>
                              {profile.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    )}
                    <label>
                      Profile name
                      <input
                        value={profileName}
                        onChange={(event) => setProfileName(event.target.value)}
                        placeholder="Casual"
                        maxLength={40}
                      />
                    </label>
                    <button
                      type="button"
                      disabled={!!busy || !profileName.trim()}
                      onClick={saveProfile}
                    >
                      Save profile
                    </button>
                  </div>

                  {analysis && (
                    <div className="test-results" aria-live="polite">
                      <h3>
                        Start position · depth {analysis.depth} · {analysis.nodes} nodes
                      </h3>
                      <ol>
                        {analysis.lines.map((line) => (
                          <li key={line.move}>
                            <strong>{line.san}</strong> <span>{formatScore(line)}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
