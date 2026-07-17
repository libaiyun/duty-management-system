<template>
  <section class="shift-rule-view">
    <h1>排班规则</h1>
    <div class="shift-rule-view__toolbar"><el-button type="primary" @click="openDialog()">新增规则</el-button></div>
    <el-table :data="shiftRules" v-loading="loading" stripe>
      <el-table-column prop="code" label="规则编码" width="150" />
      <el-table-column prop="name" label="规则名称" min-width="180" />
      <el-table-column prop="cycle_days" label="循环天数" width="100" align="center" />
      <el-table-column prop="start_date" label="起始日期" width="120" />
      <el-table-column prop="persons_per_cell" label="每格人数" width="100" align="center" />
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }"><el-tag :type="STATUS_TAG[row.status] || 'info'" size="small">{{ STATUS_LABELS[row.status] || row.status }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="320" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openDialog(row)">编辑</el-button>
          <el-button v-if="row.status === 'draft'" size="small" type="success" :loading="publishingId === row.id" @click="publish(row)">发布</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑规则' : '新增规则'" width="900px" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="规则编码" prop="code"><el-input v-model="form.code" :disabled="!!editing" placeholder="留空自动生成" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="规则名称" prop="name"><el-input v-model="form.name" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="循环天数 (N)" prop="cycle_days"><el-input-number v-model="form.cycle_days" :min="1" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="起始日期" prop="start_date"><el-date-picker v-model="form.start_date" type="date" :disabled-date="disablePastDates" placeholder="只能从明天起" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="每格人数" prop="persons_per_cell"><el-input-number v-model="form.persons_per_cell" :min="1" style="width: 100%" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
        <el-divider content-position="left">排班表格（{{ form.cycle_days }} 天 × {{ enabledShiftDefs.length }} 班）</el-divider>
        <div v-if="form.cycle_days > 0" class="shift-rule-view__grid-container">
          <table class="shift-rule-view__grid-table">
            <thead><tr><th class="shift-rule-view__grid-day-header">天数 / 班次</th><th v-for="shift in enabledShiftDefs" :key="shift.id" class="shift-rule-view__grid-shift-header"><div>{{ shift.name }}</div><div class="shift-rule-view__grid-shift-time">{{ shift.start_time }}-{{ shift.end_time }}</div></th></tr></thead>
            <tbody><tr v-for="dayNo in form.cycle_days" :key="dayNo"><td class="shift-rule-view__grid-day-label"><span class="shift-rule-view__grid-day-no">第 {{ dayNo }} 天</span><span class="shift-rule-view__grid-day-date">{{ computeDayDate(dayNo) }}</span></td><td v-for="shift in enabledShiftDefs" :key="shift.id" class="shift-rule-view__grid-cell"><el-select v-for="slotNo in form.persons_per_cell" :key="slotNo" :model-value="getCellPerson(dayNo, shift.id, slotNo)" @update:model-value="(value: number) => setCellPerson(dayNo, shift.id, slotNo, value)" filterable placeholder="选择人员" style="width: 100%"><el-option v-for="person in availablePersons" :key="person.id" :label="person.name" :value="person.id" /></el-select></td></tr></tbody>
          </table>
        </div>
        <el-empty v-else description="请设置循环天数" />
      </el-form>
        <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import { httpClient, resolveErrorMessage } from '@/services/http'

interface ShiftDefItem { id: number; code: string; name: string; start_time: string; end_time: string; display_order: number; status: string }
interface ShiftRuleItem { id: number; day_no: number; cell_persons: Record<string, number[]> }
interface ShiftRuleData { id: number; code: string; name: string; cycle_days: number; start_date: string; persons_per_cell: number; status: string; remark: string | null; latest_version_id: number | null; items: ShiftRuleItem[] }
interface PersonItem { id: number; code: string; name: string; person_type: string; org_unit_id: number | null; participate_schedule: boolean; status: string }

const STATUS_LABELS: Record<string, string> = { draft: '草稿', published: '已发布' }
const STATUS_TAG: Record<string, string> = { draft: 'info', published: 'success' }
const shiftRules = ref<ShiftRuleData[]>([])
const shiftDefs = ref<ShiftDefItem[]>([])
const persons = ref<PersonItem[]>([])
const loading = ref(false)
const saving = ref(false)
const publishingId = ref<number | null>(null)
const dialogVisible = ref(false)
const editing = ref<ShiftRuleData | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({ code: '', name: '', cycle_days: 6, start_date: null as Date | null, persons_per_cell: 2, remark: '', cellData: {} as Record<number, Record<number, number[]>> })
const enabledShiftDefs = computed(() => shiftDefs.value.filter((shift) => shift.status === 'enabled').sort((a, b) => a.display_order - b.display_order))
const availablePersons = computed(() => persons.value.filter((person) => person.participate_schedule && person.status === 'enabled'))
const formRules: FormRules = {
  name: [{ required: true, message: '请输入规则名称' }],
  cycle_days: [{ required: true, message: '请设置循环天数' }],
  start_date: [{ required: true, message: '请选择起始日期' }],
  persons_per_cell: [{ required: true, message: '请设置每格人数' }],
}

onMounted(async () => { await Promise.all([loadRules(), loadShiftDefs(), loadPersons()]) })

