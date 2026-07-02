import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'

import HomeView from '@/views/HomeView.vue'
import AppShell from '@/layouts/AppShell.vue'

async function mountAppShell() {
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      {
        path: '/',
        name: 'home',
        component: HomeView,
        meta: { title: '工作台' },
      },
    ],
  })
  await router.push('/')
  await router.isReady()

  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mount(AppShell, {
    global: {
      plugins: [pinia, router, ElementPlus],
    },
  })

  return wrapper
}

describe('AppShell', () => {
  let wrapper: ReturnType<typeof mount>

  beforeEach(async () => {
    wrapper = await mountAppShell()
  })

  it('renders the system name in the header', () => {
    const title = wrapper.find('.app-header__title')
    expect(title.exists()).toBe(true)
    expect(title.text()).toBe('广播电视台站值班管理系统')
  })

  it('renders the user name in the header', () => {
    const userName = wrapper.find('.app-header__user-name')
    expect(userName.exists()).toBe(true)
    expect(userName.text()).toBe('管理员')
  })

  it('renders sidebar menu items', () => {
    const menu = wrapper.find('.app-sidebar__menu')
    expect(menu.exists()).toBe(true)
  })

  it('renders breadcrumb with current route title', () => {
    const breadcrumb = wrapper.find('.app-breadcrumb')
    expect(breadcrumb.exists()).toBe(true)
    expect(breadcrumb.text()).toContain('工作台')
  })

  it('toggles sidebar collapse when clicking the collapse icon', async () => {
    const icon = wrapper.find('.app-header__collapse-icon')
    expect(icon.exists()).toBe(true)

    const sidebar = wrapper.find('.app-sidebar')
    const styleBefore = sidebar.attributes('style')
    expect(styleBefore).toBeDefined()

    await icon.trigger('click')
    await nextTick()

    const styleAfter = sidebar.attributes('style')
    expect(styleAfter).toBeDefined()
    expect(styleAfter).not.toBe(styleBefore)
  })

  it('renders the content area with RouterView', () => {
    const content = wrapper.find('.app-content')
    expect(content.exists()).toBe(true)
  })
})
