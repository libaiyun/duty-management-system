<template>
  <el-container class="app-layout">
    <el-header class="app-header">
      <div class="app-header__left">
        <el-icon
          class="app-header__collapse-icon"
          :size="20"
          @click="appStore.toggleSidebar()"
        >
          <Fold v-if="!appStore.sidebarCollapsed" />
          <Expand v-else />
        </el-icon>
        <span class="app-header__title">{{ appStore.systemName }}</span>
      </div>
      <div class="app-header__right">
        <el-badge :value="appStore.notificationCount" :hidden="appStore.notificationCount === 0">
          <el-icon :size="20" class="app-header__icon">
            <Bell />
          </el-icon>
        </el-badge>
        <el-select
          v-if="showRoomSwitcher"
          :model-value="roomContextStore.selectedRoomId"
          class="app-header__room-switcher"
          placeholder="选择机房"
          clearable
          @update:model-value="roomContextStore.selectRoom"
        >
          <el-option
            v-for="room in roomContextStore.rooms"
            :key="room.id"
            :label="room.name"
            :value="room.id"
          />
        </el-select>
        <el-dropdown trigger="click">
          <div class="app-header__user">
            <el-avatar :size="32" :icon="UserFilled" />
            <span class="app-header__user-name">{{ userLabel }}</span>
            <el-icon :size="14">
              <ArrowDown />
            </el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item>个人设置</el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>

    <el-container class="app-body">
      <el-aside :width="appStore.sidebarCollapsed ? '64px' : '220px'" class="app-sidebar">
        <el-menu
          :default-active="route.path"
          :collapse="appStore.sidebarCollapsed"
          :router="true"
          class="app-sidebar__menu"
        >
          <template v-for="item in visibleMenuItems" :key="item.name">
            <el-sub-menu v-if="item.children && item.children.length" :index="item.path">
              <template #title>
                <el-icon v-if="item.icon">
                  <component :is="item.icon" />
                </el-icon>
                <span>{{ item.title }}</span>
              </template>
              <el-menu-item
                v-for="child in item.children"
                :key="child.name"
                :index="child.path"
              >
                {{ child.title }}
              </el-menu-item>
            </el-sub-menu>
            <el-menu-item v-else :index="item.path">
              <el-icon v-if="item.icon">
                <component :is="item.icon" />
              </el-icon>
              <template #title>{{ item.title }}</template>
            </el-menu-item>
          </template>
        </el-menu>
      </el-aside>

      <el-main class="app-content">
        <el-breadcrumb class="app-breadcrumb" separator="/">
          <el-breadcrumb-item
            v-for="crumb in breadcrumbs"
            :key="crumb.path"
            :to="{ path: crumb.path }"
          >
            {{ crumb.title }}
          </el-breadcrumb-item>
        </el-breadcrumb>

        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowDown,
  Bell,
  Expand,
  Fold,
  UserFilled,
} from '@element-plus/icons-vue'

import { filterMenuByPermission, menuItems } from '@/config/menu'
import { useBreadcrumb } from '@/composables/useBreadcrumb'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { usePermissionStore } from '@/stores/permission'
import { useRoomContextStore } from '@/stores/room-context'

const appStore = useAppStore()
const authStore = useAuthStore()
const permissionStore = usePermissionStore()
const roomContextStore = useRoomContextStore()
const route = useRoute()
const router = useRouter()
const { breadcrumbs } = useBreadcrumb()

const GLOBAL_PAGE_NAMES = new Set(['org-unit', 'account-role', 'operation-log', 'backup-archive'])

const showRoomSwitcher = computed(() =>
  authStore.canSwitchRoom && !GLOBAL_PAGE_NAMES.has(String(route.name)),
)
const userLabel = computed(() => {
  if (authStore.canSwitchRoom || !roomContextStore.currentRoomName) return appStore.userName
  return `${appStore.userName} · ${roomContextStore.currentRoomName}`
})

const visibleMenuItems = computed(() =>
  filterMenuByPermission(menuItems, (code) => permissionStore.hasPermission(code)),
)

onMounted(async () => {
  try {
    await roomContextStore.loadRooms()
  } catch {
    // The selector remains empty until organization data becomes available.
  }
})

async function handleLogout(): Promise<void> {
  await authStore.logout()
  router.push({ name: 'login' })
}
</script>

<style scoped>
.app-layout {
  height: 100vh;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 16px;
  border-bottom: 1px solid var(--el-border-color-light);
  background: #fff;
}

.app-header__left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-header__collapse-icon {
  cursor: pointer;
  color: var(--el-text-color-regular);
  flex-shrink: 0;
}

.app-header__collapse-icon:hover {
  color: var(--el-color-primary);
}

.app-header__title {
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

.app-header__right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.app-header__icon {
  cursor: pointer;
  color: var(--el-text-color-regular);
}

.app-header__icon:hover {
  color: var(--el-color-primary);
}

.app-header__room-switcher {
  width: 180px;
}

.app-header__user {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
}

.app-header__user:hover {
  background: var(--el-fill-color-light);
}

.app-header__user-name {
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.app-body {
  height: calc(100vh - 56px);
}

.app-sidebar {
  border-right: 1px solid var(--el-border-color-light);
  background: #fff;
  overflow-x: hidden;
  transition: width 0.3s;
}

.app-sidebar__menu {
  border-right: none;
  min-height: 100%;
}

.app-content {
  background: var(--el-bg-color-page);
  overflow-y: auto;
}

.app-breadcrumb {
  margin-bottom: 16px;
}
</style>
