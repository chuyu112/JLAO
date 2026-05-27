from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ProductRecord(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    material: Mapped[str] = mapped_column(String(100), default="")
    color: Mapped[str] = mapped_column(String(100), default="")
    water: Mapped[str] = mapped_column(String(100), default="")
    size: Mapped[str] = mapped_column(String(255), default="")
    weight: Mapped[str] = mapped_column(String(100), default="")
    certificate: Mapped[str] = mapped_column(String(255), default="")
    flaws: Mapped[str] = mapped_column(Text, default="")
    cautions: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    selling_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    faq: Mapped[list[str]] = mapped_column(JSON, default=list)
    recommended_scripts: Mapped[list[str]] = mapped_column(JSON, default=list)


class LiveSessionRecord(Base):
    __tablename__ = "live_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(100), default="未设置")
    anchor_name: Mapped[str] = mapped_column(String(100), default="主播")
    operator_name: Mapped[str] = mapped_column(String(100), default="场控")
    status: Mapped[str] = mapped_column(String(50), default="待开始")
    current_product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manual_product_name: Mapped[str] = mapped_column(String(255), default="")
    live_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_color: Mapped[str] = mapped_column(String(100), default="")
    detected_water: Mapped[str] = mapped_column(String(100), default="")
    detected_subject: Mapped[str] = mapped_column(String(100), default="")
    detected_extra: Mapped[str] = mapped_column(String(255), default="")
    detected_full_name: Mapped[str] = mapped_column(String(255), default="")
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class TranscriptSegmentRecord(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class SuggestionRecord(Base):
    __tablename__ = "suggestions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    type: Mapped[str] = mapped_column(String(100))
    target_role: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=1)
    risk_level: Mapped[str] = mapped_column(String(50), default="低")
    content: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, default="")
    source_context: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="待审核")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class FrameSnapshotRecord(Base):
    __tablename__ = "frame_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    image_path: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    detected_scene: Mapped[str] = mapped_column(String(100), default="未识别")
    sharpness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    brightness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recognized_product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recognized_product_name: Mapped[str] = mapped_column(String(255), default="")
    recognition_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    recognition_source: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ReplayReportRecord(Base):
    __tablename__ = "replay_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    summary: Mapped[str] = mapped_column(Text)
    useful_scripts: Mapped[list[str]] = mapped_column(JSON, default=list)
    missed_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    risk_warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    audience_questions: Mapped[list[str]] = mapped_column(JSON, default=list)
    next_suggestions: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class WikiChunkRecord(Base):
    __tablename__ = "wiki_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_path: Mapped[str] = mapped_column(Text)
    heading: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class VirtualCustomerRecord(Base):
    __tablename__ = "virtual_customers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(100))
    level: Mapped[str] = mapped_column(String(50))
    personality: Mapped[str] = mapped_column(String(100), default="")
    preferred_colors: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    budget_range: Mapped[str] = mapped_column(String(100), default="")
    common_questions: Mapped[list[str]] = mapped_column(JSON, default=list)
    purchased_items: Mapped[list[str]] = mapped_column(JSON, default=list)
    purchased_amount: Mapped[float] = mapped_column(Float, default=0)
    relationship_strategy: Mapped[str] = mapped_column(Text, default="")
    activity_level: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class CustomerMemoryRecord(Base):
    __tablename__ = "customer_memories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    said_texts: Mapped[list[str]] = mapped_column(JSON, default=list)
    asked_questions: Mapped[list[str]] = mapped_column(JSON, default=list)
    purchased_items: Mapped[list[str]] = mapped_column(JSON, default=list)
    preference_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    interest_score: Mapped[float] = mapped_column(Float, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class VirtualCustomerEventRecord(Base):
    __tablename__ = "virtual_customer_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    customer_nickname: Mapped[str] = mapped_column(String(100))
    customer_level: Mapped[str] = mapped_column(String(50))
    event_type: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    trigger_reason: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class AgentProfileRecord(Base):
    __tablename__ = "agent_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(100))
    persona: Mapped[str] = mapped_column(Text, default="")
    tone: Mapped[str] = mapped_column(String(100), default="")
    allowed_auto_actions: Mapped[list[str]] = mapped_column(JSON, default=list)
    risk_policy: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class AgentUtteranceRecord(Base):
    __tablename__ = "agent_utterances"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    agent_id: Mapped[str] = mapped_column(String(64))
    agent_name: Mapped[str] = mapped_column(String(100))
    agent_role: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(String(100), default="JLAO")
    content: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(50), default="低")
    send_mode: Mapped[str] = mapped_column(String(50), default="auto_simulated")
    status: Mapped[str] = mapped_column(String(50), default="已生成")
    trigger_reason: Mapped[str] = mapped_column(Text, default="")
    wiki_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    customer_event_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
