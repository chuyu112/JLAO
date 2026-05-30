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
      <div class="metric-box live-analysis-box">
        <span class="metric-label">清晰度</span>
        <span class="analysis-value">{{ formatScore(latestFrame?.sharpness_score) }}</span>
      </div>
      <div class="metric-box live-analysis-box">
        <span class="metric-label">亮度</span>
        <span class="analysis-value">{{ formatScore(latestFrame?.brightness_score) }}</span>
      </div>
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
const audioInputStream = ref<MediaStream | null>(null)
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
      audio: mode === 'tab' ? {
        echoCancellation: false,
        noiseSuppression: false,
        sampleRate: 48000,
        suppressLocalAudioPlayback: false,
      } as MediaTrackConstraints : false,
      preferCurrentTab: false,
      selfBrowserSurface: 'exclude',
      systemAudio: mode === 'tab' ? 'include' : 'exclude',
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
    if (audioActive.value) {
      emit('startStt')
      await startAudioStreaming(stream.value)
    }
    startFrameCaptureLoop()

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

async function startAudioInputCapture() {
  if (!props.sessionId) {
    message.error('请先载入手机端会话。')
    return false
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    message.error('当前浏览器不支持音频输入采集，请使用最新版 Chrome 或 Edge。')
    return false
  }
  if (audioInputStream.value && audioActive.value) {
    emit('startStt')
    if (!audioProcessor.value) {
      await startAudioStreaming(audioInputStream.value)
    }
    return true
  }

  try {
    const mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
        sampleRate: 48000,
      },
      video: false,
    })
    audioInputStream.value = mediaStream
    audioActive.value = true
    emit('startStt')
    await startAudioStreaming(mediaStream)
    for (const audioTrack of mediaStream.getAudioTracks()) {
      audioTrack.addEventListener('ended', () => {
        stopAudioInputCapture()
      })
    }
    message.success('音频输入已随手机端同步接入。')
    return true
  } catch (error) {
    audioInputStream.value = null
    audioActive.value = false
    emit('stopStt')
    message.error('音频输入未接入，请确认浏览器麦克风权限和电脑音频输入设备。')
    return false
  }
}

async function startProjectedAudioCapture() {
  if (!props.sessionId) {
    message.error('请先载入手机端会话。')
    return false
  }
  if (!navigator.mediaDevices?.getDisplayMedia) {
    message.error('当前浏览器不支持投屏音频采集，请使用最新版 Chrome 或 Edge。')
    return false
  }
  if (projectedAudioStream.value && audioActive.value) {
    if (!audioProcessor.value) {
      await startAudioStreaming(projectedAudioStream.value)
    }
    emit('startStt')
    return true
  }

  try {
    const mediaOptions: DisplayMediaStreamOptions = {
      video: {
        displaySurface: 'monitor',
        frameRate: { ideal: 1, max: 1 },
        width: { ideal: 1280 },
        height: { ideal: 720 },
      } as MediaTrackConstraints,
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
        sampleRate: 48000,
        suppressLocalAudioPlayback: false,
      } as MediaTrackConstraints,
      preferCurrentTab: false,
      selfBrowserSurface: 'exclude',
      systemAudio: 'include',
      surfaceSwitching: 'exclude',
    } as DisplayMediaStreamOptions

    const mediaStream = await navigator.mediaDevices.getDisplayMedia(mediaOptions)
    if (mediaStream.getAudioTracks().length === 0) {
      mediaStream.getTracks().forEach((track) => track.stop())
      projectedAudioStream.value = null
      audioActive.value = false
      emit('stopStt')
      message.error('投屏系统音频未接入，请在浏览器弹窗选择整个屏幕并勾选共享系统音频。')
      return false
    }

    projectedAudioStream.value = mediaStream
    audioActive.value = true
    await startAudioStreaming(mediaStream)
    emit('startStt')
    for (const track of mediaStream.getTracks()) {
      track.addEventListener('ended', () => {
        stopProjectedAudioCapture()
      })
    }
    message.success('投屏声音已随手机采集接入实时转写。')
    return true
  } catch (error) {
    projectedAudioStream.value = null
    audioActive.value = false
    emit('stopStt')
    const secure = window.isSecureContext || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    message.error(secure ? '没有选择投屏音频来源。' : '浏览器要求 HTTPS 或 localhost 才能接入投屏系统音频。')
    return false
  }
}

function stopProjectedAudioCapture() {
  stopAudioStreaming()
  projectedAudioStream.value?.getTracks().forEach((track) => track.stop())
  projectedAudioStream.value = null
  audioActive.value = false
  emit('stopStt')
}

function stopAudioInputCapture() {
  stopAudioStreaming()
  audioInputStream.value?.getTracks().forEach((track) => track.stop())
  audioInputStream.value = null
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
  const crop = captureMode.value === 'tab' ? getScaledTabCaptureCrop(sourceWidth, sourceHeight) : null
  const inputX = crop?.x ?? 0
  const inputY = crop?.y ?? 0
  const inputWidth = crop?.width ?? sourceWidth
  const inputHeight = crop?.height ?? sourceHeight
  const scale = Math.min(1, maxWidth / inputWidth)
  const width = Math.round(inputWidth * scale)
  const height = Math.round(inputHeight * scale)
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d', { willReadFrequently: true })
  if (!context) return null
  context.drawImage(source, inputX, inputY, inputWidth, inputHeight, 0, 0, width, height)
  if (isMostlyBlackFrame(context, width, height)) return null
  return new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.92))
}

function getScaledTabCaptureCrop(sourceWidth: number, sourceHeight: number) {
  const TAB_CAPTURE_CROP = { x: 520, y: 0, width: 480, height: 845 }
  const scaleX = sourceWidth / 1920
  const scaleY = sourceHeight / 920
  const x = clamp(Math.round(TAB_CAPTURE_CROP.x * scaleX), 0, sourceWidth - 1)
  const y = clamp(Math.round(TAB_CAPTURE_CROP.y * scaleY), 0, sourceHeight - 1)
  const width = clamp(Math.round(TAB_CAPTURE_CROP.width * scaleX), 80, sourceWidth - x)
  const height = clamp(Math.round(TAB_CAPTURE_CROP.height * scaleY), 80, sourceHeight - y)
  return { x, y, width, height }
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

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), Math.max(min, max))
}

defineExpose({
  startProjectedAudioCapture,
  stopProjectedAudioCapture,
  startAudioInputCapture,
  stopAudioInputCapture,
})

onBeforeUnmount(() => {
  stopWindowCapture()
  stopProjectedAudioCapture()
  stopAudioInputCapture()
})
</script>
