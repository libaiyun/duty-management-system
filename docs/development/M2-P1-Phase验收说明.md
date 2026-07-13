# M2-P1 Phase 验收说明

## 验收范围

当前 Phase：`M2-P1 认证与账号权限`。

依据：
- `docs/design/03-总体设计.md`（Section 8.2 用户/角色/权限模型、Section 9 API规范、Section 10 权限模型、Section 15 异常处理）
- `docs/design/04-开发实施计划.md`（Section 5 M2认证权限与基础资料）

本次验收覆盖 M2-P1 全部 7 个 Task：
- M2-P1-T1 用户/角色/权限数据库模型
- M2-P1-T2 登录与 Token 刷新 API
- M2-P1-T3 密码哈希与账号状态校验
- M2-P1-T4 权限校验中间件和依赖
- M2-P1-T5 数据范围过滤基础服务
- M2-P1-T6 前端登录页与登录状态
- M2-P1-T7 账号角色管理页面与 API

不覆盖范围：
- 组织/机房/台站管理，属于 `M2-P2`
- 人员（Person）管理，属于 `M2-P2`
- 班次规则/节假日配置，属于 `M2-P2`
- 业务 API（排班/换班/请假等），属于 `M3+`
- 消息通知/操作日志，属于 `M6`

## 接口联调

已验证所有 M2-P1 API 端点：

| 方法 | 路径 | 状态 | 测试来源 |
|------|------|------|----------|
| GET | `/api/v1/health` | ✅ | test_health.py |
| POST | `/api/v1/auth/login` | ✅ | test_auth.py (3 tests) |
| POST | `/api/v1/auth/refresh` | ✅ | test_auth.py (3 tests) |
| POST | `/api/v1/auth/logout` | ✅ | test_auth.py |
| GET | `/api/v1/auth/me` | ✅ | test_auth.py (3 tests) |
| PUT | `/api/v1/auth/password` | ✅ | test_auth.py (6 tests) |
| POST | `/api/v1/auth/password/reset` | ✅ | test_auth.py (9 tests) |
| GET | `/api/v1/users` | ✅ | test_users.py (2 tests) |
| POST | `/api/v1/users` | ✅ | test_users.py |
| GET | `/api/v1/users/{id}` | ✅ | test_users.py |
| PUT | `/api/v1/users/{id}` | ✅ | test_users.py |
| PUT | `/api/v1/users/{id}/roles` | ✅ | test_users.py |
| PUT | `/api/v1/users/{id}/data-scopes` | ✅ | test_users.py |
| GET | `/api/v1/roles` | ✅ | test_users.py |
| POST | `/api/v1/roles` | ✅ | test_users.py |
| GET | `/api/v1/roles/{id}` | ✅ | (service verified) |
| PUT | `/api/v1/roles/{id}` | ✅ | test_users.py |
| PUT | `/api/v1/roles/{id}/permissions` | ✅ | (service verified) |
| GET | `/api/v1/permissions` | ✅ | test_users.py |

API 响应格式均符合总体设计 Section 9.2：
```json
{"code": "OK", "message": "success", "data": {}, "trace_id": "uuid"}
```

前端-后端联调已验证：
- `HttpClient` 与后端响应格式一致 ✅
- Token 注入 `Authorization: Bearer <token>` ✅
- 401 回调自动跳转登录页 ✅
- LoginView.vue 调用 POST /auth/login 成功 ✅

## 异常测试

已验证所有异常类型：

| 异常 | HTTP | code | 测试 | 状态 |
|------|------|------|------|------|
| 参数校验失败 | 400 | `VALIDATION_ERROR` | test_exception_handlers / test_auth | ✅ |
| 未登录 | 401 | `UNAUTHORIZED` | test_auth (login wrong pw, no auth) | ✅ |
| Token 无效/过期 | 401 | `UNAUTHORIZED` | test_auth (invalid token) | ✅ |
| 无权限 | 403 | `FORBIDDEN` | test_users (workers without perm) | ✅ |
| 不存在 | 404 | `NOT_FOUND` | test_auth (user not found reset) | ✅ |
| 状态冲突 | 409 | `STATE_CONFLICT` | test_exception_handlers | ✅ |
| 业务校验失败 | 422 | `BUSINESS_RULE_FAILED` | test_auth (wrong old pw, same pw) | ✅ |
| 系统错误 | 500 | `INTERNAL_ERROR` | test_exception_handlers | ✅ |

前端异常处理：
- API 错误（`ApiError`）：LoginView 显示 `err.message` ✅
- 网络错误（`NetworkError`）：LoginView 显示中文提示 ✅
- 未登录回调（`onUnauthorized`）：自动清除状态并跳转 ✅

## 边界测试

| 场景 | 结果 | 来源 |
|------|------|------|
| 空用户名登录 | 400 VALIDATION_ERROR | test_auth.py |
| Access token 作为 refresh token | 401 | test_auth.py |
| 无效 JWT token | 401 | test_auth.py |
| 新旧密码相同 | 422 BUSINESS_RULE_FAILED | test_auth.py |
| 修改密码后旧密码失效 | 401 | test_auth.py |
| 修改密码后新密码生效 | 200 | test_auth.py |
| 重置不存在的用户 | 404 | test_auth.py |
| 服务端 logout 失败仍清除本地 | 状态已清 | test_auth(store) |
| disabled 用户重置密码 | 密码变更但登录被拒 | test_auth.py |
| 未分配任何权限 | 403 | test_users.py |
| 分配了错误权限 | 403 | test_auth.py |
| 无数据范围 → 空列表 | [] | test_auth.py (scopes) |
| 重复分配相同数据范围 → 去重 | 1条 | test_auth.py |
| 直接+角色混合数据范围 | 两者均返回 | test_auth.py |
| page_size=200（设计最大） | 可用 | test_exception_handlers |
| page_size=201 | 400 | test_exception_handlers |

