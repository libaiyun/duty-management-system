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
    name: 'schedule-table',
    path: '/schedule-mgmt/table',
    title: '排班表',
    icon: Calendar,
    permission: PC.SCHEDULE_MONTHLY_VIEW,
  },
  {
    name: 'swap-request',
    path: '/swap-request',
    title: '换班申请',
    icon: Clock,
    permission: PC.DUTY_SWAP_VIEW_SELF,
  },
  {
    name: 'leave-request',
    path: '/leave-request',
    title: '请假申请',
    icon: Clock,
    permission: PC.DUTY_LEAVE_VIEW_SELF,
  },
  {
    name: 'my-cover',
    path: '/my-cover',
    title: '我的顶班',
    icon: Clock,
    permission: PC.DUTY_COVER_VIEW_SELF,
  },
  {
    name: 'approval-center',
    path: '/approval',
    title: '审批中心',
    icon: Document,
    permission: PC.APPROVAL_TASK_VIEW_TODO,
  },
  {
    name: 'schedule-rule',
    path: '/schedule-rule',
    title: '排班规则',
    icon: Grid,
    permission: PC.SHIFT_RULE_VIEW,
  },
  {
    name: 'actual-duty',
    path: '/actual-duty',
    title: '值班变更台账',
    icon: Clock,
    permission: PC.DUTY_ACTUAL_VIEW,
  },
  {
    name: 'leave-records',
    path: '/leave-records',
    title: '请假记录',
    icon: Clock,
    permission: PC.LEAVE_RECORD_VIEW,
  },
  {
    name: 'refund-management',
    path: '/refund',
    title: '退费管理',
    icon: Coin,
    permission: PC.REFUND_BATCH_CALCULATE,
  },
  {
    name: 'monthly-attendance',
    path: '/attendance/monthly',
    title: '月度考勤',
    icon: DataAnalysis,
    permission: PC.ATTENDANCE_MONTHLY_VIEW,
  },
  {
    name: 'export-history',
    path: '/export-history',
    title: '导出历史',
    icon: DataAnalysis,
    permission: PC.EXPORT_TASK_VIEW,
  },
  {
    name: 'person',
    path: '/base-data/person',
    title: '人员管理',
    icon: List,
    permission: PC.PERSON_MANAGE_VIEW,
  },
  {
    name: 'shift-def',
    path: '/base-data/shifts',
    title: '班次规则',
    icon: List,
    permission: PC.SHIFT_DEF_VIEW,
  },
  {
    name: 'holiday-standard',
    path: '/base-data/holiday',
    title: '节假日与标准',
    icon: List,
    permission: PC.HOLIDAY_STANDARD_VIEW,
  },
  {
    name: 'org-unit',
    path: '/system/org-unit',
    title: '台站机房',
    icon: Setting,
    permission: PC.ORG_UNIT_VIEW,
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
