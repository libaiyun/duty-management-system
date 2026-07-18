<template>
  <section class="approval-center">
    <h1>审批中心</h1>
    <el-form inline class="approval-center__filters">
      <el-form-item label="业务类型"><el-select v-model="bizType" clearable placeholder="全部" @change="load"><el-option label="换班" value="shift_swap" /><el-option label="请假" value="leave_request" /><el-option label="顶班" value="cover_assignment" /></el-select></el-form-item>
      <el-form-item label="申请人"><el-input v-model="applicant" clearable placeholder="姓名" @change="load" /></el-form-item>
      <el-form-item label="到达时间"><el-date-picker v-model="arrivedRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" @change="load" /></el-form-item>
      <el-form-item v-if="tab === 'done'" label="审批结果"><el-select v-model="result" clearable placeholder="全部" @change="load"><el-option label="同意" value="approved" /><el-option label="拒绝" value="rejected" /></el-select></el-form-item>
    </el-form>
    <el-tabs v-model="tab" @tab-change="load">
      <el-tab-pane label="待办审批" name="todo">
        <el-table v-loading="loading" :data="tasks" border>
          <el-table-column prop="id" label="待办编号" width="100" />
          <el-table-column label="业务类型" width="120"><template #default="{ row }">{{ typeLabel(row.biz_type) }}</template></el-table-column>
          <el-table-column label="申请人" width="120"><template #default="{ row }">{{ snapshotValue(row, 'applicant_name') }}</template></el-table-column>
          <el-table-column label="班次日期" width="120"><template #default="{ row }">{{ snapshotValue(row, 'duty_date') }}</template></el-table-column>
          <el-table-column label="摘要" min-width="160"><template #default="{ row }">{{ snapshotValue(row, 'summary') }}</template></el-table-column>
          <el-table-column prop="biz_id" label="业务单号" width="110" />
          <el-table-column prop="arrived_at" label="到达时间" min-width="180" />
          <el-table-column label="操作" width="120"><template #default="{ row }"><el-button link type="primary" @click="open(row)">处理</el-button></template></el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="已办审批" name="done">
        <el-table v-loading="loading" :data="tasks" border>
          <el-table-column prop="id" label="审批编号" width="100" />
          <el-table-column label="业务类型" width="120"><template #default="{ row }">{{ typeLabel(row.biz_type) }}</template></el-table-column>
          <el-table-column prop="biz_id" label="业务单号" width="110" />
          <el-table-column label="申请人" width="120"><template #default="{ row }">{{ snapshotValue(row, 'applicant_name') }}</template></el-table-column>
          <el-table-column label="审批结果" width="110"><template #default="{ row }">{{ row.status === 'approved' ? '同意' : '拒绝' }}</template></el-table-column>
          <el-table-column prop="opinion" label="审批意见" min-width="180" />
          <el-table-column prop="handled_at" label="处理时间" min-width="180" />
          <el-table-column label="操作" width="110"><template #default="{ row }"><el-button link type="primary" @click="open(row)">查看详情</el-button></template></el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
    <el-drawer v-model="drawer" title="审批详情" direction="rtl">
      <el-descriptions v-if="selected" :column="1" border><el-descriptions-item label="业务类型">{{ typeLabel(selected.biz_type) }}</el-descriptions-item><el-descriptions-item label="业务单号">{{ selected.biz_id }}</el-descriptions-item><el-descriptions-item label="申请人">{{ snapshotValue(selected, 'applicant_name') }}</el-descriptions-item><el-descriptions-item label="班次日期">{{ snapshotValue(selected, 'duty_date') }}</el-descriptions-item><el-descriptions-item label="业务摘要">{{ snapshotValue(selected, 'summary') }}</el-descriptions-item></el-descriptions>
      <el-form v-if="tab === 'todo'" label-position="top"><el-form-item label="审批意见"><el-input v-model="opinion" type="textarea" :rows="4" maxlength="500" show-word-limit /></el-form-item></el-form>
      <div v-if="tab === 'todo'" class="approval-center__actions"><el-button @click="act('reject')">拒绝</el-button><el-button type="primary" @click="act('approve')">同意</el-button></div>
    </el-drawer>
  </section>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { httpClient, resolveErrorMessage } from '@/services/http'
interface Task { id: number; biz_type: string; biz_id: number; status: string; arrived_at: string; handled_at?: string; opinion?: string; snapshot: Record<string, unknown> }
const tab = ref<'todo' | 'done'>('todo'); const tasks = ref<Task[]>([]); const loading = ref(false); const drawer = ref(false); const selected = ref<Task>(); const opinion = ref(''); const bizType = ref(''); const applicant = ref(''); const result = ref(''); const arrivedRange = ref<string[]>()
async function load(): Promise<void> { loading.value = true; try { const query = new URLSearchParams({ page: '1', page_size: '50' }); if (bizType.value) query.set('biz_type', bizType.value); if (applicant.value) query.set('applicant', applicant.value); if (tab.value === 'done' && result.value) query.set('result', result.value); if (arrivedRange.value) { query.set('arrived_from', arrivedRange.value[0]); query.set('arrived_to', arrivedRange.value[1]) }; tasks.value = (await httpClient.get<{ items: Task[] }>(`/approval-tasks/${tab.value}?${query}`)).data.items } catch (e) { ElMessage.error(resolveErrorMessage(e, '加载审批任务失败')) } finally { loading.value = false } }
function open(task: Task): void { selected.value = task; opinion.value = ''; drawer.value = true }
async function act(action: 'approve' | 'reject'): Promise<void> { if (!selected.value) return; if (action === 'reject' && !opinion.value.trim()) { ElMessage.warning('拒绝时请填写审批意见'); return } try { await httpClient.post(`/approval-tasks/${selected.value.id}/${action}`, { opinion: opinion.value || undefined }); ElMessage.success('审批已提交'); drawer.value = false; await load() } catch (e) { ElMessage.error(resolveErrorMessage(e, '审批提交失败')) } }
function typeLabel(type: string): string { return ({ shift_swap: '换班', leave_request: '请假', cover_assignment: '顶班' }[type] || type) }
function snapshotValue(task: Task, key: string): string { return String(task.snapshot[key] || '-') }
onMounted(load)
</script>
<style scoped>.approval-center__filters { margin-bottom: 12px; }.approval-center__actions { display: flex; justify-content: flex-end; gap: 12px; }</style>
