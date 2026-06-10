<template>
  <main class="page jade-recognition-page">
    <app-top-nav title="翡翠多模态识别" subtitle="图像 + 主播讲解文本 · 颜色 / 种水 / 样式 / 题材" />

    <section class="recognition-shell">
      <n-card class="control-card" title="批量识别">
        <div class="control-grid">
          <label class="file-drop">
            <input type="file" accept="image/*" multiple @change="handleFileChange" />
            <span>选择翡翠图片</span>
            <small>支持多图；每张图会单独融合相同的讲解文本。</small>
          </label>

          <n-input
            v-model:value="text"
            type="textarea"
            :autosize="{ minRows: 4, maxRows: 7 }"
            placeholder="可选：粘贴主播讲解，如：冰种阳绿观音吊坠，尺寸 45×28mm..."
          />
        </div>

        <div class="selected-files" v-if="files.length">
          <n-tag v-for="file in files" :key="file.name" size="small" type="success">
            {{ file.name }}
          </n-tag>
        </div>

        <div class="actions-row">
          <n-button type="primary" :loading="loading" @click="runBatchRecognition">
            开始识别
          </n-button>
          <n-button quaternary :disabled="loading" @click="clearAll">
            清空
          </n-button>
          <n-button
            v-if="result?.items.length"
            secondary
            type="success"
            :loading="savingAll"
            @click="saveAllCorrections"
          >
            保存全部校正
          </n-button>
          <n-button v-if="result?.items.length" secondary :disabled="loading" @click="exportResultsCsv">
            导出结果 CSV
          </n-button>
          <n-button
            v-if="currentBatchId"
            secondary
            :loading="batchTraceLoading"
            @click="() => refreshBatchTrace()"
          >
            查询本批反馈
          </n-button>
          <span class="hint">也可以只填文本，用来测试文本属性抽取。</span>
          <span v-if="Object.keys(savedFeedbackIds).length" class="hint">
            已保存的卡片不会在批量保存时重复写入。
          </span>
          <span v-if="batchTraceCount !== null" class="hint">
            本批反馈池记录：{{ batchTraceCount }} 条
          </span>
          <span v-if="batchTraceSummary" class="hint">
            可训练 {{ batchTraceSummary.training_counts.yolo_ready }} 条，需框 {{ batchTraceSummary.training_counts.requires_manual_box }} 条
          </span>
          <span v-if="batchTraceSummary" class="hint">
            覆盖：色{{ batchTraceSummary.attribute_counts.color }} / 水{{ batchTraceSummary.attribute_counts.water }} / 样{{ batchTraceSummary.attribute_counts.style }} / 题{{ batchTraceSummary.attribute_counts.theme }}
          </span>
          <span v-if="batchTraceSummary?.readiness" class="hint">
            下一步：{{ batchTraceSummary.readiness.recommended_next_steps.join(' / ') }}
          </span>
          <n-button
            v-if="batchTrainingCommand"
            size="small"
            secondary
            @click="copyBatchTrainingCommand"
          >
            复制批次训练命令
          </n-button>
        </div>

        <n-alert v-if="error" type="error" class="mt">
          {{ error }}
        </n-alert>
        <n-alert v-else type="info" class="mt">
          单次批量保存会跳过已保存卡片，也会跳过低置信度且未人工改动的卡片；刷新页面后的历史重复样本会在训练导入和 manifest 检查阶段继续去重。
        </n-alert>
        <pre v-if="batchTrainingCommand" class="command-box">{{ batchTrainingCommand }}</pre>
      </n-card>

      <n-card class="runtime-card" title="运行状态">
        <n-alert v-if="modelWarning" type="warning" class="runtime-alert">
          {{ modelWarning }}
        </n-alert>
        <div v-if="reviewSummaryItems.length" class="review-summary">
          <span>本批复核标记</span>
          <n-tag v-for="item in reviewSummaryItems" :key="item.flag" size="small" type="warning">
            {{ item.flag }} × {{ item.count }}
          </n-tag>
        </div>
        <div v-if="modelStatus?.limits" class="limit-line">
          支持 {{ modelStatus.limits.upload_image_extensions.join(' / ') }}；
          单图 ≤ {{ modelStatus.limits.upload_max_mb }}MB；
          API 批量上限 {{ modelStatus.limits.batch_max_items }} 张；
          批次训练建议至少 {{ modelStatus.limits.batch_readiness_min_yolo_ready_records || 12 }} 条可训练反馈。
        </div>
        <div class="runtime-grid">
          <div>
            <span>YOLO</span>
            <strong>{{ runtimeLabel('yolo') }}</strong>
          </div>
          <div>
            <span>VLM</span>
            <strong>{{ runtimeLabel('vlm') }}</strong>
            <small v-if="vlmModelLabel">{{ vlmModelLabel }}</small>
          </div>
          <div>
            <span>反馈学习</span>
            <strong>{{ runtimeLabel('feedback_learning') }}</strong>
          </div>
        </div>
      </n-card>

      <n-spin :show="loading">
        <section v-if="result?.items.length" class="result-grid">
          <article v-for="(item, index) in result.items" :key="`${item.input.image}-${index}`" class="result-card">
            <div class="preview">
              <img v-if="item.input.image" :src="resolveAssetUrl(item.input.image)" :alt="item.input.source_filename || 'jade sample'" />
              <div v-else class="text-only">TEXT</div>
            </div>

            <div class="result-body">
              <div class="result-title">
                <strong>{{ item.name || '未形成完整名称' }}</strong>
                <n-tag size="small" :type="confidenceType(item.confidence)">
                  {{ percent(item.confidence) }}
                </n-tag>
              </div>
              <n-alert v-if="item.review_flags?.length" type="warning" class="confidence-warning">
                需复核：{{ item.review_flags.join(' / ') }}
              </n-alert>

              <dl class="attrs">
                <div>
                  <dt>颜色</dt>
                  <dd>{{ item.attributes.color || '未识别' }}</dd>
                  <small>{{ attrSource(item, 'color') }}</small>
                </div>
                <div>
                  <dt>种水</dt>
                  <dd>{{ item.attributes.water || '未识别' }}</dd>
                  <small>{{ attrSource(item, 'water') }}</small>
                </div>
                <div>
                  <dt>样式</dt>
                  <dd>{{ item.attributes.style || '未识别' }}</dd>
                  <small>{{ attrSource(item, 'style') }}</small>
                </div>
                <div>
                  <dt>题材</dt>
                  <dd>{{ item.attributes.theme || '未识别' }}</dd>
                  <small>{{ attrSource(item, 'theme') }}</small>
                </div>
              </dl>

              <div v-if="hasColorDiagnostics(item)" class="color-diagnostics">
                <span class="diagnostic-title">颜色诊断</span>
                <div class="diagnostic-grid">
                  <div>
                    <small>色系</small>
                    <strong>{{ colorLayer(item, 'family') || '未提供' }}</strong>
                  </div>
                  <div>
                    <small>细分</small>
                    <strong>{{ colorLayer(item, 'detail') || '未提供' }}</strong>
                  </div>
                  <div>
                    <small>花色</small>
                    <strong>{{ colorLayer(item, 'pattern') || '未提供' }}</strong>
                  </div>
                </div>
                <div v-if="observedColors(item, 'opencv_subject_colors').length" class="color-chip-line">
                  <span>主体 ROI</span>
                  <n-tag
                    v-for="candidate in observedColors(item, 'opencv_subject_colors')"
                    :key="`subject-${candidate.family}-${candidate.ratio}`"
                    size="small"
                    type="success"
                  >
                    {{ candidate.family }} {{ ratioPercent(candidate.ratio) }}
                  </n-tag>
                </div>
                <div v-if="observedColors(item, 'opencv_frame_colors').length" class="color-chip-line muted">
                  <span>画面整体</span>
                  <n-tag
                    v-for="candidate in observedColors(item, 'opencv_frame_colors')"
                    :key="`frame-${candidate.family}-${candidate.ratio}`"
                    size="small"
                  >
                    {{ candidate.family }} {{ ratioPercent(candidate.ratio) }}
                  </n-tag>
                </div>
                <small v-if="opencvPatternLabel(item)" class="roi-line">{{ opencvPatternLabel(item) }}</small>
                <small v-if="subjectRoiLabel(item)" class="roi-line">{{ subjectRoiLabel(item) }}</small>
              </div>

              <div v-if="corrections[index]" class="correction-box">
                <span class="correction-title">人工校正后写入训练池</span>
                <div class="correction-grid">
                  <n-select
                    v-model:value="corrections[index].color"
                    size="small"
                    filterable
                    tag
                    clearable
                    placeholder="颜色"
                    :options="taxonomySelectOptions.colors"
                  />
                  <n-select
                    v-model:value="corrections[index].water"
                    size="small"
                    filterable
                    tag
                    clearable
                    placeholder="种水"
                    :options="taxonomySelectOptions.waters"
                  />
                  <n-select
                    v-model:value="corrections[index].style"
                    size="small"
                    filterable
                    tag
                    clearable
                    placeholder="样式"
                    :options="taxonomySelectOptions.styles"
                  />
                  <n-select
                    v-model:value="corrections[index].theme"
                    size="small"
                    filterable
                    tag
                    clearable
                    placeholder="题材"
                    :options="taxonomySelectOptions.themes"
                  />
                </div>
                <p class="correction-hint">
                  优先选择标准标签；自定义标签可保存，但训练前会被 manifest 检查标记为待确认。
                </p>
                <div class="save-line">
                  <n-button
                    size="small"
                    type="primary"
                    secondary
                    :loading="Boolean(feedbackSaving[index])"
                    @click="saveCorrection(index, item)"
                  >
                    写入反馈训练池
                  </n-button>
                  <span v-if="savedFeedbackIds[index]">已保存：{{ savedFeedbackIds[index] }}</span>
                </div>
                <div class="save-line">
                  <n-button
                    size="small"
                    secondary
                    :loading="Boolean(productCreating[index])"
                    @click="createProductDraft(index, item)"
                  >
                    生成商品草稿
                  </n-button>
                  <span v-if="createdProductIds[index]">商品：{{ createdProductIds[index] }}</span>
                </div>
              </div>

              <div class="evidence-line">
                <span>检测 {{ item.evidence.detections.length }} 个目标</span>
                <span v-if="item.input.source_filename">{{ item.input.source_filename }}</span>
                <span v-if="item.input.batch_id || result?.batch_id">{{ item.input.batch_id || result?.batch_id }}</span>
              </div>
            </div>
          </article>
        </section>

        <n-empty v-else class="empty-state" description="上传图片或填写文本后开始识别" />
      </n-spin>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NAlert, NButton, NCard, NEmpty, NInput, NSelect, NSpin, NTag, useMessage } from 'naive-ui'
