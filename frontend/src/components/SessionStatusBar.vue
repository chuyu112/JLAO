<template>
  <section class="status-bar">
    <div class="status-left">
      <n-tag :type="statusType" size="large">{{ statusLabel }}</n-tag>
      <div>
        <div class="panel-title">{{ statusTitle }}</div>
        <div class="transcript-meta">{{ metaLine }}</div>
      </div>
    </div>

    <div class="status-right">
      <n-tag :type="connected ? 'success' : 'warning'">
        {{ connected ? '实时连接正常' : '实时连接未建立' }}
      </n-tag>
      <n-tag :type="audioConnected ? 'success' : audioError ? 'error' : 'warning'">
        {{ audioConnected ? '音频已接入' : audioError || '音频未接入' }}
      </n-tag>
      <n-button
        type="primary"
        size="small"
        :loading="starting"
        :disabled="startDisabledComputed"
        @click="$emit('start')"
      >
        <template #icon><play :size="16" /></template>
        {{ effectiveStartButtonLabel }}
      </n-button>
      <n-button
        size="small"
        secondary
        type="error"
        :disabled="starting || !captureRunning"
        @click="$emit('stop')"
      >
        <template #icon><square :size="16" /></template>
        {{ stopButtonLabel }}
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
  mode?: 'own' | 'observe'
  starting?: boolean
  startDisabled?: boolean
  captureActive?: boolean
  sourceActive?: boolean
}>()

defineEmits<{
  start: []
  stop: []
}>()

const isObservation = computed(() => props.mode === 'observe')
const sourceRunning = computed(() => Boolean(props.sourceActive))
const videoActive = computed(() => Boolean(props.captureActive))
const needsVideoSource = computed(() => sourceRunning.value && !videoActive.value)
const captureRunning = computed(() => sourceRunning.value || videoActive.value)
const startDisabledComputed = computed(() => Boolean(props.startDisabled) || captureRunning.value)

const statusLabel = computed(() => {
  const status = String(props.session?.status || '')
  if (props.starting) return '采集启动中'
  if (videoActive.value) return '采集中'
  if (needsVideoSource.value) return '待接入视频流'
  if (status.includes('结束')) return '已结束'
  return '待采集'
})

const statusType = computed(() => {
  const status = String(props.session?.status || '')
  if (props.starting || videoActive.value) return 'success'
  if (needsVideoSource.value) return 'warning'
  if (status.includes('结束')) return 'default'
  return 'warning'
})

const statusTitle = computed(() => {
  if (props.session?.live_room_name) return props.session.live_room_name
  if (props.session?.title) return props.session.title
  return isObservation.value ? '其它直播间分析' : 'JLAO 翡翠直播'
})

const metaLine = computed(() => {
  const platform = props.session?.platform || '-'
  const anchor = props.session?.anchor_name || '-'
  if (isObservation.value) return `平台：${platform} · 主播：${anchor} · 黑盒观察`
  return `平台：${platform} · 主播：${anchor} · 场控：${props.session?.operator_name || '-'}`
})

const startButtonLabel = computed(() => '采集')
const effectiveStartButtonLabel = computed(() => (props.starting ? '启动中' : startButtonLabel.value))
const stopButtonLabel = computed(() => '停止采集')
</script>
