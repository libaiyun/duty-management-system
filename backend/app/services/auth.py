from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import exists, inspect, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.core.exceptions import BusinessRuleError, NotFoundError, StateConflictError, UnauthorizedError
from app.core.role_matrix import CANONICAL_ROLE_CODES, ROLE_MATRIX, canonical_permissions
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.shift import ShiftDef, ShiftRule, ShiftRuleItem, ShiftRuleVersion
from app.models.user import SysDataScope, SysPermission, SysRole, SysUser, sys_role_permission, sys_user_role
from app.services.schedule import generate_schedule_from_rule


def _generated_code_suffix(number: int) -> str:
    """Produce an alphabetic suffix so generated shift codes match their stricter pattern."""
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(ord("a") + remainder) + result
    return result


def _generate_unique_code(db: Session, model, prefix: str, *scope) -> str:
    number = 0
    while True:
        code = prefix if number == 0 else f"{prefix}_{_generated_code_suffix(number)}"
        if len(code) > 64:
            raise StateConflictError(message="无法生成可用编码")
        if db.scalar(select(model.id).where(model.code == code, *scope).limit(1)) is None:
            return code
        number += 1


def authenticate_user(db: Session, username: str, password: str) -> SysUser:
    user = db.scalar(select(SysUser).where(SysUser.username == username))
    if user is None:
        raise UnauthorizedError(message="账号或密码错误")
    if user.status == "locked":
        raise UnauthorizedError(message="账号已被锁定")
    if user.status != "enabled":
        raise UnauthorizedError(message="账号已停用")
    if not verify_password(password, user.password_hash):
        raise UnauthorizedError(message="账号或密码错误")
    return user


def create_user(db: Session, username: str, password: str, display_name: str, person_id: int | None = None) -> SysUser:
    if person_id is not None:
        person = db.get(Person, person_id)
        if person is None:
            raise NotFoundError(message="绑定的员工不存在")
        existing = db.scalars(select(SysUser).where(SysUser.person_id == person_id)).first()
        if existing:
            raise StateConflictError(message="该员工已绑定账号")
    user = SysUser(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name,
        person_id=person_id,
    )
    db.add(user)
    db.flush()
    return user


def issue_tokens(settings: Settings, user: SysUser) -> tuple[str, str]:
    access = create_access_token(settings, user.id, user.username)
    refresh = create_refresh_token(settings, user.id, user.username)
    return access, refresh


def refresh_access_token(settings: Settings, token: str) -> tuple[str, str]:
    payload = decode_token(settings, token)
    if payload.get("type") != "refresh":
        raise UnauthorizedError(message="仅支持 refresh token 刷新")
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedError()
    return (
        create_access_token(settings, int(user_id_str), payload.get("username", "")),
        create_refresh_token(settings, int(user_id_str), payload.get("username", "")),
    )


def change_own_password(db: Session, user: SysUser, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password_hash):
        raise BusinessRuleError(message="原密码错误")
    if old_password == new_password:
        raise BusinessRuleError(message="新密码不能与原密码相同")
    user.password_hash = hash_password(new_password)
    db.flush()


def reset_user_password(db: Session, user_id: int, new_password: str) -> None:
    user = db.get(SysUser, user_id)
    if user is None:
        raise NotFoundError(message="用户不存在或已注销")
    user.password_hash = hash_password(new_password)
    db.flush()


def check_user_permission(db: Session, user: SysUser, permission_code: str) -> bool:
    stmt = (
        exists()
        .where(
            SysPermission.code == permission_code,
            SysPermission.id == sys_role_permission.c.permission_id,
            sys_role_permission.c.role_id == sys_user_role.c.role_id,
            sys_user_role.c.user_id == user.id,
        )
    )
    return db.scalar(select(stmt)) or False


@dataclass(frozen=True)
class DataScope:
    scope_type: str
    org_unit_id: int | None = None


