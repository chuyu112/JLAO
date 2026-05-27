from collections.abc import Iterable

from sqlalchemy import delete, select

from app.db import session_scope
from app.db_models import (
    AgentProfileRecord,
    AgentUtteranceRecord,
    CustomerMemoryRecord,
    FrameSnapshotRecord,
    LiveSessionRecord,
    ProductRecord,
    ReplayReportRecord,
    SuggestionRecord,
    TranscriptSegmentRecord,
    VirtualCustomerEventRecord,
    VirtualCustomerRecord,
    WikiChunkRecord,
)
from app.schemas import (
    AgentProfile,
    AgentUtterance,
    CustomerMemory,
    FrameSnapshot,
    LiveSession,
    Product,
    ReplayReport,
    SessionStatus,
    Suggestion,
    SuggestionStatus,
    TranscriptSegment,
    VirtualCustomer,
    VirtualCustomerEvent,
    WikiChunk,
)


def _status_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _product_from_record(record: ProductRecord) -> Product:
    return Product(
        id=record.id,
        name=record.name,
        category=record.category,
        material=record.material or "",
        color=record.color or "",
        water=record.water or "",
        size=record.size or "",
        weight=record.weight or "",
        certificate=record.certificate or "",
        flaws=record.flaws or "",
        cautions=record.cautions or "",
        price=record.price,
        selling_points=record.selling_points or [],
        faq=record.faq or [],
        recommended_scripts=record.recommended_scripts or [],
    )


def _upsert_product_record(session, product: Product) -> None:
    record = session.get(ProductRecord, product.id)
    payload = product.model_dump()
    if record:
        for key, value in payload.items():
            setattr(record, key, value)
    else:
        session.add(ProductRecord(**payload))


def seed_products(products: Iterable[Product]) -> None:
    with session_scope() as session:
        existing = session.scalar(select(ProductRecord.id).limit(1))
        if existing:
            return
        for product in products:
            _upsert_product_record(session, product)


def save_product(product: Product) -> None:
    with session_scope() as session:
        _upsert_product_record(session, product)


def delete_product(product_id: str) -> None:
    with session_scope() as session:
        session.execute(delete(ProductRecord).where(ProductRecord.id == product_id))


def list_products() -> list[Product]:
    with session_scope() as session:
        records = session.scalars(select(ProductRecord).order_by(ProductRecord.id)).all()
        return [_product_from_record(record) for record in records]


