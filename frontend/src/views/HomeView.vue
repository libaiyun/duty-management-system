<template>
  <section class="home-view">
    <h1>工作台</h1>
    <div class="home-view__cards">
      <el-card class="home-view__card">
        <template #header>今日值班</template>
        <p>暂无排班数据</p>
      </el-card>
      <el-card class="home-view__card">
        <template #header>待办提醒</template>
        <p>暂无待办事项</p>
      </el-card>
      <el-card class="home-view__card">
        <template #header>排班状态</template>
        <p>暂无排班信息</p>
      </el-card>
    </div>
  </section>
</template>

<style scoped>
.home-view h1 {
  margin: 0 0 24px;
  font-size: 24px;
  font-weight: 600;
}

.home-view__cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.home-view__card p {
  margin: 0;
  color: #9ca3af;
  font-size: 14px;
}
</style>
