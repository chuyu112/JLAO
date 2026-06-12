<template>
  <section class="yolo-live-panel">
    <div class="yolo-live-head">
      <div class="yolo-live-title">
        <span>实时视频流</span>
        <small>{{ statusLabel }}</small>
      </div>
      <div class="yolo-live-head-tags">
        <span :class="['stream-pill', captureActive ? 'is-on' : '']">视频 {{ captureActive ? '已接入' : '未接入' }}</span>
        <span :class="['stream-pill', ocrRunning ? 'is-on ocr' : '']">截图/OCR {{ ocrRunning ? '运行中' : '停止' }}</span>
        <span :class="['stream-pill', recordingRunning ? 'is-on rec' : '']">录屏 {{ recordingRunning ? '运行中' : '停止' }}</span>
      </div>
    </div>

    <div ref="stageRef" class="yolo-live-stage">
      <video
        v-show="captureActive && !backendPreviewActive"
        ref="videoRef"
        :class="['yolo-live-video', videoRotationClass, videoMirrorClass, videoFitClass]"
        autoplay
        muted
        playsinline
        @loadedmetadata="handleVideoReady"
      />
      <img
        v-show="captureActive && backendPreviewActive"
        ref="imageRef"
        :class="['yolo-live-video', videoRotationClass, videoMirrorClass, videoFitClass]"
        crossorigin="anonymous"
        alt=""
        @load="handleBackendImageLoad"
        @error="handleBackendImageError"
      />
      <canvas ref="overlayCanvasRef" class="yolo-live-overlay" />
      <div v-if="captureActive" class="fps-badge">{{ fpsLabel }}</div>
      <div v-if="backendNoSignal" class="signal-warning">采集卡黑屏 / 无有效画面</div>
      <div v-if="!captureActive" class="yolo-live-empty">
        <span>未接入视频流</span>
      </div>
    </div>

    <div class="yolo-live-metrics">
      <div class="metric-box yolo-live-metric">
        <span class="metric-label">检测</span>
        <span class="analysis-value">{{ detectionLabel }}</span>
      </div>
      <div class="metric-box yolo-live-metric">
        <span class="metric-label">YOLO</span>
        <span class="analysis-value">{{ formatMs(lastTiming?.yolo_ms) }}</span>
      </div>
      <div class="metric-box yolo-live-metric">
        <span class="metric-label">总耗时</span>
        <span class="analysis-value">{{ formatMs(lastTiming?.total_ms) }}</span>
      </div>
      <div class="metric-box yolo-live-metric">
        <span class="metric-label">FPS</span>
        <span class="analysis-value">{{ fpsLabel }}</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { detectCaptureCardYoloLiveFrame, detectJadeYoloLiveFrame } from '../api/jlao'
import type { JadeYoloLiveDetection, JadeYoloLiveDetectionResult } from '../types'

const props = defineProps<{
  sessionId: string | null
  inputMode?: 'capture_card' | 'scrcpy' | string
  videoRotation?: number
  videoMirror?: boolean
  backendStreamUrl?: string
  backendFrameCount?: number
  backendSignalPresent?: boolean
  sourceActive?: boolean
  sourceBlocked?: boolean
  staleTimeoutMs?: number
}>()

const emit = defineEmits<{
  captureStateChange: [active: boolean]
  captureFrame: [blob: Blob]
  captureBackendFrame: []
  recordingBlob: [blob: Blob | null]
}>()

const DETECT_INTERVAL_MS = 1000
const VIDEO_STALE_TIMEOUT_MS = 3000
const VIDEO_STALE_CHECK_MS = 1000
const MAX_CAPTURE_WIDTH = 1920
const MAX_RECORDING_WIDTH = 1280
const BACKEND_RECORDING_FPS = 15
const CAPTURE_CARD_FRAME_UPLOAD_INTERVAL_MS = 5000
const RECORDING_MIME_TYPES = [
  'video/webm;codecs=vp9',
  'video/webm;codecs=vp8',
  'video/webm',
]
const DISPLAY_CANDIDATE_MIN_CONFIDENCE = 0.01
const DISPLAY_CONFIRMED_MIN_CONFIDENCE = 0.03

