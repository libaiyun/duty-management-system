import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createRouter, createWebHistory } from 'vue-router'
import { describe, expect, it } from 'vitest'

import ForbiddenView from '@/views/ForbiddenView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: { template: '<div />' } },
    { path: '/403', name: 'forbidden', component: { template: '<div />' } },
  ],
})

describe('ForbiddenView', () => {
  it('renders 403 heading', () => {
    const wrapper = mount(ForbiddenView, {
      global: {
        plugins: [ElementPlus, router],
      },
    })

    expect(wrapper.find('h1').text()).toBe('403')
    expect(wrapper.text()).toContain('你无权访问该页面')
  })

  it('has a button to go back to workbench', () => {
    const wrapper = mount(ForbiddenView, {
      global: {
        plugins: [ElementPlus, router],
      },
    })

    const button = wrapper.find('button')
    expect(button.exists()).toBe(true)
    expect(button.text()).toContain('返回工作台')
  })
})
