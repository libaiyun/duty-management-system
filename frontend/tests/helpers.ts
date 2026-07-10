import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore } from '@/stores/auth'

export function createTestPinia() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return pinia
}

export function createAuthStore() {
  createTestPinia()
  return useAuthStore()
}
