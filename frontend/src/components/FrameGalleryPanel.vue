<template>
  <section class="panel frame-gallery-panel" :class="{ 'is-collapsed': collapsed }">
    <header class="panel-header">
      <div class="frame-gallery-heading">
        <div class="panel-title">截图卡片</div>
        <div class="transcript-meta">{{ collapsed ? collapsedMeta : '手动上传或实时截图后显示在这里' }}</div>
      </div>
      <div class="frame-gallery-actions">
        <n-tag size="small" type="info">{{ frames.length }} 张</n-tag>
        <n-button size="tiny" quaternary :aria-expanded="!collapsed" @click="toggleCollapsed">
          <template #icon>
            <chevron-right v-if="collapsed" :size="14" />
            <chevron-down v-else :size="14" />
          </template>
          {{ collapsed ? '展开' : '收起' }}
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
            <div v-if="jadeTags(frame).length" class="frame-card-jade">
              <n-tag v-for="tag in jadeTags(frame)" :key="tag.key" size="small" type="success">
                {{ tag.label }}
              </n-tag>
              <n-tag v-if="frame.jade_confidence" size="small" type="info">
                置信 {{ Math.round(frame.jade_confidence * 100) }}%
              </n-tag>
            </div>
            <div v-if="jadeSourceLabels(frame).length" class="frame-card-line frame-card-sources">
              来源：{{ jadeSourceLabels(frame).join(' · ') }}
            </div>
            <div v-if="frame.jade_detections?.length" class="frame-card-line frame-card-sources">
              检测：{{ frame.jade_detections.length }} 个候选框
            </div>
            <div v-if="frame.jade_ocr_lines?.length" class="frame-card-ocr">
              <strong>画面 OCR</strong>
              <span v-for="line in frame.jade_ocr_lines.slice(0, 3)" :key="line">{{ line }}</span>
            </div>
            <div v-else-if="frame.jade_ocr_error" class="frame-card-line frame-card-sources">
              OCR：{{ frame.jade_ocr_error }}
            </div>
            <div class="frame-card-actions">
              <n-button size="tiny" secondary @click="toggleCorrection(frame)">
                {{ correctionOpen[frame.id] ? '收起校正' : '校正属性' }}
              </n-button>
            </div>
            <div v-if="correctionOpen[frame.id]" class="frame-correction-form">
              <n-select
                v-model:value="correctionForms[frame.id].color"
                size="small"
                filterable
                tag
                :options="jadeSelectOptions.colors"
                placeholder="颜色"
              />
              <n-select
                v-model:value="correctionForms[frame.id].water"
                size="small"
                filterable
                tag
                :options="jadeSelectOptions.waters"
                placeholder="种水"
              />
              <n-select
                v-model:value="correctionForms[frame.id].style"
                size="small"
                filterable
                tag
                :options="jadeSelectOptions.styles"
                placeholder="款式"
              />
              <n-select
                v-model:value="correctionForms[frame.id].theme"
                size="small"
                filterable
                tag
                :options="jadeSelectOptions.themes"
                placeholder="题材"
              />
              <n-button size="tiny" type="warning" secondary :loading="correctionSaving[frame.id]" @click="submitCorrection(frame)">
                保存校正
              </n-button>
            </div>
            <div class="frame-card-time">{{ formatTime(frame.created_at) }}</div>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { NButton, NSelect, NTag, useMessage } from 'naive-ui'
import { ChevronDown, ChevronRight } from 'lucide-vue-next'
import { fetchJadeTaxonomyOptions, resolveAssetUrl, submitFrameJadeFeedback } from '../api/jlao'
import type { FrameSnapshot, JadeTaxonomyOptions } from '../types'

type CorrectionForm = {
  color: string
  water: string
  style: string
  theme: string
}

const props = defineProps<{
  frames: FrameSnapshot[]
}>()

