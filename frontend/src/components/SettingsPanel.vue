<template>
  <n-modal
    v-model:show="showModal"
    preset="card"
    title="设置"
    style="width: min(760px, 92vw)"
    :mask-closable="false"
  >
    <div class="settings-content">
      <h3 class="settings-section-title">HDMI 采集卡设备</h3>
      <div class="capture-options capture-card-options">
        <div class="option-row device-select-row">
          <span>输入模式</span>
          <n-select
            :value="store.inputMode"
            size="small"
            class="device-select"
            :options="inputModeOptions"
            @update:value="setInputMode"
          />
        </div>
      </div>
      <div class="driver-status">
        <span class="status-label">当前状态：</span>
        <n-tag v-if="captureCardStatus === 'ready'" type="success">
          已检测到视频 {{ captureCardDevices?.video_devices.length || 0 }} 个 / 音频 {{ captureCardDevices?.audio_devices.length || 0 }} 个
        </n-tag>
        <n-tag v-else-if="captureCardLoading" type="info">正在检测</n-tag>
        <n-tag v-else type="warning">未检测到完整采集卡设备</n-tag>
      </div>
      <div class="capture-options capture-card-options">
        <div class="option-row device-select-row">
          <span>视频设备</span>
          <n-select
            :value="selectedVideoDeviceId"
            size="small"
            class="device-select"
            filterable
            clearable
            :loading="captureCardLoading"
            :options="videoDeviceOptions"
            placeholder="未检测到视频设备"
            @update:value="setSelectedVideoDevice"
          />
        </div>
        <div class="option-row device-select-row">
          <span>音频设备</span>
          <n-select
            :value="selectedAudioDeviceId"
            size="small"
            class="device-select"
            filterable
            clearable
            :loading="captureCardLoading"
            :options="audioDeviceOptions"
            placeholder="未检测到音频设备"
            @update:value="setSelectedAudioDevice"
          />
        </div>
        <div class="option-row device-select-row">
          <span>画面方向</span>
          <n-select
            :value="store.captureCardVideoRotation"
            size="small"
            class="device-select"
            :options="captureCardRotationOptions"
            @update:value="setCaptureCardVideoRotation"
          />
        </div>
        <div class="option-row device-select-row">
          <span>左右方向</span>
          <n-select
            :value="store.captureCardVideoMirror ? 'true' : 'false'"
            size="small"
            class="device-select"
            :options="captureCardMirrorOptions"
            @update:value="setCaptureCardVideoMirror"
          />
        </div>
        <p class="option-hint">
          HDMI 模式下，“采集”会由后端打开采集卡视频；STT、OCR、录屏仍需单独启动。
        </p>
        <p v-if="captureCardDevices?.errors.length" class="option-hint error-hint">
          {{ captureCardDevices.errors.join('；') }}
        </p>
        <div class="driver-actions">
          <n-button size="small" secondary :loading="captureCardLoading" @click="refreshCaptureCardDevices">
            <template #icon><refresh-cw :size="14" /></template>
            刷新采集卡设备
          </n-button>
        </div>
      </div>

      <h3 class="settings-section-title">本地 scrcpy 驱动</h3>
      <div class="driver-status">
        <span class="status-label">当前状态：</span>
        <n-tag v-if="drivers.length > 0" type="success">已检测到 {{ drivers.length }} 个驱动</n-tag>
        <n-tag v-else type="warning">未检测到驱动</n-tag>
      </div>

      <div class="driver-list">
        <div
          v-for="driver in drivers"
          :key="driver.path"
          class="driver-item"
          :class="{ active: selectedPath === driver.path }"
          @click="selectDriver(driver)"
        >
          <div class="driver-info">
            <strong>{{ driver.name }}</strong>
            <span class="driver-path">{{ driver.path }}</span>
          </div>
          <n-tag :type="driver.type === 'scrcpy' ? 'info' : 'success'" size="small">
            {{ driver.type === 'scrcpy' ? 'scrcpy' : 'QtScrcpy' }}
          </n-tag>
        </div>
      </div>

      <div class="driver-actions">
        <n-button size="small" secondary :loading="loading" @click="refreshDrivers">
          <template #icon><refresh-cw :size="14" /></template>
          刷新驱动列表
        </n-button>
      </div>

      <div class="manual-path">
        <h4>手动指定路径</h4>
        <n-input
          v-model:value="manualPath"
          placeholder="例如：D:\\scrcpy\\scrcpy.exe"
          size="small"
        />
        <n-button size="small" type="primary" @click="setManualPath">
          使用此路径
        </n-button>
      </div>
      <div class="capture-options">
        <h4>截图/OCR 频率</h4>
        <div class="option-row">
          <span>处理间隔</span>
          <n-select
            :value="store.ocrIntervalMs"
            size="small"
            class="option-select"
            :options="ocrIntervalOptions"
            @update:value="setOcrInterval"
          />
        </div>
      </div>
      <div class="capture-options">
        <h4>视频流检测</h4>
        <div class="option-row">
          <span>断流判定</span>
          <n-select
            :value="store.videoStaleTimeoutMs"
            size="small"
            class="option-select"
            :options="videoStaleTimeoutOptions"
            @update:value="setVideoStaleTimeout"
          />
        </div>
      </div>
      <div class="capture-options">
        <h4>FunASR 运行设备</h4>
        <div class="option-row">
          <span>语音识别设备</span>
          <n-select
            :value="store.sttRuntimeSettings?.local_stt_device || 'cpu'"
            size="small"
            class="option-select"
            :loading="store.sttRuntimeSettingsLoading"
            :options="sttDeviceOptions"
            @update:value="setSttDevice"
          />
          <span>Provider</span>
          <n-select
            :value="store.sttRuntimeSettings?.stt_provider || 'local'"
            size="small"
            class="option-select"
            :loading="store.sttRuntimeSettingsLoading"
            :options="sttProviderOptions"
            @update:value="setSttProvider"
          />
        </div>
        <p class="option-hint">
          {{ store.sttRuntimeSettings?.cuda_available ? 'CUDA 可用，切换后下次启动语音识别生效。' : '当前后端环境未检测到 CUDA，只能使用 CPU。' }}
        </p>
      </div>
      <div class="reset-tools">
        <h4>采集状态重置</h4>
        <p>清理前后端旧状态、残留任务和本项目启动的 scrcpy/audio 进程；不删除日志、样本和录屏文件。</p>
        <div class="reset-actions">
          <n-button size="small" secondary :loading="resetting" @click="softReset">
            软重置
          </n-button>
          <n-button size="small" secondary class="hard-reset-button" :loading="resetting" @click="hardReset">
            硬重置
          </n-button>
        </div>
      </div>
    </div>
  </n-modal>

  <n-button size="small" quaternary @click="openSettings">
    <template #icon><settings :size="16" /></template>
    设置
  </n-button>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { NButton, NModal, NTag, NInput, NSelect } from 'naive-ui'
