from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    idle = "待开始"
    running = "直播中"
    stopped = "已结束"


class SuggestionStatus(str, Enum):
    pending = "待审核"
    accepted = "已接受"
    edited = "已编辑"
    copied = "已复制"
    used = "已使用"
    rejected = "已拒绝"


class Product(BaseModel):
    id: str
    name: str
    category: str
    material: str = ""
    color: str = ""
    water: str = ""
    size: str = ""
    weight: str = ""
    certificate: str = ""
    flaws: str = ""
    cautions: str = ""
    price: float | None = None
    selling_points: list[str] = Field(default_factory=list)
    faq: list[str] = Field(default_factory=list)
    recommended_scripts: list[str] = Field(default_factory=list)


class ProductCreate(BaseModel):
    name: str
    category: str
    material: str = "天然翡翠"
    color: str = ""
    water: str = ""
    size: str = ""
    weight: str = ""
    certificate: str = ""
    flaws: str = ""
    cautions: str = ""
    price: float | None = None
    selling_points: list[str] = Field(default_factory=list)
    faq: list[str] = Field(default_factory=list)
    recommended_scripts: list[str] = Field(default_factory=list)


class LiveSession(BaseModel):
    id: str
    title: str
    platform: str = "未设置"
    anchor_name: str = "主播"
    operator_name: str = "场控"
    status: SessionStatus = SessionStatus.idle
    current_product_id: str | None = None
    manual_product_name: str = ""
    live_url: str | None = None
    detected_color: str = ""
    detected_water: str = ""
    detected_subject: str = ""
    detected_extra: str = ""
    detected_full_name: str = ""
    start_time: datetime | None = None
    end_time: datetime | None = None
    created_at: datetime
    updated_at: datetime


class LiveSessionCreate(BaseModel):
    title: str
    platform: str = "抖音"
    anchor_name: str = "主播"
    operator_name: str = "场控"
    current_product_id: str | None = None
    live_url: str | None = None


class LiveUrlUpdate(BaseModel):
    live_url: str | None = None


class ManualProductNameUpdate(BaseModel):
    manual_product_name: str = ""


class TranscriptSegment(BaseModel):
    id: str
    session_id: str
    index: int
    text: str
    keywords: list[str] = Field(default_factory=list)
    created_at: datetime


class Suggestion(BaseModel):
    id: str
    session_id: str
    product_id: str | None = None
    type: str
    target_role: str
    priority: int = 1
    risk_level: str = "低"
    content: str
    reason: str
    source_context: str = ""
    status: SuggestionStatus = SuggestionStatus.pending
    created_at: datetime
    updated_at: datetime


class SuggestionUpdate(BaseModel):
    content: str | None = None
    feedback: str | None = None


class ReplayReport(BaseModel):
    id: str
    session_id: str
    summary: str
    useful_scripts: list[str]
    missed_points: list[str]
    risk_warnings: list[str]
    audience_questions: list[str]
    next_suggestions: list[str]
    created_at: datetime


class FrameSnapshot(BaseModel):
    id: str
    session_id: str
    timestamp: datetime
    image_path: str
    summary: str = ""
    detected_scene: str = "未识别"
    sharpness_score: float | None = None
    brightness_score: float | None = None
    change_score: float | None = None
    recognized_product_id: str | None = None
    recognized_product_name: str = ""
    recognition_confidence: float | None = None
    recognition_source: str = ""
    created_at: datetime


class WikiChunk(BaseModel):
    id: str
    source_path: str
    heading: str
    content: str
    tags: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VirtualCustomer(BaseModel):
    id: str
    nickname: str
    level: str
    personality: str
    preferred_colors: list[str] = Field(default_factory=list)
    preferred_categories: list[str] = Field(default_factory=list)
    budget_range: str = ""
    common_questions: list[str] = Field(default_factory=list)
    purchased_items: list[str] = Field(default_factory=list)
    purchased_amount: float = 0
    relationship_strategy: str = ""
    activity_level: float = 0.5
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CustomerMemory(BaseModel):
    id: str
    customer_id: str
    said_texts: list[str] = Field(default_factory=list)
    asked_questions: list[str] = Field(default_factory=list)
    purchased_items: list[str] = Field(default_factory=list)
    preference_tags: list[str] = Field(default_factory=list)
    interest_score: float = 0
    last_seen_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VirtualCustomerEvent(BaseModel):
    id: str
    session_id: str
    customer_id: str
    customer_nickname: str
    customer_level: str
    event_type: str
    content: str
    trigger_reason: str
    priority: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentProfile(BaseModel):
    id: str
    name: str
    role: str
    persona: str
    tone: str
    allowed_auto_actions: list[str] = Field(default_factory=list)
    risk_policy: str = ""
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentUtterance(BaseModel):
    id: str
    session_id: str
    agent_id: str
    agent_name: str
    agent_role: str
    target: str
    content: str
    risk_level: str
    send_mode: str
    status: str
    trigger_reason: str
    wiki_chunk_ids: list[str] = Field(default_factory=list)
    customer_event_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: datetime | None = None


class WsEvent(BaseModel):
    event: str
    data: dict[str, Any]


class LoginRequest(BaseModel):
    username: str
    password: str


class UserProfile(BaseModel):
    id: str
    username: str
    display_name: str
    role: str


class ScrcpyStartRequest(BaseModel):
    serial: str = ""
    max_size: int = Field(default=1024, ge=480, le=2560)
    bit_rate: int = Field(default=4_000_000, ge=1_000_000, le=20_000_000)


class ScrcpyStatus(BaseModel):
    running: bool
    serial: str = ""
    last_error: str = ""
    width: int = 0
    height: int = 0


class PhoneCaptureStartRequest(BaseModel):
    serial: str = ""
    interval_seconds: float = Field(default=0.2, ge=0.2, le=10.0)


class PhoneCaptureStatus(BaseModel):
    running: bool
    serial: str = ""
    interval_seconds: float = 0.2
    last_error: str = ""
    last_frame_id: str | None = None


class LoginResponse(BaseModel):
    token: str
    user: UserProfile
