import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { usePermissionStore } from '@/stores/permission'
import { PERMISSION_CODES } from '@/types/permission'

describe('usePermissionStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with all permissions by default', () => {
    const store = usePermissionStore()
    expect(store.hasPermission(PERMISSION_CODES.SYSTEM_USER_MANAGE)).toBe(true)
    expect(store.hasPermission(PERMISSION_CODES.DUTY_SCHEDULE_VIEW_SELF)).toBe(true)
  })

  it('can set specific permissions', () => {
    const store = usePermissionStore()
    store.setPermissions([PERMISSION_CODES.DUTY_SCHEDULE_VIEW_SELF])

    expect(store.hasPermission(PERMISSION_CODES.DUTY_SCHEDULE_VIEW_SELF)).toBe(true)
    expect(store.hasPermission(PERMISSION_CODES.SYSTEM_USER_MANAGE)).toBe(false)
  })

  it('can clear all permissions', () => {
    const store = usePermissionStore()
    store.clearPermissions()

    expect(store.hasPermission(PERMISSION_CODES.DUTY_SCHEDULE_VIEW_SELF)).toBe(false)
    expect(store.hasPermission(PERMISSION_CODES.SYSTEM_USER_MANAGE)).toBe(false)
  })

  it('hasPermission returns false for unknown codes', () => {
    const store = usePermissionStore()
    store.clearPermissions()

    expect(store.hasPermission(PERMISSION_CODES.SYSTEM_LOG_VIEW)).toBe(false)
  })
})
