# M1-P2 Phase 验收说明

## 验收范围

当前 Phase：`M1-P2 前端工程基础`。

依据：

- `docs/design/02-原型设计.md`
- `docs/design/03-总体设计.md`
- `docs/design/04-开发实施计划.md`

本次验收覆盖 M1-P2 全部已完成 Task：

- M1-P2-T1 初始化前端工程结构
- M1-P2-T2 Web 后台基础布局
- M1-P2-T3 API 请求封装与错误处理
- M1-P2-T4 动态路由与权限菜单骨架

不覆盖范围：

- 认证登录、JWT 签发、Token 刷新，属于 `M2-P1`。
- 后端 API 真实联调（后端在本环境不可用），属于 `M1-P3` Docker Compose 开发环境。
- 业务页面、表格、表单、审批流程，属于后续业务 Task。
- 角色权限矩阵、数据范围过滤，属于 `M2-P1`。
- 日志审计、通知、运维，属于 `M6`。

## 接口联调

已验证前端与后端 API 规范的兼容性：

| 后端规范（03-总体设计 Section 9） | 前端实现 | 状态 |
|----------------------------------|----------|------|
| API 前缀 `/api/v1` | `HttpClient.baseUrl` 默认 `/api/v1` | 一致 |
| 分页参数 `page`（从 1 开始）、`page_size`（默认 20，最大 200） | `PageParams` 类型 + `getPage()` 方法自动拼接 query | 一致 |
| 成功响应 `{ code, message, data, trace_id }` | `ApiResponse<T>` | 一致 |
| 错误响应 `{ code, message, trace_id, details? }` | `ErrorResponse` + `ApiError` | 一致 |
| 分页响应 `{ items, total, page, page_size, total_pages }` | `PageResponse<T>` | 一致 |
| 认证方式 `Authorization: Bearer <token>` | `getToken` 回调自动注入 | 一致 |
| Content-Type `application/json` | POST/PUT 自动设置 | 一致 |

HttpClient 方法覆盖：

```text
GET     -> httpClient.get<T>(path)
POST    -> httpClient.post<T>(path, body)
PUT     -> httpClient.put<T>(path, body)
DELETE  -> httpClient.delete<T>(path)
GET分页 -> httpClient.getPage<T>(path, params)
```

测试覆盖：

- `frontend/tests/http.test.ts`（15 tests）

## 异常测试

已验证前端对后端错误场景的处理：

| 场景 | HTTP 状态 | 处理方式 | 测试覆盖 |
|------|-----------|----------|----------|
| 参数校验失败 | 400 | `ApiError`，附带 `details` | ✅ |
| 未登录 | 401 | `ApiError` + `onUnauthorized` 回调 | ✅ |
| 无权限 | 403 | 路由守卫重定向 `/403` | ✅ |
| 不存在 | 404 | `ApiError`，含 `code`/`message`/`traceId` | ✅ |
| 状态冲突 | 409 | `ApiError` | ✅ |
| 业务校验失败 | 422 | `ApiError` | ✅ |
| 服务器错误 | 500 | `ApiError`，通用错误 | ✅ |
| 网络连接失败 | N/A | `NetworkError` | ✅ |
| 非 JSON 错误响应 | N/A | `ApiError` 容错（code='UNKNOWN'） | ✅ |
| 非 Error 异常 | N/A | `NetworkError` 中文兜底消息 | ✅ |

HttpClient 业务错误检测（`code !== 'OK'` 时抛出 `ApiError`）也已通过测试。

测试覆盖：

- `frontend/tests/http.test.ts`（15 tests 中 8 个异常测试）

## 边界测试

已验证边界和极端场景：

- 路由无 `meta.permission` 时通过守卫（工作台首页、403 页）。
- `/403` 路由无权限码，避免无限循环。
- 菜单过滤：全部权限时显示完整菜单（9 组）。
- 菜单过滤：无权限时仅显示工作台。
- 菜单过滤：部分权限时仅显示匹配的子项，无子项的分组隐藏。
- 菜单项路径不重复。
- 所有叶子菜单项（除工作台）均分配了唯一权限码。
- 所有叶子路由均注册了 `component`。
- 父路由自动重定向到第一个子路由。
- 面包屑支持多级路径（嵌套路由 matched 记录）。
- 侧边栏折叠/展开切换样式正常。
- 未知路径通过 catch-all `/:pathMatch(.*)*` 匹配到 404 页面。
- 权限 store 默认拥有全部 22 个权限码，支持 `setPermissions`/`clearPermissions`。
- `getToken` 返回空值时不注入 `Authorization` header。
- `getToken` 返回 token 时注入 `Bearer <token>`。

