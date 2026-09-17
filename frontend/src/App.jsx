import React, { useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import { StressCard, IndicatorGrid, ShapPanel, UncertaintyPanel, ExplanationPanel, fmtDate } from './components/panels.jsx'

export default function App() {
  const [sites, setSites] = useState([])
  const [siteId, setSiteId] = useState('')
  const [observations, setObservations] = useState([])
  const [obsId, setObsId] = useState('')
  const [assessment, setAssessment] = useState(null)
  const [loading, setLoading] = useState(false)
  const [explaining, setExplaining] = useState(false)
  const [error, setError] = useState(null)
  const [health, setHealth] = useState(null)

  // sites once
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
    api.sites().then((s) => {
      setSites(s)
      // default: the site with the most observations that has all three targets, else the busiest
      const full = s.filter((x) => x.targets_observed.length === 3).sort((a, b) => b.n_observations - a.n_observations)
      const busiest = [...s].sort((a, b) => b.n_observations - a.n_observations)
      setSiteId((full[0] || busiest[0])?.site_no || '')
    }).catch((e) => setError(`Cannot reach the API: ${e.message}`))
  }, [])

  // observations when the site changes
  useEffect(() => {
    if (!siteId) return
    setObservations([]); setObsId(''); setAssessment(null)
    api.observations(siteId, 400).then((o) => {
      setObservations(o)
      setObsId(o[o.length - 1]?.observation_id || '')
    }).catch((e) => setError(e.message))
  }, [siteId])

  // assessment when the observation changes
  useEffect(() => {
    if (!siteId || !obsId) return
    setLoading(true); setError(null)
    api.assessment(siteId, obsId, false)
      .then(setAssessment)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [siteId, obsId])

  const explain = () => {
    setExplaining(true)
    api.assessment(siteId, obsId, true)
      .then(setAssessment)
      .catch((e) => setError(e.message))
      .finally(() => setExplaining(false))
  }

  const byBasin = useMemo(() => {
    const m = {}
    sites.forEach((s) => { (m[s.basin] ||= []).push(s) })
    return m
  }, [sites])

  const site = sites.find((s) => s.site_no === siteId)

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <h1>HydroSentinel</h1>
          <span className="tagline">Satellite-based freshwater condition assessment</span>
        </div>
        <div className="flow"><span>Observe</span><span>Predict</span><span>Explain</span><span>Assess</span><span>Act</span></div>
      </header>

      <div className="controls">
        <label className="field">Monitoring site
          <select value={siteId} onChange={(e) => setSiteId(e.target.value)}>
            {Object.keys(byBasin).sort().map((b) => (
              <optgroup label={b} key={b}>
                {byBasin[b].map((s) => (
                  <option key={s.site_no} value={s.site_no}>
                    {s.station_nm} · {s.n_observations} obs{s.targets_observed.length === 3 ? ' · all 3' : ''}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        <label className="field">Sentinel-2 observation
          <select value={obsId} onChange={(e) => setObsId(e.target.value)}>
            {[...observations].reverse().map((o) => (
              <option key={o.observation_id} value={o.observation_id}>
                {fmtDate(o.scene_datetime_utc).slice(0, 16)} · {o.n_mask} px
              </option>
            ))}
          </select>
        </label>
        <div className="meta">
          {site ? <><b>{site.basin}</b> basin · {site.lat.toFixed(3)}, {site.lon.toFixed(3)}<br />ground truth: {site.targets_observed.join(', ') || 'none'}</> : null}
        </div>
        <div className="meta">{loading ? <><span className="spin" />assessing…</> : null}</div>
      </div>

      {error && <div className="notice err" style={{ marginBottom: 16 }}>{error}</div>}

      {assessment ? (
        <div className="grid">
          <StressCard a={assessment} />
          <IndicatorGrid a={assessment} />
          <ShapPanel a={assessment} />
          <UncertaintyPanel a={assessment} />
          <ExplanationPanel a={assessment} loading={explaining} onExplain={explain} />
        </div>
      ) : !error && <div className="empty">{loading ? 'Loading assessment…' : 'Select a site to begin.'}</div>}

      <footer className="footer">
        <span>Current-condition estimate from a single Sentinel-2 overpass — not a forecast.</span>
        <span>Training data: USGS matched Sentinel-2 / water-quality release, DOI 10.5066/P1A7T4FV (CC0).</span>
        {health && <span>Models trained {fmtDate(health.model_version).slice(0, 16)} · {health.n_sites} sites · {health.n_observations} observations</span>}
      </footer>
    </div>
  )
}
