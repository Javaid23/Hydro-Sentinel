/**
 * What the dashboard must never do: show a number it does not have, or present an unvalidated
 * figure as a validated one. These assert those guarantees as rendered, since that is where a
 * regression would actually mislead someone.
 */
import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

// The charts and map are exercised elsewhere; stub them so these assertions are about wording.
vi.mock('../components/charts.jsx', () => ({
  Gauge: ({ score, label }) => <div data-testid="gauge">{score == null ? '—' : Math.round(score)} {label}</div>,
  ReferenceHistogram: () => <div data-testid="histogram" />,
  ImportanceChart: () => <div data-testid="importance" />,
  BaselineHistogram: () => <div data-testid="baseline-histogram" />,
}))

const { StressCard, IndicatorGrid, UncertaintyPanel, ExplanationPanel, LocalBaselinePanel, fmt, fmtDate } =
  await import('../components/panels.jsx')

const indicator = (over = {}) => ({
  key: 'turbidity', label: 'Turbidity', unit: 'FNU', note: '',
  prediction: 1.63,
  interval: { lower: 0.43, upper: 3.84, coverage: 0.9, method: 'split conformal' },
  observed: 1.4, percentile: 18.8, reference_level: 'site', n_reference: 367,
  status: 'Low', validation_tier: 'site_seen', confidence: 'Moderate',
  confidence_note: 'This site is in the training data.',
  baseline_prediction: 9.7,
  top_contributions: [{ feature: 'B05_buf250_mean', label: 'B05 red edge 1', value: 132, shap_log: -0.4, factor: 0.67, direction: 'lowered' }],
  ...over,
})

const assessment = (over = {}) => ({
  observation: {
    observation_id: 'x', scene: 'S2B_TEST', scene_datetime_utc: '2026-09-11T19:09:09+00:00',
    site_no: '14211720', station_nm: 'WILLAMETTE RIVER AT PORTLAND, OR', basin: 'Willamette',
    lat: 45.5, lon: -122.7, n_mask: 261, n_l2flag: 305,
  },
  stress: {
    name: 'Freshwater Stress Score', score: 40.4, label: 'Moderate stress',
    indicators_used: ['turbidity'], indicators_missing: [], description: 'Equal-weight mean.',
  },
  indicators: { turbidity: indicator() },
  validation_tier: 'site_seen', model_version: '2026-09-17T13:49:09+00:00',
  ...over,
})

describe('number formatting', () => {
  it('renders an em dash rather than a zero when a value is missing', () => {
    expect(fmt(null)).toBe('—')
    expect(fmt(undefined)).toBe('—')
    expect(fmt(NaN)).toBe('—')
    expect(fmt(0)).toBe('0.00')          // a real zero is a value, not a gap
  })

  it('keeps precision sensible across magnitudes', () => {
    expect(fmt(1.6349)).toBe('1.63')
    expect(fmt(208.4)).toBe('208')
    expect(fmtDate(null)).toBe('—')
    expect(fmtDate('2026-09-11T19:09:09+00:00')).toMatch(/11 Sep 2026/)
  })
})

describe('stress score card', () => {
  it('shows the score and its band when one can be computed', () => {
    render(<StressCard a={assessment()} />)
    expect(screen.getByTestId('gauge')).toHaveTextContent('40')
    expect(screen.getByTestId('gauge')).toHaveTextContent('Moderate stress')
  })

  it('explains the absence instead of drawing an empty gauge out of region', () => {
    const a = assessment({
      stress: { name: 'Freshwater Stress Score', score: null, label: null, indicators_used: [], indicators_missing: ['turbidity'], description: '' },
      validation_tier: 'out_of_region',
      observation: { ...assessment().observation, station_nm: 'Nile at Luxor', site_no: null, basin: null },
    })
    render(<StressCard a={a} />)
    expect(screen.getByText(/Stress score not available here/i)).toBeInTheDocument()
    expect(screen.getByText(/no history in the training data/i)).toBeInTheDocument()
    expect(screen.queryByTestId('gauge')).not.toBeInTheDocument()
    expect(screen.getByText(/never computed against a pooled all-basin reference/i)).toBeInTheDocument()
  })
})

