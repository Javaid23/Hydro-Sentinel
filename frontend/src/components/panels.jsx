import React from 'react'
import { Gauge, ReferenceHistogram, ImportanceChart, BaselineHistogram } from './charts.jsx'

const fmt = (v, d = 2) => (v == null || Number.isNaN(v) ? '—' : Number(v).toFixed(v >= 100 ? 0 : d))
const fmtDate = (iso) => (iso ? new Date(iso).toUTCString().replace(':00 GMT', ' UTC') : '—')

export function Chip({ kind, text, icon }) {
  return (
    <span className={`chip ${kind}`}>
      <span className="dot" aria-hidden="true" />
      {icon ? <span aria-hidden="true">{icon}</span> : null}
      {text}
    </span>
  )
}

const STATUS_ICON = { Low: '▽', Typical: '○', Elevated: '△', High: '▲' }
const CONF_ICON = { Moderate: '◐', Low: '◔', 'Very low': '○' }
const TIER_TEXT = {
  site_seen: 'Site in training data',
  basin_seen: 'Basin in training data, site not',
  out_of_region: 'Out of region — unvalidated',
  mixed: 'Mixed validation tiers',
}

// ---------------------------------------------------------------- 1. Current assessment
export function StressCard({ a }) {
  const s = a.stress
  const o = a.observation
  if (s.score == null) {
    // No site or basin history to rank against (out-of-region): say so instead of drawing an empty gauge.
    return (
      <section className="card span-8">
        <h2>Current assessment</h2>
        <div className="hero">
          <div>
            <div className="label">Stress score not available here</div>
            <div className="meta" style={{ marginTop: 6, maxWidth: 720 }}>
              The Freshwater Stress Score ranks each prediction against <b>this site's own historical record</b> (or its basin's).
              {o.station_nm ? <> <b>{o.station_nm}</b> has</> : ' This location has'} no history in the training data and lies outside
              the five training basins, and the score is never computed against a pooled all-basin reference — a naturally
              clear or naturally turbid river would look anomalous just for being itself. The predictions and their
              90 % intervals below stand on their own.
            </div>
            <div className="meta" style={{ marginTop: 8 }}>
              Sentinel-2 overpass {fmtDate(o.scene_datetime_utc)} · <Chip kind="tier" text={TIER_TEXT[a.validation_tier]} />
            </div>
          </div>
        </div>
      </section>
    )
  }
  return (
    <section className="card span-8">
      <h2>Current assessment</h2>
      <p className="sub">Freshwater Stress Score — how unusual the predicted conditions are relative to this site's own history. Not a validated ecological health index.</p>
      <div className="hero">
        <Gauge score={s.score} label={s.label} />
        <div style={{ flex: 1, minWidth: 240 }}>
          <div className="bands-row">
            <span className="band low">0–40 Lower</span><span className="band mid">40–70 Moderate</span><span className="band high">70–100 Higher</span>
          </div>
          <div className="mini-indicators">
            {Object.values(a.indicators).map((ind) => (
              <div key={ind.key} className="mini">
                <div className="mini-label">{ind.label}</div>
                <div className="mini-val">{ind.percentile == null ? '—' : `${Math.round(ind.percentile)}th`}</div>
                <div className="mini-sub">{ind.status || 'no reference'}</div>
              </div>
            ))}
          </div>
          <div className="meta" style={{ marginTop: 8 }}>
            <b>{o.station_nm || 'Unnamed location'}</b> · {o.basin || 'unknown basin'} · Sentinel-2 overpass {fmtDate(o.scene_datetime_utc)}
            <br />
            Based on {s.indicators_used.length} of 3 indicators
            {s.indicators_missing.length ? ` (no reference for: ${s.indicators_missing.join(', ')})` : ''} ·{' '}
            <Chip kind="tier" text={TIER_TEXT[a.validation_tier]} />
          </div>
        </div>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------- 2. Indicator breakdown
export function IndicatorGrid({ a, history }) {
  return (
    <section className="card span-12">
      <h2>Indicator breakdown</h2>
      <p className="sub">Each predicted value is ranked against the site's historical observations (or the basin's, when the site has too few). Percentile → status.</p>
      <div className="indicators">
        {Object.values(a.indicators).map((ind) => (
          <div className="indicator" key={ind.key}>
            <div className="name">
              <span>{ind.label}</span>
              {ind.status ? <Chip kind={ind.status} icon={STATUS_ICON[ind.status]} text={ind.status} /> : <Chip kind="tier" text="no reference" />}
            </div>
            <div className="value">{fmt(ind.prediction)}<small>{ind.unit}</small></div>
            {ind.observed != null && (
              <div className="observed">{a.mode === 'live' ? 'Live USGS sonde reading' : 'Matched sonde reading'}: {fmt(ind.observed)} {ind.unit}</div>
            )}
            <div className="pbar" role="img" aria-label={`${ind.label} percentile ${ind.percentile ?? 'unavailable'}`}>
              <div className="fill" style={{ width: `${ind.percentile ?? 0}%` }} />
              {ind.percentile != null && <div className="marker" style={{ left: `calc(${ind.percentile}% - 1px)` }} />}
            </div>
            <div className="pbar-caption">
              <span>{ind.percentile == null ? 'No site/basin reference' : `${Math.round(ind.percentile)}th percentile`}</span>
              <span>{ind.reference_level !== 'none' ? `${ind.reference_level} history, n=${ind.n_reference}` : ''}</span>
            </div>
            <div className="chips">
              <Chip kind={`conf-${ind.confidence.split(' ')[0]}`} icon={CONF_ICON[ind.confidence]} text={`${ind.confidence} confidence`} />
            </div>
            {history?.targets?.[ind.key]?.histogram?.counts?.length > 0 && (
              <div className="hist">
                <div className="meta" style={{ fontSize: 11, marginTop: 8 }}>Where this prediction sits in the {ind.reference_level} record (log-spaced bins)</div>
                <ReferenceHistogram history={history} target={ind.key} value={ind.prediction} status={ind.status} unit={ind.unit} />
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------- 3. Why? (SHAP)
export function ShapPanel({ a, importance }) {
  return (
    <section className="card span-6">
      <h2>Why? — what drove each prediction</h2>
      <p className="sub">Top SHAP contributions per indicator. Bars show how much each satellite feature moved the model's prediction relative to its baseline — a contribution, not a cause.</p>
      <div className="legend">
        <span><i style={{ background: 'var(--div-warm)' }} />raised the prediction</span>
        <span><i style={{ background: 'var(--div-cool)' }} />lowered the prediction</span>
      </div>
      {Object.values(a.indicators).map((ind) => {
        const max = Math.max(...ind.top_contributions.map((c) => Math.abs(c.shap_log)), 1e-6)
        return (
          <div className="shap-target" key={ind.key}>
            <h3>{ind.label} <span className="meta">· baseline {fmt(ind.baseline_prediction)} → {fmt(ind.prediction)} {ind.unit}</span></h3>
            {ind.top_contributions.map((c) => {
              const w = (Math.abs(c.shap_log) / max) * 50
              return (
                <div className="shap-row" key={c.feature} title={`${c.label}: value ${fmt(c.value, 3)}, ×${c.factor}`}>
                  <span className="lbl">{c.label}</span>
                  <div className="shap-bar">
                    <div className="mid" />
                    <div className={`seg ${c.direction}`} style={{ width: `${w}%` }} />
                  </div>
                  <span className="val">×{c.factor.toFixed(2)}</span>
                </div>
              )
            })}
          </div>
        )
      })}
      {importance && (
        <details className="live-note" style={{ marginTop: 6 }}>
          <summary className="meta"><b>Overall</b> — which satellite features the models rely on across all training data (mean |SHAP|) — details</summary>
          {Object.entries(importance).map(([k, feats]) => (
            <div key={k} style={{ marginTop: 10 }}>
              <div className="meta"><b>{a.indicators[k]?.label || k}</b></div>
              <ImportanceChart features={feats} />
            </div>
          ))}
        </details>
      )}
    </section>
  )
}

// ---------------------------------------------------------------- 4. How certain?
export function UncertaintyPanel({ a }) {
  return (
    <section className="card span-6">
      <h2>How certain? — prediction intervals</h2>
      <p className="sub">90 % split-conformal intervals, calibrated on held-out observations. Coverage is guaranteed only for sites in the training data; the confidence label states how far this observation is from that regime.</p>
      {Object.values(a.indicators).map((ind) => {
        const lo = ind.interval.lower, hi = ind.interval.upper
        const span = Math.max(hi * 1.15, 1e-6)
        const pct = (v) => `${Math.min(100, (v / span) * 100)}%`
        return (
          <div className="iv-row" key={ind.key}>
            <div>
              <div><b>{ind.label}</b></div>
              <Chip kind={`conf-${ind.confidence.split(' ')[0]}`} icon={CONF_ICON[ind.confidence]} text={ind.confidence} />
            </div>
            <div className="iv-track" role="img" aria-label={`${ind.label}: ${fmt(lo)} to ${fmt(hi)} ${ind.unit}, point ${fmt(ind.prediction)}`}>
              <div className="axis" />
              <div className="range" style={{ left: pct(lo), width: `calc(${pct(hi)} - ${pct(lo)})` }} />
              <div className="point" style={{ left: pct(ind.prediction) }} />
              {ind.observed != null && <div className="obs" style={{ left: pct(ind.observed) }} title={`sonde ${fmt(ind.observed)}`} />}
            </div>
            <div className="iv-num">
              {fmt(ind.prediction)} <span className="meta">[{fmt(lo)} – {fmt(hi)}] {ind.unit}</span>
            </div>
          </div>
        )
      })}
      <div className="legend" style={{ marginTop: 10 }}>
        <span><i style={{ background: 'var(--seq-600)', borderRadius: '50%' }} />prediction</span>
        <span><i style={{ background: 'var(--seq-200)' }} />90 % interval</span>
        <span><i style={{ background: 'var(--text-primary)', width: 2 }} />{a.mode === 'live' ? 'live' : 'matched'} sonde reading (if any)</span>
      </div>
      <div className="notice" style={{ marginTop: 10 }}>
        {Object.values(a.indicators)[0].confidence_note}
      </div>
    </section>
  )
}

// ---------------------------------------------------------------- 5 + 6. LLM explanation and actions
export function ExplanationPanel({ a, loading, onExplain }) {
  const e = a.llm_explanation
  return (
    <>
      <section className="card span-8">
        <h2>What does this mean?</h2>
        <p className="sub">Plain-language interpretation generated from the numbers above. The language model does not produce or modify any value.</p>
        {e ? (
          <div className="prose">
            <p><b>{e.summary}</b></p>
            <p>{e.interpretation}</p>
            {e.caveats?.length ? <ul className="caveats">{e.caveats.map((c, i) => <li key={i}>{c}</li>)}</ul> : null}
            <div className="disclaimer">{e.disclaimer} · {e.model}</div>
          </div>
        ) : a.llm_error ? (
          <div className="notice warn">Explanation unavailable — {a.llm_error}. The numeric assessment above is complete without it.</div>
        ) : (
          <div className="empty">
            <button className="primary" disabled={loading} onClick={onExplain}>
              {loading ? <><span className="spin" />Generating…</> : 'Generate explanation'}
            </button>
          </div>
        )}
      </section>
      <section className="card span-4">
        <h2>Recommended actions</h2>
        <p className="sub">Ranked suggestions for investigation. Decision support, not instructions.</p>
        {e?.actions?.length ? (
          <ol className="actions">
            {e.actions.map((x) => (
              <li key={x.rank}><span className="n">{x.rank}</span><div><div>{x.action}</div><div className="r">{x.rationale}</div></div></li>
            ))}
          </ol>
        ) : <div className="empty">{e ? 'No actions suggested.' : 'Generate the explanation to see actions.'}</div>}
      </section>
    </>
  )
}

export { fmt, fmtDate }


// ---------------------------------------------------------------- local baseline (out of region)
export function LocalBaselinePanel({ a, building, onBuild }) {
  const b = a.local_baseline
  if (!b) return null

  if (!b.available) {
    return (
      <section className="card span-12">
        <h2>No local baseline yet</h2>
        <p className="sub">
          A score needs something to compare against. There are no measurements here, but the Sentinel-2
          archive still covers this spot — we can run the same models over past scenes and use those
          estimates as a reference for how unusual today is.
        </p>
        <div className="empty">
          <button className="primary" disabled={building} onClick={onBuild}>
            {building ? <><span className="spin" />Reading the archive… this takes a few minutes</> : 'Build a baseline from the archive'}
          </button>
          <div className="meta" style={{ marginTop: 10, maxWidth: 620, margin: '10px auto 0' }}>
            Extracts roughly two dozen cloud-free scenes from the last two years at these coordinates.
            Slow once, then cached. The result is model output, not ground truth — it says how unusual
            today is for this spot, not whether the values are right.
          </div>
        </div>
      </section>
    )
  }

  const cls = b.score == null ? '' : b.score >= 70 ? 'high' : b.score >= 40 ? 'mid' : 'low'
  return (
    <section className="card span-12 baseline-card">
      <div className="chart-head">
        <div>
          <h2>{b.name} — relative to this location's own satellite record</h2>
          <p className="sub" style={{ margin: 0 }}>{b.description}</p>
        </div>
        <span className={`chip ${b.covers_seasonal_cycle === false ? 'Elevated' : 'tier'}`}>
          {b.covers_seasonal_cycle === false ? <span className="dot" aria-hidden="true" /> : null}
          {b.n_scenes} scenes · {b.first_scene} to {b.last_scene}
          {b.span_days != null ? ` · ${Math.round(b.span_days / 30)} months` : ''}
        </span>
      </div>

      <div className="hero" style={{ marginBottom: 6 }}>
        <div>
          <div className="number">{b.score == null ? '—' : Math.round(b.score)}<small> / 100</small></div>
          <div className="label">{b.label || '—'}</div>
        </div>
        <div style={{ flex: 1, minWidth: 260 }}>
          <div className="scorebar" role="img" aria-label={`Local anomaly score ${b.score ?? 'unavailable'} of 100`}>
            <div className={`fill ${cls}`} style={{ width: `${b.score ?? 0}%` }} />
          </div>
          <div className="ticks"><span>0 · Lower</span><span>40</span><span>70</span><span>100</span></div>
          <div className="notice warn" style={{ marginTop: 10 }}>{b.note}</div>
          {b.span_warning && <div className="notice warn" style={{ marginTop: 6 }}><b>Narrow window. </b>{b.span_warning}</div>}
        </div>
      </div>

      <div className="indicators" style={{ marginTop: 12 }}>
        {Object.entries(b.indicators || {}).map(([k, ind]) => (
          <div className="indicator" key={k}>
            <div className="name">
              <span>{ind.label}</span>
              {ind.status ? <Chip kind={ind.status} icon={STATUS_ICON[ind.status]} text={ind.status} /> : null}
            </div>
            <div className="value">{fmt(ind.prediction)}<small>{ind.unit}</small></div>
            <div className="pbar" role="img" aria-label={`${ind.label} ${ind.percentile} percentile of the local record`}>
              <div className="fill" style={{ width: `${ind.percentile}%` }} />
              <div className="marker" style={{ left: `calc(${ind.percentile}% - 1px)` }} />
            </div>
            <div className="pbar-caption">
              <span>{Math.round(ind.percentile)}th percentile here</span>
              <span>median {fmt(ind.quantiles.p50)} {ind.unit}</span>
            </div>
            <BaselineHistogram target={b.targets?.[k]} value={ind.prediction} status={ind.status} unit={ind.unit} />
          </div>
        ))}
      </div>
      <div className="meta" style={{ fontSize: 12, marginTop: 8 }}>
        Source: {b.source}. Built {b.built_utc?.slice(0, 10)}.
      </div>
    </section>
  )
}
