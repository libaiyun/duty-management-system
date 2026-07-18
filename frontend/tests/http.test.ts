import { describe, expect, it, vi } from 'vitest'

import { ApiError, HttpClient, NetworkError, resolveErrorMessage } from '@/services/http'

type Fetcher = (...args: Parameters<typeof fetch>) => Promise<Response>

function makeFetchResponse(
  json: object,
  status = 200,
  ok = true,
): Response {
  return {
    ok,
    status,
    json: vi.fn().mockResolvedValue(json),
  } as unknown as Response
}

describe('HttpClient', () => {
  it('sends GET request and parses JSON response', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      makeFetchResponse({ code: 'OK', message: 'success', data: { status: 'ok' }, trace_id: 't1' }),
    )
    const client = new HttpClient({ baseUrl: '/api/v1', fetcher: fetcher as Fetcher })

    const res = await client.get<{ status: string }>('health')

    expect(fetcher).toHaveBeenCalledWith('/api/v1/health', expect.objectContaining({ method: 'GET' }))
    expect(res.data.status).toBe('ok')
    expect(res.trace_id).toBe('t1')
  })

  it('sends POST request with JSON body', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      makeFetchResponse({ code: 'OK', message: 'success', data: { id: 1 }, trace_id: 't2' }),
    )
    const client = new HttpClient({ baseUrl: '/api/v1', fetcher: fetcher as Fetcher })

    const res = await client.post<{ id: number }>('/items', { name: 'test' })

    expect(fetcher).toHaveBeenCalledWith('/api/v1/items', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ name: 'test' }),
    }))
    expect(res.data.id).toBe(1)
  })

  it('sends PUT request with JSON body', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      makeFetchResponse({ code: 'OK', message: 'success', data: { updated: true }, trace_id: 't3' }),
    )
    const client = new HttpClient({ baseUrl: '/api/v1', fetcher: fetcher as Fetcher })

    const res = await client.put<{ updated: boolean }>('/items/1', { name: 'changed' })

    expect(fetcher).toHaveBeenCalledWith('/api/v1/items/1', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({ name: 'changed' }),
    }))
    expect(res.data.updated).toBe(true)
  })

  it('sends DELETE request', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      makeFetchResponse({ code: 'OK', message: 'success', data: null, trace_id: 't4' }),
    )
    const client = new HttpClient({ baseUrl: '/api/v1', fetcher: fetcher as Fetcher })

    const res = await client.delete<null>('/items/1')

    expect(fetcher).toHaveBeenCalledWith('/api/v1/items/1', expect.objectContaining({ method: 'DELETE' }))
    expect(res.code).toBe('OK')
  })

  it('injects Authorization header from getToken callback', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      makeFetchResponse({ code: 'OK', message: 'success', data: null, trace_id: 't5' }),
    )
    const client = new HttpClient({
      baseUrl: '/api/v1',
      fetcher: fetcher as Fetcher,
      callbacks: { getToken: () => 'token-abc' },
    })

    await client.get('health')

    const callHeaders = (fetcher.mock.calls[0] as Parameters<typeof fetch>)[1]?.headers as Record<string, string> | undefined
    expect(callHeaders?.Authorization).toBe('Bearer token-abc')
  })

  it('does not inject Authorization header when getToken returns null', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      makeFetchResponse({ code: 'OK', message: 'success', data: null, trace_id: 't6' }),
    )
    const client = new HttpClient({
      baseUrl: '/api/v1',
      fetcher: fetcher as Fetcher,
      callbacks: { getToken: () => null },
    })

    await client.get('health')

    const callHeaders = (fetcher.mock.calls[0] as Parameters<typeof fetch>)[1]?.headers as Record<string, string> | undefined
    expect(callHeaders?.Authorization).toBeUndefined()
  })

  it('sends getPage request with query params', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      makeFetchResponse({
        code: 'OK',
        message: 'success',
        data: { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 },
        trace_id: 't7',
      }),
    )
    const client = new HttpClient({ baseUrl: '/api/v1', fetcher: fetcher as Fetcher })

    const res = await client.getPage('/items', { page: 2, page_size: 50 })

    expect(fetcher).toHaveBeenCalledWith(
      '/api/v1/items?page=2&page_size=50',
      expect.any(Object),
    )
    expect(res.data.total).toBe(0)
  })

  it('downloads a blob with authentication and room headers', async () => {
    const blob = new Blob(['xlsx'])
    const fetcher = vi.fn().mockResolvedValue({ ok: true, status: 200, blob: vi.fn().mockResolvedValue(blob) })
    const client = new HttpClient({
      baseUrl: '/api/v1', fetcher: fetcher as Fetcher,
      callbacks: { getToken: () => 'token-abc', getCurrentRoomId: () => 7 },
    })

    await expect(client.getBlob('/exports/1/download')).resolves.toBe(blob)
    expect(fetcher).toHaveBeenCalledWith('/api/v1/exports/1/download', expect.objectContaining({
      method: 'GET', headers: expect.objectContaining({ Authorization: 'Bearer token-abc', 'X-Current-Room-Id': '7' }),
    }))
  })
})

