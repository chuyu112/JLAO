<template>
  <main class="page annotation-workbench-page">
    <app-top-nav title="人工标注工作台" subtitle="直播截图 / AI 扩增图 · YOLO 主体框精标" />

    <section class="toolbar">
      <div class="toolbar-group">
        <span class="toolbar-label">任务数</span>
        <n-input-number v-model:value="limit" size="small" :min="20" :max="500" :step="20" />
        <n-button size="small" type="primary" :loading="loading" @click="loadTasks">刷新任务</n-button>
        <n-button size="small" secondary type="success" :loading="building" @click="buildDataset">重建训练集</n-button>
        <n-button size="small" secondary :disabled="!canGoPrevious" @click="goPrevious">上一个</n-button>
        <n-button size="small" secondary :disabled="!canGoNext" @click="goNext">下一个</n-button>
      </div>
      <div class="toolbar-meta">
        <n-tag size="small" type="info">任务 {{ tasks.length }}</n-tag>
        <n-tag size="small" type="warning">待复核 {{ summary?.pending_review ?? 0 }}</n-tag>
        <n-tag size="small" type="success">人工框 {{ manualBoxCount }}</n-tag>
      </div>
    </section>

    <section v-if="error" class="status-line error">{{ error }}</section>
    <section v-if="message" class="status-line success">{{ message }}</section>

    <section class="workbench-grid">
      <aside class="task-queue">
        <header>
          <strong>标注队列</strong>
          <span>{{ queueHint }}</span>
        </header>
        <button
          v-for="task in tasks"
          :key="task.id"
          class="task-row"
          :class="{ active: task.id === selectedTask?.id }"
          type="button"
          @click="selectTask(task)"
        >
          <img :src="resolveAssetUrl(task.image)" alt="" />
          <span>
            <strong>{{ taskClassText(task) }}</strong>
            <small>{{ task.corrected.style || '款式未选' }} · {{ task.corrected.theme || task.corrected.craft || '题材/工艺未选' }}</small>
            <small>{{ task.training?.box_mode === 'manual-box' ? '已有人工框' : task.status }}</small>
          </span>
        </button>
      </aside>

      <section class="canvas-panel">
        <div v-if="selectedTask" class="canvas-header">
          <div>
            <strong>{{ taskClassText(selectedTask) }}</strong>
            <span>{{ selectedTask.text || '无讲解文本' }}</span>
          </div>
          <div class="canvas-actions">
            <n-button size="small" secondary :disabled="!canGoPrevious" @click="goPrevious">上一个</n-button>
            <n-button size="small" secondary :disabled="!canGoNext" @click="goNext">下一个</n-button>
            <n-tag size="small" type="info">{{ classLabel(selectedClass) }}</n-tag>
            <n-button size="small" secondary @click="addCenterBox">中心框</n-button>
            <n-button size="small" secondary :disabled="!boxes.length" @click="undoLastBox">撤回画框</n-button>
            <n-button size="small" secondary type="error" :disabled="selectedBoxIndex < 0" @click="deleteSelectedBox">删除框</n-button>
            <n-button size="small" type="primary" :loading="saving" @click="saveCurrentTask">保存标注</n-button>
          </div>
        </div>

        <div v-if="selectedTask" class="image-stage-shell">
          <div
            ref="stageRef"
            class="image-stage"
            @pointerdown="beginDraw"
            @pointermove="moveDraw"
            @pointerup="finishDraw"
            @pointercancel="cancelDraw"
            @pointerleave="cancelDraw"
          >
            <img :src="resolveAssetUrl(selectedTask.image)" draggable="false" alt="待标注图" />
            <div
              v-for="(box, index) in boxes"
              :key="`${box.class_name}-${index}`"
              class="drawn-box"
              :class="{ selected: selectedBoxIndex === index }"
              :style="boxStyle(box)"
            >
              <span>{{ classLabel(box.class_name) }}</span>
            </div>
            <div v-if="previewBox" class="drawn-box preview" :style="boxStyle(previewBox)">
              <span>{{ classLabel(previewBox.class_name) }}</span>
            </div>
          </div>
        </div>

        <div v-else class="empty-state">暂无可标注任务。先采集真实图或保存识别反馈，再刷新任务。</div>
      </section>

      <aside class="box-panel">
        <header>
          <strong>当前框</strong>
          <span>拖拽图片即可新增</span>
        </header>

        <div v-if="selectedTask" class="task-meta">
          <n-tag size="small" :type="selectedTask.needs_review ? 'warning' : 'success'">
            {{ selectedTask.needs_review ? '需复核' : '已确认' }}
          </n-tag>
          <n-tag v-if="selectedTask.training?.requires_manual_box" size="small" type="warning">需精框</n-tag>
          <n-tag v-if="selectedTask.training?.box_mode" size="small" type="info">{{ selectedTask.training.box_mode }}</n-tag>
        </div>

        <div v-if="selectedTask" class="attribute-form">
          <label>
            <span>颜色</span>
            <div class="option-grid">
              <button
                v-for="option in taxonomySelectOptions.colors"
                :key="option.value"
                type="button"
                class="option-chip"
                :class="{ active: attributeDraft.color === option.value }"
                @click="selectAttribute('color', option.value)"
              >
                {{ option.label }}
              </button>
            </div>
          </label>
          <label>
            <span>种水</span>
            <div class="option-grid">
              <button
                v-for="option in taxonomySelectOptions.waters"
                :key="option.value"
                type="button"
                class="option-chip"
                :class="{ active: attributeDraft.water === option.value }"
                @click="selectAttribute('water', option.value)"
              >
                {{ option.label }}
              </button>
            </div>
          </label>
          <label>
            <span>款式</span>
            <div class="option-grid">
              <button
                v-for="option in taxonomySelectOptions.styles"
                :key="option.value"
                type="button"
                class="option-chip"
                :class="{ active: attributeDraft.style === option.value }"
                @click="selectAttribute('style', option.value)"
              >
                {{ option.label }}
              </button>
            </div>
          </label>
          <label v-if="attributeDraft.style === '吊坠'">
            <span>题材</span>
            <div class="option-grid">
              <button
                v-for="option in taxonomySelectOptions.themes"
                :key="option.value"
                type="button"
                class="option-chip"
                :class="{ active: attributeDraft.theme === option.value }"
                @click="selectAttribute('theme', option.value)"
              >
                {{ option.label }}
              </button>
            </div>
          </label>
          <label>
            <span>工艺</span>
            <div class="option-grid">
              <button
                v-for="option in taxonomySelectOptions.crafts"
                :key="option.value"
                type="button"
                class="option-chip"
                :class="{ active: attributeDraft.craft === option.value }"
                @click="selectAttribute('craft', option.value)"
              >
                {{ option.label }}
              </button>
            </div>
          </label>
        </div>

        <div v-if="selectedTask" class="negative-panel">
          <strong>无可标注</strong>
          <span>选中原因后保存，样本进入负样本池，不进翡翠框训练集。</span>
          <div class="option-grid">
            <button
              v-for="reason in negativeReasons"
              :key="reason"
              type="button"
              class="option-chip negative"
              :class="{ active: negativeReason === reason }"
              @click="toggleNegativeReason(reason)"
            >
              {{ reason }}
            </button>
          </div>
        </div>

        <div class="box-list">
          <div
            v-for="(box, index) in boxes"
            :key="index"
            class="box-row"
            :class="{ selected: selectedBoxIndex === index }"
            @click="selectedBoxIndex = index"
          >
            <n-select
              :value="box.class_name"
              size="small"
              :options="classOptions"
              @update:value="value => setBoxClass(index, String(value || ''))"
            />
            <div class="box-numbers">
              <span>x {{ box.x_center.toFixed(3) }}</span>
              <span>y {{ box.y_center.toFixed(3) }}</span>
              <span>w {{ box.width.toFixed(3) }}</span>
              <span>h {{ box.height.toFixed(3) }}</span>
            </div>
            <n-button size="tiny" secondary type="error" @click.stop="removeBox(index)">删除</n-button>
          </div>
          <div v-if="!boxes.length" class="empty-state compact">还没有主体框。</div>
        </div>

        <div v-if="selectedTask" class="side-actions">
          <n-button secondary :disabled="!canGoPrevious" @click="goPrevious">上一个</n-button>
          <n-button secondary :disabled="!canGoNext" @click="goNext">下一个</n-button>
          <n-button secondary :disabled="!boxes.length" @click="undoLastBox">撤回画框</n-button>
          <n-button secondary type="error" :disabled="selectedBoxIndex < 0" @click="deleteSelectedBox">删除框</n-button>
          <n-button type="primary" :loading="saving" @click="saveCurrentTask">保存</n-button>
          <n-button secondary type="warning" :loading="saving" :disabled="!negativeReason" @click="saveCurrentTask">
            保存无可标注
          </n-button>
        </div>
      </aside>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NInputNumber, NSelect, NTag, useMessage } from 'naive-ui'
