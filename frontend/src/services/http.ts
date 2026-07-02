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
  private readonly callbacks: HttpClientCallbacks

  constructor(options: HttpClientOptions = {}) {
    this.baseUrl = options.baseUrl ?? import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
    this.fetcher = options.fetcher ?? fetch
    this.callbacks = options.callbacks ?? {}
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

  private async request<T>(method: string, path: string, body?: unknown): Promise<ApiResponse<T>> {
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

    const init: RequestInit = {
      method,
      headers,
    }
    if (body !== undefined) {
      init.body = JSON.stringify(body)
    }

    let response: Response
    try {
      response = await this.fetcher(this.createUrl(path), init)
    } catch (err) {
      throw new NetworkError(
        err instanceof Error ? err.message : '网络连接失败，请检查网络',
      )
    }

    if (!response.ok) {
      if (response.status === 401) {
        this.callbacks.onUnauthorized?.()
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

  private createUrl(path: string): string {
    const normalizedBase = this.baseUrl.replace(/\/$/, '')
    const normalizedPath = path.startsWith('/') ? path : `/${path}`
    return `${normalizedBase}${normalizedPath}`
  }
}

export const httpClient = new HttpClient()
