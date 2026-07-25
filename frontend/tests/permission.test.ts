import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { usePermissionStore } from '@/stores/permission'
import { PERMISSION_CODES } from '@/types/permission'

describe('usePermissionStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with empty permissions by default', () => {
    const store = usePermissionStore()
    expect(store.hasPermission(PERMISSION_CODES.SYSTEM_USER_MANAGE)).toBe(false)
    expect(store.hasPermission(PERMISSION_CODES.SCHEDULE_MONTHLY_VIEW)).toBe(false)
  })

  it('can set specific permissions', () => {
    const store = usePermissionStore()
    store.setPermissions([PERMISSION_CODES.SCHEDULE_MONTHLY_VIEW])

    expect(store.hasPermission(PERMISSION_CODES.SCHEDULE_MONTHLY_VIEW)).toBe(true)
    expect(store.hasPermission(PERMISSION_CODES.SYSTEM_USER_MANAGE)).toBe(false)
  })

  it('can clear all permissions', () => {
    const store = usePermissionStore()
    store.clearPermissions()

    expect(store.hasPermission(PERMISSION_CODES.SCHEDULE_MONTHLY_VIEW)).toBe(false)
    expect(store.hasPermission(PERMISSION_CODES.SYSTEM_USER_MANAGE)).toBe(false)
  })

  it('hasPermission returns false for unknown codes', () => {
    const store = usePermissionStore()
    store.clearPermissions()

    expect(store.hasPermission(PERMISSION_CODES.SYSTEM_LOG_VIEW)).toBe(false)
  })
})
