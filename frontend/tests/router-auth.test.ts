import { describe, it, expect, beforeEach } from 'vitest'

import { createAuthStore } from './helpers'
import { router } from '@/router'

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
