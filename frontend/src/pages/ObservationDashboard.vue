<template>
  <main class="page observation-dashboard-page">
    <app-top-nav title="别人直播间分析" subtitle="黑盒观察 · 成交卡片 · 弹幕累积" />

    <div class="dashboard one-screen-dashboard">
      <section class="main-grid ops-screen-grid observation-screen-grid">
        <section class="projection-stage observation-projection-stage">
          <div class="projection-empty">
            <span>直播间观察</span>
            <small>投屏窗口保持原生；这里沉淀抽帧、成交卡片和弹幕证据。</small>
          </div>
        </section>

        <div class="ops-data-wall observation-data-wall">
          <session-status-bar
            mode="observe"
            :session="store.currentSession"
            :connected="store.connected"
            :audio-connected="store.sttConnected || Boolean(store.nativeSttInfo?.running)"
            :audio-error="store.sttError || store.nativeSttInfo?.last_error || ''"
            @start="handleStart"
            @stop="handleStop"
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

          <product-library-panel
            id="observation-products"
            class="data-panel"
            :products="store.products"
            :current-product-id="store.currentSession?.current_product_id || null"
            :detected-name="store.currentSession?.detected_full_name || ''"
            @select-product="store.selectProduct"
          />

          <frame-gallery-panel id="observation-frames" class="data-panel" :frames="store.frames" />

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
import { onMounted } from 'vue'
import { NButton, NTag, useMessage } from 'naive-ui'
import { FileText } from 'lucide-vue-next'
import AppTopNav from '../components/AppTopNav.vue'
import FrameGalleryPanel from '../components/FrameGalleryPanel.vue'
import ProductLibraryPanel from '../components/ProductLibraryPanel.vue'
import SessionStatusBar from '../components/SessionStatusBar.vue'
import TranscriptPanel from '../components/TranscriptPanel.vue'
import { useJlaoStore } from '../stores/jlao'

const store = useJlaoStore()
const message = useMessage()

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
    message.success('观察采集已启动：投屏、0.2 秒抽帧、原生音频转写正在运行')
  } else if (store.scrcpyInfo?.running && phoneCaptureReady) {
    message.error(store.nativeSttInfo?.last_error || '原生手机音频没有接进实时转写')
  } else if (phoneCaptureReady) {
    message.warning('抽帧已启动，投屏窗口未启动，请检查本地后端和桌面权限')
  } else {
    message.error(store.phoneCaptureInfo?.last_error || store.scrcpyInfo?.last_error || '观察采集启动失败')
  }
}

async function handleStop() {
  await store.stop()
  message.info('观察采集已停止')
}

async function handleGenerateReplay() {
  await store.generateReplay()
  message.success('复盘报告已生成')
}
</script>

<style scoped>
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
</style>
