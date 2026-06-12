<template>
  <main class="page live-dashboard-page">
    <app-top-nav title="自有直播间运营" subtitle="手机投屏 · 实时转写 · 运营数据墙" />

    <div class="dashboard one-screen-dashboard">
      <!-- 平台选择 -->
      <div class="platform-selector">
        <span class="platform-label">直播平台：</span>
        <n-select
          v-model:value="selectedPlatform"
          :options="platformOptions"
          size="small"
          style="width: 160px"
          @update:value="handlePlatformChange"
        />
        <n-tag v-if="selectedPlatform === '视频号'" type="success" size="small">
          {{ store.liveRoomNameLabel }}
        </n-tag>
      </div>

      <section class="main-grid ops-screen-grid">
        <section class="projection-stage yolo-projection-stage">
          <jade-yolo-live-panel
            ref="yoloLivePanel"
            :session-id="store.currentSession?.id || null"
            :input-mode="store.inputMode"
            :video-rotation="store.captureCardVideoRotation"
            :video-mirror="store.captureCardVideoMirror"
            :backend-stream-url="ownBackendStreamUrl"
            :backend-frame-count="store.captureCardInfo?.frame_count || 0"
            :backend-signal-present="store.captureCardInfo?.signal_present"
            :source-active="ownSourceActive"
            :source-blocked="store.isCaptureModeBlocked('own')"
            :stale-timeout-ms="store.videoStaleTimeoutMs"
            @capture-state-change="handleYoloCaptureStateChange"
            @capture-frame="store.uploadCaptureFrame"
            @capture-backend-frame="store.uploadCaptureCardFrame"
            @recording-blob="handleDetachedRecordingBlob"
          />
        </section>

        <div class="audio-capture-agent" aria-hidden="true">
          <live-source-panel
            :live-url="store.currentSession?.live_url || null"
            :stt-connected="store.sttConnected"
            :stt-error="store.sttError"
            :latest-frame="store.frames[0] || null"
            :frame-analyzing="store.frameAnalyzing"
            :session-id="store.currentSession?.id || null"
            :manual-product-name="store.currentSession?.manual_product_name || ''"
            @update="store.updateLiveUrl"
            @capture-frame="store.uploadCaptureFrame"
          />
        </div>

        <div class="ops-data-wall">
          <session-status-bar
            :session="store.currentSession"
            :connected="store.connected"
            :audio-connected="Boolean(store.nativeAudioInfo?.running)"
            :audio-error="store.nativeAudioInfo?.last_error || store.sttError || store.nativeSttInfo?.last_error || ''"
            :starting="store.captureStartupMode === 'own' || store.captureCardLoading"
            :stopping="ownProjectionStopping"
            :start-disabled="store.isCaptureModeBlocked('own')"
            :video-loading="ownVideoLoading"
            :ocr-loading="ownOcrLoading"
            :ocr-runtime-loading="store.frameAnalyzing"
            :native-audio-loading="store.nativeAudioLoading"
            :stt-loading="store.nativeSttLoading"
            :recording-loading="store.recorderLoading"
            :projection-active="ownProjectionActive"
            :video-active="ownVideoCaptureActive"
            :native-audio-active="Boolean(store.nativeAudioInfo?.running)"
            :stt-active="Boolean(store.nativeSttInfo?.running)"
            :ocr-active="ownOcrActive"
            :recording-active="ownRecordingActive"
            @toggle-projection="toggleProjection"
            @toggle-video="toggleVideo"
            @toggle-audio="toggleAudio"
            @toggle-stt="toggleStt"
            @toggle-ocr="toggleOcr"
            @toggle-recording="toggleRecording"
          />

          <transcript-panel
            id="transcript"
            class="data-panel data-panel-transcript"
            :transcripts="store.transcripts"
            :partial-transcript="store.partialTranscript"
            :comment-events="store.liveComments"
          />
          <knowledge-panel id="wiki-knowledge" class="data-panel" :hits="store.wikiHits" :total="store.wikiChunks.length" />
          <virtual-customer-panel
            id="customers"
            class="data-panel"
            :customers="store.virtualCustomers"
            :events="store.customerEvents"
          />
          <jade-knowledge-prompt-panel
            id="knowledge"
            class="data-panel"
            :product="store.currentProduct"
            :detected-name="store.currentSession?.detected_full_name || store.currentSession?.manual_product_name || ''"
          />
          <agent-utterance-panel
            id="operations"
            class="data-panel"
            :agents="store.agents"
            :utterances="store.agentUtterances"
          />
          <product-library-panel
            id="products"
            class="data-panel"
            :products="store.products"
            :current-product-id="store.currentSession?.current_product_id || null"
            :detected-name="store.currentSession?.detected_full_name || ''"
            @select-product="store.selectProduct"
            @product-annotated="handleProductAnnotated"
          />
          <frame-gallery-panel id="frames" class="data-panel" :frames="store.frames" />
        </div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import AgentUtterancePanel from '../components/AgentUtterancePanel.vue'
