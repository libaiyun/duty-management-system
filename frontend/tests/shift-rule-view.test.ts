import { mount } from '@vue/test-utils'
import ElementPlus, { ElSelect } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { router as appRouter } from '@/router'
import { httpClient } from '@/services/http'

import ShiftRuleView from '@/views/base-data/ShiftRuleView.vue'
import ShiftDefView from '@/views/base-data/ShiftDefView.vue'

vi.mock('@/services/http', () => ({
  httpClient: {
    get: vi.fn((url: string) => {
      if (url === '/shifts') return Promise.resolve({ data: [] })
      if (url === '/shift-rules') return Promise.resolve({ data: [] })
      if (url === '/persons') return Promise.resolve({ data: [] })
      return Promise.resolve({ data: [] })
    }),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

async function mountView(component: typeof ShiftRuleView | typeof ShiftDefView) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mount(component, {
    global: {
      plugins: [pinia, appRouter, ElementPlus],
    },
  })

  // Wait for async mounted hooks
  await new Promise((resolve) => setTimeout(resolve, 10))
  return wrapper
}

describe('ShiftDefView', () => {
  let wrapper: ReturnType<typeof mount>

  beforeEach(async () => {
    wrapper = await mountView(ShiftDefView)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders the shift definition page', () => {
    expect(wrapper.find('h1').text()).toBe('班次规则')
    expect(wrapper.text()).toContain('新增班次')
    expect(wrapper.find('.el-tabs').exists()).toBe(false)
    expect(httpClient.get).toHaveBeenCalledWith('/shifts')
  })
})

describe('ShiftRuleView', () => {
  let wrapper: ReturnType<typeof mount>

  beforeEach(async () => {
    wrapper = await mountView(ShiftRuleView)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders the scheduling rule page without an org-unit selector', () => {
    expect(wrapper.find('h1').text()).toBe('排班规则')
    expect(wrapper.text()).toContain('新增规则')
    expect(wrapper.text()).not.toContain('适用机房')
    expect(wrapper.find('.el-tabs').exists()).toBe(false)
    expect(httpClient.get).toHaveBeenCalledWith('/shift-rules')
    expect(httpClient.get).not.toHaveBeenCalledWith('/org-units')
  })

  it('offers publishing again after the refreshed rule is a draft', async () => {
    vi.mocked(httpClient.get).mockImplementation((url: string) => {
      if (url === '/shift-rules') {
        return Promise.resolve({
          code: 'OK',
          message: 'success',
          trace_id: '',
          data: [{ id: 1, code: 'rule', name: '规则', cycle_days: 1, start_date: '2027-01-01', persons_per_cell: 1, status: 'draft', remark: null, latest_version_id: 2, items: [] }],
        })
      }
      return Promise.resolve({ code: 'OK', message: 'success', trace_id: '', data: [] })
    })
    wrapper.unmount()
    wrapper = await mountView(ShiftRuleView)

    expect(wrapper.text()).toContain('发布')
  })

  it('renders one person selector per configured slot in each grid cell', async () => {
    vi.mocked(httpClient.get).mockImplementation((url: string) => {
      if (url === '/shifts') {
        return Promise.resolve({ code: 'OK', message: 'success', trace_id: '', data: [
          { id: 1, code: 'morning', name: '早班', start_time: '00:00', end_time: '08:00', display_order: 1, status: 'enabled' },
          { id: 2, code: 'afternoon', name: '中班', start_time: '08:00', end_time: '16:00', display_order: 2, status: 'enabled' },
        ] })
      }
      return Promise.resolve({ code: 'OK', message: 'success', trace_id: '', data: [] })
    })
    wrapper.unmount()
    wrapper = await mountView(ShiftRuleView)

    await wrapper.get('.shift-rule-view__toolbar button').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 300))

    expect(wrapper.findAllComponents(ElSelect)).toHaveLength(24)
  })
})

describe('ShiftRuleView route', () => {
  it('schedule-rule route is registered with correct path', () => {
    const route = appRouter.getRoutes().find((r) => r.name === 'schedule-rule')
    expect(route).toBeDefined()
    expect(route?.path).toBe('/schedule-rule')
  })

  it('schedule-rule route has permission code assigned', () => {
    const route = appRouter.getRoutes().find((r) => r.name === 'schedule-rule')
    expect(route?.meta.permission).toBe('shift:rule:view')
  })

  it('schedule-rule route has a component', () => {
    const route = appRouter.getRoutes().find((r) => r.name === 'schedule-rule')
    expect(route?.components?.default).toBeDefined()
  })

  it('shift-def route is registered with the shift definition component', async () => {
    const route = appRouter.getRoutes().find((r) => r.name === 'shift-def')
    expect(route?.path).toBe('/base-data/shifts')
    expect(route?.components?.default).toBeDefined()
  })
})
