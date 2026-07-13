<template>
  <section class="account-role-view">
    <h1>账号角色</h1>

    <el-tabs v-model="activeTab" class="account-role-view__tabs">
      <el-tab-pane label="账号管理" name="users">
        <div class="account-role-view__toolbar">
          <el-button type="primary" @click="openUserDialog(null)">新增账号</el-button>
        </div>
        <el-table :data="users" v-loading="userLoading" stripe>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="username" label="账号" />
          <el-table-column prop="display_name" label="姓名" />
          <el-table-column label="绑定人员" width="160">
            <template #default="{ row }">
              <template v-if="row.person_id != null">
                <el-tag type="success" size="small" effect="plain">
                  {{ personName(row.person_id) }}
                </el-tag>
              </template>
              <span v-else style="color: #9ca3af">未绑定</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'enabled' ? 'success' : 'danger'" size="small">
                {{ row.status === 'enabled' ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="240">
            <template #default="{ row }">
              <el-button size="small" @click="openUserDialog(row)">编辑</el-button>
              <el-button size="small" @click="openRoleDialog(row)">角色</el-button>
              <el-button
                size="small"
                :type="row.status === 'enabled' ? 'warning' : 'success'"
                @click="toggleUserStatus(row)"
              >
                {{ row.status === 'enabled' ? '停用' : '启用' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="角色管理" name="roles">
        <div class="account-role-view__toolbar">
          <el-button type="primary" @click="openRoleCreateDialog()">新增角色</el-button>
        </div>
        <el-table :data="roles" v-loading="roleLoading" stripe>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="code" label="编码" />
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="remark" label="备注" />
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button size="small" @click="openRoleEditDialog(row)">编辑</el-button>
              <el-button size="small" @click="openPermissionDialog(row)">权限</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- User create/edit dialog -->
    <el-dialog
      v-model="userDialogVisible"
      :title="editingUser ? '编辑账号' : '新增账号'"
      width="460px"
      @closed="resetUserForm"
    >
      <el-form ref="userFormRef" :model="userForm" :rules="userRules" label-position="top">
        <el-form-item label="账号" prop="username">
          <el-input v-model="userForm.username" :disabled="!!editingUser" />
        </el-form-item>
        <el-form-item v-if="!editingUser" label="密码" prop="password">
          <el-input v-model="userForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="姓名" prop="display_name">
          <el-input v-model="userForm.display_name" />
        </el-form-item>
        <el-form-item label="绑定人员">
          <el-select
            v-model="userForm.person_id"
            placeholder="请选择人员（可选）"
            style="width: 100%"
            clearable
            filterable
          >
            <el-option
              v-for="p in availablePersons"
              :key="p.id"
              :label="`${p.name}（${p.code}）`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="userSaving" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>

    <!-- Role assign dialog -->
    <el-dialog
      v-model="roleDialogVisible"
      title="分配角色"
      width="400px"
    >
      <el-checkbox-group v-model="selectedRoleIds">
        <el-checkbox
          v-for="role in roles"
          :key="role.id"
          :value="role.id"
          :label="role.name"
        />
      </el-checkbox-group>
      <p v-if="roles.length === 0" style="color: #9ca3af">暂无可分配角色，请先在角色管理中添加。</p>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="roleAssignSaving" @click="saveUserRoles">保存</el-button>
      </template>
    </el-dialog>

    <!-- Role create/edit dialog -->
    <el-dialog
      v-model="roleFormVisible"
      :title="editingRole ? '编辑角色' : '新增角色'"
      width="460px"
      @closed="resetRoleForm"
    >
      <el-form ref="roleFormRef" :model="roleForm" :rules="roleRules" label-position="top">
        <el-form-item label="编码" prop="code">
          <el-input v-model="roleForm.code" :disabled="!!editingRole" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="roleForm.name" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="roleForm.remark" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleFormVisible = false">取消</el-button>
        <el-button type="primary" :loading="roleSaving" @click="saveRole">保存</el-button>
      </template>
    </el-dialog>

    <!-- Permission assign dialog -->
    <el-dialog
      v-model="permDialogVisible"
      title="分配权限"
      width="500px"
    >
      <el-checkbox-group v-model="selectedPermIds">
        <el-checkbox
          v-for="perm in permissions"
          :key="perm.id"
          :value="perm.id"
          :label="`${perm.name} (${perm.code})`"
        />
      </el-checkbox-group>
      <template #footer>
        <el-button @click="permDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="permSaving" @click="saveRolePermissions">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import { httpClient } from '@/services/http'

interface UserItem {
  id: number
  username: string
  display_name: string
  person_id: number | null
  status: string
  last_login_at: string | null
}

interface PersonBrief {
  id: number
  code: string
  name: string
}

interface UserDetail extends UserItem {
  role_ids: number[]
}

interface RoleItem {
  id: number
  code: string
  name: string
  remark: string | null
  status: string
}

interface RoleDetail extends RoleItem {
  permission_ids: number[]
}

interface PermItem {
  id: number
  code: string
  name: string
  type: string
}

const activeTab = ref('users')
const users = ref<UserItem[]>([])
const roles = ref<RoleItem[]>([])
const permissions = ref<PermItem[]>([])
const persons = ref<PersonBrief[]>([])
const userLoading = ref(false)
const roleLoading = ref(false)

// User form
const userDialogVisible = ref(false)
const editingUser = ref<UserItem | null>(null)
const userSaving = ref(false)
const userFormRef = ref<FormInstance>()
const userForm = reactive({ username: '', password: '', display_name: '', person_id: null as number | null })
const userRules: FormRules = {
  username: [{ required: true, message: '请输入账号' }],
  password: [{ required: true, message: '请输入密码' }],
  display_name: [{ required: true, message: '请输入姓名' }],
}

// Role form
const roleFormVisible = ref(false)
const editingRole = ref<RoleItem | null>(null)
const roleSaving = ref(false)
const roleFormRef = ref<FormInstance>()
const roleForm = reactive({ code: '', name: '', remark: '' })
const roleRules: FormRules = {
  code: [{ required: true, message: '请输入编码' }],
  name: [{ required: true, message: '请输入名称' }],
}

// Role assign
const roleDialogVisible = ref(false)
const roleAssignSaving = ref(false)
const assignTargetUser = ref<UserItem | null>(null)
const selectedRoleIds = ref<number[]>([])

// Permission assign
const permDialogVisible = ref(false)
const permSaving = ref(false)
const assignTargetRole = ref<RoleItem | null>(null)
const selectedPermIds = ref<number[]>([])

const route = useRoute()

onMounted(() => {
  loadUsers()
  loadRoles()
  loadPermissions()
  loadPersons().then(() => {
    const bindPersonId = route.query.bindPersonId
    if (bindPersonId) {
      openUserDialog(null)
      userForm.person_id = Number(bindPersonId)
    }
  })
})

function personName(id: number | null): string {
  if (id == null) return '-'
  const p = persons.value.find((x) => x.id === id)
  return p ? `${p.name}（${p.code}）` : '-'
}

const availablePersons = computed(() => {
  const boundIds = new Set(
    users.value.filter((u) => u.person_id != null).map((u) => u.person_id as number)
  )
  if (editingUser.value?.person_id) {
    boundIds.delete(editingUser.value.person_id)
  }
  return persons.value.filter((p) => !boundIds.has(p.id))
})

async function loadUsers() {
  userLoading.value = true
  try {
    const resp = await httpClient.get<UserItem[]>('/users')
    users.value = resp.data
  } catch {
    ElMessage.error('加载用户列表失败')
  } finally {
    userLoading.value = false
  }
}

async function loadRoles() {
  roleLoading.value = true
  try {
    const resp = await httpClient.get<RoleItem[]>('/roles')
    roles.value = resp.data
  } catch {
    ElMessage.error('加载角色列表失败')
  } finally {
    roleLoading.value = false
  }
}

async function loadPermissions() {
  try {
    const resp = await httpClient.get<PermItem[]>('/permissions')
    permissions.value = resp.data
  } catch {
    // ignore
  }
}

async function loadPersons() {
  try {
    const resp = await httpClient.get<PersonBrief[]>('/persons')
    persons.value = resp.data
  } catch {
    // ignore
  }
}

// ---- User CRUD ----

function openUserDialog(user: UserItem | null) {
  editingUser.value = user
  if (user) {
    userForm.username = user.username
    userForm.display_name = user.display_name
    userForm.password = ''
    userForm.person_id = user.person_id
  } else {
    resetUserForm()
  }
  userDialogVisible.value = true
}

function resetUserForm() {
  userForm.username = ''
  userForm.password = ''
  userForm.display_name = ''
  userForm.person_id = null
  userFormRef.value?.resetFields()
}

async function saveUser() {
  const valid = await userFormRef.value?.validate().catch(() => false)
  if (!valid) return
  userSaving.value = true
  try {
    if (editingUser.value) {
      await httpClient.put(`/users/${editingUser.value.id}`, {
        display_name: userForm.display_name,
        person_id: userForm.person_id,
      })
      ElMessage.success('编辑成功')
    } else {
      await httpClient.post('/users', {
        username: userForm.username,
        password: userForm.password,
        display_name: userForm.display_name,
        person_id: userForm.person_id,
      })
      ElMessage.success('创建成功')
    }
    userDialogVisible.value = false
    await loadUsers()
  } catch {
    ElMessage.error('操作失败')
  } finally {
    userSaving.value = false
  }
}

async function toggleUserStatus(user: UserItem) {
  const action = user.status === 'enabled' ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(`确认${action}账号 ${user.username} 吗？`, `${action}确认`)
    await httpClient.put(`/users/${user.id}`, { status: user.status === 'enabled' ? 'disabled' : 'enabled' })
    ElMessage.success(`${action}成功`)
    await loadUsers()
  } catch {
    // cancelled
  }
}

// ---- Role assignment ----

async function openRoleDialog(user: UserItem) {
  assignTargetUser.value = user
  try {
    const resp = await httpClient.get<UserDetail>(`/users/${user.id}`)
    selectedRoleIds.value = resp.data.role_ids
  } catch {
    selectedRoleIds.value = []
  }
  roleDialogVisible.value = true
}

async function saveUserRoles() {
  if (!assignTargetUser.value) return
  roleAssignSaving.value = true
  try {
    await httpClient.put(`/users/${assignTargetUser.value.id}/roles`, {
      role_ids: selectedRoleIds.value,
    })
    ElMessage.success('角色分配成功')
    roleDialogVisible.value = false
  } catch {
    ElMessage.error('角色分配失败')
  } finally {
    roleAssignSaving.value = false
  }
}

// ---- Role CRUD ----

function openRoleCreateDialog() {
  editingRole.value = null
  resetRoleForm()
  roleFormVisible.value = true
}

function openRoleEditDialog(role: RoleItem) {
  editingRole.value = role
  roleForm.code = role.code
  roleForm.name = role.name
  roleForm.remark = role.remark || ''
  roleFormVisible.value = true
}

function resetRoleForm() {
  roleForm.code = ''
  roleForm.name = ''
  roleForm.remark = ''
  roleFormRef.value?.resetFields()
}

async function saveRole() {
  const valid = await roleFormRef.value?.validate().catch(() => false)
  if (!valid) return
  roleSaving.value = true
  try {
    if (editingRole.value) {
      await httpClient.put(`/roles/${editingRole.value.id}`, {
        name: roleForm.name,
        remark: roleForm.remark || null,
      })
      ElMessage.success('编辑成功')
    } else {
      await httpClient.post('/roles', {
        code: roleForm.code,
        name: roleForm.name,
        remark: roleForm.remark || null,
      })
      ElMessage.success('创建成功')
    }
    roleFormVisible.value = false
    await loadRoles()
  } catch {
    ElMessage.error('操作失败')
  } finally {
    roleSaving.value = false
  }
}

// ---- Permission assignment ----

async function openPermissionDialog(role: RoleItem) {
  assignTargetRole.value = role
  try {
    const resp = await httpClient.get<RoleDetail>(`/roles/${role.id}`)
    selectedPermIds.value = resp.data.permission_ids
  } catch {
    selectedPermIds.value = []
  }
  permDialogVisible.value = true
}

async function saveRolePermissions() {
  if (!assignTargetRole.value) return
  permSaving.value = true
  try {
    await httpClient.put(`/roles/${assignTargetRole.value.id}/permissions`, {
      permission_ids: selectedPermIds.value,
    })
    ElMessage.success('权限分配成功')
    permDialogVisible.value = false
  } catch {
    ElMessage.error('权限分配失败')
  } finally {
    permSaving.value = false
  }
}
</script>

<style scoped>
.account-role-view h1 {
  margin: 0 0 24px;
  font-size: 24px;
  font-weight: 600;
}

.account-role-view__tabs {
  background: #fff;
  border-radius: 6px;
  padding: 0 24px 24px;
}

.account-role-view__toolbar {
  margin-bottom: 16px;
}
</style>
