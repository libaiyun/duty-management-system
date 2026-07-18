<template>
  <section class="schedule-table-view">
    <div class="schedule-table-view__header">
      <div class="schedule-table-view__title">
        <h1>排班表</h1>
        <p v-if="roomContextStore.currentRoomName" class="schedule-table-view__room">
          {{ roomContextStore.currentRoomName }}
        </p>
      </div>
      <div class="schedule-table-view__actions">
        <el-tag v-if="schedule" :type="statusTagType(schedule.status)">
          {{ statusLabel(schedule.status) }}
        </el-tag>
        <el-button v-if="canManage && schedule?.status === 'draft'" type="primary" @click="publishSchedule">发布排班</el-button>
        <el-button v-if="canManage" @click="openExportHistory">导出 Excel</el-button>
      </div>
    </div>

    <el-alert
      v-if="emptyMessage"
      :title="emptyMessage"
      type="info"
      :closable="false"
      show-icon
      class="schedule-table-view__alert"
    />

    <div class="schedule-table-view__toolbar">
      <el-button :icon="ArrowLeft" circle size="small" aria-label="上月" @click="changeMonth(-1)" />
      <span class="schedule-table-view__month">{{ displayMonth }}</span>
      <el-button :icon="ArrowRight" circle size="small" aria-label="下月" @click="changeMonth(1)" />
      <el-radio-group v-model="viewMode" size="small" class="schedule-table-view__view-switch">
        <el-radio-button value="calendar">日历</el-radio-button>
        <el-radio-button value="list">列表</el-radio-button>
      </el-radio-group>
    </div>

    <div v-if="viewMode === 'calendar'" v-loading="loading" class="schedule-table-view__calendar">
      <el-calendar v-model="calendarDate">
        <template #date-cell="{ data }">
          <article
            class="schedule-table-view__day"
            :class="dayClasses(data.day, data.type)"
            @click="openActionMenu(data.day)"
          >
            <div class="schedule-table-view__date">
              <span>{{ dayNumber(data.day) }}</span>
              <small v-if="dayFor(data.day)?.holiday_name">{{ dayFor(data.day)?.holiday_name }}</small>
            </div>
            <template v-if="dayFor(data.day) && data.type === 'current-month'">
              <div
                v-for="shift in dayFor(data.day)?.shifts || []"
                :key="shift.id"
                class="schedule-table-view__shift"
              >
                <strong>{{ shift.shift_def_name }}</strong>
                <span :title="personText(shift)">{{ personText(shift) }}</span>
                <el-button v-if="canManage && !isLocked" link type="primary" size="small" @click.stop="openEditor(shift)">编辑</el-button>
              </div>
              <div v-if="actionDate === data.day && isMyDay(data.day)" class="schedule-table-view__action-menu" @click.stop>
                <el-button v-for="shift in myShifts(data.day)" :key="shift.id" link type="primary" @click="openSwap(shift)">
                  换班（{{ shift.shift_def_name }}）
                </el-button>
                <el-button link :disabled="Boolean(dayFor(data.day)?.is_legal_holiday) || isLocked" @click="showPlaceholder('请假')">
                  发起请假
                </el-button>
              </div>
            </template>
          </article>
        </template>
      </el-calendar>
    </div>

    <template v-else>
      <section class="schedule-table-view__filter-panel" aria-label="排班查询条件">
        <div class="schedule-table-view__filter-heading">
          <span>查询条件</span>
          <el-button class="schedule-table-view__reset" link type="primary" @click="resetListFilters">重置</el-button>
        </div>
        <div class="schedule-table-view__filters">
          <div class="schedule-table-view__filter-field schedule-table-view__filter-field--date">
            <label>日期范围</label>
            <el-date-picker v-model="listDateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" />
          </div>
          <div class="schedule-table-view__filter-field">
            <label for="schedule-person">人员</label>
            <el-input id="schedule-person" v-model="personKeyword" placeholder="输入人员姓名" clearable />
          </div>
        </div>
      </section>
      <section class="schedule-table-view__list-panel">
        <div class="schedule-table-view__list-heading">
          <span>排班明细</span>
          <span class="schedule-table-view__result-count">共 {{ filteredDays.length }} 条</span>
        </div>
        <div class="schedule-table-view__table-wrap">
          <el-table :data="filteredDays" v-loading="loading" border class="schedule-table-view__list">
        <el-table-column label="日期" width="120">
          <template #default="{ row }">
            <span class="schedule-table-view__date-value">{{ row.duty_date }}</span>
          </template>
        </el-table-column>
        <el-table-column label="星期" width="72">
          <template #default="{ row }">{{ weekdayLabel(row.weekday) }}</template>
        </el-table-column>
        <el-table-column label="节假日" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.is_legal_holiday" size="small" type="danger">{{ row.holiday_name || '节假日' }}</el-tag>
            <span v-else class="schedule-table-view__empty-value">-</span>
          </template>
        </el-table-column>
          <el-table-column v-for="shift in shiftColumns" :key="shift.id" :label="shift.name" min-width="160">
          <template #default="{ row }"><span>{{ personText(shiftFor(row, shift.id)) }}</span><el-button v-if="canManage && !isLocked" link type="primary" @click="openEditor(shiftFor(row, shift.id))">编辑</el-button></template>
        </el-table-column>
          </el-table>
        </div>
      </section>
    </template>
  </section>
  <el-dialog v-model="editorVisible" title="调整值班人员" width="420px">
    <el-select v-model="editorPersonIds" multiple filterable placeholder="选择值班人员" style="width: 100%">
      <el-option v-for="person in eligiblePersons" :key="person.id" :label="person.name" :value="person.id" />
    </el-select>
    <template #footer><el-button @click="editorVisible = false">取消</el-button><el-button type="primary" @click="saveEditor">保存</el-button></template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { httpClient, resolveErrorMessage } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import { useRoomContextStore } from '@/stores/room-context'
