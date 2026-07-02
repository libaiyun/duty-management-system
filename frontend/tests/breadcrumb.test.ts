import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import { describe, expect, it } from 'vitest'

import { useBreadcrumb } from '@/composables/useBreadcrumb'

async function createTestRouter() {
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      {
        path: '/',
        name: 'home',
        component: { template: '<div />' },
        meta: { title: '工作台' },
      },
      {
        path: '/my-duty',
        name: 'my-duty',
        meta: { title: '我的值班' },
        redirect: '/my-duty/schedule',
        children: [
          {
            path: 'schedule',
            name: 'my-schedule',
            component: { template: '<div />' },
            meta: { title: '我的排班' },
          },
        ],
      },
    ],
  })
  await router.push('/')
  await router.isReady()
  return router
}

describe('useBreadcrumb', () => {
  it('returns single breadcrumb for top-level route', async () => {
    const router = await createTestRouter()
    const app = createApp({
      setup() {
        return useBreadcrumb()
      },
      template: '<div></div>',
    })
    app.use(router)
    const el = document.createElement('div')
    const instance = app.mount(el)

    expect((instance as unknown as Record<string, unknown>).breadcrumbs).toEqual([
      { title: '工作台', path: '/' },
    ])
    app.unmount()
  })

  it('returns multi-level breadcrumb for nested route', async () => {
    const router = await createTestRouter()
    await router.push('/my-duty/schedule')

    const app = createApp({
      setup() {
        return useBreadcrumb()
      },
      template: '<div></div>',
    })
    app.use(router)
    const el = document.createElement('div')
    const instance = app.mount(el)

    expect((instance as unknown as Record<string, unknown>).breadcrumbs).toEqual([
      { title: '我的值班', path: '/my-duty' },
      { title: '我的排班', path: '/my-duty/schedule' },
    ])
    app.unmount()
  })
})
