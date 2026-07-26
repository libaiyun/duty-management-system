<template>
  <section class="home-view">
    <div class="home-view__heading">
      <div>
        <h1>工作台</h1>
        <p>查看与您相关的值班和待办。</p>
      </div>
      <el-button :loading="loading" circle title="刷新" @click="loadDashboard">↻</el-button>
    </div>

    <el-alert v-if="error" class="home-view__alert" type="error" :title="error" show-icon :closable="false" />
    <div v-else class="home-view__cards">
      <el-card class="home-view__card">
        <template #header>今日值班</template>
        <template v-if="dashboard.personal.today_duties.length">
          <p v-for="duty in dashboard.personal.today_duties" :key="`${duty.duty_date}-${duty.shift_name}`">
            {{ duty.shift_name }}：{{ duty.persons.join('、') }}
          </p>
        </template>
        <p v-else class="muted">今日暂无值班安排</p>
        <router-link v-if="auth.personId !== null" to="/schedule-mgmt/table">查看排班</router-link>
      </el-card>

      <el-card v-if="canUsePersonalBusiness" class="home-view__card">
        <template #header>个人待办</template>
        <p v-if="canInitiateDutyBusiness">待确认换班 {{ dashboard.personal.pending_swap_confirm_count }} 项</p>
        <p v-if="canConfirmCover">待确认顶班 {{ dashboard.personal.pending_cover_confirm_count }} 项</p>
        <p v-if="dashboard.personal.next_duty" class="muted">
          下次值班：{{ dashboard.personal.next_duty.duty_date }} {{ dashboard.personal.next_duty.shift_name }}
        </p>
        <router-link v-if="canInitiateDutyBusiness" to="/swap-request">处理换班申请</router-link>
        <router-link v-else-if="canConfirmCover" to="/my-cover">处理顶班任务</router-link>
      </el-card>

      <template v-if="dashboard.management">
        <el-card v-if="dashboard.management.pending_approval_count !== null" class="home-view__card">
          <template #header>审批待办</template>
          <p>待审批 {{ dashboard.management.pending_approval_count }} 项</p>
          <router-link to="/approval">前往审批中心</router-link>
        </el-card>
        <el-card v-if="dashboard.management.pending_cover_arrangement_count !== null" class="home-view__card">
          <template #header>顶班安排</template>
          <p>待安排顶班 {{ dashboard.management.pending_cover_arrangement_count }} 项</p>
          <router-link to="/leave-records">安排顶班</router-link>
        </el-card>
        <el-card v-if="dashboard.management.schedule_status !== null" class="home-view__card">
          <template #header>排班批次</template>
          <p>{{ scheduleStatusText }}</p>
          <router-link to="/schedule-mgmt/table">查看排班表</router-link>
        </el-card>
        <el-card v-if="dashboard.management.system_status.length" class="home-view__card">
          <template #header>系统状态</template>
          <p v-for="item in dashboard.management.system_status" :key="item">{{ item }}</p>
        </el-card>
      </template>
      <el-card v-if="dashboard.reminders.length" class="home-view__card">
        <template #header>业务提醒</template>
        <p v-for="reminder in dashboard.reminders" :key="reminder.type">
          <router-link v-if="reminder.path" :to="reminder.path">{{ reminder.title }} {{ reminder.count }} 项</router-link>
          <span v-else>{{ reminder.title }}</span>
        </p>
      </el-card>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { httpClient, resolveErrorMessage } from '@/services/http'
import { useAuthStore } from '@/stores/auth'

interface DutySummary { duty_date: string; shift_name: string; persons: string[] }
interface DashboardData {
  personal: { today_duties: DutySummary[]; next_duty: { duty_date: string; shift_name: string } | null; pending_swap_confirm_count: number; pending_cover_confirm_count: number }
  management: { pending_approval_count: number | null; pending_cover_arrangement_count: number | null; schedule_status: string | null; system_status: string[] } | null
  reminders: { type: string; title: string; count: number; path: string | null }[]
}

const emptyDashboard = (): DashboardData => ({
  personal: { today_duties: [], next_duty: null, pending_swap_confirm_count: 0, pending_cover_confirm_count: 0 },
  management: null,
  reminders: [],
})
const dashboard = ref<DashboardData>(emptyDashboard())
const auth = useAuthStore()
const loading = ref(false)
const error = ref('')
const scheduleStatusText = computed(() => dashboard.value.management?.schedule_status === 'published' ? '当前排班已发布' : '当前排班尚未发布')
const canInitiateDutyBusiness = computed(() => auth.personStatus === 'enabled' && auth.personType === 'duty_operator' && auth.participateSchedule)
const canConfirmCover = computed(() => auth.personStatus === 'enabled' && ['maintenance', 'room_director', 'deputy_director'].includes(auth.personType || ''))
const canUsePersonalBusiness = computed(() => canInitiateDutyBusiness.value || canConfirmCover.value)

async function loadDashboard(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    dashboard.value = (await httpClient.get<DashboardData>('/dashboard')).data
  } catch (err) {
    error.value = resolveErrorMessage(err, '工作台数据加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>

<style scoped>
.home-view__heading { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.home-view h1 { margin: 0; font-size: 24px; font-weight: 600; }
.home-view__heading p, .muted { color: #9ca3af; }
.home-view__alert { margin-bottom: 16px; }
.home-view__cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.home-view__card p { margin: 0 0 10px; font-size: 14px; }
.home-view__card a { font-size: 14px; color: var(--el-color-primary); text-decoration: none; }
</style>
