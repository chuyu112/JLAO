<template>
  <section class="panel frame-gallery-panel" :class="{ 'is-collapsed': collapsed }">
    <header class="panel-header">
      <div class="frame-gallery-heading">
        <div class="panel-title">截屏卡片</div>
        <div class="transcript-meta">{{ collapsed ? collapsedMeta : '手动上传或截图后显示在这里' }}</div>
      </div>
      <div class="frame-gallery-actions">
        <n-tag size="small" type="info">{{ frames.length }} 张</n-tag>
        <n-button size="tiny" quaternary :aria-expanded="!collapsed" @click="toggleCollapsed">
          <template #icon>
            <chevron-right v-if="collapsed" :size="14" />
            <chevron-down v-else :size="14" />
          </template>
          {{ collapsed ? '展开' : '折叠' }}
        </n-button>
      </div>
    </header>

    <div v-if="collapsed" class="frame-gallery-strip">
      <template v-if="latestFrame">
        <img class="frame-gallery-strip-image" :src="resolveAssetUrl(latestFrame.image_path)" :alt="latestFrame.detected_scene" />
        <div class="frame-gallery-strip-copy">
          <strong>{{ latestFrame.recognized_product_name || latestFrame.detected_scene }}</strong>
          <span>{{ formatTime(latestFrame.created_at) }} · 清晰度 {{ formatScore(latestFrame.sharpness_score) }}</span>
        </div>
      </template>
      <div v-else class="frame-gallery-strip-empty">暂无截图</div>
    </div>

    <div v-if="!collapsed" class="panel-body frame-gallery-body">
      <div v-if="frames.length === 0" class="empty-state compact">上传截图后，这里会显示识别卡片。</div>
      <div v-else class="frame-card-list">
        <article v-for="frame in frames" :key="frame.id" class="frame-card">
          <img class="frame-card-image" :src="resolveAssetUrl(frame.image_path)" :alt="frame.detected_scene" />
          <div class="frame-card-meta">
            <div class="frame-card-title">{{ frame.recognized_product_name || frame.detected_scene }}</div>
            <div v-if="frame.recognized_product_name" class="frame-card-line frame-card-recognition">
              识别 · {{ frame.recognition_source || '图像' }}
              <span v-if="frame.recognition_confidence != null"> · {{ frame.recognition_confidence.toFixed(2) }}</span>
            </div>
            <div class="frame-card-line">清晰度 {{ formatScore(frame.sharpness_score) }} · 亮度 {{ formatScore(frame.brightness_score) }}</div>
            <div class="frame-card-time">{{ formatTime(frame.created_at) }}</div>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { NButton, NTag } from 'naive-ui'
import { ChevronDown, ChevronRight } from 'lucide-vue-next'
import { resolveAssetUrl } from '../api/jlao'
import type { FrameSnapshot } from '../types'

const props = defineProps<{
  frames: FrameSnapshot[]
}>()

const collapsed = ref(true)
const latestFrame = computed(() => props.frames[0] || null)
const collapsedMeta = computed(() => {
  if (!latestFrame.value) return '默认折叠，不占主屏空间'
  return `最新：${latestFrame.value.recognized_product_name || latestFrame.value.detected_scene}`
})

function toggleCollapsed() {
  collapsed.value = !collapsed.value
}

function formatScore(value: number | null | undefined) {
  return value == null ? '-' : String(Math.round(value))
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString('zh-CN', { hour12: false })
}
</script>
