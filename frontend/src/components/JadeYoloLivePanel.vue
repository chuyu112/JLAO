<template>
  <section class="yolo-live-panel">
    <div class="yolo-live-head">
      <div class="yolo-live-title">
        <span>复制视频流 YOLO识别</span>
        <small>{{ statusLabel }}</small>
      </div>
      <div class="yolo-live-actions">
        <button
          v-if="!captureActive"
          :disabled="connectDisabled || captureStarting"
          @click="startCapture"
          class="jlao-btn jlao-btn-connect"
        >
          <span v-if="captureStarting" class="jlao-btn-spinner"></span>
          <video-icon v-else :size="18" />
          接入视频流
        </button>
        <template v-else>
          <button
            @click="toggleRecording"
            :class="['jlao-btn', isRecording ? 'jlao-btn-recording' : 'jlao-btn-record']"
          >
            <circle-dot v-if="isRecording" :size="16" class="rec-dot" />
            <circle v-else :size="16" />
            {{ isRecording ? '停止录屏' : '录屏' }}
          </button>
          <button @click="() => stopCapture()" class="jlao-btn jlao-btn-stop">
            <square :size="14" />
            停止
          </button>
        </template>
      </div>
    </div>

    <div ref="stageRef" class="yolo-live-stage">
      <video
        v-show="captureActive"
        ref="videoRef"
        class="yolo-live-video"
        autoplay
        muted
        playsinline
        @loadedmetadata="handleVideoReady"
      />
      <canvas ref="overlayCanvasRef" class="yolo-live-overlay" />
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
        <span class="metric-label">主播语音</span>
        <span class="analysis-value">{{ audioLabel }}</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { Square, Video as VideoIcon, Circle, CircleDot } from 'lucide-vue-next'
import { detectJadeYoloLiveFrame } from '../api/jlao'
import type { JadeYoloLiveDetection, JadeYoloLiveDetectionResult } from '../types'

const props = defineProps<{
  sessionId: string | null
  sourceActive?: boolean
  sourceBlocked?: boolean
  nativeSttRunning?: boolean
}>()

const emit = defineEmits<{
  startStt: []
  stopStt: []
  audioFrame: [frame: ArrayBuffer]
  captureStateChange: [active: boolean]
}>()

const DETECT_INTERVAL_MS = 200
const MAX_CAPTURE_WIDTH = 1920
const DISPLAY_CANDIDATE_MIN_CONFIDENCE = 0.01
const DISPLAY_CONFIRMED_MIN_CONFIDENCE = 0.03

const message = useMessage()
const stageRef = ref<HTMLDivElement | null>(null)
const videoRef = ref<HTMLVideoElement | null>(null)
const overlayCanvasRef = ref<HTMLCanvasElement | null>(null)
const captureActive = ref(false)
const captureStarting = ref(false)
const detecting = ref(false)
const audioActive = ref(false)
const stream = ref<MediaStream | null>(null)
const frameTimer = ref<number | null>(null)
const isRecording = ref(false)
const mediaRecorder = ref<MediaRecorder | null>(null)
const recordedChunks = ref<Blob[]>([])
const recordingStartTime = ref<number>(0)
const audioContext = ref<AudioContext | null>(null)
const audioProcessor = ref<ScriptProcessorNode | null>(null)
const audioSource = ref<MediaStreamAudioSourceNode | null>(null)
const lastResult = ref<JadeYoloLiveDetectionResult | null>(null)
const lastDetections = ref<JadeYoloLiveDetection[]>([])
const lastCandidates = ref<JadeYoloLiveDetection[]>([])
const displayDetections = computed(() => lastDetections.value.filter((detection) => isDisplayableDetection(detection)))
const displayCandidates = computed(() => lastCandidates.value.filter((detection) => isDisplayableDetection(detection)))
const overlayDetections = computed(() => displayDetections.value.length ? displayDetections.value : displayCandidates.value)
const lastTiming = computed(() => lastResult.value?.timings || null)
const lastTracking = computed(() => lastResult.value?.tracking || null)
const lastImageSize = ref({ width: 0, height: 0 })
const lastError = ref('')
const captureCanvas = document.createElement('canvas')

