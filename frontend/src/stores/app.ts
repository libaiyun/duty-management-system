import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', {
  state: () => ({
    systemName: '广播电视台站值班管理系统',
    sidebarCollapsed: false,
    userName: '管理员',
    notificationCount: 0,
    userAvatar: '',
  }),
  actions: {
    toggleSidebar(): void {
      this.sidebarCollapsed = !this.sidebarCollapsed
    },
  },
})
