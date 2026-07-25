export const PERMISSION_CODES = {
  APPROVAL_TASK_VIEW_TODO: 'approval:task:view_todo',
  APPROVAL_RECORD_VIEW_DONE: 'approval:record:view_done',
  SCHEDULE_MONTHLY_VIEW: 'schedule:monthly:view',
  SCHEDULE_MONTHLY_GENERATE: 'schedule:monthly:generate',
  SCHEDULE_HISTORY_CORRECT: 'schedule:history:correct',
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
  SHIFT_RULE_MANAGE: 'shift:rule:manage',
  SHIFT_DEF_VIEW: 'shift:def:view',
  SHIFT_DEF_MANAGE: 'shift:def:manage',
  HOLIDAY_STANDARD_VIEW: 'holiday:standard:view',
  HOLIDAY_STANDARD_MANAGE: 'holiday:standard:manage',
  HOLIDAY_GLOBAL_MANAGE: 'holiday:global:manage',
  SYSTEM_USER_MANAGE: 'system:user:manage',
  SYSTEM_LOG_VIEW: 'system:log:view',
  SYSTEM_BACKUP_VIEW: 'system:backup:view',
} as const

export type PermissionCode = (typeof PERMISSION_CODES)[keyof typeof PERMISSION_CODES]

export const ALL_PERMISSIONS: PermissionCode[] = Object.values(PERMISSION_CODES)