const statusLabel = computed(() => {
  if (!props.sessionId) return '等待会话'
  if (lastError.value) return lastError.value
  if (detecting.value) return '检测中'
  if (lastTracking.value?.status === 'confirmed') return '追踪中'
  if (lastTracking.value?.status === 'pending') return '候选确认中'
  if (lastTracking.value?.status === 'lost') return '短暂保持'
  if (captureActive.value) return '运行中'
  return '待接入'
})

const detectionLabel = computed(() => {
  const count = displayDetections.value.length
  const candidateCount = displayCandidates.value.length
  const tracking = lastTracking.value
  if (!captureActive.value) return '-'
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
  if (!count) return '未确认'
  return '未确认'
})

const audioLabel = computed(() => {
  if (!captureActive.value) return '-'
  if (props.nativeSttRunning) return 'Native 音频已接入'
  return audioActive.value ? '已接入' : '未共享'
})

const connectDisabled = computed(() => !props.sessionId || !props.sourceActive || props.sourceBlocked)

async function startCapture(): Promise<boolean> {
  if (captureActive.value) return true
  if (captureStarting.value) return false
  if (props.sourceBlocked) {
    message.warning('另一个页面正在采集，请先停止采集')
    return false
  }
  if (!props.sourceActive) {
    message.warning('请先点击采集')
    return false
  }
  if (!props.sessionId) {
    message.warning('请先启动直播会话')
    return false
  }
  if (!navigator.mediaDevices?.getDisplayMedia) {
    message.error('当前浏览器不支持视频接入')
    return false
  }

  captureStarting.value = true
  lastError.value = ''
  try {
    stream.value = await navigator.mediaDevices.getDisplayMedia({
      video: {
        displaySurface: 'window',
        frameRate: 30,
      } as MediaTrackConstraints,
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      } as MediaTrackConstraints,
      selfBrowserSurface: 'exclude',
      systemAudio: 'include',
      windowAudio: 'system',
      surfaceSwitching: 'include',
    } as DisplayMediaStreamOptions & { systemAudio?: string; windowAudio?: string })

    captureActive.value = true
    emit('captureStateChange', true)
    await nextTick()
    if (videoRef.value) {
      videoRef.value.srcObject = stream.value
      await videoRef.value.play()
    }

    const [videoTrack] = stream.value.getVideoTracks()
    videoTrack?.addEventListener('ended', handleVideoTrackEnded)
    for (const audioTrack of stream.value.getAudioTracks()) {
      audioTrack.addEventListener('ended', () => {
        audioActive.value = false
        stopAudioStreaming()
      })
    }
    if (stream.value.getAudioTracks().length) {
      if (props.nativeSttRunning) {
        audioActive.value = false
        message.info('Native 手机音频转写已运行，跳过浏览器音频采集以避免双重识别。')
      } else {
        emit('startStt')
        await startAudioStreaming(stream.value)
        audioActive.value = true
      }
    } else {
      audioActive.value = false
      message.warning('视频已接入，但没有拿到主播音频；请在共享弹窗里选择可共享音频的标签页/窗口并勾选音频。')
    }
    startDetectionLoop()
    return true
  } catch (error) {
    stopCapture()
    lastError.value = '接入失败'
    message.error('没有选择直播画面')
    return false
  } finally {
    captureStarting.value = false
  }
}

function handleVideoTrackEnded() {
  if (!captureActive.value) return
  stopCapture({ keepError: true })
  lastError.value = '视频流已断开，请重新接入'
  message.warning('视频流已断开；投屏恢复后请重新点击“接入视频流”')
}