import { RefreshCw, Settings } from 'lucide-vue-next'
import { useMessage } from 'naive-ui'
import { API_BASE } from '../api/client'
import { getCaptureCardDevices } from '../api/jlao'
import { useJlaoStore } from '../stores/jlao'
import type { CaptureCardDevice, CaptureCardDevicesInfo } from '../types'

interface ScrcpyDriver {
  name: string
  path: string
  type: string
}

const message = useMessage()
const store = useJlaoStore()
const showModal = ref(false)
const drivers = ref<ScrcpyDriver[]>([])
const selectedPath = ref('')
const loading = ref(false)
const resetting = ref(false)
const manualPath = ref('')
const captureCardDevices = ref<CaptureCardDevicesInfo | null>(null)
const captureCardLoading = ref(false)
const selectedVideoDeviceId = ref<string | null>(store.captureCardVideoDeviceId || null)
const selectedAudioDeviceId = ref<string | null>(store.captureCardAudioDeviceId || null)
const inputModeOptions = [
  { label: 'HDMI 采集卡', value: 'capture_card' },
  { label: 'Android scrcpy', value: 'scrcpy' },
]
const captureCardRotationOptions = [
  { label: '正常', value: 0 },
  { label: '旋转 180 度', value: 180 },
]
const captureCardMirrorOptions = [
  { label: '修正镜像', value: 'true' },
  { label: '原始画面', value: 'false' },
]
const ocrIntervalOptions = [
  { label: '1 秒一次', value: 1000 },
  { label: '2 秒一次', value: 2000 },
  { label: '5 秒一次', value: 5000 },
]
const videoStaleTimeoutOptions = [
  { label: '3 秒无新帧', value: 3000 },
  { label: '5 秒无新帧', value: 5000 },
  { label: '10 秒无新帧', value: 10000 },
]
const sttDeviceOptions = computed(() => {
  const options = store.sttRuntimeSettings?.local_stt_device_options || [
    { label: 'CPU', value: 'cpu', available: true },
    { label: 'GPU (CUDA)', value: 'cuda', available: false },
  ]
  return options.map((option) => ({
    label: option.label,
    value: option.value,
    disabled: !option.available,
  }))
})
const sttProviderOptions = computed(() => {
  const options = store.sttRuntimeSettings?.stt_provider_options || [
    { label: '本地 FunASR', value: 'local', available: true },
    { label: '阿里云', value: 'aliyun', available: false },
  ]
  return options.map((option) => ({
    label: option.label,
    value: option.value,
    disabled: !option.available,
  }))
})
const captureCardStatus = computed(() => {
  const devices = captureCardDevices.value
  if (!devices) return 'unknown'
  return devices.video_devices.length > 0 && devices.audio_devices.length > 0 ? 'ready' : 'missing'
})
const videoDeviceOptions = computed(() => (captureCardDevices.value?.video_devices || []).map(captureDeviceOption))
const audioDeviceOptions = computed(() => (captureCardDevices.value?.audio_devices || []).map(captureDeviceOption))

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('jlao_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function refreshCaptureCardDevices() {
  captureCardLoading.value = true
  try {
    captureCardDevices.value = await getCaptureCardDevices()
    autoSelectCaptureCardDevices()
    if (captureCardStatus.value === 'ready') {
      message.success('已检测到采集卡音视频设备')
    } else {
      message.warning('未检测到完整的采集卡视频/音频设备')
    }
  } catch (error: any) {
    console.error('读取采集卡设备失败:', error)
    message.error(error?.response?.data?.detail || error?.message || '读取采集卡设备失败')
  } finally {
    captureCardLoading.value = false
  }
}

