<template>
  <main class="page">
    <app-top-nav title="JLAO 视频号翡翠直播观察沙盘" subtitle="公开视频号直播观察、虚拟场控回复和训练样本生成" />

    <div class="dashboard">
      <session-status-bar
        :session="store.currentSession"
        :products="store.products"
        :connected="store.connected"
        @start="handleStart"
        @stop="handleStop"
        @load-tab="liveSourcePanel?.startTabCapture()"
        @change-product="store.selectProduct"
      />

      <section class="main-grid">
        <aside class="phone-screen-stage">
          <div class="phone-window-placeholder">
            <div class="phone-window-title">手机实时投屏</div>
            <div class="phone-window-text">
              scrcpy 原生窗口会在电脑桌面弹出；这里不再重复显示抽帧截图。
            </div>
          </div>

          <scrcpy-panel
            ref="scrcpyPanel"
            :session-id="store.currentSession?.id || ''"
            :capture-running="store.phoneCaptureInfo?.running || false"
            :capture-loading="store.phoneCaptureLoading"
            @start="handleScrcpyStart"
            @stop="handleScrcpyStop"
            @start-capture="handlePhoneCaptureStart"
            @stop-capture="handlePhoneCaptureStop"
          />

          <div class="phone-capture-status" :class="{ error: !!store.phoneCaptureInfo?.last_error }">
            <span>API: {{ apiBase }}</span>
            <span>投屏：{{ store.scrcpyInfo?.running ? '原生窗口已启动' : '未启动 / 已关闭' }}</span>
            <span>
              抽帧：{{ store.phoneCaptureInfo?.running ? '运行中' : '未运行' }}
              <template v-if="store.phoneCaptureInfo?.last_error">｜{{ store.phoneCaptureInfo.last_error }}</template>
            </span>
            <span>音频：暂未接入手机声音；当前音频链路仍需单独开启麦克风/标签页采集。</span>
          </div>
        </aside>

        <div class="left-workspace">
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

        <div class="right-workspace">
          <section class="side-metrics-panel">
            <div class="metric-box">
              <span class="metric-label">实时转写</span>
              <span class="metric-value">{{ store.transcripts.length }}</span>
            </div>
            <div class="metric-box">
              <span class="metric-label">虚拟回复</span>
              <span class="metric-value">{{ store.suggestions.length }}</span>
            </div>
            <div class="metric-box">
              <span class="metric-label">风险样本</span>
              <span class="metric-value">{{ highRiskCount }}</span>
            </div>
          </section>
          <frame-gallery-panel :frames="store.frames" />
          <knowledge-panel :hits="store.wikiHits" :total="store.wikiChunks.length" />
          <virtual-customer-panel :customers="store.virtualCustomers" :events="store.customerEvents" />
          <agent-utterance-panel :agents="store.agents" :utterances="store.agentUtterances" />
          <transcript-panel :transcripts="store.transcripts" :partial-transcript="store.partialTranscript" />
          <suggestion-panel
            :suggestions="store.topSuggestions"
            @accept="handleSuggestionAction('accept', $event)"
            @copy="handleSuggestionAction('copy', $event)"
            @used="handleSuggestionAction('used', $event)"
            @reject="handleSuggestionAction('reject', $event)"
          />
          <product-panel
            :product="store.currentProduct"
            :manual-name="store.currentSession?.manual_product_name || ''"
            :detected-color="store.currentSession?.detected_color || ''"
            :detected-water="store.currentSession?.detected_water || ''"
            :detected-subject="store.currentSession?.detected_subject || ''"
            :detected-extra="store.currentSession?.detected_extra || ''"
            :detected-full-name="store.currentSession?.detected_full_name || ''"
            @set-manual-product-name="store.setManualProductName"
          />
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
import KnowledgePanel from '../components/KnowledgePanel.vue'
import LiveSourcePanel from '../components/LiveSourcePanel.vue'
import ProductPanel from '../components/ProductPanel.vue'
import ScrcpyPanel from '../components/ScrcpyPanel.vue'
import SessionStatusBar from '../components/SessionStatusBar.vue'
import SuggestionPanel from '../components/SuggestionPanel.vue'
import TranscriptPanel from '../components/TranscriptPanel.vue'
import VirtualCustomerPanel from '../components/VirtualCustomerPanel.vue'
import { API_BASE } from '../api/client'
import { useJlaoStore } from '../stores/jlao'

const store = useJlaoStore()
const message = useMessage()
const liveSourcePanel = ref<InstanceType<typeof LiveSourcePanel> | null>(null)
const scrcpyPanel = ref<InstanceType<typeof ScrcpyPanel> | null>(null)
const defaultPhoneSerial = '3AF9K24227080668'
const apiBase = API_BASE

const highRiskCount = computed(() =>
  store.suggestions.filter((item) => String(item.risk_level).includes('高') || String(item.risk_level).includes('楂')).length,
)

onMounted(async () => {
  await store.initDemo()
  await store.refreshSessionData()
})

async function handleStart() {
  await store.start()

  await store.startScrcpySession(defaultPhoneSerial)
  if (store.scrcpyInfo?.running) {
    scrcpyPanel.value?.markStarted()
  }

  await store.startPhoneCaptureSession(defaultPhoneSerial)

  if (store.scrcpyInfo?.running && store.phoneCaptureInfo?.running) {
    message.success('手机端已载入，投屏窗口和抽帧已启动')
  } else if (store.phoneCaptureInfo?.running) {
    message.warning('抽帧已启动，但 scrcpy 投屏窗口未启动，请检查本地后端/桌面权限')
  } else {
    message.error(store.phoneCaptureInfo?.last_error || store.scrcpyInfo?.last_error || '手机端载入失败')
  }
}

async function handleStop() {
  await store.stop()
  scrcpyPanel.value?.disconnect()
  message.info('手机端已停止')
}

async function handleSuggestionAction(action: 'accept' | 'copy' | 'used' | 'reject', id: string) {
  await store.setSuggestionAction(id, action)
}

async function handleScrcpyStart(serial: string) {
  await store.startScrcpySession(serial)
  if (store.scrcpyInfo?.running) {
    scrcpyPanel.value?.markStarted()
    if (!store.phoneCaptureInfo?.running) {
      await store.startPhoneCaptureSession(serial || defaultPhoneSerial)
    }
    message.success(store.phoneCaptureInfo?.running ? 'scrcpy 已启动，截屏同步中' : 'scrcpy 已启动')
  } else {
    const error = store.scrcpyInfo?.last_error || 'scrcpy 启动失败'
    scrcpyPanel.value?.markFailed(error)
    message.error(error)
  }
}

async function handleScrcpyStop() {
  await store.stopScrcpySession()
  scrcpyPanel.value?.disconnect()
}

async function handlePhoneCaptureStart(serial: string) {
  await store.startPhoneCaptureSession(serial)
  if (store.phoneCaptureInfo?.running) {
    message.success('1FPS 截屏已启动')
  } else {
    message.error(store.phoneCaptureInfo?.last_error || '1FPS 截屏启动失败')
  }
}

async function handlePhoneCaptureStop() {
  await store.stopPhoneCaptureSession()
  message.info('1FPS 截屏已停止')
}
</script>