const message = useMessage()
const stageRef = ref<HTMLDivElement | null>(null)
const videoRef = ref<HTMLVideoElement | null>(null)
const imageRef = ref<HTMLImageElement | null>(null)
const overlayCanvasRef = ref<HTMLCanvasElement | null>(null)
const captureActive = ref(false)
const captureStarting = ref(false)
const ocrRunning = ref(false)
const detecting = ref(false)
const stream = ref<MediaStream | null>(null)
const backendPreviewActive = ref(false)
const backendPreviewUrl = ref('')
const frameTimer = ref<number | null>(null)
const mediaRecorder = ref<MediaRecorder | null>(null)
const recordedChunks = ref<Blob[]>([])
const recordingSourceStream = ref<MediaStream | null>(null)
const recordingOwnsSourceStream = ref(false)
const backendRecordingTimer = ref<number | null>(null)
const recordingRunning = ref(false)
const recordingStopResolver = ref<((blob: Blob | null) => void) | null>(null)
const emitDetachedRecording = ref(false)
const lastResult = ref<JadeYoloLiveDetectionResult | null>(null)
const lastDetections = ref<JadeYoloLiveDetection[]>([])
const lastCandidates = ref<JadeYoloLiveDetection[]>([])
const lastImageSize = ref({ width: 0, height: 0 })
const lastError = ref('')
const fps = ref(0)
const fpsFrameCount = ref(0)
const fpsWindowStartedAt = ref(0)
const lastVideoFrameAt = ref(0)
const lastBackendFrameCount = ref(0)
const lastBackendFrameSampleAt = ref(0)
const lastFrameUploadAt = ref(0)
const staleCheckTimer = ref<number | null>(null)
const captureCanvas = document.createElement('canvas')
const recordingCanvas = document.createElement('canvas')

const displayDetections = computed(() => lastDetections.value.filter((detection) => isDisplayableDetection(detection)))
const displayCandidates = computed(() => lastCandidates.value.filter((detection) => isDisplayableDetection(detection)))
const overlayDetections = computed(() => displayDetections.value.length ? displayDetections.value : displayCandidates.value)
const lastTiming = computed(() => lastResult.value?.timings || null)
const lastTracking = computed(() => lastResult.value?.tracking || null)
const fpsLabel = computed(() => `${fps.value.toFixed(1)} fps`)
const staleTimeoutMs = computed(() => Math.max(1000, props.staleTimeoutMs || VIDEO_STALE_TIMEOUT_MS))
const backendNoSignal = computed(() => (
  props.inputMode === 'capture_card' &&
  captureActive.value &&
  Number(props.backendFrameCount || 0) > 0 &&
  props.backendSignalPresent === false
))
const normalizedVideoRotation = computed(() => (
  props.inputMode === 'capture_card' && Number(props.videoRotation || 0) === 180 ? 180 : 0
))
const videoRotationClass = computed(() => (
  normalizedVideoRotation.value === 180 ? 'is-rotated-180' : ''
))
const videoMirrorEnabled = computed(() => (
  props.inputMode === 'capture_card' && props.videoMirror !== false
))
const videoMirrorClass = computed(() => (
  videoMirrorEnabled.value ? 'is-mirrored' : ''
))
const videoFitMode = computed<'contain' | 'cover'>(() => (
  props.inputMode === 'capture_card' ? 'cover' : 'contain'
))
const videoFitClass = computed(() => (
  videoFitMode.value === 'cover' ? 'is-fill-preview' : ''
))

watch(
  () => props.backendFrameCount,
  (count) => {
    updateBackendFps(Number(count || 0))
  },
)

const statusLabel = computed(() => {
  if (!props.sessionId) return '等待会话'
  if (lastError.value) return lastError.value
  if (backendNoSignal.value) return '采集卡已打开，当前黑屏/无信号'
  if (!captureActive.value) return '等待接入'
  if (detecting.value) return '截图识别中'
  if (lastTracking.value?.status === 'confirmed') return '已确认目标'
  if (lastTracking.value?.status === 'pending') return '候选确认中'
  if (lastTracking.value?.status === 'lost') return '短暂保持'
  return ocrRunning.value ? '视频运行，截图/OCR运行' : '视频运行'
})

