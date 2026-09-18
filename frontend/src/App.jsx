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
  const [mode, setMode] = useState(() => {                  // 'historical' | 'live' | 'coords'; ?mode= preselects
    const m = new URLSearchParams(window.location.search).get('mode')
    return ['historical', 'live', 'coords'].includes(m) ? m : 'historical'
  })
  const [coords, setCoords] = useState({ lat: '38.6270', lon: '-90.1794', name: 'Mississippi River at St. Louis, MO' })

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

  // assessment when the observation / mode changes (?explain=1 in the URL requests the explanation immediately)
  const autoExplain = new URLSearchParams(window.location.search).get('explain') === '1'
  const fetchAssessment = (withExplain) => {
    if (mode === 'historical') return (siteId && obsId) ? api.assessment(siteId, obsId, withExplain) : null
    if (mode === 'live') return siteId ? api.liveSite(siteId, withExplain) : null
    return api.liveCoords(Number(coords.lat), Number(coords.lon), coords.name, withExplain)
  }
  const load = (withExplain, setBusy) => {
    const p = fetchAssessment(withExplain)
    if (!p) return
    setBusy(true); setError(null)
    p.then(setAssessment).catch((e) => setError(e.message)).finally(() => setBusy(false))
  }
  useEffect(() => {
    setAssessment(null); setError(null)
    if (mode !== 'coords') load(autoExplain, setLoading)
    else if (new URLSearchParams(window.location.search).get('auto') === '1') load(autoExplain, setLoading)  // demo links
  }, [siteId, obsId, mode])

  const explain = () => load(true, setExplaining)
  const runCoords = () => { setAssessment(null); load(false, setLoading) }

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

      <div className="modebar">
        {[['historical', 'Historical (labelled 2015–2024)'], ['live', 'Live — newest Sentinel-2 scene'], ['coords', 'Regional demo — any coordinates']].map(([m, label]) => (
          <button key={m} className={mode === m ? 'primary' : 'ghost'} onClick={() => setMode(m)}>{label}</button>
        ))}
      </div>

      {mode === 'coords' && (
        <div className="controls coords">
          <label className="field">Latitude<input value={coords.lat} onChange={(e) => setCoords({ ...coords, lat: e.target.value })} /></label>
          <label className="field">Longitude<input value={coords.lon} onChange={(e) => setCoords({ ...coords, lon: e.target.value })} /></label>
          <label className="field">Label<input value={coords.name} onChange={(e) => setCoords({ ...coords, name: e.target.value })} /></label>
          <button className="primary" disabled={loading} onClick={runCoords}>{loading ? <><span className="spin" />extracting…</> : 'Assess'}</button>
          <details className="notice warn span-all live-note">
            <summary>
              <b>Regional Demonstration Mode — live Sentinel-2 imagery, unvalidated location.</b> The models were trained on five US
              river basins only; here they run end-to-end on a new place with no local history, so no percentiles or stress score are
              possible and confidence is low. <span className="meta">— details</span>
            </summary>
            <div className="meta" style={{ marginTop: 8 }}>
              Inputs may fall outside the range the models learned from, and there is no ground truth to check against.
              Imagery comes from USGS's conterminous-US product, so coordinates must be inside the lower 48 states; a non-US site
              such as the Ravi River at Lahore would need a Copernicus / Earth Engine feed, which is not wired in.
            </div>
          </details>
        </div>
      )}

      <div className="controls" style={mode === 'coords' ? { display: 'none' } : undefined}>
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
        <label className="field">{mode === 'live' ? 'Sentinel-2 observation (live)' : 'Sentinel-2 observation'}
          <select value={obsId} onChange={(e) => setObsId(e.target.value)} disabled={mode === 'live'}>
            {mode === 'live' && <option value={obsId}>newest usable scene (auto)</option>}
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

      {assessment?.mode === 'live' && (() => {
        const skipped = assessment.scenes_tried.filter((t) => !t.usable)
        const hasLive = Object.values(assessment.live_readings || {}).some(Boolean)
        const d = new Date(assessment.observation.scene_datetime_utc)
        const ageDays = Math.round((Date.now() - d.getTime()) / 86400000)
        return (
          <details className="notice live-note" style={{ marginBottom: 16 }}>
            <summary>
              <b>Live:</b> newest cloud-free Sentinel-2 pass over this site, {fmtDate(assessment.observation.scene_datetime_utc).slice(0, 16)}
              {' '}({ageDays === 0 ? 'today' : `${ageDays} day${ageDays === 1 ? '' : 's'} ago`})
              {hasLive ? ' · live USGS sonde readings shown beside the predictions' : ''}
              {skipped.length ? ` · ${skipped.length} newer pass${skipped.length === 1 ? '' : 'es'} skipped (cloud or no clear water)` : ''}
              <span className="meta"> — details</span>
            </summary>
            <div className="meta" style={{ marginTop: 8 }}>
              Scene <code>{assessment.observation.scene}</code> from {assessment.source}.<br />
              {assessment.extraction_note}
              {skipped.length > 0 && (
                <><br />Skipped: {skipped.map((t) => `${t.date.slice(0, 10)} (${t.reason})`).join('; ')}</>
              )}
            </div>
          </details>
        )
      })()}

      {assessment ? (
        <div className="grid">
          <StressCard a={assessment} />
          <IndicatorGrid a={assessment} />
          <ShapPanel a={assessment} />
          <UncertaintyPanel a={assessment} />
          <ExplanationPanel a={assessment} loading={explaining} onExplain={explain} />
        </div>
      ) : !error && <div className="empty">{loading ? 'Loading assessment…' : mode === 'coords' ? 'Enter coordinates inside the conterminous US and press Assess.' : 'Select a site to begin.'}</div>}

      <footer className="footer">
        <span>Current-condition estimate from a single Sentinel-2 overpass — not a forecast.</span>
        <span>Training data: USGS matched Sentinel-2 / water-quality release, DOI 10.5066/P1A7T4FV (CC0).</span>
        {health && <span>Models trained {fmtDate(health.model_version).slice(0, 16)} · {health.n_sites} sites · {health.n_observations} observations</span>}
      </footer>
    </div>
  )
}