function stopCapture(options: { keepError?: boolean } = {}) {
  const wasActive = captureActive.value
  stopDetectionLoop()
  stopAudioStreaming()
  stopRecording()
  emit('stopStt')
  stream.value?.getTracks().forEach((track) => track.stop())
  stream.value = null
  captureActive.value = false
  detecting.value = false
  audioActive.value = false
  lastDetections.value = []
  lastCandidates.value = []
  lastResult.value = null
  lastImageSize.value = { width: 0, height: 0 }
  if (videoRef.value) videoRef.value.srcObject = null
  if (!options.keepError) lastError.value = ''
  clearOverlay()
  if (wasActive) emit('captureStateChange', false)
}

// 录屏功能
function toggleRecording() {
  if (isRecording.value) {
    stopRecording()
  } else {
    startRecording()
  }
}

function startRecording() {
  if (!stream.value) return

  recordedChunks.value = []
  recordingStartTime.value = Date.now()

  // 优先使用 vp9 编码，质量更好
  const mimeTypes = [
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm;codecs=vp9',
    'video/webm;codecs=vp8',
    'video/webm',
  ]

  let selectedMimeType = ''
  for (const mimeType of mimeTypes) {
    if (MediaRecorder.isTypeSupported(mimeType)) {
      selectedMimeType = mimeType
      break
    }
  }

  try {
    mediaRecorder.value = selectedMimeType
      ? new MediaRecorder(stream.value, { mimeType: selectedMimeType })
      : new MediaRecorder(stream.value)
  } catch (e) {
    mediaRecorder.value = new MediaRecorder(stream.value)
  }

  mediaRecorder.value.ondataavailable = (event) => {
    if (event.data.size > 0) {
      recordedChunks.value.push(event.data)
    }
  }

  mediaRecorder.value.onstop = () => {
    saveRecording()
  }

  mediaRecorder.value.start(100) // 每 100ms 收集一次数据，确保时长信息完整
  isRecording.value = true
  message.success('开始录屏')
}

function stopRecording() {
  if (!mediaRecorder.value || mediaRecorder.value.state === 'inactive') return
  mediaRecorder.value.stop()
  isRecording.value = false
  message.success('录屏已停止，正在转换为 MP4...')
}

async function saveRecording() {
  if (recordedChunks.value.length === 0) return

  const durationMs = Date.now() - recordingStartTime.value
  const webmBlob = new Blob(recordedChunks.value, { type: 'video/webm' })

  try {
    // 尝试使用 FFmpeg.wasm 转换为 MP4
    // @ts-ignore - FFmpeg.wasm 动态加载，可能没有类型声明
    const { FFmpeg } = await import('@ffmpeg/ffmpeg')
    // @ts-ignore
    const { toBlobURL } = await import('@ffmpeg/util')

    const ffmpeg = new FFmpeg()
    const baseURL = 'https://unpkg.com/@ffmpeg/core@0.12.6/dist/esm'

    await ffmpeg.load({
      coreURL: await toBlobURL(`${baseURL}/ffmpeg-core.js`, 'text/javascript'),
      wasmURL: await toBlobURL(`${baseURL}/ffmpeg-core.wasm`, 'application/wasm'),
    })

    // 写入 WebM 文件
    const webmData = new Uint8Array(await webmBlob.arrayBuffer())
    await ffmpeg.writeFile('input.webm', webmData)

    // 转换为 MP4
    await ffmpeg.exec(['-i', 'input.webm', '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-c:a', 'aac', '-movflags', '+faststart', 'output.mp4'])

    // 读取 MP4 文件
    const mp4Data = await ffmpeg.readFile('output.mp4')
    const mp4Blob = new Blob([mp4Data as BlobPart], { type: 'video/mp4' })

    downloadBlob(mp4Blob, `recording-${new Date().toISOString().replace(/[:.]/g, '-')}.mp4`)
    message.success('录屏已保存为 MP4')
  } catch (e) {
    // FFmpeg 不可用时，下载 WebM 格式
    console.warn('FFmpeg 转换失败，保存为 WebM 格式:', e)
    downloadBlob(webmBlob, `recording-${new Date().toISOString().replace(/[:.]/g, '-')}.webm`)
    message.warning('MP4 转换失败，已保存为 WebM 格式')
  }

  recordedChunks.value = []
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// 截图功能
function takeScreenshot() {
  if (!videoRef.value) return

  const canvas = document.createElement('canvas')
  canvas.width = videoRef.value.videoWidth
  canvas.height = videoRef.value.videoHeight
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  ctx.drawImage(videoRef.value, 0, 0)

  // 添加 YOLO 检测框到截图
  if (overlayCanvasRef.value) {
    ctx.drawImage(overlayCanvasRef.value, 0, 0)
  }

  const url = canvas.toDataURL('image/png')
  const a = document.createElement('a')
  a.href = url
  a.download = `screenshot-${new Date().toISOString().replace(/[:.]/g, '-')}.png`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)

  message.success('截图已保存到下载目录')
}