import AppTopNav from '../components/AppTopNav.vue'
import {
  buildJadeTrainingDataset,
  fetchJadeAnnotationTasks,
  fetchJadeTaxonomyOptions,
  fetchJadeTrainingStatus,
  reviewJadeAnnotationTask,
  resolveAssetUrl,
  saveJadeAnnotationBoxes,
} from '../api/jlao'
import type { JadeAnnotationTasks, JadeTaxonomyOptions, JadeTrainingStatus } from '../types'

type AnnotationTask = JadeAnnotationTasks['tasks'][number]
type YoloBox = {
  class_name: string
  x_center: number
  y_center: number
  width: number
  height: number
}
type AttributeKey = 'color' | 'water' | 'style' | 'theme' | 'craft'
type AttributeDraft = {
  color: string
  water: string
  style: string
  theme: string
  craft: string
}
type DrawState = {
  startX: number
  startY: number
  currentX: number
  currentY: number
  pointerId: number
}

const CLASS_LABELS: Record<string, string> = {
  jade_bangle: '手镯',
  jade_beads: '珠串',
  jade_necklace: '珠链',
  jade_cabochon: '蛋面',
  jade_pendant: '吊坠',
  jade_ring: '戒指',
  jade_plaque: '吊坠',
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
  dragon_plaque: '龙牌',
  fu_gua: '福瓜',
  fu_dou: '福豆',
  jade_earring: '耳饰',
}

