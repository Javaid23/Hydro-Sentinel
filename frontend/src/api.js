const BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

async function get(path, params = {}) {
  const url = new URL(BASE + path)
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== null && url.searchParams.set(k, v))
  let res
  try {
    res = await fetch(url)
  } catch (e) {
    const err = new Error('Cannot reach the HydroSentinel API — is the backend running?')
    err.retryable = true; err.status = 0
    throw err
  }
  if (!res.ok) {
    let detail = res.statusText
    try { const j = await res.json(); detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail || j) } catch { /* ignore */ }
    const err = new Error(detail)
    err.status = res.status
    err.retryable = res.status === 503 || res.status >= 500   // imagery service hiccup, cold start
    throw err
  }
  return res.json()
}

export const api = {
  health: () => get('/health'),
  sites: () => get('/sites'),
  observations: (siteId, limit = 200) => get(`/sites/${siteId}/observations`, { limit }),
  assessment: (siteId, observationId, explain) =>
    get(`/assessment/${siteId}`, { observation_id: observationId, explain: explain ? 'true' : undefined }),
  globalImportance: (target, topK = 8) => get(`/models/${target}/global-importance`, { top_k: topK }),
  history: (siteId) => get(`/sites/${siteId}/history`),
  liveSite: (siteId, explain) => get(`/live/${siteId}`, { explain: explain ? 'true' : undefined }),
  liveCoords: (lat, lon, name, explain) => get('/live/coords', { lat, lon, name, explain: explain ? 'true' : undefined }),
}
