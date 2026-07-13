# M2-P2 Phase 验收说明

## 验收范围

当前 Phase：`M2-P2 组织、人员与基础规则`。

依据：
- `docs/design/03-总体设计.md`（§8.2 组织与人员、§8.3 班次与排班规则、§8.8 节假日、§9 API 规范、§10 权限模型、§12.2 固定标准、§15 异常处理）
- `docs/design/04-开发实施计划.md`（§5 M2 认证权限与基础资料）

本次验收覆盖 M2-P2 全部 9 个 Task：

- M2-P2-T1 组织机构模型与 API
- M2-P2-T2 台站机房前端页面
- M2-P2-T3 人员模型与 API
- M2-P2-T4 人员管理前端页面
- M2-P2-T5 班次定义模型与 API
- M2-P2-T6 排班规则模型与 API
- M2-P2-T7 班次规则前端页面
- M2-P2-T8 节假日与固定标准模型/API
- M2-P2-T9 节假日与标准前端页面

不覆盖范围：
- 月度排班/实际值班，属于 `M3`
- 换班/请假/顶班/审批，属于 `M4`
- 退费/考勤/导出，属于 `M5`
- 操作日志/通知/备份，属于 `M6`

## 接口联调

已验证 M2-P2 全部 API 端点，响应格式均符合总体设计 §9.2：

| 方法 | 路径 | 状态 | 测试来源 |
|------|------|------|----------|
| GET | `/api/v1/org-units` | ✅ | test_org_units.py |
| GET | `/api/v1/org-units/tree` | ✅ | test_org_units.py |
| POST | `/api/v1/org-units` | ✅ | test_org_units.py |
| GET | `/api/v1/org-units/{id}` | ✅ | test_org_units.py |
| PUT | `/api/v1/org-units/{id}` | ✅ | test_org_units.py |
| DELETE | `/api/v1/org-units/{id}` | ✅ | test_org_units.py |
| GET | `/api/v1/persons` | ✅ | test_persons.py |
| POST | `/api/v1/persons` | ✅ | test_persons.py |
| GET | `/api/v1/persons/{id}` | ✅ | test_persons.py |
| PUT | `/api/v1/persons/{id}` | ✅ | test_persons.py |
| GET | `/api/v1/shifts` | ✅ | test_shifts.py |
| POST | `/api/v1/shifts` | ✅ | test_shifts.py |
| GET | `/api/v1/shifts/{id}` | ✅ | test_shifts.py |
| PUT | `/api/v1/shifts/{id}` | ✅ | test_shifts.py |
| GET | `/api/v1/shift-rules` | ✅ | test_shift_rules.py |
| POST | `/api/v1/shift-rules` | ✅ | test_shift_rules.py |
| GET | `/api/v1/shift-rules/{id}` | ✅ | test_shift_rules.py |
| PUT | `/api/v1/shift-rules/{id}` | ✅ | test_shift_rules.py |
| DELETE | `/api/v1/shift-rules/{id}` | ✅ | test_shift_rules.py |
| GET | `/api/v1/holidays` | ✅ | test_holidays.py |
| GET | `/api/v1/holidays/standard` | ✅ | test_holidays.py |
| POST | `/api/v1/holidays` | ✅ | test_holidays.py |
| POST | `/api/v1/holidays/import` | ✅ | test_holidays.py |
| GET | `/api/v1/holidays/{id}` | ✅ | test_holidays.py |
| PUT | `/api/v1/holidays/{id}` | ✅ | test_holidays.py |
| DELETE | `/api/v1/holidays/{id}` | ✅ | test_holidays.py |

前后端联调（4 个前端页面）：
- OrgUnitView / PersonView / ShiftRuleView / HolidayView 字段映射与后端 schema 一致 ✅
- 运行环境实测（Docker Compose）：登录 → org-units/persons/shifts/shift-rules/holidays 全链路可用 ✅

## 异常测试

对照总体设计 §15 异常码：

