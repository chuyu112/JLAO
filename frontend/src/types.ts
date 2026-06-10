export type SessionStatus = '待开始' | '直播中' | '已结束'
export type SuggestionStatus = '待审核' | '已接受' | '已编辑' | '已复制' | '已使用' | '已拒绝'

export interface Product {
  id: string
  name: string
  category: string
  status: string
  material: string
  color: string
  water: string
  style: string
  theme: string
  size: string
  weight: string
  certificate: string
  flaws: string
  cautions: string
  price: number | null
  selling_points: string[]
  faq: string[]
  recommended_scripts: string[]
  evidence_image_paths: string[]
  evidence_texts: string[]
  analysis_confidence: number
  attribute_sources: Record<string, {
    source?: string
    method?: string
    value?: string | number | null
    from?: string
  }>
  fusion_scores: Record<string, number>
}

export interface ProductCreatePayload {
  name: string
  category: string
  status?: string
  material?: string
  color?: string
  water?: string
  style?: string
  theme?: string
  size?: string
  weight?: string
  certificate?: string
  flaws?: string
  cautions?: string
  price?: number | null
  selling_points?: string[]
  faq?: string[]
  recommended_scripts?: string[]
  evidence_image_paths?: string[]
  evidence_texts?: string[]
  analysis_confidence?: number
  attribute_sources?: Product['attribute_sources']
  fusion_scores?: Product['fusion_scores']
}

export interface ProductJadeAnnotationResult {
  status: string
  product: Product
  feedback_id: string
  training?: Record<string, unknown>
  dataset?: JadeTrainingBuildResult | null
}

export interface JadeModelStatus {
  status: string
  readiness?: {
    can_analyze_image: boolean
    can_read_frame_text: boolean
    has_jade_yolo_model: boolean
    uses_pretrained_yolo_fallback: boolean
    has_vlm: boolean
    has_feedback_learning: boolean
    has_yolo_training_data: boolean
    requires_manual_box: number
  }
  yolo: {
    source: string
    enabled: boolean
    reason: string
    configured_model_path: string
    resolved_model_path: string
    model_ref?: string
    model_kind?: string
    pretrained_fallback?: boolean
    package_available: boolean
    package_error?: string
    model_candidates: string[]
    pretrained_model?: string
  }
  vlm?: {
    source: string
    enabled: boolean
    reason: string
    configured_model_path: string
    http_url?: string
    http_format?: string
    default_http_url?: string
    default_http_model?: string
    using_default_http_url?: boolean
    using_default_http_model?: boolean
    package_available: Record<string, boolean>
    env: string
    config_path?: string
    required_env?: string[]
    install_hint?: string
  }
  ocr?: {
    source: string
    enabled: boolean
    reason: string
    engine: string
    languages: string[]
    language_error?: string
    interval_seconds: number
  }
  feedback_learning?: {
    source: string
    enabled: boolean
    min_correction_count: number
    feedback_path: string
    rules: Record<'color' | 'water' | 'style' | 'theme', Record<string, string>>
    stats: Record<string, unknown>
  }
  training?: JadeTrainingStatus
  limits?: {
    upload_image_extensions: string[]
    upload_max_bytes: number
    upload_max_mb: number
    batch_max_items: number
    page_default_batch_items: number
    batch_readiness_min_yolo_ready_records?: number
  }
  fusion: {
    image: string[]
    speech: string[]
    attributes: string[]
  }
}

export interface JadeSampleAnalysis {
  name: string
  attributes: {
    color: string
    water: string
    style: string
    theme: string
    size: string
    price: number | null
  }
  confidence: number
  evidence: {
    images: string[]
    texts: string[]
    detections: Array<Record<string, unknown>>
  }
  signals: Record<string, unknown>
  review_flags?: string[]
  input: {
    image: string
    text: string
    batch_id?: string
  }
  runtime: {
    yolo: {
      source: string
      enabled: boolean
      reason: string
      configured_model_path: string
      resolved_model_path: string
      model_ref?: string
      model_kind?: string
      pretrained_fallback?: boolean
      package_available: boolean
      package_error?: string
      model_candidates: string[]
      pretrained_model?: string
    }
    ocr?: JadeModelStatus['ocr']
    vlm?: {
      source: string
      enabled: boolean
      reason: string
      configured_model_path: string
      http_url?: string
      http_format?: string
      default_http_url?: string
      default_http_model?: string
      using_default_http_url?: boolean
      using_default_http_model?: boolean
      package_available: Record<string, boolean>
      env: string
      config_path?: string
      required_env?: string[]
      install_hint?: string
    }
    feedback_learning?: JadeModelStatus['feedback_learning']
    training?: JadeTrainingStatus
  }
}

