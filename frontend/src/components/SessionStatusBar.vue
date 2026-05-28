<template>
  <section class="status-bar">
    <div class="status-left">
      <n-tag :type="statusType" size="large">{{ statusLabel }}</n-tag>
      <div>
        <div class="panel-title">{{ session?.title || 'JLAO 翡翠直播' }}</div>
        <div class="transcript-meta">
          平台：{{ session?.platform || '-' }} · 主播：{{ session?.anchor_name || '-' }} · 场控：{{ session?.operator_name || '-' }}
        </div>
      </div>
    </div>

    <div class="status-right">
      <n-tag :type="connected ? 'success' : 'warning'">
        {{ connected ? '实时连接正常' : '实时连接未建立' }}
      </n-tag>
      <n-tag :type="audioConnected ? 'success' : audioError ? 'error' : 'warning'">
        {{ audioConnected ? '音频已接入' : audioError || '音频未接入' }}
      </n-tag>
      <n-button type="primary" size="small" :disabled="isRunningStatus(session?.status)" @click="$emit('start')">
        <template #icon><play :size="16" /></template>
        开始手机采集
      </n-button>
      <n-button size="small" secondary type="error" :disabled="!isRunningStatus(session?.status)" @click="$emit('stop')">
        <template #icon><square :size="16" /></template>
        停止采集
      </n-button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NButton, NTag } from 'naive-ui'
import { Play, Square } from 'lucide-vue-next'
import type { LiveSession } from '../types'

const props = defineProps<{
  session: LiveSession | null
  connected: boolean
  audioConnected: boolean
  audioError: string
}>()

defineEmits<{
  start: []
  stop: []
}>()

const statusLabel = computed(() => {
  const status = String(props.session?.status || '')
  if (isRunningStatus(status)) return '手机端已载入'
  if (status.includes('结束')) return '已结束'
  return '待载入'
})

const statusType = computed(() => {
  const status = String(props.session?.status || '')
  if (isRunningStatus(status)) return 'success'
  if (status.includes('结束')) return 'default'
  return 'warning'
})

function isRunningStatus(status: unknown) {
  const value = String(status || '')
  return value.includes('直播中') || value.includes('运行')
}
</script>
