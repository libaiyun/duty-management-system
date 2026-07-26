import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it, vi } from 'vitest'
import HomeView from '@/views/HomeView.vue'
import { httpClient } from '@/services/http'
import { createTestPinia } from './helpers'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/services/http', () => ({ httpClient: { get: vi.fn() }, resolveErrorMessage: vi.fn((_e: unknown, fallback: string) => fallback) }))

describe('HomeView', () => {
  it('renders personal and permission-gated management dashboard cards', async () => {
    vi.mocked(httpClient.get).mockResolvedValue({ code: 'OK', message: 'success', trace_id: '', data: {
      personal: { today_duties: [{ duty_date: '2026-07-26', shift_name: '早班', persons: ['张三'] }], next_duty: null, pending_swap_confirm_count: 1, pending_cover_confirm_count: 0 },
      management: { pending_approval_count: 2, pending_cover_arrangement_count: null, schedule_status: 'published', system_status: [] },
      reminders: [{ type: 'swap_confirm', title: '待确认换班', count: 1, path: '/swap-request' }],
    } })
    const pinia = createTestPinia()
    const auth = useAuthStore()
    auth.personId = 1
    auth.personStatus = 'enabled'
    auth.personType = 'duty_operator'
    auth.participateSchedule = true
    const wrapper = mount(HomeView, { global: { plugins: [pinia, ElementPlus], stubs: { RouterLink: RouterLinkStub } } })

    await flushPromises()

    expect(httpClient.get).toHaveBeenCalledWith('/dashboard')
    expect(wrapper.text()).toContain('今日值班')
    expect(wrapper.text()).toContain('待确认换班 1 项')
    expect(wrapper.text()).toContain('待审批 2 项')
    expect(wrapper.text()).not.toContain('待安排顶班')
  })
})