const STYLE_CLASS_BY_VALUE: Record<string, string> = {
  手镯: 'jade_bangle',
  珠串: 'jade_beads',
  珠链: 'jade_necklace',
  蛋面: 'jade_cabochon',
  戒指: 'jade_ring',
  吊坠: 'jade_pendant',
  耳饰: 'jade_earring',
  摆件: 'jade_ornament',
}

const THEME_CLASS_BY_VALUE: Record<string, string> = {
  观音: 'guanyin',
  佛公: 'buddha',
  平安扣: 'pingan_kou',
  如意: 'ruyi',
  叶子: 'leaf',
  山水: 'landscape',
  貔貅: 'pixiu',
  葫芦: 'gourd',
  无事牌: 'jade_plaque',
  财神: 'caishen',
  龙牌: 'dragon_plaque',
  福瓜: 'fu_gua',
  福豆: 'fu_dou',
}

const ATTRIBUTE_BY_CLASS: Record<string, Partial<Pick<AttributeDraft, 'style' | 'theme'>>> = {
  jade_bangle: { style: '手镯' },
  jade_beads: { style: '珠串' },
  jade_necklace: { style: '珠链' },
  jade_cabochon: { style: '蛋面' },
  jade_ring: { style: '戒指' },
  jade_pendant: { style: '吊坠' },
  jade_earring: { style: '耳饰' },
  jade_ornament: { style: '摆件' },
  jade_plaque: { style: '吊坠', theme: '无事牌' },
  pingan_kou: { style: '吊坠', theme: '平安扣' },
  guanyin: { style: '吊坠', theme: '观音' },
  buddha: { style: '吊坠', theme: '佛公' },
  ruyi: { style: '吊坠', theme: '如意' },
  leaf: { style: '吊坠', theme: '叶子' },
  landscape: { style: '吊坠', theme: '山水' },
  pixiu: { style: '吊坠', theme: '貔貅' },
  gourd: { style: '吊坠', theme: '葫芦' },
  caishen: { style: '吊坠', theme: '财神' },
  dragon_plaque: { style: '吊坠', theme: '龙牌' },
  fu_gua: { style: '吊坠', theme: '福瓜' },
  fu_dou: { style: '吊坠', theme: '福豆' },
}

const negativeReasons = [
  '图里没有翡翠',
  '画面太糊看不清',
  '主体太小',
  '主体被遮挡',
  '被手遮挡',
  '被字幕/弹幕遮挡',
  '只有包装/证书/桌面',
  '多件货混在一起',
  '无法确定主商品',
  '颜色无法100%判断',
  '种水无法100%判断',
  '款式无法100%判断',
  '题材无法100%判断',
  '工艺无法100%判断',
  '图片重复',
  '截图异常/黑屏/花屏',
  '非翡翠商品',
]

