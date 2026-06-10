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
            <small>{{ task.corrected.style || '样式未填' }} · {{ task.corrected.theme || '题材未填' }}</small>
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
            <n-select v-model:value="selectedClass" size="small" class="class-select" :options="classOptions" filterable />
            <n-button size="small" secondary @click="addCenterBox">中心框</n-button>
            <n-button size="small" secondary :disabled="!boxes.length" @click="undoLastBox">撤回画框</n-button>
            <n-button size="small" secondary type="error" :disabled="selectedBoxIndex < 0" @click="deleteSelectedBox">删除框</n-button>
            <n-button size="small" secondary type="warning" :loading="saving" @click="confirmWholeImage">整图框</n-button>
            <n-button size="small" type="primary" :loading="saving" @click="saveBoxes">保存标注</n-button>
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
            <n-select v-model:value="attributeDraft.color" size="small" :options="taxonomySelectOptions.colors" filterable clearable />
          </label>
          <label>
            <span>种水</span>
            <n-select v-model:value="attributeDraft.water" size="small" :options="taxonomySelectOptions.waters" filterable clearable />
          </label>
          <label>
            <span>样式</span>
            <n-select v-model:value="attributeDraft.style" size="small" :options="taxonomySelectOptions.styles" filterable clearable />
          </label>
          <label>
            <span>题材</span>
            <n-select v-model:value="attributeDraft.theme" size="small" :options="taxonomySelectOptions.themes" filterable clearable />
          </label>
        </div>

        <div class="box-list">
          <div
            v-for="(box, index) in boxes"
            :key="index"
            class="box-row"
            :class="{ selected: selectedBoxIndex === index }"
            @click="selectedBoxIndex = index"
          >
            <n-select v-model:value="box.class_name" size="small" :options="classOptions" filterable />
            <div class="box-numbers">
              <span>x {{ box.x_center.toFixed(3) }}</span>
              <span>y {{ box.y_center.toFixed(3) }}</span>
              <span>w {{ box.width.toFixed(3) }}</span>
              <span>h {{ box.height.toFixed(3) }}</span>
            </div>
            <n-button size="tiny" secondary type="error" @click="removeBox(index)">删除</n-button>
          </div>
          <div v-if="!boxes.length" class="empty-state compact">还没有主体框。</div>
        </div>

        <div v-if="selectedTask" class="side-actions">
          <n-button secondary :disabled="!canGoPrevious" @click="goPrevious">上一个</n-button>
          <n-button secondary :disabled="!canGoNext" @click="goNext">下一个</n-button>
          <n-button secondary :disabled="!boxes.length" @click="undoLastBox">撤回画框</n-button>
          <n-button secondary type="error" :disabled="selectedBoxIndex < 0" @click="deleteSelectedBox">删除框</n-button>
          <n-button type="primary" :loading="saving" @click="saveBoxes">保存</n-button>
          <n-button secondary type="error" :loading="saving" @click="rejectTask">丢弃样本</n-button>
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
  approveJadeAnnotationWholeImageBox,
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
  dragon_plaque: '龙牌',
  fu_gua: '福瓜',
  fu_dou: '福豆',
}

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
const attributeDraft = ref({ color: '', water: '', style: '', theme: '' })
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
  styles: toSelectOptions(taxonomy.value?.styles || ['手镯', '珠串', '蛋面', '吊坠', '戒指', '牌子', '平安扣', '摆件']),
  themes: toSelectOptions(taxonomy.value?.themes || ['观音', '佛公', '如意', '叶子', '山水', '貔貅', '葫芦', '无事牌', '财神', '龙牌', '福瓜', '福豆']),
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
  attributeDraft.value = {
    color: task?.corrected.color || '',
    water: task?.corrected.water || '',
    style: task?.corrected.style || '',
    theme: task?.corrected.theme || '',
  }
  selectedClass.value = task?.classes[0] || boxes.value[0]?.class_name || classOrder.value[0] || 'jade_bangle'
}

function classLabel(className: string) {
  return CLASS_LABELS[className] || className
}

function taskClassText(task: AnnotationTask) {
  return task.classes.length ? task.classes.map(classLabel).join(' / ') : '待选类别'
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

async function saveBoxes() {
  if (!selectedTask.value) return
  if (!boxes.value.length) {
    error.value = '请至少画一个主体框'
    return
  }
  saving.value = true
  error.value = ''
  try {
    await reviewJadeAnnotationTask(selectedTask.value.id, 'approve', cleanAttributeDraft())
    await saveJadeAnnotationBoxes(selectedTask.value.id, boxes.value.map(normalizeBox))
    await buildJadeTrainingDataset({ split: 'train', val_every: 5, write_yaml: true })
    message.value = `已保存 ${boxes.value.length} 个主体框，并重建训练集`
    messageApi.success(message.value)
    await Promise.all([loadTrainingStatus(), loadTasks()])
  } catch (err) {
    error.value = err instanceof Error ? err.message : '保存标注失败'
  } finally {
    saving.value = false
  }
}

async function confirmWholeImage() {
  if (!selectedTask.value) return
  saving.value = true
  error.value = ''
  try {
    await approveJadeAnnotationWholeImageBox(selectedTask.value.id, cleanAttributeDraft())
    await buildJadeTrainingDataset({ split: 'train', val_every: 5, write_yaml: true })
    message.value = '已按整图框确认，并重建训练集'
    messageApi.success(message.value)
    await Promise.all([loadTrainingStatus(), loadTasks()])
  } catch (err) {
    error.value = err instanceof Error ? err.message : '整图框确认失败'
  } finally {
    saving.value = false
  }
}

async function rejectTask() {
  if (!selectedTask.value) return
  saving.value = true
  error.value = ''
  try {
    await reviewJadeAnnotationTask(selectedTask.value.id, 'reject')
    message.value = '样本已丢弃'
    await loadTasks()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '丢弃样本失败'
  } finally {
    saving.value = false
  }
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
  return {
    color: attributeDraft.value.color || '',
    water: attributeDraft.value.water || '',
    style: attributeDraft.value.style || '',
    theme: attributeDraft.value.theme || '',
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