import AppTopNav from '../components/AppTopNav.vue'
import {
  analyzeJadeBatch,
  createProduct,
  fetchJadeBatchFeedbackTrace,
  fetchJadeModelStatus,
  fetchJadeTaxonomyOptions,
  resolveAssetUrl,
  submitJadeSampleFeedback,
  submitJadeSampleFeedbackBatch,
} from '../api/jlao'
import type {
  JadeBatchAnalysis,
  JadeBatchFeedbackTrace,
  JadeModelStatus,
  JadeSampleFeedbackPayload,
  JadeTaxonomyOptions,
  ProductCreatePayload,
} from '../types'

const files = ref<File[]>([])
const text = ref('')
const loading = ref(false)
const error = ref('')
const result = ref<JadeBatchAnalysis | null>(null)
const modelStatus = ref<JadeModelStatus | null>(null)
const corrections = ref<Record<number, { color: string; water: string; style: string; theme: string }>>({})
const feedbackSaving = ref<Record<number, boolean>>({})
const savedFeedbackIds = ref<Record<number, string>>({})
const savingAll = ref(false)
const productCreating = ref<Record<number, boolean>>({})
const createdProductIds = ref<Record<number, string>>({})
const batchTraceLoading = ref(false)
const batchTraceCount = ref<number | null>(null)
const batchTraceSummary = ref<NonNullable<JadeBatchFeedbackTrace['summary']> | null>(null)
const message = useMessage()
const taxonomy = ref<JadeTaxonomyOptions>({
  status: 'local',
  colors: ['帝王绿', '阳绿', '辣绿', '苹果绿', '豆绿', '绿色', '蓝水', '晴水', '油青', '紫罗兰', '春带彩', '白冰', '无色', '白底青', '飘花', '黄翡', '冰黄', '洒金', '墨翠', '红翡', '多彩'],
  waters: ['玻璃种', '高冰', '冰种', '冰胶', '起冰', '冰糯', '糯冰', '起胶', '糯化', '细糯', '糯种', '豆种'],
  styles: ['手镯', '珠串', '蛋面', '戒面', '戒指', '挂件', '吊坠', '平安扣', '摆件', '把件', '耳饰'],
  themes: ['观音', '佛公', '如意', '叶子', '山水', '貔貅', '葫芦', '无事牌', '财神', '龙', '福瓜', '福豆'],
})

