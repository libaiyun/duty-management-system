import {
  Calendar,
  Clock,
  Coin,
  DataAnalysis,
  Document,
  Grid,
  List,
  Monitor,
  Setting,
  UserFilled,
} from '@element-plus/icons-vue'

import type { MenuItem } from '@/types/menu'

export const menuItems: MenuItem[] = [
  {
    name: 'home',
    path: '/',
    title: '工作台',
    icon: Monitor,
  },
  {
    name: 'my-duty',
    path: '/my-duty',
    title: '我的值班',
    icon: Calendar,
    children: [
      { name: 'my-schedule', path: '/my-duty/schedule', title: '我的排班' },
      { name: 'my-swap', path: '/my-duty/swap', title: '我的换班' },
      { name: 'my-leave', path: '/my-duty/leave', title: '我的请假' },
      { name: 'my-cover', path: '/my-duty/cover', title: '我的顶班' },
    ],
  },
  {
    name: 'approval',
    path: '/approval',
    title: '审批中心',
    icon: Document,
    children: [
      { name: 'approval-todo', path: '/approval/todo', title: '待办审批' },
      { name: 'approval-done', path: '/approval/done', title: '已办审批' },
    ],
  },
  {
    name: 'schedule-mgmt',
    path: '/schedule-mgmt',
    title: '排班管理',
    icon: Grid,
    children: [
      { name: 'monthly-schedule', path: '/schedule-mgmt/monthly', title: '月度排班' },
      { name: 'schedule-detail', path: '/schedule-mgmt/detail', title: '排班明细' },
      { name: 'actual-duty', path: '/schedule-mgmt/actual', title: '实际值班' },
    ],
  },
  {
    name: 'leave-cover',
    path: '/leave-cover',
    title: '请假顶班',
    icon: Clock,
    children: [
      { name: 'leave-records', path: '/leave-cover/records', title: '请假记录' },
      { name: 'cover-arrange', path: '/leave-cover/arrange', title: '顶班安排' },
    ],
  },
  {
    name: 'refund',
    path: '/refund',
    title: '退费管理',
    icon: Coin,
    children: [
      { name: 'refund-calc', path: '/refund/calc', title: '退费计算' },
      { name: 'refund-detail', path: '/refund/detail', title: '退费明细' },
    ],
  },
  {
    name: 'attendance',
    path: '/attendance',
    title: '考勤报表',
    icon: DataAnalysis,
    children: [
      { name: 'monthly-attendance', path: '/attendance/monthly', title: '月度考勤' },
      { name: 'export-history', path: '/attendance/export', title: '导出历史' },
    ],
  },
  {
    name: 'base-data',
    path: '/base-data',
    title: '基础资料',
    icon: List,
    children: [
      { name: 'org-unit', path: '/base-data/org-unit', title: '台站机房' },
      { name: 'person', path: '/base-data/person', title: '人员管理' },
      { name: 'shift-rule', path: '/base-data/shift-rule', title: '班次规则' },
      { name: 'holiday-standard', path: '/base-data/holiday', title: '节假日与标准' },
    ],
  },
  {
    name: 'system',
    path: '/system',
    title: '系统管理',
    icon: Setting,
    children: [
      { name: 'account-role', path: '/system/account-role', title: '账号角色' },
      { name: 'operation-log', path: '/system/operation-log', title: '操作日志' },
      { name: 'backup-archive', path: '/system/backup-archive', title: '备份归档' },
    ],
  },
]

export function collectRoutes(menus: MenuItem[]): MenuItem[] {
  const result: MenuItem[] = []
  for (const item of menus) {
    result.push(item)
    if (item.children) {
      result.push(...item.children)
    }
  }
  return result
}
