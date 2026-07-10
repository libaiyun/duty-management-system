import { describe, it, expect, beforeEach, vi } from 'vitest'

import { createAuthStore } from './helpers'
import { httpClient } from '@/services/http'
import { useAppStore } from '@/stores/app'
import { usePermissionStore } from '@/stores/permission'

const TOKEN_KEY = 'duty_access_token'
const REFRESH_TOKEN_KEY = 'duty_refresh_token'
const USER_KEY = 'duty_user_name'

describe('useAuthStore', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('isLoggedIn is false when no token', () => {
    const store = createAuthStore()
    expect(store.isLoggedIn).toBe(false)
  })

  it('isLoggedIn is true when token exists in localStorage', () => {
    localStorage.setItem(TOKEN_KEY, 'existing-token')
    const store = createAuthStore()
    expect(store.isLoggedIn).toBe(true)
  })

  it('login stores tokens on success', async () => {
    vi.spyOn(httpClient, 'post').mockResolvedValueOnce({
      code: 'OK',
      message: 'success',
      data: { access_token: 'at', refresh_token: 'rt', token_type: 'bearer' },
      trace_id: '',
    })
    vi.spyOn(httpClient, 'get').mockResolvedValueOnce({
      code: 'OK',
      message: 'success',
      data: { id: 1, username: 'admin', display_name: '管理员', status: 'enabled' },
      trace_id: '',
    })

    const store = createAuthStore()
    await store.login('admin', 'password123')

    expect(store.accessToken).toBe('at')
    expect(store.refreshToken).toBe('rt')
    expect(store.displayName).toBe('管理员')
    expect(localStorage.getItem(TOKEN_KEY)).toBe('at')
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe('rt')
    expect(localStorage.getItem(USER_KEY)).toBe('管理员')
  })

  it('logout clears state', async () => {
    vi.spyOn(httpClient, 'post').mockResolvedValueOnce({
      code: 'OK',
      message: 'success',
      data: null,
      trace_id: '',
    })
    localStorage.setItem(TOKEN_KEY, 'at')
    localStorage.setItem(USER_KEY, 'test')

    const store = createAuthStore()
    store.accessToken = 'at'
    store.refreshToken = 'rt'
    store.displayName = 'test'

    await store.logout()

    expect(store.accessToken).toBe('')
    expect(store.refreshToken).toBe('')
    expect(store.displayName).toBe('')
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(USER_KEY)).toBeNull()
  })

  it('logout clears state even when server call fails', async () => {
    vi.spyOn(httpClient, 'post').mockRejectedValueOnce(new Error('network'))
    localStorage.setItem(TOKEN_KEY, 'at')

    const store = createAuthStore()
    store.accessToken = 'at'

    await store.logout()

    expect(store.accessToken).toBe('')
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('forceLogout clears state', () => {
    localStorage.setItem(TOKEN_KEY, 'at')
    const store = createAuthStore()
    store.accessToken = 'at'

    store.forceLogout()

    expect(store.accessToken).toBe('')
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('restoreSession sets app store userName', () => {
    localStorage.setItem(USER_KEY, '张三')
    const store = createAuthStore()
    store.displayName = '张三'
    store.accessToken = 'at'

    store.restoreSession()

    const appStore = useAppStore()
    expect(appStore.userName).toBe('张三')
  })

  it('forceLogout clears permission store', () => {
    const store = createAuthStore()
    store.forceLogout()

    const permStore = usePermissionStore()
    expect(permStore.permissions.size).toBe(0)
  })
})
