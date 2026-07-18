<template>
  <section class="actual-duty-view">
    <div class="actual-duty-view__header"><h1>值班变更台账</h1></div>
    <el-form inline aria-label="值班变更台账查询条件">
      <el-form-item label="日期范围"><el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" /></el-form-item>
      <el-form-item label="人员 ID"><el-input-number v-model="personId" :min="1" controls-position="right" /></el-form-item>
      <el-form-item label="班次 ID"><el-input-number v-model="shiftDefId" :min="1" controls-position="right" /></el-form-item>
      <el-form-item label="变更类型"><el-select v-model="sourceType" clearable placeholder="全部"><el-option label="换班" value="swap" /><el-option label="历史人工修正" value="historical_correction" /><el-option label="人工调整" value="manual" /></el-select></el-form-item>
      <el-form-item><el-button type="primary" @click="load">查询</el-button></el-form-item>
    </el-form>
    <el-table :data="items" v-loading="loading" border>
      <el-table-column prop="duty_date" label="日期" width="120" />
      <el-table-column prop="shift_def_name" label="班次" width="120" />
      <el-table-column label="班次时间" min-width="180"><template #default="{ row }">{{ formatShiftTime(row) }}</template></el-table-column>
      <el-table-column prop="original_person_name" label="原始排班人员" />
      <el-table-column prop="before_person_name" label="变更前人员" />
      <el-table-column prop="after_person_name" label="变更后人员" />
      <el-table-column label="变更类型"><template #default="{ row }">{{ sourceLabel(row.change_type) }}</template></el-table-column>
      <el-table-column prop="source_biz_no" label="来源业务单" />
      <el-table-column prop="reason" label="原因" min-width="160" />
      <el-table-column label="修正信息" min-width="180"><template #default="{ row }">{{ formatCorrectionInfo(row) }}</template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" @current-change="load" />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { httpClient, resolveErrorMessage } from '@/services/http'
import { ElMessage } from 'element-plus'

interface DutyChange { id: number; duty_date: string; shift_def_name: string; start_at: string; end_at: string; original_person_name: string; before_person_name: string; after_person_name: string; source_biz_no?: string; reason?: string; created_at: string; created_by?: number; created_by_name?: string; change_type: string }
const route = useRoute()
const items = ref<DutyChange[]>([])
const range = ref<string[]>([])
const sourceType = ref('')
const personId = ref<number | undefined>()
const shiftDefId = ref<number | undefined>()
const page = ref(1)
const total = ref(0)
const loading = ref(false)
async function load(): Promise<void> {
  loading.value = true
  try {
    const query = new URLSearchParams({ page: String(page.value), page_size: '20' })
    if (range.value.length === 2) { query.set('from', range.value[0]); query.set('to', range.value[1]) }
    if (personId.value) query.set('person_id', String(personId.value))
    if (shiftDefId.value) query.set('shift_def_id', String(shiftDefId.value))
    if (sourceType.value) query.set('change_type', sourceType.value)
    const response = await httpClient.get<{ items: DutyChange[]; total: number }>(`/schedules/change-ledger?${query}`)
    items.value = response.data.items; total.value = response.data.total
  } catch (error) { ElMessage.error(resolveErrorMessage(error, '加载值班变更台账失败')) } finally { loading.value = false }
}
function sourceLabel(source: string): string { return ({ swap: '换班', swap_cancel: '换班作废', manual: '人工调整', historical_correction: '历史人工修正', leave_cover: '请假顶班' }[source] || source) }
function formatShiftTime(row: DutyChange): string { return `${row.start_at.slice(11, 16)}-${row.end_at.slice(11, 16)}` }
function formatCorrectionInfo(row: DutyChange): string { return `${row.created_at.slice(0, 16).replace('T', ' ')}${row.created_by_name ? `，操作人 ${row.created_by_name}` : row.created_by ? `，操作人 #${row.created_by}` : ''}` }
onMounted(() => {
  const from = typeof route.query.from === 'string' ? route.query.from : ''
  const to = typeof route.query.to === 'string' ? route.query.to : ''
  if (from && to) range.value = [from, to]
  void load()
})
</script>

<style scoped>
.actual-duty-view__header { margin-bottom: 16px; }.actual-duty-view h1 { margin: 0; font-size: 22px; }.el-pagination { margin-top: 16px; justify-content: flex-end; }
</style>
