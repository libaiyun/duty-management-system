import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useAppStore } from '@/stores/app'

describe('useAppStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('has default system name', () => {
    const store = useAppStore()
    expect(store.systemName).toBe('广播电视台站值班管理系统')
  })

  it('starts with sidebar expanded', () => {
    const store = useAppStore()
    expect(store.sidebarCollapsed).toBe(false)
  })

  it('toggles sidebar collapse', () => {
    const store = useAppStore()
    store.toggleSidebar()
    expect(store.sidebarCollapsed).toBe(true)
    store.toggleSidebar()
    expect(store.sidebarCollapsed).toBe(false)
  })

  it('has default user placeholder values', () => {
    const store = useAppStore()
    expect(store.userName).toBe('管理员')
    expect(store.notificationCount).toBe(0)
    expect(store.userAvatar).toBe('')
  })
})
