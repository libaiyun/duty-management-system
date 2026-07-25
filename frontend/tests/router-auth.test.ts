import { describe, it, expect, beforeEach, vi } from 'vitest'

import { createAuthStore } from './helpers'
import { router } from '@/router'
import { httpClient } from '@/services/http'

describe('router auth guard', () => {
  beforeEach(() => {
    const store = createAuthStore()
    store.forceLogout()
  })

  it('/login route exists', () => {
    const route = router.resolve({ name: 'login' })
    expect(route.name).toBe('login')
  })

  it('unauthenticated user is redirected to /login', async () => {
    await router.push('/schedule-mgmt/table')
    expect(router.currentRoute.value.name).toBe('login')
  })

  it('unauthenticated user can access /login', async () => {
    await router.push('/login')
    expect(router.currentRoute.value.name).toBe('login')
  })

  it('redirect query is set when redirecting to login', async () => {
    await router.push('/schedule-mgmt/table')
    expect(router.currentRoute.value.query.redirect).toBe('/schedule-mgmt/table')
  })

  it('authenticated user can access protected route', async () => {
    const store = createAuthStore()
    store.accessToken = 'valid-token'
    await router.push('/')
    expect(router.currentRoute.value.name).toBe('home')
  })

  it('restores the session before authorizing a protected route after refresh', async () => {
    const store = createAuthStore()
    store.accessToken = 'valid-token'
    vi.spyOn(httpClient, 'get').mockResolvedValueOnce({
      code: 'OK', message: 'success', trace_id: '',
      data: {
        id: 1, username: 'operator', display_name: '值班员', status: 'enabled',
        permissions: ['schedule:monthly:view'],
        person_id: 1, person_status: 'enabled', person_type: 'duty_operator',
        participate_schedule: true, is_superuser: false,
        room_id: 1, room_name: '发射机房', can_switch_room: false,
      },
    })

    await router.push('/schedule-mgmt/table')

    expect(router.currentRoute.value.name).toBe('schedule-table')
  })

  it('authenticated user can access /login', async () => {
    const store = createAuthStore()
    store.accessToken = 'valid-token'
    await router.push('/login')
    expect(router.currentRoute.value.name).toBe('login')
  })

  it('forbidden route is public', async () => {
    await router.push('/403')
    expect(router.currentRoute.value.name).toBe('forbidden')
  })

  it('not-found route is public', async () => {
    await router.push('/nonexistent')
    expect(router.currentRoute.value.name).toBe('not-found')
  })
})