测试覆盖：

- `frontend/tests/router.test.ts`（8 tests）
- `frontend/tests/menu.test.ts`（10 tests）
- `frontend/tests/permission.test.ts`（4 tests）
- `frontend/tests/breadcrumb.test.ts`（2 tests）
- `frontend/tests/app-shell.test.ts`（6 tests）

## 权限测试

当前 Phase 实现了权限菜单过滤和路由守卫骨架：

- **路由守卫**：`router.beforeEach` 检查 `to.meta.permission`，无权限时重定向到 `/403`。
- **菜单过滤**：`filterMenuByPermission()` 根据 `PermissionCode` 集合过滤菜单树。
- **权限 store**：`usePermissionStore` 维护当前用户权限集合，默认全权限（开发环境）。
- **403 页面**：`ForbiddenView` 显示 403 文案和「返回工作台」按钮。
- **404 页面**：`NotFoundView` 处理未知路径，显示 404 文案和「返回工作台」按钮。
- **权限码规范**：22 个权限码遵循 `module:resource:action` 格式。

后续 `M2-P1` 需要在此基础上补充：

- 登录成功后从后端获取权限列表并调用 `permissionStore.setPermissions()`。
- `onUnauthorized` 回调绑定到 Router 跳转登录页。
- 数据范围过滤（本人/本机房/本台站/全部）。

测试覆盖：

- `frontend/tests/permission.test.ts`（4 tests）
- `frontend/tests/menu.test.ts`（4 filter tests）
- `frontend/tests/forbidden.test.ts`（2 tests）
- `frontend/tests/router.test.ts`（3 permission-related tests）

## 性能检查

### 构建性能

```text
Build time: ~4.4s（3 次平均）
Modules transformed: 1625
```

### 测试性能

```text
Test count: 51（8 files）
Avg duration: ~2.26s（3 次平均）
Per-test: ~44ms
```

### 构建产物大小

| 文件 | 大小 | Gzip |
|------|------|------|
| HTML | 0.42 KB | 0.32 KB |
| CSS (Element Plus + app) | 353 KB | 48 KB |
| JS (Vue + Element Plus + app) | 1.07 MB | 346 KB |
| 总计 | 1.4 MB | ~394 KB |

说明：

- 构建产物大小主要来自 Element Plus 全量引入（包含所有组件样式和 JS）。
- 后续可按需引入 Element Plus 组件或使用 `unplugin-element-plus` 减少体积。
- 当前 Phase 仅建立工程基础，体积优化属于后续阶段。

## 补充遗漏功能

本次 Phase 验收发现并修复：

- **缺少 catch-all 路由**：未知路径导航时 Vue Router 静默失败，无法给用户反馈。
- 已新增 `NotFoundView.vue`（404 页面含返回工作台按钮）。
- 已新增 `/:pathMatch(.*)*` catch-all 路由，无权限限制。
- 已补充对应测试。
- **`collectRoutes` 函数**在 menu.ts 中定义但未被任何文件使用，已移除。
- **`UserFilled` icon** 在 menu.ts 中导入但未使用，已移除。

## 验收结果

命令：

```bash
cd frontend
npm run test
```

结果：

```text
✓ tests/http.test.ts          (15 tests)
✓ tests/store.test.ts         (4 tests)
✓ tests/permission.test.ts    (4 tests)
✓ tests/breadcrumb.test.ts    (2 tests)
✓ tests/menu.test.ts          (10 tests)
✓ tests/router.test.ts        (8 tests)
✓ tests/forbidden.test.ts     (2 tests)
✓ tests/app-shell.test.ts     (6 tests)

Test Files  8 passed (8)
     Tests  51 passed (51)
```

构建：

```text
vue-tsc --noEmit  -> passed
vite build         -> ✓ built in 4.37s
```

## 结论

`M1-P2 前端工程基础` 当前满足本 Phase 完成标准：

- 前端工程可启动（Vue 3 + TypeScript + Vite）。
- Web 后台布局可用（顶部栏、左侧菜单、面包屑、内容区）。
- 侧边栏菜单按原型设计覆盖全部 9 组 23 个页面。
- HTTP 客户端支持 GET/POST/PUT/DELETE、Token 注入、分页查询、异常处理。
- 路由守卫和权限菜单过滤骨架可用。
- 403/404 错误页面可用。
- 所有 API 类型定义与后端规范一致。
- 51 个单元测试全覆盖，零失败。
- TypeScript 类型检查通过，构建无错误。
- 当前 Phase 范围内的接口联调、异常测试、边界测试、权限测试和轻量性能检查已完成。
