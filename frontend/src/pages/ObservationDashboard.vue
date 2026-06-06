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
          {{ store.currentSession?.live_room_name || '待识别直播间名' }}
        </n-tag>
      </div>

      <section class="main-grid ops-screen-grid observation-screen-grid">
        <section class="projection-stage observation-projection-stage observation-yolo-stage">
          <jade-yolo-live-panel
            ref="yoloLivePanel"
            :session-id="store.currentSession?.id || null"
            :source-active="observeSourceActive"
            :source-blocked="store.isCaptureModeBlocked('observe')"
            @start-stt="store.connectStt"
            @stop-stt="store.disconnectStt"
            @audio-frame="store.sendSttAudio"
            @capture-state-change="handleYoloCaptureStateChange"
          />
        </section>

        <div class="ops-data-wall observation-data-wall">
          <session-status-bar
            mode="observe"
            :session="store.currentSession"
            :connected="store.connected"
            :audio-connected="store.sttConnected || Boolean(store.nativeSttInfo?.running)"
            :audio-error="store.sttError || store.nativeSttInfo?.last_error || ''"
            :starting="store.captureStartupMode === 'observe'"
            :start-disabled="store.isCaptureModeBlocked('observe')"
            :capture-active="observeCaptureActive"
            :source-active="observeSourceActive"
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
import { computed, onMounted, ref } from 'vue'
import { NButton, NTag, useMessage } from 'naive-ui'
import { FileText } from 'lucide-vue-next'
import AppTopNav from '../components/AppTopNav.vue'
import FrameGalleryPanel from '../components/FrameGalleryPanel.vue'
import JadeYoloLivePanel from '../components/JadeYoloLivePanel.vue'
import ProductLibraryPanel from '../components/ProductLibraryPanel.vue'
import SessionStatusBar from '../components/SessionStatusBar.vue'
import TranscriptPanel from '../components/TranscriptPanel.vue'
import { useJlaoStore } from '../stores/jlao'

const store = useJlaoStore()
const message = useMessage()
const yoloLivePanel = ref<InstanceType<typeof JadeYoloLivePanel> | null>(null)
const observeCaptureActive = ref(false)
const stoppingObserveCapture = ref(false)
const observeSourceActive = computed(
  () => store.activeCaptureMode === 'observe' || Boolean(store.scrcpyInfo?.running || store.phoneCaptureInfo?.running),
)

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
})

async function handlePlatformChange(platform: string) {
  selectedPlatform.value = platform
  // 重新创建会话
  await store.initDemo(platform)
  message.success(`已切换到 ${platform} 平台`)
}

async function handleStart() {
  if (observeSourceActive.value && !observeCaptureActive.value) {
    message.info('采集已启动，请在视频区域点击“接入视频流”')
    return
  }

  if (!store.beginCaptureStartup('observe')) {
    message.warning('自有运营正在启动或运行，请先停止后再切换')
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
      message.warning('抽帧已启动，请点击“接入视频流”；手机投屏窗口未启动，请检查本地后端和桌面权限')
    } else {
      message.warning(store.phoneCaptureInfo?.last_error || store.scrcpyInfo?.last_error || '采集会话已启动，请点击“接入视频流”选择网页或视频窗口')
    }
  } catch (error) {
    console.error('接入视频流失败:', error)
    yoloLivePanel.value?.stopCapture()
    observeCaptureActive.value = false
    await store.stop()
    store.clearCaptureMode('observe')
    message.error('采集启动失败')
  } finally {
    store.finishCaptureStartup('observe')
  }
}

async function handleStop() {
  if (stoppingObserveCapture.value) return
  stoppingObserveCapture.value = true
  try {
    yoloLivePanel.value?.stopCapture()
    observeCaptureActive.value = false
    await store.stop()
    message.info('采集已停止')
  } finally {
    stoppingObserveCapture.value = false
    store.clearCaptureMode('observe')
  }
}

function handleYoloCaptureStateChange(active: boolean) {
  observeCaptureActive.value = active
  if (!active && store.activeCaptureMode === 'observe' && !stoppingObserveCapture.value) {
    void handleStop()
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
