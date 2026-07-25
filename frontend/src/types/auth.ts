export interface LoginRequest {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface UserMeResponse {
  id: number
  username: string
  display_name: string
  status: string
  permissions: string[]
  person_id: number | null
  person_status: string | null
  person_type: string | null
  participate_schedule: boolean
  is_superuser: boolean
  room_id: number | null
  room_name: string | null
  can_switch_room: boolean
}
