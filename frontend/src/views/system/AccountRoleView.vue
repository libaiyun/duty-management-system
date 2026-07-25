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
          <el-table-column label="账号类型" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.is_superuser" type="danger" size="small">超级管理员</el-tag>
              <span v-else>普通账号</span>
            </template>
          </el-table-column>
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
          <el-table-column label="操作" width="320">
            <template #default="{ row }">
              <el-button size="small" :disabled="isProtectedSuperuser(row)" @click="openUserDialog(row)">编辑</el-button>
              <el-button size="small" :disabled="isProtectedSuperuser(row)" @click="openRoleDialog(row)">角色</el-button>
              <el-button size="small" :disabled="isProtectedSuperuser(row)" @click="openPermissionDialog(row)">直接权限</el-button>
              <el-button
                size="small"
                :disabled="isProtectedSuperuser(row)"
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
          <el-button type="primary" @click="openRoleEditDialog(null)">新增角色</el-button>
        </div>
        <el-table :data="roles" v-loading="roleLoading" stripe>
          <el-table-column prop="code" label="编码" />
          <el-table-column prop="name" label="角色名称" />
          <el-table-column prop="remark" label="说明" />
          <el-table-column prop="status" label="状态" width="90" />
          <el-table-column label="操作" width="240">
            <template #default="{ row }">
              <el-button size="small" @click="openRoleEditDialog(row)">编辑</el-button>
              <el-button size="small" @click="openRolePermissionDialog(row)">授权</el-button>
              <el-button size="small" @click="openRoleAccountsDialog(row)">账号</el-button>
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

    <el-dialog v-model="permissionDialogVisible" width="960px" class="permission-dialog permission-dialog--raised">
      <template #header>
        <div class="permission-dialog-header">
          <div class="permission-dialog-header__identity">
            <span class="permission-dialog-header__badge">权</span>
            <div>
              <h2>账号权限配置</h2>
              <p>
                {{ permissionTargetUser?.display_name || permissionTargetUser?.username }}
                · 配置直接授予权限并预览最终生效结果
              </p>
            </div>
          </div>
          <el-tag :type="permissionTargetUser?.is_superuser ? 'danger' : 'info'" effect="plain">
            {{ permissionTargetUser?.is_superuser ? '超级管理员' : '普通账号' }}
          </el-tag>
        </div>
      </template>
      <div class="permission-workspace permission-workspace--fixed-height">
        <section class="permission-workspace__direct">
          <div class="permission-panel-heading permission-panel-heading--direct">
            <span class="permission-panel-heading__badge">直</span>
            <div class="permission-panel-heading__copy">
              <h3>直接权限</h3>
              <p>仅补充角色未覆盖的功能权限</p>
            </div>
            <el-input v-model="permissionSearchKeyword" placeholder="搜索权限" clearable size="small" />
          </div>
          <div class="permission-workspace__scrollable">
            <article v-for="group in filteredPermissionGroups" :key="group.code" class="direct-permission-card permission-group">
              <div class="direct-permission-card__header">
                <button type="button" class="direct-permission-card__title" @click="toggleDirectPermissionGroupExpansion(group.code)">
                  <span>{{ group.name }}（{{ group.items.length }} 项）</span>
                  <span>{{ isDirectPermissionGroupExpanded(group.code) || permissionSearchKeyword ? '收起' : '展开' }}</span>
                </button>
                <el-checkbox
                  :model-value="isDirectPermissionGroupSelected(group)"
                  :indeterminate="isDirectPermissionGroupIndeterminate(group)"
                  @change="toggleDirectPermissionGroup(group, $event === true)"
                >
                  全选
                </el-checkbox>
              </div>
              <el-checkbox-group v-show="isDirectPermissionGroupExpanded(group.code) || permissionSearchKeyword" v-model="selectedDirectPermissionIds" class="direct-permission-card__options">
                <el-checkbox v-for="permission in group.items" :key="permission.id" :value="permission.id">
                  {{ permission.name }}
                </el-checkbox>
              </el-checkbox-group>
            </article>
            <el-empty v-if="filteredPermissionGroups.length === 0" description="未找到匹配权限" :image-size="72" />
          </div>
        </section>

        <section class="permission-workspace__effective">
          <div class="permission-panel-heading permission-panel-heading--effective">
            <span class="permission-panel-heading__badge">效</span>
            <div class="permission-panel-heading__copy">
              <h3>最终有效权限</h3>
              <p>角色权限与直接授予权限的合并结果</p>
            </div>
            <span v-if="!permissionTargetUser?.is_superuser" class="effective-permission-summary">{{ effectivePermissionSummary }}</span>
          </div>
          <el-alert
            v-if="permissionTargetUser?.is_superuser"
            title="超级管理员拥有全部系统权限"
            type="warning"
            :closable="false"
            show-icon
          />
          <div v-else-if="effectivePermissionGroups.length" class="effective-permission-list">
            <article v-for="group in effectivePermissionGroups" :key="group.code" class="effective-permission-card">
              <button type="button" class="effective-permission-card__header" @click="toggleEffectivePermissionGroupExpansion(group.code)">
                <span>{{ group.name }}（{{ group.items.length }} 项）</span>
                <span>{{ isEffectivePermissionGroupExpanded(group.code) ? '收起' : '查看' }}</span>
              </button>
              <div v-show="isEffectivePermissionGroupExpanded(group.code)" class="effective-permission-card__details">
                <div v-for="permission in group.items" :key="permission.code" class="effective-permission-item">
                  <div class="effective-permission-item__content">
                    <strong>{{ permission.name }}</strong>
                    <el-tag v-for="source in permission.sources" :key="source.label" :type="source.type" size="small" effect="plain">
                      {{ source.label }}
                    </el-tag>
                  </div>
                </div>
              </div>
            </article>
          </div>
          <el-empty v-else description="暂无有效权限" :image-size="72" />
        </section>
      </div>
      <template #footer>
        <el-button @click="permissionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="permissionSaving" @click="saveUserPermissions">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="roleEditDialogVisible" :title="editingRole ? '编辑角色' : '新增角色'" width="460px">
      <el-form :model="roleForm" label-position="top">
        <el-form-item label="角色编码"><el-input v-model="roleForm.code" :disabled="!!editingRole" /></el-form-item>
        <el-form-item label="角色名称"><el-input v-model="roleForm.name" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="roleForm.remark" type="textarea" /></el-form-item>
        <el-form-item v-if="editingRole" label="状态"><el-switch v-model="roleForm.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleEditDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRole">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rolePermissionDialogVisible" title="角色授权" width="620px">
      <el-checkbox-group v-model="selectedRolePermissionIds">
        <div v-for="group in permissionGroups" :key="group.code" class="permission-group">
          <strong>{{ group.name }}</strong>
          <div>
            <el-checkbox v-for="permission in group.items" :key="permission.id" :value="permission.id">
              {{ permission.name }}
            </el-checkbox>
          </div>
        </div>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="rolePermissionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRolePermissions">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="roleAccountsDialogVisible" title="关联账号" width="520px">
      <el-table :data="roleAccounts" stripe>
        <el-table-column prop="username" label="账号" />
        <el-table-column prop="display_name" label="姓名" />
        <el-table-column prop="status" label="状态" />
      </el-table>
      <el-empty v-if="roleAccounts.length === 0" description="暂无关联账号" />
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
        >
          {{ role.name }}
        </el-checkbox>
      </el-checkbox-group>
      <p v-if="roles.length === 0" style="color: #9ca3af">暂无可分配角色，请先在角色管理中添加。</p>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="roleAssignSaving" @click="saveUserRoles">保存</el-button>
      </template>
    </el-dialog>

  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import { httpClient } from '@/services/http'
