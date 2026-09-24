import React, { useEffect, useMemo, useState } from 'react'
import {
  ResponsiveContainer, ComposedChart, LineChart, BarChart, Line, Area, Bar, XAxis, YAxis, Tooltip,
  ReferenceLine, ReferenceArea, ReferenceDot, CartesianGrid, Cell, Legend,
} from 'recharts'
import { MapContainer, TileLayer, CircleMarker, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { fmt } from './panels.jsx'

// palette roles (see styles.css); series colours are fixed per entity, never cycled
const COL = {
  observed: '#2a78d6',   // slot 1 blue — ground truth
  predicted: '#eb6834',  // slot 2 orange — model
  band: '#9ec5f4',       // sequential light blue — interval / typical range
  now: '#0b0b0b',
  seq: ['#cde2fb', '#9ec5f4', '#5598e7', '#2a78d6', '#184f95'],
  basins: { Delaware: '#2a78d6', Illinois: '#eb6834', Trinity: '#1baf7a', 'Upper Colorado': '#eda100', Willamette: '#e87ba4' },
}

const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim()

// ---------------------------------------------------------------- score gauge
export function Gauge({ score, label }) {
  const r = 78, cx = 100, cy = 100, stroke = 16
  const start = -210, sweep = 240                                   // degrees, gap at the bottom
  const arc = (from, to, color, width) => {
    const a0 = ((start + from) * Math.PI) / 180, a1 = ((start + to) * Math.PI) / 180
    const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0), x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1)
    return <path d={`M ${x0} ${y0} A ${r} ${r} 0 ${to - from > 180 ? 1 : 0} 1 ${x1} ${y1}`} stroke={color} strokeWidth={width} fill="none" strokeLinecap="round" />
  }
  const pct = score == null ? 0 : Math.max(0, Math.min(100, score)) / 100
  const color = score == null ? css('--border') : score >= 70 ? css('--status-critical') : score >= 40 ? css('--status-warning') : css('--status-good')
  return (
    <svg viewBox="0 0 200 162" width="230" role="img" aria-label={`Stress score ${score ?? 'unavailable'} of 100`}>
      {arc(0, sweep, css('--surface-2'), stroke)}
      {/* band ticks at 40 and 70 */}
      {[40, 70].map((t) => { const a = ((start + (t / 100) * sweep) * Math.PI) / 180; return <line key={t} x1={cx + (r - 13) * Math.cos(a)} y1={cy + (r - 13) * Math.sin(a)} x2={cx + (r + 13) * Math.cos(a)} y2={cy + (r + 13) * Math.sin(a)} stroke={css('--surface-1')} strokeWidth={3} /> })}
      {score != null && arc(0, Math.max(0.5, pct * sweep), color, stroke)}
      <text x={cx} y={cy - 2} textAnchor="middle" fontSize="44" fontWeight="700" fill={css('--text-primary')} letterSpacing="-1">{score == null ? '—' : Math.round(score)}</text>
      <text x={cx} y={cy + 20} textAnchor="middle" fontSize="12" fill={css('--text-muted')}>/ 100</text>
      <text x={cx} y={cy + 40} textAnchor="middle" fontSize="13" fontWeight="600" fill={css('--text-primary')}>{label || 'No reference'}</text>
      <text x={cx - r + 6} y={cy + 52} textAnchor="middle" fontSize="10" fill={css('--text-muted')}>0</text>
      <text x={cx + r - 6} y={cy + 52} textAnchor="middle" fontSize="10" fill={css('--text-muted')}>100</text>
    </svg>
  )
}

// ---------------------------------------------------------------- history: observed vs predicted with typical range
const tooltipStyle = { background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12, color: 'var(--text-primary)' }

