import { describe, it, expect, vi } from 'vitest'

import { HttpClient } from '@/services/http'

describe('HttpClient callbacks', () => {
  const authUrl = '/api/v1/auth/protected'

  async function makeMockResponse(status: number, body: object): Promise<Response> {
    return {
      ok: status >= 200 && status < 300,
      status,
      headers: new Headers(),
      json: () => Promise.resolve(body),
    } as Response
  }

  it('injects token via getToken callback', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(
      makeMockResponse(200, { code: 'OK', message: 'ok', data: null, trace_id: '' }),
    )
    const client = new HttpClient({
      baseUrl: '/api/v1',
      fetcher,
      callbacks: { getToken: () => 'my-token' },
    })

    await client.get(authUrl)

    const init = fetcher.mock.calls[0][1] as RequestInit
    const headers = init.headers as Record<string, string>
    expect(headers['Authorization']).toBe('Bearer my-token')
  })

  it('does not inject token when getToken returns null', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(
      makeMockResponse(200, { code: 'OK', message: 'ok', data: null, trace_id: '' }),
    )
    const client = new HttpClient({
      baseUrl: '/api/v1',
      fetcher,
      callbacks: { getToken: () => null },
    })

    await client.get(authUrl)

    const init = fetcher.mock.calls[0][1] as RequestInit
    const headers = init.headers as Record<string, string>
    expect(headers['Authorization']).toBeUndefined()
  })

  it('calls onUnauthorized on 401 response', async () => {
    const onUnauthorized = vi.fn()
    const fetcher = vi.fn().mockResolvedValueOnce(
      makeMockResponse(401, { code: 'UNAUTHORIZED', message: '', trace_id: '' }),
    )
    const client = new HttpClient({
      baseUrl: '/api/v1',
      fetcher,
      callbacks: { onUnauthorized },
    })

    await expect(client.get(authUrl)).rejects.toThrow()
    expect(onUnauthorized).toHaveBeenCalledOnce()
  })

  it('configureCallbacks updates callback references', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(
      makeMockResponse(200, { code: 'OK', message: 'ok', data: null, trace_id: '' }),
    )
    const client = new HttpClient({ baseUrl: '/api/v1', fetcher })

    client.configureCallbacks({ getToken: () => 'new-token' })

    await client.get(authUrl)

    const init = fetcher.mock.calls[0][1] as RequestInit
    const headers = init.headers as Record<string, string>
    expect(headers['Authorization']).toBe('Bearer new-token')
  })
})
