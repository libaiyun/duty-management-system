import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { router as appRouter } from '@/router'
import AccountRoleView from '@/views/system/AccountRoleView.vue'

const { get } = vi.hoisted(() => ({ get: vi.fn().mockResolvedValue({ data: [] }) }))

vi.mock('@/services/http', () => ({
  httpClient: { get, post: vi.fn(), put: vi.fn() },
}))

describe('AccountRoleView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockClear()
  })

  it('loads global binding persons from the dedicated endpoint', async () => {
    mount(AccountRoleView, { global: { plugins: [appRouter, ElementPlus] } })
    await vi.waitFor(() => expect(get).toHaveBeenCalledWith('/users/persons'))
    expect(get).not.toHaveBeenCalledWith('/persons')
    expect(get).toHaveBeenCalledWith('/permissions')
  })

  it('groups direct and effective permissions by function with Chinese labels', async () => {
    get.mockImplementation((url: string) => {
      const responses: Record<string, unknown> = {
        '/users': [{ id: 1, username: 'zhangsan', display_name: '张三', person_id: null, status: 'enabled', last_login_at: null, is_superuser: false }],
        '/roles': [{ id: 7, code: 'schedule-manager', name: '排班管理员', remark: null, status: 'enabled' }],
        '/permissions': [
          { id: 11, code: 'schedule:monthly:view', name: '查看排班', type: 'api', group_code: 'schedule', group_name: '排班管理' },
          { id: 12, code: 'schedule:rule:manage', name: '管理排班规则', type: 'api', group_code: 'schedule', group_name: '排班管理' },
          { id: 13, code: 'system:log:view', name: '查看操作日志', type: 'api', group_code: 'system', group_name: '系统管理' },
        ],
        '/users/persons': [],
        '/users/1': {
          id: 1,
          username: 'zhangsan',
          display_name: '张三',
          person_id: null,
          status: 'enabled',
          last_login_at: null,
          is_superuser: false,
          role_ids: [7],
          direct_permission_ids: [12],
          effective_permission_codes: ['schedule:monthly:view', 'schedule:rule:manage', 'system:log:view'],
          permission_sources: {
            'schedule:monthly:view': ['role:schedule-manager'],
            'schedule:rule:manage': ['role:schedule-manager', 'direct'],
            'system:log:view': ['role:schedule-manager'],
          },
        },
      }
      return Promise.resolve({ data: responses[url] ?? [] })
    })

    const wrapper = mount(AccountRoleView, { attachTo: document.body, global: { plugins: [appRouter, ElementPlus] } })
    await vi.waitFor(() => expect(get).toHaveBeenCalledWith('/permissions'))
    await vi.waitFor(() => expect(wrapper.text()).toContain('直接权限'))
    await wrapper.findAll('button').find((button) => button.text() === '直接权限')!.trigger('click')
    await nextTick()

    await vi.waitFor(() => expect(document.body.textContent).toContain('共 3 项 · 1 个角色 · 1 项直授'))
    expect(document.body.textContent).not.toContain('来源：')
    expect(document.body.textContent).toContain('全选')
    expect(document.body.textContent).toContain('系统管理')
    expect(document.body.textContent).not.toContain('schedule:monthly:view')
    expect(document.body.textContent).not.toContain('schedule:rule:manage')
    expect(document.body.textContent).not.toContain('role:schedule-manager')
    expect(document.body.textContent).not.toContain('direct')

    expect(document.querySelectorAll('.permission-workspace--fixed-height')).toHaveLength(1)
    expect(document.querySelectorAll('.permission-dialog-header')).toHaveLength(1)
    expect(document.querySelectorAll('.permission-dialog--raised')).toHaveLength(1)
    expect(document.body.textContent).toContain('账号权限配置')
    expect(document.querySelectorAll('.direct-permission-card')).toHaveLength(2)
    expect(document.querySelectorAll('.effective-permission-card')).toHaveLength(2)
    expect(document.querySelectorAll('.effective-permission-item__content')).toHaveLength(3)

    const checkboxes = Array.from(document.querySelectorAll<HTMLInputElement>('.permission-group .el-checkbox input'))
    await checkboxes[0].click()
    await nextTick()
    expect(checkboxes[1].checked).toBe(true)
    expect(checkboxes[2].checked).toBe(true)
    expect(checkboxes[3].checked).toBe(false)
    expect(checkboxes[4].checked).toBe(false)
    expect(document.body.textContent).toContain('共 3 项 · 1 个角色 · 2 项直授')

    wrapper.unmount()
  })
})