import AppTopNav from '../components/AppTopNav.vue'
import FrameGalleryPanel from '../components/FrameGalleryPanel.vue'
import JadeKnowledgePromptPanel from '../components/JadeKnowledgePromptPanel.vue'
import JadeYoloLivePanel from '../components/JadeYoloLivePanel.vue'
import KnowledgePanel from '../components/KnowledgePanel.vue'
import LiveSourcePanel from '../components/LiveSourcePanel.vue'
import ProductLibraryPanel from '../components/ProductLibraryPanel.vue'
import SessionStatusBar from '../components/SessionStatusBar.vue'
import TranscriptPanel from '../components/TranscriptPanel.vue'
import VirtualCustomerPanel from '../components/VirtualCustomerPanel.vue'
import { useJlaoStore } from '../stores/jlao'
import type { Product } from '../types'

const store = useJlaoStore()
const message = useMessage()
const yoloLivePanel = ref<InstanceType<typeof JadeYoloLivePanel> | null>(null)
const ownVideoCaptureActive = ref(false)
const ownOcrActive = ref(false)
const ownRecordingActive = ref(false)
const ownProjectionStopping = ref(false)
const ownVideoLoading = ref(false)
const ownOcrLoading = ref(false)
const ownStoppingVideo = ref(false)
const ownSuppressDetachedRecording = ref(false)
const ownHandlingAudioStop = ref(false)
const ownCaptureCardPollTimer = ref<number | null>(null)
const usingCaptureCard = computed(() => store.inputMode === 'capture_card')
const ownProjectionActive = computed(() => (
  usingCaptureCard.value ? Boolean(store.captureCardInfo?.running) : Boolean(store.scrcpyInfo?.running)
))
const ownSourceActive = computed(
  () => store.activeCaptureMode === 'own' || ownProjectionActive.value,
)
const ownBackendStreamUrl = computed(() => (usingCaptureCard.value ? store.getCaptureCardStreamUrl() : ''))

// 平台选择
const selectedPlatform = ref('抖音')
const platformOptions = [
  { label: '抖音', value: '抖音' },
  { label: '视频号', value: '视频号' },
  { label: '快手', value: '快手' },
  { label: '淘宝', value: '淘宝' },
]

onMounted(async () => {
  await store.initDemo(selectedPlatform.value)
  await store.refreshSessionData()
  await store.refreshCaptureStatus()
  if (usingCaptureCard.value && ownProjectionActive.value) startCaptureCardStatusPolling()
})

onBeforeUnmount(() => {
  stopCaptureCardStatusPolling()
})

watch(
  () => store.captureResetToken,
  () => {
    resetLocalCaptureState(true)
  },
)

watch(
  () => store.captureStatusInfo?.resources.browser_video_stream.running,
  (running) => {
    if (running === false && ownVideoCaptureActive.value) {
      resetLocalCaptureState(true)
    }
  },
)

watch(
  () => store.captureStatusInfo?.resources.ocr_capture.running,
  (running) => {
    if (running === false && ownOcrActive.value) {
      yoloLivePanel.value?.stopOcr()
      ownOcrActive.value = false
    }
  },
)

watch(
  () => store.captureStatusInfo?.resources.recorder.running,
  (running) => {
    if (running === false && ownRecordingActive.value) {
      ownSuppressDetachedRecording.value = true
      void yoloLivePanel.value?.stopRecording()
      ownRecordingActive.value = false
      window.setTimeout(() => {
        ownSuppressDetachedRecording.value = false
      }, 3000)
    }
  },
)

watch(
  () => store.nativeAudioInfo?.running,
  (running, previous) => {
    if (previous === true && running === false) {
      void handleNativeAudioStopped()
    }
  },
)

function resetLocalCaptureState(suppressRecording: boolean) {
  const wasRecording = ownRecordingActive.value
  ownSuppressDetachedRecording.value = suppressRecording && wasRecording
  yoloLivePanel.value?.stopCapture()
  ownVideoCaptureActive.value = false
  ownOcrActive.value = false
  ownRecordingActive.value = false
  ownProjectionStopping.value = false
  ownVideoLoading.value = false
  ownOcrLoading.value = false
  if (ownSuppressDetachedRecording.value) {
    window.setTimeout(() => {
      ownSuppressDetachedRecording.value = false
    }, 3000)
  }
}