function autoSelectCaptureCardDevices() {
  const devices = captureCardDevices.value
  const videoDevices = devices?.video_devices || []
  const audioDevices = devices?.audio_devices || []
  const currentVideo = videoDevices.find((device) => device.id === store.captureCardVideoDeviceId)
  const currentAudio = audioDevices.find((device) => device.id === store.captureCardAudioDeviceId)
  const video = currentVideo || preferredCaptureDevice(videoDevices)
  const audio = currentAudio || preferredCaptureDevice(audioDevices)
  setSelectedVideoDevice(video?.id || null)
  setSelectedAudioDevice(audio?.id || null)
}

function preferredCaptureDevice(devices: CaptureCardDevice[]) {
  return devices.find((device) => device.is_capture_candidate) || devices[0] || null
}

function captureDeviceOption(device: CaptureCardDevice) {
  const suffix = [device.pnp_class, device.status].filter(Boolean).join(' / ')
  return {
    label: suffix ? `${device.name} (${suffix})` : device.name,
    value: device.id,
  }
}

function setInputMode(value: string) {
  store.setInputMode(value)
}

function setSelectedVideoDevice(value: string | null) {
  selectedVideoDeviceId.value = value
  store.setCaptureCardVideoDeviceId(value || '')
}

function setSelectedAudioDevice(value: string | null) {
  selectedAudioDeviceId.value = value
  store.setCaptureCardAudioDeviceId(value || '')
}

