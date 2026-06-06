<template>
  <main class="page">
    <app-top-nav title="翡翠商品库" subtitle="直播里真实出现过的货品，图像、讲解、人工标注一起进入识别闭环" />

    <section class="dashboard product-page">
      <section class="hero-panel">
        <div>
          <p class="eyebrow">JADE MULTIMODAL ENGINE</p>
          <h1>翡翠多模态识别</h1>
          <p class="hero-copy">
            主线是 YOLO 小模型 + STT 主播讲解；OCR 只做弱补充证据，通用 VLM 只做预标注助手，人工确认后才回流训练集。
          </p>
        </div>
        <div class="hero-actions">
          <n-button type="primary" :loading="loadingProducts" @click="loadProducts">刷新商品</n-button>
          <n-button secondary type="info" :loading="loadingStatus" @click="loadRuntime">刷新模型状态</n-button>
        </div>
      </section>

      <section class="grid two">
        <article class="panel runtime-panel">
          <header class="panel-header">
            <div>
              <div class="panel-title">识别运行时</div>
              <div class="transcript-meta">YOLO + STT 是主信号；OCR / VLM 只做弱补充和预标注</div>
            </div>
            <n-tag :type="jadeModelStatus?.readiness?.has_vlm ? 'success' : 'warning'">
              {{ jadeModelStatus?.readiness?.has_vlm ? 'VLM 已接入' : 'VLM 未接入' }}
            </n-tag>
          </header>

          <div class="runtime-grid">
            <div class="runtime-card" :class="{ ok: !!jadeModelStatus?.yolo?.enabled }">
              <span>YOLO 主信号</span>
              <strong>{{ runtimeEnabled(jadeModelStatus?.yolo?.enabled) }}</strong>
              <small>{{ yoloText }}</small>
            </div>
            <div class="runtime-card ok">
              <span>STT 主信号</span>
              <strong>本地讲解</strong>
              <small>主播讲解用于颜色 / 种水 / 尺寸 / 题材属性识别</small>
            </div>
            <div class="runtime-card" :class="{ ok: !!jadeModelStatus?.ocr?.enabled }">
              <span>OCR 弱补充</span>
              <strong>{{ runtimeEnabled(jadeModelStatus?.ocr?.enabled) }}</strong>
              <small>{{ ocrText }}</small>
            </div>
            <div class="runtime-card" :class="{ ok: !!jadeModelStatus?.vlm?.enabled }">
              <span>VLM 弱预标注</span>
              <strong>{{ runtimeEnabled(jadeModelStatus?.vlm?.enabled) }}</strong>
              <small>{{ vlmText }}</small>
            </div>
            <div class="runtime-card" :class="{ ok: !!jadeModelStatus?.feedback_learning?.enabled }">
              <span>反馈学习</span>
              <strong>{{ runtimeEnabled(jadeModelStatus?.feedback_learning?.enabled) }}</strong>
              <small>{{ feedbackText }}</small>
            </div>
          </div>

          <div v-if="vlmDiagnosticText" class="callout warning">
            {{ vlmDiagnosticText }}
          </div>

          <div class="inline-actions">
            <n-button type="info" secondary :loading="vlmProbeLoading" @click="runVlmProbe">
              探测外部 VLM 预标注
            </n-button>
            <n-button type="warning" secondary :loading="vlmPrelabelSaving" @click="saveVlmPrelabel">
              生成 VLM 待确认预标注
            </n-button>
          </div>

          <div v-if="vlmProbeSummary" class="callout">{{ vlmProbeSummary }}</div>
          <div v-if="vlmPrelabelMessage" class="callout success">{{ vlmPrelabelMessage }}</div>
          <div v-if="runtimeError" class="error-text">{{ runtimeError }}</div>
        </article>

        <article class="panel sample-panel">
          <header class="panel-header">
            <div>
              <div class="panel-title">样图识别</div>
              <div class="transcript-meta">上传一张翡翠图，可附主播讲解，综合识别颜色 / 种水 / 样式 / 题材</div>
            </div>
          </header>

          <div class="sample-form">
            <input class="file-input" type="file" accept="image/*" @change="handleSampleFileChange" />
            <n-input
              v-model:value="sampleText"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 6 }"
              placeholder="主播讲解，例如：这条是蓝水珠串，糯冰，珠子很匀..."
            />
            <div class="inline-actions">
              <n-button type="primary" :loading="sampleLoading" @click="runSampleAnalysis">开始识别</n-button>
              <n-button secondary @click="clearSample">清空</n-button>
            </div>
          </div>

          <div v-if="sampleAnalysis" class="analysis-result">
            <div class="result-head">
              <strong>{{ sampleAnalysis.name || '翡翠样图' }}</strong>
              <n-tag>{{ confidenceText(sampleAnalysis.confidence) }}</n-tag>
            </div>
            <img
              v-if="sampleAnalysis.evidence.images[0]"
              :src="resolveAssetUrl(sampleAnalysis.evidence.images[0])"
              alt="翡翠样图"
            />
            <div class="attr-grid">
              <div v-for="item in sampleAttributes" :key="item.key">
                <span>{{ item.label }}</span>
                <strong>{{ item.value || '待识别' }}</strong>
                <n-tag v-if="item.sourceLabel" size="tiny" :type="item.sourceType">{{ item.sourceLabel }}</n-tag>
              </div>
            </div>
            <div v-if="opencvCandidateItems.length" class="class-count-row">
              <n-tag v-for="item in opencvCandidateItems" :key="item.key" size="tiny" type="warning">
                图像弱候选 {{ item.label }}：{{ item.value }}
              </n-tag>
            </div>
            <div class="feedback-grid">
              <n-auto-complete v-model:value="feedbackDraft.color" :options="taxonomyOptionsFor('color')" placeholder="校正颜色" />
              <n-auto-complete v-model:value="feedbackDraft.water" :options="taxonomyOptionsFor('water')" placeholder="校正种水" />
              <n-auto-complete v-model:value="feedbackDraft.style" :options="taxonomyOptionsFor('style')" placeholder="校正样式" />
              <n-auto-complete v-model:value="feedbackDraft.theme" :options="taxonomyOptionsFor('theme')" placeholder="校正题材" />
            </div>
            <n-button type="success" secondary :loading="feedbackSaving" @click="submitFeedback">
              保存人工校正到训练池
            </n-button>
          </div>

          <div v-if="sampleError" class="error-text">{{ sampleError }}</div>
          <div v-if="feedbackMessage" class="callout success">{{ feedbackMessage }}</div>
        </article>
      </section>

      <section class="grid two">
        <article class="panel training-panel">
          <header class="panel-header">
            <div>
              <div class="panel-title">训练闭环</div>
              <div class="transcript-meta">人工校正和画框样本会进入 YOLO 小模型训练集</div>
            </div>
            <div class="inline-actions">
              <n-button type="primary" secondary :loading="trainingBuilding" @click="buildTrainingDataset">
                从反馈生成训练集
              </n-button>
              <n-button secondary type="warning" :loading="evaluationLoading" @click="runLocalEvaluation">
                评估识别准确率
              </n-button>
              <n-button type="success" :loading="trainingStarting" :disabled="trainingRunStatus?.running || !trainingRunStatus?.can_start" @click="startLocalTraining">
                启动本地 YOLO 训练
              </n-button>
              <n-button secondary type="info" @click="loadTrainingRunStatus">
                刷新训练状态
              </n-button>
            </div>
          </header>

          <div class="metric-grid">
            <div>
              <span>反馈记录</span>
              <strong>{{ trainingStatus?.feedback.records ?? 0 }}</strong>
            </div>
            <div>
              <span>可进 YOLO</span>
              <strong>{{ trainingStatus?.feedback.usable_for_yolo ?? 0 }}</strong>
            </div>
            <div>
              <span>整图弱框</span>
              <strong>{{ trainingStatus?.feedback.whole_image_box ?? 0 }}</strong>
            </div>
            <div>
              <span>人工精框</span>
              <strong>{{ trainingStatus?.feedback.manual_box ?? 0 }}</strong>
            </div>
            <div>
              <span>待画框</span>
              <strong>{{ trainingStatus?.feedback.requires_manual_box ?? 0 }}</strong>
            </div>
          </div>

          <div class="transcript-meta">
            训练标签：{{ trainingStatus?.dataset.labels.train ?? 0 }}，验证标签：{{ trainingStatus?.dataset.labels.val ?? 0 }}；整图弱框用于快速预训练，后期人工精框用于提高主体定位。
          </div>
          <div v-if="classCountItems.length" class="class-count-row">
            <n-tag v-for="item in classCountItems" :key="item.name" size="tiny" type="info">
              {{ item.label }} × {{ item.count }}
            </n-tag>
          </div>
          <div v-if="missingClassText" class="callout warning">缺样本类别：{{ missingClassText }}</div>
          <div class="transcript-meta">
            模型：{{ trainingStatus?.model.exists ? '已生成' : '未生成' }} · {{ trainingStatus?.model.path || 'models/jade-yolo.pt' }}
          </div>
          <div class="training-run-card">
            <div>
              <span>本地训练状态</span>
              <strong>{{ trainingRunStatus?.running ? `训练中 PID ${trainingRunStatus.pid}` : '空闲' }}</strong>
            </div>
            <div>
              <span>能否启动</span>
              <strong>{{ trainingRunStatus?.can_start ? '可以' : '暂不能' }}</strong>
            </div>
            <div>
              <span>模型产物</span>
              <strong>{{ trainingRunStatus?.model_exists ? '已生成' : '未生成' }}</strong>
            </div>
          </div>
          <div v-if="trainingRunStatus?.blocking_reasons?.length" class="callout warning">
            {{ trainingRunStatus.blocking_reasons.join('；') }}
          </div>
          <div class="transcript-meta">
            最低启动门槛：train {{ trainingMinTrainLabels }} 条，val {{ trainingMinValLabels }} 条。
          </div>
          <div v-if="trainingGapText" class="callout warning">{{ trainingGapText }}</div>
          <div v-if="sampleCollectionText" class="callout warning">{{ sampleCollectionText }}</div>
          <pre v-if="trainingRunStatus?.log_tail" class="training-log">{{ trainingRunStatus.log_tail }}</pre>
          <div v-if="trainingMessage" class="callout success">{{ trainingMessage }}</div>
          <div v-if="trainingError" class="error-text">{{ trainingError }}</div>
          <div v-if="evaluationResult" class="callout">
            评估：整体 {{ Math.round(evaluationResult.overall.accuracy * 100) }}%，最弱 {{ evaluationResult.weakest_attribute || '无' }}，样本 {{ evaluationResult.evaluated }}/{{ evaluationResult.selected }}
            <div class="eval-metric-row">
              <n-tag v-for="item in evaluationMetricItems" :key="item.key" size="tiny" :type="item.accuracy >= 0.8 ? 'success' : item.accuracy >= 0.5 ? 'warning' : 'error'">
                {{ item.label }} {{ Math.round(item.accuracy * 100) }}% ({{ item.correct }}/{{ item.total }})
              </n-tag>
            </div>
            <div v-if="evaluationResult.recommendations?.length" class="eval-recommendations">
              {{ evaluationResult.recommendations.join('；') }}
            </div>
            <div v-if="evaluationMissItems.length" class="eval-miss-row">
              <n-tag v-for="item in evaluationMissItems" :key="`${item.attribute}-${item.pair}`" size="tiny" type="warning">
                {{ item.label }}：{{ item.pair }} × {{ item.count }}
              </n-tag>
            </div>
            <div v-if="evaluationHardCases.length" class="eval-hard-cases">
              <div v-for="item in evaluationHardCases" :key="`${item.id}-${item.attribute}`" class="eval-hard-case">
                <img v-if="item.image" :src="resolveAssetUrl(item.image)" alt="评估错例" />
                <div>
                  <strong>{{ item.attribute_label || item.attribute }} · {{ item.id }}</strong>
                  <span>预测：{{ item.predicted || '空' }}，正确：{{ item.corrected || '空' }}</span>
                </div>
              </div>
            </div>
          </div>
          <div v-if="evaluationError" class="error-text">{{ evaluationError }}</div>
        </article>

        <article class="panel annotation-panel">
          <header class="panel-header">
            <div>
              <div class="panel-title">人工标注任务</div>
              <div class="transcript-meta">需要人工确认样式 / 题材 / 主体框的样本</div>
              <div v-if="annotationStatsText" class="transcript-meta">{{ annotationStatsText }}</div>
            </div>
            <n-button secondary type="info" :loading="annotationLoading" @click="loadAnnotationTasks">刷新</n-button>
          </header>

          <div class="annotation-list">
            <div v-for="task in annotationTasks?.tasks.slice(0, 6)" :key="task.id" class="annotation-item">
              <img :src="resolveAssetUrl(task.image)" alt="待标注图" />
              <div>
                <strong>{{ taskClassNamesText(task) }}</strong>
                <small>{{ task.corrected.style || '样式未填' }} · {{ task.corrected.theme || '题材未填' }}</small>
                <small>{{ task.text || '无讲解文本' }}</small>
                <div class="task-correction-grid">
                  <n-auto-complete size="small" placeholder="颜色" :options="taxonomyOptionsFor('color')" :value="taskDraft(task).color" @update:value="value => updateTaskDraft(task, 'color', value)" />
                  <n-auto-complete size="small" placeholder="种水" :options="taxonomyOptionsFor('water')" :value="taskDraft(task).water" @update:value="value => updateTaskDraft(task, 'water', value)" />
                  <n-auto-complete size="small" placeholder="样式" :options="taxonomyOptionsFor('style')" :value="taskDraft(task).style" @update:value="value => updateTaskDraft(task, 'style', value)" />
                  <n-auto-complete size="small" placeholder="题材" :options="taxonomyOptionsFor('theme')" :value="taskDraft(task).theme" @update:value="value => updateTaskDraft(task, 'theme', value)" />
                </div>
                <div class="tag-row">
                  <n-tag size="tiny" :type="task.needs_review ? 'warning' : 'success'">
                    {{ task.needs_review ? '需复核' : '已校正' }}
                  </n-tag>
                  <n-tag v-if="task.training?.requires_manual_box" size="tiny" type="warning">待画框</n-tag>
                  <n-tag v-if="!task.classes.length" size="tiny" type="warning">待选类别</n-tag>
                  <n-tag v-if="task.training?.box_mode === 'whole-image'" size="tiny" type="info">整图框</n-tag>
                  <n-tag v-if="task.classes.length > 1" size="tiny" type="error">多类别需手动画框</n-tag>
                  <n-tag v-else-if="task.classes.length === 1" size="tiny" type="success">单类别可中心精框</n-tag>
                  <n-tag
                    v-for="item in taskSourceTags(task)"
                    :key="item.key"
                    size="tiny"
                    :type="sourceTagType(item.source)"
                  >
                    {{ item.label }}：{{ sourceLabel(item.source) }}
                  </n-tag>
                </div>
                <div v-if="taskClassOptions(task).length" class="manual-box-grid">
                  <span class="manual-box-label">类别</span>
                  <span class="manual-box-label">X</span>
                  <span class="manual-box-label">Y</span>
                  <span class="manual-box-label">宽</span>
                  <span class="manual-box-label">高</span>
                  <span class="manual-box-label">操作</span>
                  <select class="manual-box-input" :value="boxDraft(task).class_name" @change="event => updateBoxDraftClass(task, event)">
                    <option v-for="className in taskClassOptions(task)" :key="className" :value="className">{{ yoloClassLabel(className) }}</option>
                  </select>
                  <input class="manual-box-input" type="number" min="0" max="1" step="0.01" :value="boxDraft(task).x_center" @input="event => updateBoxDraftNumber(task, 'x_center', event)" />
                  <input class="manual-box-input" type="number" min="0" max="1" step="0.01" :value="boxDraft(task).y_center" @input="event => updateBoxDraftNumber(task, 'y_center', event)" />
                  <input class="manual-box-input" type="number" min="0.01" max="1" step="0.01" :value="boxDraft(task).width" @input="event => updateBoxDraftNumber(task, 'width', event)" />
                  <input class="manual-box-input" type="number" min="0.01" max="1" step="0.01" :value="boxDraft(task).height" @input="event => updateBoxDraftNumber(task, 'height', event)" />
                  <n-button size="tiny" secondary type="primary" :loading="annotationActionId === task.id" @click="saveManualBoxTask(task)">
                    保存手动画框
                  </n-button>
                </div>
                <div class="inline-actions annotation-actions">
                  <n-button size="tiny" secondary type="success" :loading="annotationActionId === task.id" @click="approveAndConfirmTask(task)">
                    确认并进 YOLO
                  </n-button>
                  <n-button
                    v-if="task.training?.requires_manual_box && task.classes.length && !task.needs_review"
                    size="tiny"
                    secondary
                    type="warning"
                    :loading="annotationActionId === task.id"
                    @click="confirmWholeImage(task.id)"
                  >
                    整图框进训练
                  </n-button>
                  <n-button v-if="task.classes.length === 1" size="tiny" secondary type="info" :loading="annotationActionId === task.id" @click="saveCenterBoxTask(task)">
                    中心精框入库
                  </n-button>
                  <n-button size="tiny" secondary type="error" :loading="annotationActionId === task.id" @click="rejectTask(task.id)">
                    丢弃
                  </n-button>
                </div>
              </div>
            </div>
            <div v-if="!annotationTasks?.tasks.length" class="empty-state compact">暂无待标注样本；请先上传翡翠样本或从直播帧保存反馈，再回来选类别并画主体框。</div>
          </div>
          <div v-if="annotationError" class="error-text">{{ annotationError }}</div>
        </article>
      </section>

      <section class="panel products-panel">
        <header class="panel-header">
          <div>
            <div class="panel-title">直播在售商品</div>
            <div class="transcript-meta">全部按在售处理，不再区分闲置</div>
          </div>
        </header>

        <div class="product-grid">
          <article v-for="product in products" :key="product.id" class="product-card">
            <img
              v-if="product.evidence_image_paths[0]"
              :src="resolveAssetUrl(product.evidence_image_paths[0])"
              alt="商品图"
            />
            <div class="product-card-body">
              <div class="product-title">{{ product.name || '翡翠商品' }}</div>
              <div class="product-attrs">
                {{ product.color || '颜色待识别' }} · {{ product.water || '种水待识别' }} · {{ product.style || product.category }}
              </div>
              <div class="transcript-meta">
                {{ product.theme ? `题材：${product.theme}` : '题材待识别' }} · 关键帧 {{ product.evidence_image_paths.length }}/3 · 讲解 {{ product.evidence_texts.length }} 条
              </div>
              <div class="class-count-row">
                <n-tag
                  v-for="item in productAttributeItems(product)"
                  :key="item.key"
                  size="tiny"
                  :type="sourceTagType(item.source)"
                >
                  {{ item.label }}：{{ item.value }} · {{ sourceLabel(item.source) }}{{ item.score ? ` ${item.score}` : '' }}
                </n-tag>
              </div>
              <div class="source-row">
                <n-tag
                  v-for="item in productSourceTags(product)"
                  :key="item.key"
                  size="tiny"
                  :type="sourceTagType(item.source)"
                >
                  {{ item.label }}：{{ sourceLabel(item.source) }}
                </n-tag>
              </div>
              <div class="product-correction-grid">
                <n-auto-complete size="small" placeholder="颜色" :options="taxonomyOptionsFor('color')" :value="productDraft(product).color" @update:value="value => updateProductDraft(product, 'color', value)" />
                <n-auto-complete size="small" placeholder="种水" :options="taxonomyOptionsFor('water')" :value="productDraft(product).water" @update:value="value => updateProductDraft(product, 'water', value)" />
                <n-auto-complete size="small" placeholder="样式" :options="taxonomyOptionsFor('style')" :value="productDraft(product).style" @update:value="value => updateProductDraft(product, 'style', value)" />
                <n-auto-complete size="small" placeholder="题材" :options="taxonomyOptionsFor('theme')" :value="productDraft(product).theme" @update:value="value => updateProductDraft(product, 'theme', value)" />
              </div>
              <n-button class="product-correction-button" size="tiny" secondary type="success" :loading="productCorrectionId === product.id" @click="submitProductCorrection(product)">
                保存纠错回流
              </n-button>
            </div>
          </article>
          <div v-if="!products.length" class="empty-state compact">暂无直播商品</div>
        </div>
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { NAutoComplete, NButton, NInput, NTag } from 'naive-ui'
import AppTopNav from '../components/AppTopNav.vue'
import {
  annotateProductJade,
  analyzeJadeSample,
  approveJadeAnnotationWholeImageBox,
  buildJadeTrainingDataset,
  confirmJadeAnnotationWholeImageBox,
  fetchJadeAnnotationTasks,
  fetchJadeModelStatus,
  fetchJadeTaxonomyOptions,
  fetchJadeTrainingRunStatus,
  fetchJadeTrainingStatus,
  fetchProducts,
  probeJadeVlm,
  reviewJadeAnnotationTask,
  resolveAssetUrl,
  runJadeEvaluation,
  saveJadeAnnotationBoxes,
  saveJadeVlmPrelabel,
  startJadeYoloTraining,
  submitJadeSampleFeedback,
} from '../api/jlao'
import type {
  JadeAnnotationTasks,
  JadeEvaluationResult,
  JadeModelStatus,
  JadeSampleAnalysis,
  JadeTaxonomyOptions,
  JadeTrainingRunStatus,
  JadeTrainingStatus,
  JadeVlmProbeResult,
  Product,
} from '../types'