| 异常 | HTTP | code | 场景 | 状态 |
|------|------|------|------|------|
| 参数校验失败 | 400 | `VALIDATION_ERROR` | persons_per_shift=0、时间格式、code 正则 | ✅ |
| 无权限 | 403 | `FORBIDDEN` | 无对应 view 权限访问 5 组端点 | ✅ |
| 不存在 | 404 | `NOT_FOUND` | 各资源 not-found、org 无效 parent、person 无效 org | ✅ |
| 状态冲突 | 409 | `STATE_CONFLICT` | **org/person 编码重复**、组织有子级/人员删除、班次重叠外的规则/节假日重复、自引用 parent | ✅ |
| 业务校验失败 | 422 | `BUSINESS_RULE_FAILED` | 班次时间重叠 | ✅ |

## 边界测试

| 场景 | 结果 | 来源 |
|------|------|------|
| 组织树多层嵌套/自引用 | 正确构建 | test_org_units.py |
| 组织 self-parent | 409 | test_org_units.py |
| 排班规则空 items | 允许 | test_shift_rules.py |
| 排班规则明细乱序 → 按 sequence_no 持久化 | 一致 | test_shift_rules.py |
| 节假日批量导入去重（已存在 + 批内重复） | created/skipped 正确 | test_holidays.py |
| 节假日按年度过滤 | 正确 | test_holidays.py |
| 节假日按日期排序 | 正确 | test_holidays.py |
| 固定标准值 10/10/14/4/150/56 | 正确 | test_holidays.py |
| 数据范围裁剪后子树成根 | tree 正确挂载 | org_units 路由 `_build_tree` |

## 权限测试

RBAC + 数据范围（对照 §10）：

| 维度 | 测试 | 来源 |
|------|------|------|
| API 权限保护 | 5 组端点各自 `RequirePermission` | 各 test_*.py 的 requires_permission |
| **数据范围过滤（room）** | room 范围仅见本机房组织/人员 | test_org_units.py, test_persons.py |
| **无数据范围 → 空列表** | 有权限但无 scope 返回 [] | test_org_units.py |
| **全局范围（all）→ 不过滤** | super-admin 见全部 | 运行环境实测 + fixtures |
| self 范围 → 按绑定人员所属机房 | resolve_scoped_org_unit_ids 支持 | services/auth.py |

数据范围实现（本 Phase 补充）：
- `resolve_scoped_org_unit_ids(db, user)`：`all`→None（不过滤）；`room/station`→该组织及后代；`self`→用户绑定人员所属机房；无 scope→空集合。
- `list_org_units` / `list_persons` 接受 `org_unit_ids` 过滤参数。
- `org-units` / `org-units/tree` / `persons` 列表端点接入。
- CLI `create-admin` 自动为管理员分配 `all` 数据范围。

## 性能检查

| 指标 | 结果 |
|------|------|
| 登录请求 | ~214ms（含 bcrypt + DB） |
| org-units 列表 | ~8ms |
| holidays 列表 | ~9ms |
| 后端测试总耗时 | ~66s（165 tests, SQLite） |
| 前端测试总耗时 | ~3.5s（99 tests） |

说明：
- 数据范围过滤中 `_descendant_org_unit_ids` 一次性加载组织表在内存构树，组织规模小无瓶颈；后续组织量大可改递归 CTE。
- 未发现明显性能瓶颈。

## 补充遗漏功能

本次 Phase 验收发现并处理的问题：

