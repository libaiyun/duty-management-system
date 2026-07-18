import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { router as appRouter } from '@/router'
import { httpClient } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import { usePermissionStore } from '@/stores/permission'
import { useRoomContextStore } from '@/stores/room-context'
import { createTestPinia } from './helpers'
import ScheduleTableView from '@/views/schedule/ScheduleTableView.vue'

vi.mock('@/services/http', () => ({
  httpClient: { get: vi.fn(), post: vi.fn() },
  resolveErrorMessage: vi.fn((_error: unknown, fallback: string) => fallback),
}))

const days = [
  {
    duty_date: '2026-07-01', weekday: 2, is_legal_holiday: false, holiday_name: null,
    shifts: [
      { id: 1, shift_def_id: 1, shift_def_name: '早班', persons: [{ person_id: 11, person_name: '张三' }] },
      { id: 2, shift_def_id: 2, shift_def_name: '中班', persons: [{ person_id: 12, person_name: '李四' }] },
    ],
  },
  {
    duty_date: '2026-07-02', weekday: 3, is_legal_holiday: true, holiday_name: '国庆节',
    shifts: [{ id: 3, shift_def_id: 1, shift_def_name: '早班', persons: [{ person_id: 11, person_name: '张三' }] }],
  },
]

async function mountView(coverageThrough = '2099-12-31', canManage = false, scheduleStatus = 'published') {
  const pinia = createTestPinia()
  const authStore = useAuthStore()
  authStore.personId = 11
  authStore.roomId = 1
  authStore.roomName = '发射机房'
  const roomContextStore = useRoomContextStore()
  roomContextStore.selectRoom(1)
  if (canManage) usePermissionStore().setPermissions(['schedule:monthly:generate'])

  vi.mocked(httpClient.get).mockImplementation((path: string) => {
    if (path.startsWith('/schedules?')) {
      return Promise.resolve({ code: 'OK', message: 'success', data: { items: [{ id: 99, status: scheduleStatus, coverage_through: coverageThrough }] }, trace_id: '' })
    }
    return Promise.resolve({ code: 'OK', message: 'success', data: days, trace_id: '' })
  })
  vi.mocked(httpClient.post).mockResolvedValue({ code: 'OK', message: 'success', data: {}, trace_id: '' })

  const wrapper = mount(ScheduleTableView, {
    global: { plugins: [pinia, appRouter, ElementPlus] },
  })
  await flushPromises()
  return wrapper
}

describe('ScheduleTableView', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders the revised page title without a room filter', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('h1').text()).toBe('排班表')
    expect(wrapper.find('.schedule-calendar-view__filter-room').exists()).toBe(false)
  })

  it('loads an already covered month without generating it again', async () => {
    await mountView()
    expect(httpClient.get).toHaveBeenCalledWith('/schedules?org_unit_id=1')
    expect(httpClient.post).not.toHaveBeenCalled()
    expect(httpClient.get).toHaveBeenCalledWith(expect.stringContaining('/schedules/99/days?year='))
  })

  it('extends coverage before loading an uncovered month', async () => {
    await mountView('2000-01-01', true)
    expect(httpClient.post).toHaveBeenCalledWith(expect.stringMatching(/^\/schedules\/99\/generate\?through=\d{4}-\d{2}-\d{2}$/))
  })

  it('renders shift personnel in the calendar', async () => {
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('早班')
    expect(wrapper.text()).toContain('张三')
    expect(wrapper.text()).toContain('李四')
  })

  it('does not display a change marker without an effective change ledger entry', async () => {
    const changedShift = days[0].shifts[0] as typeof days[number]['shifts'][number] & { change_types?: string[] }
    changedShift.change_types = ['manual']
    const wrapper = await mountView()

    expect(wrapper.find('.schedule-table-view__change-tag').exists()).toBe(false)
    delete changedShift.change_types
  })

  it('marks personal and legal-holiday duty dates', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('.schedule-table-view__day--mine').exists()).toBe(true)
    expect(wrapper.find('.schedule-table-view__day--holiday').exists()).toBe(true)
    expect(wrapper.text()).toContain('国庆节')
  })

  it('creates the current-month export before opening its history', async () => {
    const wrapper = await mountView('2099-12-31', true)
    const push = vi.spyOn(appRouter, 'push').mockResolvedValue(undefined)
    const exportButton = wrapper.findAll('button').find((button) => button.text().includes('导出 Excel'))

    expect((exportButton?.element as HTMLButtonElement).disabled).toBe(false)
    await exportButton?.trigger('click')
    expect(httpClient.post).toHaveBeenCalledWith('/exports/schedule', expect.objectContaining({ schedule_id: 99 }))
    expect(push).toHaveBeenCalledWith('/export-history')
  })

  it('does not expose the export action to read-only users', async () => {
    const wrapper = await mountView()
    expect(wrapper.findAll('button').some((button) => button.text().includes('导出 Excel'))).toBe(false)
  })

  it('lets a manager publish an adjusted draft schedule', async () => {
    const wrapper = await mountView('2099-12-31', true, 'draft')
    const publishButton = wrapper.findAll('button').find((button) => button.text().includes('发布排班'))

    expect(publishButton?.exists()).toBe(true)
    await publishButton?.trigger('click')
    expect(httpClient.post).toHaveBeenCalledWith('/schedules/99/publish')
  })

  it('switches to the list view with dynamic shift columns', async () => {
    const wrapper = await mountView()
    await wrapper.find('input[value="list"]').setValue()
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTable' }).exists()).toBe(true)
    expect(wrapper.text()).toContain('中班')
  })

  it('shows a concise list query panel and the filtered result count', async () => {
    const wrapper = await mountView()
    await wrapper.find('input[value="list"]').setValue()
    await flushPromises()

    expect(wrapper.find('.schedule-table-view__filter-panel').exists()).toBe(true)
    expect(wrapper.find('.schedule-table-view__result-count').text()).toContain('共 2 条')
    expect(wrapper.find('button.schedule-table-view__reset').text()).toBe('重置')
    expect(wrapper.find('#schedule-shift').exists()).toBe(false)
  })

})

describe('ScheduleTableView route', () => {
  it('registers the schedule-table route', () => {
    const route = appRouter.getRoutes().find((item) => item.name === 'schedule-table')
    expect(route?.path).toBe('/schedule-mgmt/table')
    expect(route?.meta.permission).toBe('schedule:monthly:view')
  })
})