import { useAuthStore } from '@/stores/auth'

interface UserItem {
  id: number
  username: string
  display_name: string
  person_id: number | null
  status: string
  last_login_at: string | null
  is_superuser: boolean
}

interface PersonBrief {
  id: number
  code: string
  name: string
}

interface UserDetail extends UserItem {
  role_ids: number[]
  direct_permission_ids: number[]
  effective_permission_codes: string[]
  permission_sources: Record<string, string[]>
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
  user_ids: number[]
}

interface PermItem {
  id: number
  code: string
  name: string
  type: string
  group_code: string
  group_name: string
}

interface PermissionGroup {
  code: string
  name: string
  items: PermItem[]
}

interface EffectivePermissionItem {
  code: string
  name: string
  sources: EffectivePermissionSource[]
}

interface EffectivePermissionSource {
  label: string
  type: 'primary' | 'info' | 'warning'
}

interface EffectivePermissionGroup {
  code: string
  name: string
  items: EffectivePermissionItem[]
}

const activeTab = ref('users')
const authStore = useAuthStore()
const users = ref<UserItem[]>([])
const roles = ref<RoleItem[]>([])
const persons = ref<PersonBrief[]>([])
const permissions = ref<PermItem[]>([])
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

// Role assign
const roleDialogVisible = ref(false)
const roleAssignSaving = ref(false)
const assignTargetUser = ref<UserItem | null>(null)
const selectedRoleIds = ref<number[]>([])
const permissionDialogVisible = ref(false)
const permissionSaving = ref(false)
const selectedDirectPermissionIds = ref<number[]>([])
const effectivePermissionCodes = ref<string[]>([])
const permissionSources = ref<Record<string, string[]>>({})
const permissionTargetUser = ref<UserItem | null>(null)
const expandedEffectivePermissionGroups = ref<string[]>([])
const expandedDirectPermissionGroups = ref<string[]>([])
const permissionSearchKeyword = ref('')

