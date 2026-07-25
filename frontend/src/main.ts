import 'element-plus/dist/index.css'
import '@/styles/index.css'

import {
  ElAlert,
  ElAside,
  ElAvatar,
  ElBadge,
  ElBreadcrumb,
  ElBreadcrumbItem,
  ElButton,
  ElCalendar,
  ElCard,
  ElCheckbox,
  ElCheckboxGroup,
  ElCol,
  ElContainer,
  ElDatePicker,
  ElDescriptions,
  ElDescriptionsItem,
  ElDialog,
  ElDivider,
  ElDrawer,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElHeader,
  ElIcon,
  ElInput,
  ElInputNumber,
  ElMain,
  ElMenu,
  ElMenuItem,
  ElOption,
  ElPagination,
  ElRadio,
  ElRadioButton,
  ElRadioGroup,
  ElRow,
  ElSelect,
  ElSubMenu,
  ElSwitch,
  ElTabPane,
  ElTable,
  ElTableColumn,
  ElTabs,
  ElTag,
  ElTree,
} from 'element-plus'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from '@/App.vue'
import { router } from '@/router'
import { httpClient } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import { useRoomContextStore } from '@/stores/room-context'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
const elementComponents = [
  ElAlert, ElAside, ElAvatar, ElBadge, ElBreadcrumb, ElBreadcrumbItem,
  ElButton, ElCalendar, ElCard, ElCheckbox, ElCheckboxGroup, ElCol,
  ElContainer, ElDatePicker, ElDescriptions, ElDescriptionsItem, ElDialog,
  ElDivider, ElDrawer, ElDropdown, ElDropdownItem, ElDropdownMenu, ElEmpty,
  ElForm, ElFormItem, ElHeader, ElIcon, ElInput, ElInputNumber, ElMain,
  ElMenu, ElMenuItem, ElOption, ElPagination, ElRadio, ElRadioButton,
  ElRadioGroup, ElRow, ElSelect, ElSubMenu, ElSwitch, ElTabPane, ElTable,
  ElTableColumn, ElTabs, ElTag, ElTree,
]
for (const component of elementComponents) {
  app.component(component.name!, component)
}

const authStore = useAuthStore()
const roomContextStore = useRoomContextStore()

httpClient.configureCallbacks({
  getToken: () => authStore.accessToken || null,
  getCurrentRoomId: () => roomContextStore.currentRoomId,
  refreshToken: () => authStore.refreshAccessToken(),
  onUnauthorized: () => {
    authStore.forceLogout()
    router.push({ name: 'login' })
  },
})

;(async () => {
  try {
    await authStore.restoreSession()
  } catch {
    // session restore failure already handled internally
  }
  app.use(router)
  app.mount('#app')
})()
