import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { router as appRouter } from '@/router'

import PersonView from '@/views/base-data/PersonView.vue'

vi.mock('@/services/http', () => ({
  httpClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}))

async function mountPersonView() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mount(PersonView, {
    global: {
      plugins: [pinia, appRouter, ElementPlus],
    },
  })

  return wrapper
}

describe('PersonView', () => {
  let wrapper: ReturnType<typeof mount>

  beforeEach(async () => {
    wrapper = await mountPersonView()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page title', () => {
    expect(wrapper.find('h1').text()).toBe('人员管理')
  })

  it('renders the add person button', () => {
    const btn = wrapper.find('.person-view__toolbar .el-button')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toContain('新增人员')
  })

  it('renders filter inputs', () => {
    const filters = wrapper.find('.person-view__filters')
    expect(filters.exists()).toBe(true)
  })

  it('renders the person table', () => {
    const table = wrapper.findComponent({ name: 'ElTable' })
    expect(table.exists()).toBe(true)
  })

  it('has correct data columns in table', () => {
    const headerCells = wrapper.findAll('.el-table__header-wrapper th .cell')
    const headerTexts = headerCells.map((c) => c.text())
    expect(headerTexts).toContain('编号')
    expect(headerTexts).toContain('姓名')
    expect(headerTexts).toContain('人员类型')
    expect(headerTexts).toContain('所属台站机房')
    expect(headerTexts).toContain('状态')
    expect(headerTexts).toContain('账号状态')
    expect(headerTexts).toContain('操作')
  })
})

describe('PersonView route', () => {
  it('person route is registered with correct path', () => {
    const route = appRouter.getRoutes().find((r) => r.name === 'person')
    expect(route).toBeDefined()
    expect(route?.path).toBe('/base-data/person')
  })

  it('person route has permission code assigned', () => {
    const route = appRouter.getRoutes().find((r) => r.name === 'person')
    expect(route?.meta.permission).toBe('person:manage:view')
  })

  it('person route has a component', () => {
    const route = appRouter.getRoutes().find((r) => r.name === 'person')
    expect(route?.components?.default).toBeDefined()
  })
})