const runtime = computed(() => result.value?.runtime || modelStatus.value || null)
const currentBatchId = computed(() => result.value?.batch_id || '')
const modelWarning = computed(() => {
  const status = modelStatus.value
  if (!status?.readiness) return ''
  if (!status.readiness.has_jade_yolo_model && status.readiness.uses_pretrained_yolo_fallback) {
    return '当前未检测到翡翠专用 YOLO 模型，图像样式/题材识别会使用通用模型和规则兜底；建议积累校正样本后训练。'
  }
  if (!status.readiness.has_vlm && !status.readiness.has_feedback_learning) {
    return '当前没有 VLM 或反馈学习增强，复杂题材和弱图像信号需要更多人工复核。'
  }
  return ''
})
const vlmModelLabel = computed(() => {
  const vlm = runtime.value?.vlm
  if (!vlm) return ''
  const model = vlm.configured_model_path || vlm.default_http_model || ''
  if (!model) return ''
  if (vlm.using_default_http_model) return `${model}（默认 Ollama）`
  return `${model}（配置）`
})
const reviewSummaryItems = computed(() => (
  Object.entries(result.value?.review_summary || {})
    .map(([flag, count]) => ({ flag, count }))
    .sort((a, b) => b.count - a.count || a.flag.localeCompare(b.flag))
))
const batchTrainingCommand = computed(() => {
  if (!currentBatchId.value || !batchTraceSummary.value?.readiness) return ''
  const escaped = currentBatchId.value.replace(/"/g, '\\"')
  const base = `powershell -ExecutionPolicy Bypass -File scripts\\jade.ps1 train-batch-feedback -BatchId "${escaped}" -IncludeRows -ExportMistakes`
  return batchTraceSummary.value.readiness.can_try_batch_training ? base : `${base} -SkipTrain`
})
const taxonomySelectOptions = computed(() => ({
  colors: taxonomy.value.colors.map(toSelectOption),
  waters: taxonomy.value.waters.map(toSelectOption),
  styles: taxonomy.value.styles.map(toSelectOption),
  themes: taxonomy.value.themes.map(toSelectOption),
}))

onMounted(async () => {
  try {
    taxonomy.value = await fetchJadeTaxonomyOptions()
  } catch (err) {
    console.warn('加载翡翠标签体系失败，使用本地兜底标签', err)
  }
  try {
    modelStatus.value = await fetchJadeModelStatus()
  } catch (err) {
    console.warn('加载翡翠模型状态失败', err)
  }
})

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  files.value = Array.from(input.files || [])
}