const messageApi = useMessage()
const limit = ref(120)
const loading = ref(false)
const saving = ref(false)
const building = ref(false)
const error = ref('')
const message = ref('')
const summary = ref<JadeAnnotationTasks | null>(null)
const trainingStatus = ref<JadeTrainingStatus | null>(null)
const taxonomy = ref<JadeTaxonomyOptions | null>(null)
const tasks = ref<AnnotationTask[]>([])
const selectedId = ref('')
const boxes = ref<YoloBox[]>([])
const selectedBoxIndex = ref(-1)
const attributeDraft = ref<AttributeDraft>({ color: '', water: '', style: '', theme: '', craft: '' })
const negativeReason = ref('')
const selectedClass = ref('jade_bangle')
const stageRef = ref<HTMLElement | null>(null)
const drawing = ref<DrawState | null>(null)

const selectedTask = computed(() => tasks.value.find(task => task.id === selectedId.value) || null)
const selectedTaskIndex = computed(() => tasks.value.findIndex(task => task.id === selectedId.value))
const canGoPrevious = computed(() => selectedTaskIndex.value > 0)
const canGoNext = computed(() => selectedTaskIndex.value >= 0 && selectedTaskIndex.value < tasks.value.length - 1)
const classOrder = computed(() => trainingStatus.value?.dataset.classes?.length ? trainingStatus.value.dataset.classes : Object.keys(CLASS_LABELS))
const classOptions = computed(() => classOrder.value.map(value => ({ value, label: `${classLabel(value)} (${value})` })))
const taxonomySelectOptions = computed(() => ({
  colors: toSelectOptions(taxonomy.value?.colors || ['阳绿', '蓝水', '晴水', '紫罗兰', '白冰', '飘花', '黄翡', '墨翠', '红翡']),
  waters: toSelectOptions(taxonomy.value?.waters || ['玻璃种', '高冰', '冰种', '冰糯', '糯冰', '细糯', '糯种', '豆种']),
  styles: toSelectOptions(taxonomy.value?.styles || ['手镯', '珠串', '珠链', '蛋面', '戒指', '吊坠', '耳饰', '摆件']),
  themes: toSelectOptions(taxonomy.value?.themes || ['观音', '佛公', '平安扣', '如意', '叶子', '山水', '貔貅', '葫芦', '无事牌', '财神', '龙牌', '福瓜', '福豆']),
  crafts: toSelectOptions(taxonomy.value?.crafts || ['裸石', '镶嵌']),
}))
const manualBoxCount = computed(() => tasks.value.filter(task => task.training?.box_mode === 'manual-box').length)
const queueHint = computed(() => {
  const counts = summary.value?.class_counts || {}
  const top = Object.entries(counts).slice(0, 3).map(([name, count]) => `${classLabel(name)} ${count}`).join(' / ')
  return top || '按最近反馈排序'
})
const previewBox = computed(() => drawing.value ? drawStateToBox(drawing.value) : null)

onMounted(async () => {
  await Promise.all([loadTrainingStatus(), loadTaxonomy(), loadTasks()])
})

async function loadTaxonomy() {
  taxonomy.value = await fetchJadeTaxonomyOptions()
}

async function loadTrainingStatus() {
  trainingStatus.value = await fetchJadeTrainingStatus()
  if (!classOrder.value.includes(selectedClass.value)) {
    selectedClass.value = classOrder.value[0] || 'jade_bangle'
  }
}

