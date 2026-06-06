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
          {{ store.currentSession?.live_room_name || '待识别直播间名' }}
        </n-tag>
      </div>

      <section class="main-grid ops-screen-grid">
        <section class="projection-stage yolo-projection-stage">
          <jade-yolo-live-panel
            ref="yoloLivePanel"
            :session-id="store.currentSession?.id || null"
            :source-active="ownSourceActive"
            :source-blocked="store.isCaptureModeBlocked('own')"
            @start-stt="store.connectStt"
            @stop-stt="store.disconnectStt"
            @audio-frame="store.sendSttAudio"
            @capture-state-change="handleYoloCaptureStateChange"
          />
        </section>

        <div class="audio-capture-agent" aria-hidden="true">
          <live-source-panel
            ref="liveSourcePanel"
            :live-url="store.currentSession?.live_url || null"
            :stt-connected="store.sttConnected"
            :stt-error="store.sttError"
            :latest-frame="store.frames[0] || null"
            :frame-analyzing="store.frameAnalyzing"
            :session-id="store.currentSession?.id || null"
            :manual-product-name="store.currentSession?.manual_product_name || ''"
            @update="store.updateLiveUrl"
            @start-stt="store.connectStt"
            @stop-stt="store.disconnectStt"
            @audio-frame="store.sendSttAudio"
            @capture-frame="store.uploadCaptureFrame"
          />
        </div>

        <div class="ops-data-wall">
          <session-status-bar
            :session="store.currentSession"
            :connected="store.connected"
            :audio-connected="store.sttConnected || Boolean(store.nativeSttInfo?.running)"
            :audio-error="store.sttError || store.nativeSttInfo?.last_error || ''"
            :starting="store.captureStartupMode === 'own'"
            :start-disabled="store.isCaptureModeBlocked('own')"
            :capture-active="ownVideoCaptureActive"
            :source-active="ownSourceActive"
            @start="handleStart"
            @stop="handleStop"
          />

          <transcript-panel
            id="transcript"
            class="data-panel data-panel-transcript"
            :transcripts="store.transcripts"
            :partial-transcript="store.partialTranscript"
            :comment-events="store.liveComments"
          />
          <knowledge-panel id="knowledge" class="data-panel" :hits="store.wikiHits" :total="store.wikiChunks.length" />
          <virtual-customer-panel
            id="customers"
            class="data-panel"
            :customers="store.virtualCustomers"
            :events="store.customerEvents"
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
          <agent-utterance-panel
            id="operations"
            class="data-panel"
            :agents="store.agents"
            :utterances="store.agentUtterances"
          />
          <frame-gallery-panel id="frames" class="data-panel" :frames="store.frames" />
        </div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import AgentUtterancePanel from '../components/AgentUtterancePanel.vue'
import AppTopNav from '../components/AppTopNav.vue'
import FrameGalleryPanel from '../components/FrameGalleryPanel.vue'
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
const liveSourcePanel = ref<InstanceType<typeof LiveSourcePanel> | null>(null)
const yoloLivePanel = ref<InstanceType<typeof JadeYoloLivePanel> | null>(null)
const ownVideoCaptureActive = ref(false)
const stoppingOwnCapture = ref(false)
const ownSourceActive = computed(
  () => store.activeCaptureMode === 'own' || Boolean(store.scrcpyInfo?.running || store.phoneCaptureInfo?.running),
)

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
})

async function handlePlatformChange(platform: string) {
  selectedPlatform.value = platform
  // 重新创建会话
  await store.initDemo(platform)
  message.success(`已切换到 ${platform} 平台`)
}

async function handleStart() {
  if (ownSourceActive.value && !ownVideoCaptureActive.value) {
    message.info('采集已启动，请在视频区域点击“接入视频流”')
    return
  }

  if (!store.beginCaptureStartup('own')) {
    message.warning('其它分析正在启动或运行，请先停止后再切换')
    return
  }

  try {
    await store.start()
    await store.startScrcpySession()
    await store.startPhoneCaptureSession()
    await new Promise((resolve) => window.setTimeout(resolve, 1200))
    await store.refreshPhoneCaptureStatus()
    await store.stopNativeSttSession()

    const phoneCaptureReady = Boolean(store.phoneCaptureInfo?.running && !store.phoneCaptureInfo?.last_error)

    if (store.scrcpyInfo?.running && phoneCaptureReady) {
      message.success('采集源已启动，请点击“接入视频流”选择手机投屏窗口')
    } else if (phoneCaptureReady) {
      message.warning('抽帧已启动，请点击“接入视频流”；投屏窗口未启动，请检查本地后端和桌面权限')
    } else {
      message.warning(store.phoneCaptureInfo?.last_error || store.scrcpyInfo?.last_error || '采集会话已启动，请点击“接入视频流”选择网页或视频窗口')
    }
  } catch (error) {
    console.error('启动采集失败:', error)
    yoloLivePanel.value?.stopCapture()
    ownVideoCaptureActive.value = false
    await store.stop()
    store.clearCaptureMode('own')
    message.error('采集启动失败')
  } finally {
    store.finishCaptureStartup('own')
  }
}

async function handleStop() {
  if (stoppingOwnCapture.value) return
  stoppingOwnCapture.value = true
  try {
    yoloLivePanel.value?.stopCapture()
    ownVideoCaptureActive.value = false
    await store.stop()
    message.info('采集已停止')
  } finally {
    stoppingOwnCapture.value = false
    store.clearCaptureMode('own')
  }
}

function handleYoloCaptureStateChange(active: boolean) {
  ownVideoCaptureActive.value = active
  if (!active && store.activeCaptureMode === 'own' && !stoppingOwnCapture.value) {
    void handleStop()
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


