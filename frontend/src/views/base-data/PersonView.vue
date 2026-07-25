<template>
  <section class="person-view">
    <h1>人员管理</h1>

    <div class="person-view__filters">
      <el-input
        v-model="filters.name"
        placeholder="搜索姓名..."
        size="default"
        clearable
        class="person-view__filter-name"
      />
      <el-select
        v-model="filters.person_type"
        placeholder="人员类型"
        size="default"
        clearable
        class="person-view__filter-type"
      >
        <el-option
          v-for="(label, value) in PERSON_TYPE_LABELS"
          :key="value"
          :label="label"
          :value="value"
        />
      </el-select>
      <el-select
        v-model="filters.status"
        placeholder="状态"
        size="default"
        clearable
        class="person-view__filter-status"
      >
        <el-option label="启用" value="enabled" />
        <el-option label="停用" value="disabled" />
      </el-select>
      <el-button @click="resetFilters">重置</el-button>
    </div>

    <div class="person-view__toolbar">
      <el-button type="primary" @click="openCreateDialog">新增人员</el-button>
    </div>

    <el-table :data="filteredPersons" v-loading="loading" stripe max-height="calc(100vh - 320px)">
      <el-table-column prop="code" label="编号" width="120" />
      <el-table-column prop="name" label="姓名" width="120" />
      <el-table-column label="人员类型" width="140">
        <template #default="{ row }">
          {{ personTypeLabel(row.person_type) }}
        </template>
      </el-table-column>
      <el-table-column label="所属台站机房" min-width="180">
        <template #default="{ row }">
          {{ orgUnitLabel(row.org_unit_id) || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="phone" label="手机号" width="140" />
      <el-table-column label="参与排班" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="row.participate_schedule ? 'success' : 'info'" size="small" effect="plain">
            {{ row.participate_schedule ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 'enabled' ? 'success' : 'danger'" size="small">
            {{ row.status === 'enabled' ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="账号状态" width="120" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.account_bound" type="success" size="small" effect="plain">
            {{ row.account_username }}
          </el-tag>
          <el-tag v-else type="info" size="small" effect="plain">
            未绑定
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEditDialog(row)">编辑</el-button>
          <el-button
            size="small"
            :type="row.status === 'enabled' ? 'warning' : 'success'"
            @click="toggleStatus(row)"
          >
            {{ row.status === 'enabled' ? '停用' : '启用' }}
          </el-button>
          <el-button size="small" @click="goToBindAccount(row)">绑定账号</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="formVisible"
      :title="editingPerson ? '编辑人员' : '新增人员'"
      width="500px"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-position="top">
        <el-form-item label="人员编号" prop="code">
          <el-input v-model="formData.code" :disabled="!!editingPerson" placeholder="留空自动生成" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="formData.name" />
        </el-form-item>
        <el-form-item label="人员类型" prop="person_type">
          <el-select v-model="formData.person_type" style="width: 100%">
            <el-option
              v-for="(label, value) in PERSON_TYPE_LABELS"
              :key="value"
              :label="label"
              :value="value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="formData.phone" />
        </el-form-item>
        <el-form-item label="参与排班">
          <el-switch v-model="formData.participate_schedule" :disabled="formData.person_type !== 'duty_operator'" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="formData.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import { httpClient, resolveErrorMessage } from '@/services/http'
import { useRoomContextStore } from '@/stores/room-context'

interface OrgUnitItem {
  id: number
  code: string
  name: string
  type: string
  parent_id: number | null
}

interface PersonItem {
  id: number
  org_unit_id: number | null
  code: string
  name: string
  person_type: string
  phone: string | null
  participate_schedule: boolean
  status: string
  remark: string | null
  account_bound: boolean
  account_username: string | null
}

const PERSON_TYPE_LABELS: Record<string, string> = {
  duty_operator: '值机员',
  maintenance: '检修班',
  room_director: '机房主任',
  deputy_director: '机房副主任',
}

function personTypeLabel(type: string): string {
  return PERSON_TYPE_LABELS[type] || type
}

const router = useRouter()
const roomContextStore = useRoomContextStore()

const loading = ref(false)
const saving = ref(false)
const persons = ref<PersonItem[]>([])
const orgUnits = ref<OrgUnitItem[]>([])

const filters = reactive({
  name: '',
  person_type: '',
  status: '',
})

const filteredPersons = computed(() => {
  return persons.value.filter((p) => {
    if (filters.name && !p.name.includes(filters.name)) return false
    if (filters.person_type && p.person_type !== filters.person_type) return false
    if (filters.status && p.status !== filters.status) return false
    return true
  })
})

const orgUnitMap = computed(() => {
  const map = new Map<number, OrgUnitItem>()
  for (const unit of orgUnits.value) {
    map.set(unit.id, unit)
  }
  return map
})

function orgUnitLabel(id: number | null): string {
  if (id == null) return ''
  const unit = orgUnitMap.value.get(id)
  if (!unit) return ''
  if (unit.parent_id) {
    const parent = orgUnitMap.value.get(unit.parent_id)
    return parent ? `${parent.name} / ${unit.name}` : unit.name
  }
  return unit.name
}

// Form
const formVisible = ref(false)
const editingPerson = ref<PersonItem | null>(null)
const formRef = ref<FormInstance>()
const formData = reactive({
  code: '',
  name: '',
  person_type: 'duty_operator',
  phone: '',
  participate_schedule: true,
  remark: '',
})
const formRules: FormRules = {
  name: [{ required: true, message: '请输入姓名' }],
  person_type: [{ required: true, message: '请选择人员类型' }],
}

onMounted(async () => {
  await Promise.all([loadOrgUnits(), loadPersons()])
})

watch(() => roomContextStore.currentRoomId, () => {
  void loadPersons()
})

watch(() => formData.person_type, (personType) => {
  if (personType !== 'duty_operator') formData.participate_schedule = false
})

async function loadOrgUnits() {
  try {
    const resp = await httpClient.get<OrgUnitItem[]>('/org-units')
    orgUnits.value = resp.data
  } catch {
    // org units data is optional for the page to function
  }
}

async function loadPersons() {
  loading.value = true
  try {
    const resp = await httpClient.get<PersonItem[]>('/persons')
    persons.value = resp.data
  } catch (err) {
    ElMessage.error(resolveErrorMessage(err, '加载人员列表失败'))
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.name = ''
  filters.person_type = ''
  filters.status = ''
}

function openCreateDialog() {
  editingPerson.value = null
  formData.code = ''
  formData.name = ''
  formData.person_type = 'duty_operator'
  formData.phone = ''
  formData.participate_schedule = true
  formData.remark = ''
  formVisible.value = true
}

function openEditDialog(person: PersonItem) {
  editingPerson.value = person
  formData.code = person.code
  formData.name = person.name
  formData.person_type = person.person_type
  formData.phone = person.phone || ''
  formData.participate_schedule = person.participate_schedule
  formData.remark = person.remark || ''
  formVisible.value = true
}

function resetForm() {
  editingPerson.value = null
  formData.code = ''
  formData.name = ''
  formData.person_type = 'duty_operator'
  formData.phone = ''
  formData.participate_schedule = true
  formData.remark = ''
  formRef.value?.resetFields()
}

async function save() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (editingPerson.value) {
      await httpClient.put(`/persons/${editingPerson.value.id}`, {
        name: formData.name,
        person_type: formData.person_type,
        phone: formData.phone || null,
        participate_schedule: formData.participate_schedule,
        remark: formData.remark || null,
      })
      ElMessage.success('编辑成功')
    } else {
      await httpClient.post('/persons', {
        ...(formData.code ? { code: formData.code } : {}),
        name: formData.name,
        person_type: formData.person_type,
        phone: formData.phone || null,
        participate_schedule: formData.participate_schedule,
        remark: formData.remark || null,
      })
      ElMessage.success('创建成功')
    }
    formVisible.value = false
    await loadPersons()
  } catch {
    ElMessage.error('操作失败')
  } finally {
    saving.value = false
  }
}

async function toggleStatus(person: PersonItem) {
  const action = person.status === 'enabled' ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(`确认${action}人员「${person.name}」吗？`, `${action}确认`)
    await httpClient.put(`/persons/${person.id}`, {
      status: person.status === 'enabled' ? 'disabled' : 'enabled',
    })
    ElMessage.success(`${action}成功`)
    await loadPersons()
  } catch {
    // cancelled
  }
}

function goToBindAccount(person: PersonItem) {
  router.push({ name: 'account-role', query: { bindPersonId: person.id, bindPersonName: `${person.name}（${person.code}）` } })
}
</script>

<style scoped>
.person-view h1 {
  margin: 0 0 16px;
  font-size: 24px;
  font-weight: 600;
}

.person-view__filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.person-view__filter-name {
  width: 200px;
}

.person-view__filter-type,
.person-view__filter-status {
  width: 160px;
}

.person-view__toolbar {
  margin-bottom: 16px;
}
</style>