def resolve_user_data_scopes(db: Session, user: SysUser) -> list[DataScope]:
    role_ids = db.scalars(
        select(sys_user_role.c.role_id).where(sys_user_role.c.user_id == user.id)
    ).all()

    # Data scope is fixed by assigned canonical roles.  Legacy per-user rows
    # must not widen a user's access. Retain persisted scope behavior only for
    # users still on a pre-matrix role; the API cannot assign those roles.
    role_codes = set(db.scalars(select(SysRole.code).where(SysRole.id.in_(role_ids))).all()) if role_ids else set()
    if role_codes & CANONICAL_ROLE_CODES:
        stmt = select(SysDataScope).where(SysDataScope.role_id.in_(role_ids))
    else:
        stmt = select(SysDataScope).where(
            (SysDataScope.user_id == user.id)
            | (SysDataScope.role_id.in_(role_ids) if role_ids else False)
        )

    seen: set[tuple[str, int | None]] = set()
    result: list[DataScope] = []
    for scope in db.scalars(stmt):
        key = (scope.scope_type, scope.org_unit_id)
        if key not in seen:
            seen.add(key)
            result.append(DataScope(scope.scope_type, scope.org_unit_id))

    return result


def has_global_scope(scopes: list[DataScope]) -> bool:
    return any(s.scope_type == "all" for s in scopes)


def resolve_scoped_org_unit_ids(db: Session, user: SysUser) -> set[int] | None:
    """计算用户数据范围可见的 org_unit id 集合。

    返回 None 表示全局范围（不过滤）。
    返回空集合表示无任何可见组织。
    self 范围按用户绑定人员所属机房处理。
    """
    scopes = resolve_user_data_scopes(db, user)
    if has_global_scope(scopes):
        return None

    root_ids: set[int] = set()
    for scope in scopes:
        if scope.scope_type == "room" and scope.org_unit_id is not None:
            root_ids.add(scope.org_unit_id)
        elif scope.scope_type == "self":
            if user.person_id is not None:
                person = db.get(Person, user.person_id)
                if person is not None and person.org_unit_id is not None:
                    root_ids.add(person.org_unit_id)

    if not root_ids:
        return set()
    return root_ids


def list_users(db: Session) -> list[SysUser]:
    return list(db.scalars(select(SysUser).order_by(SysUser.id)).all())


def get_user_detail(db: Session, user_id: int) -> SysUser | None:
    return db.get(SysUser, user_id)


def update_user(
    db: Session, user_id: int,
    display_name: str | None,
    status: str | None,
    person_id: int | None = None,
    update_person: bool = False,
) -> SysUser:
    user = db.get(SysUser, user_id)
    if user is None:
        raise NotFoundError(message="用户不存在")
    if display_name is not None:
        user.display_name = display_name
    if status is not None:
        user.status = status
    if update_person:
        if person_id is not None:
            if db.get(Person, person_id) is None:
                raise NotFoundError(message="绑定的员工不存在")
            existing = db.scalars(
                select(SysUser).where(SysUser.person_id == person_id, SysUser.id != user_id)
            ).first()
            if existing:
                raise StateConflictError(message="该员工已绑定其他账号")
        user.person_id = person_id
    db.flush()
    return user


def assign_user_roles(db: Session, user_id: int, role_ids: list[int]) -> SysUser:
    user = db.get(SysUser, user_id)
    if user is None:
        raise NotFoundError(message="用户不存在")
    roles = db.scalars(select(SysRole).where(SysRole.id.in_(role_ids))).all() if role_ids else []
    if len(roles) != len(role_ids):
        raise NotFoundError(message="角色不存在")
    if any(role.code not in CANONICAL_ROLE_CODES for role in roles):
        raise BusinessRuleError(message="只能分配预置角色")
    user.roles = roles  # type: ignore[assignment]
    db.flush()
    return user


def list_roles(db: Session) -> list[SysRole]:
    return list(db.scalars(select(SysRole).where(SysRole.code.in_(CANONICAL_ROLE_CODES)).order_by(SysRole.id)).all())


