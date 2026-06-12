<template>
  <section class="status-bar">
    <div class="status-left">
      <n-tag :type="statusType" size="large">{{ statusLabel }}</n-tag>
      <div>
        <div class="panel-title">{{ statusTitle }}</div>
        <div class="transcript-meta">{{ metaLine }}</div>
      </div>
    </div>

    <div class="resource-toggles">
      <button
        v-for="item in toggleItems"
        :key="item.key"
        type="button"
        :class="[
          'resource-toggle',
          item.className,
          item.active ? 'is-active' : '',
          item.busy ? 'is-busy' : '',
        ]"
        :aria-pressed="item.active"
        :aria-busy="item.busy"
        :data-toggle-state="item.active ? 'locked' : 'released'"
        :disabled="item.disabled"
        @click="item.handler"
      >
        <span v-if="item.busy" class="resource-toggle-spinner" aria-hidden="true"></span>
        <component v-else :is="item.icon" :size="16" />
        <span>{{ item.label }}</span>
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NTag } from 'naive-ui'
import { AudioLines, Cable, CircleDot, Mic, MonitorUp, ScanLine } from 'lucide-vue-next'
import type { LiveSession } from '../types'

const props = defineProps<{
  session: LiveSession | null
  connected: boolean
  audioConnected: boolean
  audioError: string
  mode?: 'own' | 'observe'
  starting?: boolean
  stopping?: boolean
  startDisabled?: boolean
  videoLoading?: boolean
  ocrLoading?: boolean
  ocrRuntimeLoading?: boolean
  nativeAudioLoading?: boolean
  sttLoading?: boolean
  recordingLoading?: boolean
  projectionActive?: boolean
  videoActive?: boolean
  nativeAudioActive?: boolean
  sttActive?: boolean
  ocrActive?: boolean
  recordingActive?: boolean
}>()

const emit = defineEmits<{
  toggleProjection: []
  toggleVideo: []
  toggleAudio: []
  toggleStt: []
  toggleOcr: []
  toggleRecording: []
}>()

const isObservation = computed(() => props.mode === 'observe')
const anyRunning = computed(() => Boolean(
  props.projectionActive ||
  props.videoActive ||
  props.nativeAudioActive ||
  props.sttActive ||
  props.ocrActive ||
  props.recordingActive,
))

const statusLabel = computed(() => {
  if (props.starting) return '启动中'
  if (props.stopping) return '停止中'
  if (props.videoLoading) return '视频接入中'
  if (props.nativeAudioLoading) return '音频接入中'
  if (props.sttLoading || props.ocrLoading) return 'CPU/GPU 初始化中'
  if (props.recordingLoading) return '录屏处理中'
  if (props.recordingActive) return '录屏中'
  if (props.ocrActive) return 'OCR识别中'
  if (props.sttActive) return '语音识别中'
  if (props.videoActive) return '视频已接入'
  if (props.nativeAudioActive) return '音频已接入'
  if (props.projectionActive) return '投屏运行中'
  return anyRunning.value ? '运行中' : '待采集'
})

const statusType = computed(() => {
  if (props.audioError) return 'error'
  if (anyRunning.value || props.connected) return 'success'
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
  const backend = props.connected ? '后端已连接' : '后端未连接'
  const audio = props.nativeAudioActive ? '音频接入' : props.audioError ? props.audioError : '音频未接入'
  if (isObservation.value) return `平台：${platform} · 主播：${anchor} · ${backend} · ${audio}`
  return `平台：${platform} · 主播：${anchor} · 场控：${props.session?.operator_name || '-'} · ${backend} · ${audio}`
})

const allBusy = computed(() => Boolean(
  props.starting ||
  props.stopping ||
  props.videoLoading ||
  props.ocrLoading ||
  props.nativeAudioLoading ||
  props.sttLoading ||
  props.recordingLoading,
))

