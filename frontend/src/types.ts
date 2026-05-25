export type SessionStatus = '待开始' | '直播中' | '已结束'
export type SuggestionStatus = '待审核' | '已接受' | '已编辑' | '已复制' | '已使用' | '已拒绝'

export interface Product {
  id: string
  name: string
  category: string
  material: string
  color: string
  water: string
  size: string
  weight: string
  certificate: string
  flaws: string
  cautions: string
  price: number | null
  selling_points: string[]
  faq: string[]
  recommended_scripts: string[]
}

export interface LiveSession {
  id: string
  title: string
  platform: string
  anchor_name: string
  operator_name: string
  status: SessionStatus
  current_product_id: string | null
  manual_product_name: string
  live_url: string | null
  detected_color: string
  detected_water: string
  detected_subject: string
  detected_extra: string
  detected_full_name: string
  start_time: string | null
  end_time: string | null
  created_at: string
  updated_at: string
}

export interface TranscriptSegment {
  id: string
  session_id: string
  index: number
  text: string
  keywords: string[]
  created_at: string
}

export interface Suggestion {
  id: string
  session_id: string
  product_id: string | null
  type: string
  target_role: string
  priority: number
  risk_level: string
  content: string
  reason: string
  source_context: string
  status: SuggestionStatus
  created_at: string
  updated_at: string
}

export interface ReplayReport {
  id: string
  session_id: string
  summary: string
  useful_scripts: string[]
  missed_points: string[]
  risk_warnings: string[]
  audience_questions: string[]
  next_suggestions: string[]
  created_at: string
}

export interface FrameSnapshot {
  id: string
  session_id: string
  timestamp: string
  image_path: string
  summary: string
  detected_scene: string
  sharpness_score: number | null
  brightness_score: number | null
  change_score: number | null
  recognized_product_id: string | null
  recognized_product_name: string
  recognition_confidence: number | null
  recognition_source: string
  created_at: string
}

export interface WikiChunk {
  id: string
  source_path: string
  heading: string
  content: string
  tags: string[]
  updated_at: string
}

export interface VirtualCustomer {
  id: string
  nickname: string
  level: string
  personality: string
  preferred_colors: string[]
  preferred_categories: string[]
  budget_range: string
  common_questions: string[]
  purchased_items: string[]
  purchased_amount: number
  relationship_strategy: string
  activity_level: number
  created_at: string
  updated_at: string
}

export interface VirtualCustomerEvent {
  id: string
  session_id: string
  customer_id: string
  customer_nickname: string
  customer_level: string
  event_type: string
  content: string
  trigger_reason: string
  priority: number
  created_at: string
}

export interface AgentProfile {
  id: string
  name: string
  role: string
  persona: string
  tone: string
  allowed_auto_actions: string[]
  risk_policy: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface AgentUtterance {
  id: string
  session_id: string
  agent_id: string
  agent_name: string
  agent_role: string
  target: string
  content: string
  risk_level: string
  send_mode: string
  status: string
  trigger_reason: string
  wiki_chunk_ids: string[]
  customer_event_ids: string[]
  created_at: string
  sent_at: string | null
}

export interface WsMessage {
  event: string
  data: unknown
}

export interface ScrcpyDeviceInfo {
  running: boolean
  serial: string
  last_error: string
  width: number
  height: number
}

export interface PhoneCaptureInfo {
  running: boolean
  serial: string
  interval_seconds: number
  last_error: string
  last_frame_id: string | null
}

export interface SttStatus {
  connected: boolean
  active: boolean
  error: string
}