def list_permissions(db: Session) -> list[SysPermission]:
    return list(db.scalars(select(SysPermission).order_by(SysPermission.id)).all())


def seed_role_matrix(db: Session) -> None:
    """Create and repair the immutable role, grant, and scope records."""
    permissions = {p.code: p for p in db.scalars(select(SysPermission)).all()}
    for code in canonical_permissions(ROLE_MATRIX[-1]):
        if code not in permissions:
            permissions[code] = SysPermission(code=code, name=code, type="api")
            db.add(permissions[code])
    db.flush()
    for definition in ROLE_MATRIX:
        role = db.scalar(select(SysRole).where(SysRole.code == definition.code))
        if role is None:
            role = SysRole(code=definition.code, name=definition.name, remark="系统预置角色")
            db.add(role)
            db.flush()
        role.name = definition.name
        role.status = "enabled"
        role.permissions = [permissions[code] for code in canonical_permissions(definition)]
        scopes = db.scalars(select(SysDataScope).where(SysDataScope.role_id == role.id)).all()
        for scope in scopes:
            db.delete(scope)
        db.add(SysDataScope(role_id=role.id, scope_type=definition.scope_type))
    db.flush()


def list_org_units(db: Session, org_unit_ids: set[int] | None = None) -> list[OrgUnit]:
    stmt = select(OrgUnit)
    if org_unit_ids is not None:
        if not org_unit_ids:
            return []
        stmt = stmt.where(OrgUnit.id.in_(org_unit_ids))
    stmt = stmt.order_by(OrgUnit.sort_order, OrgUnit.id)
    return list(db.scalars(stmt).all())


def create_org_unit(
    db: Session, code: str | None, name: str, type_: str,
    parent_id: int | None = None, sort_order: int = 0,
    manager_person_id: int | None = None,
) -> OrgUnit:
    code = code or _generate_unique_code(db, OrgUnit, "org_unit")
    existing = db.scalars(select(OrgUnit).where(OrgUnit.code == code)).first()
    if existing:
        raise StateConflictError(message=f"组织编码 '{code}' 已存在")
    if parent_id is not None and db.get(OrgUnit, parent_id) is None:
        raise NotFoundError(message="上级组织不存在")
    if manager_person_id is not None and db.get(Person, manager_person_id) is None:
        raise NotFoundError(message="负责人不存在")
    unit = OrgUnit(
        code=code, name=name, type=type_, parent_id=parent_id,
        sort_order=sort_order, manager_person_id=manager_person_id,
    )
    db.add(unit)
    db.flush()
    return unit


def update_org_unit(
    db: Session, unit_id: int,
    parent_id: int | None, name: str | None, status: str | None, sort_order: int | None,
    manager_person_id: int | None = None, update_manager: bool = False,
) -> OrgUnit:
    unit = db.get(OrgUnit, unit_id)
    if unit is None:
        raise NotFoundError(message="组织不存在")
    if parent_id is not None:
        if db.get(OrgUnit, parent_id) is None:
            raise NotFoundError(message="上级组织不存在")
        if parent_id == unit_id:
            raise StateConflictError(message="上级组织不能是自身")
        unit.parent_id = parent_id
    if name is not None:
        unit.name = name
    if update_manager:
        if manager_person_id is not None and db.get(Person, manager_person_id) is None:
            raise NotFoundError(message="负责人不存在")
        unit.manager_person_id = manager_person_id
    if status is not None:
        if status == "disabled" and unit.status != "disabled" and _org_unit_has_active_persons(db, unit_id):
            raise StateConflictError(message="当前组织存在在职人员，不能停用")
        unit.status = status
    if sort_order is not None:
        unit.sort_order = sort_order
    db.flush()
    return unit


def get_org_unit_children(db: Session, parent_id: int | None) -> list[OrgUnit]:
    return list(db.scalars(
        select(OrgUnit).where(OrgUnit.parent_id == parent_id).order_by(OrgUnit.sort_order, OrgUnit.id)
    ).all())


