export const PERMISSION_CODES = {
  DUTY_SCHEDULE_VIEW_SELF: 'duty:schedule:view_self',
  DUTY_SWAP_VIEW_SELF: 'duty:swap:view_self',
  DUTY_LEAVE_VIEW_SELF: 'duty:leave:view_self',
  DUTY_COVER_VIEW_SELF: 'duty:cover:view_self',
  APPROVAL_TASK_VIEW_TODO: 'approval:task:view_todo',
  APPROVAL_RECORD_VIEW_DONE: 'approval:record:view_done',
  SCHEDULE_MONTHLY_VIEW: 'schedule:monthly:view',
  SCHEDULE_DETAIL_VIEW: 'schedule:detail:view',
  DUTY_ACTUAL_VIEW: 'duty:actual:view',
  LEAVE_RECORD_VIEW: 'leave:record:view',
  COVER_ASSIGNMENT_VIEW: 'cover:assignment:view',
  REFUND_BATCH_CALCULATE: 'refund:batch:calculate',
  REFUND_DETAIL_VIEW: 'refund:detail:view',
  ATTENDANCE_MONTHLY_VIEW: 'attendance:monthly:view',
  EXPORT_TASK_VIEW: 'export:task:view',
  ORG_UNIT_VIEW: 'org:unit:view',
  PERSON_MANAGE_VIEW: 'person:manage:view',
  SHIFT_RULE_VIEW: 'shift:rule:view',
  HOLIDAY_STANDARD_VIEW: 'holiday:standard:view',
  SYSTEM_USER_MANAGE: 'system:user:manage',
  SYSTEM_LOG_VIEW: 'system:log:view',
  SYSTEM_BACKUP_VIEW: 'system:backup:view',
} as const

export type PermissionCode = (typeof PERMISSION_CODES)[keyof typeof PERMISSION_CODES]

export const ALL_PERMISSIONS: PermissionCode[] = Object.values(PERMISSION_CODES)
