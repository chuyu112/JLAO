<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NButton, NInput, NSpace, NTag } from 'naive-ui'

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

const defaultSerial = '3AF9K24227080668'
const serial = ref(defaultSerial)
const connecting = ref(false)
const connected = ref(false)
const error = ref('')

onMounted(() => {
  const saved = localStorage.getItem('jlao-scrcpy-serial')
  serial.value = saved || defaultSerial
})

function currentSerial() {
  const deviceSerial = serial.value.trim()
  localStorage.setItem('jlao-scrcpy-serial', deviceSerial)
  return deviceSerial
}

function handleStart() {
  error.value = ''
  connecting.value = true
  emit('start', currentSerial())
}

function handleStop() {
  connected.value = false
  connecting.value = false
  emit('stop')
}

function handleStartCapture() {
  emit('start-capture', currentSerial())
}

function markStarted() {
  connected.value = true
  connecting.value = false
  error.value = ''
}

function markFailed(messageText: string) {
  connected.value = false
  connecting.value = false
  error.value = messageText
}

function disconnect() {
  connected.value = false
  connecting.value = false
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
      <NTag v-else-if="connecting" type="warning" size="small">启动中</NTag>
      <NTag v-else type="default" size="small">未投屏</NTag>
    </div>

    <NSpace vertical size="small">
      <NInput
        v-model:value="serial"
        placeholder="设备序列号，可留空使用默认设备"
        :disabled="connected || connecting || captureRunning"
        size="small"
      />
      <NSpace>
        <NButton v-if="!connected" type="primary" size="small" :loading="connecting" @click="handleStart">
          启动投屏窗口
        </NButton>
        <NButton v-else type="error" size="small" @click="handleStop">
          关闭投屏
        </NButton>
        <NButton
          v-if="!captureRunning"
          size="small"
          type="success"
          :loading="captureLoading"
          @click="handleStartCapture"
        >
          开始 1秒截屏
        </NButton>
        <NButton v-else size="small" type="warning" :loading="captureLoading" @click="$emit('stop-capture')">
          停止截屏
        </NButton>
      </NSpace>
      <div v-if="error" class="scrcpy-error">{{ error }}</div>
    </NSpace>

    <div class="scrcpy-native-hint">
      <div class="hint-title">当前模式：scrcpy 原生窗口 + adb 1FPS 截屏</div>
      <div class="hint-text">
        投屏窗口负责实时操作手机；1 秒截屏会把手机画面同步到左侧手机屏区域，并进入截图识别链路。
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
  color: #d03050;
  font-size: 12px;
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