const detectionLabel = computed(() => {
  const count = displayDetections.value.length
  const candidateCount = displayCandidates.value.length
  const tracking = lastTracking.value
  if (!captureActive.value) return '-'
  if (!ocrRunning.value) return '未启动'
  if (!lastResult.value) return '等待'
  if (count) {
    const best = bestDetection(displayDetections.value)
    if (!best) return '未确认'
    if (best.tracking_state === 'lost') return `保持 ${best.lost_frames || 0} 帧`
    if (best.confidence < DISPLAY_CONFIRMED_MIN_CONFIDENCE) {
      return `弱确认 ${count} 个 · ${Math.round(best.confidence * 100)}%`
    }
    return `${count} 个 · ${Math.round(best.confidence * 100)}%`
  }
  if (candidateCount) {
    const best = bestDetection(displayCandidates.value)
    return `候选 ${candidateCount} 个 · ${Math.round((best?.confidence || 0) * 100)}%`
  }
  if (!count && tracking?.status === 'pending') {
    return `候选 ${tracking.stable_frames || 0}/${tracking.confirm_frames || 3}`
  }
  if (!count && lastDetections.value.length) return '待确认'
  return '未确认'
})

async function startCapture(): Promise<boolean> {
  if (captureActive.value) return true
  if (captureStarting.value) return false
  if (props.sourceBlocked) {
    message.warning('其它页面正在采集，请先停止后再接入视频流')
    return false
  }
  if (!props.sourceActive) {
    message.warning('请先启动采集投屏')
    return false
  }
  if (!props.sessionId) {
    message.warning('请先启动直播会话')
    return false
  }
  if (props.inputMode === 'capture_card') {
    return startBackendPreviewCapture()
  }
  if (!navigator.mediaDevices?.getDisplayMedia) {
    message.error('当前浏览器不支持视频流接入')
    return false
  }

  releaseCaptureStream()
  await waitForCaptureRelease()
  captureStarting.value = true
  lastError.value = ''
  try {
    stream.value = await navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: false,
    })

    const videoTracks = stream.value.getVideoTracks()
    if (!videoTracks.length) {
      stream.value.getTracks().forEach((track) => track.stop())
      stream.value = null
      throw new Error('浏览器没有返回视频轨道')
    }

    captureActive.value = true
    emit('captureStateChange', true)
    await nextTick()
    if (videoRef.value) {
      videoRef.value.srcObject = stream.value
      await videoRef.value.play()
    }

    const [videoTrack] = videoTracks
    videoTrack?.addEventListener('ended', handleVideoTrackEnded)
    startFpsMonitor()
    return true
  } catch (error) {
    stopCapture({ keepError: true })
    lastError.value = displayMediaErrorMessage(error)
    message.error(lastError.value)
    return false
  } finally {
    captureStarting.value = false
  }
}

async function startBackendPreviewCapture(): Promise<boolean> {
  if (!props.backendStreamUrl) {
    message.error('采集卡预览地址未就绪')
    return false
  }
  releaseCaptureStream()
  await waitForCaptureRelease()
  captureStarting.value = true
  lastError.value = ''
  try {
    backendPreviewActive.value = true
    backendPreviewUrl.value = props.backendStreamUrl
    captureActive.value = true
    emit('captureStateChange', true)
    await nextTick()
    if (imageRef.value) {
      imageRef.value.src = backendPreviewUrl.value
    }
    startBackendPreviewMonitor()
    return true
  } finally {
    captureStarting.value = false
  }
}

function displayMediaErrorMessage(error: unknown): string {
  const err = error as { name?: string; message?: string }
  const name = err?.name || ''
  if (name === 'NotAllowedError') return '视频流接入失败：浏览器权限被取消或拒绝'
  if (name === 'NotFoundError') return '视频流接入失败：没有可共享的窗口或屏幕'
  if (name === 'NotReadableError') return '视频流接入失败：窗口正被系统或其它程序占用'
  if (name === 'OverconstrainedError') return '视频流接入失败：浏览器不支持当前采集约束'
  return `视频流接入失败${err?.message ? `：${err.message}` : ''}`
}

function waitForCaptureRelease() {
  return new Promise<void>((resolve) => window.setTimeout(resolve, 120))
}

function releaseCaptureStream() {
  stream.value?.getTracks().forEach((track) => {
    track.removeEventListener('ended', handleVideoTrackEnded)
    track.stop()
  })
  stream.value = null
  if (videoRef.value) videoRef.value.srcObject = null
  if (imageRef.value) imageRef.value.removeAttribute('src')
  backendPreviewUrl.value = ''
  backendPreviewActive.value = false
  stopFpsMonitor()
}