def check_org_unit_referenced(db: Session, unit_id: int) -> bool:
    has_children = db.scalar(
        exists().where(OrgUnit.parent_id == unit_id).select()
    ) or False
    return bool(has_children) or _org_unit_has_persons(db, unit_id)


def _org_unit_has_persons(db: Session, unit_id: int) -> bool:
    return bool(db.scalar(
        exists().where(Person.org_unit_id == unit_id).select()
    ))


def _org_unit_has_active_persons(db: Session, unit_id: int) -> bool:
    return bool(db.scalar(
        exists().where(
            Person.org_unit_id == unit_id,
            Person.status == "enabled",
        ).select()
    ))


def list_persons(
    db: Session,
    org_unit_ids: set[int] | None = None,
    participate_schedule: bool | None = None,
    org_unit_id: int | None = None,
    person_type: str | None = None,
) -> list[Person]:
    stmt = select(Person).options(selectinload(Person.account))
    if org_unit_ids is not None:
        if not org_unit_ids:
            return []
        stmt = stmt.where(Person.org_unit_id.in_(org_unit_ids))
    if org_unit_id is not None:
        stmt = stmt.where(Person.org_unit_id == org_unit_id)
    if participate_schedule is not None:
        stmt = stmt.where(Person.participate_schedule == participate_schedule)
    if person_type is not None:
        stmt = stmt.where(Person.person_type == person_type)
    stmt = stmt.order_by(Person.id)
    return list(db.scalars(stmt).all())


def create_person(
    db: Session, code: str | None, name: str, person_type: str,
    org_unit_id: int | None = None, phone: str | None = None,
    participate_schedule: bool = False,
    remark: str | None = None,
) -> Person:
    code = code or _generate_unique_code(db, Person, "person")
    existing = db.scalars(select(Person).where(Person.code == code)).first()
    if existing:
        raise StateConflictError(message=f"人员编号 '{code}' 已存在")
    if org_unit_id is not None and db.get(OrgUnit, org_unit_id) is None:
        raise NotFoundError(message="组织不存在")
    p = Person(
        code=code, name=name, person_type=person_type,
        org_unit_id=org_unit_id, phone=phone,
        participate_schedule=participate_schedule,
        remark=remark,
    )
    db.add(p)
    db.flush()
    return p


def update_person(
    db: Session, person_id: int,
    org_unit_id: int | None = None,
    name: str | None = None,
    phone: str | None = None,
    participate_schedule: bool | None = None,
    status: str | None = None,
    remark: str | None = None,
) -> Person:
    p = db.get(Person, person_id)
    if p is None:
        raise NotFoundError(message="人员不存在")
    if org_unit_id is not None:
        if db.get(OrgUnit, org_unit_id) is None:
            raise NotFoundError(message="组织不存在")
        p.org_unit_id = org_unit_id
    if name is not None:
        p.name = name
    if phone is not None:
        p.phone = phone
    if participate_schedule is not None:
        p.participate_schedule = participate_schedule
    if status is not None:
        p.status = status
    if remark is not None:
        p.remark = remark
    db.flush()
    return p


def _parse_time(t: str) -> tuple[int, int]:
    parts = t.split(":")
    return int(parts[0]), int(parts[1])


def _times_overlap(
    start_a: str, end_a: str,
    start_b: str, end_b: str,
) -> bool:
    """Check overlap between daily ranges, including ranges that cross midnight."""
    sa_h, sa_m = _parse_time(start_a)
    ea_h, ea_m = _parse_time(end_a)
    sb_h, sb_m = _parse_time(start_b)
    eb_h, eb_m = _parse_time(end_b)
    a_start = sa_h * 60 + sa_m
    a_end = ea_h * 60 + ea_m
    b_start = sb_h * 60 + sb_m
    b_end = eb_h * 60 + eb_m

    def intervals(start: int, end: int) -> list[tuple[int, int]]:
        if start < end:
            return [(start, end)]
        return [(start, 1440), (0, end)]

    a_intervals = intervals(a_start, a_end)
    b_intervals = intervals(b_start, b_end)
    return any(
        interval_a_start < interval_b_end and interval_b_start < interval_a_end
        for interval_a_start, interval_a_end in a_intervals
        for interval_b_start, interval_b_end in b_intervals
    )