async function loadRules() {
  loading.value = true
  try { shiftRules.value = (await httpClient.get<ShiftRuleData[]>('/shift-rules')).data } catch (err) { ElMessage.error(resolveErrorMessage(err, '加载排班规则失败')) } finally { loading.value = false }
}
async function loadShiftDefs() {
  try { shiftDefs.value = (await httpClient.get<ShiftDefItem[]>('/shifts')).data } catch (err) { ElMessage.error(resolveErrorMessage(err, '加载班次列表失败')) }
}
async function loadPersons() {
  try { persons.value = (await httpClient.get<PersonItem[]>('/persons')).data } catch { /* optional list */ }
}
function disablePastDates(date: Date) { const today = new Date(); today.setHours(0, 0, 0, 0); return date <= today }
function computeDayDate(dayNo: number) { if (!form.start_date) return ''; const date = new Date(form.start_date); date.setDate(date.getDate() + dayNo - 1); return `${date.getMonth() + 1}月${date.getDate()}日` }
function getCellPersons(dayNo: number, shiftDefId: number) { return form.cellData[dayNo]?.[shiftDefId] ?? [] }
function getCellPerson(dayNo: number, shiftDefId: number, slotNo: number) { return getCellPersons(dayNo, shiftDefId)[slotNo - 1] }
function setCellPerson(dayNo: number, shiftDefId: number, slotNo: number, personId: number) {
  if (!form.cellData[dayNo]) form.cellData[dayNo] = {}
  const personIds = form.cellData[dayNo][shiftDefId] ?? []
  personIds[slotNo - 1] = personId
  form.cellData[dayNo][shiftDefId] = personIds
}
function formatDate(date: Date) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}` }

function openDialog(rule?: ShiftRuleData) {
  editing.value = rule ?? null
  form.code = rule?.code ?? ''; form.name = rule?.name ?? ''; form.cycle_days = rule?.cycle_days ?? 6; form.start_date = rule?.start_date ? new Date(rule.start_date) : null; form.persons_per_cell = rule?.persons_per_cell ?? 2; form.remark = rule?.remark ?? ''; form.cellData = {}
  for (const item of rule?.items ?? []) { form.cellData[item.day_no] = {}; for (const [shiftDefId, personIds] of Object.entries(item.cell_persons)) form.cellData[item.day_no][Number(shiftDefId)] = personIds }
  dialogVisible.value = true
}
function resetForm() { editing.value = null; form.code = ''; form.name = ''; form.cycle_days = 6; form.start_date = null; form.persons_per_cell = 2; form.remark = ''; form.cellData = {}; formRef.value?.resetFields() }
function buildDaysPayload() { return Array.from({ length: form.cycle_days }, (_, index) => ({ day_no: index + 1, cells: enabledShiftDefs.value.map((shift) => ({ shift_def_id: shift.id, person_ids: getCellPersons(index + 1, shift.id).slice(0, form.persons_per_cell).filter((personId): personId is number => typeof personId === 'number') })) })) }
async function save() {
  const valid = await formRef.value?.validate().catch(() => false); if (!valid) return
  saving.value = true
  const payload = { name: form.name, cycle_days: form.cycle_days, start_date: form.start_date ? formatDate(form.start_date) : '', persons_per_cell: form.persons_per_cell, remark: form.remark || null, days: buildDaysPayload() }
  try {
    if (editing.value) { await httpClient.put(`/shift-rules/${editing.value.id}`, payload); ElMessage.success('编辑成功') }
    else { await httpClient.post('/shift-rules', { ...(form.code ? { code: form.code } : {}), ...payload }); ElMessage.success('创建成功') }
    dialogVisible.value = false; await loadRules()
  } catch (err) { ElMessage.error(resolveErrorMessage(err, '操作失败')) } finally { saving.value = false }
}
async function publish(rule: ShiftRuleData) {
  try { await ElMessageBox.confirm('发布后规则立即生效，排班将自动生成。确认发布？', '发布确认') } catch { return }
  publishingId.value = rule.id
  try { await httpClient.post(`/shift-rules/${rule.id}/publish`); ElMessage.success('规则已发布'); await loadRules() } catch (err) { ElMessage.error(resolveErrorMessage(err, '发布失败')) } finally { publishingId.value = null }
}
async function remove(rule: ShiftRuleData) {
  try { await ElMessageBox.confirm(`确认删除规则「${rule.name}」吗？`, '删除确认', { type: 'warning' }) } catch { return }
  try { await httpClient.delete(`/shift-rules/${rule.id}`); ElMessage.success('删除成功'); await loadRules() } catch (err) { ElMessage.error(resolveErrorMessage(err, '删除失败')) }
}
</script>

<style scoped>
.shift-rule-view h1 { margin: 0 0 16px; font-size: 24px; font-weight: 600; }
.shift-rule-view__toolbar { margin-bottom: 16px; }
.shift-rule-view__grid-container { overflow: auto; max-height: 500px; scrollbar-gutter: stable; }
.shift-rule-view__grid-table { border-collapse: collapse; table-layout: fixed; width: 100%; font-size: 13px; }
.shift-rule-view__grid-table th, .shift-rule-view__grid-table td { border: 1px solid #dcdfe6; padding: 8px; text-align: center; vertical-align: top; min-width: 120px; }
.shift-rule-view__grid-day-header, .shift-rule-view__grid-shift-header { background: #f5f7fa; font-weight: 600; }
.shift-rule-view__grid-day-header { min-width: 100px; }
.shift-rule-view__grid-shift-time, .shift-rule-view__grid-day-date { display: block; font-size: 11px; color: #909399; font-weight: normal; }
.shift-rule-view__grid-day-label { background: #fafafa; font-weight: 500; }
.shift-rule-view__grid-day-no { display: block; }
.shift-rule-view__grid-shift-header, .shift-rule-view__grid-cell { width: 180px; }
.shift-rule-view__grid-cell .el-select + .el-select { margin-top: 8px; }
</style>