defineExpose({ startCapture, stopCapture, takeScreenshot })

async function startAudioStreaming(mediaStream: MediaStream) {
  stopAudioStreaming()
  const audioTracks = mediaStream.getAudioTracks()
  if (!audioTracks.length) return

  const context = new AudioContext()
  const source = context.createMediaStreamSource(new MediaStream(audioTracks))
  const processor = context.createScriptProcessor(4096, 1, 1)
  processor.onaudioprocess = (event) => {
    const input = event.inputBuffer.getChannelData(0)
    emit('audioFrame', resampleToPcm16(input, context.sampleRate, 16000))
  }

  const silentOutput = context.createGain()
  silentOutput.gain.value = 0
  source.connect(processor)
  processor.connect(silentOutput)
  silentOutput.connect(context.destination)
  audioContext.value = context
  audioSource.value = source
  audioProcessor.value = processor
}

function stopAudioStreaming() {
  audioProcessor.value?.disconnect()
  audioSource.value?.disconnect()
  void audioContext.value?.close()
  audioProcessor.value = null
  audioSource.value = null
  audioContext.value = null
}

function startDetectionLoop() {
  stopDetectionLoop()
  // 使用 setTimeout 替代 requestAnimationFrame，确保页面不可见时继续运行
  const loop = () => {
    if (!captureActive.value) return
    void detectCurrentFrame()
    frameTimer.value = window.setTimeout(loop, DETECT_INTERVAL_MS)
  }
  frameTimer.value = window.setTimeout(loop, 350)
}

function stopDetectionLoop() {
  if (frameTimer.value) {
    clearTimeout(frameTimer.value)
    frameTimer.value = null
  }
}

