import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { router as appRouter } from '@/router'
import AccountRoleView from '@/views/system/AccountRoleView.vue'

const { get } = vi.hoisted(() => ({ get: vi.fn().mockResolvedValue({ data: [] }) }))

vi.mock('@/services/http', () => ({
  httpClient: { get, post: vi.fn(), put: vi.fn() },
}))

describe('AccountRoleView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockClear()
  })

  it('loads global binding persons from the dedicated endpoint', async () => {
    mount(AccountRoleView, { global: { plugins: [appRouter, ElementPlus] } })
    await vi.waitFor(() => expect(get).toHaveBeenCalledWith('/users/persons'))
    expect(get).not.toHaveBeenCalledWith('/persons')
    expect(get).not.toHaveBeenCalledWith('/permissions')
  })
})