function stopCapture(options: { keepError?: boolean } = {}) {
  const wasActive = captureActive.value
  stopOcr()
  if (recordingRunning.value && mediaRecorder.value && mediaRecorder.value.state !== 'inactive') {
    emitDetachedRecording.value = true
    recordingRunning.value = false
    mediaRecorder.value?.stop()
  } else {
    cleanupRecordingSource()
  }
  releaseCaptureStream()
  captureActive.value = false
  detecting.value = false
  lastDetections.value = []
  lastCandidates.value = []
  lastResult.value = null
  lastImageSize.value = { width: 0, height: 0 }
  lastFrameUploadAt.value = 0
  fps.value = 0
  if (!options.keepError) lastError.value = ''
  clearOverlay()
  if (wasActive) emit('captureStateChange', false)
}

function handleVideoTrackEnded() {
  if (!captureActive.value) return
  stopCapture({ keepError: true })
  lastError.value = '视频流已断开，请重新接入'
  message.warning('视频流已断开，请重新接入')
}

function handleVideoStreamStalled() {
  if (!captureActive.value) return
  stopCapture({ keepError: true })
  lastError.value = '视频流无新帧，请重新接入'
  message.warning('视频流无新帧，请重新接入')
}

function startOcr(intervalMs = DETECT_INTERVAL_MS): boolean {
  if (!captureActive.value) {
    message.warning('请先接入视频流')
    return false
  }
  if (ocrRunning.value) return true
  ocrRunning.value = true
  startDetectionLoop(intervalMs)
  return true
}

function stopOcr() {
  ocrRunning.value = false
  stopDetectionLoop()
  detecting.value = false
}

function startRecording(): boolean {
  if (!captureActive.value) {
    message.warning('请先接入视频流')
    return false
  }
  if (typeof MediaRecorder === 'undefined') {
    message.warning('当前浏览器不支持录屏')
    return false
  }
  if (recordingRunning.value) return true
  if (backendPreviewActive.value && props.inputMode === 'capture_card') {
    return startBackendPreviewRecording()
  }
  if (!stream.value) {
    message.warning('Video stream is not connected')
    return false
  }
  const videoTracks = stream.value.getVideoTracks()
  if (!videoTracks.length) {
    message.warning('视频流没有可录制的视频轨道')
    return false
  }

  recordedChunks.value = []
  const recordingStream = new MediaStream(videoTracks)
  const recorder = createMediaRecorder(recordingStream)
  if (!recorder) return false
  mediaRecorder.value = recorder
  bindRecorderHandlers()
  try {
    recorder.start(250)
  } catch (error) {
    mediaRecorder.value = null
    message.error((error as Error)?.message || '浏览器录屏启动失败')
    return false
  }
  recordingRunning.value = true
  return true
}

function stopRecording(): Promise<Blob | null> {
  if (!mediaRecorder.value || mediaRecorder.value.state === 'inactive') {
    recordingRunning.value = false
    cleanupRecordingSource()
    return Promise.resolve(null)
  }
  return new Promise((resolve) => {
    recordingStopResolver.value = resolve
    recordingRunning.value = false
    try {
      mediaRecorder.value?.requestData()
    } catch {
      // Some browsers throw if requestData races with stop.
    }
    try {
      mediaRecorder.value?.stop()
    } catch {
      recordingStopResolver.value = null
      cleanupRecordingSource()
      resolve(null)
    }
  })
}

function startBackendPreviewRecording(): boolean {
  if (typeof recordingCanvas.captureStream !== 'function') {
    message.warning('Canvas recording is not supported by this browser')
    return false
  }
  if (!drawBackendRecordingFrame()) {
    message.warning('Capture-card preview is not ready')
    return false
  }

  recordedChunks.value = []
  let sourceStream: MediaStream
  try {
    sourceStream = recordingCanvas.captureStream(BACKEND_RECORDING_FPS)
  } catch (error) {
    cleanupRecordingSource()
    message.error((error as Error)?.message || 'Canvas recording failed')
    return false
  }
  recordingSourceStream.value = sourceStream
  recordingOwnsSourceStream.value = true

  const recorder = createMediaRecorder(sourceStream)
  if (!recorder) {
    cleanupRecordingSource()
    return false
  }
  mediaRecorder.value = recorder
  bindRecorderHandlers({ cleanupSource: true })
  try {
    recorder.start(500)
  } catch (error) {
    mediaRecorder.value = null
    cleanupRecordingSource()
    message.error((error as Error)?.message || '浏览器录屏启动失败')
    return false
  }
  recordingRunning.value = true
  const intervalMs = Math.max(50, Math.round(1000 / BACKEND_RECORDING_FPS))
  backendRecordingTimer.value = window.setInterval(() => {
    if (!captureActive.value || !recordingRunning.value) return
    drawBackendRecordingFrame()
  }, intervalMs)
  return true
}

