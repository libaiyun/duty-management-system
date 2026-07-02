# M1-P1 Phase 验收说明

## 验收范围

当前 Phase：`M1-P1 后端工程基础`。

依据：

- `docs/design/03-总体设计.md`
- `docs/design/04-开发实施计划.md`

本次验收只覆盖 M1-P1 已完成内容：

- FastAPI 后端工程结构。
- 配置与环境变量管理。
- SQLAlchemy 与 Alembic 集成。
- 统一响应、分页和异常处理。
- 后端测试基础。

不覆盖范围：

- 认证登录、JWT 签发、RBAC、数据范围，属于 `M2-P1`。
- 业务 API 和业务模型，属于后续 Milestone。
- Docker Compose 联调，属于 `M1-P3`。
- 前端 API client，属于 `M1-P2-T3`。

## 接口联调

已验证：

- `GET /api/v1/health` 可通过 FastAPI TestClient 调用。
- 健康检查返回统一成功响应结构，包含 `trace_id`。
- 成功、分页和错误响应均包含 `code`、`message`、`trace_id`。
- 应用可正常创建，并挂载测试配置。
- OpenAPI 由 FastAPI 自动生成，路由前缀使用 `/api/v1`。

测试覆盖：

- `backend/tests/test_health.py`
- `backend/tests/test_test_fixtures.py`

## 异常测试

已验证统一错误响应：

| 场景 | HTTP 状态 | code |
| --- | --- | --- |
| 参数错误 | 400 | `VALIDATION_ERROR` |
| 未登录 | 401 | `UNAUTHORIZED` |
| 无权限 | 403 | `FORBIDDEN` |
| 不存在 | 404 | `NOT_FOUND` |
| 状态冲突 | 409 | `STATE_CONFLICT` |
| 业务校验失败 | 422 | `BUSINESS_RULE_FAILED` |
| 未预期异常 | 500 | `INTERNAL_ERROR` |

已验证：

- `HTTPException` 统一转换。
- `HTTPException` headers 透传，例如 `WWW-Authenticate`。
- 非标准 HTTP 状态码不会破坏异常处理器。
- 请求参数校验错误返回 400，并包含 `details`。
- 500 响应隐藏内部异常信息，仅返回通用文案和 `trace_id`。

测试覆盖：

- `backend/tests/test_exception_handlers.py`

## 边界测试

已验证：

- `page` 从 1 开始，小于 1 返回 400。
- `page_size` 默认 20。
- `page_size` 最大 200，符合总体设计。
- `page_size=200` 可用。
- `page_size=201` 返回 400。
- 分页响应正确计算 `total_pages`。
- 生产环境缺少关键配置会报明确配置错误。
- 生产环境禁止使用占位 JWT 密钥。
- Alembic 可执行到 `head`。
- 测试 session 支持回滚和被测代码内部 `commit()`。

测试覆盖：

- `backend/tests/test_config.py`
- `backend/tests/test_database.py`
- `backend/tests/test_exception_handlers.py`
- `backend/tests/test_test_fixtures.py`

## 权限测试

当前 Phase 尚未实现认证、RBAC、数据范围和业务权限判断，这些内容属于 `M2-P1`。

当前已验证权限相关基础能力：

- 403 错误格式符合总体设计。
- `ForbiddenError` 可统一转换为：

```json
{
  "code": "FORBIDDEN",
  "message": "无权限",
  "trace_id": "..."
}
```

后续 `M2-P1` 需要在此基础上补充：

- 登录态校验。
- API 权限校验。
- 数据范围过滤。
- 权限失败的 401/403 端到端测试。

## 性能检查

执行轻量健康检查性能探测：

```text
requests=500
total_seconds=1.496589
avg_ms=2.993
```

说明：

- 该结果基于 FastAPI TestClient 内存调用，不代表生产网络性能。
- 当前 Phase 只用于发现明显慢启动、异常处理或响应包装带来的基础性能问题。
- 未发现明显性能异常。

后续性能检查应在 `M1-P3` Docker Compose 环境和业务 API 完成后继续补充。

## 补充遗漏功能

本次检查发现并修复：

- `page_size` 最大值原实现为 100，与总体设计 `最大 200` 不一致。
- 已修改为 200。
- 已补充 `page_size=200` 和 `page_size=201` 测试。
- 已同步更新 `M1-P1-T4` 开发说明。
- 成功响应原先缺少 `trace_id`，与总体设计 9.2 不一致。
- 已为 `ApiResponse` 补充 `trace_id`，并补充健康检查、分页成功响应和测试夹具接口断言。

## 验收结果

命令：

```bash
pytest
```

结果：

```text
30 passed, 1 warning
```

剩余 warning 来自 FastAPI/TestClient 依赖链：

```text
StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated
```

该 warning 不影响当前 Phase 功能，后续依赖升级或 FastAPI 推荐方案变化时再处理。

## 结论

`M1-P1 后端工程基础` 当前满足本 Phase 完成标准：

- 后端可启动。
- 健康检查接口可用。
- 配置可从环境变量读取。
- 数据库基础和迁移链路可用。
- API 统一响应、分页和异常格式可用。
- 测试基础可复用。
- 当前 Phase 范围内的接口联调、异常测试、边界测试、权限基础错误格式和轻量性能检查已完成。
