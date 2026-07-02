<template>
  <section class="placeholder-view">
    <h2>{{ route.meta.title }}</h2>
    <p>该页面功能将在后续 Task 中实现。</p>
  </section>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<style scoped>
.placeholder-view {
  background: #fff;
  border-radius: 6px;
  padding: 32px 24px;
  min-height: 200px;
}

.placeholder-view h2 {
  margin: 0 0 12px;
  font-size: 20px;
  font-weight: 600;
  color: #1f2937;
}

.placeholder-view p {
  margin: 0;
  color: #9ca3af;
  font-size: 14px;
}
</style>
