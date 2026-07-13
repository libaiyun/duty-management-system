import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { router as appRouter } from '@/router'

import HolidayView from '@/views/base-data/HolidayView.vue'

vi.mock('@/services/http', () => ({
  httpClient: {
    get: vi.fn(() => Promise.resolve({ data: [] })),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

async function mountHolidayView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mount(HolidayView, {
    global: {
      plugins: [pinia, appRouter, ElementPlus],
    },
  })

  return wrapper
}

describe('HolidayView', () => {
  let wrapper: ReturnType<typeof mount>

  beforeEach(async () => {
    wrapper = await mountHolidayView()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page title', () => {
    expect(wrapper.find('h1').text()).toBe('节假日与标准')
  })

  it('renders three tabs', () => {
    const labels = wrapper.findAll('.el-tabs__item').map((t) => t.text())
    expect(labels).toContain('法定节假日')
    expect(labels).toContain('餐补标准')
    expect(labels).toContain('节假日加班费标准')
  })

  it('renders toolbar buttons', () => {
    const texts = wrapper.findAll('.holiday-view__toolbar .el-button').map((b) => b.text())
    expect(texts).toContain('新增节假日')
    expect(texts).toContain('批量导入')
  })

  it('renders the holiday table', () => {
    const table = wrapper.findComponent({ name: 'ElTable' })
    expect(table.exists()).toBe(true)
  })

  it('has correct holiday table columns', () => {
    const headerTexts = wrapper
      .findAll('.el-table__header-wrapper th .cell')
      .map((c) => c.text())
    expect(headerTexts).toContain('日期')
    expect(headerTexts).toContain('名称')
    expect(headerTexts).toContain('是否法定')
    expect(headerTexts).toContain('状态')
    expect(headerTexts).toContain('操作')
  })
})

describe('HolidayView route', () => {
  it('holiday route is registered with correct path', () => {
    const route = appRouter.getRoutes().find((r) => r.name === 'holiday-standard')
    expect(route).toBeDefined()
    expect(route?.path).toBe('/base-data/holiday')
  })

  it('holiday route has permission code assigned', () => {
    const route = appRouter.getRoutes().find((r) => r.name === 'holiday-standard')
    expect(route?.meta.permission).toBe('holiday:standard:view')
  })

  it('holiday route has a component', () => {
    const route = appRouter.getRoutes().find((r) => r.name === 'holiday-standard')
    expect(route?.components?.default).toBeDefined()
  })
})
