import 'element-plus/dist/index.css'
import '@/styles/index.css'

import ElementPlus from 'element-plus'
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
app.use(router)
app.use(ElementPlus)

const authStore = useAuthStore()
const roomContextStore = useRoomContextStore()

httpClient.configureCallbacks({
  getToken: () => authStore.accessToken || null,
  getCurrentRoomId: () => roomContextStore.currentRoomId,
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
  app.mount('#app')
})()