async function loadTasks() {
  loading.value = true
  error.value = ''
  try {
    const result = await fetchJadeAnnotationTasks(limit.value)
    summary.value = result
    tasks.value = result.tasks
    if (!selectedId.value || !tasks.value.some(task => task.id === selectedId.value)) {
      selectTask(tasks.value[0] || null)
    } else {
      const task = selectedTask.value
      if (task) hydrateBoxes(task)
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '标注任务读取失败'
  } finally {
    loading.value = false
  }
}

function selectTask(task: AnnotationTask | null) {
  selectedId.value = task?.id || ''
  hydrateBoxes(task)
}

function hydrateBoxes(task: AnnotationTask | null) {
  const existing = task?.training?.yolo_boxes || []
  boxes.value = existing.map(box => ({ ...box }))
  selectedBoxIndex.value = boxes.value.length ? 0 : -1
  const rawStyle = task?.corrected.style || ''
  const normalizedStyle = normalizeStyle(rawStyle)
  const normalizedTheme = normalizeTheme(task?.corrected.theme || themeFromLegacyStyle(rawStyle))
  attributeDraft.value = {
    color: task?.corrected.color || '',
    water: task?.corrected.water || '',
    style: normalizedStyle,
    theme: normalizedStyle === '吊坠' ? normalizedTheme : '',
    craft: task?.corrected.craft || '',
  }
  negativeReason.value = ''
  syncSelectedClassWithAttributes()
  selectedClass.value = classFromAttributes() || task?.classes[0] || boxes.value[0]?.class_name || classOrder.value[0] || 'jade_bangle'
}

function classLabel(className: string) {
  return CLASS_LABELS[className] || className
}

function taskClassText(task: AnnotationTask) {
  return task.classes.length ? task.classes.map(classLabel).join(' / ') : '待选类别'
}

function normalizeStyle(value: string) {
  if (['挂件', '吊坠', '牌子', '牌坠', '平安扣', '观音', '佛公', '如意', '叶子', '山水', '貔貅', '葫芦', '无事牌', '财神', '龙牌', '福瓜', '福豆'].includes(value)) {
    return '吊坠'
  }
  if (['耳环', '耳坠', '耳钉'].includes(value)) return '耳饰'
  if (value === '项链') return '珠链'
  return value
}

function normalizeTheme(value: string) {
  if (value === '龙') return '龙牌'
  if (value === '山水牌') return '山水'
  if (value === '平安无事牌') return '无事牌'
  if (['四季豆', '豆荚', '豆子'].includes(value)) return '福豆'
  return value
}

function themeFromLegacyStyle(value: string) {
  if (['平安扣', '观音', '佛公', '如意', '叶子', '山水', '貔貅', '葫芦', '无事牌', '财神', '龙牌', '福瓜', '福豆'].includes(value)) {
    return value
  }
  return ''
}

function selectAttribute(key: AttributeKey, value: string) {
  negativeReason.value = ''
  attributeDraft.value[key] = key === 'theme' ? normalizeTheme(value) : value
  if (key === 'style' && value !== '吊坠') {
    attributeDraft.value.theme = ''
  }
  if (key === 'theme' && value) {
    attributeDraft.value.style = '吊坠'
  }
  syncSelectedClassWithAttributes()
}

function toggleNegativeReason(reason: string) {
  negativeReason.value = negativeReason.value === reason ? '' : reason
}

function classFromAttributes() {
  if (attributeDraft.value.style === '吊坠' && attributeDraft.value.theme) {
    return THEME_CLASS_BY_VALUE[attributeDraft.value.theme] || 'jade_pendant'
  }
  return STYLE_CLASS_BY_VALUE[attributeDraft.value.style] || ''
}

function syncSelectedClassWithAttributes() {
  const nextClass = classFromAttributes()
  if (!nextClass) return
  selectedClass.value = nextClass
  if (boxes.value.length) {
    const index = selectedBoxIndex.value >= 0 ? selectedBoxIndex.value : boxes.value.length - 1
    boxes.value[index].class_name = nextClass
    selectedBoxIndex.value = index
  }
}

function setBoxClass(index: number, value: string | null) {
  const className = value || ''
  if (!className || !boxes.value[index]) return
  boxes.value[index].class_name = className
  selectedBoxIndex.value = index
  selectedClass.value = className
  syncAttributesFromClass(className)
}

function syncAttributesFromClass(className: string) {
  const next = ATTRIBUTE_BY_CLASS[className]
  if (!next) return
  negativeReason.value = ''
  if (next.style) {
    attributeDraft.value.style = next.style
  }
  if (next.theme) {
    attributeDraft.value.theme = next.theme
  } else if (next.style && next.style !== '吊坠') {
    attributeDraft.value.theme = ''
  }
}

function applyCurrentClassToBoxes() {
  const nextClass = classFromAttributes()
  if (!nextClass) return
  selectedClass.value = nextClass
  boxes.value = boxes.value.map(box => ({ ...box, class_name: nextClass }))
}

function pointerPosition(event: PointerEvent) {
  const rect = stageRef.value?.getBoundingClientRect()
  if (!rect || rect.width <= 0 || rect.height <= 0) return null
  return {
    x: clamp01((event.clientX - rect.left) / rect.width),
    y: clamp01((event.clientY - rect.top) / rect.height),
  }
}

function beginDraw(event: PointerEvent) {
  if (!selectedTask.value || event.button !== 0) return
  const point = pointerPosition(event)
  if (!point) return
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
  drawing.value = {
    startX: point.x,
    startY: point.y,
    currentX: point.x,
    currentY: point.y,
    pointerId: event.pointerId,
  }
}

function moveDraw(event: PointerEvent) {
  if (!drawing.value || drawing.value.pointerId !== event.pointerId) return
  const point = pointerPosition(event)
  if (!point) return
  drawing.value.currentX = point.x
  drawing.value.currentY = point.y
}

function finishDraw(event: PointerEvent) {
  if (!drawing.value || drawing.value.pointerId !== event.pointerId) return
  const next = drawStateToBox(drawing.value)
  drawing.value = null
  if (!next || next.width < 0.03 || next.height < 0.03 || next.width * next.height < 0.01) {
    messageApi.warning('框太小，已忽略')
    return
  }
  boxes.value.push(next)
  selectedBoxIndex.value = boxes.value.length - 1
}

function cancelDraw(event: PointerEvent) {
  if (drawing.value?.pointerId === event.pointerId) drawing.value = null
}

function drawStateToBox(state: DrawState): YoloBox {
  const left = Math.min(state.startX, state.currentX)
  const right = Math.max(state.startX, state.currentX)
  const top = Math.min(state.startY, state.currentY)
  const bottom = Math.max(state.startY, state.currentY)
  return normalizeBox({
    class_name: selectedClass.value,
    x_center: (left + right) / 2,
    y_center: (top + bottom) / 2,
    width: right - left,
    height: bottom - top,
  })
}

function normalizeBox(box: YoloBox): YoloBox {
  return {
    class_name: box.class_name,
    x_center: round(clamp01(box.x_center)),
    y_center: round(clamp01(box.y_center)),
    width: round(clamp01(box.width)),
    height: round(clamp01(box.height)),
  }
}

function boxStyle(box: YoloBox) {
  const left = clamp01(box.x_center - box.width / 2)
  const top = clamp01(box.y_center - box.height / 2)
  return {
    left: `${left * 100}%`,
    top: `${top * 100}%`,
    width: `${box.width * 100}%`,
    height: `${box.height * 100}%`,
  }
}

function addCenterBox() {
  boxes.value.push({
    class_name: selectedClass.value,
    x_center: 0.5,
    y_center: 0.5,
    width: 0.8,
    height: 0.8,
  })
  selectedBoxIndex.value = boxes.value.length - 1
}

function removeBox(index: number) {
  boxes.value.splice(index, 1)
  selectedBoxIndex.value = boxes.value.length ? Math.min(index, boxes.value.length - 1) : -1
}

function undoLastBox() {
  if (!boxes.value.length) return
  boxes.value.pop()
  selectedBoxIndex.value = boxes.value.length ? boxes.value.length - 1 : -1
}

function deleteSelectedBox() {
  if (selectedBoxIndex.value < 0) return
  removeBox(selectedBoxIndex.value)
}

function goPrevious() {
  if (!canGoPrevious.value) return
  selectTask(tasks.value[selectedTaskIndex.value - 1])
}

function goNext() {
  if (!canGoNext.value) return
  selectTask(tasks.value[selectedTaskIndex.value + 1])
}

async function saveCurrentTask() {
  if (!selectedTask.value || saving.value) return
  if (negativeReason.value) {
    await saveNegativeTask()
    return
  }
  await savePositiveTask()
}

async function savePositiveTask() {
  if (!selectedTask.value) return
  const validationError = validatePositiveAnnotation()
  if (validationError) {
    error.value = validationError
    message.value = ''
    messageApi.warning(validationError)
    return
  }
  const selection = nextSelectionAfterCurrent()
  applyCurrentClassToBoxes()
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    await reviewJadeAnnotationTask(selectedTask.value.id, 'approve', cleanAttributeDraft())
    await saveJadeAnnotationBoxes(selectedTask.value.id, boxes.value.map(normalizeBox))
    message.value = `已保存 ${boxes.value.length} 个主体框`
    messageApi.success(message.value)
    await reloadTasksAndSelect(selection)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '保存标注失败'
  } finally {
    saving.value = false
  }
}

