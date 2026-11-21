import { useEffect, useMemo, useState } from 'react'
import './App.css'

type EngineEntry = {
  id: string
  name: string
  version: string
  license: string
  source_url: string
  status: 'not_installed' | 'installed' | 'installing'
  installed?: { binary: string }
}

type UciOption = {
  name: string
  type: 'spin' | 'check' | 'combo' | 'string' | 'button'
  default: unknown
  min: number | null
  max: number | null
  choices: string[] | null
}

type Candidate = {
  move_uci: string | null
  score_cp: number | null
  mate: number | null
  depth: number | null
  nodes: number | null
  pv: string[]
}

const START_POS = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
const BASIC = new Set(['Threads', 'Hash', 'Skill Level', 'UCI_LimitStrength', 'UCI_Elo'])
const ALLOWED_OPTIONS = new Set([...BASIC, 'UCI_ShowWDL'])
const safeOptions = (values: Record<string, unknown>) =>
  Object.fromEntries(Object.entries(values).filter(([name]) => ALLOWED_OPTIONS.has(name)))

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail || 'Request failed')
  }
  return response.json()
}

function App() {
  const [engines, setEngines] = useState<EngineEntry[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [options, setOptions] = useState<Record<string, UciOption>>({})
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [limitType, setLimitType] = useState<'nodes' | 'depth' | 'time'>('nodes')
  const [limitValue, setLimitValue] = useState(100000)
  const [candidateCount, setCandidateCount] = useState(3)
  const [profiles, setProfiles] = useState<Array<{ name: string; limit: { type: string; value: number }; multipv: number; options: Record<string, unknown> }>>([])
  const [profileName, setProfileName] = useState('')
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const selected = useMemo(
    () => engines.find((engine) => engine.id === selectedId) || null,
    [engines, selectedId],
  )

  const refresh = async () => {
    try {
      const entries = await api<EngineEntry[]>('/engines')
      setEngines(entries)
      setSelectedId((current) => current || entries[0]?.id || null)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Could not load engines')
    }
  }

  useEffect(() => { void refresh() }, [])

  useEffect(() => {
    if (!selected?.installed) return
    api<{ options: Record<string, UciOption> }>(`/engines/${selected.id}/options`)
      .then((result) => {
        setOptions(result.options)
        setValues((current) => {
          const next = { ...current }
          Object.values(result.options).forEach((option) => {
            if (ALLOWED_OPTIONS.has(option.name) && next[option.name] === undefined) {
              next[option.name] = option.default
            }
          })
          return next
        })
      })
      .catch((requestError) => setError(requestError.message))
    api<{ profiles: typeof profiles }>(`/engines/${selected.id}/profiles`)
      .then((result) => setProfiles(result.profiles))
      .catch(() => setProfiles([]))
  }, [selected?.id, selected?.installed])

  const install = async (engineId: string) => {
    setBusy(true)
    setError('')
    setEngines((current) => current.map((engine) => engine.id === engineId ? { ...engine, status: 'installing' } : engine))
    try {
      await api(`/engines/${engineId}/install`, { method: 'POST' })
      await refresh()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Install failed')
      await refresh()
    } finally {
      setBusy(false)
    }
  }

  const remove = async (engineId: string) => {
    setBusy(true)
    try {
      await api(`/engines/${engineId}`, { method: 'DELETE' })
      await refresh()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Remove failed')
    } finally {
      setBusy(false)
    }
  }

  const saveSettings = async () => {
    if (!selected) return
    await api(`/engines/${selected.id}/settings`, {
      method: 'PUT',
      body: JSON.stringify({ limit: { type: limitType, value: limitValue }, multipv: candidateCount, options: safeOptions(values) }),
    })
  }

  const saveProfile = async () => {
    if (!selected || !profileName.trim()) {
      setError('Enter a profile name')
      return
    }
    setBusy(true)
    setError('')
    try {
      await api(`/engines/${selected.id}/profiles`, {
        method: 'POST',
        body: JSON.stringify({
          name: profileName,
          settings: { limit: { type: limitType, value: limitValue }, multipv: candidateCount, options: safeOptions(values) },
        }),
      })
      const result = await api<{ profiles: typeof profiles }>(`/engines/${selected.id}/profiles`)
      setProfiles(result.profiles)
      setProfileName('')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Could not save profile')
    } finally {
      setBusy(false)
    }
  }

  const testEngine = async () => {
    if (!selected) return
    setBusy(true)
    setError('')
    setCandidates([])
    try {
      await saveSettings()
      const result = await api<{ candidates: Candidate[] }>(`/engines/${selected.id}/analyse`, {
        method: 'POST',
        body: JSON.stringify({
          fen: START_POS,
          limit: { type: limitType, value: limitValue },
          multipv: candidateCount,
          overrides: safeOptions(values),
        }),
      })
      setCandidates(result.candidates)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Engine test failed')
    } finally {
      setBusy(false)
    }
  }

  const basicOptions = Object.values(options).filter((option) => BASIC.has(option.name))
  const advancedOptions = Object.values(options).filter((option) =>
    ALLOWED_OPTIONS.has(option.name) && !BASIC.has(option.name),
  )

  return (
    <main className="app-shell">
      <header className="page-header">
        <div><p className="eyebrow">Duck Gambit</p><h1>Engines</h1></div>
        {selected && (
          <a className="attribution" href={selected.source_url} target="_blank" rel="noreferrer">
            {selected.name} is licensed under {selected.license}
          </a>
        )}
      </header>
      {error && <div className="alert" role="alert">{error}</div>}
      <div className="engine-layout">
        <section className="engine-list" aria-label="Available engines">
          {engines.map((engine) => (
            <button
              className={`engine-card ${selectedId === engine.id ? 'selected' : ''}`}
              key={engine.id}
              onClick={() => setSelectedId(engine.id)}
              type="button"
            >
              <div><h2>{engine.name}</h2><p>{engine.version} · {engine.license}</p></div>
              <span className={`status ${engine.status}`}>{engine.status.replace('_', ' ')}</span>
            </button>
          ))}
        </section>
        {selected ? (
          <section className="settings-panel" aria-label={`${selected.name} settings`}>
            <div className="settings-heading">
              <div><h2>{selected.name}</h2><p>Native process · UCI protocol</p></div>
              {selected.status === 'not_installed' ? (
                <button className="primary" type="button" disabled={busy} onClick={() => install(selected.id)}>Install</button>
              ) : selected.status === 'installed' ? (
                <button className="danger" type="button" disabled={busy} onClick={() => remove(selected.id)}>Remove</button>
              ) : null}
            </div>
            {selected.status === 'installed' && (
              <>
                <section className="settings-section">
                  <h3>Basic</h3>
                  <div className="field-grid">
                    <label>Search limit
                      <select value={limitType} onChange={(event) => setLimitType(event.target.value as typeof limitType)}>
                        <option value="nodes">Nodes (reproducible)</option>
                        <option value="depth">Depth</option>
                        <option value="time">Time (hardware-dependent)</option>
                      </select>
                    </label>
                    <label>{limitType === 'time' ? 'Milliseconds' : limitType === 'nodes' ? 'Nodes' : 'Depth'}
                      <input type="number" min="1" value={limitValue} onChange={(event) => setLimitValue(Number(event.target.value))} />
                    </label>
                    <label>Lines
                      <input type="number" min="1" max="10" value={candidateCount} onChange={(event) => setCandidateCount(Number(event.target.value))} />
                    </label>
                    {basicOptions.map((option) => (
                      <OptionField key={option.name} option={option} value={values[option.name] ?? option.default}
                        onChange={(value) => setValues((current) => ({ ...current, [option.name]: value }))} />
                    ))}
                  </div>
                  {limitType === 'time' && <p className="warning">Time limits can produce different results on different machines.</p>}
                </section>
                {advancedOptions.length > 0 && (
                  <details className="advanced">
                    <summary>Advanced options</summary>
                    <div className="field-grid">
                      {advancedOptions.map((option) => (
                        <OptionField key={option.name} option={option} value={values[option.name] ?? option.default}
                          onChange={(value) => setValues((current) => ({ ...current, [option.name]: value }))} />
                      ))}
                    </div>
                  </details>
                )}
                <div className="actions">
                  <button type="button" disabled={busy} onClick={() => {
                    const defaults: Record<string, unknown> = {}
                    Object.values(options).forEach((option) => {
                      if (ALLOWED_OPTIONS.has(option.name)) defaults[option.name] = option.default
                    })
                    setValues(defaults); setLimitType('nodes'); setLimitValue(100000); setCandidateCount(3)
                  }}>Reset to defaults</button>
                  <button type="button" disabled={busy} onClick={() => void saveSettings().catch((requestError) => setError(requestError.message))}>Save settings</button>
                  <button className="primary" type="button" disabled={busy} onClick={() => void testEngine()}>Test engine</button>
                </div>
                <div className="profile-row">
                  {profiles.length > 0 && (
                    <label>Load profile
                      <select aria-label="Load profile" defaultValue="" onChange={(event) => {
                        const profile = profiles.find((item) => item.name === event.target.value)
                        if (!profile) return
                        setLimitType(profile.limit.type as typeof limitType)
                        setLimitValue(profile.limit.value)
                        setCandidateCount(profile.multipv)
                        setValues(safeOptions(profile.options))
                      }}>
                        <option value="" disabled>Choose profile</option>
                        {profiles.map((profile) => <option key={profile.name} value={profile.name}>{profile.name}</option>)}
                      </select>
                    </label>
                  )}
                  <label>Profile name
                    <input value={profileName} onChange={(event) => setProfileName(event.target.value)} placeholder="Casual" />
                  </label>
                  <button type="button" disabled={busy} onClick={() => void saveProfile()}>Save profile</button>
                </div>
                {candidates.length > 0 && (
                  <section className="test-results" aria-live="polite">
                    <h3>Start-position candidates</h3>
                    {candidates.map((candidate, index) => (
                      <div className="candidate" key={`${candidate.move_uci}-${index}`}>
                        <strong>{candidate.move_uci || '—'}</strong>
                        <span>{candidate.mate !== null ? `Mate ${candidate.mate}` : `${candidate.score_cp ?? 0} cp`}</span>
                        <span>depth {candidate.depth ?? '-'}</span><span>{candidate.nodes ?? 0} nodes</span>
                      </div>
                    ))}
                  </section>
                )}
              </>
            )}
            {selected.status === 'installing' && <p role="status">Downloading and verifying Stockfish…</p>}
          </section>
        ) : <section className="settings-panel empty">No engines available.</section>}
      </div>
    </main>
  )
}

function OptionField({ option, value, onChange }: { option: UciOption; value: unknown; onChange: (value: unknown) => void }) {
  if (option.type === 'check') return <label className="check-field"><input type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} />{option.name}</label>
  if (option.type === 'combo') return <label>{option.name}<select value={String(value)} onChange={(event) => onChange(event.target.value)}>{(option.choices || []).map((choice) => <option key={choice} value={choice}>{choice}</option>)}</select></label>
  if (option.type === 'spin') return <label>{option.name}<input type="number" min={option.min ?? undefined} max={option.max ?? undefined} value={Number(value)} onChange={(event) => onChange(Number(event.target.value))} /></label>
  if (option.type === 'string') return <label>{option.name}<input type="text" value={String(value)} readOnly aria-label={`${option.name} server-controlled`} /></label>
  return null
}

export default App
