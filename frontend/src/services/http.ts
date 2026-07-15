import type { ApiErrorDetail, ApiResponse, ErrorResponse, PageParams, PageResponse } from '@/types/api'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly traceId: string
  readonly details?: ApiErrorDetail[]

  constructor(status: number, body: ErrorResponse) {
    super(body.message)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code
    this.traceId = body.trace_id
    this.details = body.details
  }
}

export class NetworkError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'NetworkError'
  }
}

export async function parseApiError(response: Response): Promise<ApiError> {
  let body: ErrorResponse
  try {
    body = await response.json()
  } catch {
    body = {
      code: 'UNKNOWN',
      message: `请求失败 (${response.status})`,
      trace_id: '',
    }
  }
  return new ApiError(response.status, body)
}

interface HttpClientCallbacks {
  getToken?: () => string | null
  getCurrentRoomId?: () => number | null
  refreshToken?: () => Promise<boolean>
  onUnauthorized?: () => void
}

export interface HttpClientOptions {
  baseUrl?: string
  fetcher?: typeof fetch
  callbacks?: HttpClientCallbacks
}

export class HttpClient {
  private readonly baseUrl: string
  private readonly fetcher: typeof fetch
  private callbacks: HttpClientCallbacks
  private refreshPromise: Promise<boolean> | null = null
  private hasNotifiedUnauthorized = false

  constructor(options: HttpClientOptions = {}) {
    this.baseUrl = options.baseUrl ?? import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
    this.fetcher = options.fetcher ?? fetch
    this.callbacks = options.callbacks ?? {}
  }

  configureCallbacks(callbacks: HttpClientCallbacks): void {
    this.callbacks = callbacks
    this.hasNotifiedUnauthorized = false
  }

  async get<T>(path: string): Promise<ApiResponse<T>> {
    return this.request<T>('GET', path)
  }

  async post<T>(path: string, body?: unknown): Promise<ApiResponse<T>> {
    return this.request<T>('POST', path, body)
  }

  async put<T>(path: string, body?: unknown): Promise<ApiResponse<T>> {
    return this.request<T>('PUT', path, body)
  }

  async delete<T>(path: string): Promise<ApiResponse<T>> {
    return this.request<T>('DELETE', path)
  }

  async getPage<T>(path: string, params: PageParams): Promise<ApiResponse<PageResponse<T>>> {
    const query = new URLSearchParams()
    query.set('page', String(params.page))
    query.set('page_size', String(params.page_size))
    const separator = path.includes('?') ? '&' : '?'
    return this.request<PageResponse<T>>('GET', `${path}${separator}${query.toString()}`)
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    hasRetried = false,
  ): Promise<ApiResponse<T>> {
    const headers: Record<string, string> = {
      Accept: 'application/json',
    }
    if (body !== undefined) {
      headers['Content-Type'] = 'application/json'
    }

    const token = this.callbacks.getToken?.()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    const roomId = this.callbacks.getCurrentRoomId?.()
    if (roomId) {
      headers['X-Current-Room-Id'] = String(roomId)
    }

    const init: RequestInit = {
      method,
      headers,
    }
    if (body !== undefined) {
      init.body = JSON.stringify(body)
    }

    let response: Response
    try {
      const doFetch = this.fetcher
      response = await doFetch(this.createUrl(path), init)
    } catch (err) {
      throw new NetworkError(
        err instanceof Error ? err.message : '网络连接失败，请检查网络',
      )
    }

    if (!response.ok) {
      if (response.status === 401) {
        const refreshed = !hasRetried && path !== '/auth/refresh' && await this.refreshAccessToken()
        if (refreshed) {
          return this.request<T>(method, path, body, true)
        }
        this.notifyUnauthorized()
      }
      throw await parseApiError(response)
    }

    const data: ApiResponse<T> = await response.json()
    if (data.code !== 'OK') {
      throw new ApiError(response.status, {
        code: data.code,
        message: data.message,
        trace_id: data.trace_id,
      })
    }

    return data
  }

  private async refreshAccessToken(): Promise<boolean> {
    if (!this.callbacks.refreshToken) return false
    if (!this.refreshPromise) {
      this.refreshPromise = this.callbacks.refreshToken()
        .catch(() => false)
        .finally(() => {
          this.refreshPromise = null
        })
    }
    const refreshed = await this.refreshPromise
    if (refreshed) this.hasNotifiedUnauthorized = false
    return refreshed
  }

  private notifyUnauthorized(): void {
    if (this.hasNotifiedUnauthorized) return
    this.hasNotifiedUnauthorized = true
    this.callbacks.onUnauthorized?.()
  }

  private createUrl(path: string): string {
    const normalizedBase = this.baseUrl.replace(/\/$/, '')
    const normalizedPath = path.startsWith('/') ? path : `/${path}`
    return `${normalizedBase}${normalizedPath}`
  }
}

export const httpClient = new HttpClient()

export function resolveErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError || err instanceof NetworkError) {
    return err.message || fallback
  }
  if (err && typeof err === 'object' && 'message' in err) {
    return String((err as { message: unknown }).message) || fallback
  }
  return fallback
}