const products = ref<Product[]>([])
const jadeModelStatus = ref<JadeModelStatus | null>(null)
const trainingStatus = ref<JadeTrainingStatus | null>(null)
const trainingRunStatus = ref<JadeTrainingRunStatus | null>(null)
const annotationTasks = ref<JadeAnnotationTasks | null>(null)
const taxonomyOptions = ref<JadeTaxonomyOptions | null>(null)

const loadingProducts = ref(false)
const loadingStatus = ref(false)
const runtimeError = ref('')
const vlmProbeLoading = ref(false)
const vlmProbeResult = ref<JadeVlmProbeResult | null>(null)
const vlmPrelabelSaving = ref(false)
const vlmPrelabelMessage = ref('')

const sampleFile = ref<File | null>(null)
const sampleText = ref('')
const sampleAnalysis = ref<JadeSampleAnalysis | null>(null)
const sampleLoading = ref(false)
const sampleError = ref('')
const feedbackSaving = ref(false)
const feedbackMessage = ref('')
const feedbackDraft = reactive({
  color: '',
  water: '',
  style: '',
  theme: '',
})

const trainingBuilding = ref(false)
const trainingStarting = ref(false)
const trainingPollTimer = ref<ReturnType<typeof setInterval> | null>(null)
const trainingMessage = ref('')
const trainingError = ref('')
const evaluationLoading = ref(false)
const evaluationResult = ref<JadeEvaluationResult | null>(null)
const evaluationError = ref('')
const annotationLoading = ref(false)
const annotationError = ref('')
const annotationActionId = ref('')
type JadeAttributeKey = 'color' | 'water' | 'style' | 'theme'
type JadeCorrectionDraft = Record<JadeAttributeKey, string>
type YoloBoxKey = 'x_center' | 'y_center' | 'width' | 'height'
type YoloBoxDraft = {
  class_name: string
  x_center: number
  y_center: number
  width: number
  height: number
}
type JadeAnnotationTask = JadeAnnotationTasks['tasks'][number]
const taskCorrectionDrafts = reactive<Record<string, JadeCorrectionDraft>>({})
const taskBoxDrafts = reactive<Record<string, YoloBoxDraft>>({})
const productCorrectionDrafts = reactive<Record<string, JadeCorrectionDraft>>({})
const productCorrectionId = ref('')
const PRODUCT_ATTRIBUTE_LABELS: Record<JadeAttributeKey, string> = {
  color: '颜色',
  water: '种水',
  style: '样式',
  theme: '题材',
}
const YOLO_CLASS_LABELS: Record<string, string> = {
  jade_bangle: '手镯',
  jade_beads: '珠串',
  jade_cabochon: '蛋面',
  jade_pendant: '吊坠',
  jade_ring: '戒指',
  jade_plaque: '挂件',
  pingan_kou: '平安扣',
  guanyin: '观音',
  buddha: '佛公',
  ruyi: '如意',
  leaf: '叶子',
  landscape: '山水',
  pixiu: '貔貅',
  gourd: '葫芦',
  jade_ornament: '摆件',
  caishen: '财神',
  dragon_plaque: '龙',
}

