# CLI 工具使用说明

## 初始化管理员

首次部署后，数据库中没有任何用户，需要先创建初始管理员。

```bash
docker compose exec backend python -m app.cli create-admin \
  --username admin \
  --password admin123 \
  --display-name "管理员"
```

执行成功后输出：
```
Admin user created: id=1, username=admin
```

## 功能说明

`create-admin` 命令执行以下操作：

| 步骤 | 说明 |
|------|------|
| 1. 种子权限 | 在 `sys_permission` 表中创建全部 22 个权限码（如 `system:user:manage`、`org:unit:view` 等），已存在的跳过 |
| 2. 创建角色 | 查找或创建 `code="super-admin"` 的「超级管理员」角色，关联所有权限 |
| 3. 创建用户 | 创建指定用户，分配 super-admin 角色 |

创建的用户拥有全部权限，包括：
- 管理账号角色 (`system:user:manage`)
- 管理组织架构 (`org:unit:view`)
- 管理班次规则、节假日、排班、换班、请假、退费、考勤等业务权限

## 重复执行

第二次执行（用户名已存在）：
```
Error: username 'admin' already exists
```

重复执行不破坏已有权限数据（`super-admin` 角色保持所有权限），仅无法创建同名用户。

## 后续用户创建

初始管理员登录后，可通过 Web 页面「系统管理 → 账号角色」创建其他用户和角色，无需再使用 CLI。
