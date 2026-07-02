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
} from '@element-plus/icons-vue'

import type { MenuItem } from '@/types/menu'
import type { PermissionCode } from '@/types/permission'
import { PERMISSION_CODES } from '@/types/permission'

const PC = PERMISSION_CODES

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
      { name: 'my-schedule', path: '/my-duty/schedule', title: '我的排班', permission: PC.DUTY_SCHEDULE_VIEW_SELF },
      { name: 'my-swap', path: '/my-duty/swap', title: '我的换班', permission: PC.DUTY_SWAP_VIEW_SELF },
      { name: 'my-leave', path: '/my-duty/leave', title: '我的请假', permission: PC.DUTY_LEAVE_VIEW_SELF },
      { name: 'my-cover', path: '/my-duty/cover', title: '我的顶班', permission: PC.DUTY_COVER_VIEW_SELF },
    ],
  },
  {
    name: 'approval',
    path: '/approval',
    title: '审批中心',
    icon: Document,
    children: [
      { name: 'approval-todo', path: '/approval/todo', title: '待办审批', permission: PC.APPROVAL_TASK_VIEW_TODO },
      { name: 'approval-done', path: '/approval/done', title: '已办审批', permission: PC.APPROVAL_RECORD_VIEW_DONE },
    ],
  },
  {
    name: 'schedule-mgmt',
    path: '/schedule-mgmt',
    title: '排班管理',
    icon: Grid,
    children: [
      { name: 'monthly-schedule', path: '/schedule-mgmt/monthly', title: '月度排班', permission: PC.SCHEDULE_MONTHLY_VIEW },
      { name: 'schedule-detail', path: '/schedule-mgmt/detail', title: '排班明细', permission: PC.SCHEDULE_DETAIL_VIEW },
      { name: 'actual-duty', path: '/schedule-mgmt/actual', title: '实际值班', permission: PC.DUTY_ACTUAL_VIEW },
    ],
  },
  {
    name: 'leave-cover',
    path: '/leave-cover',
    title: '请假顶班',
    icon: Clock,
    children: [
      { name: 'leave-records', path: '/leave-cover/records', title: '请假记录', permission: PC.LEAVE_RECORD_VIEW },
      { name: 'cover-arrange', path: '/leave-cover/arrange', title: '顶班安排', permission: PC.COVER_ASSIGNMENT_VIEW },
    ],
  },
  {
    name: 'refund',
    path: '/refund',
    title: '退费管理',
    icon: Coin,
    children: [
      { name: 'refund-calc', path: '/refund/calc', title: '退费计算', permission: PC.REFUND_BATCH_CALCULATE },
      { name: 'refund-detail', path: '/refund/detail', title: '退费明细', permission: PC.REFUND_DETAIL_VIEW },
    ],
  },
  {
    name: 'attendance',
    path: '/attendance',
    title: '考勤报表',
    icon: DataAnalysis,
    children: [
      { name: 'monthly-attendance', path: '/attendance/monthly', title: '月度考勤', permission: PC.ATTENDANCE_MONTHLY_VIEW },
      { name: 'export-history', path: '/attendance/export', title: '导出历史', permission: PC.EXPORT_TASK_VIEW },
    ],
  },
  {
    name: 'base-data',
    path: '/base-data',
    title: '基础资料',
    icon: List,
    children: [
      { name: 'org-unit', path: '/base-data/org-unit', title: '台站机房', permission: PC.ORG_UNIT_VIEW },
      { name: 'person', path: '/base-data/person', title: '人员管理', permission: PC.PERSON_MANAGE_VIEW },
      { name: 'shift-rule', path: '/base-data/shift-rule', title: '班次规则', permission: PC.SHIFT_RULE_VIEW },
      { name: 'holiday-standard', path: '/base-data/holiday', title: '节假日与标准', permission: PC.HOLIDAY_STANDARD_VIEW },
    ],
  },
  {
    name: 'system',
    path: '/system',
    title: '系统管理',
    icon: Setting,
    children: [
      { name: 'account-role', path: '/system/account-role', title: '账号角色', permission: PC.SYSTEM_USER_MANAGE },
      { name: 'operation-log', path: '/system/operation-log', title: '操作日志', permission: PC.SYSTEM_LOG_VIEW },
      { name: 'backup-archive', path: '/system/backup-archive', title: '备份归档', permission: PC.SYSTEM_BACKUP_VIEW },
    ],
  },
]

export function filterMenuByPermission(
  menus: MenuItem[],
  hasPermission: (code: PermissionCode) => boolean,
): MenuItem[] {
  return menus
    .map((item) => {
      if (item.children) {
        const visibleChildren = item.children.filter(
          (child) => !child.permission || hasPermission(child.permission),
        )
        if (visibleChildren.length === 0) return null
        return { ...item, children: visibleChildren }
      }
      if (item.permission && !hasPermission(item.permission)) return null
      return item
    })
    .filter((item): item is MenuItem => item !== null)
}