async function runBatchRecognition() {
  error.value = ''
  if (!files.value.length && !text.value.trim()) {
    error.value = '请至少选择一张图片或填写讲解文本'
    return
  }
  loading.value = true
  try {
    result.value = await analyzeJadeBatch({
      files: files.value,
      text: text.value,
      maxItems: 20,
    })
    corrections.value = Object.fromEntries(
      result.value.items.map((item, index) => [
        index,
        {
          color: item.attributes.color || '',
          water: item.attributes.water || '',
          style: item.attributes.style || '',
          theme: item.attributes.theme || '',
        },
      ])
    )
    savedFeedbackIds.value = {}
    batchTraceCount.value = null
    batchTraceSummary.value = null
  } catch (err) {
    console.error(err)
    error.value = '识别失败，请检查后端服务、模型状态或上传文件'
  } finally {
    loading.value = false
  }
}

function clearAll() {
  files.value = []
  text.value = ''
  result.value = null
  error.value = ''
  corrections.value = {}
  savedFeedbackIds.value = {}
  productCreating.value = {}
  createdProductIds.value = {}
  batchTraceCount.value = null
  batchTraceSummary.value = null
}

async function createProductDraft(index: number, item: JadeBatchAnalysis['items'][number]) {
  productCreating.value = { ...productCreating.value, [index]: true }
  try {
    const payload = buildProductPayload(index, item)
    const product = await createProduct(payload)
    createdProductIds.value = { ...createdProductIds.value, [index]: product.id }
    message.success('商品草稿已生成')
  } catch (err) {
    console.error(err)
    message.error('生成商品草稿失败')
  } finally {
    productCreating.value = { ...productCreating.value, [index]: false }
  }
}