const toggleItems = computed(() => {
  const projectionActive = Boolean(props.projectionActive)
  const videoActive = Boolean(props.videoActive)
  const nativeAudioActive = Boolean(props.nativeAudioActive)
  const sttActive = Boolean(props.sttActive)
  const ocrActive = Boolean(props.ocrActive)
  const recordingActive = Boolean(props.recordingActive)
  const projectionBusy = Boolean(props.starting || props.stopping)
  const videoBusy = Boolean(props.videoLoading)
  const audioBusy = Boolean(props.nativeAudioLoading)
  const sttBusy = Boolean(props.sttLoading)
  const ocrBusy = Boolean(props.ocrLoading)
  const recordingBusy = Boolean(props.recordingLoading)

  return [
    {
      key: 'projection',
      label: props.starting ? '采集中...' : props.stopping ? '停止中...' : projectionActive ? '停止采集' : '采集',
      icon: Cable,
      className: 'toggle-capture',
      active: projectionActive,
      busy: projectionBusy,
      disabled: projectionBusy || (!projectionActive && Boolean(props.startDisabled)),
      handler: () => emit('toggleProjection'),
    },
    {
      key: 'video',
      label: videoBusy ? '视频接入中...' : videoActive ? '停止视频流' : '接入视频流',
      icon: MonitorUp,
      className: 'toggle-video',
      active: videoActive,
      busy: videoBusy,
      disabled: allBusy.value || (!videoActive && !projectionActive),
      handler: () => emit('toggleVideo'),
    },
    {
      key: 'audio',
      label: audioBusy ? '音频接入中...' : nativeAudioActive ? '停止音频' : '音频接入',
      icon: AudioLines,
      className: 'toggle-audio',
      active: nativeAudioActive,
      busy: audioBusy,
      disabled: allBusy.value,
      handler: () => emit('toggleAudio'),
    },
    {
      key: 'stt',
      label: sttBusy ? 'CPU/GPU 初始化中...' : sttActive ? 'STT处理中' : '语音识别',
      icon: Mic,
      className: 'toggle-stt',
      active: sttActive,
      busy: sttBusy,
      disabled: allBusy.value || (!sttActive && !nativeAudioActive),
      handler: () => emit('toggleStt'),
    },
    {
      key: 'ocr',
      label: ocrBusy ? 'CPU/GPU 初始化中...' : ocrActive ? 'OCR识别中' : '截图/OCR',
      icon: ScanLine,
      className: 'toggle-ocr',
      active: ocrActive,
      busy: ocrBusy,
      disabled: allBusy.value || (!ocrActive && !videoActive),
      handler: () => emit('toggleOcr'),
    },
    {
      key: 'recording',
      label: recordingBusy ? '录屏处理中...' : recordingActive ? '停止录屏' : '录屏',
      icon: CircleDot,
      className: 'toggle-record',
      active: recordingActive,
      busy: recordingBusy,
      disabled: allBusy.value || (!recordingActive && (!videoActive || !nativeAudioActive)),
      handler: () => emit('toggleRecording'),
    },
  ]
})
</script>

<style scoped>
.status-bar {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(0, 2fr);
  align-items: center;
  gap: 12px;
  overflow: visible;
}

.status-left {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.resource-toggles {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  min-width: 0;
  overflow: visible;
}

.resource-toggle {
  --toggle-color: #8fa3b6;
  --toggle-lift: 3px;
  position: relative;
  flex: 0 0 auto;
  min-height: 36px;
  min-width: 112px;
  max-width: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 9px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-top-color: rgba(255, 255, 255, 0.22);
  border-bottom-color: rgba(0, 0, 0, 0.72);
  border-radius: 8px;
  color: #d6e3e8;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.16) 0%, rgba(255, 255, 255, 0.055) 46%, rgba(0, 0, 0, 0.12) 100%),
    color-mix(in srgb, var(--toggle-color) 5%, rgba(255, 255, 255, 0.04));
  font-family: inherit;
  font-size: 11px;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  cursor: pointer;
  box-shadow:
    0 var(--toggle-lift) 0 rgba(0, 0, 0, 0.72),
    0 9px 16px rgba(0, 0, 0, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.24),
    inset 0 -1px 0 rgba(0, 0, 0, 0.22);
  transform: translateY(0);
  transition:
    transform 0.12s ease,
    border-color 0.15s ease,
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease;
}

.resource-toggle::before {
  content: '';
  position: absolute;
  inset: 1px 1px auto;
  height: 45%;
  border-radius: 7px 7px 5px 5px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.18), rgba(255, 255, 255, 0));
  pointer-events: none;
}

.resource-toggle::after {
  content: '';
  position: absolute;
  inset: auto 2px 2px;
  height: 1px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.42);
  pointer-events: none;
}

.resource-toggle > svg,
.resource-toggle > span {
  position: relative;
  z-index: 1;
}

.resource-toggle span:last-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.resource-toggle:hover:not(:disabled) {
  color: #e9fff8;
  border-color: color-mix(in srgb, var(--toggle-color) 55%, transparent);
  border-top-color: rgba(255, 255, 255, 0.28);
  border-bottom-color: rgba(0, 0, 0, 0.74);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.18) 0%, rgba(255, 255, 255, 0.07) 46%, rgba(0, 0, 0, 0.12) 100%),
    color-mix(in srgb, var(--toggle-color) 13%, rgba(255, 255, 255, 0.04));
  box-shadow:
    0 calc(var(--toggle-lift) + 1px) 0 rgba(0, 0, 0, 0.74),
    0 11px 18px rgba(0, 0, 0, 0.26),
    inset 0 1px 0 rgba(255, 255, 255, 0.28),
    inset 0 -1px 0 rgba(0, 0, 0, 0.22);
}

