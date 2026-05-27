import { API_BASE, api } from './client'
import type {
  FrameSnapshot,
  AgentProfile,
  AgentUtterance,
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
} from '../types'

export function resolveAssetUrl(path: string) {
  if (/^https?:\/\//.test(path)) return path
  const token = localStorage.getItem('jlao_token') || ''
  const fullPath = `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
  return token ? `${fullPath}?token=${encodeURIComponent(token)}` : fullPath
}

export async function fetchProducts() {
  const { data } = await api.get<Product[]>('/api/products')
  return data
}

export async function createSession(payload: {
  title: string
  platform: string
  anchor_name: string
  operator_name: string
  current_product_id?: string | null
}) {
  const { data } = await api.post<LiveSession>('/api/sessions', payload)
  return data
}

export async function startSession(sessionId: string) {
  const { data } = await api.post<LiveSession>(`/api/sessions/${sessionId}/start`)
  return data
}

export async function stopSession(sessionId: string) {
  const { data } = await api.post<LiveSession>(`/api/sessions/${sessionId}/stop`)
  return data
}

export async function setCurrentProduct(sessionId: string, productId: string) {
  const { data } = await api.post<LiveSession>(`/api/sessions/${sessionId}/current-product/${productId}`)
  return data
}

export async function setManualProductName(sessionId: string, manualProductName: string) {
  const { data } = await api.post<LiveSession>(`/api/sessions/${sessionId}/manual-product-name`, {
    manual_product_name: manualProductName,
  })
  return data
}

export async function setLiveUrl(sessionId: string, liveUrl: string | null) {
  const { data } = await api.post<LiveSession>(`/api/sessions/${sessionId}/live-url`, { live_url: liveUrl })
  return data
}

export async function fetchTranscripts(sessionId: string) {
  const { data } = await api.get<TranscriptSegment[]>(`/api/sessions/${sessionId}/transcripts`)
  return data
}

export async function fetchSuggestions(sessionId: string) {
  const { data } = await api.get<Suggestion[]>(`/api/suggestions/sessions/${sessionId}`)
  return data
}

export async function updateSuggestionStatus(suggestionId: string, action: 'accept' | 'copy' | 'used' | 'reject') {
  const { data } = await api.post<Suggestion>(`/api/suggestions/${suggestionId}/${action}`)
  return data
}

export async function createReplay(sessionId: string) {
  const { data } = await api.post<ReplayReport>(`/api/sessions/${sessionId}/replay`)
  return data
}

export async function uploadFrame(sessionId: string, blob: Blob) {
  const form = new FormData()
  form.append('file', blob, `capture-${Date.now()}.jpg`)
  const { data } = await api.post<FrameSnapshot>(`/api/sessions/${sessionId}/frames/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function fetchFrames(sessionId: string) {
  const { data } = await api.get<FrameSnapshot[]>(`/api/sessions/${sessionId}/frames`)
  return data
}

export async function startScrcpy(sessionId: string, payload: { serial: string; max_size?: number; bit_rate?: number }) {
  const { data } = await api.post<ScrcpyDeviceInfo>(`/api/sessions/${sessionId}/scrcpy/start`, payload)
  return data
}

export async function stopScrcpy(sessionId: string) {
  const { data } = await api.post<ScrcpyDeviceInfo>(`/api/sessions/${sessionId}/scrcpy/stop`)
  return data
}

export async function getScrcpyStatus(sessionId: string) {
  const { data } = await api.get<ScrcpyDeviceInfo>(`/api/sessions/${sessionId}/scrcpy/status`)
  return data
}

export async function startPhoneCapture(sessionId: string, payload: { serial: string; interval_seconds?: number }) {
  const { data } = await api.post<PhoneCaptureInfo>(`/api/sessions/${sessionId}/phone-capture/start`, payload)
  return data
}

export async function stopPhoneCapture(sessionId: string) {
  const { data } = await api.post<PhoneCaptureInfo>(`/api/sessions/${sessionId}/phone-capture/stop`)
  return data
}

export async function getPhoneCaptureStatus(sessionId: string) {
  const { data } = await api.get<PhoneCaptureInfo>(`/api/sessions/${sessionId}/phone-capture/status`)
  return data
}

export async function fetchWikiChunks() {
  const { data } = await api.get<WikiChunk[]>('/api/wiki/chunks')
  return data
}

export async function searchWiki(query: string) {
  const { data } = await api.get<WikiChunk[]>('/api/wiki/search', { params: { q: query } })
  return data
}

export async function reloadWiki() {
  const { data } = await api.post<WikiChunk[]>('/api/wiki/reload')
  return data
}

export async function fetchVirtualCustomers(sessionId: string) {
  const { data } = await api.get<VirtualCustomer[]>(`/api/sessions/${sessionId}/virtual-customers`)
  return data
}

export async function fetchCustomerEvents(sessionId: string) {
  const { data } = await api.get<VirtualCustomerEvent[]>(`/api/sessions/${sessionId}/customer-events`)
  return data
}

export async function fetchAgents() {
  const { data } = await api.get<AgentProfile[]>('/api/agents')
  return data
}

export async function fetchAgentUtterances(sessionId: string) {
  const { data } = await api.get<AgentUtterance[]>(`/api/sessions/${sessionId}/agent-utterances`)
  return data
}
