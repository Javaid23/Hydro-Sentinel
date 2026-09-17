const BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

async function get(path, params = {}) {
  const url = new URL(BASE + path)
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== null && url.searchParams.set(k, v))
  const res = await fetch(url)
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail || detail } catch { /* ignore */ }
    throw new Error(`${res.status}: ${detail}`)
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
}
