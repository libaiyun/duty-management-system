import type { Component } from 'vue'

import type { PermissionCode } from '@/types/permission'

export interface MenuItem {
  name: string
  path: string
  title: string
  icon?: Component
  permission?: PermissionCode
  children?: MenuItem[]
}