function createMediaRecorder(sourceStream: MediaStream): MediaRecorder | null {
  const mimeType = RECORDING_MIME_TYPES.find((item) => MediaRecorder.isTypeSupported(item)) || ''
  try {
    return mimeType
      ? new MediaRecorder(sourceStream, { mimeType })
      : new MediaRecorder(sourceStream)
  } catch (error) {
    try {
      return new MediaRecorder(sourceStream)
    } catch {
      message.error((error as Error)?.message || '浏览器录屏初始化失败')
      return null
    }
  }
}

function bindRecorderHandlers(options: { cleanupSource?: boolean } = {}) {
  const recorder = mediaRecorder.value
  if (!recorder) return
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) recordedChunks.value.push(event.data)
  }
  recorder.onstop = () => {
    const blob = recordedChunks.value.length ? new Blob(recordedChunks.value, { type: 'video/webm' }) : null
    const resolve = recordingStopResolver.value
    recordingStopResolver.value = null
    recordedChunks.value = []
    mediaRecorder.value = null
    recordingRunning.value = false
    if (options.cleanupSource) cleanupRecordingSource()
    if (emitDetachedRecording.value) {
      emitDetachedRecording.value = false
      emit('recordingBlob', blob)
    } else {
      resolve?.(blob)
    }
  }
}

function cleanupRecordingSource() {
  if (backendRecordingTimer.value) {
    clearInterval(backendRecordingTimer.value)
    backendRecordingTimer.value = null
  }
  if (recordingOwnsSourceStream.value) {
    recordingSourceStream.value?.getTracks().forEach((track) => track.stop())
  }
  recordingSourceStream.value = null
  recordingOwnsSourceStream.value = false
}

function drawBackendRecordingFrame(): boolean {
  const image = imageRef.value
  const sourceWidth = image?.naturalWidth || 0
  const sourceHeight = image?.naturalHeight || 0
  if (!image || !sourceWidth || !sourceHeight) return false

  const scale = Math.min(1, MAX_RECORDING_WIDTH / sourceWidth)
  const width = Math.max(1, Math.round(sourceWidth * scale))
  const height = Math.max(1, Math.round(sourceHeight * scale))
  if (recordingCanvas.width !== width) recordingCanvas.width = width
  if (recordingCanvas.height !== height) recordingCanvas.height = height

  const context = recordingCanvas.getContext('2d')
  if (!context) return false
  context.fillStyle = '#000'
  context.fillRect(0, 0, width, height)

  if (normalizedVideoRotation.value === 180 || videoMirrorEnabled.value) {
    context.save()
    context.translate(width / 2, height / 2)
    if (normalizedVideoRotation.value === 180) context.rotate(Math.PI)
    context.scale(videoMirrorEnabled.value ? -1 : 1, 1)
    context.drawImage(image, -width / 2, -height / 2, width, height)
    context.restore()
  } else {
    context.drawImage(image, 0, 0, width, height)
  }
  return true
}

function startDetectionLoop(intervalMs = DETECT_INTERVAL_MS) {
  stopDetectionLoop()
  const loop = () => {
    if (!captureActive.value || !ocrRunning.value) return
    void detectCurrentFrame()
    frameTimer.value = window.setTimeout(loop, Math.max(500, intervalMs))
  }
  frameTimer.value = window.setTimeout(loop, 250)
}

function stopDetectionLoop() {
  if (frameTimer.value) {
    clearTimeout(frameTimer.value)
    frameTimer.value = null
  }
}

async function detectCurrentFrame() {
  if (!captureActive.value || !ocrRunning.value || !props.sessionId || detecting.value) return
  detecting.value = true
  try {
    let result: JadeYoloLiveDetectionResult
    if (backendPreviewActive.value && props.inputMode === 'capture_card') {
      maybeCaptureBackendFrame()
      result = await detectCaptureCardYoloLiveFrame(props.sessionId, {
        rotation: normalizedVideoRotation.value,
        mirror: videoMirrorEnabled.value,
      })
    } else {
      const blob = await captureFrameBlob()
      if (!blob) return
      emit('captureFrame', blob)
      result = await detectJadeYoloLiveFrame(props.sessionId, blob)
    }
    if (!captureActive.value || !ocrRunning.value) return
    lastResult.value = result
    lastDetections.value = result.detections || []
    lastCandidates.value = result.candidates || []
    lastImageSize.value = {
      width: result.image_width || 0,
      height: result.image_height || 0,
    }
    lastError.value = ''
    drawOverlay()
  } catch (error: any) {
    lastError.value = error?.response?.data?.detail || '本地后端未连接'
    clearOverlay()
  } finally {
    detecting.value = false
  }
}