async function saveNegativeTask() {
  if (!selectedTask.value) return
  if (!negativeReason.value) {
    error.value = '请选择一个无可标注原因'
    message.value = ''
    messageApi.warning(error.value)
    return
  }
  const selection = nextSelectionAfterCurrent()
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    await reviewJadeAnnotationTask(selectedTask.value.id, 'reject', { negative_reason: negativeReason.value })
    message.value = `已保存为无可标注：${negativeReason.value}`
    messageApi.success(message.value)
    await reloadTasksAndSelect(selection)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '保存无可标注失败'
  } finally {
    saving.value = false
  }
}

function validatePositiveAnnotation() {
  if (!boxes.value.length) {
    return '请先框出翡翠主体；如果图里没有可标注主体，请选无可标注原因'
  }
  if (!attributeDraft.value.color) {
    return '请选择颜色；不能100%判断就选“颜色无法100%判断”'
  }
  if (!attributeDraft.value.water) {
    return '请选择种水；不能100%判断就选“种水无法100%判断”'
  }
  if (!attributeDraft.value.style) {
    return '请选择款式；不能100%判断就选“款式无法100%判断”'
  }
  if (attributeDraft.value.style === '吊坠' && !attributeDraft.value.theme) {
    return '吊坠必须选择题材；不能100%判断就选“题材无法100%判断”'
  }
  if (!attributeDraft.value.craft) {
    return '请选择工艺；不能100%判断就选“工艺无法100%判断”'
  }
  return ''
}

