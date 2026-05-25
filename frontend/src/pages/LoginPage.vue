<template>
  <main class="login-page">
    <section class="login-shell">
      <div class="login-visual">
        <div class="brand" style="min-width: auto">
          <div class="brand-mark">J</div>
          <div>
            <div class="brand-title">JLAO 翡翠直播 AI 中控台</div>
            <div class="transcript-meta">主播、场控、客服的实时 AI 副驾</div>
          </div>
        </div>

        <div class="login-metrics">
          <div class="metric-box live-metric">
            <span class="metric-label">实时转写</span>
            <span class="metric-value">实时</span>
          </div>
          <div class="metric-box live-metric">
            <span class="metric-label">AI 建议</span>
            <span class="metric-value">5类</span>
          </div>
          <div class="metric-box live-metric">
            <span class="metric-label">人审执行</span>
            <span class="metric-value">100%</span>
          </div>
        </div>

        <div class="login-slogan">
          <h1>直播节奏要快，建议要准，界面要一眼看懂。</h1>
          <p>先登录进入直播中控台，选择当前翡翠商品，接入真实直播音画，AI 会实时给出话术、漏讲和风险提醒。</p>
        </div>
      </div>

      <div class="login-card">
        <h2>登录直播间</h2>
        <p class="transcript-meta">Demo 账号：operator / jlao123</p>
        <n-form :show-label="false" @submit.prevent="handleLogin">
          <n-form-item>
            <n-input v-model:value="username" size="large" placeholder="账号" />
          </n-form-item>
          <n-form-item>
            <n-input v-model:value="password" size="large" type="password" placeholder="密码" show-password-on="click" />
          </n-form-item>
          <n-button type="primary" size="large" block :loading="loading" @click="handleLogin">
            进入中控台
          </n-button>
        </n-form>

        <div class="login-roles">
          <n-tag size="small">场控 operator</n-tag>
          <n-tag size="small">主播 anchor</n-tag>
          <n-tag size="small">管理员 admin</n-tag>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NForm, NFormItem, NInput, NTag, useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()
const username = ref('operator')
const password = ref('jlao123')
const loading = ref(false)

async function handleLogin() {
  loading.value = true
  try {
    const user = await auth.login(username.value, password.value)
    message.success(`欢迎回来，${user.display_name}`)
    router.push('/live')
  } catch {
    message.error('账号或密码不正确')
  } finally {
    loading.value = false
  }
}
</script>
