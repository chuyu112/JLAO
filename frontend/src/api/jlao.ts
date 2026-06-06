import { API_BASE, api } from './client'
import type {
  FrameSnapshot,
  AgentProfile,
  AgentUtterance,
  JadeAnnotationExportResult,
  JadeAnnotationImportResult,
  JadeAnnotationReviewResult,
  JadeAnnotationTasks,
  JadeTaxonomyOptions,
  JadeBatchAnalysis,
  JadeBatchFeedbackTrace,
  JadeModelStatus,
  ProductJadeAnnotationResult,
  JadeEvaluationResult,
  JadeSampleAnalysis,
  JadeSampleFeedbackPayload,
  JadeTrainingBuildResult,
  JadeTrainingRunStatus,
  JadeTrainingStatus,
  JadeVlmProbeResult,
  JadeYoloLiveDetectionResult,
  LiveSession,
  NativeSttInfo,
  PhoneCaptureInfo,
  Product,
  ProductCreatePayload,
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

export async function fetchProducts(status?: string) {
  const params = status ? { params: { status } } : {}
  const { data } = await api.get<Product[]>('/api/products', params)
  return data
}

export async function fetchJadeModelStatus() {
  const { data } = await api.get<JadeModelStatus>('/api/products/jade-model/status')
  return data
}

export async function analyzeJadeSample(payload: { file?: File | null; text?: string }) {
  const form = new FormData()
  if (payload.file) form.append('file', payload.file)
  form.append('text', payload.text || '')
  const { data } = await api.post<JadeSampleAnalysis>('/api/products/jade-analysis/sample', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function analyzeJadeBatch(payload: { files?: File[]; text?: string; maxItems?: number }) {
  const form = new FormData()
  for (const file of payload.files || []) {
    form.append('files', file)
  }
  form.append('text', payload.text || '')
  form.append('max_items', String(payload.maxItems ?? 20))
  const { data } = await api.post<JadeBatchAnalysis>('/api/products/jade-analysis/batch', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function probeJadeVlm(payload: { file?: File | null; text?: string }) {
  const form = new FormData()
  if (payload.file) form.append('file', payload.file)
  form.append('text', payload.text || '')
  const { data } = await api.post<JadeVlmProbeResult>('/api/products/jade-model/vlm-probe', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function saveJadeVlmPrelabel(payload: { file?: File | null; text?: string }) {
  const form = new FormData()
  if (payload.file) form.append('file', payload.file)
  form.append('text', payload.text || '')
  const { data } = await api.post<{
    status: string
    id?: string
    image?: string
    runtime: JadeModelStatus['vlm']
    attributes: {
      color?: string
      water?: string
      style?: string
      theme?: string
    }
    needs_review?: boolean
    training?: Record<string, unknown>
    message?: string
  }>('/api/products/jade-model/vlm-prelabel', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function createProduct(payload: ProductCreatePayload) {
  const { data } = await api.post<Product>('/api/products', payload)
  return data
}

export async function annotateProductJade(
  productId: string,
  corrected: { color?: string; water?: string; style?: string; theme?: string }
) {
  const { data } = await api.post<ProductJadeAnnotationResult>(`/api/products/${encodeURIComponent(productId)}/jade-annotation`, {
    corrected,
  })
  return data
}

export async function submitJadeSampleFeedback(payload: JadeSampleFeedbackPayload) {
  const { data } = await api.post<{
    status: string
    id: string
    path: string
    training?: Record<string, unknown>
    dataset?: JadeTrainingBuildResult | null
  }>(
    '/api/products/jade-analysis/feedback',
    payload
  )
  return data
}

export async function submitJadeSampleFeedbackBatch(payload: { items: JadeSampleFeedbackPayload[] }) {
  const { data } = await api.post<{
    status: string
    saved: number
    skipped: number
    skipped_reasons?: Record<string, number>
    path: string
    results: Array<{
      index: number
      status: string
      id?: string
      reason?: string
      training?: Record<string, unknown>
    }>
    dataset?: JadeTrainingBuildResult | null
  }>('/api/products/jade-analysis/feedback/batch', payload)
  return data
}

export async function fetchJadeBatchFeedbackTrace(batchId: string) {
  const { data } = await api.get<JadeBatchFeedbackTrace>(
    `/api/products/jade-analysis/batches/${encodeURIComponent(batchId)}/feedback`
  )
  return data
}

export async function fetchJadeTrainingStatus() {
  const { data } = await api.get<JadeTrainingStatus>('/api/products/jade-training/status')
  return data
}

export async function buildJadeTrainingDataset(payload: { split?: 'train' | 'val'; val_every?: number; write_yaml?: boolean } = {}) {
  const { data } = await api.post<JadeTrainingBuildResult>('/api/products/jade-training/build-dataset', payload)
  return data
}

export async function fetchJadeTrainingRunStatus() {
  const { data } = await api.get<JadeTrainingRunStatus>('/api/products/jade-training/train/status')
  return data
}

export async function startJadeYoloTraining(payload: { epochs?: number; imgsz?: number; batch?: string; model?: string } = {}) {
  const { data } = await api.post<JadeTrainingRunStatus>('/api/products/jade-training/train/start', payload)
  return data
}

export async function runJadeEvaluation(payload: { limit?: number } = {}) {
  const { data } = await api.post<JadeEvaluationResult>('/api/products/jade-evaluation/run', payload)
  return data
}

export async function fetchJadeAnnotationTasks(limit = 80) {
  const { data } = await api.get<JadeAnnotationTasks>('/api/products/jade-annotation/tasks', { params: { limit } })
  return data
}

export async function exportJadeAnnotationTasks(payload: { limit?: number } = {}) {
  const { data } = await api.post<JadeAnnotationExportResult>('/api/products/jade-annotation/export', payload)
  return data
}

export async function importJadeAnnotationPackage(payload: {
  file: File
  split?: 'auto' | 'train' | 'val' | 'test'
  auto_val_ratio?: number
}) {
  const form = new FormData()
  form.append('file', payload.file)
  form.append('split', payload.split || 'auto')
  form.append('auto_val_ratio', String(payload.auto_val_ratio ?? 0.2))
  const { data } = await api.post<JadeAnnotationImportResult>('/api/products/jade-annotation/import', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function reviewJadeAnnotationTask(
  feedbackId: string,
  action: 'approve' | 'reject',
  corrected?: {
    color?: string
    water?: string
    style?: string
    theme?: string
  }
) {
  const { data } = await api.post<JadeAnnotationReviewResult>(
    `/api/products/jade-annotation/tasks/${encodeURIComponent(feedbackId)}/review`,
    { action, corrected }
  )
  return data
}

export async function confirmJadeAnnotationWholeImageBox(feedbackId: string) {
  const { data } = await api.post<{
    status: string
    id: string
    review_status: string
    training: Record<string, unknown>
    training_eligible: boolean
  }>(`/api/products/jade-annotation/tasks/${encodeURIComponent(feedbackId)}/whole-image-box`)
  return data
}

export async function approveJadeAnnotationWholeImageBox(
  feedbackId: string,
  corrected?: {
    color?: string
    water?: string
    style?: string
    theme?: string
  }
) {
  const { data } = await api.post<{
    status: string
    id: string
    review_status: string
    corrected: {
      color: string
      water: string
      style: string
      theme: string
    }
    training: Record<string, unknown>
    training_eligible: boolean
    dataset?: JadeTrainingBuildResult
  }>(`/api/products/jade-annotation/tasks/${encodeURIComponent(feedbackId)}/approve-whole-image-box`, { corrected })
  return data
}

export async function saveJadeAnnotationBoxes(
  feedbackId: string,
  boxes: Array<{
    class_name: string
    x_center: number
    y_center: number
    width: number
    height: number
  }>
) {
  const { data } = await api.post<{
    status: string
    id: string
    review_status: string
    training: Record<string, unknown>
    training_eligible: boolean
  }>(`/api/products/jade-annotation/tasks/${encodeURIComponent(feedbackId)}/boxes`, { boxes })
  return data
}

export async function fetchJadeTaxonomyOptions() {
  const { data } = await api.get<JadeTaxonomyOptions>('/api/products/jade-taxonomy/options')
  return data
}

export async function createSession(payload: {
  title: string
  platform: string
  live_room_name?: string
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

export async function detectJadeYoloLiveFrame(sessionId: string, blob: Blob) {
  const form = new FormData()
  form.append('file', blob, `yolo-live-${Date.now()}.jpg`)
  const { data } = await api.post<JadeYoloLiveDetectionResult>(
    `/api/sessions/${sessionId}/jade-yolo/detect-frame`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 8000 }
  )
  return data
}

export async function fetchFrames(sessionId: string) {
  const { data } = await api.get<FrameSnapshot[]>(`/api/sessions/${sessionId}/frames`)
  return data
}

export async function submitFrameJadeFeedback(
  sessionId: string,
  frameId: string,
  payload: { corrected: { color?: string; water?: string; style?: string; theme?: string } }
) {
  const { data } = await api.post<FrameSnapshot>(`/api/sessions/${sessionId}/frames/${frameId}/jade-feedback`, payload)
  return data
}

export async function startScrcpy(sessionId: string, payload: { serial?: string; max_size?: number; bit_rate?: number }) {
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

export async function startPhoneCapture(sessionId: string, payload: { serial?: string; interval_seconds?: number }) {
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

export async function startNativeStt(sessionId: string, payload: { serial?: string; chunk_seconds?: number }) {
  const { data } = await api.post<NativeSttInfo>(`/api/sessions/${sessionId}/native-stt/start`, payload)
  return data
}

export async function stopNativeStt(sessionId: string) {
  const { data } = await api.post<NativeSttInfo>(`/api/sessions/${sessionId}/native-stt/stop`)
  return data
}

export async function getNativeSttStatus(sessionId: string) {
  const { data } = await api.get<NativeSttInfo>(`/api/sessions/${sessionId}/native-stt/status`)
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

export async function fetchLiveComments(sessionId: string) {
  const { data } = await api.get<VirtualCustomerEvent[]>(`/api/sessions/${sessionId}/live-comments`)
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
