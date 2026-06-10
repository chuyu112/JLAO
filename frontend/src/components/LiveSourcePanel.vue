<template>
  <section class="panel live-source-panel">
    <div class="live-preview" :class="{ 'is-capturing': captureActive }">
      <video v-if="captureActive" ref="captureVideo" class="live-media" autoplay playsinline controls />
      <img v-else-if="latestFrame" class="live-media latest-live-frame" :src="resolveAssetUrl(latestFrame.image_path)" :alt="latestFrame.detected_scene" />
      <div v-else class="empty-state compact">
        请在下方选择接入直播画面。
      </div>
    </div>

    <div class="frame-analysis">
      <div class="metric-box live-analysis-box recognized-product-box" :class="{ 'manual-override': manualProductName, 'recognition-candidate': !manualProductName && ((latestFrame?.recognition_confidence ?? 0) < 0.6) && !!latestFrame?.recognized_product_name }">
        <span class="metric-label">识别商品</span>
        <span class="analysis-value">{{ recognizedProductLabel }}</span>
        <span v-if="recognitionMeta" class="recognition-meta">{{ recognitionMeta }}</span>
      </div>
      <div class="metric-box live-analysis-box">
        <span class="metric-label">画面识别</span>
        <span class="analysis-value">{{ frameAnalyzing ? '识别中' : latestFrame?.detected_scene || (captureActive ? '手动识别' : '待接入') }}</span>
      </div>
      <div class="metric-box live-analysis-box jade-attribute-box">
        <span class="metric-label">翡翠属性</span>
        <span class="analysis-value">{{ jadeAttributeLabel }}</span>
        <span v-if="jadeAttributeSourceLabel" class="recognition-meta">{{ jadeAttributeSourceLabel }}</span>
      </div>
      <div class="metric-box live-analysis-box">
        <span class="metric-label">清晰度</span>
        <span class="analysis-value">{{ formatScore(latestFrame?.sharpness_score) }}</span>
      </div>
      <div class="metric-box live-analysis-box">
        <span class="metric-label">亮度</span>
        <span class="analysis-value">{{ formatScore(latestFrame?.brightness_score) }}</span>
      </div>
    </div>

    <div v-if="hasColorDiagnostics" class="live-color-diagnostics">
      <div class="live-color-head">
        <span>颜色诊断</span>
        <strong>{{ colorLayer('family') || '未提供' }} / {{ colorLayer('detail') || '未提供' }} / {{ colorLayer('pattern') || '未提供' }}</strong>
      </div>
      <div v-if="observedColors('opencv_subject_colors').length" class="live-color-row">
        <span>主体 ROI</span>
        <b v-for="candidate in observedColors('opencv_subject_colors')" :key="`subject-${candidate.family}-${candidate.ratio}`">
          {{ candidate.family }} {{ ratioPercent(candidate.ratio) }}
        </b>
      </div>
      <div v-if="observedColors('opencv_frame_colors').length" class="live-color-row muted">
        <span>画面整体</span>
        <b v-for="candidate in observedColors('opencv_frame_colors')" :key="`frame-${candidate.family}-${candidate.ratio}`">
          {{ candidate.family }} {{ ratioPercent(candidate.ratio) }}
        </b>
      </div>
      <small v-if="opencvPatternLabel">{{ opencvPatternLabel }}</small>
      <small v-if="subjectRoiLabel">{{ subjectRoiLabel }}</small>
    </div>

  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { resolveAssetUrl } from '../api/jlao'
import type { FrameSnapshot } from '../types'

const props = defineProps<{
  liveUrl: string | null
  sttConnected: boolean
  sttError: string
  latestFrame: FrameSnapshot | null
  frameAnalyzing: boolean
  sessionId: string | null
  manualProductName: string
}>()

const emit = defineEmits<{
  update: [url: string | null]
  startStt: []
  stopStt: []
  audioFrame: [frame: ArrayBuffer]
  captureFrame: [frame: Blob]
}>()

const message = useMessage()
const captureVideo = ref<HTMLVideoElement | null>(null)
const captureActive = ref(false)
const captureStarting = ref(false)
const audioActive = ref(false)
const captureMode = ref<CaptureMode | null>(null)
const stream = ref<MediaStream | null>(null)
const audioContext = ref<AudioContext | null>(null)
const audioProcessor = ref<ScriptProcessorNode | null>(null)
const audioSource = ref<MediaStreamAudioSourceNode | null>(null)
const projectedAudioStream = ref<MediaStream | null>(null)
const frameTimer = ref<number | null>(null)
const captureFrameBusy = ref(false)
const imageCapture = ref<{ grabFrame: () => Promise<ImageBitmap> } | null>(null)

type CaptureMode = 'tab' | 'screen'

const recognizedProductLabel = computed(() => {
  if (props.manualProductName) return props.manualProductName
  const frame = props.latestFrame
  if (props.frameAnalyzing) return '识别中'
  if (frame?.recognized_product_name) return frame.recognized_product_name
  return '待识别'
})

