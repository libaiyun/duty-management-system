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

  it('refreshes once and retries a normal 401 request with the replacement token', async () => {
    let token = 'expired-token'
    const refreshToken = vi.fn().mockImplementation(async () => {
      token = 'replacement-token'
      return true
    })
    const onUnauthorized = vi.fn()
    const fetcher = vi.fn()
      .mockResolvedValueOnce(makeMockResponse(401, { code: 'UNAUTHORIZED', message: '', trace_id: '' }))
      .mockResolvedValueOnce(makeMockResponse(200, { code: 'OK', message: 'ok', data: null, trace_id: '' }))
    const client = new HttpClient({
      baseUrl: '/api/v1', fetcher,
      callbacks: { getToken: () => token, refreshToken, onUnauthorized },
    })

    await client.get(authUrl)

    expect(refreshToken).toHaveBeenCalledOnce()
    expect(onUnauthorized).not.toHaveBeenCalled()
    expect((fetcher.mock.calls[1][1] as RequestInit).headers).toMatchObject({
      Authorization: 'Bearer replacement-token',
    })
  })

  it('only refreshes once before forcing logout when the retry is also unauthorized', async () => {
    const refreshToken = vi.fn().mockResolvedValue(true)
    const onUnauthorized = vi.fn()
    const fetcher = vi.fn().mockResolvedValue(
      makeMockResponse(401, { code: 'UNAUTHORIZED', message: '', trace_id: '' }),
    )
    const client = new HttpClient({
      baseUrl: '/api/v1', fetcher,
      callbacks: { getToken: () => 'expired-token', refreshToken, onUnauthorized },
    })

    await expect(client.get(authUrl)).rejects.toThrow()

    expect(refreshToken).toHaveBeenCalledOnce()
    expect(onUnauthorized).toHaveBeenCalledOnce()
  })

  it('forces logout when token refresh fails', async () => {
    const refreshToken = vi.fn().mockResolvedValue(false)
    const onUnauthorized = vi.fn()
    const fetcher = vi.fn().mockResolvedValue(
      makeMockResponse(401, { code: 'UNAUTHORIZED', message: '', trace_id: '' }),
    )
    const client = new HttpClient({
      baseUrl: '/api/v1', fetcher,
      callbacks: { refreshToken, onUnauthorized },
    })

    await expect(client.get(authUrl)).rejects.toThrow()

    expect(refreshToken).toHaveBeenCalledOnce()
    expect(onUnauthorized).toHaveBeenCalledOnce()
  })

  it('shares one refresh attempt across concurrent unauthorized requests', async () => {
    let resolveRefresh!: (result: boolean) => void
    const refreshToken = vi.fn(() => new Promise<boolean>((resolve) => { resolveRefresh = resolve }))
    const fetcher = vi.fn()
      .mockResolvedValueOnce(makeMockResponse(401, { code: 'UNAUTHORIZED', message: '', trace_id: '' }))
      .mockResolvedValueOnce(makeMockResponse(401, { code: 'UNAUTHORIZED', message: '', trace_id: '' }))
      .mockResolvedValue(makeMockResponse(200, { code: 'OK', message: 'ok', data: null, trace_id: '' }))
    const client = new HttpClient({ baseUrl: '/api/v1', fetcher, callbacks: { refreshToken } })

    const requests = Promise.all([client.get('/first'), client.get('/second')])
    await vi.waitFor(() => expect(refreshToken).toHaveBeenCalledOnce())
    resolveRefresh(true)
    await requests

    expect(refreshToken).toHaveBeenCalledOnce()
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
