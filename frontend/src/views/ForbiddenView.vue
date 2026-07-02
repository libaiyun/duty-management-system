<template>
  <section class="forbidden-view">
    <h1>403</h1>
    <p>你无权访问该页面。</p>
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
.forbidden-view {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  text-align: center;
}

.forbidden-view h1 {
  font-size: 72px;
  font-weight: 700;
  color: var(--el-color-danger);
  margin: 0 0 8px;
  line-height: 1;
}

.forbidden-view p {
  font-size: 16px;
  color: var(--el-text-color-secondary);
  margin: 0 0 24px;
}
</style>
