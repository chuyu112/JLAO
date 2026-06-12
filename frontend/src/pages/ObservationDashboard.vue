<template>
  <main class="page observation-dashboard-page">
    <app-top-nav title="其它直播间分析" subtitle="黑盒观察 · 成交卡片 · 弹幕累积" />

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

      <section class="main-grid ops-screen-grid observation-screen-grid">
        <section class="projection-stage observation-projection-stage observation-yolo-stage">
          <jade-yolo-live-panel
            ref="yoloLivePanel"
            :session-id="store.currentSession?.id || null"
            :input-mode="store.inputMode"
            :video-rotation="store.captureCardVideoRotation"
            :video-mirror="store.captureCardVideoMirror"
            :backend-stream-url="observeBackendStreamUrl"
            :backend-frame-count="store.captureCardInfo?.frame_count || 0"
            :backend-signal-present="store.captureCardInfo?.signal_present"
            :source-active="observeSourceActive"
            :source-blocked="store.isCaptureModeBlocked('observe')"
            :stale-timeout-ms="store.videoStaleTimeoutMs"
            @capture-state-change="handleYoloCaptureStateChange"
            @capture-frame="store.uploadCaptureFrame"
            @capture-backend-frame="store.uploadCaptureCardFrame"
            @recording-blob="handleDetachedRecordingBlob"
          />
        </section>

        <div class="ops-data-wall observation-data-wall">
          <session-status-bar
            mode="observe"
            :session="store.currentSession"
            :connected="store.connected"
            :audio-connected="Boolean(store.nativeAudioInfo?.running)"
            :audio-error="store.nativeAudioInfo?.last_error || store.sttError || store.nativeSttInfo?.last_error || ''"
            :starting="store.captureStartupMode === 'observe' || store.captureCardLoading"
            :stopping="observeProjectionStopping"
            :start-disabled="store.isCaptureModeBlocked('observe')"
            :video-loading="observeVideoLoading"
            :ocr-loading="observeOcrLoading"
            :ocr-runtime-loading="store.frameAnalyzing"
            :native-audio-loading="store.nativeAudioLoading"
            :stt-loading="store.nativeSttLoading"
            :recording-loading="store.recorderLoading"
            :projection-active="observeProjectionActive"
            :video-active="observeCaptureActive"
            :native-audio-active="Boolean(store.nativeAudioInfo?.running)"
            :stt-active="Boolean(store.nativeSttInfo?.running)"
            :ocr-active="observeOcrActive"
            :recording-active="observeRecordingActive"
            @toggle-projection="toggleProjection"
            @toggle-video="toggleVideo"
            @toggle-audio="toggleAudio"
            @toggle-stt="toggleStt"
            @toggle-ocr="toggleOcr"
            @toggle-recording="toggleRecording"
          />

          <transcript-panel
            id="observation-transcript"
            class="data-panel data-panel-transcript"
            :transcripts="store.transcripts"
            :partial-transcript="store.partialTranscript"
            :comment-events="store.liveComments"
          />

          <section id="sale-cards" class="panel data-panel sale-card-panel">
            <header class="panel-header">
              <div>
                <div class="panel-title">成交卡片</div>
                <div class="transcript-meta">截图证据优先，字段先按卖家、买家、货品、价格落库</div>
              </div>
              <n-tag size="small" type="warning">待识别</n-tag>
            </header>
            <div class="panel-body sale-card-body">
              <div class="sale-card-fields">
                <n-tag size="small">卖家</n-tag>
                <n-tag size="small">买家</n-tag>
                <n-tag size="small">货品</n-tag>
                <n-tag size="small">价格</n-tag>
              </div>
              <div class="sale-card-empty">
                <strong>等待主播截图写卡片</strong>
                <span>识别到成交卡片后，会把卖家、买家、货品、价格和截图证据归到本场直播。</span>
              </div>
            </div>
          </section>

          <jade-knowledge-prompt-panel
            id="observation-jade-knowledge"
            class="data-panel"
            :product="store.currentProduct"
            :detected-name="store.currentSession?.detected_full_name || store.currentSession?.manual_product_name || ''"
          />

          <frame-gallery-panel id="observation-frames" class="data-panel" :frames="store.frames" />

          <section id="customer-leads" class="panel data-panel customer-leads-panel">
            <header class="panel-header">
              <div>
                <div class="panel-title">客户线索</div>
                <div class="transcript-meta">直播间互动用户</div>
              </div>
              <n-tag size="small" type="info">{{ store.liveComments?.length || 0 }} 条弹幕</n-tag>
            </header>
            <div class="panel-body customer-leads-body">
              <div v-if="!store.liveComments?.length" class="customer-leads-empty">
                <strong>暂无客户线索</strong>
                <span>等待观众互动后显示</span>
              </div>
              <div v-else class="customer-leads-list">
                <div
                  v-for="comment in uniqueCustomers"
                  :key="comment.id"
                  class="customer-lead-item"
                >
                  <div class="lead-avatar">
                    {{ comment.customer_nickname?.charAt(0) || '?' }}
                  </div>
                  <div class="lead-info">
                    <strong>{{ comment.customer_nickname }}</strong>
                    <span>{{ comment.content }}</span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <product-library-panel
            id="observation-products"
            class="data-panel"
            :products="store.products"
            :current-product-id="store.currentSession?.current_product_id || null"
            :detected-name="store.currentSession?.detected_full_name || ''"
            @select-product="store.selectProduct"
          />

          <section id="replay-outline" class="panel data-panel review-outline-panel">
            <header class="panel-header">
              <div>
                <div class="panel-title">复盘骨架</div>
                <div class="transcript-meta">一场直播结束后按证据生成复盘报告</div>
              </div>
              <n-button size="small" secondary :disabled="!store.currentSession" @click="handleGenerateReplay">
                <template #icon><file-text :size="16" /></template>
                生成报告
              </n-button>
            </header>
            <div class="panel-body review-outline-body">
              <div class="review-outline-item">
                <strong>讲了多少件货</strong>
                <span>按讲解片段、画面变化和货品识别合并。</span>
              </div>
              <div class="review-outline-item">
                <strong>哪些货卖了</strong>
                <span>以成交卡片和截图证据作为确认来源。</span>
              </div>
              <div class="review-outline-item">
                <strong>卖给谁</strong>
                <span>关联买家昵称、成交截图和弹幕上下文。</span>
              </div>
              <div class="review-outline-item">
                <strong>每个客人发言累计</strong>
                <span>按直播间、场次、客人维度累积互动记录。</span>
              </div>
            </div>
          </section>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { NButton, NTag, useMessage } from 'naive-ui'