export interface JadeBatchAnalysis {
  status: string
  batch_id?: string
  count: number
  items: Array<JadeSampleAnalysis & {
    input: JadeSampleAnalysis['input'] & {
      source_filename?: string
      batch_id?: string
    }
  }>
  review_summary?: Record<string, number>
  runtime: JadeSampleAnalysis['runtime']
}

export interface JadeBatchFeedbackTrace {
  status: string
  batch_id: string
  feedback_path: string
  count: number
  summary?: {
    attribute_counts: Record<'color' | 'water' | 'style' | 'theme', number>
    training_counts: {
      yolo_ready: number
      requires_manual_box: number
      whole_image_box: number
      manual_box: number
    }
    source_counts: Record<string, number>
    readiness?: {
      can_try_batch_training: boolean
      blocking_reasons: string[]
      recommended_next_steps: string[]
      minimum_yolo_ready_records: number
    }
  }
  records: Array<{
    id: string
    created_at: string
    source: string
    input: Record<string, unknown>
    corrected: Record<string, string>
    predicted: Record<string, unknown>
    confidence: number
    training: Record<string, unknown>
    evidence: {
      images: string[]
      texts: string[]
    }
  }>
}

export interface JadeVlmProbeResult {
  status: string
  message?: string
  image?: string
  runtime: JadeModelStatus['vlm']
  attributes: {
    color?: string
    water?: string
    style?: string
    theme?: string
  }
  raw_text?: string
}

export interface JadeSampleFeedbackPayload {
  input: JadeSampleAnalysis['input']
  predicted: JadeSampleAnalysis['attributes']
  corrected: {
    color: string
    water: string
    style: string
    theme: string
  }
  evidence: JadeSampleAnalysis['evidence']
  confidence: number
  attribute_sources?: Record<string, unknown>
}

export interface JadeTrainingStatus {
  status: string
  feedback: {
    path: string
    exists: boolean
    records: number
    eligible_records?: number
    pending_review?: number
    rejected?: number
    approved?: number
    usable_for_yolo: number
    weak_live_usable?: number
    requires_manual_box?: number
    whole_image_box?: number
    manual_box?: number
  }
  dataset: {
    root: string
    yaml: string
    yaml_exists: boolean
    images: Record<'train' | 'val' | 'test', number>
    labels: Record<'train' | 'val' | 'test', number>
    class_counts?: Record<string, number>
    classes: string[]
  }
  model: {
    path: string
    exists: boolean
    size: number
  }
  workflow: string[]
}

export interface JadeTrainingBuildResult {
  status: string
  feedback_path: string
  dataset_root?: string
  records: number
  written: number
  skipped: number
  missing_image: number
  no_class: number
  requires_manual_box?: number
  skipped_unreviewed_or_rejected?: number
  whole_image_box?: number
  manual_box?: number
  auto_fix?: {
    status: string
    reason?: string
    moved: number
    skipped: number
    train_labels_before: number
    val_labels_before: number
    train_labels_after: number
    val_labels_after: number
  }
}

export interface JadeTrainingRunStatus {
  status: string
  running: boolean
  pid: number
  return_code: number | null
  can_start: boolean
  blocking_reasons: string[]
  auto_build?: {
    status: string
    reason?: string
    records: number
    written: number
    skipped: number
    missing_image: number
    no_class: number
    requires_manual_box?: number
    skipped_unreviewed_or_rejected?: number
    whole_image_box?: number
  }
  auto_fix?: {
    status: string
    reason: string
    moved: number
    skipped: number
    train_labels_before: number
    val_labels_before: number
    train_labels_after: number
    val_labels_after: number
  }
  runtime: {
    ultralytics_available: boolean
    ultralytics_error?: string
    python: string
    dataset_yaml: string
    train_labels: number
    val_labels: number
    class_counts?: Record<string, number>
    }
  script: string
  log_path: string
  log_tail: string
  model_path: string
  model_exists: boolean
  model_size: number
}

export interface JadeEvaluationResult {
  status: string
  feedback_path: string
  records: number
  eligible_records?: number
  selected: number
  evaluated: number
  skipped: number
  overall: {
    correct: number
    total: number
    accuracy: number
  }
  weakest_attribute: string
  recommendations: string[]
  misses: Record<'color' | 'water' | 'style' | 'theme', Array<{
    pair: string
    count: number
  }>>
  hard_cases?: Array<{
    id: string
    attribute: 'color' | 'water' | 'style' | 'theme'
    attribute_label: string
    predicted: string
    corrected: string
    confidence?: number
    source?: string
    image?: string
  }>
  metrics: Record<'color' | 'water' | 'style' | 'theme', {
    correct: number
    total: number
    accuracy: number
  }>
  modality_counts?: Record<string, number>
  source_metrics?: Record<'color' | 'water' | 'style' | 'theme', Array<{
    source: string
    correct: number
    total: number
    accuracy: number
  }>>
  details: Array<{
    id: string
    status: string
    reason?: string
    corrected: Record<string, string>
    predicted: Record<string, string>
    matches?: Record<string, boolean>
    confidence?: number
    evidence_mode?: string
    attribute_sources?: Record<string, unknown>
  }>
}