_DEFAULT_SHIFT_DEFS = (
    ("early", "早班", "00:00", "08:00", 1),
    ("middle", "中班", "08:00", "16:00", 2),
    ("night", "晚班", "16:00", "24:00", 3),
)


def _ensure_default_shift_defs(db: Session, org_unit_id: int) -> None:
    # Lock the room so concurrent first access cannot create duplicate defaults.
    db.scalar(select(OrgUnit).where(OrgUnit.id == org_unit_id).with_for_update())
    if db.scalar(select(ShiftDef.id).where(ShiftDef.org_unit_id == org_unit_id).limit(1)) is not None:
        return
    db.add_all([
        ShiftDef(
            org_unit_id=org_unit_id,
            code=code,
            name=name,
            start_time=start_time,
            end_time=end_time,
            display_order=display_order,
        )
        for code, name, start_time, end_time, display_order in _DEFAULT_SHIFT_DEFS
    ])
    db.flush()


def list_shift_defs(db: Session, org_unit_id: int) -> list[ShiftDef]:
    _ensure_default_shift_defs(db, org_unit_id)
    return list(db.scalars(
        select(ShiftDef)
        .where(ShiftDef.org_unit_id == org_unit_id)
        .order_by(ShiftDef.display_order, ShiftDef.id)
    ).all())


def create_shift_def(
    db: Session, org_unit_id: int, code: str | None, name: str,
    start_time: str, end_time: str,
    display_order: int = 0,
) -> ShiftDef:
    code = code or _generate_unique_code(db, ShiftDef, "shift", ShiftDef.org_unit_id == org_unit_id)
    existing = db.scalars(
        select(ShiftDef)
        .where(ShiftDef.org_unit_id == org_unit_id)
        .where(ShiftDef.code == code)
    ).first()
    if existing:
        raise StateConflictError(message=f"班次编码 '{code}' 已存在")
    overlaps = db.scalars(
        select(ShiftDef)
        .where(ShiftDef.org_unit_id == org_unit_id)
        .where(ShiftDef.status == "enabled")
    ).all()
    for s in overlaps:
        if _times_overlap(start_time, end_time, s.start_time, s.end_time):
            raise BusinessRuleError(message=f"班次时间与 '{s.name}' ({s.start_time}-{s.end_time}) 重叠")
    sd = ShiftDef(
        org_unit_id=org_unit_id, code=code, name=name,
        start_time=start_time, end_time=end_time,
        display_order=display_order,
    )
    db.add(sd)
    db.flush()
    return sd


def update_shift_def(
    db: Session, shift_id: int,
    name: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    display_order: int | None = None,
    status: str | None = None,
) -> ShiftDef:
    sd = db.get(ShiftDef, shift_id)
    if sd is None:
        raise NotFoundError(message="班次不存在")
    resolved_start = start_time if start_time is not None else sd.start_time
    resolved_end = end_time if end_time is not None else sd.end_time
    overlap = db.scalars(
        select(ShiftDef).where(
            ShiftDef.org_unit_id == sd.org_unit_id,
            ShiftDef.status == "enabled",
            ShiftDef.id != shift_id,
        )
    ).all()
    for s in overlap:
        if _times_overlap(resolved_start, resolved_end, s.start_time, s.end_time):
            raise BusinessRuleError(message=f"班次时间与 '{s.name}' ({s.start_time}-{s.end_time}) 重叠")
    if name is not None:
        sd.name = name
    if start_time is not None:
        sd.start_time = start_time
    if end_time is not None:
        sd.end_time = end_time
    if display_order is not None:
        sd.display_order = display_order
    if status is not None:
        sd.status = status
    db.flush()
    return sd


