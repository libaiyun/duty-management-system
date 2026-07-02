import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it } from 'vitest'

import AppShell from '@/layouts/AppShell.vue'

describe('AppShell', () => {
  it('renders the configured system name from the app store', () => {
    const wrapper = mount(AppShell, {
      global: {
        plugins: [createPinia()],
        stubs: {
          RouterView: true,
        },
      },
    })

    expect(wrapper.find('.app-shell__title').text()).toBe('广播电视台站值班管理系统')
  })
})
