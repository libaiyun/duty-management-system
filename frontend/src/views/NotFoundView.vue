<template>
  <section class="not-found-view">
    <h1>404</h1>
    <p>页面不存在。</p>
    <el-button type="primary" @click="goHome">返回工作台</el-button>
  </section>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function goHome(): void {
  router.push({ name: 'home' })
}
</script>

<style scoped>
.not-found-view {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  text-align: center;
}

.not-found-view h1 {
  font-size: 72px;
  font-weight: 700;
  color: var(--el-text-color-disabled);
  margin: 0 0 8px;
  line-height: 1;
}

.not-found-view p {
  font-size: 16px;
  color: var(--el-text-color-secondary);
  margin: 0 0 24px;
}
</style>
