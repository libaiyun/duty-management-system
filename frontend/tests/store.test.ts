import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useAppStore } from '@/stores/app'

describe('useAppStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('stores shell state and toggles sidebar collapse', () => {
    const store = useAppStore()

    expect(store.systemName).toBe('广播电视台站值班管理系统')
    expect(store.sidebarCollapsed).toBe(false)

    store.toggleSidebar()

    expect(store.sidebarCollapsed).toBe(true)
  })
})