def _validate_start_date(start_date_str: str) -> None:
    try:
        sd = date.fromisoformat(start_date_str)
    except (ValueError, TypeError):
        raise BusinessRuleError(message=f"起始日期格式无效: {start_date_str}")
    tomorrow = date.today() + timedelta(days=1)
    if sd < tomorrow:
        raise BusinessRuleError(message=f"起始日期必须从明天（{tomorrow.isoformat()}）起，不能是过去日期")


def _validate_cells(
    db: Session, rule: ShiftRule, days: list[dict],
) -> None:
    enabled_stmt = select(ShiftDef).where(ShiftDef.status == "enabled")
    if rule.org_unit_id is not None:
        enabled_stmt = enabled_stmt.where(ShiftDef.org_unit_id == rule.org_unit_id)
    enabled_defs = list(db.scalars(enabled_stmt.order_by(ShiftDef.display_order)).all())
    if not enabled_defs:
        raise BusinessRuleError(message="当前机房未配置班次定义，无法设置排班规则。")
    expected_def_ids = {sd.id for sd in enabled_defs}

    if not days:
        return

    persons_needed = rule.persons_per_cell
    day_nos_seen = set()
    for day in days:
        day_no = day.get("day_no")
        if day_no in day_nos_seen:
            raise BusinessRuleError(message=f"第 {day_no} 天重复出现")
        day_nos_seen.add(day_no)

        cells = day.get("cells", [])
        cell_shift_ids = set()
        for cell in cells:
            sid = cell.get("shift_def_id")
            cell_shift_ids.add(sid)
            pids = cell.get("person_ids", [])
            if len(pids) != persons_needed:
                raise BusinessRuleError(
                    message=f"第 {day_no} 天班次 {sid} 需要 {persons_needed} 人，当前 {len(pids)} 人",
                )
            if len(set(pids)) != len(pids):
                raise BusinessRuleError(message=f"第 {day_no} 天班次 {sid} 的人员不能重复")
            for pid in pids:
                person = db.get(Person, pid)
                if not person or person.org_unit_id != rule.org_unit_id:
                    raise BusinessRuleError(
                        message=f"第 {day_no} 天班次 {sid} 的人员 {pid} 不属于当前机房",
                    )
                if person.status != "enabled" or not person.participate_schedule or person.person_type != "duty_operator":
                    raise BusinessRuleError(
                        message=f"第 {day_no} 天班次 {sid} 的人员 {pid} 不符合排班条件",
                    )

        invalid = cell_shift_ids - expected_def_ids
        if invalid:
            raise BusinessRuleError(
                message=f"第 {day_no} 天包含不属于当前机房的启用班次: {sorted(invalid)}",
            )
        missing = expected_def_ids - cell_shift_ids
        if missing:
            raise BusinessRuleError(
                message=f"第 {day_no} 天缺少班次: {sorted(missing)}",
            )

    expected_days = set(range(1, rule.cycle_days + 1))
    missing_days = expected_days - day_nos_seen
    if missing_days:
        raise BusinessRuleError(
            message=f"缺少第 {'、'.join(str(d) for d in sorted(missing_days))} 天的排班数据",
        )


def list_shift_rules(db: Session, org_unit_id: int | None = None) -> list[ShiftRule]:
    stmt = select(ShiftRule).order_by(ShiftRule.id)
    if org_unit_id is not None:
        stmt = stmt.where(ShiftRule.org_unit_id == org_unit_id)
    return list(db.scalars(stmt).all())


def get_shift_rule(db: Session, rule_id: int, org_unit_id: int | None = None) -> ShiftRule | None:
    stmt = select(ShiftRule).where(ShiftRule.id == rule_id)
    if org_unit_id is not None:
        stmt = stmt.where(ShiftRule.org_unit_id == org_unit_id)
    return db.scalars(stmt).first()


