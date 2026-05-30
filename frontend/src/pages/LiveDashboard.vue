<template>
  <main class="page live-dashboard-page">
    <app-top-nav title="自己直播间运营" subtitle="手机投屏 · 实时转写 · 运营数据墙" />

    <div class="dashboard one-screen-dashboard">
      <section class="main-grid ops-screen-grid">
        <section class="projection-stage">
          <div class="projection-empty">
            <span>手机投屏</span>
            <small>QtScrcpy 实时窗口；抽帧进截屏卡片。</small>
          </div>
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
import { onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import AgentUtterancePanel from '../components/AgentUtterancePanel.vue'
import AppTopNav from '../components/AppTopNav.vue'
import FrameGalleryPanel from '../components/FrameGalleryPanel.vue'
import KnowledgePanel from '../components/KnowledgePanel.vue'
import LiveSourcePanel from '../components/LiveSourcePanel.vue'
import ProductLibraryPanel from '../components/ProductLibraryPanel.vue'
import SessionStatusBar from '../components/SessionStatusBar.vue'
import TranscriptPanel from '../components/TranscriptPanel.vue'
import VirtualCustomerPanel from '../components/VirtualCustomerPanel.vue'
import { useJlaoStore } from '../stores/jlao'

const store = useJlaoStore()
const message = useMessage()
const liveSourcePanel = ref<InstanceType<typeof LiveSourcePanel> | null>(null)

onMounted(async () => {
  await store.initDemo()
  await store.refreshSessionData()
})

async function handleStart() {
  await store.start()
  await store.startScrcpySession()
  await store.startPhoneCaptureSession()
  await new Promise((resolve) => window.setTimeout(resolve, 1200))
  await store.refreshPhoneCaptureStatus()

  const phoneCaptureReady = Boolean(store.phoneCaptureInfo?.running && !store.phoneCaptureInfo?.last_error)
  if (phoneCaptureReady) await store.startNativeSttSession()
  const audioStarted = Boolean(store.nativeSttInfo?.running && !store.nativeSttInfo?.last_error)

  if (store.scrcpyInfo?.running && phoneCaptureReady && audioStarted) {
    message.success('手机采集已启动：投屏、抽帧、原生音频转写同步运行')
  } else if (store.scrcpyInfo?.running && phoneCaptureReady) {
    message.error(store.nativeSttInfo?.last_error || '原生手机音频没有接进实时转写')
  } else if (phoneCaptureReady) {
    message.warning('抽帧已启动，投屏窗口未启动，请检查本地后端和桌面权限')
  } else {
    message.error(store.phoneCaptureInfo?.last_error || store.scrcpyInfo?.last_error || '手机端加载失败')
  }
}

async function handleStop() {
  await store.stop()
  liveSourcePanel.value?.stopProjectedAudioCapture()
  message.info('手机采集已停止')
}
</script>
