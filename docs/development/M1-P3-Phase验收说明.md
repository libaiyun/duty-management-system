# M1-P3 Phase 验收说明

## 验收范围

当前 Phase：`M1-P3 本地部署与开发工具`。

依据：

- `docs/design/03-总体设计.md`（Section 16 部署方案）
- `docs/design/04-开发实施计划.md`

本次验收覆盖 M1-P3 全部已完成 Task：

- M1-P3-T1 Docker Compose 开发环境
- M1-P3-T2 Nginx 反向代理开发配置
- M1-P3-T3 代码质量工具
- M1-P3-T4 基础 CI 脚本

不覆盖范围：

- Celery Worker / Beat 容器，属于 `M6-P3-T1`。
- 生产环境 Compose 和 HTTPS，属于 `M6-P3-T5`。
- 文件存储卷（export/backup/logs），属于 `M5-P3`。
- 外部 CI 平台配置（GitHub Actions 等），属于后续部署阶段。

## 接口联调

已验证全链路连通性：

| 端点 | 方式 | 状态 | 结果 |
|------|------|------|------|
| Backend 健康检查 | `curl localhost:8000/api/v1/health` | ✅ | `{"code":"OK","data":{"status":"ok"}}` |
| 前端静态资源 | `curl localhost/` | ✅ | HTTP 200, text/html, 423B |
| API 代理 | `curl localhost/api/v1/health` | ✅ | `{"code":"OK"}` |
| PostgreSQL 连接 | `psql -c "SELECT 1"` | ✅ | 查询成功 |
| Redis 连接 | `redis-cli ping` | ✅ | PONG |
| 数据库迁移 | `alembic upgrade head` | ✅ | `-> 202607020001` |
| 后端测试（容器内） | `pytest` | ✅ | 30 passed |

服务拓扑验证：

```text
Browser -> localhost:80 (nginx)
  -> /          -> frontend/dist (SPA, try_files /index.html)
  -> /api/v1/*  -> http://backend:8000/api/v1/*
                    -> db:5432 + redis:6379
```

## 异常测试

已验证异常场景：

| 场景 | 预期 | 结果 |
|------|------|------|
| 无效 API 路径 | HTTP 404 | ✅ 404 |
| 不存在的前端路由 | SPA fallback 返 index.html | ✅ HTTP 200, index.html |
| Backend 停止 | 健康检查标记 unhealthy | ✅ `unhealthy` |
| Backend 恢复 | 健康检查重新标记 healthy | ✅ `healthy` |
| 缺失环境变量（prod） | `ConfigError` | ✅ `M1-P1-T2` 已验证 |
| 网络连接失败 | `NetworkError` | ✅ `M1-P2-T3` 已验证 |

## 边界测试

已验证边界场景：

| 场景 | 预期 | 结果 |
|------|------|------|
| DB 端口隔离 | 不暴露宿主机端口 | ✅ `invalid IP:0`（仅容器网络内） |
| Redis 端口隔离 | 不暴露宿主机端口 | ✅ `invalid IP:0`（仅容器网络内） |
| 仅 nginx 暴露 80 | nginx:80 对外 | ✅ `0.0.0.0:80` |
| 数据卷持久化 | 容器重启后数据不丢失 | ✅ psql 查询成功 |
| 前端 dist 挂载 | nginx 读取只读卷 | ✅ HTTP 200 |
| 代码热重载（dev） | 修改后自动重载 | ✅ `--reload` 模式 |
| 菜单无权限时过滤 | 仅显示工作台 | ✅ `M1-P2-T4` 已验证 |
| Docker 构建缓存 | 依赖层复用 | ✅ pyproject.toml 单独 COPY |

## 权限测试

当前 Phase 权限配置已验证：

- Nginx 配置为只读挂载（`:ro`），生产环境同理。
- Backend 健康检查不要求认证，前端/API 均可访问。
- 后端 `app.state.settings` 正确加载开发环境配置。
- 认证和 RBAC 权限不在 M1-P3 范围（属于 `M2-P1`）。

## 性能检查

### 镜像大小

```text
duty-management-system-backend:latest  716 MB
```

说明：包含 Python 3.13、全部依赖（FastAPI、SQLAlchemy、psycopg、pytest、mypy 等）、gcc 编译工具链。后续生产镜像可通过多阶段构建减少体积。

### 运行时资源

| 容器 | CPU | 内存 |
|------|-----|------|
| nginx | 0.00% | 15.6 MiB |
| backend | 0.53% | 58.3 MiB |
| db | 0.03% | 35.3 MiB |
| redis | 0.19% | 7.7 MiB |

### API 响应时间

```text
10 次健康检查请求平均: 2.0 ms（Docker 内部网络）
前端页面首次字节: 0.7 ms
```

说明：基于 Docker 网络内部调用，不代表生产物理网络延迟。当前 Phase 未发现明显性能瓶颈。

### CI 脚本执行时间

```text
Backend lint:        < 1s
Backend type-check:  < 1s
Backend test:        0.4s (30 tests)
Frontend lint:       < 1s
Frontend type-check: ~2s
Frontend build:      ~5s
Total CI:            ~15s
```

## 补充遗漏功能

本次 Phase 未发现需要补充的功能。与总体设计 Section 16 的对照：

| 设计项 | 状态 |
|--------|------|
| Docker Compose 编排 6 个服务 | ✅ backend + db + redis + nginx（worker/scheduler 属 M6） |
| 独立 bridge 网络 `duty_net` | ✅ |
| 仅 nginx 暴露宿主机端口 | ✅ |
| DB/Redis 仅容器网络内访问 | ✅ |
| 健康检查（pg_isready, redis-cli, /api/v1/health） | ✅ |
| 数据持久化卷 | ✅ postgres_data, redis_data |
| 环境分离（dev overlay） | ✅ |
| Nginx SPA fallback + API 代理 | ✅ |
| proxy_read_timeout 配置 | ✅ 120s |
| 后端代码质量工具 | ✅ flake8/black/mypy |
| 前端代码质量工具 | ✅ eslint/vue-tsc |
| 统一 CI 检查脚本 | ✅ check.sh |

## 验收结果

命令：

```bash
bash check.sh
```

结果：

```text
✓ Backend lint (flake8)       — 0 errors
✓ Backend type-check (mypy)   — Success: no issues found in 24 source files
✓ Backend test (pytest)       — 30 passed, 1 warning
✓ Frontend lint (eslint)      — 0 errors
✓ Frontend type-check (tsc)   — 0 errors
✓ Frontend build (vite)       — ✓ built in 4.64s

All CI checks passed
```

## 结论

`M1-P3 本地部署与开发工具` 当前满足本 Phase 完成标准：

- Docker Compose 可启动 backend、db、redis、nginx。
- 后端可访问数据库和 Redis，健康检查通过。
- Nginx 可代理前端静态资源和 `/api`，本地完整访问链路可用。
- 后端 lint/format/type-check 命令可运行。
- 前端 lint/type-check/build 命令可运行。
- 统一 CI 脚本覆盖后端测试、前端构建、类型检查。
- 当前 Phase 范围内的接口联调、异常测试、边界测试、权限校验、性能检查已完成。

**至此 M1（工程基础与开发框架）全部 4 个 Phase 验收完毕，可进入 M2（认证权限与基础资料）开发。**