async function detectCurrentFrame() {
  if (!captureActive.value || !props.sessionId || detecting.value) return
  const blob = await captureFrameBlob()
  if (!blob) return

  detecting.value = true
  try {
    const result = await detectJadeYoloLiveFrame(props.sessionId, blob)
    if (!captureActive.value) return
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

async function captureFrameBlob() {
  const video = videoRef.value
  if (!video?.videoWidth || !video.videoHeight) return null

  const scale = Math.min(1, MAX_CAPTURE_WIDTH / video.videoWidth)
  const width = Math.round(video.videoWidth * scale)
  const height = Math.round(video.videoHeight * scale)
  captureCanvas.width = width
  captureCanvas.height = height
  const context = captureCanvas.getContext('2d')
  if (!context) return null

  context.drawImage(video, 0, 0, width, height)
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
  canvas.width = Math.round(width * ratio)
  canvas.height = Math.round(height * ratio)
  canvas.style.width = `${width}px`
  canvas.style.height = `${height}px`
  const context = canvas.getContext('2d')
  if (context) context.scale(ratio, ratio)
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

  const scale = Math.min(stageWidth / imageWidth, stageHeight / imageHeight)
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

function resampleToPcm16(input: Float32Array, inputSampleRate: number, outputSampleRate: number) {
  const ratio = inputSampleRate / outputSampleRate
  const outputLength = Math.floor(input.length / ratio)
  const buffer = new ArrayBuffer(outputLength * 2)
  const view = new DataView(buffer)
  for (let index = 0; index < outputLength; index += 1) {
    const sample = Math.max(-1, Math.min(1, input[Math.floor(index * ratio)]))
    view.setInt16(index * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true)
  }
  return buffer
}

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
  grid-template-rows: auto minmax(0, 1fr) auto;
  background: #020407;
}

.yolo-live-head {
  min-height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid #1c2b35;
  background: #0b1219;
  flex-wrap: wrap;
}

.yolo-live-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1 1 auto;
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

.yolo-live-actions {
  flex: 0 0 auto;
  display: flex;
  gap: 8px;
  align-items: center;
}

.yolo-live-title {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
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

.yolo-live-actions {
  flex: 0 0 auto;
  display: flex;
  gap: 8px;
  align-items: center;
}

/* JLAO 自定义按钮 - 匹配整体暗色风格 */
.jlao-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid transparent;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
  white-space: nowrap;
  font-family: inherit;
}

.jlao-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* 接入视频流 - 绿色主按钮，凸起 */
.jlao-btn-connect {
  padding: 10px 24px;
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #22d3a6, #12a97f);
  border-color: rgba(34, 211, 166, 0.3);
  box-shadow:
    0 3px 8px rgba(34, 211, 166, 0.35),
    0 1px 3px rgba(0, 0, 0, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.15);
  transform: translateY(-1px);
}

.jlao-btn-connect:hover:not(:disabled) {
  background: linear-gradient(135deg, #5ee8c7, #22d3a6);
  transform: translateY(-2px);
  box-shadow:
    0 6px 20px rgba(34, 211, 166, 0.5),
    0 2px 6px rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.jlao-btn-connect:active:not(:disabled) {
  transform: translateY(1px);
  box-shadow:
    0 1px 4px rgba(34, 211, 166, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
  background: linear-gradient(135deg, #12a97f, #0e8a65);
}

/* 录屏按钮 - 橙色 */
.jlao-btn-record {
  color: #fff;
  background: rgba(255, 209, 102, 0.15);
  border-color: rgba(255, 209, 102, 0.4);
  box-shadow: 0 2px 6px rgba(255, 209, 102, 0.2);
}

.jlao-btn-record:hover:not(:disabled) {
  background: rgba(255, 209, 102, 0.25);
  border-color: rgba(255, 209, 102, 0.6);
  box-shadow: 0 3px 10px rgba(255, 209, 102, 0.35);
}

/* 录屏中 - 红色脉冲 */
.jlao-btn-recording {
  color: #fff;
  background: rgba(208, 48, 60, 0.2);
  border-color: rgba(208, 48, 60, 0.5);
  box-shadow: 0 2px 6px rgba(208, 48, 60, 0.3);
  animation: pulse-rec 1.5s ease-in-out infinite;
}

.jlao-btn-recording:hover:not(:disabled) {
  background: rgba(208, 48, 60, 0.35);
  border-color: rgba(208, 48, 60, 0.7);
}

.rec-dot {
  animation: blink-rec 1s step-end infinite;
}

@keyframes pulse-rec {
  0%, 100% { box-shadow: 0 2px 6px rgba(208, 48, 60, 0.3); }
  50% { box-shadow: 0 4px 14px rgba(208, 48, 60, 0.6); }
}

@keyframes blink-rec {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* 停止按钮 - 灰色 */
.jlao-btn-stop {
  color: #dce9e4;
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.15);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
}

.jlao-btn-stop:hover:not(:disabled) {
  background: rgba(208, 48, 60, 0.15);
  border-color: rgba(208, 48, 60, 0.4);
  color: #ff6b7a;
}

/* 加载中 spinner */
.jlao-btn-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
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
}

.yolo-live-overlay {
  pointer-events: none;
}

.yolo-live-empty {
  display: grid;
  place-items: center;
  color: #5f737d;
  font-size: 14px;
  font-weight: 700;
}

.yolo-live-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  padding: 8px;
  border-top: 1px solid #1c2b35;
  background: #0b1219;
  position: relative;
  z-index: 10;
}

.yolo-live-metric {
  min-height: 52px;
  padding: 7px 8px;
}
</style>