function yoloClassLabel(className: string) {
  return YOLO_CLASS_LABELS[className] || className
}

function taskClassOptions(task: JadeAnnotationTask) {
  return task.classes.length ? task.classes : Object.keys(YOLO_CLASS_LABELS)
}

function taskClassNamesText(task: JadeAnnotationTask) {
  return task.classes.length ? task.classes.map(yoloClassLabel).join(' / ') : '待选类别'
}

const yoloText = computed(() => {
  const yolo = jadeModelStatus.value?.yolo
  if (!yolo) return '状态读取中'
  if (yolo.enabled && yolo.model_kind === 'jade-trained') return '已使用翡翠训练模型'
  if (yolo.enabled && yolo.pretrained_fallback) return '使用通用 YOLO 兜底'
  return yolo.reason || '未启用'
})

const ocrText = computed(() => {
  const ocr = jadeModelStatus.value?.ocr
  if (!ocr) return '状态读取中'
  return ocr.enabled ? `已启用 ${ocr.languages.join('/')}` : ocr.reason
})

const vlmText = computed(() => {
  const vlm = jadeModelStatus.value?.vlm
  if (!vlm) return '状态读取中'
  const model = vlm.configured_model_path || vlm.default_http_model || ''
  const modelLabel = model ? ` · ${model}${vlm.using_default_http_model ? '（默认）' : '（配置）'}` : ''
  if (vlm.enabled) return `${vlm.source}${modelLabel}`
  return vlm.reason || '未启用'
})

