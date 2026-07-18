import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it, vi } from 'vitest'
import ApprovalCenterView from '@/views/approval/ApprovalCenterView.vue'
import { httpClient } from '@/services/http'
import { createTestPinia } from './helpers'

vi.mock('@/services/http', () => ({ httpClient: { get: vi.fn(), post: vi.fn() }, resolveErrorMessage: vi.fn((_e: unknown, fallback: string) => fallback) }))

describe('ApprovalCenterView', () => {
  it('loads todo tasks and submits the approval action from its drawer', async () => {
    vi.mocked(httpClient.get).mockResolvedValue({ code: 'OK', message: 'success', trace_id: '', data: { items: [{ id: 1, biz_type: 'leave_request', biz_id: 8, node_code: 'director_approval', status: 'pending', arrived_at: '2026-07-18T00:00:00Z', snapshot: { applicant: '张三' } }] } })
    vi.mocked(httpClient.post).mockResolvedValue({ code: 'OK', message: 'success', trace_id: '', data: {} })
    const wrapper = mount(ApprovalCenterView, { global: { plugins: [createTestPinia(), ElementPlus] } })
    await flushPromises()
    expect(httpClient.get).toHaveBeenCalledWith('/approval-tasks/todo?page=1&page_size=50')
    await wrapper.find('button').trigger('click')
    await wrapper.find('textarea').setValue('同意')
    await wrapper.findAll('button').find((button) => button.text() === '同意')!.trigger('click')
    expect(httpClient.post).toHaveBeenCalledWith('/approval-tasks/1/approve', { opinion: '同意' })
  })
})
