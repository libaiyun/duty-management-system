<template>
  <div class="app-shell">
    <header class="app-shell__header">
      <span class="app-shell__title">{{ appStore.systemName }}</span>
    </header>
    <main class="app-shell__main">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
</script>