const feedbackText = computed(() => {
  const learning = jadeModelStatus.value?.feedback_learning
  if (!learning) return '状态读取中'
  const total = Object.values(learning.rules || {}).reduce((sum, rules) => sum + Object.keys(rules).length, 0)
  return learning.enabled ? `${total} 条规则` : `阈值 ${learning.min_correction_count} 次`
})

const vlmDiagnosticText = computed(() => {
  const vlm = jadeModelStatus.value?.vlm
  if (!vlm || vlm.enabled) return ''
  const env = (vlm.required_env || [vlm.env]).join(' + ')
  const model = vlm.configured_model_path || vlm.default_http_model || ''
  const modelText = model ? `当前模型 ${model}；` : ''
  return `${modelText}${vlm.config_path || '本地后端 .env'} 可配置 ${env}；${vlm.install_hint || '通用 VLM 仅做预标注，需人工确认'}`
})

const vlmProbeSummary = computed(() => {
  const result = vlmProbeResult.value
  if (!result) return ''
  const runtime = result.runtime
  if (!runtime?.enabled) return `VLM 探测未启用：${runtime?.reason || result.status}`
  const attrs = result.attributes || {}
  const values = [attrs.color, attrs.water, attrs.style, attrs.theme].filter(Boolean)
  return values.length ? `VLM 输出：${values.join(' · ')}` : `VLM 已调用但未识别属性：${runtime.reason || result.status}`
})

const sampleAttributes = computed(() => {
  const attrs = sampleAnalysis.value?.attributes
  const sources = sampleAttributeSources.value
  return [
    { key: 'color', label: '颜色', value: attrs?.color || '', ...sourceBadge(sources.color) },
    { key: 'water', label: '种水', value: attrs?.water || '', ...sourceBadge(sources.water) },
    { key: 'style', label: '样式', value: attrs?.style || '', ...sourceBadge(sources.style) },
    { key: 'theme', label: '题材', value: attrs?.theme || '', ...sourceBadge(sources.theme) },
  ]
})

const sampleAttributeSources = computed(() => {
  const signals = sampleAnalysis.value?.signals || {}
  return (signals.attribute_sources || {}) as Record<string, Record<string, unknown>>
})

function sourceBadge(source: Record<string, unknown> | undefined) {
  const name = String(source?.source || '')
  const labels: Record<string, string> = {
    speech: 'STT主信号',
    yolo: 'YOLO',
    opencv: '图像弱补充',
    'local-vlm': 'VLM弱预标注',
    'image-context': '上下文补充',
    ocr: 'OCR弱补充',
    'feedback-learning': '人工规则',
    'live-frame-correction': '帧人工校正',
    'live-product-manual-annotation': '商品人工校正',
  }
  const types: Record<string, 'default' | 'success' | 'warning' | 'error' | 'info'> = {
    speech: 'success',
    yolo: 'success',
    opencv: 'warning',
    'local-vlm': 'warning',
    'image-context': 'info',
    ocr: 'warning',
    'feedback-learning': 'success',
    'live-frame-correction': 'success',
    'live-product-manual-annotation': 'success',
  }
  return {
    sourceLabel: labels[name] || '',
    sourceType: types[name] || 'default',
  }
}

const opencvCandidateItems = computed(() => {
  const signals = sampleAnalysis.value?.signals || {}
  const candidates = (signals.opencv_candidates || {}) as Record<string, unknown>
  const labels: Record<string, string> = {
    color: '颜色',
    water: '种水',
    style: '样式',
  }
  return Object.entries(labels)
    .map(([key, label]) => ({ key, label, value: String(candidates[key] || '') }))
    .filter(item => item.value)
})

