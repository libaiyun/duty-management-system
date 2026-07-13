import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import { menuItems } from '@/config/menu'
import type { MenuItem } from '@/types/menu'
import type { PermissionCode } from '@/types/permission'
import { useAuthStore } from '@/stores/auth'
import { usePermissionStore } from '@/stores/permission'
import ForbiddenView from '@/views/ForbiddenView.vue'
import HomeView from '@/views/HomeView.vue'
import LoginView from '@/views/LoginView.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import PlaceholderView from '@/views/PlaceholderView.vue'

const CUSTOM_VIEWS: Record<string, unknown> = {
  home: HomeView,
  'account-role': () => import('@/views/system/AccountRoleView.vue'),
  'org-unit': () => import('@/views/base-data/OrgUnitView.vue'),
  person: () => import('@/views/base-data/PersonView.vue'),
  'shift-rule': () => import('@/views/base-data/ShiftRuleView.vue'),
}

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
      component: CUSTOM_VIEWS[item.name] ?? PlaceholderView,
      meta,
    }
  })
}

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { title: '登录' },
    },
    ...buildRoutes(menuItems),
    {
      path: '/403',
      name: 'forbidden',
      component: ForbiddenView,
      meta: { title: '无权访问' },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: NotFoundView,
      meta: { title: '页面不存在' },
    },
  ],
})

const PUBLIC_ROUTES = new Set(['login', 'forbidden', 'not-found'])

router.beforeEach((to, _from, next) => {
  if (PUBLIC_ROUTES.has(to.name as string)) {
    next()
    return
  }

  const authStore = useAuthStore()
  if (!authStore.isLoggedIn) {
    next({ name: 'login', query: { redirect: to.fullPath } })
    return
  }

  const permission = to.meta.permission as PermissionCode | undefined
  if (permission && !usePermissionStore().hasPermission(permission)) {
    next({ name: 'forbidden' })
    return
  }

  next()
})