async function saveCorrection(index: number, item: JadeBatchAnalysis['items'][number]) {
  const corrected = corrections.value[index]
  if (!corrected || !Object.values(corrected).some((value) => value.trim())) {
    message.warning('请至少填写一个校正字段')
    return
  }
  feedbackSaving.value = { ...feedbackSaving.value, [index]: true }
  try {
    const response = await submitJadeSampleFeedback(buildFeedbackPayload(index, item))
    savedFeedbackIds.value = { ...savedFeedbackIds.value, [index]: response.id }
    await refreshBatchTrace(false)
    message.success('校正已写入反馈训练池')
  } catch (err) {
    console.error(err)
    message.error('写入反馈训练池失败')
  } finally {
    feedbackSaving.value = { ...feedbackSaving.value, [index]: false }
  }
}

async function saveAllCorrections() {
  if (!result.value?.items.length) return
  const items = result.value.items
    .map((item, index) => (
      savedFeedbackIds.value[index] || isLowConfidenceUnchanged(index, item)
        ? null
        : buildFeedbackPayload(index, item)
    ))
    .filter((payload): payload is JadeSampleFeedbackPayload => Boolean(payload))
    .filter((payload) => Object.values(payload.corrected).some((value) => value.trim()))
  if (!items.length) {
    message.warning('没有可保存的校正字段')
    return
  }
  savingAll.value = true
  try {
    const response = await submitJadeSampleFeedbackBatch({ items })
    const saved: Record<number, string> = { ...savedFeedbackIds.value }
    response.results.forEach((item) => {
      if (item.status === 'ok' && item.id) {
        saved[item.index - 1] = item.id
      }
    })
    savedFeedbackIds.value = saved
    await refreshBatchTrace(false)
    if (response.skipped) {
      message.warning(`已保存 ${response.saved} 条，跳过 ${response.skipped} 条`)
    } else {
      message.success(`已保存 ${response.saved} 条校正反馈`)
    }
  } catch (err) {
    console.error(err)
    message.error('批量写入反馈训练池失败')
  } finally {
    savingAll.value = false
  }
}

async function refreshBatchTrace(showMessage = true) {
  if (!currentBatchId.value) return
  batchTraceLoading.value = true
  try {
    const trace = await fetchJadeBatchFeedbackTrace(currentBatchId.value)
    batchTraceCount.value = trace.count
    batchTraceSummary.value = trace.summary || null
    if (showMessage) message.success(`本批反馈池记录：${trace.count} 条`)
  } catch (err) {
    console.error(err)
    if (showMessage) message.error('查询本批反馈失败')
  } finally {
    batchTraceLoading.value = false
  }
}

async function copyBatchTrainingCommand() {
  if (!batchTrainingCommand.value) return
  try {
    await navigator.clipboard.writeText(batchTrainingCommand.value)
    message.success('批次训练命令已复制')
  } catch (err) {
    console.error(err)
    message.error('复制失败，请从页面命令框手动复制')
  }
}

function buildProductPayload(index: number, item: JadeBatchAnalysis['items'][number]): ProductCreatePayload {
  const corrected = normalizeCorrection(corrections.value[index])
  const attrs = {
    color: corrected.color || item.attributes.color || '',
    water: corrected.water || item.attributes.water || '',
    style: corrected.style || item.attributes.style || '',
    theme: corrected.theme || item.attributes.theme || '',
  }
  const displaySubject = attrs.style || attrs.theme
  const name = [attrs.color, attrs.water, displaySubject].filter(Boolean).join(' ') || item.name || '翡翠商品'
  const attributeSources = item.signals.attribute_sources as ProductCreatePayload['attribute_sources'] | undefined
  const fusionScores = item.signals.fusion_scores as ProductCreatePayload['fusion_scores'] | undefined
  const batchId = item.input.batch_id || result.value?.batch_id || ''
  return {
    name,
    category: displaySubject || '翡翠',
    material: '翡翠',
    color: attrs.color,
    water: attrs.water,
    style: attrs.style,
    theme: attrs.theme,
    size: item.attributes.size || '',
    price: item.attributes.price ?? null,
    evidence_image_paths: item.input.image ? [item.input.image] : item.evidence.images,
    evidence_texts: [
      ...(item.input.text ? [item.input.text] : item.evidence.texts),
      batchId ? `batch_id=${batchId}` : '',
    ].filter(Boolean),
    analysis_confidence: item.confidence,
    attribute_sources: {
      ...(attributeSources || {}),
      ...(batchId
        ? {
            _trace: {
              source: 'jade-recognition-page',
              method: 'batch-trace',
              value: batchId,
            },
          }
        : {}),
    },
    fusion_scores: fusionScores || {},
    selling_points: [
      attrs.color ? `颜色：${attrs.color}` : '',
      attrs.water ? `种水：${attrs.water}` : '',
      attrs.style ? `样式：${attrs.style}` : '',
      attrs.theme ? `题材：${attrs.theme}` : '',
    ].filter(Boolean),
    faq: [],
    recommended_scripts: [],
  }
}