import { usePermissionStore } from '@/stores/permission'

interface ScheduleItem {
  id: number
  status: string
  coverage_through: string | null
}

interface SchedulePerson {
  person_id: number
  person_name: string
}

interface ScheduleShift {
  id: number
  shift_def_id: number
  shift_def_name: string
  persons: SchedulePerson[]
}
interface PersonOption { id: number; name: string }

interface ScheduleDay {
  duty_date: string
  weekday: number
  is_legal_holiday: boolean
  holiday_name: string | null
  shifts: ScheduleShift[]
}

const authStore = useAuthStore()
const roomContextStore = useRoomContextStore()
const permissionStore = usePermissionStore()
const router = useRouter()
const loading = ref(false)
const schedule = ref<ScheduleItem | null>(null)
const days = ref<ScheduleDay[]>([])
const calendarDate = ref(new Date())
const viewMode = ref<'calendar' | 'list'>('calendar')
const actionDate = ref('')
const listDateRange = ref<string[]>([])
const personKeyword = ref('')
const loadError = ref('')
const editorVisible = ref(false)
const editingShift = ref<ScheduleShift | undefined>()
const editorPersonIds = ref<number[]>([])
const eligiblePersons = ref<PersonOption[]>([])
const canManage = computed(() => permissionStore.hasPermission('schedule:monthly:generate'))