function setCaptureCardVideoRotation(value: number) {
  store.setCaptureCardVideoRotation(value)
}

function setCaptureCardVideoMirror(value: string) {
  store.setCaptureCardVideoMirror(value)
}

async function refreshDrivers() {
  loading.value = true
  try {
    const base = API_BASE || ''
    const response = await fetch(`${base}/api/scrcpy/drivers`, {
      headers: getAuthHeaders(),
    })
    if (!response.ok) {
      message.error('读取 scrcpy 驱动失败')
      return
    }

    drivers.value = await response.json() as ScrcpyDriver[]
    autoSelectPreferredDriver()
  } catch (error) {
    console.error('读取 scrcpy 驱动失败:', error)
    message.error('读取 scrcpy 驱动失败')
  } finally {
    loading.value = false
  }
}

function autoSelectPreferredDriver() {
  const preferred = drivers.value.find((d) => d.type === 'scrcpy') || drivers.value[0]
  if (preferred) {
    selectedPath.value = preferred.path
  }
}

async function selectDriver(driver: ScrcpyDriver) {
  const appliedPath = await setDriverPath(driver.path)
  if (appliedPath) {
    selectedPath.value = appliedPath
  }
}

async function setManualPath() {
  if (!manualPath.value.trim()) {
    message.error('请输入路径')
    return
  }
  const appliedPath = await setDriverPath(manualPath.value.trim())
  if (appliedPath) {
    selectedPath.value = appliedPath
    manualPath.value = ''
  }
}