.resource-toggle.is-active {
  --toggle-lift: 1px;
  color: #f6fff9;
  border-color: color-mix(in srgb, var(--toggle-color) 68%, transparent);
  border-top-color: color-mix(in srgb, var(--toggle-color) 35%, rgba(255, 255, 255, 0.1));
  border-bottom-color: color-mix(in srgb, var(--toggle-color) 48%, rgba(0, 0, 0, 0.76));
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--toggle-color) 18%, rgba(0, 0, 0, 0.10)) 0%, color-mix(in srgb, var(--toggle-color) 26%, rgba(0, 0, 0, 0.22)) 100%),
    rgba(255, 255, 255, 0.04);
  box-shadow:
    0 1px 0 rgba(0, 0, 0, 0.72),
    inset 0 2px 10px rgba(0, 0, 0, 0.38),
    inset 0 0 0 1px color-mix(in srgb, var(--toggle-color) 28%, transparent),
    inset 0 -1px 0 color-mix(in srgb, var(--toggle-color) 36%, rgba(255, 255, 255, 0.08));
  transform: translateY(2px);
}

.resource-toggle.is-active:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--toggle-color) 72%, transparent);
  border-top-color: color-mix(in srgb, var(--toggle-color) 28%, rgba(0, 0, 0, 0.18));
  border-bottom-color: color-mix(in srgb, var(--toggle-color) 50%, rgba(0, 0, 0, 0.78));
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--toggle-color) 16%, rgba(0, 0, 0, 0.16)) 0%, color-mix(in srgb, var(--toggle-color) 29%, rgba(0, 0, 0, 0.26)) 100%),
    rgba(255, 255, 255, 0.04);
  box-shadow:
    0 1px 0 rgba(0, 0, 0, 0.72),
    inset 0 2px 11px rgba(0, 0, 0, 0.42),
    inset 0 0 0 1px color-mix(in srgb, var(--toggle-color) 32%, transparent),
    inset 0 -1px 0 color-mix(in srgb, var(--toggle-color) 36%, rgba(255, 255, 255, 0.08));
  transform: translateY(2px);
}

.resource-toggle.is-active::before {
  opacity: 0.35;
  height: 36%;
}

.resource-toggle.is-active::after {
  background: color-mix(in srgb, var(--toggle-color) 54%, rgba(0, 0, 0, 0.4));
}

.resource-toggle:active:not(:disabled) {
  border-top-color: rgba(0, 0, 0, 0.28);
  transform: translateY(3px);
  box-shadow:
    0 0 0 rgba(0, 0, 0, 0),
    inset 0 3px 12px rgba(0, 0, 0, 0.46),
    inset 0 0 0 1px color-mix(in srgb, var(--toggle-color) 36%, rgba(0, 0, 0, 0.2));
}

.resource-toggle.is-active:active:not(:disabled) {
  transform: translateY(3px);
  box-shadow:
    0 0 0 rgba(0, 0, 0, 0),
    inset 0 3px 14px rgba(0, 0, 0, 0.52),
    inset 0 0 0 1px color-mix(in srgb, var(--toggle-color) 40%, rgba(0, 0, 0, 0.2));
}

.resource-toggle:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--toggle-color) 70%, #ffffff);
  outline-offset: 3px;
}

.resource-toggle:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  color: #7f929b;
  box-shadow:
    0 1px 0 rgba(0, 0, 0, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.resource-toggle.is-busy {
  opacity: 0.82;
  color: #f2fffb;
}

.resource-toggle-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid color-mix(in srgb, var(--toggle-color) 32%, rgba(255, 255, 255, 0.28));
  border-top-color: color-mix(in srgb, var(--toggle-color) 82%, #ffffff);
  border-radius: 50%;
  animation: resource-toggle-spin 0.8s linear infinite;
}

@keyframes resource-toggle-spin {
  to {
    transform: rotate(360deg);
  }
}

.toggle-capture {
  --toggle-color: #22c55e;
}

.toggle-video {
  --toggle-color: #38bdf8;
}

.toggle-audio {
  --toggle-color: #2dd4bf;
}

.toggle-stt {
  --toggle-color: #a78bfa;
  min-width: 124px;
}

.toggle-ocr {
  --toggle-color: #f59e0b;
  min-width: 124px;
}

.toggle-record {
  --toggle-color: #ef4444;
  min-width: 112px;
}

@media (max-width: 1100px) {
  .status-bar {
    grid-template-columns: 1fr;
  }

  .resource-toggles {
    justify-content: flex-start;
  }
}
</style>
