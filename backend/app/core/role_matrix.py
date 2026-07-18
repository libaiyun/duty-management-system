"""The confirmed, non-configurable application role matrix."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalRole:
    code: str
    name: str
    scope_type: str
    permissions: tuple[str, ...]


VIEW = "schedule:monthly:view"
ROLE_MATRIX = (
    CanonicalRole("duty_operator", "值机员", "self", (
        VIEW, "duty:schedule:view_self", "duty:swap:view_self", "duty:leave:view_self", "duty:cover:view_self", "approval:record:view_done",
    )),
    CanonicalRole("maintenance", "检修班", "self", ("duty:cover:view_self", "approval:record:view_done",)),
    CanonicalRole("deputy_director", "副主任", "room", (
        VIEW, "duty:swap:view_self", "duty:leave:view_self", "duty:cover:view_self",
        "approval:task:view_todo", "approval:record:view_done", "schedule:monthly:generate", "shift:rule:view", "shift:rule:manage",
        "shift:def:view", "shift:def:manage", "duty:actual:view", "leave:record:view",
        "refund:batch:calculate", "refund:detail:view", "attendance:monthly:view", "export:task:view",
        "person:manage:view", "holiday:standard:view", "holiday:standard:manage",
    )),
    CanonicalRole("room_director", "机房主任", "room", (
        VIEW, "duty:swap:view_self", "duty:leave:view_self", "duty:cover:view_self",
        "approval:task:view_todo", "approval:record:view_done", "schedule:monthly:generate", "shift:rule:view", "shift:rule:manage",
        "shift:def:view", "shift:def:manage", "duty:actual:view", "leave:record:view",
        "refund:batch:calculate", "refund:detail:view", "attendance:monthly:view", "export:task:view",
        "person:manage:view", "holiday:standard:view", "holiday:standard:manage",
    )),
    CanonicalRole("schedule_admin", "排班管理员", "room", (
        VIEW, "schedule:monthly:generate", "shift:rule:view", "shift:rule:manage", "duty:actual:view", "export:task:view",
    )),
    CanonicalRole("finance_statistics", "财务/统计", "room", (
        VIEW, "refund:batch:calculate", "refund:detail:view", "attendance:monthly:view", "export:task:view",
    )),
    CanonicalRole("system_admin", "系统管理员", "all", ()),
)

CANONICAL_ROLE_CODES = frozenset(role.code for role in ROLE_MATRIX)
ALL_PERMISSION_CODES = frozenset({permission for role in ROLE_MATRIX for permission in role.permissions} | {
    "schedule:monthly:generate", "holiday:global:manage", "org:unit:view", "system:user:manage",
    "system:log:view", "system:backup:view", "cover:assignment:view",
})


def canonical_permissions(role: CanonicalRole) -> tuple[str, ...]:
    return tuple(ALL_PERMISSION_CODES) if role.code == "system_admin" else role.permissions