async function setDriverPath(path: string): Promise<string | null> {
  try {
    const base = API_BASE || ''
    const response = await fetch(`${base}/api/scrcpy/drivers/select?path=${encodeURIComponent(path)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
    })
    if (response.ok) {
      const data = await response.json() as { path?: string }
      message.success('已设置 scrcpy 驱动')
      return data.path || path
    }

    const err = await response.json().catch(() => null) as { detail?: string } | null
    message.error('设置 scrcpy 驱动失败: ' + (err?.detail || response.statusText))
  } catch (error) {
    console.error('设置 scrcpy 驱动失败:', error)
    message.error('设置 scrcpy 驱动失败')
  }
  return null
}

function setOcrInterval(value: number) {
  store.setOcrIntervalMs(value)
  message.success('截图/OCR 频率已保存')
}

function setVideoStaleTimeout(value: number) {
  store.setVideoStaleTimeoutMs(value)
  message.success('视频流检测阈值已保存')
}

async function refreshRuntimeSettings() {
  try {
    await store.refreshSttRuntimeSettings()
  } catch (error) {
    console.error('读取 FunASR 设置失败:', error)
    message.error('读取 FunASR 设置失败')
  }
}

async function setSttDevice(value: string) {
  try {
    await store.setSttRuntimeDevice(value)
    message.success('FunASR 运行设备已保存')
  } catch (error: any) {
    message.error(error?.response?.data?.detail || error?.message || 'FunASR 运行设备保存失败')
  }
}

async function setSttProvider(value: string) {
  try {
    await store.setSttRuntimeProvider(value)
    message.success('语音识别服务已保存')
  } catch (error: any) {
    message.error(error?.response?.data?.detail || error?.message || '语音识别服务保存失败')
  }
}

function openSettings() {
  showModal.value = true
  void refreshCaptureCardDevices()
  refreshDrivers()
  void refreshRuntimeSettings()
}

async function softReset() {
  if (!store.currentSession) {
    message.warning('当前没有直播会话')
    return
  }
  resetting.value = true
  try {
    const result = await store.softResetCaptureState()
    message.success(resetSummary(result, '软重置完成'))
  } catch (error: any) {
    message.error(error?.response?.data?.detail || error?.message || '软重置失败')
  } finally {
    resetting.value = false
  }
}

async function hardReset() {
  if (!store.currentSession) {
    message.warning('当前没有直播会话')
    return
  }
  if (!window.confirm('确认执行硬重置？这会停止采集、音频、STT、OCR、录屏，并清理本项目启动的 scrcpy/audio 进程。')) {
    return
  }
  resetting.value = true
  try {
    const result = await store.hardResetCaptureState()
    message.success(resetSummary(result, '硬重置完成'))
  } catch (error: any) {
    message.error(error?.response?.data?.detail || error?.message || '硬重置失败')
  } finally {
    resetting.value = false
  }
}

function resetSummary(result: unknown, fallback: string) {
  const payload = result as {
    cleanup?: Array<{ status?: string; message?: string }>
    adb_status?: { status?: string; device_count?: number; online_count?: number; offline_count?: number }
  } | undefined
  const cleanup = payload?.cleanup || []
  const adbStatus = payload?.adb_status
  const adbText = adbStatus
    ? `，ADB：${adbStatus.status || 'unknown'} / 在线${adbStatus.online_count || 0} / 离线${adbStatus.offline_count || 0}`
    : ''
  if (!cleanup.length) return `${fallback}${adbText}`
  const okCount = cleanup.filter((item) => item.status === 'ok').length
  const errorCount = cleanup.length - okCount
  return errorCount
    ? `${fallback}，${okCount}项完成，${errorCount}项失败${adbText}`
    : `${fallback}，${okCount}项清理完成${adbText}`
}

onMounted(() => {
  void refreshCaptureCardDevices()
  refreshDrivers()
  void refreshRuntimeSettings()
})
</script>

<style scoped>
.settings-content {
  padding: 16px;
}

.settings-section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #f4fffc;
}

.driver-status {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-label {
  color: #8fa3b6;
  font-size: 14px;
}

.driver-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.driver-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
}

.driver-item:hover {
  background: rgba(255, 255, 255, 0.08);
}

.driver-item.active {
  border-color: rgba(34, 211, 166, 0.55);
  background: rgba(34, 211, 166, 0.1);
}

.driver-info {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.driver-info strong {
  color: #f4fffc;
  font-size: 13px;
}

.driver-path {
  color: #8fa3b6;
  font-size: 11px;
  word-break: break-all;
}

.driver-actions {
  margin-bottom: 16px;
}

.manual-path {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 16px;
}

.manual-path h4 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  color: #f4fffc;
}

.manual-path .n-input {
  margin-bottom: 8px;
}

.capture-options {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.capture-options h4 {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 10px;
  color: #f4fffc;
}

.option-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #8fa3b6;
  font-size: 13px;
}

.option-select {
  width: 140px;
}

.capture-card-options {
  margin-bottom: 18px;
}

.device-select-row {
  align-items: center;
  margin-bottom: 8px;
}

.device-select {
  width: min(520px, 100%);
}

.option-hint {
  margin: 8px 0 0;
  color: #8fa3b6;
  font-size: 12px;
  line-height: 1.5;
}

.error-hint {
  color: #ffd08a;
}

.reset-tools {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.reset-tools h4 {
  margin: 0 0 8px;
  color: #f4fffc;
  font-size: 14px;
}

.reset-tools p {
  margin: 0 0 10px;
  color: #8fa3b6;
  font-size: 12px;
  line-height: 1.5;
}

.reset-actions {
  display: flex;
  gap: 8px;
}

.hard-reset-button {
  color: #ffd08a;
  border-color: rgba(245, 158, 11, 0.45);
}
</style>
