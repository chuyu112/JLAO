from datetime import datetime

from fastapi import HTTPException

from app.repositories import (
    list_virtual_customer_events,
    list_virtual_customers,
    save_agent_utterance,
    save_suggestion,
    save_transcript,
    save_virtual_customer_event,
)
from app.schemas import TranscriptSegment
from app.services.agent_service import generate_suggestions
from app.services.context_service import extract_keywords
from app.services.multi_agent_service import generate_agent_utterances
from app.services.product_recognition_service import (
    apply_recognition,
    extract_dimensions_from_text,
    match_products_by_text,
)
from app.services.virtual_customer_service import generate_customer_events
from app.services.wiki_service import search_indexed_wiki
from app.state import app_state
from app.ws.manager import manager


async def append_transcript(session_id: str, text: str) -> TranscriptSegment:
    cleaned = text.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="转写内容不能为空")
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")

    segments = app_state.transcripts.setdefault(session_id, [])
    segment = TranscriptSegment(
        id=app_state.new_id("seg"),
        session_id=session_id,
        index=len(segments) + 1,
        text=cleaned,
        keywords=extract_keywords(cleaned),
        created_at=datetime.utcnow(),
    )
    segments.append(segment)
    save_transcript(segment)
    await manager.broadcast(session_id, "transcript_segment", segment.model_dump(mode="json"))

    text_scores = match_products_by_text(cleaned)
    water, subject, extra = extract_dimensions_from_text(cleaned)
    if text_scores:
        await apply_recognition(
            session_id,
            text_scores=text_scores,
            detected_water=water,
            detected_subject=subject,
            detected_extra=extra,
        )
    elif water or subject or extra:
        await apply_recognition(
            session_id,
            detected_water=water,
            detected_subject=subject,
            detected_extra=extra,
        )

    session = app_state.sessions[session_id]
    product = app_state.products.get(session.current_product_id) if session.current_product_id else None
    new_suggestions = generate_suggestions(session_id, product, segments)
    if new_suggestions:
        existing = app_state.suggestions.setdefault(session_id, [])
        for suggestion in new_suggestions:
            if any(item.content == suggestion.content for item in existing[-8:]):
                continue
            existing.append(suggestion)
            save_suggestion(suggestion)
            await manager.broadcast(session_id, "suggestion_created", suggestion.model_dump(mode="json"))
            if suggestion.type == "风险提醒":
                await manager.broadcast(session_id, "risk_warning", suggestion.model_dump(mode="json"))

    wiki_query = " ".join(
        [
            cleaned,
            product.name if product else "",
            product.category if product else "",
            product.color if product else "",
        ]
    )
    wiki_hits = search_indexed_wiki(wiki_query, limit=5)
    if wiki_hits:
        await manager.broadcast(session_id, "wiki_hits", {"items": [item.model_dump(mode="json") for item in wiki_hits]})

    existing_event_count = len(list_virtual_customer_events(session_id))
    customer_events = generate_customer_events(
        session_id=session_id,
        customers=list_virtual_customers(),
        product=product,
        transcript_text=cleaned,
        existing_event_count=existing_event_count,
    )
    for event in customer_events:
        save_virtual_customer_event(event)
        await manager.broadcast(session_id, "virtual_customer_event", event.model_dump(mode="json"))
        if event.event_type == "高价值进房":
            await manager.broadcast(session_id, "high_value_customer_alert", event.model_dump(mode="json"))

    utterances = generate_agent_utterances(
        session_id=session_id,
        product=product,
        transcript_text=cleaned,
        wiki_hits=wiki_hits,
        customer_events=customer_events,
    )
    for utterance in utterances:
        save_agent_utterance(utterance)
        await manager.broadcast(session_id, "agent_utterance", utterance.model_dump(mode="json"))

    return segment
