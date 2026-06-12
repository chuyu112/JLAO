import { defineStore } from 'pinia'
import { WS_BASE } from '../api/client'
import {
  createReplay,
  createSession,
  fetchAgentUtterances,
  fetchAgents,
  fetchCustomerEvents,
  fetchFrames,
  fetchLiveComments,
  fetchProducts,
  fetchSuggestions,
  fetchTranscripts,
  fetchVirtualCustomers,
  fetchWikiChunks,
  abortRecorder,
  captureCardStreamUrl,
  getCaptureStatus,
  getCaptureCardPreviewStatus,
  getNativeAudioStatus,
  getNativeSttStatus,
  getRecorderStatus,
  getSttRuntimeSettings,
  getScrcpyStatus,
  hardResetCapture,
  setCurrentProduct,
  setLiveUrl,
  setManualProductName,
  softResetCapture,
  startCaptureCardPreview,
  startNativeAudio,
  startNativeStt,
  startRecorder,
  startScrcpy,
  stopNativeAudio,
  stopPhoneCapture,
  stopNativeStt,
  stopRecorder,
  startSession,
  stopScrcpy,
  stopCaptureCardPreview,
  stopSession,
  updateSttRuntimeSettings,
  updateBrowserVideoStatus,
  updateOcrCaptureStatus,
  uploadCaptureCardFrame as uploadCaptureCardFrameApi,
  updateSuggestionStatus,
  uploadFrame,
} from '../api/jlao'
import type {
  AgentProfile,
  AgentUtterance,
  CaptureStatusInfo,
  CaptureCardPreviewInfo,
  FrameSnapshot,
  LiveSession,
  NativeAudioInfo,
  NativeSttInfo,
  PhoneCaptureInfo,
  Product,
  ReplayReport,
  RecorderInfo,
  ScrcpyDeviceInfo,
  SttRuntimeSettings,
  Suggestion,
  TranscriptSegment,
  VirtualCustomer,
  VirtualCustomerEvent,
  WikiChunk,
  WsMessage,
} from '../types'
import {
  clearCaptureModeLock,
  isModeStartBlocked,
  writeCaptureModeLock,
  type CaptureMode,
} from '../utils/captureMode'

interface State {
  products: Product[]
  currentSession: LiveSession | null
  transcripts: TranscriptSegment[]
  suggestions: Suggestion[]
  frames: FrameSnapshot[]
  report: ReplayReport | null
  wikiChunks: WikiChunk[]
  wikiHits: WikiChunk[]
  virtualCustomers: VirtualCustomer[]
  customerEvents: VirtualCustomerEvent[]
  liveComments: VirtualCustomerEvent[]
  agents: AgentProfile[]
  agentUtterances: AgentUtterance[]
  connected: boolean
  loading: boolean
  frameAnalyzing: boolean
  socket: WebSocket | null
  sttSocket: WebSocket | null
  pendingSttFrames: ArrayBuffer[]
  partialTranscript: string
  sttConnected: boolean
  sttError: string
  scrcpyInfo: ScrcpyDeviceInfo | null
  scrcpyLoading: boolean
  phoneCaptureInfo: PhoneCaptureInfo | null
  inputMode: 'capture_card' | 'scrcpy'
  captureCardVideoDeviceId: string
  captureCardAudioDeviceId: string
  captureCardVideoRotation: 0 | 180
  captureCardVideoMirror: boolean
  captureCardInfo: CaptureCardPreviewInfo | null
  captureCardLoading: boolean
  nativeAudioInfo: NativeAudioInfo | null
  nativeAudioLoading: boolean
  nativeSttInfo: NativeSttInfo | null
  nativeSttLoading: boolean
  recorderInfo: RecorderInfo | null
  recorderLoading: boolean
  captureStatusInfo: CaptureStatusInfo | null
  activeCaptureMode: CaptureMode | null
  captureStartupMode: CaptureMode | null
  ocrIntervalMs: number
  videoStaleTimeoutMs: number
  sttRuntimeSettings: SttRuntimeSettings | null
  sttRuntimeSettingsLoading: boolean
  captureResetToken: number
}

