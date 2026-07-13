<template>
  <section class="shift-rule-view">
    <h1>班次规则</h1>

    <el-tabs v-model="activeTab" class="shift-rule-view__tabs">
      <!-- 班次定义 -->
      <el-tab-pane label="班次定义" name="shift-def">
        <div class="shift-rule-view__toolbar">
          <el-button type="primary" @click="openShiftDialog()">新增班次</el-button>
        </div>
        <el-table :data="shiftDefs" v-loading="shiftLoading" stripe>
          <el-table-column prop="code" label="编码" width="140" />
          <el-table-column prop="name" label="名称" width="140" />
          <el-table-column label="时间段" min-width="160">
            <template #default="{ row }">{{ row.start_time }} - {{ row.end_time }}</template>
          </el-table-column>
          <el-table-column prop="display_order" label="顺序" width="90" align="center" />
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.status === 'enabled' ? 'success' : 'info'" size="small">
                {{ row.status === 'enabled' ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openShiftDialog(row)">编辑</el-button>
              <el-button
                size="small"
                :type="row.status === 'enabled' ? 'warning' : 'success'"
                @click="toggleShiftStatus(row)"
              >
                {{ row.status === 'enabled' ? '停用' : '启用' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 排班规则 -->
      <el-tab-pane label="排班规则" name="shift-rule">
        <div class="shift-rule-view__toolbar">
          <el-button type="primary" @click="openRuleDialog()">新增规则</el-button>
        </div>
        <el-table :data="shiftRules" v-loading="ruleLoading" stripe>
          <el-table-column prop="code" label="规则编码" width="150" />
          <el-table-column prop="name" label="规则名称" min-width="180" />
          <el-table-column prop="cycle_days" label="循环天数" width="100" align="center" />
          <el-table-column prop="start_date" label="起始日期" width="120" />
          <el-table-column prop="persons_per_cell" label="每格人数" width="100" align="center" />
          <el-table-column label="适用机房" min-width="160">
            <template #default="{ row }">{{ orgUnitLabel(row.org_unit_id) || '全部' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="RULE_STATUS_TAG[row.status] || 'info'" size="small">
                {{ RULE_STATUS_LABELS[row.status] || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="320" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openRuleDialog(row)">编辑</el-button>
              <el-button
                v-if="row.status === 'draft'"
                size="small"
                type="success"
                @click="publishRule(row)"
                :loading="publishingId === row.id"
              >
                发布
              </el-button>
              <el-button size="small" type="danger" @click="deleteRule(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 班次定义 弹窗 -->
    <el-dialog
      v-model="shiftDialogVisible"
      :title="editingShift ? '编辑班次' : '新增班次'"
      width="480px"
      @closed="resetShiftForm"
    >
      <el-form ref="shiftFormRef" :model="shiftForm" :rules="shiftFormRules" label-position="top">
        <el-form-item label="班次编码" prop="code">
          <el-input v-model="shiftForm.code" :disabled="!!editingShift" placeholder="如 early/middle/night" />
        </el-form-item>
        <el-form-item label="班次名称" prop="name">
          <el-input v-model="shiftForm.name" placeholder="如 早班/中班/晚班" />
        </el-form-item>
        <el-form-item label="开始时间" prop="start_time">
          <el-input v-model="shiftForm.start_time" placeholder="HH:MM，如 00:00" />
        </el-form-item>
        <el-form-item label="结束时间" prop="end_time">
          <el-input v-model="shiftForm.end_time" placeholder="HH:MM，如 08:00" />
        </el-form-item>
        <el-form-item label="展示顺序">
          <el-input-number v-model="shiftForm.display_order" :min="0" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shiftDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="shiftSaving" @click="saveShift">保存</el-button>
      </template>
    </el-dialog>

    <!-- 排班规则 弹窗 -->
    <el-dialog
      v-model="ruleDialogVisible"
      :title="editingRule ? '编辑规则' : '新增规则'"
      width="900px"
      @closed="resetRuleForm"
    >
      <el-form ref="ruleFormRef" :model="ruleForm" :rules="ruleFormRules" label-position="top">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="规则编码" prop="code">
              <el-input v-model="ruleForm.code" :disabled="!!editingRule" placeholder="小写字母/数字/下划线" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="规则名称" prop="name">
              <el-input v-model="ruleForm.name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="循环天数 (N)" prop="cycle_days">
              <el-input-number v-model="ruleForm.cycle_days" :min="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="起始日期" prop="start_date">
              <el-date-picker
                v-model="ruleForm.start_date"
                type="date"
                :disabled-date="disablePastDates"
                placeholder="只能从明天起"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="每格人数" prop="persons_per_cell">
              <el-input-number v-model="ruleForm.persons_per_cell" :min="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="适用机房">
          <el-select v-model="ruleForm.org_unit_id" placeholder="不选则适用全部" style="width: 100%" clearable>
            <el-option
              v-for="unit in orgUnitOptions"
              :key="unit.id"
              :label="orgUnitDisplayLabel(unit)"
              :value="unit.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="ruleForm.remark" type="textarea" :rows="2" />
        </el-form-item>

        <el-divider content-position="left">
          排班表格（{{ ruleForm.cycle_days }} 天 × {{ enabledShiftDefs.length }} 班）
        </el-divider>

        <div v-if="ruleForm.cycle_days > 0" class="shift-rule-view__grid-container">
          <table class="shift-rule-view__grid-table">
            <thead>
              <tr>
                <th class="shift-rule-view__grid-day-header">天数 / 班次</th>
                <th
                  v-for="sd in enabledShiftDefs"
                  :key="sd.id"
                  class="shift-rule-view__grid-shift-header"
                >
                  <div>{{ sd.name }}</div>
                  <div class="shift-rule-view__grid-shift-time">{{ sd.start_time }}-{{ sd.end_time }}</div>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="dayNo in ruleForm.cycle_days" :key="dayNo">
                <td class="shift-rule-view__grid-day-label">
                  <span class="shift-rule-view__grid-day-no">第 {{ dayNo }} 天</span>
                  <span class="shift-rule-view__grid-day-date">
                    {{ computeDayDate(dayNo) }}
                  </span>
                </td>
                <td
                  v-for="sd in enabledShiftDefs"
                  :key="sd.id"
                  class="shift-rule-view__grid-cell"
                >
                  <el-select
                    :model-value="getCellPersons(dayNo, sd.id)"
                    @update:model-value="(val: number[]) => setCellPersons(dayNo, sd.id, val)"
                    multiple
                    filterable
                    placeholder="选择人员"
                    style="width: 100%"
                    :disabled="!ruleForm.org_unit_id"
                  >
                    <el-option
                      v-for="p in availablePersons"
                      :key="p.id"
                      :label="p.name"
                      :value="p.id"
                    />
                  </el-select>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <el-empty v-else description="请设置循环天数" />
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="ruleSaving" @click="saveRule">
          {{ editingRule && editingRule.status === 'published' ? '保存并重新发布' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import { httpClient, resolveErrorMessage } from '@/services/http'

interface OrgUnitItem {
  id: number
  code: string
  name: string
  type: string
  parent_id: number | null
}

interface ShiftDefItem {
  id: number
  code: string
  name: string
  start_time: string
  end_time: string
  display_order: number
  status: string
}

interface ShiftRuleItemData {
  id: number
  day_no: number
  cell_persons: Record<string, number[]>
}

interface ShiftRuleData {
  id: number
  org_unit_id: number | null
  code: string
  name: string
  cycle_days: number
  start_date: string
  persons_per_cell: number
  status: string
  remark: string | null
  latest_version_id: number | null
  items: ShiftRuleItemData[]
}

interface PersonItem {
  id: number
  code: string
  name: string
  person_type: string
  org_unit_id: number | null
  participate_schedule: boolean
  status: string
}

const RULE_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  published: '已发布',
}

const RULE_STATUS_TAG: Record<string, string> = {
  draft: 'info',
  published: 'success',
}

const activeTab = ref('shift-def')

// ── Org units ──
const orgUnits = ref<OrgUnitItem[]>([])

const orgUnitOptions = computed(() =>
  orgUnits.value.filter((u) => u.type === 'room' || u.type === 'station'),
)

const orgUnitMap = computed(() => {
  const map = new Map<number, OrgUnitItem>()
  for (const unit of orgUnits.value) map.set(unit.id, unit)
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

function orgUnitDisplayLabel(unit: OrgUnitItem): string {
  return orgUnitLabel(unit.id) || unit.name
}

// ── Persons (for grid cell selection) ──
const persons = ref<PersonItem[]>([])

const availablePersons = computed(() =>
  persons.value.filter(
    (p) =>
      p.participate_schedule &&
      p.status === 'enabled' &&
      (!ruleForm.org_unit_id || p.org_unit_id === ruleForm.org_unit_id),
  ),
)

const enabledShiftDefs = computed(() =>
  shiftDefs.value.filter((s) => s.status === 'enabled').sort((a, b) => a.display_order - b.display_order),
)

// ── 班次定义 ──
const shiftDefs = ref<ShiftDefItem[]>([])
const shiftLoading = ref(false)
const shiftSaving = ref(false)
const shiftDialogVisible = ref(false)
const editingShift = ref<ShiftDefItem | null>(null)
const shiftFormRef = ref<FormInstance>()
const shiftForm = reactive({
  code: '',
  name: '',
  start_time: '',
  end_time: '',
  display_order: 0,
})
const shiftFormRules: FormRules = {
  code: [{ required: true, message: '请输入班次编码' }],
  name: [{ required: true, message: '请输入班次名称' }],
  start_time: [
    { required: true, message: '请输入开始时间' },
    { pattern: /^\d{2}:\d{2}$/, message: '格式应为 HH:MM' },
  ],
  end_time: [
    { required: true, message: '请输入结束时间' },
    { pattern: /^\d{2}:\d{2}$/, message: '格式应为 HH:MM' },
  ],
}

// ── 排班规则 ──
const shiftRules = ref<ShiftRuleData[]>([])
const ruleLoading = ref(false)
const ruleSaving = ref(false)
const publishingId = ref<number | null>(null)
const ruleDialogVisible = ref(false)
const editingRule = ref<ShiftRuleData | null>(null)
const ruleFormRef = ref<FormInstance>()
const ruleForm = reactive({
  code: '',
  name: '',
  cycle_days: 6,
  start_date: null as Date | null,
  persons_per_cell: 2,
  org_unit_id: null as number | null,
  remark: '',
  cellData: {} as Record<number, Record<number, number[]>>,
})
const ruleFormRules: FormRules = {
  code: [
    { required: true, message: '请输入规则编码' },
    { pattern: /^[a-z0-9_]+$/, message: '只能包含小写字母、数字、下划线' },
  ],
  name: [{ required: true, message: '请输入规则名称' }],
  cycle_days: [{ required: true, message: '请设置循环天数' }],
  start_date: [{ required: true, message: '请选择起始日期' }],
  persons_per_cell: [{ required: true, message: '请设置每格人数' }],
}

onMounted(async () => {
  await Promise.all([loadOrgUnits(), loadShiftDefs(), loadShiftRules(), loadPersons()])
})

async function loadOrgUnits() {
  try {
    const resp = await httpClient.get<OrgUnitItem[]>('/org-units')
    orgUnits.value = resp.data
  } catch {
    // 组织数据可选
  }
}

async function loadShiftDefs() {
  shiftLoading.value = true
  try {
    const resp = await httpClient.get<ShiftDefItem[]>('/shifts')
    shiftDefs.value = resp.data
  } catch {
    ElMessage.error('加载班次列表失败')
  } finally {
    shiftLoading.value = false
  }
}

async function loadShiftRules() {
  ruleLoading.value = true
  try {
    const resp = await httpClient.get<ShiftRuleData[]>('/shift-rules')
    shiftRules.value = resp.data
  } catch {
    ElMessage.error('加载排班规则失败')
  } finally {
    ruleLoading.value = false
  }
}

async function loadPersons() {
  try {
    const resp = await httpClient.get<PersonItem[]>('/persons')
    persons.value = resp.data
  } catch {
    // persons optional
  }
}

function disablePastDates(date: Date): boolean {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return date <= today
}

function computeDayDate(dayNo: number): string {
  if (!ruleForm.start_date) return ''
  const d = new Date(ruleForm.start_date)
  d.setDate(d.getDate() + dayNo - 1)
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

function getCellPersons(dayNo: number, shiftDefId: number): number[] {
  return ruleForm.cellData[dayNo]?.[shiftDefId] ?? []
}

function setCellPersons(dayNo: number, shiftDefId: number, personIds: number[]) {
  if (!ruleForm.cellData[dayNo]) {
    ruleForm.cellData[dayNo] = {}
  }
  ruleForm.cellData[dayNo][shiftDefId] = personIds
}

function formatDate(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

// ── 班次定义 操作 ──
function openShiftDialog(shift?: ShiftDefItem) {
  editingShift.value = shift ?? null
  shiftForm.code = shift?.code ?? ''
  shiftForm.name = shift?.name ?? ''
  shiftForm.start_time = shift?.start_time ?? ''
  shiftForm.end_time = shift?.end_time ?? ''
  shiftForm.display_order = shift?.display_order ?? 0
  shiftDialogVisible.value = true
}

function resetShiftForm() {
  editingShift.value = null
  shiftForm.code = ''
  shiftForm.name = ''
  shiftForm.start_time = ''
  shiftForm.end_time = ''
  shiftForm.display_order = 0
  shiftFormRef.value?.resetFields()
}

async function saveShift() {
  const valid = await shiftFormRef.value?.validate().catch(() => false)
  if (!valid) return
  shiftSaving.value = true
  try {
    if (editingShift.value) {
      await httpClient.put(`/shifts/${editingShift.value.id}`, {
        name: shiftForm.name,
        start_time: shiftForm.start_time,
        end_time: shiftForm.end_time,
        display_order: shiftForm.display_order,
      })
      ElMessage.success('编辑成功')
    } else {
      await httpClient.post('/shifts', {
        code: shiftForm.code,
        name: shiftForm.name,
        start_time: shiftForm.start_time,
        end_time: shiftForm.end_time,
        display_order: shiftForm.display_order,
      })
      ElMessage.success('创建成功')
    }
    shiftDialogVisible.value = false
    await loadShiftDefs()
  } catch (err) {
    ElMessage.error(resolveErrorMessage(err, '操作失败'))
  } finally {
    shiftSaving.value = false
  }
}

async function toggleShiftStatus(shift: ShiftDefItem) {
  const action = shift.status === 'enabled' ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(`确认${action}班次「${shift.name}」吗？`, `${action}确认`)
    await httpClient.put(`/shifts/${shift.id}`, {
      status: shift.status === 'enabled' ? 'disabled' : 'enabled',
    })
    ElMessage.success(`${action}成功`)
    await loadShiftDefs()
  } catch {
    // cancelled
  }
}

// ── 排班规则 操作 ──
function openRuleDialog(rule?: ShiftRuleData) {
  editingRule.value = rule ?? null
  ruleForm.code = rule?.code ?? ''
  ruleForm.name = rule?.name ?? ''
  ruleForm.cycle_days = rule?.cycle_days ?? 6
  ruleForm.start_date = rule?.start_date ? new Date(rule.start_date) : null
  ruleForm.persons_per_cell = rule?.persons_per_cell ?? 2
  ruleForm.org_unit_id = rule?.org_unit_id ?? null
  ruleForm.remark = rule?.remark ?? ''

  // Initialize cell data from existing items
  ruleForm.cellData = {}
  if (rule?.items) {
    for (const item of rule.items) {
      ruleForm.cellData[item.day_no] = {}
      for (const [shiftDefId, personIds] of Object.entries(item.cell_persons)) {
        ruleForm.cellData[item.day_no][Number(shiftDefId)] = personIds
      }
    }
  }

  ruleDialogVisible.value = true
}

function resetRuleForm() {
  editingRule.value = null
  ruleForm.code = ''
  ruleForm.name = ''
  ruleForm.cycle_days = 6
  ruleForm.start_date = null
  ruleForm.persons_per_cell = 2
  ruleForm.org_unit_id = null
  ruleForm.remark = ''
  ruleForm.cellData = {}
  ruleFormRef.value?.resetFields()
}

function buildDaysPayload(): Array<{ day_no: number; cells: Array<{ shift_def_id: number; person_ids: number[] }> }> {
  const days = []
  for (let dayNo = 1; dayNo <= ruleForm.cycle_days; dayNo++) {
    const cells = []
    for (const sd of enabledShiftDefs.value) {
      cells.push({
        shift_def_id: sd.id,
        person_ids: getCellPersons(dayNo, sd.id),
      })
    }
    days.push({ day_no: dayNo, cells })
  }
  return days
}

async function saveRule() {
  const valid = await ruleFormRef.value?.validate().catch(() => false)
  if (!valid) return

  const days = buildDaysPayload()
  const startDate = ruleForm.start_date ? formatDate(ruleForm.start_date) : ''
  const isRepublish = editingRule.value?.status === 'published'

  ruleSaving.value = true
  try {
    if (editingRule.value) {
      await httpClient.put(`/shift-rules/${editingRule.value.id}`, {
        name: ruleForm.name,
        cycle_days: ruleForm.cycle_days,
        start_date: startDate,
        persons_per_cell: ruleForm.persons_per_cell,
        org_unit_id: ruleForm.org_unit_id,
        remark: ruleForm.remark || null,
        days,
      })
      ElMessage.success(isRepublish ? '保存并重新发布成功' : '编辑成功')
    } else {
      await httpClient.post('/shift-rules', {
        code: ruleForm.code,
        name: ruleForm.name,
        cycle_days: ruleForm.cycle_days,
        start_date: startDate,
        persons_per_cell: ruleForm.persons_per_cell,
        org_unit_id: ruleForm.org_unit_id,
        remark: ruleForm.remark || null,
        days,
      })
      ElMessage.success('创建成功')
    }
    ruleDialogVisible.value = false
    await loadShiftRules()
  } catch (err) {
    ElMessage.error(resolveErrorMessage(err, '操作失败'))
  } finally {
    ruleSaving.value = false
  }
}

async function publishRule(rule: ShiftRuleData) {
  try {
    await ElMessageBox.confirm('发布后规则立即生效，排班将自动生成。确认发布？', '发布确认')
  } catch {
    return
  }
  publishingId.value = rule.id
  try {
    await httpClient.post(`/shift-rules/${rule.id}/publish`)
    ElMessage.success('规则已发布')
    await loadShiftRules()
  } catch (err) {
    ElMessage.error(resolveErrorMessage(err, '发布失败'))
  } finally {
    publishingId.value = null
  }
}

async function deleteRule(rule: ShiftRuleData) {
  try {
    await ElMessageBox.confirm(`确认删除规则「${rule.name}」吗？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await httpClient.delete(`/shift-rules/${rule.id}`)
    ElMessage.success('删除成功')
    await loadShiftRules()
  } catch (err) {
    ElMessage.error(resolveErrorMessage(err, '删除失败'))
  }
}
</script>

<style scoped>
.shift-rule-view h1 {
  margin: 0 0 16px;
  font-size: 24px;
  font-weight: 600;
}

.shift-rule-view__toolbar {
  margin-bottom: 16px;
}

.shift-rule-view__grid-container {
  overflow-x: auto;
  max-height: 500px;
  overflow-y: auto;
}

.shift-rule-view__grid-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
}

.shift-rule-view__grid-table th,
.shift-rule-view__grid-table td {
  border: 1px solid #dcdfe6;
  padding: 8px;
  text-align: center;
  vertical-align: top;
  min-width: 120px;
}

.shift-rule-view__grid-day-header {
  background: #f5f7fa;
  font-weight: 600;
  min-width: 100px;
}

.shift-rule-view__grid-shift-header {
  background: #f5f7fa;
  font-weight: 600;
}

.shift-rule-view__grid-shift-time {
  font-size: 11px;
  color: #909399;
  font-weight: normal;
}

.shift-rule-view__grid-day-label {
  background: #fafafa;
  font-weight: 500;
}

.shift-rule-view__grid-day-no {
  display: block;
}

.shift-rule-view__grid-day-date {
  display: block;
  font-size: 11px;
  color: #909399;
}

.shift-rule-view__grid-cell {
  min-width: 180px;
}
</style>
