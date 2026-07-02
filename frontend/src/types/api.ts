export interface ApiResponse<T> {
  code: string
  message: string
  data: T
  trace_id: string
}

export interface ApiErrorDetail {
  field: string
  message: string
}

export interface ErrorResponse {
  code: string
  message: string
  trace_id: string
  details?: ApiErrorDetail[]
}

export interface PageParams {
  page: number
  page_size: number
}

export interface PageResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