const classCountItems = computed(() => {
  const counts = trainingStatus.value?.dataset.class_counts || {}
  return Object.entries(counts)
    .map(([name, count]) => ({ name, label: YOLO_CLASS_LABELS[name] || name, count: Number(count) || 0 }))
    .filter(item => item.count > 0)
    .sort((a, b) => b.count - a.count)
})

const missingClassText = computed(() => {
  if (!trainingStatus.value) return ''
  const counts = trainingStatus.value.dataset.class_counts || {}
  const missing = Object.entries(YOLO_CLASS_LABELS)
    .filter(([name]) => Number(counts[name] || 0) <= 0)
    .map(([, label]) => label)
  return missing.join('、')
})

function runtimeMinLabel(runtime: unknown, key: 'min_train_labels' | 'min_val_labels', fallback: number) {
  const value = runtime && typeof runtime === 'object' ? (runtime as Record<string, unknown>)[key] : undefined
  const numeric = Number(value ?? fallback)
  return Number.isFinite(numeric) ? numeric : fallback
}

const trainingMinTrainLabels = computed(() => runtimeMinLabel(trainingRunStatus.value?.runtime, 'min_train_labels', 10))
const trainingMinValLabels = computed(() => runtimeMinLabel(trainingRunStatus.value?.runtime, 'min_val_labels', 2))

const trainingGapText = computed(() => {
  const runtime = trainingRunStatus.value?.runtime
  if (!runtime) return ''
  const trainGap = Math.max(0, trainingMinTrainLabels.value - Number(runtime.train_labels || 0))
  const valGap = Math.max(0, trainingMinValLabels.value - Number(runtime.val_labels || 0))
  if (!trainGap && !valGap) return ''
  const parts = []
  if (trainGap) parts.push(`train 还差 ${trainGap} 条`)
  if (valGap) parts.push(`val 还差 ${valGap} 条`)
  return `距离可启动训练还差：${parts.join('，')}`
})

const sampleCollectionText = computed(() => {
  const runtime = trainingRunStatus.value?.runtime
  if (!runtime) return ''
  const trainGap = Math.max(0, trainingMinTrainLabels.value - Number(runtime.train_labels || 0))
  const valGap = Math.max(0, trainingMinValLabels.value - Number(runtime.val_labels || 0))
  const requiredBoxes = trainGap + valGap
  if (!requiredBoxes) return ''
  const taskCount = annotationTasks.value?.tasks.length ?? 0
  if (taskCount > 0) return `下一步：先在下方标注 ${Math.min(taskCount, requiredBoxes)} 个样本；仍需补 ${requiredBoxes} 个 YOLO 主体框。`
  return `下一步：至少再采集 ${requiredBoxes} 张翡翠图片反馈，并保存手动画框，才能启动本地 YOLO 训练。`
})

const annotationStatsText = computed(() => {
  const tasks = annotationTasks.value
  if (!tasks) return ''
  const parts = [`待标 ${tasks.task_count}`]
  if (tasks.no_class) parts.push(`待选类别 ${tasks.no_class}`)
  if (tasks.missing_image) parts.push(`缺图 ${tasks.missing_image}`)
  return parts.join(' · ')
})

const evaluationMetricItems = computed(() => {
  const metrics = evaluationResult.value?.metrics
  if (!metrics) return []
  const labels: Record<string, string> = {
    color: '颜色',
    water: '种水',
    style: '样式',
    theme: '题材',
  }
  return Object.entries(metrics).map(([key, value]) => ({
    key,
    label: labels[key] || key,
    correct: value.correct,
    total: value.total,
    accuracy: value.accuracy,
  }))
})

const evaluationHardCases = computed(() => {
  return (evaluationResult.value?.hard_cases || []).slice(0, 5)
})

const evaluationMissItems = computed(() => {
  const misses = evaluationResult.value?.misses
  if (!misses) return []
  const labels: Record<string, string> = {
    color: '颜色',
    water: '种水',
    style: '样式',
    theme: '题材',
  }
  return Object.entries(misses).flatMap(([attribute, rows]) =>
    (rows || []).slice(0, 3).map(row => ({
      attribute,
      label: labels[attribute] || attribute,
      pair: row.pair,
      count: row.count,
    }))
  )
})

onMounted(async () => {
  await Promise.all([loadProducts(), loadRuntime(), loadTrainingStatus(), loadTrainingRunStatus(), loadAnnotationTasks(), loadTaxonomyOptions()])
})

onBeforeUnmount(() => {
  stopTrainingPoll()
})

function runtimeEnabled(value: boolean | undefined) {
  if (value === undefined) return '读取中'
  return value ? '可用' : '未启用'
}

function confidenceText(value: number | undefined) {
  if (typeof value !== 'number') return '置信度未知'
  return `置信 ${Math.round(value * 100)}%`
}

function datasetAutoFixText(result: { auto_fix?: { moved?: number; val_labels_after?: number } } | null | undefined) {
  const moved = Number(result?.auto_fix?.moved || 0)
  if (!moved) return ''
  return `，自动补 val ${moved} 条，当前 val ${result?.auto_fix?.val_labels_after ?? 0} 条`
}

async function loadTaxonomyOptions() {
  try {
    taxonomyOptions.value = await fetchJadeTaxonomyOptions()
  } catch {
    taxonomyOptions.value = null
  }
}

function taxonomyOptionsFor(key: JadeAttributeKey) {
  const options = taxonomyOptions.value
  const values = key === 'color'
    ? options?.colors
    : key === 'water'
      ? options?.waters
      : key === 'style'
        ? options?.styles
        : options?.themes
  const fallback = key === 'color'
    ? ['帝王绿', '阳绿', '辣绿', '苹果绿', '豆绿', '绿色', '蓝水', '晴水', '油青', '紫罗兰', '春带彩', '白冰', '无色', '白底青', '飘花', '黄翡', '冰黄', '洒金', '墨翠', '红翡', '多彩']
    : key === 'water'
      ? ['玻璃种', '高冰', '冰种', '冰胶', '起冰', '冰糯', '糯冰', '起胶', '糯化', '细糯', '糯种', '豆种']
      : key === 'style'
        ? ['手镯', '珠串', '蛋面', '戒面', '戒指', '挂件', '吊坠', '平安扣', '摆件', '把件', '耳饰']
        : ['观音', '佛公', '如意', '叶子', '山水', '貔貅', '葫芦', '无事牌', '财神', '龙', '福瓜']
  return ((values?.length ? values : fallback) || []).map(value => ({ label: value, value }))
}

function productSourceTags(product: Product) {
  return (Object.keys(PRODUCT_ATTRIBUTE_LABELS) as JadeAttributeKey[])
    .filter(key => !!product[key])
    .map(key => ({
      key,
      label: PRODUCT_ATTRIBUTE_LABELS[key],
      source: product.attribute_sources?.[key]?.source || 'unknown',
    }))
}

function productAttributeItems(product: Product) {
  return (Object.keys(PRODUCT_ATTRIBUTE_LABELS) as JadeAttributeKey[])
    .filter(key => !!product[key])
    .map(key => ({
      key,
      label: PRODUCT_ATTRIBUTE_LABELS[key],
      value: String(product[key] || ''),
      source: product.attribute_sources?.[key]?.source || 'unknown',
      score: product.fusion_scores?.[key] ? Math.round(product.fusion_scores[key]) : 0,
    }))
}

function taskSourceTags(task: JadeAnnotationTask) {
  return (Object.keys(PRODUCT_ATTRIBUTE_LABELS) as JadeAttributeKey[])
    .filter(key => !!task.corrected?.[key])
    .map(key => ({
      key,
      label: PRODUCT_ATTRIBUTE_LABELS[key],
      source: task.attribute_sources?.[key]?.source || 'unknown',
    }))
}