export interface JadeAnnotationTasks {
  status: string
  feedback_path: string
  records: number
  task_count: number
  class_counts: Record<string, number>
  source_counts?: Record<string, number>
  missing_image: number
  no_class: number
  pending_review?: number
  rejected?: number
  instruction: string
  tasks: Array<{
    id: string
    created_at: string
    image: string
    image_path: string
    text: string
    corrected: {
      color: string
      water: string
      style: string
      theme: string
    }
    classes: string[]
    needs_manual_class?: boolean
    source?: string
    attribute_sources?: Record<string, {
      source?: string
      method?: string
      value?: string | number | null
      from?: string
    }>
    needs_review?: boolean
    review_reason?: string
    review_status?: string
    confidence?: number
    training?: {
      suggested_classes: string[]
      yolo_ready: boolean
      requires_manual_box: boolean
      box_mode?: string
      box_confirmed_by?: string
      yolo_boxes?: Array<{
        class_name: string
        x_center: number
        y_center: number
        width: number
        height: number
      }>
    }
    status: string
  }>
}

export interface JadeAnnotationReviewResult {
  status: string
  id: string
  action: 'approve' | 'reject'
  review_status: string
  corrected: {
    color: string
    water: string
    style: string
    theme: string
  }
  training_eligible: boolean
}

export interface JadeTaxonomyOptions {
  status: string
  colors: string[]
  waters: string[]
  styles: string[]
  themes: string[]
}

export interface JadeAnnotationExportResult {
  status: string
  export_dir: string
  zip_path: string
  zip_url: string
  manifest: string
  classes: string
  images_dir: string
  labels_suggested_dir: string
  task_count: number
  copied: number
  class_counts: Record<string, number>
}

export interface JadeAnnotationImportResult {
  status: string
  split: string
  auto_val_ratio: number
  per_split: Record<'train' | 'val' | 'test', {
    images: number
    labels: number
  }>
  dataset_root: string
  images_dir: string
  labels_dir: string
  source_zip: string
  found_images: number
  found_labels: number
  copied_images: number
  copied_labels: number
  unmatched_labels: number
  invalid_label_count: number
  invalid_labels: Array<{
    label: string
    errors: string[]
  }>
}

export interface LiveSession {
  id: string
  title: string
  live_room_name: string
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
  jade_color: string
  jade_water: string
  jade_style: string
  jade_theme: string
  jade_size: string
  jade_price: number | null
  jade_confidence: number
  jade_attribute_sources: Record<string, {
    source?: string
    method?: string
    value?: string
    from?: string
  }>
  jade_color_analysis: Record<string, unknown>
  jade_detections: Array<Record<string, unknown>>
  jade_ocr_text: string
  jade_ocr_lines: string[]
  jade_ocr_error: string
  created_at: string
}

export interface JadeYoloLiveDetection {
  label: string
  confidence: number
  box: [number, number, number, number]
  style?: string
  theme?: string
  track_id?: string
  confirmed?: boolean
  tracking_state?: 'confirmed' | 'lost' | string
  stable_frames?: number
  lost_frames?: number
}

export interface JadeYoloLiveDetectionResult {
  status: string
  image_width: number
  image_height: number
  detections: JadeYoloLiveDetection[]
  candidates?: JadeYoloLiveDetection[]
  tracking?: {
    status?: string
    confirmed?: boolean
    track_id?: string
    stable_frames?: number
    lost_frames?: number
    pending_switch_frames?: number
    candidate_count?: number
    active_count?: number
    pending_count?: number
    confirm_frames?: number
    hold_frames?: number
    switch_frames?: number
  }
  runtime: Record<string, unknown>
  timings: {
    save_ms: number
    yolo_ms: number
    total_ms: number
  }
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
  repeat_count: number
  is_updated: boolean
  created_at: string
  last_seen_at: string | null
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
  recording_path: string
  reconnecting?: boolean
  reconnect_attempts?: number
  last_exit_code?: number | null
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

export interface NativeSttInfo {
  running: boolean
  serial: string
  provider: string
  last_error: string
  audio_chunks: number
  audio_bytes: number
  transcript_segments: number
}
