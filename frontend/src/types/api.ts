export interface ApiResponse<T> {
  code: string
  message: string
  data: T
  trace_id: string
}