const OCR_INTERVAL_STORAGE_KEY = 'jlao_ocr_interval_ms'
const OCR_INTERVAL_OPTIONS = [1000, 2000, 5000]
const VIDEO_STALE_TIMEOUT_STORAGE_KEY = 'jlao_video_stale_timeout_ms'
const VIDEO_STALE_TIMEOUT_OPTIONS = [3000, 5000, 10000]
const INPUT_MODE_STORAGE_KEY = 'jlao_input_mode'
const CAPTURE_CARD_VIDEO_DEVICE_STORAGE_KEY = 'jlao_capture_card_video_device_id'
const CAPTURE_CARD_AUDIO_DEVICE_STORAGE_KEY = 'jlao_capture_card_audio_device_id'
const CAPTURE_CARD_VIDEO_ROTATION_STORAGE_KEY = 'jlao_capture_card_video_rotation'
const CAPTURE_CARD_VIDEO_MIRROR_STORAGE_KEY = 'jlao_capture_card_video_mirror'

function readInputMode(): 'capture_card' | 'scrcpy' {
  const raw = localStorage.getItem(INPUT_MODE_STORAGE_KEY)
  return raw === 'scrcpy' ? 'scrcpy' : 'capture_card'
}

function readCaptureCardVideoRotation(): 0 | 180 {
  return localStorage.getItem(CAPTURE_CARD_VIDEO_ROTATION_STORAGE_KEY) === '180' ? 180 : 0
}

function readCaptureCardVideoMirror(): boolean {
  const raw = localStorage.getItem(CAPTURE_CARD_VIDEO_MIRROR_STORAGE_KEY)
  return raw === null ? true : raw === 'true'
}

function readOcrIntervalMs(): number {
  const raw = Number(localStorage.getItem(OCR_INTERVAL_STORAGE_KEY))
  return OCR_INTERVAL_OPTIONS.includes(raw) ? raw : 1000
}

function readVideoStaleTimeoutMs(): number {
  const raw = Number(localStorage.getItem(VIDEO_STALE_TIMEOUT_STORAGE_KEY))
  return VIDEO_STALE_TIMEOUT_OPTIONS.includes(raw) ? raw : 3000
}

function cleanLiveRoomNameForDisplay(value: string): string {
  const compact = value.replace(/\s+/g, '')
  if (!compact) return ''
  const hasCarrier = /中国移动|中国联通|中国电信|移动|联通|电信/.test(compact)
  const hasStatusMarker = /HD|5G|4G|VoLTE|volte|WiFi|wifi|LTE/.test(compact)
  const hasRoomKeyword = /翡翠|珠宝|玉|手镯|寄售|回流|定制|闲置/.test(compact)
  if (hasCarrier && (hasStatusMarker || !hasRoomKeyword)) return ''
  return value.trim()
}

