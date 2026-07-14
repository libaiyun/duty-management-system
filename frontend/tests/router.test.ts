import { describe, expect, it } from 'vitest'

import { router } from '@/router'

describe('router', () => {
  it('defines the home route as top-level', () => {
    const route = router.getRoutes().find((item) => item.name === 'home')
    expect(route?.path).toBe('/')
    expect(route?.meta.title).toBe('工作台')
  })

  it('defines the revised flat schedule-table route', () => {
    const route = router.getRoutes().find((item) => item.name === 'schedule-table')
    expect(route?.path).toBe('/schedule-mgmt/table')
    expect(route?.meta.title).toBe('排班表')
  })

  it('all leaf routes have a component', () => {
    const routes = router.getRoutes()
    const leafRoutes = routes.filter((r) => r.name && !r.children)
    for (const route of leafRoutes) {
      expect(route.components?.default).toBeDefined()
    }
  })

  it('all routes have meta title', () => {
    const routes = router.getRoutes()
    for (const route of routes) {
      if (!route.name) continue
      expect(route.meta.title).toBeTruthy()
    }
  })

  it('has a 403 route', () => {
    const forbidden = router.getRoutes().find((r) => r.name === 'forbidden')
    expect(forbidden).toBeDefined()
    expect(forbidden?.path).toBe('/403')
    expect(forbidden?.meta.title).toBe('无权访问')
  })

  it('non-home leaf routes have permission code assigned', () => {
    const routes = router.getRoutes()
    const leafRoutes = routes.filter((r) => r.name && !r.children && r.name !== 'home' && r.name !== 'forbidden' && r.name !== 'not-found')
    for (const route of leafRoutes) {
      expect(route.meta.permission).toBeDefined()
    }
  })

  it('has a catch-all route for unknown paths', () => {
    const notFound = router.getRoutes().find((r) => r.name === 'not-found')
    expect(notFound).toBeDefined()
    expect(notFound?.path).toBe('/:pathMatch(.*)*')
    expect(notFound?.meta.permission).toBeUndefined()
  })
})
