<template>
  <section>
    <h1>导出历史</h1>
    <el-table v-loading="loading" :data="tasks" border>
      <el-table-column prop="year_month" label="月份" width="120" />
      <el-table-column label="类型" width="120"><template #default>值班表</template></el-table-column>
      <el-table-column label="状态" width="120"><template #default="{ row }"><el-tag :type="tagType(row.status)">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
      <el-table-column prop="created_at" label="创建时间" min-width="180" />
      <el-table-column label="操作" width="120"><template #default="{ row }"><el-button link type="primary" :disabled="row.status !== 'completed'" @click="download(row)">下载</el-button></template></el-table-column>
    </el-table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { httpClient, resolveErrorMessage } from '@/services/http'

interface ExportTask { id: number; year_month: string; status: string; created_at: string }
const tasks = ref<ExportTask[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try { tasks.value = (await httpClient.get<{ items: ExportTask[] }>('/exports?page=1&page_size=50')).data.items }
  catch (error) { ElMessage.error(resolveErrorMessage(error, '加载导出历史失败')) }
  finally { loading.value = false }
})

async function download(task: ExportTask): Promise<void> {
  try {
    const url = URL.createObjectURL(await httpClient.getBlob(`/exports/${task.id}/download`))
    const link = document.createElement('a')
    link.href = url; link.download = `值班表_${task.year_month}.xlsx`; link.click()
    URL.revokeObjectURL(url)
  } catch (error) { ElMessage.error(resolveErrorMessage(error, '下载导出文件失败')) }
}
function statusLabel(status: string): string { return { pending: '待处理', running: '生成中', completed: '已完成', failed: '失败' }[status] || status }
function tagType(status: string): 'success' | 'danger' | 'warning' | 'info' { return ({ completed: 'success', failed: 'danger', running: 'warning' }[status] || 'info') as 'success' | 'danger' | 'warning' | 'info' }
</script>
