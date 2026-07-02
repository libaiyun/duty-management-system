import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import { menuItems } from '@/config/menu'
import HomeView from '@/views/HomeView.vue'
import PlaceholderView from '@/views/PlaceholderView.vue'

function buildRoutes(items: (typeof menuItems)): RouteRecordRaw[] {
  return items.map((item): RouteRecordRaw => {
    if (item.children && item.children.length > 0) {
      return {
        path: item.path,
        name: item.name,
        meta: { title: item.title },
        redirect: item.children[0].path,
        children: buildRoutes(item.children),
      }
    }
    return {
      path: item.path,
      name: item.name,
      component: item.name === 'home' ? HomeView : PlaceholderView,
      meta: { title: item.title },
    }
  })
}

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: buildRoutes(menuItems),
})