function startCaptureCardStatusPolling() {
  stopCaptureCardStatusPolling()
  ownCaptureCardPollTimer.value = window.setInterval(() => {
    if (usingCaptureCard.value && ownProjectionActive.value) {
      void store.refreshCaptureCardStatus()
    }
  }, 1500)
}

function stopCaptureCardStatusPolling() {
  if (ownCaptureCardPollTimer.value) {
    clearInterval(ownCaptureCardPollTimer.value)
    ownCaptureCardPollTimer.value = null
  }
}

async function handleNativeAudioStopped() {
  if (ownHandlingAudioStop.value) return
  if (!store.nativeSttInfo?.running && !ownRecordingActive.value) return
  ownHandlingAudioStop.value = true
  try {
    if (store.nativeSttInfo?.running) {
      await store.stopNativeSttSession().catch(() => undefined)
      message.warning('音频接入已断开，语音识别已停止')
    }
    if (ownRecordingActive.value) {
      const blob = await yoloLivePanel.value?.stopRecording()
      ownRecordingActive.value = false
      if (blob) {
        await store.finishRecorderSession(blob)
        message.warning('音频接入已断开，录屏已按当前片段结束')
      } else {
        await store.abortRecorderSession()
      }
    }
    await store.refreshCaptureStatus()
  } finally {
    ownHandlingAudioStop.value = false
  }
}

async function handlePlatformChange(platform: string) {
  selectedPlatform.value = platform
  // 重新创建会话
  await store.initDemo(platform)
  message.success(`已切换到 ${platform} 平台`)
}

async function toggleProjection() {
  if (ownProjectionActive.value) {
    if (ownVideoCaptureActive.value || store.nativeAudioInfo?.running || store.nativeSttInfo?.running || ownOcrActive.value || ownRecordingActive.value) {
      message.error('请先停止视频流、音频、语音识别、截图/OCR和录屏')
      return
    }
    ownProjectionStopping.value = true
    try {
      if (usingCaptureCard.value) {
        await store.stopCaptureCardSession()
        stopCaptureCardStatusPolling()
      } else {
        await store.stopScrcpySession()
      }
      await store.stop()
      store.clearCaptureMode('own')
      message.info('采集已停止')
    } finally {
      ownProjectionStopping.value = false
    }
    return
  }

  if (!store.beginCaptureStartup('own')) {
    message.warning('其它分析正在启动或运行，请先停止后再切换')
    return
  }
  try {
    await store.start()
    if (usingCaptureCard.value) {
      await store.startCaptureCardSession()
      await store.refreshCaptureCardStatus()
      startCaptureCardStatusPolling()
    } else {
      await store.startScrcpySession()
      await store.refreshScrcpyStatus()
    }
    if (ownProjectionActive.value) {
      message.success(usingCaptureCard.value ? '采集卡输入已启动，请接入视频流' : '采集已启动，请接入视频流')
    } else {
      message.error(store.captureCardInfo?.last_error || store.scrcpyInfo?.last_error || '采集启动失败')
      store.clearCaptureMode('own')
    }
  } catch (error: any) {
    store.clearCaptureMode('own')
    message.error(error?.response?.data?.detail || error?.message || '采集启动失败')
  } finally {
    store.finishCaptureStartup('own')
  }
}

async function toggleVideo() {
  if (ownVideoCaptureActive.value) {
    if (ownOcrActive.value || ownRecordingActive.value) {
      message.error('请先停止截图/OCR和录屏')
      return
    }
    ownStoppingVideo.value = true
    ownVideoLoading.value = true
    try {
      yoloLivePanel.value?.stopCapture()
      ownVideoCaptureActive.value = false
      await store.markBrowserVideoStream(false)
    } finally {
      ownStoppingVideo.value = false
      ownVideoLoading.value = false
    }
    return
  }
  if (!ownProjectionActive.value) {
    message.error(usingCaptureCard.value ? '请先打开采集卡输入' : '请先启动采集投屏')
    return
  }
  ownVideoLoading.value = true
  try {
    const captured = await yoloLivePanel.value?.startCapture()
    if (captured) {
      ownVideoCaptureActive.value = true
      await store.markBrowserVideoStream(true, { source: usingCaptureCard.value ? 'capture_card' : 'browser_display' })
      message.success('视频流已接入')
    }
  } finally {
    ownVideoLoading.value = false
  }
}

