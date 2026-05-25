<template>
  <section class="panel frame-gallery-panel">
    <header class="panel-header">
      <div>
        <div class="panel-title">截屏卡片</div>
        <div class="transcript-meta">手动上传或截图后显示在这里</div>
      </div>
      <n-tag size="small" type="info">{{ frames.length }} 张</n-tag>
    </header>

    <div class="panel-body frame-gallery-body">
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
import { NTag } from 'naive-ui'
import { resolveAssetUrl } from '../api/jlao'
import type { FrameSnapshot } from '../types'

defineProps<{
  frames: FrameSnapshot[]
}>()

function formatScore(value: number | null | undefined) {
  return value == null ? '-' : String(Math.round(value))
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString('zh-CN', { hour12: false })
}
</script>