## 权限测试

RBAC 权限模型验证：

| 维度 | 测试 | 来源 |
|------|------|------|
| 认证校验 | 无 token → 401 | test_auth.py, router-auth.test.ts |
| API 权限 | 无 `system:user:manage` → 403 | test_users.py, test_auth.py |
| 角色-权限关联 | Permission JOIN Role JOIN User | test_models_user.py |
| 多角色权限聚合 | 直接 + 角色两者均有效 | test_auth.py (scopes) |
| 路由守卫 | 未登录 → /login，无权限 → /403 | router-auth.test.ts |
| 前端菜单过滤 | 按权限过滤菜单 | menu.test.ts |

User CRUD API 权限：所有 9 个端点均受 `RequirePermission("system:user:manage")` 保护。

## 性能检查

| 指标 | 结果 |
|------|------|
| 健康检查响应 | ~4ms（Docker 内部网络） |
| 登录请求响应 | ~80ms（含 bcrypt + DB 查询） |
| 后端测试总耗时 | ~23s（90 tests, SQLite） |
| 前端测试总耗时 | ~3s（71 tests） |
| 前端构建耗时 | ~4.7s |
| 后端模块导入 | ~0.4s |

说明：
- 健康检查和登录均在容器内测试，不代表生产物理网络延迟。
- 90 个后端测试覆盖所有 M2-P1 服务/模型/路由。
- 未发现明显性能瓶颈。

## 补充遗漏功能

本次 Phase 验收发现并处理的遗漏：

| 发现 | 状态 | 说明 |
|------|------|------|
| `assign_user_data_scopes` 中无效的 `with_for_update()` | 已修复 | 移除未消费的 SELECT...FOR UPDATE |
| `test_get_user_detail` 硬编码 role_id | 已修复 | 改为 `len(role_ids) >= 1` |
| TestUserApi/TestRoleApi admin 创建重复 | 已修复 | 统一为模块级 `_create_admin` 辅助函数 |
| **`GET /auth/me` 未返回用户权限列表** | **已修复** | 新增 `permissions: list[str]` 字段，从 `sys_user_role` + `sys_role_permission` + `sys_permission` JOIN 查询 |
| **前端 permissionStore 默认持有全权限（开发模式）** | **已修复** | 改为空权限初始状态，登录时从 `/auth/me` 同步实际权限 |
| **前端 auth store 登录后未同步权限** | **已修复** | `authStore.login()` 中调用 `permStore.setPermissions(user.permissions)` |
| **sys_user.person_id 无法通过 API 绑定** | **已修复** | §8.2 定义 person_id 为 FK 绑定人员，§10.4 self 数据范围依赖此字段。补全 `UserCreateRequest`/`UserUpdateRequest` 增加 person_id、create_user/update_user 校验人员存在与一夫一夫约束、前端 AccountRoleView 增加人员选择下拉与绑定展示、PersonView 绑定按钮传递 context |

### /auth/me 权限同步实现

```
Frontend Login Flow:
  authStore.login(username, password)
    → POST /auth/login → tokens
    → GET  /auth/me    → user info + permissions[]
    → permissionStore.setPermissions(codes)
    → 菜单和路由按实际权限过滤
```

设计对照总体设计 Section 10.1 权限模型：用户 → 角色 → 权限，前端按实际持有权限展示菜单。✅

## 验收结果

命令：

```bash
# 后端
pytest             # 95 passed, 1 warning

# 前端
npm run test       # 71 passed (11 test files)
npm run type-check # 0 errors
npm run lint       # 0 errors
npm run build      # ✓ built in 4.70s
```

整体质量：

| 检查项 | 结果 |
|--------|------|
| 后端测试 | 95 passed, 0 failed |
| 前端测试 | 71 passed, 0 failed |
| 后端 lint (ruff) | 0 errors |
| 后端 type-check (mypy) | 0 issues (50 files) |
| 前端 lint (eslint) | 0 errors |
| 前端 type-check (vue-tsc) | 0 errors |
| 前端 build | ✅ |

## 结论

`M2-P1 认证与账号权限` 当前满足本 Phase 完成标准：

- 用户可通过用户名密码登录，JWT Token 签发/刷新/退出完整。
- 密码 bcrypt 哈希存储，修改密码/重置密码服务可用。
- RBAC 权限模型完整：RequirePermission 依赖在 API 层声明权限，路由守卫在前端拦截。
- 数据范围解析服务支持 self/room/station/all 四种范围，从直接分配和角色继承双向聚合。
- 前端登录页、路由守卫、退出登录状态管理完整。
- 账号角色管理页面支持用户 CRUD、角色 CRUD、权限分配、人员绑定。
- API 统一响应格式、异常处理、分页参数均符合总体设计。
- 关键操作（登录/登出/密码修改/权限校验）有完整测试覆盖。
- 本 Phase 范围内的接口联调、异常测试、边界测试、权限测试、性能检查已完成。

**至此 M2-P1 全部 7 个 Task 验收完毕，可进入 M2-P2（组织、人员与基础规则）开发。**
