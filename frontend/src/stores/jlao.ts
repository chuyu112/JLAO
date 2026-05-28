import { defineStore } from 'pinia'
import { WS_BASE } from '../api/client'
import {
  createReplay,
  createSession,
  fetchAgentUtterances,
  fetchAgents,
  fetchCustomerEvents,
  fetchFrames,
  fetchProducts,
  fetchSuggestions,
  fetchTranscripts,
  fetchVirtualCustomers,
  fetchWikiChunks,
  getPhoneCaptureStatus,
  getScrcpyStatus,
  setCurrentProduct,
  setLiveUrl,
  setManualProductName,
  startPhoneCapture,
  startScrcpy,
  stopPhoneCapture,
  startSession,
  stopScrcpy,
  stopSession,
  updateSuggestionStatus,
  uploadFrame,
} from '../api/jlao'
import type {
  AgentProfile,
  AgentUtterance,
  FrameSnapshot,
  LiveSession,
  PhoneCaptureInfo,
  Product,
  ReplayReport,
  ScrcpyDeviceInfo,
  Suggestion,
  TranscriptSegment,
  VirtualCustomer,
  VirtualCustomerEvent,
  WikiChunk,
  WsMessage,
} from '../types'

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
  agents: AgentProfile[]
  agentUtterances: AgentUtterance[]
  connected: boolean
  loading: boolean
  frameAnalyzing: boolean
  socket: WebSocket | null
  sttSocket: WebSocket | null
  partialTranscript: string
  sttConnected: boolean
  sttError: string
  scrcpyInfo: ScrcpyDeviceInfo | null
  scrcpyLoading: boolean
  phoneCaptureInfo: PhoneCaptureInfo | null
  phoneCaptureLoading: boolean
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
    agents: [],
    agentUtterances: [],
    connected: false,
    loading: false,
    frameAnalyzing: false,
    socket: null,
    sttSocket: null,
    partialTranscript: '',
    sttConnected: false,
    sttError: '',
    scrcpyInfo: null,
    scrcpyLoading: false,
    phoneCaptureInfo: null,
    phoneCaptureLoading: false,
  }),

  getters: {
    currentProduct(state): Product | null {
      if (!state.currentSession?.current_product_id) return state.products[0] || null
      return state.products.find((item) => item.id === state.currentSession?.current_product_id) || null
    },
    topSuggestions(state): Suggestion[] {
      return [...state.suggestions]
        .sort((a, b) => b.priority - a.priority || Date.parse(b.created_at) - Date.parse(a.created_at))
        .slice(0, 8)
    },
  },

  actions: {
    async initDemo() {
      this.loading = true
      try {
        this.products = await fetchProducts()
        if (!this.currentSession) {
          this.currentSession = await createSession({
            title: 'JLAO 翡翠直播',
            platform: '抖音',
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
      if (message.event === 'agent_utterance') {
        const utterance = message.data as AgentUtterance
        this.agentUtterances = [utterance, ...this.agentUtterances.filter((item) => item.id !== utterance.id)].slice(0, 50)
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
      const [wikiChunks, virtualCustomers, customerEvents, agents, agentUtterances] = await Promise.all([
        fetchWikiChunks(),
        fetchVirtualCustomers(this.currentSession.id),
        fetchCustomerEvents(this.currentSession.id),
        fetchAgents(),
        fetchAgentUtterances(this.currentSession.id),
      ])
      this.wikiChunks = wikiChunks
      this.wikiHits = this.wikiHits.length ? this.wikiHits : wikiChunks.slice(0, 5)
      this.virtualCustomers = virtualCustomers
      this.customerEvents = customerEvents
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

    sendSttAudio(frame: ArrayBuffer) {
      if (this.sttSocket?.readyState === WebSocket.OPEN) {
        this.sttSocket.send(frame)
      }
    },

    connectStt() {
      if (!this.currentSession || this.sttSocket?.readyState === WebSocket.OPEN) return
      this.sttError = ''
      const socket = new WebSocket(this._wsUrl(`/ws/sessions/${this.currentSession.id}/stt`))
      socket.binaryType = 'arraybuffer'
      socket.onopen = () => {
        this.sttConnected = true
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
      }
      this.sttSocket = socket
    },

    disconnectStt() {
      this.sttSocket?.close()
      this.sttSocket = null
      this.sttConnected = false
      this.partialTranscript = ''
    },

    async startScrcpySession(serial: string) {
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

    async startPhoneCaptureSession(serial: string) {
      if (!this.currentSession) return
      this.phoneCaptureLoading = true
      try {
        this.phoneCaptureInfo = await startPhoneCapture(this.currentSession.id, {
          serial,
          interval_seconds: 0.1,
        })
      } catch (e: any) {
        const detail = e?.response?.data?.detail
        this.phoneCaptureInfo = {
          running: false,
          serial: '',
          interval_seconds: 0.1,
          last_error: detail || e.message || '手机截屏启动失败',
          last_frame_id: null,
        }
      } finally {
        this.phoneCaptureLoading = false
      }
    },

    async stopPhoneCaptureSession() {
      if (!this.currentSession) return
      this.phoneCaptureInfo = await stopPhoneCapture(this.currentSession.id)
    },

    async refreshPhoneCaptureStatus() {
      if (!this.currentSession) return
      this.phoneCaptureInfo = await getPhoneCaptureStatus(this.currentSession.id)
    },
  },
})