const recognitionMeta = computed(() => {
  if (props.manualProductName) return '手动矫正'
  const frame = props.latestFrame
  if (!frame?.recognized_product_name) return ''
  const parts: string[] = []
  if (frame.recognition_source) parts.push(frame.recognition_source)
  if (frame.recognition_confidence != null) {
    const label = frame.recognition_confidence >= 0.6 ? `置信 ${frame.recognition_confidence.toFixed(2)}` : `候选 ${frame.recognition_confidence.toFixed(2)}`
    parts.push(label)
  }
  return parts.join(' · ')
})

const jadeAttributeLabel = computed(() => {
  const frame = props.latestFrame
  if (props.frameAnalyzing) return '识别中'
  if (!frame) return '待识别'
  const parts = [
    frame.jade_color,
    frame.jade_water,
    frame.jade_style,
    frame.jade_theme,
  ].filter(Boolean)
  return parts.length ? parts.join(' · ') : '待识别'
})

const jadeAttributeSourceLabel = computed(() => {
  const frame = props.latestFrame
  const sources = frame?.jade_attribute_sources || {}
  const parts = ['color', 'water', 'style', 'theme']
    .map((key) => {
      const source = sources[key]
      if (!source?.source) return ''
      return `${source.source}${source.method ? `/${source.method}` : ''}`
    })
    .filter(Boolean)
  return Array.from(new Set(parts)).slice(0, 3).join(' · ')
})

type ObservedColor = { family: string; ratio: number }

const colorAnalysis = computed(() => recordSignal(props.latestFrame?.jade_color_analysis))

const hasColorDiagnostics = computed(() => Boolean(
  colorLayer('family') ||
  colorLayer('detail') ||
  colorLayer('pattern') ||
  observedColors('opencv_subject_colors').length ||
  observedColors('opencv_frame_colors').length ||
  opencvPatternLabel.value ||
  subjectRoiLabel.value
))

const opencvPatternLabel = computed(() => {
  const candidate = colorDiagnosticValue('opencv_pattern_candidate')
  if (!candidate) return ''
  const reason = colorDiagnosticValue('opencv_pattern_reason')
  const policy = colorAnalysis.value.vlm_color_signal === true ? 'VLM已锁定主色，仅作诊断' : '可用于缺失补全'
  return `OpenCV花色候选：${candidate}${reason ? ` / ${reason}` : ''} / ${policy}`
})

const subjectRoiLabel = computed(() => {
  const roi = recordSignal(colorAnalysis.value.opencv_subject_roi)
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
})

function colorLayer(key: 'family' | 'detail' | 'pattern') {
  const value = colorAnalysis.value[key]
  return typeof value === 'string' ? value : ''
}

function colorDiagnosticValue(key: string) {
  const value = colorAnalysis.value[key]
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') return String(value)
  return typeof value === 'string' ? value : ''
}

