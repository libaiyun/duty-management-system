import type { ApiResponse } from '@/types/api'

export interface HttpClientOptions {
  baseUrl?: string
  fetcher?: typeof fetch
}

export class HttpClient {
  private readonly baseUrl: string
  private readonly fetcher: typeof fetch

  constructor(options: HttpClientOptions = {}) {
    this.baseUrl = options.baseUrl ?? import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
    this.fetcher = options.fetcher ?? fetch
  }

  async get<T>(path: string): Promise<ApiResponse<T>> {
    const response = await this.fetcher(this.createUrl(path), {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    })
    return response.json() as Promise<ApiResponse<T>>
  }

  private createUrl(path: string): string {
    const normalizedBase = this.baseUrl.replace(/\/$/, '')
    const normalizedPath = path.startsWith('/') ? path : `/${path}`
    return `${normalizedBase}${normalizedPath}`
  }
}

export const httpClient = new HttpClient()
