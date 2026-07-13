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
          <el-table-column label="适用台站类型" width="150">
            <template #default="{ row }">{{ stationTypeLabel(row.station_type) }}</template>
          </el-table-column>
          <el-table-column prop="persons_per_shift" label="每班人数" width="100" align="center" />
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
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openRuleDialog(row)">编辑</el-button>
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
      width="720px"
      @closed="resetRuleForm"
    >
      <el-form ref="ruleFormRef" :model="ruleForm" :rules="ruleFormRules" label-position="top">
        <el-form-item label="规则编码" prop="code">
          <el-input v-model="ruleForm.code" :disabled="!!editingRule" placeholder="小写字母/数字/下划线" />
        </el-form-item>
        <el-form-item label="规则名称" prop="name">
          <el-input v-model="ruleForm.name" />
        </el-form-item>
        <el-form-item label="适用台站类型" prop="station_type">
          <el-select v-model="ruleForm.station_type" style="width: 100%">
            <el-option
              v-for="(label, value) in STATION_TYPE_LABELS"
              :key="value"
              :label="label"
              :value="value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="每班人数" prop="persons_per_shift">
          <el-input-number v-model="ruleForm.persons_per_shift" :min="1" style="width: 100%" />
        </el-form-item>
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
        <el-form-item v-if="editingRule" label="状态">
          <el-select v-model="ruleForm.status" style="width: 100%">
            <el-option
              v-for="(label, value) in RULE_STATUS_LABELS"
              :key="value"
              :label="label"
              :value="value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="ruleForm.remark" type="textarea" :rows="2" />
        </el-form-item>

        <el-divider content-position="left">轮班序列</el-divider>
        <div class="shift-rule-view__items">
          <div v-for="(item, index) in ruleForm.items" :key="index" class="shift-rule-view__item-row">
            <el-select v-model="item.group_type" placeholder="班组" class="shift-rule-view__item-group">
              <el-option
                v-for="(label, value) in GROUP_TYPE_LABELS"
                :key="value"
                :label="label"
                :value="value"
              />
            </el-select>
            <el-input-number v-model="item.sequence_no" :min="0" placeholder="顺序" class="shift-rule-view__item-seq" />
            <el-select v-model="item.shift_code" placeholder="班次" class="shift-rule-view__item-shift">
              <el-option
                v-for="(label, value) in SHIFT_CODE_LABELS"
                :key="value"
                :label="label"
                :value="value"
              />
            </el-select>
            <el-input-number v-model="item.repeat_count" :min="1" placeholder="重复" class="shift-rule-view__item-repeat" />
            <el-button type="danger" size="small" text @click="removeRuleItem(index)">删除</el-button>
          </div>
          <el-button size="small" @click="addRuleItem">+ 添加序列项</el-button>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="ruleSaving" @click="saveRule">保存</el-button>
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
  group_type: string
  sequence_no: number
  shift_code: string
  repeat_count: number
  remark?: string | null
}

interface ShiftRuleData {
  id: number
  org_unit_id: number | null
  code: string
  name: string
  station_type: string
  persons_per_shift: number
  rule_type: string
  status: string
  remark: string | null
  items: ShiftRuleItemData[]
}

const STATION_TYPE_LABELS: Record<string, string> = {
  station_broadcast: '广播发射台',
  station_satellite: '卫星地球站',
}

const RULE_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  enabled: '启用',
  disabled: '停用',
}

const RULE_STATUS_TAG: Record<string, string> = {
  draft: 'info',
  enabled: 'success',
  disabled: 'danger',
}

const GROUP_TYPE_LABELS: Record<string, string> = {
  night_early_group: '晚早组',
  middle_group: '中班组',
}

const SHIFT_CODE_LABELS: Record<string, string> = {
  early: '早班',
  middle: '中班',
  night: '晚班',
  rest: '休息',
}

function stationTypeLabel(type: string): string {
  return STATION_TYPE_LABELS[type] || type
}