export const useJlaoStore = defineStore('jlao', {
  state: (): State => ({
    products: [],
    currentSession: null,
    transcripts: [],
    suggestions: [],
    frames: [],
    report: null,
    wikiChunks: [],
    wikiHits: [],
    virtualCustomers: [],
    customerEvents: [],
    liveComments: [],
    agents: [],
    agentUtterances: [],
    connected: false,
    loading: false,
    frameAnalyzing: false,
    socket: null,
    sttSocket: null,
    pendingSttFrames: [],
    partialTranscript: '',
    sttConnected: false,
    sttError: '',
    scrcpyInfo: null,
    scrcpyLoading: false,
    phoneCaptureInfo: null,
    inputMode: readInputMode(),
    captureCardVideoDeviceId: localStorage.getItem(CAPTURE_CARD_VIDEO_DEVICE_STORAGE_KEY) || '',
    captureCardAudioDeviceId: localStorage.getItem(CAPTURE_CARD_AUDIO_DEVICE_STORAGE_KEY) || '',
    captureCardVideoRotation: readCaptureCardVideoRotation(),
    captureCardVideoMirror: readCaptureCardVideoMirror(),
    captureCardInfo: null,
    captureCardLoading: false,
    nativeAudioInfo: null,
    nativeAudioLoading: false,
    nativeSttInfo: null,
    nativeSttLoading: false,
    recorderInfo: null,
    recorderLoading: false,
    captureStatusInfo: null,
    activeCaptureMode: null,
    captureStartupMode: null,
    ocrIntervalMs: readOcrIntervalMs(),
    videoStaleTimeoutMs: readVideoStaleTimeoutMs(),
    sttRuntimeSettings: null,
    sttRuntimeSettingsLoading: false,
    captureResetToken: 0,
  }),

  getters: {
    liveRoomNameLabel(state): string {
      return cleanLiveRoomNameForDisplay(state.currentSession?.live_room_name || '') || '待识别直播间名'
    },
    currentProduct(state): Product | null {
      if (!state.currentSession?.current_product_id) return state.products[0] || null
      return state.products.find((item) => item.id === state.currentSession?.current_product_id) || null
    },
    topSuggestions(state): Suggestion[] {
      return [...state.suggestions]
        .sort((a, b) => b.priority - a.priority || Date.parse(b.created_at) - Date.parse(a.created_at))
        .slice(0, 8)
    },
    captureModeLocked(state): boolean {
      return Boolean(state.captureStartupMode || state.activeCaptureMode)
    },
    isCaptureModeBlocked: (state) => (mode: CaptureMode): boolean => {
      return isModeStartBlocked(mode, state.activeCaptureMode, state.captureStartupMode)
    },
  },

  actions: {
    beginCaptureStartup(mode: CaptureMode): boolean {
      if (isModeStartBlocked(mode, this.activeCaptureMode, this.captureStartupMode)) return false
      this.activeCaptureMode = mode
      this.captureStartupMode = mode
      writeCaptureModeLock(mode)
      return true
    },

    finishCaptureStartup(mode: CaptureMode) {
      if (this.captureStartupMode === mode) this.captureStartupMode = null
    },

    clearCaptureMode(mode: CaptureMode) {
      if (this.captureStartupMode === mode) this.captureStartupMode = null
      if (this.activeCaptureMode === mode) this.activeCaptureMode = null
      clearCaptureModeLock(mode)
    },

    setOcrIntervalMs(value: number) {
      const nextValue = OCR_INTERVAL_OPTIONS.includes(value) ? value : 1000
      this.ocrIntervalMs = nextValue
      localStorage.setItem(OCR_INTERVAL_STORAGE_KEY, String(nextValue))
    },

    setVideoStaleTimeoutMs(value: number) {
      const nextValue = VIDEO_STALE_TIMEOUT_OPTIONS.includes(value) ? value : 3000
      this.videoStaleTimeoutMs = nextValue
      localStorage.setItem(VIDEO_STALE_TIMEOUT_STORAGE_KEY, String(nextValue))
    },

    setInputMode(value: 'capture_card' | 'scrcpy' | string) {
      const nextValue = value === 'scrcpy' ? 'scrcpy' : 'capture_card'
      this.inputMode = nextValue
      localStorage.setItem(INPUT_MODE_STORAGE_KEY, nextValue)
    },

    setCaptureCardVideoDeviceId(value: string) {
      this.captureCardVideoDeviceId = value || ''
      if (value) localStorage.setItem(CAPTURE_CARD_VIDEO_DEVICE_STORAGE_KEY, value)
      else localStorage.removeItem(CAPTURE_CARD_VIDEO_DEVICE_STORAGE_KEY)
    },

    setCaptureCardAudioDeviceId(value: string) {
      this.captureCardAudioDeviceId = value || ''
      if (value) localStorage.setItem(CAPTURE_CARD_AUDIO_DEVICE_STORAGE_KEY, value)
      else localStorage.removeItem(CAPTURE_CARD_AUDIO_DEVICE_STORAGE_KEY)
    },

    setCaptureCardVideoRotation(value: number | string) {
      const nextValue = Number(value) === 180 ? 180 : 0
      this.captureCardVideoRotation = nextValue
      localStorage.setItem(CAPTURE_CARD_VIDEO_ROTATION_STORAGE_KEY, String(nextValue))
    },

    setCaptureCardVideoMirror(value: boolean | string) {
      const nextValue = value === true || value === 'true'
      this.captureCardVideoMirror = nextValue
      localStorage.setItem(CAPTURE_CARD_VIDEO_MIRROR_STORAGE_KEY, String(nextValue))
    },

    async refreshSttRuntimeSettings() {
      this.sttRuntimeSettingsLoading = true
      try {
        this.sttRuntimeSettings = await getSttRuntimeSettings()
      } finally {
        this.sttRuntimeSettingsLoading = false
      }
    },

    async setSttRuntimeDevice(device: string) {
      this.sttRuntimeSettingsLoading = true
      try {
        this.sttRuntimeSettings = await updateSttRuntimeSettings({ local_stt_device: device })
      } finally {
        this.sttRuntimeSettingsLoading = false
      }
    },

    async setSttRuntimeProvider(provider: string) {
      this.sttRuntimeSettingsLoading = true
      try {
        this.sttRuntimeSettings = await updateSttRuntimeSettings({ stt_provider: provider })
      } finally {
        this.sttRuntimeSettingsLoading = false
      }
    },

    async initDemo(platform: string = '抖音') {
      this.loading = true
      try {
        this.products = await fetchProducts()
        if (!this.currentSession) {
          this.currentSession = await createSession({
            title: 'JLAO 翡翠直播',
            platform: platform,
            anchor_name: '主播',
            operator_name: '场控',
            current_product_id: this.products[0]?.id ?? null,
          })
          this.connectSocket()
          await this.refreshOperationBrainData()
        }
      } finally {
        this.loading = false
      }
    },

    _wsUrl(path: string) {
      const token = localStorage.getItem('jlao_token') || ''
      const url = `${WS_BASE}${path}`
      return token ? `${url}?token=${encodeURIComponent(token)}` : url
    },

    connectSocket() {
      if (!this.currentSession) return
      this.socket?.close()
      const socket = new WebSocket(this._wsUrl(`/ws/sessions/${this.currentSession.id}`))
      socket.onopen = () => {
        this.connected = true
        void this.refreshCaptureStatus()
      }
      socket.onclose = () => {
        this.connected = false
      }
      socket.onerror = () => {
        this.connected = false
      }
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data) as WsMessage
        this.handleWsMessage(message)
      }
      this.socket = socket
    },

    handleWsMessage(message: WsMessage) {
      if (message.event === 'session_status') {
        this.currentSession = message.data as LiveSession
      }
      if (message.event === 'transcript_segment') {
        const segment = message.data as TranscriptSegment
        this.partialTranscript = ''
        if (!this.transcripts.some((item) => item.id === segment.id)) {
          this.transcripts.push(segment)
        }
      }
      if (message.event === 'transcript_partial') {
        this.partialTranscript = (message.data as { text?: string }).text || ''
      }
      if (message.event === 'suggestion_created') {
        const suggestion = message.data as Suggestion
        if (!this.suggestions.some((item) => item.id === suggestion.id)) {
          this.suggestions.unshift(suggestion)
        }
      }
      if (message.event === 'suggestion_updated') {
        const updated = message.data as Suggestion
        this.suggestions = this.suggestions.map((item) => (item.id === updated.id ? updated : item))
      }
      if (message.event === 'frame_snapshot') {
        const frame = message.data as FrameSnapshot
        this.frames = [frame, ...this.frames.filter((item) => item.id !== frame.id)].slice(0, 30)
      }
      if (message.event === 'wiki_hits') {
        this.wikiHits = ((message.data as { items?: WikiChunk[] }).items || []).slice(0, 5)
      }
      if (message.event === 'virtual_customer_event' || message.event === 'high_value_customer_alert') {
        const event = message.data as VirtualCustomerEvent
        this.customerEvents = [event, ...this.customerEvents.filter((item) => item.id !== event.id)].slice(0, 30)
      }
      if (message.event === 'live_comment_event') {
        const event = message.data as VirtualCustomerEvent
        this.liveComments = [event, ...this.liveComments.filter((item) => item.id !== event.id)].slice(0, 80)
      }
      if (message.event === 'agent_utterance') {
        const utterance = message.data as AgentUtterance
        this.agentUtterances = [utterance, ...this.agentUtterances.filter((item) => item.id !== utterance.id)].slice(0, 50)
      }
      if (message.event === 'stt_status') {
        const data = message.data as { status?: string; provider?: string; source?: string }
        this.sttConnected = data.status === 'connected'
        if (this.sttConnected) this.sttError = ''
      }
      if (message.event === 'stt_error') {
        this.sttError = (message.data as { message?: string }).message || '实时语音识别异常'
        this.sttConnected = false
      }
      if (message.event === 'native_stt_status') {
        this.nativeSttInfo = message.data as NativeSttInfo
        this.sttConnected = Boolean(this.nativeSttInfo.running)
        if (this.nativeSttInfo.last_error) this.sttError = this.nativeSttInfo.last_error
      }
      if (message.event === 'native_audio_status') {
        this.nativeAudioInfo = message.data as NativeAudioInfo
      }
      if (message.event === 'recorder_status') {
        this.recorderInfo = message.data as RecorderInfo
      }
      if (message.event === 'capture_status') {
        this.captureStatusInfo = message.data as CaptureStatusInfo
      }
    },

    async start() {
      if (!this.currentSession) return
      this.currentSession = await startSession(this.currentSession.id)
      this.connectSocket()
    },

    async stop() {
      if (!this.currentSession) return
      this.disconnectStt()
      await this.stopNativeSttSession()
      await this.stopCaptureCardSession()
      await this.stopScrcpySession()
      await this.stopPhoneCaptureSession()
      this.currentSession = await stopSession(this.currentSession.id)
    },

    async selectProduct(productId: string) {
      if (!this.currentSession) return
      this.currentSession = await setCurrentProduct(this.currentSession.id, productId)
    },

    async setManualProductName(name: string) {
      if (!this.currentSession) return
      this.currentSession = await setManualProductName(this.currentSession.id, name)
    },

    async updateLiveUrl(liveUrl: string | null) {
      if (!this.currentSession) return
      const cleaned = liveUrl?.trim() || null
      this.currentSession = await setLiveUrl(this.currentSession.id, cleaned)
    },

    async refreshSessionData() {
      if (!this.currentSession) return
      const [transcripts, suggestions, frames] = await Promise.all([
        fetchTranscripts(this.currentSession.id),
        fetchSuggestions(this.currentSession.id),
        fetchFrames(this.currentSession.id),
      ])
      this.transcripts = transcripts
      this.suggestions = suggestions
      this.frames = frames
      await this.refreshOperationBrainData()
    },

    async refreshOperationBrainData() {
      if (!this.currentSession) return
      const [wikiChunks, virtualCustomers, customerEvents, liveComments, agents, agentUtterances] = await Promise.all([
        fetchWikiChunks(),
        fetchVirtualCustomers(this.currentSession.id),
        fetchCustomerEvents(this.currentSession.id),
        fetchLiveComments(this.currentSession.id),
        fetchAgents(),
        fetchAgentUtterances(this.currentSession.id),
      ])
      this.wikiChunks = wikiChunks
      this.wikiHits = this.wikiHits.length ? this.wikiHits : wikiChunks.slice(0, 5)
      this.virtualCustomers = virtualCustomers
      this.customerEvents = customerEvents
      this.liveComments = liveComments
      this.agents = agents
      this.agentUtterances = agentUtterances
    },

    async setSuggestionAction(suggestionId: string, action: 'accept' | 'copy' | 'used' | 'reject') {
      const updated = await updateSuggestionStatus(suggestionId, action)
      this.suggestions = this.suggestions.map((item) => (item.id === updated.id ? updated : item))
    },

    async generateReplay() {
      if (!this.currentSession) return
      this.report = await createReplay(this.currentSession.id)
    },

    async uploadCaptureFrame(blob: Blob) {
      if (!this.currentSession || this.frameAnalyzing) return null
      this.frameAnalyzing = true
      try {
        const frame = await uploadFrame(this.currentSession.id, blob)
        this.frames = [frame, ...this.frames.filter((item) => item.id !== frame.id)].slice(0, 30)
        return frame
      } finally {
        this.frameAnalyzing = false
      }
    },

    async uploadCaptureCardFrame() {
      if (!this.currentSession || this.frameAnalyzing) return null
      this.frameAnalyzing = true
      try {
        const frame = await uploadCaptureCardFrameApi(this.currentSession.id, {
          rotation: this.captureCardVideoRotation,
          mirror: this.captureCardVideoMirror,
        })
        this.frames = [frame, ...this.frames.filter((item) => item.id !== frame.id)].slice(0, 30)
        return frame
      } finally {
        this.frameAnalyzing = false
      }
    },

    sendSttAudio(frame: ArrayBuffer) {
      const socket = this.sttSocket
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        this.pendingSttFrames = [...this.pendingSttFrames.slice(-24), frame.slice(0)]
        if (socket?.readyState !== WebSocket.CONNECTING) this.connectStt()
        return
      }
      while (this.pendingSttFrames.length > 0) {
        const pendingFrame = this.pendingSttFrames.shift()
        if (pendingFrame) socket.send(pendingFrame)
      }
      socket.send(frame)
    },

    connectStt() {
      const readyState = this.sttSocket?.readyState
      if (!this.currentSession || readyState === WebSocket.OPEN || readyState === WebSocket.CONNECTING) return
      this.sttError = ''
      const socket = new WebSocket(this._wsUrl(`/ws/sessions/${this.currentSession.id}/stt`))
      socket.binaryType = 'arraybuffer'
      socket.onopen = () => {
        this.sttConnected = true
        while (this.pendingSttFrames.length > 0 && socket.readyState === WebSocket.OPEN) {
          const frame = this.pendingSttFrames.shift()
          if (frame) socket.send(frame)
        }
      }
      socket.onclose = () => {
        this.sttConnected = false
      }
      socket.onerror = () => {
        this.sttError = '语音识别连接失败，请确认本地后端已启动'
        this.sttConnected = false
      }
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data) as WsMessage
        if (message.event === 'stt_status') {
          this.sttConnected = (message.data as { status?: string }).status === 'connected'
        }
        if (message.event === 'stt_error') {
          this.sttError = (message.data as { message?: string }).message || '实时语音识别异常'
          this.sttConnected = false
        }
        if (message.event === 'transcript_partial') {
          this.partialTranscript = (message.data as { text?: string }).text || ''
        }
        if (message.event === 'transcript_segment') {
          const segment = message.data as TranscriptSegment
          this.partialTranscript = ''
          if (!this.transcripts.some((item) => item.id === segment.id)) {
            this.transcripts.push(segment)
          }
        }
      }
      this.sttSocket = socket
    },

    disconnectStt() {
      this.sttSocket?.close()
      this.sttSocket = null
      this.pendingSttFrames = []
      this.sttConnected = false
      this.partialTranscript = ''
    },

    async startScrcpySession(serial = '') {
      if (!this.currentSession) return
      this.scrcpyLoading = true
      try {
        this.scrcpyInfo = await startScrcpy(this.currentSession.id, { serial })
      } catch (e: any) {
        const detail = e?.response?.data?.detail
        this.scrcpyInfo = {
          running: false,
          serial: '',
          last_error: detail || e.message || '启动失败',
          width: 0,
          height: 0,
          recording_path: '',
        }
      } finally {
        this.scrcpyLoading = false
      }
    },

    async stopScrcpySession() {
      if (!this.currentSession) return
      this.scrcpyInfo = await stopScrcpy(this.currentSession.id)
    },

    async refreshScrcpyStatus() {
      if (!this.currentSession) return
      this.scrcpyInfo = await getScrcpyStatus(this.currentSession.id)
    },

    async refreshCaptureStatus() {
      if (!this.currentSession) return
      this.captureStatusInfo = await getCaptureStatus(this.currentSession.id)
      const resources = this.captureStatusInfo.resources
      this.nativeAudioInfo = {
        running: Boolean(resources.native_audio_stream.running),
        state: String(resources.native_audio_stream.state || 'stopped'),
        serial: String(resources.native_audio_stream.serial || ''),
        source: String(resources.native_audio_stream.source || 'playback'),
        device_id: String(resources.native_audio_stream.device_id || ''),
        device_name: String(resources.native_audio_stream.device_name || ''),
        last_error: String(resources.native_audio_stream.last_error || ''),
        audio_chunks: Number(resources.native_audio_stream.audio_chunks || 0),
        audio_bytes: Number(resources.native_audio_stream.audio_bytes || 0),
        consumers: Array.isArray(resources.native_audio_stream.consumers) ? resources.native_audio_stream.consumers as string[] : [],
      }
      this.recorderInfo = {
        running: Boolean(resources.recorder.running),
        state: String(resources.recorder.state || 'stopped'),
        last_error: String(resources.recorder.last_error || ''),
        audio_chunks: Number(resources.recorder.audio_chunks || 0),
        audio_bytes: Number(resources.recorder.audio_bytes || 0),
        output_path: String(resources.recorder.output_path || ''),
        audio_path: String(resources.recorder.audio_path || ''),
        video_path: String(resources.recorder.video_path || ''),
      }
      if (resources.capture_card_input) {
        this.captureCardInfo = {
          running: Boolean(resources.capture_card_input.running),
          state: String(resources.capture_card_input.state || 'stopped'),
          session_id: this.currentSession.id,
          device_id: String(resources.capture_card_input.device_id || ''),
          video_index: Number(resources.capture_card_input.video_index || 0),
          width: Number(resources.capture_card_input.width || 0),
          height: Number(resources.capture_card_input.height || 0),
          fps: Number(resources.capture_card_input.fps || 0),
          frame_width: Number(resources.capture_card_input.frame_width || 0),
          frame_height: Number(resources.capture_card_input.frame_height || 0),
          frame_mean: Number(resources.capture_card_input.frame_mean || 0),
          frame_std: Number(resources.capture_card_input.frame_std || 0),
          signal_present: Boolean(resources.capture_card_input.signal_present),
          frame_count: Number(resources.capture_card_input.frame_count || 0),
          last_error: String(resources.capture_card_input.last_error || ''),
          started_at: 0,
          updated_at: 0,
        }
      }
    },

    getCaptureCardStreamUrl() {
      if (!this.currentSession) return ''
      return captureCardStreamUrl(this.currentSession.id)
    },

    async startCaptureCardSession() {
      if (!this.currentSession) return
      this.captureCardLoading = true
      try {
        this.captureCardInfo = await startCaptureCardPreview(this.currentSession.id, {
          device_id: this.captureCardVideoDeviceId,
          width: 1280,
          height: 720,
          fps: 30,
        })
      } catch (e: any) {
        const detail = e?.response?.data?.detail
        this.captureCardInfo = {
          running: false,
          state: 'error',
          session_id: this.currentSession.id,
          device_id: this.captureCardVideoDeviceId,
          video_index: 0,
          width: 0,
          height: 0,
          fps: 0,
          frame_width: 0,
          frame_height: 0,
          frame_mean: 0,
          frame_std: 0,
          signal_present: false,
          frame_count: 0,
          last_error: detail || e.message || '采集卡输入启动失败',
          started_at: 0,
          updated_at: 0,
        }
        throw e
      } finally {
        this.captureCardLoading = false
      }
    },

    async stopCaptureCardSession() {
      if (!this.currentSession) return
      this.captureCardInfo = await stopCaptureCardPreview(this.currentSession.id)
    },

    async refreshCaptureCardStatus() {
      if (!this.currentSession) return
      this.captureCardInfo = await getCaptureCardPreviewStatus(this.currentSession.id)
    },

    async markBrowserVideoStream(running: boolean, metadata: Record<string, unknown> = {}, lastError = '') {
      if (!this.currentSession) return
      this.captureStatusInfo = await updateBrowserVideoStatus(this.currentSession.id, {
        running,
        last_error: lastError,
        metadata,
      })
    },

    async markOcrCapture(running: boolean, metadata: Record<string, unknown> = {}, lastError = '') {
      if (!this.currentSession) return
      this.captureStatusInfo = await updateOcrCaptureStatus(this.currentSession.id, {
        running,
        last_error: lastError,
        metadata,
      })
    },

    async stopPhoneCaptureSession() {
      if (!this.currentSession) return
      this.phoneCaptureInfo = await stopPhoneCapture(this.currentSession.id)
    },

    async startNativeAudioSession(
      serial = '',
      options: { source?: string; device_id?: string; device_name?: string } = {},
    ) {
      if (!this.currentSession) return
      this.nativeAudioLoading = true
      try {
        this.nativeAudioInfo = await startNativeAudio(this.currentSession.id, {
          serial,
          source: options.source,
          device_id: options.device_id,
          device_name: options.device_name,
        })
      } catch (e: any) {
        const detail = e?.response?.data?.detail
        this.nativeAudioInfo = {
          running: false,
          state: 'error',
          serial: '',
          source: options.source || 'playback',
          device_id: options.device_id || '',
          device_name: options.device_name || '',
          last_error: detail || e.message || '手机音频接入启动失败',
          audio_chunks: 0,
          audio_bytes: 0,
          consumers: [],
        }
        throw e
      } finally {
        this.nativeAudioLoading = false
      }
    },

    async stopNativeAudioSession() {
      if (!this.currentSession) return
      this.nativeAudioInfo = await stopNativeAudio(this.currentSession.id)
    },

    async refreshNativeAudioStatus() {
      if (!this.currentSession) return
      this.nativeAudioInfo = await getNativeAudioStatus(this.currentSession.id)
    },

    async startNativeSttSession(serial = '') {
      if (!this.currentSession) return
      if (!this.nativeAudioInfo?.running) {
        this.sttError = '请先打开音频接入'
        throw new Error(this.sttError)
      }
      this.nativeSttLoading = true
      try {
        this.nativeSttInfo = await startNativeStt(this.currentSession.id, {
          serial,
        })
        this.sttConnected = Boolean(this.nativeSttInfo.running)
        this.sttError = this.nativeSttInfo.last_error || ''
      } catch (e: any) {
        const detail = e?.response?.data?.detail
        this.nativeSttInfo = {
          running: false,
          serial: '',
          provider: 'local',
          last_error: detail || e.message || '原生手机音频转写启动失败',
          audio_chunks: 0,
          audio_bytes: 0,
          transcript_segments: 0,
        }
        this.sttConnected = false
        this.sttError = this.nativeSttInfo.last_error
        throw e
      } finally {
        this.nativeSttLoading = false
      }
    },

    async stopNativeSttSession() {
      if (!this.currentSession) return
      this.nativeSttInfo = await stopNativeStt(this.currentSession.id)
      this.sttConnected = false
    },

    async refreshNativeSttStatus() {
      if (!this.currentSession) return
      this.nativeSttInfo = await getNativeSttStatus(this.currentSession.id)
      this.sttConnected = Boolean(this.nativeSttInfo.running)
    },

    async startRecorderSession() {
      if (!this.currentSession) return
      this.recorderLoading = true
      try {
        this.recorderInfo = await startRecorder(this.currentSession.id)
      } finally {
        this.recorderLoading = false
      }
    },

    async finishRecorderSession(blob: Blob) {
      if (!this.currentSession) return
      this.recorderLoading = true
      try {
        this.recorderInfo = await stopRecorder(this.currentSession.id, blob)
      } finally {
        this.recorderLoading = false
      }
    },

    async abortRecorderSession() {
      if (!this.currentSession) return
      this.recorderInfo = await abortRecorder(this.currentSession.id)
    },

    async softResetCaptureState() {
      if (!this.currentSession) return
      const result = await softResetCapture(this.currentSession.id)
      this.disconnectStt()
      this.scrcpyInfo = null
      this.phoneCaptureInfo = null
      this.captureCardInfo = null
      this.nativeAudioInfo = null
      this.nativeSttInfo = null
      this.recorderInfo = null
      this.captureStatusInfo = null
      this.activeCaptureMode = null
      this.captureStartupMode = null
      this.captureResetToken += 1
      clearCaptureModeLock()
      await this.refreshCaptureStatus()
      return result
    },

    async hardResetCaptureState() {
      if (!this.currentSession) return
      const result = await hardResetCapture(this.currentSession.id)
      this.disconnectStt()
      this.scrcpyInfo = null
      this.phoneCaptureInfo = null
      this.captureCardInfo = null
      this.nativeAudioInfo = null
      this.nativeSttInfo = null
      this.recorderInfo = null
      this.captureStatusInfo = null
      this.activeCaptureMode = null
      this.captureStartupMode = null
      this.captureResetToken += 1
      clearCaptureModeLock()
      await this.refreshCaptureStatus()
      return result
    },
  },
})