const monthKey = computed(() => {
  const year = calendarDate.value.getFullYear()
  const month = String(calendarDate.value.getMonth() + 1).padStart(2, '0')
  return `${year}-${month}`
})
const displayMonth = computed(() => `${monthKey.value.slice(0, 4)}年${Number(monthKey.value.slice(5))}月`)
const isLocked = computed(() => schedule.value?.status === 'locked')
const daysByDate = computed(() => new Map(days.value.map((day) => [day.duty_date, day])))
const shiftColumns = computed(() => {
  const columns = new Map<number, { id: number; name: string }>()
  for (const day of days.value) {
    for (const shift of day.shifts) columns.set(shift.shift_def_id, { id: shift.shift_def_id, name: shift.shift_def_name })
  }
  return [...columns.values()]
})
const emptyMessage = computed(() => {
  if (loadError.value) return loadError.value
  if (!roomContextStore.currentRoomId) return '请在顶部选择机房后再查看排班。'
  if (!loading.value && !schedule.value) return '当前机房暂无排班数据，请先在排班规则页配置并发布规则。'
  return ''
})
const filteredDays = computed(() => days.value.filter((day) => {
  if (listDateRange.value.length === 2 && (day.duty_date < listDateRange.value[0] || day.duty_date > listDateRange.value[1])) return false
  return !personKeyword.value || day.shifts.some((shift) => personText(shift).includes(personKeyword.value))
}))

onMounted(loadSchedule)
watch([monthKey, () => roomContextStore.currentRoomId], loadSchedule)

async function loadSchedule(): Promise<void> {
  actionDate.value = ''
  days.value = []
  schedule.value = null
  loadError.value = ''
  const roomId = roomContextStore.currentRoomId
  if (!roomId) return

  loading.value = true
  try {
    const listResponse = await httpClient.get<{ items: ScheduleItem[] }>(`/schedules?org_unit_id=${roomId}`)
    schedule.value = listResponse.data.items[0] || null
    if (!schedule.value) return
    const [year, month] = monthKey.value.split('-')
    const monthEnd = new Date(Number(year), Number(month), 0)
    const through = `${monthEnd.getFullYear()}-${String(monthEnd.getMonth() + 1).padStart(2, '0')}-${String(monthEnd.getDate()).padStart(2, '0')}`
    if (canManage.value && (!schedule.value.coverage_through || schedule.value.coverage_through < through)) {
      await httpClient.post(`/schedules/${schedule.value.id}/generate?through=${through}`)
    }
    const daysResponse = await httpClient.get<ScheduleDay[]>(`/schedules/${schedule.value.id}/days?year=${year}&month=${Number(month)}`)
    days.value = daysResponse.data
  } catch (error) {
    loadError.value = resolveErrorMessage(error, '加载排班失败')
  } finally {
    loading.value = false
  }
}

function changeMonth(offset: number): void {
  calendarDate.value = new Date(calendarDate.value.getFullYear(), calendarDate.value.getMonth() + offset, 1)
}

function resetListFilters(): void {
  listDateRange.value = []
  personKeyword.value = ''
}

function dayFor(day: string): ScheduleDay | undefined {
  return daysByDate.value.get(day)
}

function shiftFor(day: ScheduleDay, shiftId: number): ScheduleShift | undefined {
  return day.shifts.find((shift) => shift.shift_def_id === shiftId)
}

function personText(shift?: ScheduleShift): string {
  return shift?.persons.map((person) => person.person_name).join('、') || '-'
}

function isMyDay(day: string): boolean {
  if (!authStore.personId) return false
  return dayFor(day)?.shifts.some((shift) => shift.persons.some((person) => person.person_id === authStore.personId)) || false
}

function myShifts(day: string): ScheduleShift[] {
  if (!authStore.personId) return []
  return dayFor(day)?.shifts.filter((shift) => shift.persons.some((person) => person.person_id === authStore.personId)) || []
}

function dayClasses(day: string, type: string): Record<string, boolean> {
  const dutyDay = dayFor(day)
  return {
    'schedule-table-view__day--other-month': type !== 'current-month',
    'schedule-table-view__day--mine': isMyDay(day),
    'schedule-table-view__day--holiday': Boolean(dutyDay?.is_legal_holiday),
    'schedule-table-view__day--locked': isLocked.value,
  }
}

