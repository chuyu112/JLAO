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
        <router-link v-if="!isModeLinkLocked('/live')" class="nav-link mode-nav-link" to="/live">自有运营</router-link>
        <span v-else class="nav-link mode-nav-link disabled" aria-disabled="true">自有运营</span>

        <router-link v-if="!isModeLinkLocked('/observe')" class="nav-link mode-nav-link" to="/observe">其它分析</router-link>
        <span v-else class="nav-link mode-nav-link disabled" aria-disabled="true">其它分析</span>

        <a class="nav-link" href="/live#knowledge">知识库</a>
        <a class="nav-link" href="/live#customers">客户库</a>
        <a class="nav-link" href="/live#products">商品库</a>
        <a class="nav-link" href="/live#operations">运营库</a>
        <router-link class="nav-link" to="/jade-recognition">翡翠识别</router-link>
        <router-link class="nav-link" to="/replay">观察报告</router-link>
      </div>
      <div class="user-chip" v-if="auth.user">
        <span class="user-dot"></span>
        <span>{{ auth.user.display_name }}</span>
        <n-tag size="small" type="success">{{ auth.user.role }}</n-tag>
      </div>
      <settings-panel />
      <n-button size="small" quaternary @click="logout">退出</n-button>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { NButton, NTag } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { useJlaoStore } from '../stores/jlao'
import SettingsPanel from './SettingsPanel.vue'
import { isModeSwitchLocked } from '../utils/captureMode'

defineProps<{
  title: string
  subtitle?: string
}>()

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const jlao = useJlaoStore()

function isModeLinkLocked(path: string) {
  return isModeSwitchLocked(jlao.activeCaptureMode, jlao.captureStartupMode, route.path, path)
}

function logout() {
  auth.logout()
  router.push('/login')
}
</script>