const roleEditDialogVisible = ref(false)
const editingRole = ref<RoleItem | null>(null)
const roleForm = reactive({ code: '', name: '', remark: '', enabled: true })
const rolePermissionDialogVisible = ref(false)
const permissionTargetRole = ref<RoleItem | null>(null)
const selectedRolePermissionIds = ref<number[]>([])
const roleAccountsDialogVisible = ref(false)
const roleAccounts = ref<UserItem[]>([])

const permissionGroups = computed(() => {
  const groups = new Map<string, PermissionGroup>()
  for (const permission of permissions.value) {
    const group = groups.get(permission.group_code) || { code: permission.group_code, name: permission.group_name, items: [] }
    group.items.push(permission)
    groups.set(permission.group_code, group)
  }
  return [...groups.values()]
})

const effectivePermissionItems = computed<EffectivePermissionItem[]>(() => {
  const sourcesByCode = new Map<string, string[]>()
  for (const code of effectivePermissionCodes.value) {
    sourcesByCode.set(code, (permissionSources.value[code] || []).filter((source) => source !== 'direct'))
  }
  for (const permissionId of selectedDirectPermissionIds.value) {
    const permission = permissions.value.find((item) => item.id === permissionId)
    if (!permission) continue
    sourcesByCode.set(permission.code, [...(sourcesByCode.get(permission.code) || []), 'direct'])
  }
  return [...sourcesByCode.entries()].map(([code, sources]) => ({
    code,
    name: permissions.value.find((permission) => permission.code === code)?.name || `未知权限（${code}）`,
    sources: sources.map(permissionSourceText),
  }))
})

const effectivePermissionGroups = computed(() => {
  const itemsByCode = new Map(effectivePermissionItems.value.map((item) => [item.code, item]))
  const groups = permissionGroups.value
    .map((group) => ({
      code: group.code,
      name: group.name,
      items: group.items
        .map((permission) => itemsByCode.get(permission.code))
        .filter((item): item is EffectivePermissionItem => item !== undefined),
    }))
    .filter((group) => group.items.length > 0)
  const groupedCodes = new Set(groups.flatMap((group) => group.items.map((item) => item.code)))
  const unmatchedItems = effectivePermissionItems.value.filter((item) => !groupedCodes.has(item.code))
  return unmatchedItems.length ? [...groups, { code: 'unknown', name: '其他权限', items: unmatchedItems }] : groups
})

const filteredPermissionGroups = computed<PermissionGroup[]>(() => {
  const keyword = permissionSearchKeyword.value.trim()
  if (!keyword) return permissionGroups.value
  return permissionGroups.value
    .map((group) => ({ ...group, items: group.items.filter((permission) => permission.name.includes(keyword)) }))
    .filter((group) => group.items.length > 0)
})

const effectivePermissionSummary = computed(() => {
  const roleSources = new Set<string>()
  for (const sources of Object.values(permissionSources.value)) {
    for (const source of sources) if (source.startsWith('role:')) roleSources.add(source)
  }
  const directCount = effectivePermissionItems.value.filter((permission) => permission.sources.some((source) => source.label === '直授')).length
  const roleCount = roleSources.size
  return `共 ${effectivePermissionItems.value.length} 项 · ${roleCount} 个角色 · ${directCount} 项直授`
})

function isDirectPermissionGroupSelected(group: PermissionGroup): boolean {
  return group.items.length > 0 && group.items.every((permission) => selectedDirectPermissionIds.value.includes(permission.id))
}

function isDirectPermissionGroupIndeterminate(group: PermissionGroup): boolean {
  return group.items.some((permission) => selectedDirectPermissionIds.value.includes(permission.id))
    && !isDirectPermissionGroupSelected(group)
}

