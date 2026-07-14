import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { router as appRouter } from '@/router'
import { httpClient } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import { useRoomContextStore } from '@/stores/room-context'
import { createTestPinia } from './helpers'
import ScheduleTableView from '@/views/schedule/ScheduleTableView.vue'

vi.mock('@/services/http', () => ({
  httpClient: { get: vi.fn() },
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

async function mountView() {
  const pinia = createTestPinia()
  const authStore = useAuthStore()
  authStore.personId = 11
  authStore.roomId = 1
  authStore.roomName = '发射机房'
  const roomContextStore = useRoomContextStore()
  roomContextStore.selectRoom(1)

  vi.mocked(httpClient.get).mockImplementation((path: string) => {
    if (path.startsWith('/schedules?')) {
      return Promise.resolve({ code: 'OK', message: 'success', data: { items: [{ id: 99, status: 'published' }] }, trace_id: '' })
    }
    return Promise.resolve({ code: 'OK', message: 'success', data: days, trace_id: '' })
  })

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

  it('loads the selected room schedule and monthly days', async () => {
    await mountView()
    expect(httpClient.get).toHaveBeenCalledWith('/schedules?org_unit_id=1')
    expect(httpClient.get).toHaveBeenCalledWith(expect.stringContaining('/schedules/99/days?year='))
  })

  it('renders shift personnel in the calendar', async () => {
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('早班')
    expect(wrapper.text()).toContain('张三')
    expect(wrapper.text()).toContain('李四')
  })

  it('marks personal and legal-holiday duty dates', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('.schedule-table-view__day--mine').exists()).toBe(true)
    expect(wrapper.find('.schedule-table-view__day--holiday').exists()).toBe(true)
    expect(wrapper.text()).toContain('国庆节')
  })

  it('provides an enabled export-history entry', async () => {
    const wrapper = await mountView()
    const push = vi.spyOn(appRouter, 'push').mockResolvedValue(undefined)
    const exportButton = wrapper.findAll('button').find((button) => button.text().includes('导出 Excel'))

    expect((exportButton?.element as HTMLButtonElement).disabled).toBe(false)
    await exportButton?.trigger('click')
    expect(push).toHaveBeenCalledWith('/export-history')
  })

  it('switches to the list view with dynamic shift columns', async () => {
    const wrapper = await mountView()
    await wrapper.find('input[value="list"]').setValue()
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTable' }).exists()).toBe(true)
    expect(wrapper.text()).toContain('中班')
  })
})

describe('ScheduleTableView route', () => {
  it('registers the schedule-table route', () => {
    const route = appRouter.getRoutes().find((item) => item.name === 'schedule-table')
    expect(route?.path).toBe('/schedule-mgmt/table')
    expect(route?.meta.permission).toBe('schedule:monthly:view')
  })
})
