<template>
  <section class="shift-def-view">
    <h1>班次规则</h1>
    <div class="shift-def-view__toolbar">
      <el-button v-if="canManage" type="primary" @click="openDialog()">新增班次</el-button>
    </div>
    <el-table :data="shiftDefs" v-loading="loading" stripe>
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
      <el-table-column v-if="canManage" class-name="shift-def-view__actions" label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openDialog(row)">编辑</el-button>
          <el-button size="small" :type="row.status === 'enabled' ? 'warning' : 'success'" @click="toggleStatus(row)">
            {{ row.status === 'enabled' ? '停用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑班次' : '新增班次'" width="480px" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top">
        <el-form-item label="班次编码" prop="code">
          <el-input v-model="form.code" :disabled="!!editing" placeholder="留空自动生成" />
        </el-form-item>
        <el-form-item label="班次名称" prop="name"><el-input v-model="form.name" placeholder="如 早班/中班/晚班" /></el-form-item>
        <el-form-item label="开始时间" prop="start_time"><el-input v-model="form.start_time" placeholder="HH:MM，如 00:00" /></el-form-item>
        <el-form-item label="结束时间" prop="end_time"><el-input v-model="form.end_time" placeholder="HH:MM，如 08:00" /></el-form-item>
        <el-form-item label="展示顺序"><el-input-number v-model="form.display_order" :min="0" style="width: 100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import { httpClient, resolveErrorMessage } from '@/services/http'
import { useRoomContextStore } from '@/stores/room-context'
import { usePermissionStore } from '@/stores/permission'
import { PERMISSION_CODES } from '@/types/permission'

interface ShiftDefItem {
  id: number
  code: string
  name: string
  start_time: string
  end_time: string
  display_order: number
  status: string
}

const shiftDefs = ref<ShiftDefItem[]>([])
const roomContextStore = useRoomContextStore()
const permissionStore = usePermissionStore()
const canManage = computed(() => permissionStore.hasPermission(PERMISSION_CODES.SHIFT_DEF_MANAGE))
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editing = ref<ShiftDefItem | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({ code: '', name: '', start_time: '', end_time: '', display_order: 0 })
const formRules: FormRules = {
  name: [{ required: true, message: '请输入班次名称' }],
  start_time: [{ required: true, message: '请输入开始时间' }, { pattern: /^\d{2}:\d{2}$/, message: '格式应为 HH:MM' }],
  end_time: [{ required: true, message: '请输入结束时间' }, { pattern: /^\d{2}:\d{2}$/, message: '格式应为 HH:MM' }],
}

onMounted(loadShiftDefs)
watch(() => roomContextStore.currentRoomId, loadShiftDefs)

async function loadShiftDefs() {
  loading.value = true
  try {
    const resp = await httpClient.get<ShiftDefItem[]>('/shifts')
    shiftDefs.value = resp.data
  } catch {
    ElMessage.error('加载班次列表失败')
  } finally {
    loading.value = false
  }
}

function openDialog(shift?: ShiftDefItem) {
  editing.value = shift ?? null
  form.code = shift?.code ?? ''
  form.name = shift?.name ?? ''
  form.start_time = shift?.start_time ?? ''
  form.end_time = shift?.end_time ?? ''
  form.display_order = shift?.display_order ?? 0
  dialogVisible.value = true
}

function resetForm() {
  editing.value = null
  form.code = ''
  form.name = ''
  form.start_time = ''
  form.end_time = ''
  form.display_order = 0
  formRef.value?.resetFields()
}

async function save() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (editing.value) {
      await httpClient.put(`/shifts/${editing.value.id}`, { name: form.name, start_time: form.start_time, end_time: form.end_time, display_order: form.display_order })
      ElMessage.success('编辑成功')
    } else {
      await httpClient.post('/shifts', {
        ...(form.code ? { code: form.code } : {}),
        name: form.name,
        start_time: form.start_time,
        end_time: form.end_time,
        display_order: form.display_order,
      })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await loadShiftDefs()
  } catch (err) {
    ElMessage.error(resolveErrorMessage(err, '操作失败'))
  } finally {
    saving.value = false
  }
}

async function toggleStatus(shift: ShiftDefItem) {
  const action = shift.status === 'enabled' ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(`确认${action}班次「${shift.name}」吗？`, `${action}确认`)
    await httpClient.put(`/shifts/${shift.id}`, { status: shift.status === 'enabled' ? 'disabled' : 'enabled' })
    ElMessage.success(`${action}成功`)
    await loadShiftDefs()
  } catch {
    // The confirmation was cancelled.
  }
}
</script>

<style scoped>
.shift-def-view h1 { margin: 0 0 16px; font-size: 24px; font-weight: 600; }
.shift-def-view__toolbar { margin-bottom: 16px; }
</style>