function toggleDirectPermissionGroup(group: PermissionGroup, checked: boolean): void {
  const selectedIds = new Set(selectedDirectPermissionIds.value)
  for (const permission of group.items) {
    if (checked) selectedIds.add(permission.id)
    else selectedIds.delete(permission.id)
  }
  selectedDirectPermissionIds.value = [...selectedIds]
}

function isDirectPermissionGroupExpanded(groupCode: string): boolean {
  return expandedDirectPermissionGroups.value.includes(groupCode)
}

function toggleDirectPermissionGroupExpansion(groupCode: string): void {
  expandedDirectPermissionGroups.value = isDirectPermissionGroupExpanded(groupCode)
    ? expandedDirectPermissionGroups.value.filter((code) => code !== groupCode)
    : [...expandedDirectPermissionGroups.value, groupCode]
}

function isEffectivePermissionGroupExpanded(groupCode: string): boolean {
  return expandedEffectivePermissionGroups.value.includes(groupCode)
}

function toggleEffectivePermissionGroupExpansion(groupCode: string): void {
  expandedEffectivePermissionGroups.value = isEffectivePermissionGroupExpanded(groupCode)
    ? expandedEffectivePermissionGroups.value.filter((code) => code !== groupCode)
    : [...expandedEffectivePermissionGroups.value, groupCode]
}

function permissionSourceText(source: string): EffectivePermissionSource {
  if (source === 'direct') return { label: '直授', type: 'primary' }
  if (source === 'superuser') return { label: '超级管理员', type: 'warning' }
  if (source.startsWith('role:')) {
    const roleCode = source.slice('role:'.length)
    const role = roles.value.find((item) => item.code === roleCode)
    return { label: role?.name || `未知角色（${roleCode}）`, type: 'info' }
  }
  return { label: `未知来源（${source}）`, type: 'info' }
}

function isProtectedSuperuser(user: UserItem): boolean {
  return user.is_superuser && !authStore.isSuperuser
}

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
  const resp = await httpClient.get<PermItem[]>('/permissions')
  permissions.value = resp.data
}


