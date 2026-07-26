import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import { menuItems } from '@/config/menu'
import type { MenuItem, PersonalAccess } from '@/types/menu'
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
  'schedule-rule': () => import('@/views/base-data/ShiftRuleView.vue'),
  'shift-def': () => import('@/views/base-data/ShiftDefView.vue'),
  'holiday-standard': () => import('@/views/base-data/HolidayView.vue'),
  'schedule-table': () => import('@/views/schedule/ScheduleTableView.vue'),
  'actual-duty': () => import('@/views/schedule/ActualDutyView.vue'),
  'export-history': () => import('@/views/schedule/ExportHistoryView.vue'),
  'approval-center': () => import('@/views/approval/ApprovalCenterView.vue'),
  'swap-request': () => import('@/views/swap/ShiftSwapView.vue'),
  'leave-request': () => import('@/views/leave/LeaveRequestView.vue'),
  'my-cover': () => import('@/views/leave/MyCoverView.vue'),
  'leave-records': () => import('@/views/leave/LeaveRecordView.vue'),
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
    const meta: { title: string; permission?: PermissionCode; personalAccess?: PersonalAccess } = { title: item.title }
    if (item.permission) {
      meta.permission = item.permission
    }
    if (item.personalAccess) {
      meta.personalAccess = item.personalAccess
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

interface RouteAccessState {
  requiresPermission: boolean
  permissionsLoaded: boolean
  permissionGranted: boolean
  personalAccessGranted: boolean
}

export function hasRouteAccess(state: RouteAccessState): boolean {
  return state.personalAccessGranted
    || (state.requiresPermission && state.permissionsLoaded && state.permissionGranted)
}

router.beforeEach(async (to) => {
  if (PUBLIC_ROUTES.has(to.name as string)) {
    return true
  }

  const authStore = useAuthStore()
  if (!authStore.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  const permission = to.meta.permission as PermissionCode | undefined
  const personalAccess = to.meta.personalAccess as PersonalAccess | undefined
  if (permission || personalAccess) {
    const permStore = usePermissionStore()
    if (!permStore.loaded) {
      await authStore.restoreSession()
    }

    if (!authStore.isLoggedIn) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }

    const bound = authStore.personId !== null && authStore.personStatus === 'enabled'
    const hasPersonalAccess = personalAccess === 'bound'
      ? bound
      : personalAccess === 'participating_operator'
        ? bound && authStore.personType === 'duty_operator' && authStore.participateSchedule
        : personalAccess === 'cover_eligible'
          ? bound && ['maintenance', 'room_director', 'deputy_director'].includes(authStore.personType || '')
          : false
    if (!hasRouteAccess({
      requiresPermission: Boolean(permission),
      permissionsLoaded: permStore.loaded,
      permissionGranted: Boolean(permission && permStore.hasPermission(permission)),
      personalAccessGranted: hasPersonalAccess,
    })) {
      return { name: 'forbidden' }
    }
  }

  return true
})