function nextSelectionAfterCurrent() {
  const index = selectedTaskIndex.value
  return {
    nextId: index >= 0 ? tasks.value[index + 1]?.id || '' : '',
    fallbackIndex: Math.max(0, index),
  }
}

async function reloadTasksAndSelect(selection: { nextId: string; fallbackIndex: number }) {
  await Promise.all([loadTrainingStatus(), loadTasks()])
  const target =
    (selection.nextId ? tasks.value.find(task => task.id === selection.nextId) : null) ||
    tasks.value[Math.min(selection.fallbackIndex, Math.max(0, tasks.value.length - 1))] ||
    null
  selectTask(target)
}

async function buildDataset() {
  building.value = true
  error.value = ''
  try {
    const result = await buildJadeTrainingDataset({ split: 'train', val_every: 5, write_yaml: true })
    message.value = `训练集已重建：写入 ${result.written} 条，跳过 ${result.skipped} 条`
    messageApi.success(message.value)
    await loadTrainingStatus()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '训练集重建失败'
  } finally {
    building.value = false
  }
}

function clamp01(value: number) {
  return Math.max(0, Math.min(1, value))
}

function round(value: number) {
  return Number(value.toFixed(6))
}

function cleanAttributeDraft() {
  const style = attributeDraft.value.style || ''
  return {
    color: attributeDraft.value.color || '',
    water: attributeDraft.value.water || '',
    style,
    theme: style === '吊坠' ? attributeDraft.value.theme || '' : '',
    craft: attributeDraft.value.craft || '',
  }
}

function toSelectOptions(values: string[]) {
  return values.map(value => ({ label: value, value }))
}
</script>

<style scoped>
.annotation-workbench-page {
  min-height: 100vh;
  background: #080d12;
  color: #ecf7f4;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 22px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  background: #0d141b;
}

.toolbar-group,
.toolbar-meta,
.canvas-actions,
.task-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.toolbar-label,
.toolbar-meta {
  color: #9fb1bd;
  font-size: 13px;
}

.status-line {
  margin: 12px 22px 0;
  padding: 10px 12px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 6px;
}

.status-line.error {
  color: #fecaca;
  border-color: rgba(248, 113, 113, 0.4);
  background: rgba(127, 29, 29, 0.26);
}

.status-line.success {
  color: #bbf7d0;
  border-color: rgba(34, 197, 94, 0.35);
  background: rgba(20, 83, 45, 0.22);
}

.workbench-grid {
  display: grid;
  grid-template-columns: 310px minmax(0, 1fr) 330px;
  gap: 16px;
  padding: 16px 22px 24px;
}

.task-queue,
.canvas-panel,
.box-panel {
  min-height: calc(100vh - 150px);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 8px;
  background: #101820;
}

.task-queue,
.box-panel {
  overflow: hidden;
}

.task-queue header,
.box-panel header,
.canvas-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
}

.task-queue header span,
.box-panel header span,
.canvas-header span {
  color: #9fb1bd;
  font-size: 12px;
}

