import type { Component } from 'vue'

import type { PermissionCode } from '@/types/permission'

export type PersonalAccess = 'bound' | 'participating_operator' | 'cover_eligible'

export interface MenuItem {
  name: string
  path: string
  title: string
  icon?: Component
  permission?: PermissionCode
  personalAccess?: PersonalAccess
  children?: MenuItem[]
}
