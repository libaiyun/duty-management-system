# 广播电视台站值班管理系统

后端使用 FastAPI、SQLAlchemy 和 PostgreSQL，前端使用 Vue 3、TypeScript 和 Element Plus。开发环境通过 Docker Compose 运行。

## 开发环境

所有本地 Docker Compose 命令都应同时加载基础和开发覆盖配置：

```bash
COMPOSE='docker compose -f docker-compose.yml -f docker-compose.dev.yml'
```

测试环境使用独立、无持久化的 PostgreSQL 服务，不复用开发数据库：

```bash
TEST_COMPOSE='docker compose -f docker-compose.yml -f docker-compose.test.yml'
```

启动开发环境：

```bash
$COMPOSE up -d --build
```

停止开发环境：

```bash
$COMPOSE down
```

## 日常数据库迁移

修改 SQLAlchemy 模型后，先生成 migration，检查生成文件内容无误，再升级数据库：

```bash
$COMPOSE exec backend alembic revision --autogenerate -m "迁移说明"
$COMPOSE exec backend alembic upgrade head
```

常用检查命令：

```bash
$COMPOSE exec backend alembic current
$COMPOSE exec backend alembic heads
$COMPOSE exec backend alembic history
```

仅在确认最近一次 migration 可回退时执行降级：

```bash
$COMPOSE exec backend alembic downgrade -1
```

## 清空并重建开发数据库

以下操作会删除 PostgreSQL 和 Redis 的 Docker volumes，所有本地数据库数据都会丢失。仅在不需要保留本地数据时执行：

```bash
$COMPOSE down -v
$COMPOSE up -d --build
$COMPOSE exec backend alembic upgrade head
```

## 合并为初始 Migration

仅在项目尚未发布、没有需要保留的数据库或迁移兼容性要求时，才可以将多份历史 migration 合并为一份初始 migration。不要使用 `alembic merge`，该命令只用于处理分叉的迁移链，不会合并历史变更。

1. 确认现有 migration 文件不再需要保留。
2. 删除迁移文件和本地 Docker volumes。
3. 基于当前全部 SQLAlchemy 模型生成新的初始 migration。
4. 在空数据库上执行升级并验证。

```bash
rm backend/alembic/versions/*.py

$COMPOSE down -v
$COMPOSE up -d --build

$COMPOSE exec backend alembic revision --autogenerate -m "initial_schema"
$COMPOSE exec backend alembic upgrade head
$COMPOSE exec backend alembic current
```

生成后应检查新文件的 `down_revision` 为 `None`，并将新的 migration 文件提交到版本控制。

## Revision 找不到的处理

当执行迁移出现以下错误时，说明数据库 `alembic_version` 表记录的 revision 文件不在当前仓库迁移链中：

```text
Can't locate revision identified by '...'
```

若本地数据不需要保留，使用“清空并重建开发数据库”流程即可。不要直接执行 `alembic stamp head`，该命令只修改版本记录，不会创建缺失的表结构。

若数据需要保留，应停止操作，找回缺失的 migration 文件或制定数据迁移方案后再处理。

## 测试

前端：

```bash
npm --prefix frontend run test
npm --prefix frontend run build
```

后端测试会为每个并行 worker 创建独立 PostgreSQL 临时数据库，执行 Alembic migration，并在测试结束后删除。先启动测试数据库：

```bash
$TEST_COMPOSE up -d --wait db-test
```

运行完整后端测试。pytest 配置会自动启用并行执行：

```bash
$TEST_COMPOSE run --rm --no-deps backend pytest backend/tests/
```

运行单个测试文件：

```bash
$TEST_COMPOSE run --rm --no-deps backend pytest backend/tests/test_database.py
```

仅在首次运行，或修改 `Dockerfile`、`pyproject.toml` 等镜像构建输入后重建后端镜像：

```bash
$TEST_COMPOSE build backend
```

测试结束后清理临时 PostgreSQL 容器：

```bash
$TEST_COMPOSE stop db-test
$TEST_COMPOSE rm -f db-test
```