function sourceLabel(source: string | undefined) {
  const value = source || 'unknown'
  const labels: Record<string, string> = {
    speech: 'STT讲解',
    yolo: 'YOLO',
    opencv: '图像启发',
    'local-vlm': 'VLM弱预标注',
    'feedback-learning': '人工校正规则',
    'live-frame-correction': '人工帧校正',
    'live-product-manual-annotation': '商品人工纠错',
    ocr: 'OCR弱补充',
    'image-context': '图像上下文',
    text: '文本',
    unknown: '未知来源',
  }
  return labels[value] || value
}

function sourceTagType(source: string | undefined) {
  if (
    source === 'speech'
    || source === 'yolo'
    || source === 'feedback-learning'
    || source === 'live-frame-correction'
    || source === 'live-product-manual-annotation'
  ) return 'success'
  if (source === 'ocr' || source === 'local-vlm' || source === 'opencv') return 'warning'
  return 'info'
}

async function loadProducts() {
  loadingProducts.value = true
  try {
    products.value = await fetchProducts()
  } finally {
    loadingProducts.value = false
  }
}

async function loadRuntime() {
  loadingStatus.value = true
  runtimeError.value = ''
  try {
    jadeModelStatus.value = await fetchJadeModelStatus()
  } catch (error) {
    runtimeError.value = error instanceof Error ? error.message : '模型状态读取失败'
  } finally {
    loadingStatus.value = false
  }
}

async function loadTrainingStatus() {
  try {
    trainingStatus.value = await fetchJadeTrainingStatus()
  } catch (error) {
    trainingError.value = error instanceof Error ? error.message : '训练状态读取失败'
  }
}

async function loadTrainingRunStatus() {
  try {
    trainingRunStatus.value = await fetchJadeTrainingRunStatus()
    if (trainingRunStatus.value.running) {
      startTrainingPoll()
    } else {
      stopTrainingPoll()
    }
  } catch (error) {
    trainingError.value = error instanceof Error ? error.message : '训练运行状态读取失败'
  }
}

function startTrainingPoll() {
  if (trainingPollTimer.value) return
  trainingPollTimer.value = setInterval(async () => {
    await loadTrainingRunStatus()
    if (!trainingRunStatus.value?.running) {
      await loadTrainingStatus()
      await loadRuntime()
    }
  }, 3000)
}

function stopTrainingPoll() {
  if (!trainingPollTimer.value) return
  clearInterval(trainingPollTimer.value)
  trainingPollTimer.value = null
}

async function loadAnnotationTasks() {
  annotationLoading.value = true
  annotationError.value = ''
  try {
    annotationTasks.value = await fetchJadeAnnotationTasks(80)
  } catch (error) {
    annotationError.value = error instanceof Error ? error.message : '标注任务读取失败'
  } finally {
    annotationLoading.value = false
  }
}

function taskDraft(task: JadeAnnotationTask) {
  if (!taskCorrectionDrafts[task.id]) {
    taskCorrectionDrafts[task.id] = {
      color: task.corrected.color || '',
      water: task.corrected.water || '',
      style: task.corrected.style || '',
      theme: task.corrected.theme || '',
    }
  }
  return taskCorrectionDrafts[task.id]
}

function updateTaskDraft(task: JadeAnnotationTask, key: JadeAttributeKey, value: string) {
  taskDraft(task)[key] = value
}

function boxDraft(task: JadeAnnotationTask) {
  if (!taskBoxDrafts[task.id]) {
    taskBoxDrafts[task.id] = {
      class_name: task.classes[0] || Object.keys(YOLO_CLASS_LABELS)[0] || '',
      x_center: 0.5,
      y_center: 0.5,
      width: 0.8,
      height: 0.8,
    }
  }
  return taskBoxDrafts[task.id]
}

function updateBoxDraftClass(task: JadeAnnotationTask, event: Event) {
  boxDraft(task).class_name = (event.target as HTMLSelectElement).value
}

function updateBoxDraftNumber(task: JadeAnnotationTask, key: YoloBoxKey, event: Event) {
  const raw = Number((event.target as HTMLInputElement).value)
  const min = key === 'width' || key === 'height' ? 0.01 : 0
  const value = Number.isFinite(raw) ? Math.min(1, Math.max(min, raw)) : boxDraft(task)[key]
  boxDraft(task)[key] = Number(value.toFixed(3))
}

function validateYoloBoxDraft(draft: YoloBoxDraft) {
  const values = [draft.x_center, draft.y_center, draft.width, draft.height]
  if (values.some(value => !Number.isFinite(value) || value < 0 || value > 1)) return '框坐标必须在 0-1 之间'
  if (draft.width < 0.03 || draft.height < 0.03) return '框太小，宽高都至少 0.03'
  if (draft.width > 0.98 || draft.height > 0.98) return '框太大，宽高不能超过 0.98'
  const area = draft.width * draft.height
  if (area < 0.01) return '框面积太小'
  if (area > 0.92) return '框面积太大'
  if (draft.x_center - draft.width / 2 < 0 || draft.x_center + draft.width / 2 > 1) return '框横向越界'
  if (draft.y_center - draft.height / 2 < 0 || draft.y_center + draft.height / 2 > 1) return '框纵向越界'
  return ''
}

function productDraft(product: Product) {
  if (!productCorrectionDrafts[product.id]) {
    productCorrectionDrafts[product.id] = {
      color: product.color || '',
      water: product.water || '',
      style: product.style || '',
      theme: product.theme || '',
    }
  }
  return productCorrectionDrafts[product.id]
}

function updateProductDraft(product: Product, key: JadeAttributeKey, value: string) {
  productDraft(product)[key] = value
}

async function runVlmProbe() {
  vlmProbeResult.value = null
  if (!sampleFile.value) {
    runtimeError.value = '先在样图识别里上传一张翡翠图片，再探测 VLM'
    return
  }
  vlmProbeLoading.value = true
  runtimeError.value = ''
  try {
    vlmProbeResult.value = await probeJadeVlm({ file: sampleFile.value, text: sampleText.value })
  } catch (error) {
    runtimeError.value = error instanceof Error ? error.message : 'VLM 探测失败'
  } finally {
    vlmProbeLoading.value = false
  }
}

async function saveVlmPrelabel() {
  vlmPrelabelMessage.value = ''
  if (!sampleFile.value) {
    runtimeError.value = '先在样图识别里上传一张翡翠图片，再做 VLM 预标注'
    return
  }
  vlmPrelabelSaving.value = true
  runtimeError.value = ''
  try {
    const result = await saveJadeVlmPrelabel({ file: sampleFile.value, text: sampleText.value })
    if (result.status !== 'ok') {
      vlmPrelabelMessage.value = result.message || 'VLM 没有返回可用属性，未写入待确认'
      return
    }
    const attrs = result.attributes || {}
    const values = [attrs.color, attrs.water, attrs.style, attrs.theme].filter(Boolean)
    vlmPrelabelMessage.value = `已生成待确认预标注：${values.join(' · ') || result.id}`
    await loadTrainingStatus()
    await loadAnnotationTasks()
  } catch (error) {
    runtimeError.value = error instanceof Error ? error.message : 'VLM 预标注保存失败'
  } finally {
    vlmPrelabelSaving.value = false
  }
}

function handleSampleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  sampleFile.value = input.files?.[0] || null
}