async function toggleAudio() {
  if (store.nativeAudioInfo?.running) {
    if (store.nativeSttInfo?.running || ownRecordingActive.value) {
      message.error('请先停止语音识别和录屏')
      return
    }
    try {
      await store.stopNativeAudioSession()
      message.info('音频接入已停止')
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || '停止音频接入失败')
    }
    return
  }
  try {
    await store.startNativeAudioSession('', usingCaptureCard.value ? {
      source: 'capture_card',
      device_id: store.captureCardAudioDeviceId,
    } : {})
    message.success('音频接入已启动')
  } catch (error: any) {
    message.error(error?.response?.data?.detail || error?.message || '音频接入失败')
  }
}

async function toggleStt() {
  if (store.nativeSttInfo?.running) {
    await store.stopNativeSttSession()
    message.info('语音识别已停止')
    return
  }
  if (!store.nativeAudioInfo?.running) {
    message.error('请先打开音频接入')
    return
  }
  try {
    await store.startNativeSttSession()
    message.success('语音识别已启动')
  } catch (error: any) {
    message.error(error?.response?.data?.detail || store.sttError || error?.message || '语音识别启动失败')
  }
}

async function toggleOcr() {
  if (ownOcrActive.value) {
    ownOcrLoading.value = true
    try {
      yoloLivePanel.value?.stopOcr()
      ownOcrActive.value = false
      await store.markOcrCapture(false)
    } finally {
      ownOcrLoading.value = false
    }
    return
  }
  if (!ownVideoCaptureActive.value) {
    message.error('请先接入视频流')
    return
  }
  const intervalMs = store.ocrIntervalMs
  ownOcrLoading.value = true
  try {
    const started = yoloLivePanel.value?.startOcr(intervalMs)
    if (started) {
      ownOcrActive.value = true
      await store.markOcrCapture(true, { interval_ms: intervalMs })
      message.success('截图/OCR已启动')
    }
  } finally {
    ownOcrLoading.value = false
  }
}

async function toggleRecording() {
  if (ownRecordingActive.value) {
    const blob = await yoloLivePanel.value?.stopRecording()
    ownRecordingActive.value = false
    if (!blob) {
      message.error('录屏视频为空')
      return
    }
    try {
      await store.finishRecorderSession(blob)
      message.success(store.recorderInfo?.output_path ? '录屏已保存为 MP4' : '录屏已停止')
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || '录屏停止失败')
    }
    return
  }
  if (!ownVideoCaptureActive.value) {
    message.error('请先接入视频流')
    return
  }
  if (!store.nativeAudioInfo?.running) {
    message.error('请先打开音频接入')
    return
  }
  try {
    await store.startRecorderSession()
    const started = yoloLivePanel.value?.startRecording()
    if (!started) {
      await store.abortRecorderSession()
      ownRecordingActive.value = false
      message.error('浏览器录屏启动失败')
      return
    }
    ownRecordingActive.value = true
    message.success('录屏已启动')
  } catch (error: any) {
    await store.abortRecorderSession()
    ownRecordingActive.value = false
    message.error(error?.response?.data?.detail || error?.message || '录屏启动失败')
  }
}

async function handleStart() {
  await toggleProjection()
}

async function handleStop() {
  await toggleProjection()
}

function handleYoloCaptureStateChange(active: boolean) {
  ownVideoCaptureActive.value = active
  if (!active) {
    ownOcrActive.value = false
    ownRecordingActive.value = false
    const error = ownStoppingVideo.value ? '' : '视频流已断开'
    void store.markBrowserVideoStream(false, {}, error)
    void store.markOcrCapture(false, {}, error)
  }
}

async function handleDetachedRecordingBlob(blob: Blob | null) {
  ownRecordingActive.value = false
  if (ownSuppressDetachedRecording.value) {
    ownSuppressDetachedRecording.value = false
    return
  }
  if (!blob) {
    await store.abortRecorderSession()
    return
  }
  try {
    await store.finishRecorderSession(blob)
    message.warning('视频流断开，录屏已按当前片段结束')
  } catch (error: any) {
    message.error(error?.response?.data?.detail || error?.message || '录屏异常结束失败')
  }
}

function handleProductAnnotated(product: Product) {
  store.products = [product, ...store.products.filter((item) => item.id !== product.id)]
  message.success('商品人工标注已保存')
}
</script>

<style scoped>
.platform-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.04);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.platform-label {
  color: #8fa3b6;
  font-size: 13px;
}

.yolo-projection-stage {
  height: min(900px, calc(100vh - 100px));
  min-height: 600px;
  aspect-ratio: auto;
}
</style>
