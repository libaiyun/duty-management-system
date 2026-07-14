import { defineStore } from 'pinia'

import type { PermissionCode } from '@/types/permission'

export const usePermissionStore = defineStore('permission', {
  state: () => ({
    loaded: false,
    permissions: new Set<PermissionCode>(),
  }),

  getters: {
    hasPermission: (state) => {
      return (code: PermissionCode): boolean => state.permissions.has(code)
    },
  },

  actions: {
    setPermissions(codes: PermissionCode[]): void {
      this.permissions = new Set(codes)
      this.loaded = true
    },

    clearPermissions(): void {
      this.permissions = new Set()
      this.loaded = false
    },
  },
})
