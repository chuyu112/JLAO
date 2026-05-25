<template>
  <nav class="top-nav">
    <div class="brand">
      <div class="brand-mark">J</div>
      <div>
        <div class="brand-title">{{ title }}</div>
        <div class="transcript-meta">{{ subtitle }}</div>
      </div>
    </div>

    <div class="top-actions">
      <div class="nav-links">
        <router-link class="nav-link" to="/live">中控台</router-link>
        <router-link class="nav-link" to="/products">商品库</router-link>
        <router-link class="nav-link" to="/replay">观察报告</router-link>
      </div>
      <div class="user-chip" v-if="auth.user">
        <span class="user-dot"></span>
        <span>{{ auth.user.display_name }}</span>
        <n-tag size="small" type="success">{{ auth.user.role }}</n-tag>
      </div>
      <n-button size="small" quaternary @click="logout">
        退出
      </n-button>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { NButton, NTag } from 'naive-ui'
import { useAuthStore } from '../stores/auth'

defineProps<{
  title: string
  subtitle?: string
}>()

const router = useRouter()
const auth = useAuthStore()

function logout() {
  auth.logout()
  router.push('/login')
}
</script>
