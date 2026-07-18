<template>
  <section class="actual-duty-view">
    <div class="actual-duty-view__header"><h1>实际值班</h1></div>
    <el-form inline aria-label="实际值班查询条件">
      <el-form-item label="日期范围"><el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" /></el-form-item>
      <el-form-item label="变更来源"><el-select v-model="sourceType" clearable placeholder="全部"><el-option label="排班发布" value="schedule" /><el-option label="换班" value="swap" /><el-option label="顶班" value="cover" /></el-select></el-form-item>
      <el-form-item><el-button type="primary" @click="load">查询</el-button></el-form-item>
    </el-form>
    <el-table :data="items" v-loading="loading" border>
      <el-table-column prop="duty_date" label="日期" width="120" />
      <el-table-column prop="shift_def_name" label="班次" width="120" />
      <el-table-column prop="original_person_name" label="原排班人员" />
      <el-table-column prop="actual_person_name" label="实际值班人员" />
      <el-table-column label="变更来源"><template #default="{ row }">{{ sourceLabel(row.source_type) }}</template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" @current-change="load" />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { httpClient, resolveErrorMessage } from '@/services/http'
import { ElMessage } from 'element-plus'

interface ActualDuty { id: number; duty_date: string; shift_def_name: string; original_person_name: string; actual_person_name: string; source_type: string }
const items = ref<ActualDuty[]>([])
const range = ref<string[]>([])
const sourceType = ref('')
const page = ref(1)
const total = ref(0)
const loading = ref(false)
async function load(): Promise<void> {
  loading.value = true
  try {
    const query = new URLSearchParams({ page: String(page.value), page_size: '20' })
    if (range.value.length === 2) { query.set('from', range.value[0]); query.set('to', range.value[1]) }
    if (sourceType.value) query.set('source_type', sourceType.value)
    const response = await httpClient.get<{ items: ActualDuty[]; total: number }>(`/schedules/actual-duties?${query}`)
    items.value = response.data.items; total.value = response.data.total
  } catch (error) { ElMessage.error(resolveErrorMessage(error, '加载实际值班失败')) } finally { loading.value = false }
}
function sourceLabel(source: string): string { return ({ schedule: '排班发布', swap: '换班', cover: '顶班' }[source] || source) }
onMounted(load)
</script>

<style scoped>
.actual-duty-view__header { margin-bottom: 16px; }.actual-duty-view h1 { margin: 0; font-size: 22px; }.el-pagination { margin-top: 16px; justify-content: flex-end; }
</style>