async function loadPersons() {
  try {
    const resp = await httpClient.get<PersonBrief[]>('/users/persons')
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

async function openPermissionDialog(user: UserItem) {
  permissionTargetUser.value = user
  expandedEffectivePermissionGroups.value = []
  expandedDirectPermissionGroups.value = permissionGroups.value.slice(0, 1).map((group) => group.code)
  permissionSearchKeyword.value = ''
  const resp = await httpClient.get<UserDetail>(`/users/${user.id}`)
  selectedDirectPermissionIds.value = resp.data.direct_permission_ids
  effectivePermissionCodes.value = resp.data.effective_permission_codes
  permissionSources.value = resp.data.permission_sources
  permissionDialogVisible.value = true
}

async function saveUserPermissions() {
  if (!permissionTargetUser.value) return
  permissionSaving.value = true
  try {
    await httpClient.put(`/users/${permissionTargetUser.value.id}/permissions`, { permission_ids: selectedDirectPermissionIds.value })
    ElMessage.success('账号直接权限分配成功')
    await openPermissionDialog(permissionTargetUser.value)
  } finally {
    permissionSaving.value = false
  }
}

function openRoleEditDialog(role: RoleItem | null) {
  editingRole.value = role
  roleForm.code = role?.code || ''
  roleForm.name = role?.name || ''
  roleForm.remark = role?.remark || ''
  roleForm.enabled = role?.status !== 'disabled'
  roleEditDialogVisible.value = true
}

async function saveRole() {
  if (editingRole.value) {
    await httpClient.put(`/roles/${editingRole.value.id}`, {
      name: roleForm.name, remark: roleForm.remark, status: roleForm.enabled ? 'enabled' : 'disabled',
    })
  } else {
    await httpClient.post('/roles', { code: roleForm.code, name: roleForm.name, remark: roleForm.remark })
  }
  roleEditDialogVisible.value = false
  ElMessage.success('角色保存成功')
  await loadRoles()
}

async function openRolePermissionDialog(role: RoleItem) {
  permissionTargetRole.value = role
  const resp = await httpClient.get<RoleDetail>(`/roles/${role.id}`)
  selectedRolePermissionIds.value = resp.data.permission_ids
  rolePermissionDialogVisible.value = true
}

async function saveRolePermissions() {
  if (!permissionTargetRole.value) return
  await httpClient.put(`/roles/${permissionTargetRole.value.id}/permissions`, { permission_ids: selectedRolePermissionIds.value })
  rolePermissionDialogVisible.value = false
  ElMessage.success('角色授权成功')
}

async function openRoleAccountsDialog(role: RoleItem) {
  const resp = await httpClient.get<RoleDetail>(`/roles/${role.id}`)
  const userIds = new Set(resp.data.user_ids)
  roleAccounts.value = users.value.filter((user) => userIds.has(user.id))
  roleAccountsDialogVisible.value = true
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

.permission-workspace { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); min-height: 0; }
.permission-workspace--fixed-height { height: 400px; }
.permission-workspace__direct, .permission-workspace__effective { display: flex; flex-direction: column; min-height: 0; }
.permission-workspace__direct { padding-right: 20px; border-right: 1px solid var(--el-border-color-lighter); }
.permission-workspace__effective { padding-left: 20px; }
.permission-dialog--raised { margin-top: calc(15vh - 5px); }
.permission-dialog-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding-right: 28px; }
.permission-dialog-header__identity { display: flex; align-items: center; gap: 12px; }
.permission-dialog-header__badge, .permission-panel-heading__badge { display: inline-flex; align-items: center; justify-content: center; border-radius: 6px; color: #fff; font-weight: 700; }
.permission-dialog-header__badge { width: 36px; height: 36px; background: var(--el-color-primary); font-size: 17px; }
.permission-dialog-header h2 { margin: 0; font-size: 18px; line-height: 24px; }
.permission-dialog-header p, .permission-panel-heading p { margin: 2px 0 0; color: var(--el-text-color-secondary); font-size: 12px; line-height: 18px; }
.permission-panel-heading { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.permission-panel-heading__badge { width: 28px; height: 28px; flex: 0 0 auto; font-size: 13px; }
.permission-panel-heading--direct .permission-panel-heading__badge { background: var(--el-color-success); }
.permission-panel-heading--effective .permission-panel-heading__badge { background: var(--el-color-primary); }
.permission-panel-heading__copy { min-width: 0; }
.permission-panel-heading h3 { margin: 0; font-size: 16px; line-height: 20px; }
.permission-panel-heading .el-input { width: 150px; margin-left: auto; }
.permission-workspace__scrollable, .effective-permission-list { flex: 1; min-height: 0; overflow-y: auto; }
.effective-permission-summary { color: var(--el-text-color-secondary); font-size: 13px; white-space: nowrap; }
.direct-permission-card { margin-bottom: 10px; border: 1px solid var(--el-border-color-lighter); border-left: 3px solid var(--el-color-success); border-radius: 4px; overflow: hidden; }
.direct-permission-card__header { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 10px 12px; background: var(--el-fill-color-light); }
.direct-permission-card__title { display: flex; flex: 1; justify-content: space-between; min-width: 0; padding: 0; border: 0; background: transparent; color: var(--el-text-color-primary); cursor: pointer; font: inherit; font-weight: 600; text-align: left; }
.direct-permission-card__title span:last-child { color: var(--el-color-primary); font-size: 13px; font-weight: 400; }
.direct-permission-card__options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; padding: 10px 12px; }
.direct-permission-card__options .el-checkbox { margin-right: 0; min-width: 0; }
.effective-permission-card { margin-bottom: 10px; border: 1px solid var(--el-border-color-lighter); border-left: 3px solid var(--el-color-primary); border-radius: 4px; overflow: hidden; }
.effective-permission-card__header { display: flex; justify-content: space-between; width: 100%; padding: 10px 12px; border: 0; background: var(--el-fill-color-light); color: var(--el-text-color-primary); cursor: pointer; font: inherit; font-weight: 600; text-align: left; }
.effective-permission-card__header span:last-child { color: var(--el-color-primary); font-size: 13px; font-weight: 400; }
.effective-permission-card__details { padding: 4px 12px; background: var(--el-bg-color); }
.effective-permission-item { padding: 9px 0; border-top: 1px solid var(--el-border-color-lighter); }
.effective-permission-item:last-child { border-bottom: 0; }
.effective-permission-item__content { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; min-height: 24px; }
.effective-permission-item__content strong { margin-right: 2px; }

@media (max-width: 800px) {
  .permission-workspace { grid-template-columns: 1fr; }
  .permission-workspace__direct { padding: 0 0 20px; border-right: 0; border-bottom: 1px solid var(--el-border-color-lighter); }
  .permission-workspace__effective { padding: 20px 0 0; }
  .direct-permission-card__options { grid-template-columns: 1fr; }
}

</style>
