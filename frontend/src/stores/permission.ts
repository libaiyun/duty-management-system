import { defineStore } from 'pinia'

import { ALL_PERMISSIONS } from '@/types/permission'
import type { PermissionCode } from '@/types/permission'

export const usePermissionStore = defineStore('permission', {
  state: () => ({
    permissions: new Set<PermissionCode>(ALL_PERMISSIONS),
  }),

  getters: {
    hasPermission: (state) => {
      return (code: PermissionCode): boolean => state.permissions.has(code)
    },
  },

  actions: {
    setPermissions(codes: PermissionCode[]): void {
      this.permissions = new Set(codes)
    },

    clearPermissions(): void {
      this.permissions = new Set()
    },
  },
})