import { FileText } from 'lucide-vue-next'
import AppTopNav from '../components/AppTopNav.vue'
import FrameGalleryPanel from '../components/FrameGalleryPanel.vue'
import JadeKnowledgePromptPanel from '../components/JadeKnowledgePromptPanel.vue'
import JadeYoloLivePanel from '../components/JadeYoloLivePanel.vue'
import ProductLibraryPanel from '../components/ProductLibraryPanel.vue'
import SessionStatusBar from '../components/SessionStatusBar.vue'
import TranscriptPanel from '../components/TranscriptPanel.vue'
import { useJlaoStore } from '../stores/jlao'

const store = useJlaoStore()
const message = useMessage()
const yoloLivePanel = ref<InstanceType<typeof JadeYoloLivePanel> | null>(null)
const observeCaptureActive = ref(false)
const observeOcrActive = ref(false)
const observeRecordingActive = ref(false)
const observeProjectionStopping = ref(false)
const observeVideoLoading = ref(false)
const observeOcrLoading = ref(false)
const observeStoppingVideo = ref(false)
const observeSuppressDetachedRecording = ref(false)
const observeHandlingAudioStop = ref(false)
const observeCaptureCardPollTimer = ref<number | null>(null)
const usingCaptureCard = computed(() => store.inputMode === 'capture_card')
const observeProjectionActive = computed(() => (
  usingCaptureCard.value ? Boolean(store.captureCardInfo?.running) : Boolean(store.scrcpyInfo?.running)
))
const observeSourceActive = computed(
  () => store.activeCaptureMode === 'observe' || observeProjectionActive.value,
)
const observeBackendStreamUrl = computed(() => (usingCaptureCard.value ? store.getCaptureCardStreamUrl() : ''))

// 去重后的客户列表
const uniqueCustomers = computed(() => {
  const seen = new Set<string>()
  return (store.liveComments || []).filter((comment) => {
    if (seen.has(comment.customer_nickname)) return false
    seen.add(comment.customer_nickname)
    return true
  }).slice(0, 20)
})

// 平台选择
const selectedPlatform = ref('视频号')
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
  if (usingCaptureCard.value && observeProjectionActive.value) startCaptureCardStatusPolling()
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
    if (running === false && observeCaptureActive.value) {
      resetLocalCaptureState(true)
    }
  },
)