def _get_next_version_no(db: Session, rule_id: int) -> int:
    max_v = db.scalar(
        select(ShiftRuleVersion.version_no)
        .where(ShiftRuleVersion.rule_id == rule_id)
        .order_by(ShiftRuleVersion.version_no.desc())
        .limit(1),
    )
    return (max_v or 0) + 1


def _build_cell_persons(cells: list[dict]) -> dict:
    result: dict = {}
    for cell in cells:
        result[str(cell["shift_def_id"])] = cell["person_ids"]
    return result


def _create_rule_version(
    db: Session, rule: ShiftRule, days: list[dict], status: str = "draft",
) -> ShiftRuleVersion:
    version_no = _get_next_version_no(db, int(rule.id))  # type: ignore[arg-type]
    v = ShiftRuleVersion(
        rule_id=int(rule.id),  # type: ignore[arg-type]
        version_no=version_no,
        cycle_days=rule.cycle_days,
        start_date=rule.start_date,
        persons_per_cell=rule.persons_per_cell,
        status=status,
    )
    snapshot_days = []
    for day in sorted(days, key=lambda d: d["day_no"]):
        cells_dict = _build_cell_persons(day.get("cells", []))
        v.items.append(ShiftRuleItem(
            day_no=day["day_no"],
            cell_persons=cells_dict,
        ))
        snapshot_days.append({"day_no": day["day_no"], "cells": cells_dict})
    v.snapshot = {"cycle_days": rule.cycle_days, "start_date": rule.start_date, "days": snapshot_days}
    db.add(v)
    db.flush()
    return v


def _version_days(version: ShiftRuleVersion) -> list[dict]:
    return [
        {
            "day_no": item.day_no,
            "cells": [
                {"shift_def_id": int(shift_def_id), "person_ids": person_ids}
                for shift_def_id, person_ids in item.cell_persons.items()
            ],
        }
        for item in version.items
    ]


def create_shift_rule(
    db: Session, code: str | None, name: str,
    cycle_days: int = 6,
    start_date: str = "",
    persons_per_cell: int = 2,
    org_unit_id: int | None = None,
    remark: str | None = None,
    days: list[dict] | None = None,
) -> ShiftRule:
    code = code or _generate_unique_code(db, ShiftRule, "shift_rule")
    existing = db.scalars(select(ShiftRule).where(ShiftRule.code == code)).first()
    if existing:
        raise StateConflictError(message=f"规则编码 '{code}' 已存在")
    if org_unit_id is not None and db.get(OrgUnit, org_unit_id) is None:
        raise NotFoundError(message="组织不存在")
    if start_date:
        _validate_start_date(start_date)
    rule = ShiftRule(
        code=code, name=name,
        cycle_days=cycle_days, start_date=start_date,
        persons_per_cell=persons_per_cell,
        org_unit_id=org_unit_id, remark=remark,
    )
    db.add(rule)
    db.flush()
    _validate_cells(db, rule, [])
    if days:
        _validate_cells(db, rule, days)
        _create_rule_version(db, rule, days, status="draft")
    return rule


def _rule_is_referenced(db: Session, rule_id: int) -> bool:
    bind = db.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("monthly_schedule"):
        return False
    count = db.scalar(
        text("SELECT COUNT(1) FROM monthly_schedule WHERE rule_id = :rid"),
        {"rid": rule_id},
    )
    return bool(count)


