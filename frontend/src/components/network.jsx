import React, { useMemo, useState } from 'react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell, ReferenceLine,
} from 'recharts'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import { Chip, fmt, fmtDate } from './panels.jsx'

const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim()
const tooltipStyle = { background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12, color: 'var(--text-primary)' }

const scoreColour = (s) => (s == null ? css('--border')
  : s >= 70 ? css('--status-critical') : s >= 40 ? css('--status-warning') : css('--status-good'))

const STATUS_ICON = { Low: '▽', Typical: '○', Elevated: '△', High: '▲' }

// ---------------------------------------------------------------- network map
function NetworkMap({ sites, selected, onSelect }) {
  return (
    <MapContainer center={[39.5, -98]} zoom={4} style={{ height: 320, width: '100%', borderRadius: 10 }} scrollWheelZoom={false}>
      <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
      {sites.map((s) => (
        <CircleMarker key={s.site_no} center={[s.lat, s.lon]}
          radius={s.stress_score == null ? 4 : 4 + (s.stress_score / 100) * 7}
          pathOptions={{
            color: scoreColour(s.stress_score), fillColor: scoreColour(s.stress_score),
            fillOpacity: s.site_no === selected ? 1 : 0.65, weight: s.site_no === selected ? 3 : 1,
          }}
          eventHandlers={{ click: () => onSelect?.(s.site_no) }}>
          <Popup>
            <b>{s.station_nm}</b><br />
            {s.stress_score == null ? 'no reference' : `${Math.round(s.stress_score)} / 100 — ${s.stress_label}`}<br />
            {s.basin} · {s.n_observations} observations
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}

// ---------------------------------------------------------------- validation chart
export function ValidationChart({ validation }) {
  const [metric, setMetric] = useState('r2_log')
  if (!validation?.targets) return null
  const designs = ['random', 'site_holdout', 'lobo']
  const labels = { random: 'Random split', site_holdout: 'Unseen sites', lobo: 'Unseen basin' }
  const data = designs.map((d) => {
    const row = { design: labels[d] }
    Object.entries(validation.targets).forEach(([k, t]) => {
      if (t.designs[d]) row[k] = t.designs[d][metric]
    })
    return row
  })
  const colours = { turbidity: '#2a78d6', chlorophyll_a: '#eb6834', cdom: '#1baf7a' }
  const min = Math.min(0, ...data.flatMap((d) => Object.entries(d).filter(([k]) => k !== 'design').map(([, v]) => v)))
  return (
    <div>
      <div className="chart-head">
        <span className="legend">
          {Object.entries(validation.targets).map(([k, t]) => (
            <span key={k}><i style={{ background: colours[k] }} />{t.label}</span>
          ))}
        </span>
        <div className="tabs">
          <button className={metric === 'r2_log' ? 'primary' : 'ghost'} onClick={() => setMetric('r2_log')}>R² (log scale)</button>
          <button className={metric === 'r2' ? 'primary' : 'ghost'} onClick={() => setMetric('r2')}>R² (raw)</button>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }} barCategoryGap="22%">
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="design" tick={{ fontSize: 12, fill: 'var(--text-secondary)' }} axisLine={false} tickLine={false} />
          <YAxis domain={[Math.max(min, -3), 1]} allowDataOverflow tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
            axisLine={false} tickLine={false} width={40} />
          <Tooltip contentStyle={tooltipStyle}
            formatter={(v, n) => [v.toFixed(2), validation.targets[n]?.label || n]} />
          <ReferenceLine y={0} stroke="var(--text-muted)" strokeWidth={1} />
          {Object.keys(validation.targets).map((k) => (
            <Bar key={k} dataKey={k} fill={colours[k]} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <div className="meta" style={{ fontSize: 12 }}>
        Bars below zero mean the model does worse than predicting that group's average. Values are clipped at −3 for
        legibility; CDOM reaches {validation.targets.cdom?.designs?.lobo?.r2_log?.toFixed(1)} on an unseen basin.
      </div>
      <div className="notice" style={{ marginTop: 10 }}>{validation.explanation}</div>
      <div className="meta" style={{ fontSize: 11, marginTop: 6 }}>Source: {validation.source}</div>
    </div>
  )
}

// ---------------------------------------------------------------- network overview
export function NetworkOverview({ network, validation, onOpenSite, loading }) {
  const [basin, setBasin] = useState('')
  const [sort, setSort] = useState('stress')
  const sites = useMemo(() => {
    let out = network?.sites || []
    if (basin) out = out.filter((s) => s.basin === basin)
    if (sort === 'name') out = [...out].sort((a, b) => a.station_nm.localeCompare(b.station_nm))
    return out
  }, [network, basin, sort])

  if (loading) return <div className="empty"><span className="spin" />Scoring every site in the network…</div>
  if (!network) return <div className="empty">Network overview unavailable.</div>

  const basins = [...new Set((network.sites || []).map((s) => s.basin))].sort()
  const flagged = sites.filter((s) => Object.values(s.indicators).some((i) => i.status === 'Elevated' || i.status === 'High'))

  return (
    <div className="grid">
      <section className="card span-12">
        <h2>Monitoring network — what needs attention</h2>
        <p className="sub">
          Every site scored on its most recent archived observation, ranked by how unusual conditions are
          relative to that site's own record. One pass over the network instead of opening sites one at a time.
        </p>
        <div className="tiles">
          <div className="tile"><div className="tile-n">{network.n_sites}</div><div className="tile-l">sites assessed</div></div>
          <div className="tile"><div className="tile-n" style={{ color: css('--status-warning') }}>{flagged.length}</div>
            <div className="tile-l">with an elevated or high indicator</div></div>
          {Object.entries(network.counts || {}).map(([label, n]) => (
            <div className="tile" key={label}>
              <div className="tile-n">{n}</div><div className="tile-l">{label.toLowerCase()}</div>
            </div>
          ))}
        </div>
        <div className="notice" style={{ marginTop: 12 }}>{network.note}</div>
      </section>

      <section className="card span-7">
        <h2>Where</h2>
        <p className="sub">Marker size and colour follow the stress score. Click a site to open its full assessment.</p>
        <NetworkMap sites={sites} onSelect={onOpenSite} />
        <div className="legend" style={{ marginTop: 8 }}>
          <span><i style={{ background: css('--status-good'), borderRadius: '50%' }} />lower stress</span>
          <span><i style={{ background: css('--status-warning'), borderRadius: '50%' }} />moderate</span>
          <span><i style={{ background: css('--status-critical'), borderRadius: '50%' }} />higher</span>
        </div>
      </section>

      <section className="card span-5">
        <div className="chart-head">
          <h2>Ranked sites</h2>
          <div className="tabs">
            <select value={basin} onChange={(e) => setBasin(e.target.value)} style={{ fontSize: 12, padding: '4px 8px' }}>
              <option value="">All basins</option>
              {basins.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
            <button className={sort === 'stress' ? 'primary' : 'ghost'} onClick={() => setSort('stress')}>By stress</button>
            <button className={sort === 'name' ? 'primary' : 'ghost'} onClick={() => setSort('name')}>By name</button>
          </div>
        </div>
        <div className="site-list">
          {sites.map((s) => (
            <button className="site-row" key={s.site_no} onClick={() => onOpenSite(s.site_no)}>
              <span className="score" style={{ background: scoreColour(s.stress_score) }}>
                {s.stress_score == null ? '—' : Math.round(s.stress_score)}
              </span>
              <span className="who">
                <span className="nm">{s.station_nm}</span>
                <span className="sub2">{s.basin} · {fmtDate(s.scene_datetime_utc).slice(5, 16)} · {s.n_observations} obs</span>
              </span>
              <span className="inds">
                {Object.entries(s.indicators).map(([k, i]) => (
                  <span key={k} className={`mini-chip ${i.status || 'none'}`} title={`${i.label}: ${fmt(i.prediction)} ${i.unit}${i.percentile != null ? ` · ${Math.round(i.percentile)}th pct` : ' · no reference'}`}>
                    {i.status ? STATUS_ICON[i.status] : '·'}
                  </span>
                ))}
              </span>
            </button>
          ))}
        </div>
      </section>

      {validation && (
        <section className="card span-12">
          <h2>Can these numbers be trusted? — measured, per validation design</h2>
          <p className="sub">
            The same models evaluated three ways. Left to right the test gets harder: a random split lets the model
            see every site during training; then whole sites are held out; then whole basins.
          </p>
          <ValidationChart validation={validation} />
          <div className="verdicts">
            {Object.entries(validation.targets).map(([k, t]) => (
              <div className="verdict" key={k}>
                <b>{t.label}</b>
                <span>{t.verdict}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
