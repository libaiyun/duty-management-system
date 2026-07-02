import { createRouter, createWebHistory } from 'vue-router'
import type { RouteLocationNormalized, RouteRecordRaw } from 'vue-router'

import { menuItems } from '@/config/menu'
import type { MenuItem } from '@/types/menu'
import type { PermissionCode } from '@/types/permission'
import { usePermissionStore } from '@/stores/permission'
import ForbiddenView from '@/views/ForbiddenView.vue'
import HomeView from '@/views/HomeView.vue'
import PlaceholderView from '@/views/PlaceholderView.vue'

function buildRoutes(items: MenuItem[]): RouteRecordRaw[] {
  return items.map((item): RouteRecordRaw => {
    if (item.children && item.children.length > 0) {
      return {
        path: item.path,
        name: item.name,
        meta: { title: item.title },
        redirect: item.children[0].path,
        children: buildRoutes(item.children),
      }
    }
    const meta: { title: string; permission?: PermissionCode } = { title: item.title }
    if (item.permission) {
      meta.permission = item.permission
    }
    return {
      path: item.path,
      name: item.name,
      component: item.name === 'home' ? HomeView : PlaceholderView,
      meta,
    }
  })
}

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    ...buildRoutes(menuItems),
    {
      path: '/403',
      name: 'forbidden',
      component: ForbiddenView,
      meta: { title: '无权访问' },
    },
  ],
})

function getPermissionStore() {
  return usePermissionStore()
}

function checkRoutePermission(to: RouteLocationNormalized): boolean {
  const permission = to.meta.permission as PermissionCode | undefined
  if (!permission) return true
  return getPermissionStore().hasPermission(permission)
}

router.beforeEach((to, _from, next) => {
  if (!checkRoutePermission(to)) {
    next({ name: 'forbidden' })
    return
  }
  next()
})