watch(
  () => store.captureStatusInfo?.resources.ocr_capture.running,
  (running) => {
    if (running === false && observeOcrActive.value) {
      yoloLivePanel.value?.stopOcr()
      observeOcrActive.value = false
    }
  },
)

watch(
  () => store.captureStatusInfo?.resources.recorder.running,
  (running) => {
    if (running === false && observeRecordingActive.value) {
      observeSuppressDetachedRecording.value = true
      void yoloLivePanel.value?.stopRecording()
      observeRecordingActive.value = false
      window.setTimeout(() => {
        observeSuppressDetachedRecording.value = false
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
  const wasRecording = observeRecordingActive.value
  observeSuppressDetachedRecording.value = suppressRecording && wasRecording
  yoloLivePanel.value?.stopCapture()
  observeCaptureActive.value = false
  observeOcrActive.value = false
  observeRecordingActive.value = false
  observeProjectionStopping.value = false
  observeVideoLoading.value = false
  observeOcrLoading.value = false
  if (observeSuppressDetachedRecording.value) {
    window.setTimeout(() => {
      observeSuppressDetachedRecording.value = false
    }, 3000)
  }
}

function startCaptureCardStatusPolling() {
  stopCaptureCardStatusPolling()
  observeCaptureCardPollTimer.value = window.setInterval(() => {
    if (usingCaptureCard.value && observeProjectionActive.value) {
      void store.refreshCaptureCardStatus()
    }
  }, 1500)
}

function stopCaptureCardStatusPolling() {
  if (observeCaptureCardPollTimer.value) {
    clearInterval(observeCaptureCardPollTimer.value)
    observeCaptureCardPollTimer.value = null
  }
}

async function handleNativeAudioStopped() {
  if (observeHandlingAudioStop.value) return
  if (!store.nativeSttInfo?.running && !observeRecordingActive.value) return
  observeHandlingAudioStop.value = true
  try {
    if (store.nativeSttInfo?.running) {
      await store.stopNativeSttSession().catch(() => undefined)
      message.warning('音频接入已断开，语音识别已停止')
    }
    if (observeRecordingActive.value) {
      const blob = await yoloLivePanel.value?.stopRecording()
      observeRecordingActive.value = false
      if (blob) {
        await store.finishRecorderSession(blob)
        message.warning('音频接入已断开，录屏已按当前片段结束')
      } else {
        await store.abortRecorderSession()
      }
    }
    await store.refreshCaptureStatus()
  } finally {
    observeHandlingAudioStop.value = false
  }
}

async function handlePlatformChange(platform: string) {
  selectedPlatform.value = platform
  // 重新创建会话
  await store.initDemo(platform)
  message.success(`已切换到 ${platform} 平台`)
}

async function toggleProjection() {
  if (observeProjectionActive.value) {
    if (observeCaptureActive.value || store.nativeAudioInfo?.running || store.nativeSttInfo?.running || observeOcrActive.value || observeRecordingActive.value) {
      message.error('请先停止视频流、音频、语音识别、截图/OCR和录屏')
      return
    }
    observeProjectionStopping.value = true
    try {
      if (usingCaptureCard.value) {
        await store.stopCaptureCardSession()
        stopCaptureCardStatusPolling()
      } else {
        await store.stopScrcpySession()
      }
      await store.stop()
      store.clearCaptureMode('observe')
      message.info('采集已停止')
    } finally {
      observeProjectionStopping.value = false
    }
    return
  }

  if (!store.beginCaptureStartup('observe')) {
    message.warning('其它页面正在启动或运行，请先停止后再切换')
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
    if (observeProjectionActive.value) {
      message.success(usingCaptureCard.value ? '采集卡输入已启动，请接入视频流' : '采集已启动，请接入视频流')
    } else {
      message.error(store.captureCardInfo?.last_error || store.scrcpyInfo?.last_error || '采集启动失败')
      store.clearCaptureMode('observe')
    }
  } catch (error: any) {
    store.clearCaptureMode('observe')
    message.error(error?.response?.data?.detail || error?.message || '采集启动失败')
  } finally {
    store.finishCaptureStartup('observe')
  }
}

async function toggleVideo() {
  if (observeCaptureActive.value) {
    if (observeOcrActive.value || observeRecordingActive.value) {
      message.error('请先停止截图/OCR和录屏')
      return
    }
    observeStoppingVideo.value = true
    observeVideoLoading.value = true
    try {
      yoloLivePanel.value?.stopCapture()
      observeCaptureActive.value = false
      await store.markBrowserVideoStream(false)
    } finally {
      observeStoppingVideo.value = false
      observeVideoLoading.value = false
    }
    return
  }
  if (!observeProjectionActive.value) {
    message.error(usingCaptureCard.value ? '请先打开采集卡输入' : '请先启动采集投屏')
    return
  }
  observeVideoLoading.value = true
  try {
    const captured = await yoloLivePanel.value?.startCapture()
    if (captured) {
      observeCaptureActive.value = true
      await store.markBrowserVideoStream(true, { source: usingCaptureCard.value ? 'capture_card' : 'browser_display' })
      message.success('视频流已接入')
    }
  } finally {
    observeVideoLoading.value = false
  }
}

async function toggleAudio() {
  if (store.nativeAudioInfo?.running) {
    if (store.nativeSttInfo?.running || observeRecordingActive.value) {
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
  if (observeOcrActive.value) {
    observeOcrLoading.value = true
    try {
      yoloLivePanel.value?.stopOcr()
      observeOcrActive.value = false
      await store.markOcrCapture(false)
    } finally {
      observeOcrLoading.value = false
    }
    return
  }
  if (!observeCaptureActive.value) {
    message.error('请先接入视频流')
    return
  }
  const intervalMs = store.ocrIntervalMs
  observeOcrLoading.value = true
  try {
    const started = yoloLivePanel.value?.startOcr(intervalMs)
    if (started) {
      observeOcrActive.value = true
      await store.markOcrCapture(true, { interval_ms: intervalMs })
      message.success('截图/OCR已启动')
    }
  } finally {
    observeOcrLoading.value = false
  }
}

async function toggleRecording() {
  if (observeRecordingActive.value) {
    const blob = await yoloLivePanel.value?.stopRecording()
    observeRecordingActive.value = false
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
  if (!observeCaptureActive.value) {
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
      observeRecordingActive.value = false
      message.error('浏览器录屏启动失败')
      return
    }
    observeRecordingActive.value = true
    message.success('录屏已启动')
  } catch (error: any) {
    await store.abortRecorderSession()
    observeRecordingActive.value = false
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
  observeCaptureActive.value = active
  if (!active) {
    observeOcrActive.value = false
    observeRecordingActive.value = false
    const error = observeStoppingVideo.value ? '' : '视频流已断开'
    void store.markBrowserVideoStream(false, {}, error)
    void store.markOcrCapture(false, {}, error)
  }
}

async function handleDetachedRecordingBlob(blob: Blob | null) {
  observeRecordingActive.value = false
  if (observeSuppressDetachedRecording.value) {
    observeSuppressDetachedRecording.value = false
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

async function handleGenerateReplay() {
  await store.generateReplay()
  message.success('复盘报告已生成')
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

.observation-yolo-stage {
  height: min(900px, calc(100vh - 100px));
  min-height: 600px;
  aspect-ratio: auto;
}

.sale-card-body,
.review-outline-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sale-card-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.sale-card-empty {
  min-height: 92px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border: 1px dashed rgba(255, 209, 102, 0.34);
  border-radius: 6px;
  color: #dce9e4;
  background: rgba(255, 209, 102, 0.07);
}

.sale-card-empty strong,
.review-outline-item strong {
  color: #f6fff9;
  font-size: 13px;
}

.sale-card-empty span,
.review-outline-item span {
  color: #95aab3;
  font-size: 12px;
  line-height: 1.5;
}

.review-outline-item {
  display: grid;
  gap: 4px;
  padding: 9px 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.035);
}

.customer-leads-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.customer-leads-empty {
  min-height: 92px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border: 1px dashed rgba(34, 211, 166, 0.34);
  border-radius: 6px;
  color: #dce9e4;
  background: rgba(34, 211, 166, 0.07);
}

.customer-leads-empty strong {
  color: #f6fff9;
  font-size: 13px;
}

.customer-leads-empty span {
  color: #95aab3;
  font-size: 12px;
  line-height: 1.5;
}

.customer-leads-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.customer-lead-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.035);
}

.lead-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(34, 211, 166, 0.2);
  color: #22d3a6;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.lead-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.lead-info strong {
  color: #f6fff9;
  font-size: 13px;
}

.lead-info span {
  color: #95aab3;
  font-size: 12px;
  line-height: 1.5;
}
</style>