function isLowConfidenceUnchanged(index: number, item: JadeBatchAnalysis['items'][number]) {
  if (!item.review_flags?.includes('low-confidence')) return false
  const corrected = normalizeCorrection(corrections.value[index])
  return (
    corrected.color === (item.attributes.color || '') &&
    corrected.water === (item.attributes.water || '') &&
    corrected.style === (item.attributes.style || '') &&
    corrected.theme === (item.attributes.theme || '')
  )
}

function buildFeedbackPayload(index: number, item: JadeBatchAnalysis['items'][number]): JadeSampleFeedbackPayload {
  const attributeSources = item.signals.attribute_sources as Record<string, unknown> | undefined
  const corrected = normalizeCorrection(corrections.value[index])
  return {
    input: {
      image: item.input.image,
      text: item.input.text,
      batch_id: item.input.batch_id || result.value?.batch_id || '',
    },
    predicted: item.attributes,
    corrected,
    evidence: item.evidence,
    confidence: item.confidence,
    attribute_sources: attributeSources,
  }
}

function normalizeCorrection(value?: { color?: string | null; water?: string | null; style?: string | null; theme?: string | null }) {
  return {
    color: (value?.color || '').trim(),
    water: (value?.water || '').trim(),
    style: (value?.style || '').trim(),
    theme: (value?.theme || '').trim(),
  }
}

function runtimeLabel(key: 'yolo' | 'vlm' | 'feedback_learning') {
  const value = runtime.value?.[key]
  if (!value) return '待识别后加载'
  const reason = 'reason' in value ? value.reason : ''
  return value.enabled ? '可用' : reason || '不可用'
}

function confidenceType(value: number) {
  if (value >= 0.7) return 'success'
  if (value >= 0.45) return 'warning'
  return 'error'
}

function percent(value: number) {
  return `${Math.round((value || 0) * 100)}%`
}