const message = useMessage()
const collapsed = ref(true)
const correctionOpen = reactive<Record<string, boolean>>({})
const correctionSaving = reactive<Record<string, boolean>>({})
const correctionForms = reactive<Record<string, CorrectionForm>>({})
const jadeTaxonomyOptions = ref<JadeTaxonomyOptions | null>(null)
const latestFrame = computed(() => props.frames[0] || null)
const collapsedMeta = computed(() => {
  if (!latestFrame.value) return '默认收起，不占主屏空间'
  return `最新：${latestFrame.value.recognized_product_name || latestFrame.value.detected_scene}`
})
const jadeSelectOptions = computed(() => ({
  colors: toSelectOptions(jadeTaxonomyOptions.value?.colors || ['帝王绿', '阳绿', '辣绿', '苹果绿', '豆绿', '绿色', '蓝水', '晴水', '油青', '紫罗兰', '春带彩', '白冰', '无色', '白底青', '飘花', '黄翡', '冰黄', '洒金', '墨翠', '红翡', '多彩']),
  waters: toSelectOptions(jadeTaxonomyOptions.value?.waters || ['玻璃种', '高冰', '冰种', '冰胶', '起冰', '冰糯', '糯冰', '起胶', '糯化', '细糯', '糯种', '豆种']),
  styles: toSelectOptions(jadeTaxonomyOptions.value?.styles || ['手镯', '珠串', '珠链', '蛋面', '戒指', '吊坠', '耳饰', '摆件']),
  themes: toSelectOptions(jadeTaxonomyOptions.value?.themes || ['观音', '佛公', '平安扣', '如意', '叶子', '山水', '貔貅', '葫芦', '无事牌', '财神', '龙牌', '福瓜', '福豆']),
}))

onMounted(async () => {
  try {
    jadeTaxonomyOptions.value = await fetchJadeTaxonomyOptions()
  } catch {
    jadeTaxonomyOptions.value = null
  }
})

function toggleCollapsed() {
  collapsed.value = !collapsed.value
}

function formatScore(value: number | null | undefined) {
  return value == null ? '-' : String(Math.round(value))
}

function jadeTags(frame: FrameSnapshot) {
  return [
    { key: 'color', label: frame.jade_color ? `颜色：${frame.jade_color}` : '' },
    { key: 'water', label: frame.jade_water ? `种水：${frame.jade_water}` : '' },
    { key: 'style', label: frame.jade_style ? `款式：${frame.jade_style}` : '' },
    { key: 'theme', label: frame.jade_theme ? `题材：${frame.jade_theme}` : '' },
  ].filter((item) => item.label)
}

function jadeSourceLabels(frame: FrameSnapshot) {
  const sources = frame.jade_attribute_sources || {}
  return ['color', 'water', 'style', 'theme']
    .map((key) => {
      const source = sources[key]
      if (!source?.source) return ''
      const value = source.value ? `${source.value} ` : ''
      return `${value}${source.source}${source.method ? `/${source.method}` : ''}`
    })
    .filter(Boolean)
}

function toggleCorrection(frame: FrameSnapshot) {
  if (!correctionForms[frame.id]) {
    correctionForms[frame.id] = {
      color: frame.jade_color || '',
      water: frame.jade_water || '',
      style: frame.jade_style || '',
      theme: frame.jade_theme || '',
    }
  }
  correctionOpen[frame.id] = !correctionOpen[frame.id]
}

async function submitCorrection(frame: FrameSnapshot) {
  const form = correctionForms[frame.id]
  if (!form) return
  correctionSaving[frame.id] = true
  try {
    const updated = await submitFrameJadeFeedback(frame.session_id, frame.id, { corrected: form })
    Object.assign(frame, updated)
    correctionOpen[frame.id] = false
    message.success('直播帧校正已保存，会进入反馈学习和标注池')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '直播帧校正保存失败')
  } finally {
    correctionSaving[frame.id] = false
  }
}

function toSelectOptions(items: string[]) {
  return items.map((item) => ({ label: item, value: item }))
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.frame-card-ocr {
  display: grid;
  gap: 4px;
  margin-top: 8px;
  padding: 8px;
  border: 1px solid rgba(34, 197, 94, 0.22);
  border-radius: 10px;
  background: rgba(240, 253, 244, 0.68);
  color: #14532d;
  font-size: 12px;
  line-height: 1.45;
}

.frame-card-ocr strong {
  font-size: 11px;
  color: #166534;
}

.frame-correction-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  margin-top: 8px;
}

.frame-correction-form .n-button {
  grid-column: 1 / -1;
  justify-self: start;
}
</style>
