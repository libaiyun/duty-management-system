<template>
  <section class="org-unit-view">
    <h1>台站机房</h1>
    <div class="org-unit-view__toolbar">
      <el-button type="primary" @click="openCreateDialog('station')">新增台站</el-button>
      <el-button type="primary" @click="openCreateDialog('room')">新增机房</el-button>
    </div>

    <div class="org-unit-view__body">
      <div class="org-unit-view__tree-panel">
        <el-input
          v-model="filterText"
          placeholder="搜索组织..."
          size="small"
          clearable
          class="org-unit-view__filter"
        />
        <el-tree
          ref="treeRef"
          :data="treeData"
          :props="{ label: 'name', children: 'children' }"
          :filter-node-method="filterNode"
          node-key="id"
          highlight-current
          @node-click="onNodeClick"
        >
          <template #default="{ node, data }">
            <span class="org-unit-view__tree-node">
              <el-tag :type="data.type === 'station' ? 'primary' : 'success'" size="small" effect="plain">
                {{ typeLabel(data.type) }}
              </el-tag>
              <span class="org-unit-view__tree-label">{{ data.name }}</span>
            </span>
          </template>
        </el-tree>
      </div>

      <div v-if="selectedNode" class="org-unit-view__detail-panel">
        <h2 class="org-unit-view__detail-title">{{ selectedNode.name }}</h2>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="编码">{{ selectedNode.code }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ selectedNode.name }}</el-descriptions-item>
          <el-descriptions-item label="类型">
            <el-tag :type="selectedNode.type === 'station' ? 'primary' : 'success'" size="small">
              {{ typeLabel(selectedNode.type) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="selectedNode.status === 'enabled' ? 'success' : 'info'" size="small">
              {{ selectedNode.status === 'enabled' ? '启用' : '停用' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="负责人">
            {{ personName(selectedNode.manager_person_id) }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="org-unit-view__detail-actions">
          <el-button size="small" @click="openEditDialog(selectedNode)">编辑</el-button>
          <el-button
            size="small"
            :type="selectedNode.status === 'enabled' ? 'warning' : 'success'"
            @click="toggleStatus(selectedNode)"
          >
            {{ selectedNode.status === 'enabled' ? '停用' : '启用' }}
          </el-button>
          <el-button size="small" type="danger" @click="confirmDelete(selectedNode)">删除</el-button>
        </div>
      </div>

      <div v-else class="org-unit-view__empty-panel">
        <p>请从左侧组织树中选择一个节点查看详情</p>
      </div>
    </div>

    <el-dialog
      v-model="formVisible"
      :title="editingUnit ? '编辑组织' : '新增' + typeLabel(formData.type)"
      width="460px"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-position="top">
        <el-form-item label="编码" prop="code">
          <el-input v-model="formData.code" :disabled="!!editingUnit" placeholder="留空自动生成" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="formData.name" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select
            v-model="formData.manager_person_id"
            placeholder="请选择负责人（可选）"
            style="width: 100%"
            clearable
            filterable
          >
            <el-option
              v-for="p in persons"
              :key="p.id"
              :label="`${p.name}（${p.code}）`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="deleteVisible"
      title="确认删除"
      width="360px"
    >
      <p>确认删除组织「{{ deleteTarget?.name }}」吗？</p>
      <template #footer>
        <el-button @click="deleteVisible = false">取消</el-button>
        <el-button type="danger" :loading="deleting" @click="doDelete">删除</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import type { ElTree } from 'element-plus'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import { httpClient } from '@/services/http'

interface OrgUnitNode {
  id: number
  parent_id: number | null
  code: string
  name: string
  type: string
  manager_person_id: number | null
  status: string
  sort_order: number
  children: OrgUnitNode[]
}

interface PersonBrief {
  id: number
  code: string
  name: string
}

function typeLabel(type: string): string {
  return type === 'station' ? '台站' : '机房'
}

const treeRef = ref<InstanceType<typeof ElTree>>()
const treeData = ref<OrgUnitNode[]>([])
const persons = ref<PersonBrief[]>([])
const filterText = ref('')
const selectedNode = ref<OrgUnitNode | null>(null)
const loading = ref(false)

function personName(id: number | null): string {
  if (id == null) return '-'
  const p = persons.value.find((x) => x.id === id)
  return p ? `${p.name}（${p.code}）` : '-'
}

// Form
const formVisible = ref(false)
const editingUnit = ref<OrgUnitNode | null>(null)
const saving = ref(false)
const formRef = ref<FormInstance>()
const formData = ref({
  code: '',
  name: '',
  type: 'station',
  parent_id: null as number | null,
  manager_person_id: null as number | null,
})
const formRules: FormRules = {
  name: [{ required: true, message: '请输入名称' }],
}

// Delete
const deleteVisible = ref(false)
const deleteTarget = ref<OrgUnitNode | null>(null)
const deleting = ref(false)

watch(filterText, (val) => {
  treeRef.value?.filter(val)
})

function filterNode(value: string, data: OrgUnitNode): boolean {
  if (!value) return true
  return data.name.toLowerCase().includes(value.toLowerCase())
}

onMounted(async () => {
  await Promise.all([loadTree(), loadPersons()])
})

async function loadTree() {
  loading.value = true
  try {
    const resp = await httpClient.get<OrgUnitNode[]>('/org-units/tree')
    treeData.value = resp.data
  } catch {
    ElMessage.error('加载组织树失败')
  } finally {
    loading.value = false
  }
}

async function loadPersons() {
  try {
    const resp = await httpClient.get<PersonBrief[]>('/persons')
    persons.value = resp.data
  } catch {
    // 负责人下拉可选，加载失败不阻塞页面
  }
}

function onNodeClick(data: OrgUnitNode) {
  selectedNode.value = data
}

function openCreateDialog(type: string) {
  editingUnit.value = null
  formData.value = { code: '', name: '', type, parent_id: null, manager_person_id: null }
  if (selectedNode.value && selectedNode.value.type === 'station' && type === 'room') {
    formData.value.parent_id = selectedNode.value.id
  }
  formVisible.value = true
  nextTick(() => formRef.value?.clearValidate())
}

function openEditDialog(unit: OrgUnitNode) {
  editingUnit.value = unit
  formData.value = {
    code: unit.code,
    name: unit.name,
    type: unit.type,
    parent_id: unit.parent_id,
    manager_person_id: unit.manager_person_id,
  }
  formVisible.value = true
  nextTick(() => formRef.value?.clearValidate())
}

function resetForm() {
  editingUnit.value = null
  formData.value = { code: '', name: '', type: 'station', parent_id: null, manager_person_id: null }
  formRef.value?.resetFields()
}

async function save() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (editingUnit.value) {
      await httpClient.put(`/org-units/${editingUnit.value.id}`, {
        name: formData.value.name,
        manager_person_id: formData.value.manager_person_id,
      })
      ElMessage.success('编辑成功')
    } else {
      await httpClient.post('/org-units', {
        ...(formData.value.code ? { code: formData.value.code } : {}),
        name: formData.value.name,
        type: formData.value.type,
        parent_id: formData.value.parent_id,
        manager_person_id: formData.value.manager_person_id,
      })
      ElMessage.success('创建成功')
    }
    formVisible.value = false
    await loadTree()
  } catch {
    ElMessage.error('操作失败')
  } finally {
    saving.value = false
  }
}

function confirmDelete(unit: OrgUnitNode) {
  deleteTarget.value = unit
  deleteVisible.value = true
}

async function doDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await httpClient.delete(`/org-units/${deleteTarget.value.id}`)
    ElMessage.success('删除成功')
    deleteVisible.value = false
    if (selectedNode.value?.id === deleteTarget.value.id) {
      selectedNode.value = null
    }
    await loadTree()
  } catch {
    ElMessage.error('删除失败')
  } finally {
    deleting.value = false
  }
}

async function toggleStatus(unit: OrgUnitNode) {
  const action = unit.status === 'enabled' ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(`确认${action}组织「${unit.name}」吗？`, `${action}确认`)
    await httpClient.put(`/org-units/${unit.id}`, {
      status: unit.status === 'enabled' ? 'disabled' : 'enabled',
    })
    ElMessage.success(`${action}成功`)
    await loadTree()
  } catch {
    // cancelled
  }
}
</script>

<style scoped>
.org-unit-view h1 {
  margin: 0 0 16px;
  font-size: 24px;
  font-weight: 600;
}

.org-unit-view__toolbar {
  margin-bottom: 16px;
}

.org-unit-view__body {
  display: flex;
  gap: 24px;
  min-height: 500px;
}

.org-unit-view__tree-panel {
  width: 300px;
  flex-shrink: 0;
  background: #fff;
  border-radius: 6px;
  padding: 16px;
  border: 1px solid var(--el-border-color-light);
}

.org-unit-view__filter {
  margin-bottom: 12px;
}

.org-unit-view__tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
}

.org-unit-view__tree-label {
  font-size: 14px;
}

.org-unit-view__detail-panel {
  flex: 1;
  background: #fff;
  border-radius: 6px;
  padding: 24px;
  border: 1px solid var(--el-border-color-light);
}

.org-unit-view__detail-title {
  margin: 0 0 20px;
  font-size: 18px;
  font-weight: 600;
}

.org-unit-view__detail-actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
}

.org-unit-view__empty-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border-radius: 6px;
  border: 1px solid var(--el-border-color-light);
  color: #9ca3af;
}
</style>
