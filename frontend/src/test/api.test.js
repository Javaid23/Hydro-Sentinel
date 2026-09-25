/**
 * The API client decides which failures the user is offered a retry for. Getting that wrong means
 * either hiding a transient imagery hiccup behind a dead-end error, or inviting pointless retries
 * of something that will never succeed.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { api } = await import('../api.js')

const jsonResponse = (body, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  statusText: 'x',
  json: async () => body,
})

beforeEach(() => { global.fetch = vi.fn() })
afterEach(() => { vi.restoreAllMocks() })

describe('request building', () => {
  it('omits absent optional parameters rather than sending empty ones', async () => {
    global.fetch.mockResolvedValue(jsonResponse({ ok: true }))
    await api.assessment('14211720', undefined, false)
    const url = new URL(global.fetch.mock.calls[0][0])
    expect(url.pathname).toBe('/assessment/14211720')
    expect(url.searchParams.has('observation_id')).toBe(false)
    expect(url.searchParams.has('explain')).toBe(false)
  })

  it('passes coordinates and the explain flag through', async () => {
    global.fetch.mockResolvedValue(jsonResponse({ ok: true }))
    await api.liveCoords(31.6083, 74.2959, 'Ravi', true)
    const url = new URL(global.fetch.mock.calls[0][0])
    expect(url.pathname).toBe('/live/coords')
    expect(url.searchParams.get('lat')).toBe('31.6083')
    expect(url.searchParams.get('name')).toBe('Ravi')
    expect(url.searchParams.get('explain')).toBe('true')
  })
})

describe('error classification', () => {
  it('treats a dead backend as retryable and says so plainly', async () => {
    global.fetch.mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(api.health()).rejects.toMatchObject({
      retryable: true,
      status: 0,
      message: expect.stringMatching(/is the backend running/i),
    })
  })

  it('treats an imagery-service failure as retryable', async () => {
    global.fetch.mockResolvedValue(jsonResponse({ detail: 'imagery service unreachable' }, 503))
    await expect(api.liveCoords(1, 2)).rejects.toMatchObject({
      retryable: true,
      status: 503,
      message: 'imagery service unreachable',
    })
  })

  it('does not invite retries of a request that will never succeed', async () => {
    global.fetch.mockResolvedValue(jsonResponse({ detail: 'unknown site nope' }, 404))
    await expect(api.assessment('nope')).rejects.toMatchObject({ retryable: false, status: 404 })
  })

  it('surfaces a structured detail instead of [object Object]', async () => {
    global.fetch.mockResolvedValue(jsonResponse({ detail: { reason: 'no usable scene', tried: 6 } }, 503))
    await expect(api.liveCoords(1, 2)).rejects.toMatchObject({
      message: expect.stringContaining('no usable scene'),
    })
  })

  it('falls back to the status text when the body is not json', async () => {
    global.fetch.mockResolvedValue({
      ok: false, status: 500, statusText: 'Internal Server Error',
      json: async () => { throw new Error('not json') },
    })
    await expect(api.network()).rejects.toMatchObject({
      status: 500, retryable: true, message: 'Internal Server Error',
    })
  })
})