.task-row {
  display: grid;
  grid-template-columns: 68px minmax(0, 1fr);
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border: 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.task-row:hover,
.task-row.active {
  background: rgba(34, 211, 166, 0.12);
}

.task-row img {
  width: 68px;
  height: 92px;
  object-fit: cover;
  border-radius: 6px;
  background: #05080c;
}

.task-row span,
.box-row {
  min-width: 0;
}

.task-row strong,
.task-row small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-row small {
  margin-top: 5px;
  color: #9fb1bd;
  font-size: 12px;
}

.canvas-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.canvas-header > div:first-child {
  min-width: 0;
}

.canvas-header strong {
  display: block;
}

.class-select {
  width: 230px;
}

.image-stage-shell {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  padding: 14px;
  overflow: auto;
}

.image-stage {
  position: relative;
  display: inline-block;
  max-width: 100%;
  cursor: crosshair;
  touch-action: none;
  user-select: none;
}

.image-stage img {
  display: block;
  max-width: 100%;
  max-height: calc(100vh - 250px);
  border-radius: 6px;
  background: #05080c;
}

.drawn-box {
  position: absolute;
  border: 2px solid #22d3a6;
  background: rgba(34, 211, 166, 0.08);
  pointer-events: none;
}

.drawn-box.selected {
  border-color: #facc15;
  background: rgba(250, 204, 21, 0.1);
}

.drawn-box.preview {
  border-style: dashed;
  border-color: #facc15;
  background: rgba(250, 204, 21, 0.08);
}

.drawn-box span {
  position: absolute;
  left: -2px;
  top: -24px;
  max-width: 160px;
  padding: 2px 6px;
  overflow: hidden;
  border-radius: 4px;
  background: #22d3a6;
  color: #04110d;
  font-size: 12px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.box-panel {
  padding-bottom: 12px;
}

.task-meta,
.attribute-form,
.negative-panel,
.box-list {
  padding: 12px;
}

.attribute-form {
  display: grid;
  gap: 10px;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.attribute-form label {
  display: grid;
  gap: 6px;
}

.attribute-form span {
  color: #9fb1bd;
  font-size: 12px;
}

.option-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(72px, 1fr));
  gap: 8px;
}

.option-chip {
  min-height: 34px;
  padding: 7px 9px;
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.82);
  color: #d9e8e4;
  font-size: 13px;
  line-height: 1.25;
  text-align: center;
  cursor: pointer;
}

.option-chip:hover {
  border-color: rgba(34, 211, 166, 0.54);
  background: rgba(20, 83, 45, 0.32);
}

.option-chip.active {
  border-color: #22d3a6;
  background: rgba(34, 211, 166, 0.22);
  color: #f8fffd;
}

.negative-panel {
  display: grid;
  gap: 8px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.negative-panel strong {
  font-size: 13px;
}

.negative-panel span {
  color: #9fb1bd;
  font-size: 12px;
  line-height: 1.5;
}

.negative-panel .option-grid {
  grid-template-columns: 1fr;
}

.option-chip.negative {
  border-color: rgba(251, 191, 36, 0.28);
  background: rgba(113, 63, 18, 0.2);
  text-align: left;
}

.option-chip.negative.active {
  border-color: #f59e0b;
  background: rgba(180, 83, 9, 0.34);
}

.box-list {
  display: grid;
  gap: 10px;
}

.box-row {
  display: grid;
  gap: 8px;
  padding: 10px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.72);
  cursor: pointer;
}

.box-row.selected {
  border-color: rgba(250, 204, 21, 0.72);
  background: rgba(250, 204, 21, 0.08);
}

.box-numbers {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  color: #9fb1bd;
  font-size: 12px;
}

.side-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding: 0 12px 12px;
}

.side-actions :deep(.n-button__content) {
  white-space: normal;
}

.empty-state {
  margin: auto;
  padding: 24px;
  color: #9fb1bd;
  text-align: center;
}

.empty-state.compact {
  margin: 0;
  padding: 12px;
  border: 1px dashed rgba(148, 163, 184, 0.22);
  border-radius: 6px;
}

@media (max-width: 1180px) {
  .workbench-grid {
    grid-template-columns: 260px minmax(0, 1fr);
  }

  .box-panel {
    grid-column: 1 / -1;
    min-height: auto;
  }
}

@media (max-width: 760px) {
  .toolbar,
  .workbench-grid {
    padding-left: 12px;
    padding-right: 12px;
  }

  .workbench-grid {
    grid-template-columns: 1fr;
  }

  .task-queue,
  .canvas-panel,
  .box-panel {
    min-height: auto;
  }

  .canvas-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
