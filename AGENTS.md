# AGENTS.md

## 项目简介
广播电视台站值班管理系统，B/S 架构。
后端 FastAPI + SQLAlchemy + PostgreSQL；
前端 Vue3 + TypeScript + Element Plus；
Docker Compose 部署。

## 项目依据

开发和验收必须严格依据以下文档：

* `docs/design/01-需求分析.md`
* `docs/design/02-原型设计.md`
* `docs/design/03-总体设计.md`
* `docs/design/04-开发实施计划.md`
* `docs/design/06-设计修订.md`

如上述文档之间存在冲突，优先级如下：

1. 设计修订
2. 已确认的需求分析
3. 已确认的原型设计
4. 已确认的总体设计
5. 开发实施计划

如果仍然无法判断，不要自行扩大需求，停下来然后提问。

## 开发流程（TDD）

1. 先写或补测试，验证测试失败（Red）
2. 编写最小实现，让测试通过（Green）

### 测试命令

| 端     | 命令                                      |
| ------ | ----------------------------------------- |
| 后端   | `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm --no-deps backend pytest backend/tests/`（依赖 pyproject.toml 配置）       |
| 前端   | `npm --prefix frontend run test`          |

### 约定

- 后端测试文件命名 `test_<module>.py`，放在 `backend/tests/`
- 前端测试文件命名 `<module>.test.ts`，放在 `frontend/tests/`
- 每个测试函数/用例只测一个行为，保持隔离
- 测试不应依赖真实网络或外部服务