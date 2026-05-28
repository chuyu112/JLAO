<script setup lang="ts">
import { ref } from 'vue'
import { NTag } from 'naive-ui'

defineProps<{
  sessionId: string
  captureRunning?: boolean
  captureLoading?: boolean
}>()

const emit = defineEmits<{
  (e: 'start', serial: string): void
  (e: 'stop'): void
  (e: 'start-capture', serial: string): void
  (e: 'stop-capture'): void
}>()

const connected = ref(false)
const error = ref('')

function markStarted() {
  connected.value = true
  error.value = ''
}

function markFailed(messageText: string) {
  connected.value = false
  error.value = messageText
}

function disconnect() {
  connected.value = false
}

defineExpose({
  markStarted,
  markFailed,
  connectWs: markStarted,
  disconnect,
})
</script>

<template>
  <div class="scrcpy-panel">
    <div class="scrcpy-header">
      <span class="scrcpy-title">手机端控制</span>
      <NTag v-if="connected" type="success" size="small">投屏已启动</NTag>
      <NTag v-else type="default" size="small">未投屏</NTag>
    </div>

    <div class="scrcpy-status-grid">
      <div>
        <span class="status-label">实时投屏</span>
        <span>{{ connected ? '运行中' : '随开始手机采集自动尝试' }}</span>
      </div>
      <div>
        <span class="status-label">画面采样</span>
        <span>{{ captureRunning ? '1 秒采集中' : '未采集' }}</span>
      </div>
    </div>
    <div v-if="error" class="scrcpy-error">{{ error }}</div>

    <div class="scrcpy-native-hint">
      <div class="hint-title">当前模式：一个入口启动手机采集</div>
      <div class="hint-text">
        顶部“开始手机采集”会统一启动会话、adb 画面采样、音频输入，并尝试打开实时投屏窗口。
      </div>
    </div>
  </div>
</template>

<style scoped>
.scrcpy-panel {
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}
.scrcpy-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-weight: 600;
  font-size: 14px;
}
.scrcpy-title {
  flex: 1;
}
.scrcpy-error {
  margin-top: 8px;
  color: #d03050;
  font-size: 12px;
}
.scrcpy-status-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  font-size: 12px;
  color: #2f3a4a;
}
.scrcpy-status-grid > div {
  border: 1px solid #e4e9f2;
  border-radius: 6px;
  padding: 8px;
  background: #fbfcfe;
}
.status-label {
  display: block;
  margin-bottom: 4px;
  color: #667085;
}
.scrcpy-native-hint {
  margin-top: 10px;
  padding: 12px;
  border-radius: 6px;
  background: #f7f9fc;
  border: 1px dashed #c8d2e0;
}
.hint-title {
  font-size: 13px;
  font-weight: 600;
  color: #2f3a4a;
}
.hint-text {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: #667085;
}
</style>