describe('indicator breakdown', () => {
  it('shows the percentile, its reference level and the matched reading', () => {
    render(<IndicatorGrid a={assessment()} history={null} />)
    expect(screen.getByText(/19th percentile/)).toBeInTheDocument()
    expect(screen.getByText(/site history, n=367/)).toBeInTheDocument()
    expect(screen.getByText(/Matched sonde reading: 1.40 FNU/)).toBeInTheDocument()
  })

  it('never invents a status when there is no reference', () => {
    const a = assessment({
      indicators: { turbidity: indicator({ percentile: null, status: null, reference_level: 'none', n_reference: 0, observed: null, confidence: 'Low', validation_tier: 'out_of_region' }) },
    })
    render(<IndicatorGrid a={a} history={null} />)
    expect(screen.getByText(/no reference/i)).toBeInTheDocument()
    expect(screen.getByText(/No site\/basin reference/i)).toBeInTheDocument()
    expect(screen.queryByText(/percentile$/)).not.toBeInTheDocument()
    expect(screen.getByText(/Low confidence/)).toBeInTheDocument()
  })
})

describe('uncertainty panel', () => {
  it('states the interval and the confidence tier note', () => {
    render(<UncertaintyPanel a={assessment()} />)
    expect(screen.getByText(/0.43 – 3.84/)).toBeInTheDocument()
    expect(screen.getByText(/This site is in the training data/)).toBeInTheDocument()
  })
})

describe('explanation panel', () => {
  it('keeps the numeric assessment when the language model fails', () => {
    const a = assessment({ llm_explanation: null, llm_error: 'NotFoundError: model missing' })
    render(<ExplanationPanel a={a} loading={false} onExplain={() => {}} />)
    expect(screen.getByText(/Explanation unavailable/i)).toBeInTheDocument()
    expect(screen.getByText(/numeric assessment above is complete without it/i)).toBeInTheDocument()
  })

  it('carries the disclaimer whenever prose is shown', () => {
    const a = assessment({
      llm_explanation: {
        summary: 'Low turbidity.', interpretation: 'Driven by turbidity.',
        actions: [{ rank: 1, action: 'Sample the site', rationale: 'Confirm the estimate' }],
        caveats: ['One overpass only'], model: 'openai/gpt-oss-120b',
        generated_utc: '2026-09-25T12:00:00+00:00',
        disclaimer: 'Generated by a language model from the numeric assessment above.',
      },
    })
    render(<ExplanationPanel a={a} loading={false} onExplain={() => {}} />)
    expect(screen.getByText(/Generated by a language model/i)).toBeInTheDocument()
    expect(screen.getByText(/One overpass only/)).toBeInTheDocument()
    expect(screen.getByText(/Sample the site/)).toBeInTheDocument()
  })
})

describe('local baseline panel', () => {
  const baseline = {
    available: true, name: 'Local Anomaly Score',
    description: 'How unusual today is compared with this model’s own estimates here.',
    kind: 'model_predictions',
    note: 'Reference built from model predictions, not ground truth.',
    source: 'Copernicus Sentinel-2 L2A', n_scenes: 25, first_scene: '2025-09-30',
    last_scene: '2026-09-23', span_days: 357, covers_seasonal_cycle: true,
    built_utc: '2026-09-25T12:00:00+00:00', score: 78.2, label: 'Higher stress',
    indicators: { turbidity: { label: 'Turbidity', unit: 'FNU', prediction: 208, percentile: 78.2, n_reference: 25, quantiles: { p50: 110 }, status: 'Elevated' } },
    targets: { turbidity: { histogram: { edges: [], counts: [] }, series: [] } },
  }

  it('never presents itself as the validated stress score', () => {
    render(<LocalBaselinePanel a={assessment({ local_baseline: baseline })} building={false} onBuild={() => {}} />)
    expect(screen.getByText(/Local Anomaly Score/)).toBeInTheDocument()
    expect(screen.getByText(/not ground truth/i)).toBeInTheDocument()
    expect(screen.queryByText(/^Freshwater Stress Score$/)).not.toBeInTheDocument()
    expect(screen.getByText(/25 scenes/)).toBeInTheDocument()
  })

  it('warns when the window is too narrow to speak to seasonality', () => {
    const narrow = { ...baseline, span_days: 27, covers_seasonal_cycle: false, span_warning: 'These scenes span only 27 days.' }
    render(<LocalBaselinePanel a={assessment({ local_baseline: narrow })} building={false} onBuild={() => {}} />)
    expect(screen.getByText(/Narrow window/i)).toBeInTheDocument()
    expect(screen.getByText(/span only 27 days/)).toBeInTheDocument()
  })

  it('offers to build one, stating the cost and what it is not', () => {
    const none = { available: false, reason: 'not built for this location yet' }
    render(<LocalBaselinePanel a={assessment({ local_baseline: none })} building={false} onBuild={() => {}} />)
    expect(screen.getByRole('button', { name: /Build a baseline/i })).toBeInTheDocument()
    expect(screen.getByText(/model output, not ground truth/i)).toBeInTheDocument()
  })

  it('renders nothing when the assessment has no baseline field', () => {
    const { container } = render(<LocalBaselinePanel a={assessment()} building={false} onBuild={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })
})
