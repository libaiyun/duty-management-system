import { describe, expect, it, vi } from 'vitest'

import { HttpClient } from '@/services/http'

describe('HttpClient', () => {
  it('builds API URLs from a base URL and parses JSON responses', async () => {
    const fetcher = vi.fn().mockResolvedValue({
      json: vi.fn().mockResolvedValue({
        code: 'OK',
        message: 'success',
        data: { status: 'ok' },
        trace_id: 'trace-test',
      }),
    })
    const client = new HttpClient({
      baseUrl: '/api/v1/',
      fetcher: fetcher as unknown as typeof fetch,
    })

    const response = await client.get<{ status: string }>('health')

    expect(fetcher).toHaveBeenCalledWith('/api/v1/health', {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    })
    expect(response.data.status).toBe('ok')
    expect(response.trace_id).toBe('trace-test')
  })
})