function maybeCaptureBackendFrame() {
  const now = performance.now()
  if (lastFrameUploadAt.value && now - lastFrameUploadAt.value < CAPTURE_CARD_FRAME_UPLOAD_INTERVAL_MS) return
  lastFrameUploadAt.value = now
  emit('captureBackendFrame')
}

async function captureFrameBlob() {
  const video = videoRef.value
  const image = imageRef.value
  const source = backendPreviewActive.value ? image : video
  const sourceWidth = backendPreviewActive.value ? image?.naturalWidth : video?.videoWidth
  const sourceHeight = backendPreviewActive.value ? image?.naturalHeight : video?.videoHeight
  if (!source || !sourceWidth || !sourceHeight) return null

  const scale = Math.min(1, MAX_CAPTURE_WIDTH / sourceWidth)
  const width = Math.round(sourceWidth * scale)
  const height = Math.round(sourceHeight * scale)
  captureCanvas.width = width
  captureCanvas.height = height
  const context = captureCanvas.getContext('2d')
  if (!context) return null

  if (normalizedVideoRotation.value === 180 || videoMirrorEnabled.value) {
    context.save()
    context.translate(width / 2, height / 2)
    if (normalizedVideoRotation.value === 180) context.rotate(Math.PI)
    context.scale(videoMirrorEnabled.value ? -1 : 1, 1)
    context.drawImage(source, -width / 2, -height / 2, width, height)
    context.restore()
  } else {
    context.drawImage(source, 0, 0, width, height)
  }
  return new Promise<Blob | null>((resolve) => captureCanvas.toBlob(resolve, 'image/jpeg', 0.82))
}

function handleVideoReady() {
  resizeOverlay()
  drawOverlay()
}

function resizeOverlay() {
  const canvas = overlayCanvasRef.value
  const stage = stageRef.value
  if (!canvas || !stage) return
  const ratio = window.devicePixelRatio || 1
  const width = Math.max(1, Math.round(stage.clientWidth))
  const height = Math.max(1, Math.round(stage.clientHeight))
  const pixelWidth = Math.round(width * ratio)
  const pixelHeight = Math.round(height * ratio)
  if (canvas.width !== pixelWidth) canvas.width = pixelWidth
  if (canvas.height !== pixelHeight) canvas.height = pixelHeight
  const cssWidth = `${width}px`
  const cssHeight = `${height}px`
  if (canvas.style.width !== cssWidth) canvas.style.width = cssWidth
  if (canvas.style.height !== cssHeight) canvas.style.height = cssHeight
  const context = canvas.getContext('2d')
  if (context) context.setTransform(ratio, 0, 0, ratio, 0, 0)
}

function drawOverlay() {
  resizeOverlay()
  const canvas = overlayCanvasRef.value
  const stage = stageRef.value
  const context = canvas?.getContext('2d')
  const imageWidth = lastImageSize.value.width
  const imageHeight = lastImageSize.value.height
  if (!canvas || !stage || !context || !imageWidth || !imageHeight) return

  const stageWidth = stage.clientWidth
  const stageHeight = stage.clientHeight
  context.clearRect(0, 0, stageWidth, stageHeight)

  const scale = videoFitMode.value === 'cover'
    ? Math.max(stageWidth / imageWidth, stageHeight / imageHeight)
    : Math.min(stageWidth / imageWidth, stageHeight / imageHeight)
  const drawWidth = imageWidth * scale
  const drawHeight = imageHeight * scale
  const offsetX = (stageWidth - drawWidth) / 2
  const offsetY = (stageHeight - drawHeight) / 2

  context.font = '700 13px Arial'

  for (const detection of overlayDetections.value) {
    const isLost = detection.tracking_state === 'lost'
    const isCandidate = !detection.confirmed && detection.tracking_state !== 'confirmed'
    context.lineWidth = isLost ? 2 : isCandidate ? 2 : 3
    context.setLineDash(isLost ? [7, 5] : isCandidate ? [5, 4] : [])
    context.strokeStyle = isLost ? '#8fa6af' : isCandidate ? '#f59e0b' : '#18c779'
    context.fillStyle = isLost ? '#8fa6af' : isCandidate ? '#f59e0b' : '#18c779'
    const [x1, y1, x2, y2] = detection.box
    const left = offsetX + x1 * scale
    const top = offsetY + y1 * scale
    const width = (x2 - x1) * scale
    const height = (y2 - y1) * scale
    context.strokeRect(left, top, width, height)
    const label = `${detection.label || 'jade'} ${Math.round(detection.confidence * 100)}%`
    const labelTop = Math.max(16, top - 8)
    context.fillText(label, left + 4, labelTop)
  }
  context.setLineDash([])
}