| 发现 | 状态 | 说明 |
|------|------|------|
| **org_unit 重复 code 返回 500** | 已修复 | `create_org_unit` 增加服务层查重 → 409 `STATE_CONFLICT` |
| **person 重复 code 返回 500** | 已修复 | `create_person` 增加服务层查重 → 409 `STATE_CONFLICT` |
| **org_unit 无效 parent_id 未校验** | 已修复 | create/update 校验 parent 存在 → 404；自引用 → 409 |
| **删除组织未校验人员引用** | 已修复 | `check_org_unit_referenced` 增加 person 引用检查 |
| **停用组织未校验在职人员** | 已修复 | update 停用时校验在职人员 → 409 |
| **列表端点无数据范围过滤** | 已修复 | org-units/persons 接入数据范围（§10 要求） |
| **管理员无数据范围导致看不到数据** | 已修复 | CLI create-admin 自动分配 `all` scope |
| **org_unit 负责人 manager_person_id 无法维护** | 已修复 | §8.2 定义了 manager_person_id、原型 §7.18 要求"绑定负责人"。补充 create/update API（含负责人存在性校验、绑定/解绑语义）及前端 OrgUnitView 负责人下拉与详情展示 |

## 设计字段一致性核对（§8.2 / §8.3 / §8.8）

| 表 | 设计字段 | 模型 | create/update API | 结论 |
|----|---------|------|-------------------|------|
| org_unit | parent_id, code, name, type, manager_person_id, status, sort_order | 全部 | 全部（负责人已补充） | ✅ |
| person | org_unit_id, code, name, person_type, phone, participate_schedule, rotation_order, status, remark | 全部 | 全部 | ✅ |
| shift_def | code, name, start_time, end_time, display_order, status | 全部 | 全部 | ✅ |
| shift_rule | org_unit_id, code, name, station_type, persons_per_shift, rule_type, status, remark | 全部 | 全部 | ✅ |
| shift_rule_item | rule_id, group_type, sequence_no, shift_code, repeat_count, remark | 全部 | 全部 | ✅ |
| holiday_calendar | holiday_date, holiday_name, year, is_legal, status | 全部（另含 remark） | 全部 | ✅ |

> start_time/end_time 设计标注为 time 类型，实现用 `varchar(5)`（HH:MM）承载，语义等价、便于跨 SQLite/PG 测试，不影响业务。

## 验收结果

命令（全部经 Docker Compose）：

```bash
# 后端
docker compose ... run --rm --no-deps backend ruff check backend/app   # All checks passed
docker compose ... run --rm --no-deps backend mypy                     # 50 files, 0 issues
docker compose ... run --rm --no-deps backend pytest                   # 169 passed
# 迁移双向
docker compose ... run --rm --no-deps backend alembic upgrade head / downgrade -1 / upgrade head  # OK

# 前端
npm --prefix frontend run lint         # 0 errors
npm --prefix frontend run type-check   # 0 errors
npm --prefix frontend run test -- --run  # 99 passed
npm --prefix frontend run build        # ✓ built
```

| 检查项 | 结果 |
|--------|------|
| 后端测试 | 169 passed, 0 failed |
| 前端测试 | 99 passed, 0 failed |
| 后端 lint (ruff) | 0 errors |
| 后端 type-check (mypy) | 0 issues (50 files) |
| 前端 lint (eslint) | 0 errors |
| 前端 type-check (vue-tsc) | 0 errors |
| 前端 build | ✅ |

M2-P2 各 Task 后端测试数：org_units 22、persons 11、shifts 12、shift_rules 18、holidays 16。

## 结论

`M2-P2 组织、人员与基础规则` 满足本 Phase 完成标准：

- 多台站、多机房组织树可维护，编码唯一、层级校验、引用保护完整。
- 值机员及非值机人员档案可维护，编码唯一、组织归属校验完整。
- 班次定义、排班规则（含轮班序列明细）、节假日与固定标准可维护。
- 列表端点按 RBAC + 数据范围（self/room/station/all）过滤，符合 §10 权限模型。
- 4 个前端页面完成基础交互、表单校验、状态与权限禁用逻辑。
- API 统一响应格式、异常码、分页参数符合总体设计。
- 本 Phase 范围内接口联调、异常测试、边界测试、权限测试、性能检查已完成，发现问题已全部修复。

**至此 M2-P2 全部 9 个 Task 验收完毕，M2 里程碑结束，可进入 M3（排班核心链路）开发。**
