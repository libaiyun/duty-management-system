import { describe, expect, it } from 'vitest'

import { router } from '@/router'

describe('router', () => {
  it('defines the home route', () => {
    const route = router.getRoutes().find((item) => item.name === 'home')

    expect(route?.path).toBe('/')
    expect(route?.meta.title).toBe('工作台')
  })
})