def update_shift_rule(
    db: Session, rule_id: int,
    name: str | None = None,
    cycle_days: int | None = None,
    start_date: str | None = None,
    persons_per_cell: int | None = None,
    org_unit_id: int | None = None,
    remark: str | None = None,
    days: list[dict] | None = None,
) -> ShiftRule:
    rule = db.get(ShiftRule, rule_id)
    if rule is None:
        raise NotFoundError(message="排班规则不存在")
    schedule_config_changed = any(value is not None for value in (
        cycle_days, start_date, persons_per_cell,
    ))
    latest_version = db.scalars(
        select(ShiftRuleVersion)
        .where(ShiftRuleVersion.rule_id == rule_id)
        .order_by(ShiftRuleVersion.version_no.desc())
        .limit(1),
    ).first()
    if org_unit_id is not None:
        if db.get(OrgUnit, org_unit_id) is None:
            raise NotFoundError(message="组织不存在")
        rule.org_unit_id = org_unit_id
    if name is not None:
        rule.name = name
    if cycle_days is not None:
        rule.cycle_days = cycle_days
    if start_date is not None:
        rule.start_date = start_date
    if persons_per_cell is not None:
        rule.persons_per_cell = persons_per_cell
    if remark is not None:
        rule.remark = remark
    _validate_cells(db, rule, [])
    version_days = days
    if version_days is None and schedule_config_changed and latest_version is not None:
        version_days = _version_days(latest_version)
    if version_days is not None:
        _validate_start_date(rule.start_date)
        _validate_cells(db, rule, version_days)
        _create_rule_version(db, rule, version_days, status="draft")
        # Keep the currently published version active until this draft version
        # is explicitly published. A superseded rule becomes a draft candidate.
        if rule.status == "superseded":
            rule.status = "draft"
    db.flush()
    return rule


def delete_shift_rule(db: Session, rule_id: int) -> None:
    rule = db.get(ShiftRule, rule_id)
    if rule is None:
        raise NotFoundError(message="排班规则不存在")
    _validate_cells(db, rule, [])
    if _rule_is_referenced(db, rule_id):
        raise StateConflictError(message="规则已被排班引用，不能删除")
    db.delete(rule)
    db.flush()


def publish_shift_rule(db: Session, rule_id: int) -> ShiftRule:
    rule = db.scalars(
        select(ShiftRule).where(ShiftRule.id == rule_id).with_for_update(),
    ).first()
    if rule is None:
        raise NotFoundError(message="排班规则不存在")
    latest_version = db.scalars(
        select(ShiftRuleVersion)
        .where(ShiftRuleVersion.rule_id == rule_id)
        .order_by(ShiftRuleVersion.version_no.desc())
        .limit(1)
    ).first()
    if latest_version is None:
        raise BusinessRuleError(message="规则没有保存版本，请先保存")
    if latest_version.status != "draft":
        raise StateConflictError(message="当前版本已发布，请先修改再重新发布")
    if rule.org_unit_id is None:
        raise BusinessRuleError(message="排班规则未关联机房")
    _validate_cells(db, rule, [
        {
            "day_no": item.day_no,
            "cells": [
                {"shift_def_id": int(shift_def_id), "person_ids": person_ids}
                for shift_def_id, person_ids in item.cell_persons.items()
            ],
        }
        for item in latest_version.items
    ])
    # A room can retain several configurations, while exactly one can drive
    # its schedule. Lock all current candidates before changing the status.
    active_rules = list(db.scalars(
        select(ShiftRule)
        .where(ShiftRule.org_unit_id == rule.org_unit_id)
        .where(ShiftRule.status == "published")
        .where(ShiftRule.id != rule.id)
        .with_for_update(),
    ).all())
    for active_rule in active_rules:
        active_rule.status = "superseded"

    latest_version.status = "published"
    rule.status = "published"
    db.flush()
    generate_schedule_from_rule(db, rule, latest_version)
    return rule


def get_rule_latest_items(db: Session, rule_id: int) -> list[ShiftRuleItem]:
    latest_version = get_rule_latest_version(db, rule_id)
    if latest_version is None:
        return []
    return list(db.scalars(
        select(ShiftRuleItem)
        .where(ShiftRuleItem.version_id == int(latest_version.id))  # type: ignore[arg-type]
        .order_by(ShiftRuleItem.day_no)
    ).all())


def get_rule_latest_version(db: Session, rule_id: int) -> ShiftRuleVersion | None:
    return db.scalars(
        select(ShiftRuleVersion)
        .where(ShiftRuleVersion.rule_id == rule_id)
        .order_by(ShiftRuleVersion.version_no.desc())
        .limit(1)
    ).first()
