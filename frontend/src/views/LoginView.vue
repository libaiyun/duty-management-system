<template>
  <div class="login-view">
    <div class="login-view__card">
      <h1 class="login-view__title">广播电视台站值班管理系统</h1>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item label="账号" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入账号"
            :disabled="loading"
            autocomplete="username"
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :disabled="loading"
            show-password
            autocomplete="current-password"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            class="login-view__button"
            :loading="loading"
            @click="handleLogin"
          >
            {{ loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>
      <p v-if="errorMessage" class="login-view__error">{{ errorMessage }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'

import { ApiError, NetworkError } from '@/services/http'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const form = reactive({ username: '', password: '' })
const loading = ref(false)
const errorMessage = ref('')

const rules: FormRules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  errorMessage.value = ''

  try {
    await authStore.login(form.username, form.password)
    const redirect = String(route.query.redirect || '/')
    router.replace(redirect)
  } catch (err) {
    console.error('[Login]', err)
    if (err instanceof ApiError) {
      errorMessage.value = err.message
    } else if (err instanceof NetworkError) {
      errorMessage.value = '网络连接失败，请检查网络'
    } else {
      errorMessage.value = '登录失败，请稍后重试'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-view {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-view__card {
  width: 400px;
  padding: 40px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.login-view__title {
  margin: 0 0 32px;
  font-size: 20px;
  font-weight: 600;
  text-align: center;
  color: #1f2937;
}

.login-view__button {
  width: 100%;
}

.login-view__error {
  margin: 12px 0 0;
  font-size: 13px;
  color: var(--el-color-danger);
  text-align: center;
}
</style>
