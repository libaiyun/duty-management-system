<template>
  <section class="holiday-view">
    <h1>节假日与标准</h1>

    <el-tabs v-model="activeTab" class="holiday-view__tabs">
      <!-- 法定节假日 -->
      <el-tab-pane label="法定节假日" name="holiday">
        <div class="holiday-view__filters">
          <el-select
            v-model="filterYear"
            placeholder="年度"
            clearable
            class="holiday-view__filter-year"
            @change="loadHolidays"
          >
            <el-option v-for="y in yearOptions" :key="y" :label="`${y} 年`" :value="y" />
          </el-select>
          <el-button @click="resetFilter">重置</el-button>
        </div>

        <div class="holiday-view__toolbar">
          <el-button v-if="canManageGlobalHolidays" type="primary" @click="openCreateDialog">新增节假日</el-button>
          <el-button v-if="canManageGlobalHolidays" @click="openImportDialog">批量导入</el-button>
        </div>

        <el-table :data="holidays" v-loading="loading" stripe>
          <el-table-column prop="holiday_date" label="日期" width="140" />
          <el-table-column prop="holiday_name" label="名称" min-width="160" />
          <el-table-column prop="year" label="年度" width="100" align="center" />
          <el-table-column label="是否法定" width="110" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_legal ? 'danger' : 'info'" size="small">
                {{ row.is_legal ? '法定' : '非法定' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.status === 'enabled' ? 'success' : 'info'" size="small">
                {{ row.status === 'enabled' ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="140" />
          <el-table-column v-if="canManageGlobalHolidays" label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openEditDialog(row)">编辑</el-button>
              <el-button
                size="small"
                :type="row.status === 'enabled' ? 'warning' : 'success'"
                @click="toggleStatus(row)"
              >
                {{ row.status === 'enabled' ? '停用' : '启用' }}
              </el-button>
              <el-button size="small" type="danger" @click="deleteHoliday(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 餐补标准 -->
      <el-tab-pane label="餐补标准" name="meal-standard">
        <div class="holiday-view__toolbar">
          <el-button v-if="!editingStandard && canManageStandard" type="primary" @click="editingStandard = true">编辑标准</el-button>
          <template v-else>
            <el-button @click="cancelStandardEdit">取消</el-button>
            <el-button type="primary" :loading="savingStandard" @click="saveStandard">保存标准</el-button>
          </template>
        </div>
        <el-alert
          title="以下标准适用于当前机房；首次访问时系统会预填充默认值。"
          type="info"
          :closable="false"
          class="holiday-view__standard-tip"
        />
        <el-descriptions :column="1" border class="holiday-view__standard">
          <el-descriptions-item label="早班餐补"><el-input-number v-if="editingStandard" v-model="standard.early_meal" :min="0" /> <template v-else>{{ standard.early_meal }}</template> 元 / 人 / 班</el-descriptions-item>
          <el-descriptions-item label="中班餐补"><el-input-number v-if="editingStandard" v-model="standard.middle_meal" :min="0" /> <template v-else>{{ standard.middle_meal }}</template> 元 / 人 / 班</el-descriptions-item>
          <el-descriptions-item label="晚班餐补"><el-input-number v-if="editingStandard" v-model="standard.night_meal" :min="0" /> <template v-else>{{ standard.night_meal }}</template> 元 / 人 / 班</el-descriptions-item>
          <el-descriptions-item label="餐补退费（晚班退给中班）">
            <el-input-number v-if="editingStandard" v-model="standard.meal_refund_night_to_middle" :min="0" /> <template v-else>{{ standard.meal_refund_night_to_middle }}</template> 元 / 班
          </el-descriptions-item>
        </el-descriptions>
      </el-tab-pane>

      <!-- 节假日加班费标准 -->
      <el-tab-pane label="节假日加班费标准" name="overtime-standard">
        <el-alert
          title="以下标准适用于当前机房。"
          type="info"
          :closable="false"
          class="holiday-view__standard-tip"
        />
        <el-descriptions :column="1" border class="holiday-view__standard">
          <el-descriptions-item label="节假日加班费">
            <el-input-number v-if="editingStandard" v-model="standard.holiday_overtime" :min="0" /> <template v-else>{{ standard.holiday_overtime }}</template> 元 / 人 / 班
          </el-descriptions-item>
          <el-descriptions-item label="加班费退费（晚班退给中班）">
            <el-input-number v-if="editingStandard" v-model="standard.holiday_overtime_refund_night_to_middle" :min="0" /> <template v-else>{{ standard.holiday_overtime_refund_night_to_middle }}</template> 元 / 班
          </el-descriptions-item>
        </el-descriptions>
      </el-tab-pane>
    </el-tabs>

    <!-- 新增/编辑 弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingHoliday ? '编辑节假日' : '新增节假日'"
      width="480px"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-position="top">
        <el-form-item label="日期" prop="holiday_date">
          <el-date-picker
            v-model="formData.holiday_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            :disabled="!!editingHoliday"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="名称" prop="holiday_name">
          <el-input v-model="formData.holiday_name" placeholder="如 元旦/春节" />
        </el-form-item>
        <el-form-item label="是否法定节假日">
          <el-switch v-model="formData.is_legal" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="formData.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入 弹窗 -->
    <el-dialog v-model="importVisible" title="批量导入节假日" width="560px" @closed="resetImport">
      <el-alert
        title="每行一条，格式：日期,名称[,是否法定]。示例：2026-01-01,元旦,1"
        type="info"
        :closable="false"
        class="holiday-view__import-tip"
      />
      <el-input
        v-model="importText"
        type="textarea"
        :rows="8"
        placeholder="2026-01-01,元旦,1&#10;2026-05-01,劳动节,1"
      />
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="doImport">导入</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

import { httpClient, resolveErrorMessage } from '@/services/http'
import { usePermissionStore } from '@/stores/permission'
import { PERMISSION_CODES } from '@/types/permission'

interface HolidayItem {
  id: number
  holiday_date: string
  holiday_name: string
  year: number
  is_legal: boolean
  status: string
  remark: string | null
}

interface SubsidyStandard {
  early_meal: number
  middle_meal: number
  night_meal: number
  meal_refund_night_to_middle: number
  holiday_overtime: number
  holiday_overtime_refund_night_to_middle: number
}

interface ImportResult {
  created: number
  skipped: number
  skipped_dates: string[]
}

const activeTab = ref('holiday')
const permissionStore = usePermissionStore()
const canManageGlobalHolidays = computed(() => permissionStore.hasPermission(PERMISSION_CODES.HOLIDAY_GLOBAL_MANAGE))
const canManageStandard = computed(() => permissionStore.hasPermission(PERMISSION_CODES.HOLIDAY_STANDARD_MANAGE))

const holidays = ref<HolidayItem[]>([])
const loading = ref(false)
const filterYear = ref<number | null>(null)

const standard = reactive<SubsidyStandard>({
  early_meal: 0,
  middle_meal: 0,
  night_meal: 0,
  meal_refund_night_to_middle: 0,
  holiday_overtime: 0,
  holiday_overtime_refund_night_to_middle: 0,
})
const standardSnapshot = reactive<SubsidyStandard>({ ...standard })
const editingStandard = ref(false)
const savingStandard = ref(false)

const yearOptions = computed(() => {
  const current = new Date().getFullYear()
  const years: number[] = []
  for (let y = current - 2; y <= current + 3; y++) years.push(y)
  return years
})

onMounted(async () => {
  await Promise.all([loadHolidays(), loadStandard()])
})

async function loadHolidays() {
  loading.value = true
  try {
    const path = filterYear.value ? `/holidays?year=${filterYear.value}` : '/holidays'
    const resp = await httpClient.get<HolidayItem[]>(path)
    holidays.value = resp.data
  } catch {
    ElMessage.error('加载节假日列表失败')
  } finally {
    loading.value = false
  }
}

async function loadStandard() {
  try {
    const resp = await httpClient.get<SubsidyStandard>('/holidays/standard')
    Object.assign(standard, resp.data)
    Object.assign(standardSnapshot, resp.data)
  } catch {
    // 标准数据加载失败不阻塞页面
  }
}

function cancelStandardEdit() {
  Object.assign(standard, standardSnapshot)
  editingStandard.value = false
}

async function saveStandard() {
  savingStandard.value = true
  try {
    const response = await httpClient.put<SubsidyStandard>('/holidays/standard', standard)
    Object.assign(standard, response.data)
    Object.assign(standardSnapshot, response.data)
    editingStandard.value = false
    ElMessage.success('费用标准已保存')
  } catch (error) {
    ElMessage.error(resolveErrorMessage(error, '保存费用标准失败'))
  } finally {
    savingStandard.value = false
  }
}

function resetFilter() {
  filterYear.value = null
  loadHolidays()
}

// ── 新增/编辑 ──
const dialogVisible = ref(false)
const saving = ref(false)
const editingHoliday = ref<HolidayItem | null>(null)
const formRef = ref<FormInstance>()
const formData = reactive({
  holiday_date: '',
  holiday_name: '',
  is_legal: true,
  remark: '',
})
const formRules: FormRules = {
  holiday_date: [{ required: true, message: '请选择日期' }],
  holiday_name: [{ required: true, message: '请输入名称' }],
}

function openCreateDialog() {
  editingHoliday.value = null
  formData.holiday_date = ''
  formData.holiday_name = ''
  formData.is_legal = true
  formData.remark = ''
  dialogVisible.value = true
}

function openEditDialog(holiday: HolidayItem) {
  editingHoliday.value = holiday
  formData.holiday_date = holiday.holiday_date
  formData.holiday_name = holiday.holiday_name
  formData.is_legal = holiday.is_legal
  formData.remark = holiday.remark || ''
  dialogVisible.value = true
}

function resetForm() {
  editingHoliday.value = null
  formData.holiday_date = ''
  formData.holiday_name = ''
  formData.is_legal = true
  formData.remark = ''
  formRef.value?.resetFields()
}

async function save() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (editingHoliday.value) {
      await httpClient.put(`/holidays/${editingHoliday.value.id}`, {
        holiday_name: formData.holiday_name,
        is_legal: formData.is_legal,
        remark: formData.remark || null,
      })
      ElMessage.success('编辑成功')
    } else {
      await httpClient.post('/holidays', {
        holiday_date: formData.holiday_date,
        holiday_name: formData.holiday_name,
        is_legal: formData.is_legal,
        remark: formData.remark || null,
      })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await loadHolidays()
  } catch (err) {
    ElMessage.error(resolveErrorMessage(err, '操作失败'))
  } finally {
    saving.value = false
  }
}

async function toggleStatus(holiday: HolidayItem) {
  const action = holiday.status === 'enabled' ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(`确认${action}节假日「${holiday.holiday_name}」吗？`, `${action}确认`)
  } catch {
    return
  }
  try {
    await httpClient.put(`/holidays/${holiday.id}`, {
      status: holiday.status === 'enabled' ? 'disabled' : 'enabled',
    })
    ElMessage.success(`${action}成功`)
    await loadHolidays()
  } catch (err) {
    ElMessage.error(resolveErrorMessage(err, '操作失败'))
  }
}

async function deleteHoliday(holiday: HolidayItem) {
  try {
    await ElMessageBox.confirm(`确认删除节假日「${holiday.holiday_name}」吗？`, '删除确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await httpClient.delete(`/holidays/${holiday.id}`)
    ElMessage.success('删除成功')
    await loadHolidays()
  } catch (err) {
    ElMessage.error(resolveErrorMessage(err, '删除失败'))
  }
}

// ── 批量导入 ──
const importVisible = ref(false)
const importing = ref(false)
const importText = ref('')

function openImportDialog() {
  importText.value = ''
  importVisible.value = true
}

function resetImport() {
  importText.value = ''
}

function parseImportText(text: string): { holiday_date: string; holiday_name: string; is_legal: boolean }[] {
  const items: { holiday_date: string; holiday_name: string; is_legal: boolean }[] = []
  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim()
    if (!line) continue
    const parts = line.split(',').map((p) => p.trim())
    const [date, name, legal] = parts
    if (!date || !name) continue
    items.push({
      holiday_date: date,
      holiday_name: name,
      is_legal: legal === undefined || legal === '' ? true : legal === '1',
    })
  }
  return items
}

async function doImport() {
  const items = parseImportText(importText.value)
  if (items.length === 0) {
    ElMessage.warning('没有可导入的有效数据')
    return
  }
  importing.value = true
  try {
    const resp = await httpClient.post<ImportResult>('/holidays/import', { items })
    const result = resp.data
    ElMessage.success(`导入完成：新增 ${result.created} 条，跳过 ${result.skipped} 条`)
    importVisible.value = false
    await loadHolidays()
  } catch (err) {
    ElMessage.error(resolveErrorMessage(err, '导入失败'))
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.holiday-view h1 {
  margin: 0 0 16px;
  font-size: 24px;
  font-weight: 600;
}

.holiday-view__filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}

.holiday-view__filter-year {
  width: 160px;
}

.holiday-view__toolbar {
  margin-bottom: 16px;
}

.holiday-view__standard-tip,
.holiday-view__import-tip {
  margin-bottom: 16px;
}

.holiday-view__standard {
  max-width: 480px;
}
</style>