function exportResultsCsv() {
  if (!result.value?.items.length) return
  const headers = [
    'index',
    'source_filename',
    'image',
    'text',
    'batch_id',
    'predicted_name',
    'predicted_color',
    'predicted_color_family',
    'predicted_color_detail',
    'predicted_color_pattern',
    'opencv_pattern_candidate',
    'opencv_pattern_reason',
    'vlm_color_signal',
    'subject_colors',
    'frame_colors',
    'subject_roi',
    'predicted_water',
    'predicted_style',
    'predicted_theme',
    'corrected_color',
    'corrected_water',
    'corrected_style',
    'corrected_theme',
    'confidence',
    'color_source',
    'water_source',
    'style_source',
    'theme_source',
    'saved_feedback_id',
  ]
  const rows = result.value.items.map((item, index) => {
    const corrected = normalizeCorrection(corrections.value[index])
    return [
      String(index + 1),
      item.input.source_filename || '',
      item.input.image || '',
      item.input.text || '',
      item.input.batch_id || result.value?.batch_id || '',
      item.name || '',
      item.attributes.color || '',
      colorLayer(item, 'family'),
      colorLayer(item, 'detail'),
      colorLayer(item, 'pattern'),
      colorDiagnosticValue(item, 'opencv_pattern_candidate'),
      colorDiagnosticValue(item, 'opencv_pattern_reason'),
      colorDiagnosticValue(item, 'vlm_color_signal'),
      JSON.stringify(observedColors(item, 'opencv_subject_colors')),
      JSON.stringify(observedColors(item, 'opencv_frame_colors')),
      subjectRoiLabel(item),
      item.attributes.water || '',
      item.attributes.style || '',
      item.attributes.theme || '',
      corrected.color,
      corrected.water,
      corrected.style,
      corrected.theme,
      String(item.confidence || 0),
      attrSource(item, 'color'),
      attrSource(item, 'water'),
      attrSource(item, 'style'),
      attrSource(item, 'theme'),
      savedFeedbackIds.value[index] || '',
    ]
  })
  const csv = [headers, ...rows].map((row) => row.map(escapeCsv).join(',')).join('\n')
  const blob = new Blob([`\ufeff${csv}\n`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `jade-recognition-${Date.now()}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

function attrSource(item: JadeBatchAnalysis['items'][number], key: 'color' | 'water' | 'style' | 'theme') {
  const sources = item.signals.attribute_sources as Record<string, { source?: string; method?: string; value?: unknown }> | undefined
  const source = sources?.[key]
  if (!source) return '来源：未提供'
  const method = source.method ? ` / ${source.method}` : ''
  return `来源：${source.source || 'unknown'}${method}`
}

type ObservedColor = { family: string; ratio: number }

function colorAnalysis(item: JadeBatchAnalysis['items'][number]) {
  return recordSignal(item.signals.color_analysis)
}

function colorLayer(item: JadeBatchAnalysis['items'][number], key: 'family' | 'detail' | 'pattern') {
  const value = colorAnalysis(item)[key]
  return typeof value === 'string' ? value : ''
}

function observedColors(item: JadeBatchAnalysis['items'][number], key: 'opencv_subject_colors' | 'opencv_frame_colors'): ObservedColor[] {
  const value = colorAnalysis(item)[key]
  if (!Array.isArray(value)) return []
  return value
    .map((candidate) => {
      const record = recordSignal(candidate)
      const family = typeof record.family === 'string' ? record.family : ''
      const ratio = Number(record.ratio || 0)
      return family && Number.isFinite(ratio) ? { family, ratio } : null
    })
    .filter((candidate): candidate is ObservedColor => Boolean(candidate))
}

function hasColorDiagnostics(item: JadeBatchAnalysis['items'][number]) {
  return Boolean(
    colorLayer(item, 'family') ||
    colorLayer(item, 'detail') ||
    colorLayer(item, 'pattern') ||
    observedColors(item, 'opencv_subject_colors').length ||
    observedColors(item, 'opencv_frame_colors').length ||
    opencvPatternLabel(item) ||
    subjectRoiLabel(item)
  )
}

function colorDiagnosticValue(item: JadeBatchAnalysis['items'][number], key: string) {
  const value = colorAnalysis(item)[key]
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') return String(value)
  return typeof value === 'string' ? value : ''
}

function opencvPatternLabel(item: JadeBatchAnalysis['items'][number]) {
  const candidate = colorDiagnosticValue(item, 'opencv_pattern_candidate')
  if (!candidate) return ''
  const reason = colorDiagnosticValue(item, 'opencv_pattern_reason')
  const vlmLocked = colorDiagnosticValue(item, 'vlm_color_signal') === 'true'
  const policy = vlmLocked ? 'VLM已锁定主色，仅作诊断' : '可用于缺失补全'
  return `OpenCV花色候选：${candidate}${reason ? ` / ${reason}` : ''} / ${policy}`
}

function subjectRoiLabel(item: JadeBatchAnalysis['items'][number]) {
  const roi = recordSignal(colorAnalysis(item).opencv_subject_roi)
  const source = typeof roi.source === 'string' ? roi.source : ''
  const reason = typeof roi.reason === 'string' ? roi.reason : ''
  const width = Number(roi.expanded_w || roi.w || 0)
  const height = Number(roi.expanded_h || roi.h || 0)
  const area = Number(roi.expanded_area_ratio || roi.area_ratio || 0)
  if (width > 0 && height > 0) {
    return `ROI：${source || 'subject'} ${Math.round(width)}×${Math.round(height)}，面积 ${ratioPercent(area)}`
  }
  if (reason) return `ROI：${source || 'fallback'} / ${reason}`
  return source ? `ROI：${source}` : ''
}

function ratioPercent(value: number) {
  return `${Math.round((value || 0) * 100)}%`
}

function recordSignal(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function toSelectOption(value: string) {
  return { label: value, value }
}

function escapeCsv(value: string) {
  const normalized = String(value ?? '')
  return /[",\r\n]/.test(normalized) ? `"${normalized.replace(/"/g, '""')}"` : normalized
}
</script>

<style scoped>
.jade-recognition-page {
  min-height: 100vh;
  background:
    radial-gradient(circle at 20% 12%, rgba(34, 211, 166, 0.16), transparent 34%),
    radial-gradient(circle at 78% 8%, rgba(240, 184, 72, 0.12), transparent 28%),
    #071015;
}

