<template>
  <section class="schedule-calendar-view">
    <div class="schedule-calendar-view__header">
      <h1>排班日历</h1>
      <div class="schedule-calendar-view__status-bar">
        <el-alert
          v-if="!schedules || schedules.length === 0"
          :title="emptyMessage"
          type="info"
          :closable="false"
          show-icon
        />
      </div>
    </div>

    <div class="schedule-calendar-view__filters">
      <el-select
        v-model="filters.org_unit_id"
        placeholder="机房"
        size="default"
        clearable
        class="schedule-calendar-view__filter-room"
        @change="loadSchedules"
      >
        <el-option
          v-for="unit in roomOptions"
          :key="unit.id"
          :label="orgUnitLabel(unit)"
          :value="unit.id"
        />
      </el-select>
      <el-date-picker
        v-model="filters.month"
        type="month"
        placeholder="选择月份"
        size="default"
        format="YYYY年M月"
        value-format="YYYY-MM"
        class="schedule-calendar-view__filter-month"
      />
      <el-select
        v-model="filters.status"
        placeholder="状态"
        size="default"
        clearable
        class="schedule-calendar-view__filter-status"
        @change="loadSchedules"
      >
        <el-option label="草稿" value="draft" />
        <el-option label="已发布" value="published" />
        <el-option label="已锁定" value="locked" />
      </el-select>
      <el-button @click="resetFilters">重置</el-button>
    </div>

    <el-table
      :data="schedules"
      v-loading="loading"
      stripe
      max-height="calc(100vh - 320px)"
    >
      <el-table-column label="月份" width="120" align="center">
        <template #default>
          {{ displayMonth }}
        </template>
      </el-table-column>
      <el-table-column label="机房" min-width="180">
        <template #default="{ row }">
          {{ orgUnitDisplayName(row.org_unit_id) }}
        </template>
      </el-table-column>
      <el-table-column label="排班规则" min-width="140">
        <template #default="{ row }">
          {{ row.rule_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="班次数" width="80" align="center">
        <template #default="{ row }">
          {{ row.shift_count }}
        </template>
      </el-table-column>
      <el-table-column label="人员数" width="80" align="center">
        <template #default="{ row }">
          {{ row.person_count }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag
            :type="statusTagType(row.status)"
            size="small"
          >
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="170" align="center">
        <template #default="{ row }">
          {{ formatTime(row.generated_at) || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="viewDetail(row)">查看明细</el-button>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { httpClient, resolveErrorMessage } from '@/services/http'

interface OrgUnitItem {
  id: number
  code: string
  name: string
  type: string
  parent_id: number | null
}

interface ScheduleItem {
  id: number
  org_unit_id: number
  org_unit_code: string
  org_unit_name: string
  rule_id: number
  rule_code: string
  rule_name: string
  status: string
  generated_at: string | null
  shift_count: number
  person_count: number
  day_count: number
}

const STATUS_MAP: Record<string, string> = {
  draft: '草稿',
  published: '已发布',
  locked: '已锁定',
}

function statusLabel(s: string): string {
  return STATUS_MAP[s] || s
}

function statusTagType(s: string): 'info' | 'success' | 'warning' | 'danger' | '' {
  if (s === 'published') return 'success'
  if (s === 'locked') return 'warning'
  return 'info'
}

const router = useRouter()

const loading = ref(false)
const schedules = ref<ScheduleItem[]>([])
const orgUnits = ref<OrgUnitItem[]>([])

const filters = reactive({
  org_unit_id: null as number | null,
  month: '',
  status: '',
})

const now = new Date()
const defaultMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`

filters.month = defaultMonth

const displayMonth = computed(() => {
  if (!filters.month) return ''
  const [y, m] = filters.month.split('-')
  return `${y}年${m}月`
})

const roomOptions = computed(() => {
  return orgUnits.value.filter((u) => u.type === 'room')
})

function orgUnitLabel(unit: OrgUnitItem): string {
  if (unit.parent_id) {
    const parent = orgUnits.value.find((u) => u.id === unit.parent_id)
    return parent ? `${parent.name} / ${unit.name}` : unit.name
  }
  return unit.name
}

function orgUnitDisplayName(id: number): string {
  const unit = orgUnits.value.find((u) => u.id === id)
  return unit ? orgUnitLabel(unit) : String(id)
}

const emptyMessage = computed(() => {
  if (filters.org_unit_id) {
    return '该机房暂无排班数据，请先在排班规则页配置并发布规则'
  }
  if (filters.status === 'draft') {
    return '没有草稿状态的排班'
  }
  return '请选择机房查看排班，或前往排班规则页配置规则'
})

onMounted(async () => {
  await loadOrgUnits()
  await loadSchedules()
})

async function loadOrgUnits() {
  try {
    const resp = await httpClient.get<OrgUnitItem[]>('/org-units')
    orgUnits.value = resp.data
  } catch {
    // org units are optional for the page to function
  }
}

async function loadSchedules() {
  loading.value = true
  try {
    const queryParts: string[] = []
    if (filters.org_unit_id) queryParts.push(`org_unit_id=${filters.org_unit_id}`)
    if (filters.status) queryParts.push(`status=${filters.status}`)

    const path = queryParts.length > 0
      ? `/schedules?${queryParts.join('&')}`
      : '/schedules'

    const resp = await httpClient.get<{ items: ScheduleItem[]; total: number }>(path)
    schedules.value = resp.data.items || []
  } catch (err) {
    ElMessage.error(resolveErrorMessage(err, '加载排班失败'))
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.org_unit_id = null
  filters.status = ''
  filters.month = defaultMonth
  loadSchedules()
}

function viewDetail(schedule: ScheduleItem) {
  const parts = filters.month ? filters.month.split('-') : [String(now.getFullYear()), String(now.getMonth() + 1)]
  router.push({
    name: 'schedule-detail',
    query: {
      scheduleId: schedule.id,
      year: parts[0],
      month: parts[1],
    },
  })
}

function formatTime(iso: string | null): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}
</script>

<style scoped>
.schedule-calendar-view__header {
  display: flex;
  align-items: baseline;
  gap: 16px;
  margin-bottom: 16px;
}

.schedule-calendar-view h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.schedule-calendar-view__status-bar {
  flex: 1;
}

.schedule-calendar-view__filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.schedule-calendar-view__filter-room {
  width: 200px;
}

.schedule-calendar-view__filter-month {
  width: 180px;
}

.schedule-calendar-view__filter-status {
  width: 140px;
}
</style>