def _session_from_record(record: LiveSessionRecord) -> LiveSession:
    return LiveSession(
        id=record.id,
        title=record.title,
        platform=record.platform,
        anchor_name=record.anchor_name,
        operator_name=record.operator_name,
        status=SessionStatus(record.status),
        current_product_id=record.current_product_id,
        manual_product_name=record.manual_product_name or "",
        live_url=record.live_url,
        detected_color=record.detected_color or "",
        detected_water=record.detected_water or "",
        detected_subject=record.detected_subject or "",
        detected_extra=record.detected_extra or "",
        detected_full_name=record.detected_full_name or "",
        start_time=record.start_time,
        end_time=record.end_time,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def save_live_session(live_session: LiveSession) -> None:
    with session_scope() as session:
        record = session.get(LiveSessionRecord, live_session.id)
        payload = live_session.model_dump()
        payload["status"] = _status_value(live_session.status)
        if record:
            for key, value in payload.items():
                setattr(record, key, value)
        else:
            session.add(LiveSessionRecord(**payload))


def list_live_sessions() -> list[LiveSession]:
    with session_scope() as session:
        records = session.scalars(select(LiveSessionRecord).order_by(LiveSessionRecord.created_at)).all()
        return [_session_from_record(record) for record in records]


def _transcript_from_record(record: TranscriptSegmentRecord) -> TranscriptSegment:
    return TranscriptSegment(
        id=record.id,
        session_id=record.session_id,
        index=record.index,
        text=record.text,
        keywords=record.keywords or [],
        created_at=record.created_at,
    )


def save_transcript(segment: TranscriptSegment) -> None:
    with session_scope() as session:
        if not session.get(TranscriptSegmentRecord, segment.id):
            session.add(TranscriptSegmentRecord(**segment.model_dump()))


def list_transcripts(session_id: str) -> list[TranscriptSegment]:
    with session_scope() as session:
        records = session.scalars(
            select(TranscriptSegmentRecord)
            .where(TranscriptSegmentRecord.session_id == session_id)
            .order_by(TranscriptSegmentRecord.index)
        ).all()
        return [_transcript_from_record(record) for record in records]


def _suggestion_from_record(record: SuggestionRecord) -> Suggestion:
    return Suggestion(
        id=record.id,
        session_id=record.session_id,
        product_id=record.product_id,
        type=record.type,
        target_role=record.target_role,
        priority=record.priority,
        risk_level=record.risk_level,
        content=record.content,
        reason=record.reason,
        source_context=record.source_context,
        status=SuggestionStatus(record.status),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def save_suggestion(suggestion: Suggestion) -> None:
    with session_scope() as session:
        record = session.get(SuggestionRecord, suggestion.id)
        payload = suggestion.model_dump()
        payload["status"] = _status_value(suggestion.status)
        if record:
            for key, value in payload.items():
                setattr(record, key, value)
        else:
            session.add(SuggestionRecord(**payload))


def list_suggestions(session_id: str) -> list[Suggestion]:
    with session_scope() as session:
        records = session.scalars(
            select(SuggestionRecord)
            .where(SuggestionRecord.session_id == session_id)
            .order_by(SuggestionRecord.created_at)
        ).all()
        return [_suggestion_from_record(record) for record in records]


def _frame_from_record(record: FrameSnapshotRecord) -> FrameSnapshot:
    return FrameSnapshot(
        id=record.id,
        session_id=record.session_id,
        timestamp=record.timestamp,
        image_path=record.image_path,
        summary=record.summary,
        detected_scene=record.detected_scene,
        sharpness_score=record.sharpness_score,
        brightness_score=record.brightness_score,
        change_score=record.change_score,
        recognized_product_id=record.recognized_product_id,
        recognized_product_name=record.recognized_product_name,
        recognition_confidence=record.recognition_confidence,
        recognition_source=record.recognition_source,
        created_at=record.created_at,
    )


def save_frame_snapshot(snapshot: FrameSnapshot) -> None:
    with session_scope() as session:
        if not session.get(FrameSnapshotRecord, snapshot.id):
            session.add(FrameSnapshotRecord(**snapshot.model_dump()))


def list_frame_snapshots(session_id: str) -> list[FrameSnapshot]:
    with session_scope() as session:
        records = session.scalars(
            select(FrameSnapshotRecord)
            .where(FrameSnapshotRecord.session_id == session_id)
            .order_by(FrameSnapshotRecord.created_at.desc())
        ).all()
        return [_frame_from_record(record) for record in records]


def trim_frame_snapshots(session_id: str, keep: int) -> None:
    with session_scope() as session:
        records = session.scalars(
            select(FrameSnapshotRecord)
            .where(FrameSnapshotRecord.session_id == session_id)
            .order_by(FrameSnapshotRecord.created_at.desc())
            .offset(keep)
        ).all()
        for record in records:
            session.delete(record)


def save_replay_report(report: ReplayReport) -> None:
    with session_scope() as session:
        record = session.get(ReplayReportRecord, report.id)
        if record:
            return
        session.add(ReplayReportRecord(**report.model_dump()))


def _wiki_chunk_from_record(record: WikiChunkRecord) -> WikiChunk:
    return WikiChunk(
        id=record.id,
        source_path=record.source_path,
        heading=record.heading,
        content=record.content,
        tags=record.tags or [],
        updated_at=record.updated_at,
    )


def replace_wiki_chunks(chunks: list[WikiChunk]) -> None:
    with session_scope() as session:
        session.execute(delete(WikiChunkRecord))
        for chunk in chunks:
            session.add(WikiChunkRecord(**chunk.model_dump()))


def list_wiki_chunks() -> list[WikiChunk]:
    with session_scope() as session:
        records = session.scalars(select(WikiChunkRecord).order_by(WikiChunkRecord.heading)).all()
        return [_wiki_chunk_from_record(record) for record in records]


def _virtual_customer_from_record(record: VirtualCustomerRecord) -> VirtualCustomer:
    return VirtualCustomer(
        id=record.id,
        nickname=record.nickname,
        level=record.level,
        personality=record.personality,
        preferred_colors=record.preferred_colors or [],
        preferred_categories=record.preferred_categories or [],
        budget_range=record.budget_range,
        common_questions=record.common_questions or [],
        purchased_items=record.purchased_items or [],
        purchased_amount=record.purchased_amount,
        relationship_strategy=record.relationship_strategy,
        activity_level=record.activity_level,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def seed_virtual_customers(customers: Iterable[VirtualCustomer]) -> None:
    with session_scope() as session:
        existing = session.scalar(select(VirtualCustomerRecord.id).limit(1))
        if existing:
            return
        for customer in customers:
            session.add(VirtualCustomerRecord(**customer.model_dump()))
            memory_id = f"mem-{customer.id}"
            session.add(
                CustomerMemoryRecord(
                    id=memory_id,
                    customer_id=customer.id,
                    purchased_items=customer.purchased_items,
                    preference_tags=customer.preferred_colors + customer.preferred_categories,
                    interest_score=customer.activity_level,
                )
            )


def list_virtual_customers() -> list[VirtualCustomer]:
    with session_scope() as session:
        records = session.scalars(select(VirtualCustomerRecord).order_by(VirtualCustomerRecord.level.desc())).all()
        return [_virtual_customer_from_record(record) for record in records]


def save_virtual_customer_event(event: VirtualCustomerEvent) -> None:
    with session_scope() as session:
        if not session.get(VirtualCustomerEventRecord, event.id):
            session.add(VirtualCustomerEventRecord(**event.model_dump()))


def list_virtual_customer_events(session_id: str) -> list[VirtualCustomerEvent]:
    with session_scope() as session:
        records = session.scalars(
            select(VirtualCustomerEventRecord)
            .where(VirtualCustomerEventRecord.session_id == session_id)
            .order_by(VirtualCustomerEventRecord.created_at.desc())
        ).all()
        return [
            VirtualCustomerEvent(
                id=record.id,
                session_id=record.session_id,
                customer_id=record.customer_id,
                customer_nickname=record.customer_nickname,
                customer_level=record.customer_level,
                event_type=record.event_type,
                content=record.content,
                trigger_reason=record.trigger_reason,
                priority=record.priority,
                created_at=record.created_at,
            )
            for record in records
        ]


def _agent_profile_from_record(record: AgentProfileRecord) -> AgentProfile:
    return AgentProfile(
        id=record.id,
        name=record.name,
        role=record.role,
        persona=record.persona,
        tone=record.tone,
        allowed_auto_actions=record.allowed_auto_actions or [],
        risk_policy=record.risk_policy,
        enabled=record.enabled,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def seed_agent_profiles(agents: Iterable[AgentProfile]) -> None:
    with session_scope() as session:
        existing = session.scalar(select(AgentProfileRecord.id).limit(1))
        if existing:
            return
        for agent in agents:
            session.add(AgentProfileRecord(**agent.model_dump()))


def list_agent_profiles() -> list[AgentProfile]:
    with session_scope() as session:
        records = session.scalars(select(AgentProfileRecord).order_by(AgentProfileRecord.id)).all()
        return [_agent_profile_from_record(record) for record in records]


def save_agent_utterance(utterance: AgentUtterance) -> None:
    with session_scope() as session:
        if not session.get(AgentUtteranceRecord, utterance.id):
            session.add(AgentUtteranceRecord(**utterance.model_dump()))


def list_agent_utterances(session_id: str) -> list[AgentUtterance]:
    with session_scope() as session:
        records = session.scalars(
            select(AgentUtteranceRecord)
            .where(AgentUtteranceRecord.session_id == session_id)
            .order_by(AgentUtteranceRecord.created_at.desc())
        ).all()
        return [
            AgentUtterance(
                id=record.id,
                session_id=record.session_id,
                agent_id=record.agent_id,
                agent_name=record.agent_name,
                agent_role=record.agent_role,
                target=record.target,
                content=record.content,
                risk_level=record.risk_level,
                send_mode=record.send_mode,
                status=record.status,
                trigger_reason=record.trigger_reason,
                wiki_chunk_ids=record.wiki_chunk_ids or [],
                customer_event_ids=record.customer_event_ids or [],
                created_at=record.created_at,
                sent_at=record.sent_at,
            )
            for record in records
        ]


def hydrate_state(app_state) -> None:
    app_state.products = {product.id: product for product in list_products()}
    app_state.sessions = {session.id: session for session in list_live_sessions()}
    app_state.transcripts = {session_id: list_transcripts(session_id) for session_id in app_state.sessions}
    app_state.suggestions = {session_id: list_suggestions(session_id) for session_id in app_state.sessions}
    app_state.frames = {session_id: list_frame_snapshots(session_id) for session_id in app_state.sessions}