.recognition-shell {
  width: min(1180px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 22px 0 40px;
  display: grid;
  gap: 16px;
}

.control-card,
.runtime-card,
.result-card {
  border: 1px solid rgba(120, 255, 216, 0.12);
  box-shadow: 0 20px 70px rgba(0, 0, 0, 0.28);
}

.control-grid {
  display: grid;
  grid-template-columns: 0.9fr 1.1fr;
  gap: 16px;
}

.file-drop {
  min-height: 132px;
  border: 1px dashed rgba(94, 232, 199, 0.42);
  border-radius: 14px;
  display: grid;
  place-content: center;
  gap: 8px;
  text-align: center;
  cursor: pointer;
  background: linear-gradient(135deg, rgba(34, 211, 166, 0.12), rgba(255, 255, 255, 0.03));
}

.file-drop input {
  display: none;
}

.file-drop span {
  color: #dcfff6;
  font-size: 18px;
  font-weight: 700;
}

.file-drop small,
.hint,
.evidence-line,
.runtime-grid span {
  color: #8fa3b6;
}

.selected-files,
.actions-row {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.mt {
  margin-top: 14px;
}

.command-box {
  margin: 14px 0 0;
  padding: 12px;
  border-radius: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  color: #dcfff6;
  background: rgba(0, 0, 0, 0.28);
  border: 1px solid rgba(94, 232, 199, 0.18);
  font-size: 12px;
}

.runtime-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.runtime-alert {
  margin-bottom: 12px;
}

.review-summary {
  margin-bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.review-summary span {
  color: #8fa3b6;
  font-size: 12px;
}

.limit-line {
  margin-bottom: 12px;
  color: #8fa3b6;
  font-size: 12px;
  line-height: 1.5;
}

.runtime-grid div {
  padding: 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.045);
  display: grid;
  gap: 5px;
}

.runtime-grid strong {
  color: #ecf7f4;
}

.runtime-grid small {
  color: #8fa3b6;
  font-size: 11px;
  word-break: break-all;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.result-card {
  overflow: hidden;
  border-radius: 18px;
  background: rgba(11, 22, 29, 0.9);
}

.preview {
  height: 210px;
  background: #05090d;
}

.preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.text-only {
  height: 100%;
  display: grid;
  place-items: center;
  color: #5ee8c7;
  letter-spacing: 0.28em;
}

.result-body {
  padding: 14px;
}

.result-title,
.evidence-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.confidence-warning {
  margin-top: 10px;
}

.attrs {
  margin: 14px 0;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.attrs div {
  padding: 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.05);
}

.attrs dt {
  color: #8fa3b6;
  font-size: 12px;
}

.attrs dd {
  margin: 4px 0 0;
  color: #ecf7f4;
  font-weight: 700;
}

.attrs small {
  display: block;
  margin-top: 4px;
  color: #8fa3b6;
  font-size: 11px;
  line-height: 1.35;
}

.color-diagnostics {
  margin: 12px 0;
  padding: 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.045);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.diagnostic-title {
  color: #dcfff6;
  font-size: 12px;
  font-weight: 700;
}

.diagnostic-grid {
  margin-top: 9px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.diagnostic-grid div {
  padding: 8px;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.18);
}

.diagnostic-grid small,
.roi-line,
.color-chip-line span {
  color: #8fa3b6;
  font-size: 11px;
}

.diagnostic-grid strong {
  display: block;
  margin-top: 3px;
  color: #ecf7f4;
}

.color-chip-line {
  margin-top: 9px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.color-chip-line.muted {
  opacity: 0.82;
}

.roi-line {
  display: block;
  margin-top: 8px;
  line-height: 1.4;
}

.correction-box {
  margin: 12px 0;
  padding: 12px;
  border-radius: 14px;
  background: rgba(34, 211, 166, 0.08);
  border: 1px solid rgba(94, 232, 199, 0.14);
}

.correction-title {
  color: #dcfff6;
  font-size: 12px;
  font-weight: 700;
}

.correction-grid {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.correction-hint {
  margin: 8px 0 0;
  color: #8fa3b6;
  font-size: 12px;
  line-height: 1.5;
}

.save-line {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  color: #8fa3b6;
  font-size: 12px;
}

.empty-state {
  padding: 80px 0;
}

@media (max-width: 760px) {
  .control-grid,
  .runtime-grid {
    grid-template-columns: 1fr;
  }
}
</style>
