import { defineStore } from 'pinia'

import { httpClient } from '@/services/http'
import type { LoginRequest, TokenResponse, UserMeResponse } from '@/types/auth'
import { useAppStore } from '@/stores/app'
import { usePermissionStore } from '@/stores/permission'
import { useRoomContextStore } from '@/stores/room-context'
import type { PermissionCode } from '@/types/permission'

const TOKEN_KEY = 'duty_access_token'
const REFRESH_TOKEN_KEY = 'duty_refresh_token'
const USER_KEY = 'duty_user_name'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: localStorage.getItem(TOKEN_KEY) || '',
    refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY) || '',
    username: '',
    displayName: localStorage.getItem(USER_KEY) || '',
    personId: null as number | null,
    roomId: null as number | null,
    roomName: '',
    canSwitchRoom: false,
    roleCodes: [] as string[],
  }),

  getters: {
    isLoggedIn: (state): boolean => !!state.accessToken,
  },

  actions: {
    async login(username: string, password: string): Promise<void> {
      const resp = await httpClient.post<TokenResponse>('/auth/login', {
        username,
        password,
      } satisfies LoginRequest)

      const tokens = resp.data
      this.accessToken = tokens.access_token
      this.refreshToken = tokens.refresh_token
      localStorage.setItem(TOKEN_KEY, tokens.access_token)
      localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)

      const meResp = await httpClient.get<UserMeResponse>('/auth/me')
      const user = meResp.data
      this.username = user.username
      this.displayName = user.display_name
      this.personId = user.person_id
      this.roomId = user.room_id
      this.roomName = user.room_name || ''
      this.canSwitchRoom = user.can_switch_room
      this.roleCodes = user.role_codes
      localStorage.setItem(USER_KEY, user.display_name)

      const appStore = useAppStore()
      appStore.userName = user.display_name

      const permStore = usePermissionStore()
      permStore.setPermissions(user.permissions as PermissionCode[])

      if (this.canSwitchRoom) {
        await useRoomContextStore().loadRooms()
      }
    },

    async logout(): Promise<void> {
      try {
        await httpClient.post('/auth/logout')
      } catch {
        // 即使服务端登出失败，本地仍清除登录状态
      }
      this._clearAuthState()
    },

    async restoreSession(): Promise<void> {
      if (!this.accessToken) return
      const appStore = useAppStore()
      appStore.userName = this.displayName

      try {
        const meResp = await httpClient.get<UserMeResponse>('/auth/me')
        const user = meResp.data
        this.username = user.username
        this.displayName = user.display_name
        this.personId = user.person_id
        this.roomId = user.room_id
        this.roomName = user.room_name || ''
        this.canSwitchRoom = user.can_switch_room
        this.roleCodes = user.role_codes
        localStorage.setItem(USER_KEY, user.display_name)
        appStore.userName = user.display_name

        const permStore = usePermissionStore()
        permStore.setPermissions(user.permissions as PermissionCode[])

        if (this.canSwitchRoom) {
          await useRoomContextStore().loadRooms()
        }
      } catch {
        // The HTTP client handles failed token refreshes by forcing logout and redirecting.
        // on other errors, permissions remain empty → 403/limited menu (visible feedback)
      }
    },

    async refreshAccessToken(): Promise<boolean> {
      if (!this.refreshToken) return false

      try {
        const response = await httpClient.post<TokenResponse>('/auth/refresh', {
          refresh_token: this.refreshToken,
        })
        const tokens = response.data
        this.accessToken = tokens.access_token
        this.refreshToken = tokens.refresh_token
        localStorage.setItem(TOKEN_KEY, tokens.access_token)
        localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)
        return true
      } catch {
        return false
      }
    },

    forceLogout(): void {
      this._clearAuthState()
    },

    _clearAuthState(): void {
      this.accessToken = ''
      this.refreshToken = ''
      this.username = ''
      this.displayName = ''
      this.personId = null
      this.roomId = null
      this.roomName = ''
      this.canSwitchRoom = false
      this.roleCodes = []
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(REFRESH_TOKEN_KEY)
      localStorage.removeItem(USER_KEY)

      const appStore = useAppStore()
      appStore.userName = ''

      const permStore = usePermissionStore()
      permStore.clearPermissions()

      const roomContextStore = useRoomContextStore()
      roomContextStore.clear()
    },
  },
})