function dayNumber(day: string): string {
  return String(Number(day.slice(-2)))
}

function weekdayLabel(weekday: number): string {
  return ['一', '二', '三', '四', '五', '六', '日'][weekday] || ''
}

function openActionMenu(day: string): void {
  if (isMyDay(day) && !isLocked.value) actionDate.value = actionDate.value === day ? '' : day
}

async function openEditor(shift?: ScheduleShift): Promise<void> {
  if (!shift || !schedule.value) return
  editingShift.value = shift; editorPersonIds.value = shift.persons.map((person) => person.person_id)
  if (!eligiblePersons.value.length) {
    const response = await httpClient.get<PersonOption[]>(`/schedules/${schedule.value.id}/eligible-persons`)
    eligiblePersons.value = response.data
  }
  editorVisible.value = true
}
async function saveEditor(): Promise<void> {
  if (!schedule.value || !editingShift.value) return
  try {
    await httpClient.put(`/schedules/${schedule.value.id}/shifts/${editingShift.value.id}/persons`, { person_ids: editorPersonIds.value })
    editorVisible.value = false; ElMessage.success('排班调整已保存，请发布后生效'); await loadSchedule()
  } catch (error) { ElMessage.error(resolveErrorMessage(error, '保存排班调整失败')) }
}
async function publishSchedule(): Promise<void> {
  if (!schedule.value) return
  try {
    await httpClient.post(`/schedules/${schedule.value.id}/publish`)
    ElMessage.success('排班已发布')
    await loadSchedule()
  } catch (error) {
    ElMessage.error(resolveErrorMessage(error, '发布排班失败'))
  }
}
function openSwap(shift?: ScheduleShift): void {
  if (!shift) return
  void router.push({ path: '/swap-request', query: { source_shift_id: String(shift.id) } })
}
function showPlaceholder(action: string): void {
  ElMessage.info(`${action}功能将在后续任务中开放`)
}

async function openExportHistory(): Promise<void> {
  if (!schedule.value) {
    ElMessage.warning('当前机房暂无可导出的排班')
    return
  }
  try {
    const [year, month] = monthKey.value.split('-')
    await httpClient.post('/exports/schedule', {
      schedule_id: schedule.value.id,
      year: Number(year),
      month: Number(month),
    })
    ElMessage.success('值班表已生成')
    await router.push('/export-history')
  } catch (error) {
    ElMessage.error(resolveErrorMessage(error, '导出值班表失败'))
  }
}

function statusLabel(status: string): string {
  return { draft: '草稿', published: '已发布', locked: '已锁定' }[status] || status
}

function statusTagType(status: string): 'info' | 'success' | 'warning' {
  if (status === 'published') return 'success'
  if (status === 'locked') return 'warning'
  return 'info'
}
</script>

<style scoped>
.schedule-table-view__header,
.schedule-table-view__toolbar,
.schedule-table-view__actions,
.schedule-table-view__filters,
.schedule-table-view__filter-heading,
.schedule-table-view__list-heading {
  display: flex;
  align-items: center;
}

.schedule-table-view__header {
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 8px;
}

