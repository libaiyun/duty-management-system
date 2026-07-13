import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { router as appRouter } from '@/router'

import ScheduleCalendarView from '@/views/schedule/ScheduleCalendarView.vue'

vi.mock('@/services/http', () => ({
  httpClient: {
    get: vi.fn(),
  },
  resolveErrorMessage: vi.fn((_err: unknown, fallback: string) => fallback),
}))

async function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mount(ScheduleCalendarView, {
    global: {
      plugins: [pinia, appRouter, ElementPlus],
    },
  })

  return wrapper
}

describe('ScheduleCalendarView', () => {
  let wrapper: ReturnType<typeof mount>

  beforeEach(async () => {
    wrapper = await mountView()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page title', () => {
    expect(wrapper.find('h1').text()).toBe('排班日历')
  })

  it('renders filter controls', () => {
    expect(wrapper.find('.schedule-calendar-view__filter-room').exists()).toBe(true)
    expect(wrapper.find('.schedule-calendar-view__filter-month').exists()).toBe(true)
    expect(wrapper.find('.schedule-calendar-view__filter-status').exists()).toBe(true)
  })

  it('renders the schedule table', () => {
    const table = wrapper.findComponent({ name: 'ElTable' })
    expect(table.exists()).toBe(true)
  })

  it('has correct data columns', () => {
    const headerCells = wrapper.findAll('.el-table__header-wrapper th .cell')
    const texts = headerCells.map((c) => c.text())
    expect(texts).toContain('月份')
    expect(texts).toContain('机房')
    expect(texts).toContain('排班规则')
    expect(texts).toContain('状态')
    expect(texts).toContain('操作')
  })
})

describe('ScheduleCalendarView route', () => {
  it('monthly-schedule route is registered with correct path', () => {
    const route = appRouter.getRoutes().find((r) => r.name === 'monthly-schedule')
    expect(route).toBeDefined()
    expect(route?.path).toBe('/schedule-mgmt/monthly')
  })

  it('monthly-schedule route has permission code', () => {
    const route = appRouter.getRoutes().find((r) => r.name === 'monthly-schedule')
    expect(route?.meta.permission).toBe('schedule:monthly:view')
  })

  it('monthly-schedule route has a component', () => {
    const route = appRouter.getRoutes().find((r) => r.name === 'monthly-schedule')
    expect(route?.components?.default).toBeDefined()
  })
})