const activeTab = ref('shift-def')

// ── Org units（用于机房选择/展示）──
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
const ruleDialogVisible = ref(false)
const editingRule = ref<ShiftRuleData | null>(null)
const ruleFormRef = ref<FormInstance>()
const ruleForm = reactive({
  code: '',
  name: '',
  station_type: 'station_broadcast',
  persons_per_shift: 2,
  org_unit_id: null as number | null,
  status: 'draft',
  remark: '',
  items: [] as ShiftRuleItemData[],
})
const ruleFormRules: FormRules = {
  code: [
    { required: true, message: '请输入规则编码' },
    { pattern: /^[a-z0-9_]+$/, message: '只能包含小写字母、数字、下划线' },
  ],
  name: [{ required: true, message: '请输入规则名称' }],
  station_type: [{ required: true, message: '请选择适用台站类型' }],
  persons_per_shift: [{ required: true, message: '请输入每班人数' }],
}

onMounted(async () => {
  await Promise.all([loadOrgUnits(), loadShiftDefs(), loadShiftRules()])
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
  ruleForm.station_type = rule?.station_type ?? 'station_broadcast'
  ruleForm.persons_per_shift = rule?.persons_per_shift ?? 2
  ruleForm.org_unit_id = rule?.org_unit_id ?? null
  ruleForm.status = rule?.status ?? 'draft'
  ruleForm.remark = rule?.remark ?? ''
  ruleForm.items = rule
    ? rule.items.map((i) => ({
        group_type: i.group_type,
        sequence_no: i.sequence_no,
        shift_code: i.shift_code,
        repeat_count: i.repeat_count,
        remark: i.remark ?? null,
      }))
    : []
  ruleDialogVisible.value = true
}

function resetRuleForm() {
  editingRule.value = null
  ruleForm.code = ''
  ruleForm.name = ''
  ruleForm.station_type = 'station_broadcast'
  ruleForm.persons_per_shift = 2
  ruleForm.org_unit_id = null
  ruleForm.status = 'draft'
  ruleForm.remark = ''
  ruleForm.items = []
  ruleFormRef.value?.resetFields()
}

function addRuleItem() {
  ruleForm.items.push({
    group_type: 'night_early_group',
    sequence_no: ruleForm.items.length + 1,
    shift_code: 'early',
    repeat_count: 1,
    remark: null,
  })
}

function removeRuleItem(index: number) {
  ruleForm.items.splice(index, 1)
}

async function saveRule() {
  const valid = await ruleFormRef.value?.validate().catch(() => false)
  if (!valid) return
  ruleSaving.value = true
  try {
    const items = ruleForm.items.map((i) => ({
      group_type: i.group_type,
      sequence_no: i.sequence_no,
      shift_code: i.shift_code,
      repeat_count: i.repeat_count,
      remark: i.remark || null,
    }))
    if (editingRule.value) {
      await httpClient.put(`/shift-rules/${editingRule.value.id}`, {
        name: ruleForm.name,
        station_type: ruleForm.station_type,
        persons_per_shift: ruleForm.persons_per_shift,
        org_unit_id: ruleForm.org_unit_id,
        status: ruleForm.status,
        remark: ruleForm.remark || null,
        items,
      })
      ElMessage.success('编辑成功')
    } else {
      await httpClient.post('/shift-rules', {
        code: ruleForm.code,
        name: ruleForm.name,
        station_type: ruleForm.station_type,
        persons_per_shift: ruleForm.persons_per_shift,
        org_unit_id: ruleForm.org_unit_id,
        remark: ruleForm.remark || null,
        items,
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

.shift-rule-view__items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.shift-rule-view__item-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.shift-rule-view__item-group {
  width: 130px;
}

.shift-rule-view__item-shift {
  width: 110px;
}

.shift-rule-view__item-seq,
.shift-rule-view__item-repeat {
  width: 110px;
}
</style>
