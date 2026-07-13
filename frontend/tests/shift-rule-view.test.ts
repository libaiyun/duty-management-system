import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { router as appRouter } from '@/router'

import ShiftRuleView from '@/views/base-data/ShiftRuleView.vue'

vi.mock('@/services/http', () => ({
  httpClient: {
    get: vi.fn(() => Promise.resolve({ data: [] })),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

async function mountShiftRuleView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mount(ShiftRuleView, {
    global: {
      plugins: [pinia, appRouter, ElementPlus],
    },
  })

  return wrapper
}

describe('ShiftRuleView', () => {
  let wrapper: ReturnType<typeof mount>

  beforeEach(async () => {
    wrapper = await mountShiftRuleView()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page title', () => {
    expect(wrapper.find('h1').text()).toBe('班次规则')
  })

  it('renders two tabs (班次定义 / 排班规则)', () => {
    const tabs = wrapper.findAll('.el-tabs__item')
    const labels = tabs.map((t) => t.text())
    expect(labels).toContain('班次定义')
    expect(labels).toContain('排班规则')
  })

  it('renders add buttons in toolbars', () => {
    const btns = wrapper.findAll('.shift-rule-view__toolbar .el-button')
    const texts = btns.map((b) => b.text())
    expect(texts).toContain('新增班次')
    expect(texts).toContain('新增规则')
  })

  it('renders tables for both tabs', () => {
    const tables = wrapper.findAllComponents({ name: 'ElTable' })
    expect(tables.length).toBeGreaterThanOrEqual(2)
  })

  it('has shift-def columns', () => {
    const headerTexts = wrapper
      .findAll('.el-table__header-wrapper th .cell')
      .map((c) => c.text())
    expect(headerTexts).toContain('编码')
    expect(headerTexts).toContain('时间段')
  })
})

describe('ShiftRuleView route', () => {
  it('shift-rule route is registered with correct path', () => {
    const route = appRouter.getRoutes().find((r) => r.name === 'shift-rule')
    expect(route).toBeDefined()
    expect(route?.path).toBe('/base-data/shift-rule')
  })

  it('shift-rule route has permission code assigned', () => {
    const route = appRouter.getRoutes().find((r) => r.name === 'shift-rule')
    expect(route?.meta.permission).toBe('shift:rule:view')
  })

  it('shift-rule route has a component', () => {
    const route = appRouter.getRoutes().find((r) => r.name === 'shift-rule')
    expect(route?.components?.default).toBeDefined()
  })
})
