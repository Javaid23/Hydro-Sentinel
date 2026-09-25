import React, { useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import { StressCard, IndicatorGrid, ShapPanel, UncertaintyPanel, ExplanationPanel, LocalBaselinePanel, fmtDate } from './components/panels.jsx'
import { HistoryChart, SpectrumChart, SiteMap, MapLegend, OodChart } from './components/charts.jsx'

export default function App() {
  const [sites, setSites] = useState([])
  const [siteId, setSiteId] = useState('')
  const [observations, setObservations] = useState([])
  const [obsId, setObsId] = useState('')
  const [assessment, setAssessment] = useState(null)
  const [loading, setLoading] = useState(false)
  const [explaining, setExplaining] = useState(false)
  const [error, setError] = useState(null)          // { message, retryable }
  const [health, setHealth] = useState(null)
  const [history, setHistory] = useState(null)
  const [importance, setImportance] = useState(null)
  const [histTarget, setHistTarget] = useState('turbidity')
  const [building, setBuilding] = useState(false)
  const [mode, setMode] = useState(() => {                  // 'historical' | 'live' | 'coords'; ?mode= preselects
    const m = new URLSearchParams(window.location.search).get('mode')
    return ['historical', 'live', 'coords'].includes(m) ? m : 'historical'
  })
  // Every preset was verified against live imagery on 2026-09-18 (open water within the 250 m buffer).
  const PRESETS = [
    { region: 'Pakistan', name: 'Ravi River at Ravi Road Bridge, Lahore', lat: '31.6083', lon: '74.2959' },
    { region: 'Pakistan', name: 'Chenab River at Head Marala', lat: '32.6720', lon: '74.4640' },
    { region: 'Pakistan', name: 'Kabul River at Nowshera', lat: '34.0050', lon: '71.9830' },
    { region: 'Pakistan', name: 'Sutlej River at Head Islam', lat: '29.8290', lon: '72.5480' },
    { region: 'Pakistan', name: 'Indus River at Sukkur Barrage', lat: '27.6820', lon: '68.8480' },
    { region: 'Pakistan', name: 'Indus River at Kotri Barrage', lat: '25.4460', lon: '68.3090' },
    { region: 'South & East Asia', name: 'Ganges at Varanasi', lat: '25.3050', lon: '83.0200' },
    { region: 'South & East Asia', name: 'Brahmaputra at Guwahati', lat: '26.1900', lon: '91.7400' },
    { region: 'South & East Asia', name: 'Mekong at Phnom Penh', lat: '11.5650', lon: '104.9350' },
    { region: 'Africa', name: 'Nile at Luxor', lat: '25.7000', lon: '32.6400' },
    { region: 'Europe', name: 'Danube at Budapest', lat: '47.4980', lon: '19.0470' },
    { region: 'Europe', name: 'Rhine at Cologne', lat: '50.9400', lon: '6.9640' },
    { region: 'Europe', name: 'Thames at Gravesend', lat: '51.4480', lon: '0.3660' },
    { region: 'Americas', name: 'Mississippi River at St. Louis, MO', lat: '38.6270', lon: '-90.1794' },
  ]
  const REGIONS = [...new Set(PRESETS.map((p) => p.region))]
  const [coords, setCoords] = useState(PRESETS[0])

  // sites once
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
    Promise.all(['turbidity', 'chlorophyll_a', 'cdom'].map((t) => api.globalImportance(t, 8).then((r) => [t, r.features])))
      .then((pairs) => setImportance(Object.fromEntries(pairs))).catch(() => setImportance(null))
    api.sites().then((s) => {
      setSites(s)
      // default: the site with the most observations that has all three targets, else the busiest
      const full = s.filter((x) => x.targets_observed.length === 3).sort((a, b) => b.n_observations - a.n_observations)
      const busiest = [...s].sort((a, b) => b.n_observations - a.n_observations)
      setSiteId((full[0] || busiest[0])?.site_no || '')
    }).catch((e) => setError({ message: e.message, retryable: true }))
  }, [])

  // observations when the site changes
  useEffect(() => {
    if (!siteId) return
    setObservations([]); setObsId(''); setAssessment(null); setHistory(null)
    api.history(siteId).then(setHistory).catch(() => setHistory(null))
    api.observations(siteId, 400).then((o) => {
      setObservations(o)
      setObsId(o[o.length - 1]?.observation_id || '')
    }).catch((e) => setError({ message: e.message, retryable: !!e.retryable }))
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
    p.then(setAssessment)
      .catch((e) => setError({ message: e.message, retryable: !!e.retryable }))
      .finally(() => setBusy(false))
  }
  const retry = () => load(false, setLoading)
  useEffect(() => {
    setAssessment(null); setError(null)
    if (mode !== 'coords') load(autoExplain, setLoading)
    else if (new URLSearchParams(window.location.search).get('auto') === '1') load(autoExplain, setLoading)  // demo links
  }, [siteId, obsId, mode])

  const explain = () => load(true, setExplaining)
  const buildBaseline = () => {
    setBuilding(true); setError(null)
    api.buildBaseline(Number(coords.lat), Number(coords.lon))
      .then(() => load(false, setLoading))               // re-score so the new baseline is attached
      .catch((e) => setError({ message: e.message, retryable: !!e.retryable }))
      .finally(() => setBuilding(false))
  }
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
      </header>

      <div className="modebar">
        {[['historical', 'Historical (labelled 2015–2024)'], ['live', 'Live — newest Sentinel-2 scene'], ['coords', 'Regional demo — any coordinates']].map(([m, label]) => (
          <button key={m} className={mode === m ? 'primary' : 'ghost'} onClick={() => setMode(m)}>{label}</button>
        ))}
      </div>

      {mode === 'coords' && (
        <div className="controls coords">
          <label className="field span-all">Preset
            <select value="" onChange={(e) => { const p = PRESETS[Number(e.target.value)]; if (p) setCoords(p) }}>
              <option value="">Choose a river, or type coordinates below…</option>
              {REGIONS.map((r) => (
                <optgroup label={r} key={r}>
                  {PRESETS.map((p, i) => p.region === r ? <option key={p.name} value={i}>{p.name}</option> : null)}
                </optgroup>
              ))}
            </select>
          </label>
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
              Inside the conterminous US the imagery is USGS's aquatic-reflectance product (the same as the training data).
              Elsewhere it is Copernicus Sentinel-2 L2A, a land-oriented processing that reads brighter over water; its bands
              are divided by factors measured at US training sites before scoring, which adds uncertainty the intervals do not
              capture.
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
        <div className="meta">{loading ? <><span className="spin" />{mode === 'historical' ? 'assessing…' : 'fetching the newest satellite scene (20–60 s)…'}</> : null}</div>
      </div>

      {error && (
        <div className="notice err" style={{ marginBottom: 16, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ flex: 1 }}>
            {error.retryable ? <b>Temporary problem. </b> : null}{error.message}
            {error.retryable && mode !== 'historical' ? ' Live imagery is fetched from public satellite archives on the fly; brief network hiccups happen.' : ''}
          </span>
          {error.retryable && <button className="primary" disabled={loading} onClick={retry}>{loading ? 'Retrying…' : 'Retry'}</button>}
        </div>
      )}

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
              {assessment.source_key === 'global' ? ' · Copernicus L2A imagery, harmonised to the training product' : ''}
              {hasLive ? ' · live USGS sonde readings shown beside the predictions' : ''}
              {skipped.length ? ` · ${skipped.length} newer pass${skipped.length === 1 ? '' : 'es'} skipped (cloud or no clear water)` : ''}
              <span className="meta"> — details</span>
            </summary>
            <div className="meta" style={{ marginTop: 8 }}>
              Scene <code>{assessment.observation.scene}</code> from {assessment.source}
              {assessment.cloud_cover != null ? ` (scene cloud cover ${Math.round(assessment.cloud_cover)}%)` : ''}.<br />
              {assessment.extraction_note}
              {assessment.harmonisation?.applied && (
                <><br />Harmonisation factors (L2A ÷ ACOLITE, median of {assessment.harmonisation.n_pairs} same-day pairs at {assessment.harmonisation.n_sites} US sites):{' '}
                {Object.entries(assessment.harmonisation.factors).map(([b, f]) => `${b} ${f.toFixed(2)}`).join(' · ')}</>
              )}
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
          <section className="card span-4 map-card">
            <h2>Where</h2>
            <SiteMap sites={sites} selected={mode === 'coords' ? null : siteId} onSelect={(id) => { setMode('historical'); setSiteId(id) }}
              focus={mode === 'coords'
                ? { lat: Number(coords.lat), lon: Number(coords.lon), name: coords.name, zoom: 11, isSite: false }
                : site ? { lat: site.lat, lon: site.lon, name: site.station_nm, zoom: 9, isSite: true } : null} />
            <MapLegend />
          </section>
          <IndicatorGrid a={assessment} history={mode === 'coords' ? null : history} />
          <LocalBaselinePanel a={assessment} building={building} onBuild={buildBaseline} />
          {mode !== 'coords' && history && (
            <section className="card span-12">
              <div className="chart-head">
                <div>
                  <h2>How unusual is this? — site record, {history.n_observations} Sentinel-2 overpasses</h2>
                  <p className="sub" style={{ margin: 0 }}>Model predictions across every overpass at this site against the sonde readings, with the site's typical range. The black line marks the observation being assessed.</p>
                </div>
                <div className="tabs">
                  {Object.entries(assessment.indicators).map(([k, v]) => (
                    <button key={k} className={histTarget === k ? 'primary' : 'ghost'} onClick={() => setHistTarget(k)}>{v.label}</button>
                  ))}
                </div>
              </div>
              <HistoryChart history={history} target={histTarget} currentId={assessment.observation.observation_id}
                unit={assessment.indicators[histTarget]?.unit}
                livePoint={assessment.mode === 'live' ? { date: assessment.observation.scene_datetime_utc, predicted: assessment.indicators[histTarget]?.prediction } : null} />
            </section>
          )}
          <ShapPanel a={assessment} importance={importance} />
          <UncertaintyPanel a={assessment} />
          {assessment.ood && (
            <section className="card span-12">
              <div className="chart-head">
                <div>
                  <h2>Is this like anything the models have seen?</h2>
                  <p className="sub" style={{ margin: 0 }}>{assessment.ood.verdict}. Bands outside the training range mean the models are extrapolating — the intervals below do not account for that.</p>
                </div>
                <span className={`chip ${assessment.ood.n_outside === 0 ? 'Typical' : assessment.ood.n_outside > 3 ? 'High' : 'Elevated'}`}>
                  <span className="dot" aria-hidden="true" />
                  {assessment.ood.n_outside} / {assessment.ood.n_bands} bands outside
                </span>
              </div>
              <OodChart ood={assessment.ood} />
            </section>
          )}
          <section className="card span-12">
            <h2>What the satellite saw — spectral signature</h2>
            <p className="sub">Reflectance in the 11 Sentinel-2 bands over the 250 m buffer{history ? ", against this site's typical spectrum" : ''}.</p>
            <SpectrumChart bands={assessment.observation.bands} wavelengths={assessment.observation.band_wavelength_nm}
              siteMedian={mode === 'coords' ? null : history?.spectrum_median} siteIqr={mode === 'coords' ? null : history?.spectrum_iqr} />
          </section>
          <ExplanationPanel a={assessment} loading={explaining} onExplain={explain} />
        </div>
      ) : !error && <div className="empty">{loading ? (mode === 'historical' ? 'Loading assessment…' : 'Finding the newest cloud-free scene and reading the pixels around this point…') : mode === 'coords' ? 'Pick a river preset or enter coordinates, then press Assess.' : 'Select a site to begin.'}</div>}

      <footer className="footer">
        <span>Current-condition estimate from a single Sentinel-2 overpass — not a forecast.</span>
        <span>Training data: USGS matched Sentinel-2 / water-quality release, DOI 10.5066/P1A7T4FV (CC0).</span>
        {health && <span>Models trained {fmtDate(health.model_version).slice(0, 16)} · {health.n_sites} sites · {health.n_observations} observations</span>}
      </footer>
    </div>
  )
}