function isDisplayableDetection(detection: JadeYoloLiveDetection) {
  return detection.confidence >= DISPLAY_CANDIDATE_MIN_CONFIDENCE
}

function bestDetection(detections: JadeYoloLiveDetection[]) {
  let best = detections[0] || null
  for (const detection of detections) {
    if (!best || detection.confidence > best.confidence) best = detection
  }
  return best
}

function clearOverlay() {
  const canvas = overlayCanvasRef.value
  const stage = stageRef.value
  const context = canvas?.getContext('2d')
  if (context && stage) context.clearRect(0, 0, stage.clientWidth, stage.clientHeight)
}

function formatMs(value: number | undefined | null) {
  return typeof value === 'number' ? `${Math.round(value)}ms` : '-'
}

function startFpsMonitor() {
  const video = videoRef.value as (HTMLVideoElement & {
    requestVideoFrameCallback?: (callback: () => void) => number
  }) | null
  stopFpsMonitor()
  fpsFrameCount.value = 0
  fpsWindowStartedAt.value = performance.now()
  lastVideoFrameAt.value = fpsWindowStartedAt.value
  const tick = () => {
    if (!captureActive.value) return
    lastVideoFrameAt.value = performance.now()
    fpsFrameCount.value += 1
    const now = performance.now()
    if (now - fpsWindowStartedAt.value >= 1000) {
      fps.value = (fpsFrameCount.value * 1000) / (now - fpsWindowStartedAt.value)
      fpsFrameCount.value = 0
      fpsWindowStartedAt.value = now
    }
    if (video?.requestVideoFrameCallback) {
      video.requestVideoFrameCallback(tick)
    } else {
      window.requestAnimationFrame(tick)
    }
  }
  staleCheckTimer.value = window.setInterval(() => {
    if (!captureActive.value) return
    if (performance.now() - lastVideoFrameAt.value > staleTimeoutMs.value) {
      handleVideoStreamStalled()
    }
  }, VIDEO_STALE_CHECK_MS)
  if (video?.requestVideoFrameCallback) {
    video.requestVideoFrameCallback(tick)
  } else {
    window.requestAnimationFrame(tick)
  }
}

function startBackendPreviewMonitor() {
  stopFpsMonitor()
  fps.value = 0
  lastVideoFrameAt.value = performance.now()
  resetBackendFpsCounter()
  staleCheckTimer.value = window.setInterval(() => {
    if (!captureActive.value || !backendPreviewActive.value) return
    // Browser MJPEG <img> does not expose per-frame callbacks reliably.
    lastVideoFrameAt.value = performance.now()
  }, VIDEO_STALE_CHECK_MS)
}

function resetBackendFpsCounter() {
  lastBackendFrameCount.value = Number(props.backendFrameCount || 0)
  lastBackendFrameSampleAt.value = performance.now()
}

function updateBackendFps(frameCount: number) {
  const now = performance.now()
  if (!captureActive.value || !backendPreviewActive.value) {
    lastBackendFrameCount.value = frameCount
    lastBackendFrameSampleAt.value = now
    return
  }
  if (!lastBackendFrameSampleAt.value || frameCount < lastBackendFrameCount.value) {
    lastBackendFrameCount.value = frameCount
    lastBackendFrameSampleAt.value = now
    return
  }
  const elapsedMs = now - lastBackendFrameSampleAt.value
  const frameDelta = frameCount - lastBackendFrameCount.value
  if (elapsedMs < 500 || frameDelta <= 0) return
  fps.value = (frameDelta * 1000) / elapsedMs
  lastBackendFrameCount.value = frameCount
  lastBackendFrameSampleAt.value = now
  lastVideoFrameAt.value = now
}