export function HistoryChart({ history, target, currentId, unit, livePoint }) {
  const t = history?.targets?.[target]
  const data = useMemo(() => (t?.series || []).map((p) => ({ ...p, ts: new Date(p.date).getTime(), year: new Date(p.date).getFullYear() })), [t])
  const [logScale, setLogScale] = useState(true)
  if (!t || !data.length) return <div className="empty">No history for this site.</div>
  const q = t.quantiles
  // in live mode the scored scene is newer than the stored series, so it is passed in separately
  const current = data.find((p) => p.observation_id === currentId)
    || (livePoint ? { ts: new Date(livePoint.date).getTime(), predicted: livePoint.predicted, isLive: true } : null)
  const years = [...new Set(data.map((p) => p.year))]
  const ticks = years.filter((y, i) => years.length <= 6 || i % 2 === 0).map((y) => new Date(`${y}-01-01`).getTime())
  return (
    <div>
      <div className="chart-head">
        <span className="legend">
          <span><i style={{ background: COL.observed, borderRadius: '50%' }} />observed (sonde)</span>
          <span><i style={{ background: COL.predicted }} />predicted from satellite</span>
          <span><i style={{ background: COL.band }} />typical range (p25–p75)</span>
          <span><i style={{ background: COL.now, width: 2 }} />this observation</span>
        </span>
        <label className="toggle"><input type="checkbox" checked={logScale} onChange={(e) => setLogScale(e.target.checked)} /> log scale</label>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="ts" type="number" domain={[(min) => min, (max) => Math.max(max, current?.ts ?? max)]} ticks={ticks} tickFormatter={(v) => new Date(v).getFullYear()} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
          <YAxis scale={logScale ? 'log' : 'linear'} domain={logScale ? ['auto', 'auto'] : [0, 'auto']} allowDataOverflow tick={{ fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} width={44} tickFormatter={(v) => fmt(v, 1)} />
          <Tooltip contentStyle={tooltipStyle} labelFormatter={(v) => new Date(v).toUTCString().slice(0, 16)}
            formatter={(v, n) => [v == null ? '—' : `${fmt(v)} ${unit}`, n === 'observed' ? 'observed' : n === 'predicted' ? 'predicted' : n]} />
          {q?.p25 != null && <ReferenceArea y1={q.p25} y2={q.p75} fill={COL.band} fillOpacity={0.35} stroke="none" />}
          {q?.p90 != null && <ReferenceLine y={q.p90} stroke="var(--status-warning)" strokeDasharray="4 3" label={{ value: 'p90', position: 'insideTopRight', fontSize: 10, fill: 'var(--text-muted)' }} />}
          <Line dataKey="predicted" stroke={COL.predicted} strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />
          <Line dataKey="observed" stroke={COL.observed} strokeWidth={0} dot={{ r: 2.5, fill: COL.observed, strokeWidth: 0 }} isAnimationActive={false} />
          {current && <ReferenceLine x={current.ts} stroke={COL.now} strokeWidth={1.5}
            label={current.isLive ? { value: 'live', position: 'top', fontSize: 10, fill: 'var(--text-secondary)' } : undefined} />}
          {current && <ReferenceDot x={current.ts} y={current.predicted} r={6} fill={COL.predicted} stroke="var(--surface-1)" strokeWidth={2} />}
        </ComposedChart>
      </ResponsiveContainer>
      <div className="meta" style={{ fontSize: 12 }}>
        {t.n_reference} observations · {t.reference_level} reference · median {fmt(q?.p50)} {unit}, p90 {fmt(q?.p90)} {unit}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- reference histogram with current value
export function ReferenceHistogram({ history, target, value, status, unit }) {
  const t = history?.targets?.[target]
  const h = t?.histogram
  if (!h?.counts?.length) return <div className="meta">No reference distribution.</div>
  const data = h.counts.map((c, i) => ({ i, lo: h.edges[i], hi: h.edges[i + 1], mid: Math.sqrt(h.edges[i] * h.edges[i + 1]), count: c,
    isCurrent: value != null && value >= h.edges[i] && value < h.edges[i + 1] }))
  const statusCol = status === 'High' ? css('--status-critical') : status === 'Elevated' ? css('--status-warning') : css('--seq-450')
  return (
    <ResponsiveContainer width="100%" height={110}>
      <BarChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: 0 }} barCategoryGap={2}>
        <XAxis dataKey="mid" tickFormatter={(v) => (v < 10 ? Number(v).toFixed(1) : fmt(v, 0))} tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} interval={4} />
        <YAxis hide />
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => [v, 'observations']} labelFormatter={(_, p) => p?.[0] ? `${fmt(p[0].payload.lo, 1)}–${fmt(p[0].payload.hi, 1)} ${unit}` : ''} />
        <Bar dataKey="count" isAnimationActive={false} radius={[3, 3, 0, 0]}>
          {data.map((d) => <Cell key={d.i} fill={d.isCurrent ? statusCol : 'var(--seq-200)'} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

// ---------------------------------------------------------------- spectral signature
export function SpectrumChart({ bands, wavelengths, siteMedian, siteIqr }) {
  if (!bands) return null
  const data = Object.keys(wavelengths).map((b) => ({
    band: b, nm: wavelengths[b], now: bands[b], median: siteMedian?.[b], lo: siteIqr?.[b]?.[0], hi: siteIqr?.[b]?.[1],
  })).sort((a, b) => a.nm - b.nm)
  return (
    <div>
      <div className="legend">
        <span><i style={{ background: COL.predicted }} />this observation</span>
        {siteMedian && <span><i style={{ background: COL.observed }} />site median</span>}
        {siteIqr && <span><i style={{ background: COL.band }} />site p25–p75</span>}
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="nm" type="number" domain={[420, 2250]} ticks={[443, 560, 665, 783, 865, 1610, 2190]} tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} unit=" nm" />
          <YAxis tick={{ fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} width={44} />
          <Tooltip contentStyle={tooltipStyle} labelFormatter={(v, p) => `${p?.[0]?.payload.band} · ${v} nm`} formatter={(v, n) => [fmt(v, 0), n === 'now' ? 'this observation' : n === 'median' ? 'site median' : n]} />
          {siteIqr && <Area dataKey="hi" stroke="none" fill={COL.band} fillOpacity={0.35} isAnimationActive={false} />}
          {siteIqr && <Area dataKey="lo" stroke="none" fill="var(--surface-1)" fillOpacity={1} isAnimationActive={false} />}
          {siteMedian && <Line dataKey="median" stroke={COL.observed} strokeWidth={1.5} dot={false} strokeDasharray="4 3" isAnimationActive={false} />}
          <Line dataKey="now" stroke={COL.predicted} strokeWidth={2} dot={{ r: 3, fill: COL.predicted, strokeWidth: 0 }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="meta" style={{ fontSize: 12 }}>Buffer-mean aquatic reflectance × 10⁴ per Sentinel-2 band. Higher red / red-edge relative to blue is the turbidity signal the models rely on.</div>
    </div>
  )
}

// ---------------------------------------------------------------- global importance bars
export function ImportanceChart({ features }) {
  if (!features?.length) return null
  const data = features.map((f) => ({ label: f.label.replace(/\(.*?\)/g, '').trim(), share: f.share * 100 }))
  return (
    <ResponsiveContainer width="100%" height={22 * data.length + 10}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 36, bottom: 0, left: 0 }} barCategoryGap={4}>
        <XAxis type="number" hide domain={[0, 'dataMax']} />
        <YAxis type="category" dataKey="label" width={190} tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${v.toFixed(1)} %`, 'share of |SHAP|']} />
        <Bar dataKey="share" fill={COL.observed} isAnimationActive={false} radius={[0, 4, 4, 0]} label={{ position: 'right', fontSize: 10, fill: 'var(--text-muted)', formatter: (v) => `${v.toFixed(0)}%` }} />
      </BarChart>
    </ResponsiveContainer>
  )
}

// ---------------------------------------------------------------- map
const pin = L.divIcon({ className: 'pin', html: '<div class="pin-dot"></div>', iconSize: [18, 18], iconAnchor: [9, 9] })

function FlyTo({ lat, lon, zoom }) {
  const map = useMap()
  useEffect(() => { if (lat != null && lon != null) map.flyTo([lat, lon], zoom, { duration: 0.8 }) }, [lat, lon, zoom])
  return null
}

export function SiteMap({ sites, selected, onSelect, focus }) {
  const center = focus ? [focus.lat, focus.lon] : [39.5, -98]
  const zoom = focus?.zoom ?? 4
  return (
    <MapContainer center={center} zoom={zoom} style={{ height: 300, width: '100%', borderRadius: 10 }} scrollWheelZoom={false}>
      <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
      {sites.map((s) => (
        <CircleMarker key={s.site_no} center={[s.lat, s.lon]} radius={s.site_no === selected ? 7 : 4}
          pathOptions={{ color: COL.basins[s.basin] || '#888', fillColor: COL.basins[s.basin] || '#888', fillOpacity: s.site_no === selected ? 1 : 0.6, weight: s.site_no === selected ? 2 : 1 }}
          eventHandlers={{ click: () => onSelect?.(s.site_no) }}>
          <Popup><b>{s.station_nm}</b><br />{s.basin} · {s.n_observations} observations<br />{s.targets_observed.join(', ')}</Popup>
        </CircleMarker>
      ))}
      {focus && !focus.isSite && <Marker position={[focus.lat, focus.lon]} icon={pin}><Popup>{focus.name}</Popup></Marker>}
      <FlyTo lat={focus?.lat} lon={focus?.lon} zoom={zoom} />
    </MapContainer>
  )
}

export function MapLegend() {
  return (
    <div className="legend" style={{ marginTop: 6 }}>
      {Object.entries(COL.basins).map(([b, c]) => <span key={b}><i style={{ background: c, borderRadius: '50%' }} />{b}</span>)}
    </div>
  )
}

// ---------------------------------------------------------------- out-of-distribution check
export function OodChart({ ood }) {
  if (!ood?.bands?.length) return null
  const data = ood.bands.map((b) => ({ ...b, shortLabel: `${b.band} ${b.label.split(' ').slice(1).join(' ')}` }))
  return (
    <div>
      <div className="legend">
        <span><i style={{ background: COL.band }} />training range (p1–p99)</span>
        <span><i style={{ background: COL.observed, borderRadius: '50%' }} />this observation, in range</span>
        <span><i style={{ background: css('--status-critical'), borderRadius: '50%' }} />outside the training range</span>
      </div>
      <div className="ood-rows">
        {data.map((b) => {
          const pos = Math.max(0, Math.min(100, b.position))
          return (
            <div className={`ood-row ${b.outside ? 'is-outside' : ''}`} key={b.band} title={`${b.label}: ${b.value} · training p1–p99 ${b.training.p1}–${b.training.p99}`}>
              <span className="lbl">{b.shortLabel}</span>
              <div className="ood-track">
                <div className="ood-range" />
                <div className={`ood-dot ${b.outside ? 'outside' : ''}`} style={{ left: `${pos}%` }} />
              </div>
              <span className="val">{b.outside ? (b.direction === 'above' ? '↑ above' : '↓ below') : 'in range'}</span>
            </div>
          )
        })}
      </div>
      <div className="meta" style={{ fontSize: 12, marginTop: 6 }}>{ood.reference}.</div>
    </div>
  )
}