describe('HttpClient error handling', () => {
  it('throws NetworkError on connection failure', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('Connection refused'))
    const client = new HttpClient({ baseUrl: '/api/v1', fetcher: fetcher as Fetcher })

    await expect(client.get('health')).rejects.toThrow(NetworkError)
    await expect(client.get('health')).rejects.toThrow('Connection refused')
  })

  it('throws ApiError on non-OK HTTP status', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      makeFetchResponse(
        { code: 'NOT_FOUND', message: '资源不存在', trace_id: 't8' },
        404,
        false,
      ),
    )
    const client = new HttpClient({ baseUrl: '/api/v1', fetcher: fetcher as Fetcher })

    try {
      await client.get('missing')
      expect.fail('Expected ApiError')
    } catch (err) {
      const apiErr = err as ApiError
      expect(apiErr).toBeInstanceOf(ApiError)
      expect(apiErr.status).toBe(404)
      expect(apiErr.code).toBe('NOT_FOUND')
      expect(apiErr.message).toBe('资源不存在')
      expect(apiErr.traceId).toBe('t8')
    }
  })

  it('throws ApiError on business error (code !== OK)', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      makeFetchResponse(
        { code: 'SCHEDULE_LOCKED', message: '当前月份已锁定', trace_id: 't9' },
        200,
        true,
      ),
    )
    const client = new HttpClient({ baseUrl: '/api/v1', fetcher: fetcher as Fetcher })

    try {
      await client.get('schedule')
      expect.fail('Expected ApiError')
    } catch (err) {
      const apiErr = err as ApiError
      expect(apiErr.status).toBe(200)
      expect(apiErr.code).toBe('SCHEDULE_LOCKED')
      expect(apiErr.name).toBe('ApiError')
    }
  })

  it('includes validation error details', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      makeFetchResponse(
        {
          code: 'VALIDATION_ERROR',
          message: '参数校验失败',
          trace_id: 't10',
          details: [{ field: 'query.page', message: 'Input should be greater than or equal to 1' }],
        },
        400,
        false,
      ),
    )
    const client = new HttpClient({ baseUrl: '/api/v1', fetcher: fetcher as Fetcher })

    try {
      await client.get('items?page=0')
      expect.fail('Expected ApiError')
    } catch (err) {
      const apiErr = err as ApiError
      expect(apiErr.details).toBeDefined()
      expect(apiErr.details![0].field).toBe('query.page')
    }
  })

  it('calls onUnauthorized callback on 401 response', async () => {
    const onUnauthorized = vi.fn()
    const fetcher = vi.fn().mockResolvedValue(
      makeFetchResponse(
        { code: 'UNAUTHORIZED', message: '未登录', trace_id: 't11' },
        401,
        false,
      ),
    )
    const client = new HttpClient({
      baseUrl: '/api/v1',
      fetcher: fetcher as Fetcher,
      callbacks: { onUnauthorized },
    })

    await expect(client.get('secure')).rejects.toThrow(ApiError)
    expect(onUnauthorized).toHaveBeenCalledOnce()
  })

  it('handles 500 error response', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      makeFetchResponse({ code: 'INTERNAL_ERROR', message: '内部错误', trace_id: 't12' }, 500, false),
    )
    const client = new HttpClient({ baseUrl: '/api/v1', fetcher: fetcher as Fetcher })

    try {
      await client.get('fail')
      expect.fail('Expected ApiError')
    } catch (err) {
      const apiErr = err as ApiError
      expect(apiErr.status).toBe(500)
      expect(apiErr.code).toBe('INTERNAL_ERROR')
    }
  })

  it('handles non-JSON error response body gracefully', async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: vi.fn().mockRejectedValue(new Error('Invalid JSON')),
    } as unknown as Response)
    const client = new HttpClient({ baseUrl: '/api/v1', fetcher: fetcher as Fetcher })

    try {
      await client.get('fail')
      expect.fail('Expected ApiError')
    } catch (err) {
      const apiErr = err as ApiError
      expect(apiErr.status).toBe(500)
      expect(apiErr.code).toBe('UNKNOWN')
    }
  })

  it('throws NetworkError with fallback message for non-Error exceptions', async () => {
    const fetcher = vi.fn().mockRejectedValue('unexpected string error')
    const client = new HttpClient({ baseUrl: '/api/v1', fetcher: fetcher as Fetcher })

    await expect(client.get('fail')).rejects.toThrow('网络连接失败，请检查网络')
  })
})

describe('resolveErrorMessage', () => {
  it('returns ApiError message', () => {
    const err = new ApiError(409, { code: 'STATE_CONFLICT', message: '日期已存在', trace_id: 't' })
    expect(resolveErrorMessage(err, '操作失败')).toBe('日期已存在')
  })

  it('returns NetworkError message', () => {
    const err = new NetworkError('网络连接失败')
    expect(resolveErrorMessage(err, '操作失败')).toBe('网络连接失败')
  })

  it('returns fallback for unknown error shapes', () => {
    expect(resolveErrorMessage('boom', '操作失败')).toBe('操作失败')
    expect(resolveErrorMessage(null, '操作失败')).toBe('操作失败')
    expect(resolveErrorMessage({}, '操作失败')).toBe('操作失败')
  })

  it('uses message from generic object with message field', () => {
    expect(resolveErrorMessage({ message: '自定义错误' }, '操作失败')).toBe('自定义错误')
  })
})
