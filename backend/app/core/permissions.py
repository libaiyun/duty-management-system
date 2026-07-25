from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDefinition:
    code: str
    name: str
    group_code: str
    group_name: str


def _permission(code: str, name: str, group_code: str, group_name: str) -> PermissionDefinition:
    return PermissionDefinition(code, name, group_code, group_name)


PERMISSIONS = (
    _permission("schedule:monthly:view", "查看排班", "schedule", "排班管理"),
    _permission("schedule:monthly:generate", "生成、调整和发布排班", "schedule", "排班管理"),
    _permission("schedule:history:correct", "历史排班修正", "schedule", "排班管理"),
    _permission("duty:actual:view", "查看值班变更台账", "schedule", "排班管理"),
    _permission("shift:rule:view", "查看排班规则", "shift_rule", "班次和排班规则"),
    _permission("shift:rule:manage", "维护排班规则", "shift_rule", "班次和排班规则"),
    _permission("shift:def:view", "查看班次定义", "shift_rule", "班次和排班规则"),
    _permission("shift:def:manage", "维护班次定义", "shift_rule", "班次和排班规则"),
    _permission("approval:task:view_todo", "处理审批任务", "approval", "换班与请假审批"),
    _permission("approval:record:view_done", "查看审批记录", "approval", "换班与请假审批"),
    _permission("leave:record:view", "查看请假记录", "approval", "换班与请假审批"),
    _permission("cover:assignment:view", "管理顶班安排", "approval", "换班与请假审批"),
    _permission("person:manage:view", "管理人员资料", "person", "人员管理"),
    _permission("holiday:standard:view", "查看节假日与标准", "standard", "节假日与费用标准"),
    _permission("holiday:standard:manage", "维护机房费用标准", "standard", "节假日与费用标准"),
    _permission("holiday:global:manage", "维护全局节假日", "standard", "节假日与费用标准"),
    _permission("refund:batch:calculate", "管理退费批次", "refund", "退费管理"),
    _permission("refund:detail:view", "查看退费结果", "refund", "退费管理"),
    _permission("attendance:monthly:view", "管理月度考勤", "attendance", "考勤管理"),
    _permission("export:task:view", "管理导出任务", "export", "导出管理"),
    _permission("system:user:manage", "管理账号和角色", "system", "账号和角色管理"),
    _permission("org:unit:view", "管理组织机构", "system", "组织机构"),
    _permission("system:log:view", "查看操作日志", "system", "系统管理"),
    _permission("system:backup:view", "管理备份归档", "system", "系统管理"),
)

PERMISSION_CODES = frozenset(item.code for item in PERMISSIONS)

# 常用职责角色只是初始化模板，创建后可正常调整。
BUILTIN_ROLES: dict[str, tuple[str, tuple[str, ...]]] = {
    "system_admin": ("系统管理员", tuple(sorted(PERMISSION_CODES))),
    "schedule_admin": ("排班管理员", (
        "schedule:monthly:view", "schedule:monthly:generate", "schedule:history:correct",
        "duty:actual:view", "shift:rule:view", "shift:rule:manage", "shift:def:view", "shift:def:manage",
    )),
    "approval_admin": ("审批管理员", (
        "approval:task:view_todo", "approval:record:view_done", "leave:record:view", "cover:assignment:view",
    )),
    "person_admin": ("人员资料管理员", ("person:manage:view",)),
    "finance_statistics": ("财务统计", (
        "refund:batch:calculate", "refund:detail:view", "attendance:monthly:view", "export:task:view",
    )),
}