function observedColors(key: 'opencv_subject_colors' | 'opencv_frame_colors'): ObservedColor[] {
  const value = colorAnalysis.value[key]
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

function ratioPercent(value: number) {
  return `${Math.round((value || 0) * 100)}%`
}

function recordSignal(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

async function startWindowCapture(mode: CaptureMode) {
  if (!navigator.mediaDevices?.getDisplayMedia) {
    message.error('当前浏览器不支持音画接入，请使用最新版 Chrome 或 Edge。')
    return
  }

  captureStarting.value = true
  try {
    const displaySurface = mode === 'tab' ? 'browser' : 'window'
    const mediaOptions: DisplayMediaStreamOptions = {
      video: {
        displaySurface,
        frameRate: 30,
        width: { ideal: 1920 },
        height: { ideal: 1080 },
      } as MediaTrackConstraints,
      audio: true,
      preferCurrentTab: false,
      selfBrowserSurface: 'exclude',
      systemAudio: 'exclude',
      surfaceSwitching: 'include',
    } as DisplayMediaStreamOptions

    stream.value = await navigator.mediaDevices.getDisplayMedia(mediaOptions)

    audioActive.value = stream.value.getAudioTracks().length > 0
    captureMode.value = mode
    captureActive.value = true
    await nextTick()

    if (captureVideo.value) {
      captureVideo.value.srcObject = stream.value
      captureVideo.value.muted = false
      captureVideo.value.volume = 1
      await captureVideo.value.play()
    }

    message.success(audioActive.value ? '直播标签页画面和声音已接入；开始每秒截图识别' : '直播标签页画面已接入；开始每秒截图识别')
    startFrameCaptureLoop()

    // 启动音频采集（如果有音频轨道）
    if (audioActive.value) {
      emit('startStt')
      await startAudioStreaming(stream.value)
    }

    const [videoTrack] = stream.value.getVideoTracks()
    if ('ImageCapture' in window && videoTrack) {
      imageCapture.value = new (window as unknown as { ImageCapture: new (track: MediaStreamTrack) => { grabFrame: () => Promise<ImageBitmap> } }).ImageCapture(videoTrack)
    }
    videoTrack.addEventListener('ended', stopWindowCapture)
    for (const audioTrack of stream.value.getAudioTracks()) {
      audioTrack.addEventListener('ended', () => {
        audioActive.value = false
      })
    }
  } catch (error) {
    const secure = window.isSecureContext || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    message.error(secure ? '没有选择采集来源。' : '浏览器要求 HTTPS 或 localhost 才能接入直播音画。')
  } finally {
    captureStarting.value = false
  }
}

function stopWindowCapture() {
  stopFrameCaptureLoop()
  stopAudioStreaming()
  emit('stopStt')
  stream.value?.getTracks().forEach((track) => track.stop())
  stream.value = null
  imageCapture.value = null
  captureMode.value = null
  captureActive.value = false
  audioActive.value = false
  if (captureVideo.value) captureVideo.value.srcObject = null
}

async function startAudioStreaming(mediaStream: MediaStream) {
  stopAudioStreaming()
  const audioTracks = mediaStream.getAudioTracks()
  if (audioTracks.length === 0) return

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

async function startProjectedAudioCapture() {
  message.error('实时转写使用手机原生音频。')
  return false
}

function stopProjectedAudioCapture() {
  stopAudioStreaming()
  projectedAudioStream.value?.getTracks().forEach((track) => track.stop())
  projectedAudioStream.value = null
  audioActive.value = false
  emit('stopStt')
}

function stopAudioStreaming() {
  audioProcessor.value?.disconnect()
  audioSource.value?.disconnect()
  audioContext.value?.close()
  audioProcessor.value = null
  audioSource.value = null
  audioContext.value = null
}

function startFrameCaptureLoop() {
  stopFrameCaptureLoop()
  frameTimer.value = window.setInterval(() => {
    void captureCurrentFrame()
  }, 1000)
  window.setTimeout(() => {
    void captureCurrentFrame()
  }, 800)
}

function stopFrameCaptureLoop() {
  if (frameTimer.value) {
    window.clearInterval(frameTimer.value)
    frameTimer.value = null
  }
  captureFrameBusy.value = false
}

async function captureCurrentFrame() {
  if (!captureActive.value || props.frameAnalyzing || captureFrameBusy.value) return

  captureFrameBusy.value = true
  try {
    const blob = await captureFrameBlob()
    if (blob) {
      emit('captureFrame', blob)
    } else {
      message.warning(captureMode.value === 'tab' ? '当前截图仍是黑屏，已跳过上传；请改用窗口/整屏画面模式测试。' : '当前截图仍是黑屏，已跳过上传；建议下一步使用本地采集助手。')
    }
  } catch (error) {
    message.error('当前画面截图失败，请重新接入直播画面')
  } finally {
    captureFrameBusy.value = false
  }
}

async function captureFrameBlob() {
  const maxWidth = 1920
  if (imageCapture.value) {
    const bitmap = await imageCapture.value.grabFrame()
    try {
      const blob = await renderFrameToBlob(bitmap, bitmap.width, bitmap.height, maxWidth)
      if (blob) return blob
    } finally {
      bitmap.close()
    }
  }

  const video = captureVideo.value
  if (!video?.videoWidth || !video.videoHeight) return null
  return renderFrameToBlob(video, video.videoWidth, video.videoHeight, maxWidth)
}

async function renderFrameToBlob(source: CanvasImageSource, sourceWidth: number, sourceHeight: number, maxWidth: number) {
  const scale = Math.min(1, maxWidth / sourceWidth)
  const width = Math.round(sourceWidth * scale)
  const height = Math.round(sourceHeight * scale)
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d', { willReadFrequently: true })
  if (!context) return null
  context.drawImage(source, 0, 0, sourceWidth, sourceHeight, 0, 0, width, height)
  if (isMostlyBlackFrame(context, width, height)) return null
  return new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.92))
}

function isMostlyBlackFrame(context: CanvasRenderingContext2D, width: number, height: number) {
  const sampleWidth = Math.min(160, width)
  const sampleHeight = Math.min(90, height)
  const data = context.getImageData(0, 0, sampleWidth, sampleHeight).data
  let brightPixels = 0
  for (let index = 0; index < data.length; index += 16) {
    if (data[index] + data[index + 1] + data[index + 2] > 45) brightPixels += 1
  }
  return brightPixels / (data.length / 16) < 0.02
}

function formatScore(value: number | null | undefined) {
  return value == null ? '-' : String(Math.round(value))
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

defineExpose({
  startProjectedAudioCapture,
  stopProjectedAudioCapture,
})

onBeforeUnmount(() => {
  stopWindowCapture()
  stopProjectedAudioCapture()
})
</script>

<style scoped>
.live-color-diagnostics {
  margin-top: 12px;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid rgba(94, 232, 199, 0.16);
  background: rgba(10, 22, 27, 0.72);
  display: grid;
  gap: 8px;
}

.live-color-head,
.live-color-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.live-color-head span,
.live-color-row span,
.live-color-diagnostics small {
  color: #8fa3b6;
  font-size: 12px;
}

.live-color-head strong {
  color: #dcfff6;
  font-size: 13px;
}

.live-color-row b {
  padding: 3px 7px;
  border-radius: 999px;
  color: #dcfff6;
  background: rgba(94, 232, 199, 0.13);
  font-size: 12px;
  font-weight: 700;
}

.live-color-row.muted {
  opacity: 0.8;
}
</style>