async function runSampleAnalysis() {
  sampleError.value = ''
  feedbackMessage.value = ''
  if (!sampleFile.value && !sampleText.value.trim()) {
    sampleError.value = '请上传图片或填写主播讲解文本'
    return
  }
  sampleLoading.value = true
  try {
    sampleAnalysis.value = await analyzeJadeSample({ file: sampleFile.value, text: sampleText.value })
    feedbackDraft.color = sampleAnalysis.value.attributes.color || ''
    feedbackDraft.water = sampleAnalysis.value.attributes.water || ''
    feedbackDraft.style = sampleAnalysis.value.attributes.style || ''
    feedbackDraft.theme = sampleAnalysis.value.attributes.theme || ''
  } catch (error) {
    sampleError.value = error instanceof Error ? error.message : '样图识别失败'
  } finally {
    sampleLoading.value = false
  }
}

async function submitFeedback() {
  if (!sampleAnalysis.value) return
  feedbackSaving.value = true
  feedbackMessage.value = ''
  try {
    const result = await submitJadeSampleFeedback({
      input: sampleAnalysis.value.input,
      predicted: sampleAnalysis.value.attributes,
      corrected: { ...feedbackDraft },
      evidence: sampleAnalysis.value.evidence,
      confidence: sampleAnalysis.value.confidence,
      attribute_sources: (sampleAnalysis.value.signals.attribute_sources || {}) as Record<string, unknown>,
    })
    feedbackMessage.value = result.dataset
      ? `已保存校正并进入 YOLO 数据集：写入 ${result.dataset.written} 条${datasetAutoFixText(result.dataset)}`
      : `已保存校正：${result.id}`
    await loadTrainingStatus()
    await loadTrainingRunStatus()
    await loadAnnotationTasks()
  } catch (error) {
    feedbackMessage.value = error instanceof Error ? error.message : '校正保存失败'
  } finally {
    feedbackSaving.value = false
  }
}

async function buildTrainingDataset() {
  trainingBuilding.value = true
  trainingMessage.value = ''
  trainingError.value = ''
  try {
    const result = await buildJadeTrainingDataset({ split: 'train', val_every: 5, write_yaml: true })
    trainingMessage.value = `已生成训练集：写入 ${result.written} 条，人工精框 ${result.manual_box ?? 0} 条，待画框 ${result.requires_manual_box ?? 0} 条${datasetAutoFixText(result)}`
    await loadTrainingStatus()
    await loadTrainingRunStatus()
  } catch (error) {
    trainingError.value = error instanceof Error ? error.message : '训练集生成失败'
  } finally {
    trainingBuilding.value = false
  }
}

async function runLocalEvaluation() {
  evaluationLoading.value = true
  evaluationError.value = ''
  try {
    evaluationResult.value = await runJadeEvaluation({ limit: 50 })
  } catch (error) {
    evaluationError.value = error instanceof Error ? error.message : '识别评估失败'
  } finally {
    evaluationLoading.value = false
  }
}

async function startLocalTraining() {
  trainingStarting.value = true
  trainingMessage.value = ''
  trainingError.value = ''
  try {
    trainingRunStatus.value = await startJadeYoloTraining({ epochs: 50, imgsz: 640, batch: 'auto', model: 'yolo11n.pt' })
    trainingMessage.value = trainingRunStatus.value.running
      ? `本地 YOLO 训练已启动：PID ${trainingRunStatus.value.pid}`
      : '本地 YOLO 训练状态已刷新'
    if (trainingRunStatus.value.running) startTrainingPoll()
    await loadTrainingStatus()
  } catch (error) {
    trainingError.value = error instanceof Error ? error.message : '本地 YOLO 训练启动失败'
  } finally {
    trainingStarting.value = false
  }
}

async function confirmWholeImage(taskId: string) {
  annotationActionId.value = taskId
  annotationError.value = ''
  try {
    await confirmJadeAnnotationWholeImageBox(taskId)
    await loadTrainingStatus()
    await loadTrainingRunStatus()
    await loadAnnotationTasks()
  } catch (error) {
    annotationError.value = error instanceof Error ? error.message : '整图框确认失败'
  } finally {
    annotationActionId.value = ''
  }
}

async function approveAndConfirmTask(task: JadeAnnotationTask) {
  annotationActionId.value = task.id
  annotationError.value = ''
  try {
    const result = await approveJadeAnnotationWholeImageBox(task.id, { ...taskDraft(task) })
    trainingMessage.value = `已确认进 YOLO 数据集：写入 ${result.dataset?.written ?? 0} 条，待画框 ${result.dataset?.requires_manual_box ?? 0} 条${datasetAutoFixText(result.dataset)}`
    await loadTrainingStatus()
    await loadTrainingRunStatus()
    await loadAnnotationTasks()
  } catch (error) {
    annotationError.value = error instanceof Error ? error.message : '确认进 YOLO 失败'
  } finally {
    annotationActionId.value = ''
  }
}

async function saveCenterBoxTask(task: JadeAnnotationTask) {
  if (task.classes.length !== 1) {
    annotationError.value = '多类别样本不能使用中心精框，请后续使用手动画框'
    return
  }
  annotationActionId.value = task.id
  annotationError.value = ''
  try {
    await saveJadeAnnotationBoxes(
      task.id,
      task.classes.map(className => ({
        class_name: className,
        x_center: 0.5,
        y_center: 0.5,
        width: 0.8,
        height: 0.8,
      }))
    )
    trainingMessage.value = '已按中心 80% 主体框保存为人工精框'
    await buildTrainingDataset()
    await loadTrainingStatus()
    await loadAnnotationTasks()
  } catch (error) {
    annotationError.value = error instanceof Error ? error.message : '中心精框保存失败'
  } finally {
    annotationActionId.value = ''
  }
}

async function saveManualBoxTask(task: JadeAnnotationTask) {
  const draft = boxDraft(task)
  if (!draft.class_name) {
    annotationError.value = '请先选择一个 YOLO 类别'
    return
  }
  const validationError = validateYoloBoxDraft(draft)
  if (validationError) {
    annotationError.value = validationError
    return
  }
  annotationActionId.value = task.id
  annotationError.value = ''
  try {
    await saveJadeAnnotationBoxes(task.id, [{ ...draft }])
    trainingMessage.value = `已保存手动画框：${draft.class_name}`
    await buildTrainingDataset()
    await loadTrainingStatus()
    await loadTrainingRunStatus()
    await loadAnnotationTasks()
  } catch (error) {
    annotationError.value = error instanceof Error ? error.message : '手动画框保存失败'
  } finally {
    annotationActionId.value = ''
  }
}

async function rejectTask(taskId: string) {
  annotationActionId.value = taskId
  annotationError.value = ''
  try {
    await reviewJadeAnnotationTask(taskId, 'reject')
    await loadTrainingStatus()
    await loadAnnotationTasks()
  } catch (error) {
    annotationError.value = error instanceof Error ? error.message : '样本丢弃失败'
  } finally {
    annotationActionId.value = ''
  }
}

async function submitProductCorrection(product: Product) {
  productCorrectionId.value = product.id
  runtimeError.value = ''
  try {
    const result = await annotateProductJade(product.id, { ...productDraft(product) })
    trainingMessage.value = result.dataset
      ? `商品纠错已回流 YOLO 数据集：写入 ${result.dataset.written} 条${datasetAutoFixText(result.dataset)}`
      : `商品纠错已保存：${result.feedback_id}`
    productCorrectionDrafts[product.id] = {
      color: result.product.color || '',
      water: result.product.water || '',
      style: result.product.style || '',
      theme: result.product.theme || '',
    }
    await loadProducts()
    await loadTrainingStatus()
    await loadTrainingRunStatus()
    await loadRuntime()
  } catch (error) {
    runtimeError.value = error instanceof Error ? error.message : '商品纠错保存失败'
  } finally {
    productCorrectionId.value = ''
  }
}

