import { defineStore } from 'pinia'

import { httpClient } from '@/services/http'
import type { LoginRequest, TokenResponse, UserMeResponse } from '@/types/auth'
import { useAppStore } from '@/stores/app'
import { usePermissionStore } from '@/stores/permission'
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
      localStorage.setItem(USER_KEY, user.display_name)

      const appStore = useAppStore()
      appStore.userName = user.display_name

      const permStore = usePermissionStore()
      permStore.setPermissions(user.permissions as PermissionCode[])
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
        localStorage.setItem(USER_KEY, user.display_name)
        appStore.userName = user.display_name

        const permStore = usePermissionStore()
        permStore.setPermissions(user.permissions as PermissionCode[])
      } catch {
        // on 401, onUnauthorized callback in main.ts handles forceLogout + redirect
        // on other errors, permissions remain empty → 403/limited menu (visible feedback)
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
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(REFRESH_TOKEN_KEY)
      localStorage.removeItem(USER_KEY)

      const appStore = useAppStore()
      appStore.userName = ''

      const permStore = usePermissionStore()
      permStore.clearPermissions()
    },
  },
})