function stopFpsMonitor() {
  if (staleCheckTimer.value) {
    clearInterval(staleCheckTimer.value)
    staleCheckTimer.value = null
  }
}

function handleBackendImageLoad() {
  lastVideoFrameAt.value = performance.now()
  resizeOverlay()
  drawOverlay()
}

function handleBackendImageError() {
  if (!captureActive.value || !backendPreviewActive.value) return
  stopCapture({ keepError: true })
  lastError.value = '采集卡预览流已断开'
  message.warning(lastError.value)
}

defineExpose({ startCapture, stopCapture, startOcr, stopOcr, startRecording, stopRecording })

onMounted(() => {
  window.addEventListener('resize', drawOverlay)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', drawOverlay)
  stopCapture()
})
</script>

<style scoped>
.yolo-live-panel {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-rows: 42px minmax(0, 1fr) 68px;
  background: #020407;
  overflow: hidden;
}

.yolo-live-head {
  height: 42px;
  min-height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid #1c2b35;
  background: #0b1219;
  overflow: hidden;
}

.yolo-live-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  overflow: hidden;
}

.yolo-live-title span {
  color: #f1fff9;
  font-size: 13px;
  font-weight: 800;
}

.yolo-live-title small {
  overflow: hidden;
  color: #8fa6af;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.yolo-live-head-tags {
  display: flex;
  flex: 0 1 auto;
  flex-wrap: nowrap;
  justify-content: flex-end;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
}

.stream-pill {
  flex: 0 1 auto;
  min-width: 0;
  max-width: 86px;
  padding: 4px 7px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  color: #7d909a;
  background: rgba(255, 255, 255, 0.04);
  font-size: 11px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stream-pill.is-on {
  color: #dffcf4;
  border-color: rgba(43, 190, 255, 0.45);
  background: rgba(43, 190, 255, 0.12);
}

.stream-pill.ocr {
  border-color: rgba(245, 158, 11, 0.48);
  background: rgba(245, 158, 11, 0.13);
}

.stream-pill.rec {
  border-color: rgba(239, 68, 68, 0.55);
  background: rgba(239, 68, 68, 0.14);
}

.yolo-live-stage {
  position: relative;
  min-height: 0;
  overflow: hidden;
  background: #000;
  width: 100%;
  height: 100%;
}

.yolo-live-video,
.yolo-live-overlay,
.yolo-live-empty {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.yolo-live-video {
  object-fit: contain;
  background: #000;
  transform-origin: center;
}

.yolo-live-video.is-fill-preview {
  object-fit: cover;
}

.yolo-live-video.is-rotated-180 {
  transform: rotate(180deg);
}

.yolo-live-video.is-mirrored {
  transform: scaleX(-1);
}

.yolo-live-video.is-rotated-180.is-mirrored {
  transform: rotate(180deg) scaleX(-1);
}

.yolo-live-overlay {
  pointer-events: none;
}

.fps-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  padding: 4px 7px;
  border: 1px solid rgba(34, 211, 166, 0.35);
  border-radius: 6px;
  color: #dcfff6;
  background: rgba(0, 0, 0, 0.55);
  font-size: 12px;
  font-weight: 800;
}

.signal-warning {
  position: absolute;
  top: 10px;
  right: 10px;
  max-width: calc(100% - 96px);
  padding: 5px 8px;
  border: 1px solid rgba(245, 158, 11, 0.5);
  border-radius: 6px;
  color: #ffe6b0;
  background: rgba(0, 0, 0, 0.62);
  font-size: 12px;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.yolo-live-empty {
  display: grid;
  place-items: center;
  color: #5f737d;
  font-size: 14px;
  font-weight: 700;
}

.yolo-live-metrics {
  height: 68px;
  min-height: 68px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  padding: 8px;
  border-top: 1px solid #1c2b35;
  background: #0b1219;
  overflow: hidden;
}

.yolo-live-metric {
  height: 52px;
  max-height: 52px;
  min-width: 0;
  padding: 6px 8px;
  overflow: hidden;
  display: grid;
  grid-template-rows: 14px 20px;
  align-content: center;
  gap: 3px;
}

.yolo-live-metric .analysis-value {
  display: block;
  min-width: 0;
  max-width: 100%;
  height: 20px;
  line-height: 20px;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.yolo-live-metric .metric-label {
  display: block;
  height: 14px;
  line-height: 14px;
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