.schedule-table-view__title { display: flex; align-items: baseline; gap: 8px; }
.schedule-table-view h1 { margin: 0; font-size: 22px; }
.schedule-table-view__room { margin: 0; color: var(--el-text-color-secondary); font-size: 14px; }
.schedule-table-view__actions,
.schedule-table-view__toolbar,
.schedule-table-view__filters { gap: 12px; }
.schedule-table-view__toolbar { margin-bottom: 8px; }
.schedule-table-view__month { min-width: 110px; text-align: center; font-weight: 600; }
.schedule-table-view__view-switch { margin-left: auto; }
.schedule-table-view__alert { margin-bottom: 16px; }
.schedule-table-view__calendar { background: #fff; padding: 4px 8px; }
.schedule-table-view__calendar :deep(.el-calendar__header) { display: none; }
.schedule-table-view__calendar :deep(.el-calendar__body) { padding: 4px 0 0; }
.schedule-table-view__calendar :deep(.el-calendar-table thead th) { padding: 4px 0; }
.schedule-table-view__calendar :deep(.el-calendar-day) { height: 86px; padding: 2px; }
.schedule-table-view__day { position: relative; min-height: 100%; padding: 3px 4px; border-radius: 4px; }
.schedule-table-view__day--mine { background: #edf8ee; }
.schedule-table-view__day--holiday { background: #fff0f0; }
.schedule-table-view__day--mine.schedule-table-view__day--holiday { background: linear-gradient(135deg, #edf8ee 50%, #fff0f0 50%); }
.schedule-table-view__day--other-month { opacity: .45; }
.schedule-table-view__day--locked { opacity: .65; }
.schedule-table-view__date { display: flex; justify-content: space-between; margin-bottom: 2px; font-size: 13px; font-weight: 600; line-height: 16px; }
.schedule-table-view__date small { color: var(--el-color-danger); font-size: 10px; }
.schedule-table-view__shift { display: flex; gap: 3px; font-size: 11px; line-height: 16px; overflow: hidden; white-space: nowrap; }
.schedule-table-view__shift strong { color: var(--el-color-primary); flex: 0 0 auto; }
.schedule-table-view__shift span { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.schedule-table-view__action-menu { position: absolute; z-index: 2; right: 4px; bottom: 4px; display: flex; gap: 8px; padding: 2px 6px; border-radius: 4px; background: #fff; box-shadow: var(--el-box-shadow-light); }
.schedule-table-view__filter-panel,
.schedule-table-view__list-panel {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-bg-color);
}
.schedule-table-view__filter-panel { margin-bottom: 16px; padding: 14px 16px 16px; }
.schedule-table-view__filter-heading,
.schedule-table-view__list-heading { justify-content: space-between; font-weight: 600; }
.schedule-table-view__filter-heading { margin-bottom: 14px; }
.schedule-table-view__filters { gap: 16px 24px; flex-wrap: wrap; }
.schedule-table-view__filter-field { display: grid; gap: 6px; min-width: 160px; }
.schedule-table-view__filter-field label { color: var(--el-text-color-secondary); font-size: 13px; }
.schedule-table-view__filter-field--date { min-width: 300px; }
.schedule-table-view__filter-field .el-select,
.schedule-table-view__filter-field .el-input { width: 180px; }
.schedule-table-view__filter-field--date .el-date-editor { width: 300px; }
.schedule-table-view__list-panel { overflow: hidden; }
.schedule-table-view__list-heading { min-height: 52px; padding: 0 16px; border-bottom: 1px solid var(--el-border-color-lighter); }
.schedule-table-view__result-count { color: var(--el-text-color-secondary); font-size: 13px; font-weight: 400; }
.schedule-table-view__table-wrap { overflow-x: auto; }
.schedule-table-view__date-value { font-variant-numeric: tabular-nums; }
.schedule-table-view__empty-value { color: var(--el-text-color-placeholder); }
.schedule-table-view__list { min-width: 720px; }

@media (max-width: 900px) {
  .schedule-table-view__calendar { overflow-x: auto; min-width: 780px; }
}

@media (max-width: 640px) {
  .schedule-table-view__header { align-items: flex-start; }
  .schedule-table-view__actions { flex-shrink: 0; }
  .schedule-table-view__filter-panel { padding: 12px; }
  .schedule-table-view__filter-field,
  .schedule-table-view__filter-field--date,
  .schedule-table-view__filter-field .el-select,
  .schedule-table-view__filter-field .el-input,
  .schedule-table-view__filter-field--date .el-date-editor { width: 100%; min-width: 0; }
  .schedule-table-view__filters { display: grid; grid-template-columns: 1fr; }
}
</style>