function clearSample() {
  sampleFile.value = null
  sampleText.value = ''
  sampleAnalysis.value = null
  sampleError.value = ''
  feedbackMessage.value = ''
  vlmProbeResult.value = null
  vlmPrelabelMessage.value = ''
  feedbackDraft.color = ''
  feedbackDraft.water = ''
  feedbackDraft.style = ''
  feedbackDraft.theme = ''
}
</script>

<style scoped>
.product-page {
  display: grid;
  gap: 18px;
  height: auto;
}

.hero-panel,
.panel {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 24px;
  background: linear-gradient(135deg, rgba(255, 253, 247, 0.98), rgba(239, 248, 232, 0.92));
  box-shadow: 0 20px 60px rgba(23, 53, 31, 0.08);
}

.hero-panel {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 26px;
  background:
    radial-gradient(circle at 82% 18%, rgba(34, 211, 166, 0.22), transparent 26%),
    linear-gradient(135deg, #fffdf7 0%, #eaf7e5 100%);
}

.eyebrow {
  margin: 0 0 8px;
  color: #16835f;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.14em;
}

h1 {
  margin: 0;
  color: #17351f;
  font-size: 34px;
}

.hero-copy {
  max-width: 760px;
  margin: 10px 0 0;
  color: rgba(15, 23, 42, 0.64);
  line-height: 1.6;
}

.hero-actions,
.inline-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.grid {
  display: grid;
  gap: 18px;
}

.grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.panel {
  padding: 18px;
}

.runtime-grid,
.metric-grid,
.attr-grid,
.feedback-grid,
.task-correction-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  margin-top: 8px;
}

.manual-box-grid {
  display: grid;
  grid-template-columns: 1.2fr repeat(4, 0.72fr) auto;
  gap: 6px;
  margin-top: 8px;
  align-items: center;
}

.manual-box-input {
  width: 100%;
  min-width: 0;
  padding: 6px 7px;
  border: 1px solid rgba(15, 23, 42, 0.14);
  border-radius: 9px;
  color: #17351f;
  background: rgba(255, 255, 255, 0.9);
  font-size: 12px;
}

.manual-box-label {
  color: rgba(15, 23, 42, 0.52);
  font-size: 11px;
  font-weight: 800;
}

.annotation-actions {
  margin-top: 8px;
}

.product-grid {
  display: grid;
  gap: 12px;
}

.runtime-grid {
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin: 16px 0;
}

.runtime-card,
.metric-grid > div,
.attr-grid > div {
  padding: 13px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.68);
}

.runtime-card.ok {
  border-color: rgba(22, 101, 52, 0.18);
  background: #f1f8ed;
}

.runtime-card span,
.metric-grid span,
.attr-grid span {
  display: block;
  color: rgba(15, 23, 42, 0.56);
  font-size: 12px;
}

.runtime-card strong,
.metric-grid strong,
.attr-grid strong {
  display: block;
  margin: 5px 0;
  color: #17351f;
  font-size: 18px;
}

.runtime-card small {
  color: rgba(15, 23, 42, 0.55);
  font-size: 12px;
  word-break: break-all;
}

.callout {
  margin-top: 12px;
  padding: 11px 12px;
  border: 1px solid rgba(14, 116, 144, 0.14);
  border-radius: 14px;
  color: #164e63;
  background: #ecfeff;
  font-size: 13px;
}

.callout.warning {
  color: #7c2d12;
  border-color: rgba(180, 83, 9, 0.2);
  background: #fff7ed;
}

.callout.success {
  color: #166534;
  border-color: rgba(22, 101, 52, 0.16);
  background: #f0fdf4;
}

.error-text {
  margin-top: 10px;
  color: #b91c1c;
  font-size: 13px;
}

.sample-form {
  display: grid;
  gap: 12px;
}

.file-input {
  width: 100%;
  padding: 10px;
  border: 1px dashed rgba(15, 23, 42, 0.2);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
}

.analysis-result {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.analysis-result img {
  width: 100%;
  max-height: 300px;
  object-fit: cover;
  border-radius: 16px;
}

.result-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.attr-grid,
.feedback-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.metric-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin: 14px 0;
}

.training-run-card {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.training-run-card > div {
  padding: 11px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.68);
}

.training-run-card span {
  display: block;
  color: rgba(15, 23, 42, 0.56);
  font-size: 12px;
}

.training-run-card strong {
  display: block;
  margin-top: 5px;
  color: #17351f;
}

.training-log {
  max-height: 170px;
  overflow: auto;
  margin: 12px 0 0;
  padding: 12px;
  border-radius: 14px;
  color: #dbeafe;
  background: #0f172a;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.class-count-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.eval-metric-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.eval-recommendations {
  margin-top: 10px;
  color: rgba(15, 23, 42, 0.72);
  line-height: 1.6;
}

.eval-miss-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.eval-hard-cases {
  display: grid;
  gap: 6px;
  margin-top: 10px;
}

.eval-hard-case {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 9px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.58);
  font-size: 12px;
}

.eval-hard-case img {
  width: 42px;
  height: 42px;
  object-fit: cover;
  border-radius: 8px;
  background: #f6f3ec;
}

.eval-hard-case strong {
  display: block;
  color: #7c2d12;
}

.eval-hard-case span {
  display: block;
  margin-top: 3px;
}

.annotation-list {
  display: grid;
  gap: 10px;
}

.annotation-item {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: 10px;
  padding: 10px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.72);
}

.annotation-item img {
  width: 92px;
  height: 92px;
  object-fit: cover;
  border-radius: 12px;
}

.annotation-item strong,
.annotation-item small {
  display: block;
}

.annotation-item strong {
  color: #17351f;
  font-size: 13px;
}

.annotation-item small {
  margin-top: 4px;
  color: rgba(15, 23, 42, 0.58);
  font-size: 12px;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin: 7px 0;
}

.task-correction-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  margin-top: 8px;
}

.annotation-actions {
  margin-top: 8px;
}

.product-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.product-card {
  overflow: hidden;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.76);
}

.product-card img {
  width: 100%;
  height: 145px;
  object-fit: cover;
  background: #f6f3ec;
}

.product-card-body {
  padding: 13px;
}

.product-title {
  color: #17351f;
  font-weight: 800;
}

.product-attrs {
  margin-top: 8px;
  color: rgba(15, 23, 42, 0.72);
  font-size: 13px;
}

.source-row {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 8px;
}

.product-correction-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  margin-top: 10px;
}

.product-correction-button {
  margin-top: 8px;
}

.empty-state.compact {
  padding: 18px;
  border: 1px dashed rgba(15, 23, 42, 0.16);
  border-radius: 16px;
  color: rgba(15, 23, 42, 0.54);
  text-align: center;
}

@media (max-width: 1100px) {
  .grid.two,
  .task-correction-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  margin-top: 8px;
}

.annotation-actions {
  margin-top: 8px;
}

.product-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .runtime-grid,
  .metric-grid,
  .training-run-card,
  .attr-grid,
  .feedback-grid,
  .task-correction-grid,
  .manual-box-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .hero-panel,
  .grid.two,
  .product-grid,
  .runtime-grid,
  .metric-grid,
  .training-run-card,
  .attr-grid,
  .feedback-grid,
  .task-correction-grid,
  .manual-box-grid {
    grid-template-columns: 1fr;
  }

  .hero-panel {
    display: grid;
  }
}
</style>


