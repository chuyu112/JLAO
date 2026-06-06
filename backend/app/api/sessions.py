from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.repositories import save_live_session
from app.schemas import LiveSession, LiveSessionCreate, LiveUrlUpdate, ManualProductNameUpdate, SessionStatus, TranscriptSegment
from app.services.transcript_service import append_transcript
from app.state import app_state
from app.ws.manager import manager

router = APIRouter()


@router.get("", response_model=list[LiveSession])
async def list_sessions() -> list[LiveSession]:
    return list(app_state.sessions.values())


@router.post("", response_model=LiveSession)
async def create_session(payload: LiveSessionCreate) -> LiveSession:
    now = datetime.now(timezone.utc)
    session = LiveSession(
        id=app_state.new_id("live"),
        title=payload.title,
        live_room_name=payload.live_room_name.strip(),
        platform=payload.platform,
        anchor_name=payload.anchor_name,
        operator_name=payload.operator_name,
        current_product_id=payload.current_product_id,
        live_url=payload.live_url,
        created_at=now,
        updated_at=now,
    )
    app_state.sessions[session.id] = session
    app_state.transcripts[session.id] = []
    app_state.suggestions[session.id] = []
    app_state.frames[session.id] = []
    save_live_session(session)
    return session


@router.get("/{session_id}", response_model=LiveSession)
async def get_session(session_id: str) -> LiveSession:
    session = app_state.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return session


@router.post("/{session_id}/current-product/{product_id}", response_model=LiveSession)
async def set_current_product(session_id: str, product_id: str) -> LiveSession:
    session = app_state.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    if product_id not in app_state.products:
        raise HTTPException(status_code=404, detail="商品不存在")

    updated = session.model_copy(update={"current_product_id": product_id, "updated_at": datetime.now(timezone.utc)})
    app_state.sessions[session_id] = updated
    save_live_session(updated)
    await manager.broadcast(session_id, "session_status", updated.model_dump(mode="json"))
    return updated


@router.post("/{session_id}/live-url", response_model=LiveSession)
async def set_live_url(session_id: str, payload: LiveUrlUpdate) -> LiveSession:
    session = app_state.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="直播会话不存在")

    updated = session.model_copy(update={"live_url": payload.live_url, "updated_at": datetime.now(timezone.utc)})
    app_state.sessions[session_id] = updated
    save_live_session(updated)
    await manager.broadcast(session_id, "session_status", updated.model_dump(mode="json"))
    return updated


@router.post("/{session_id}/start", response_model=LiveSession)
async def start_session(session_id: str) -> LiveSession:
    session = app_state.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="直播会话不存在")

    updated = session.model_copy(
        update={"status": SessionStatus.running, "start_time": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}
    )
    app_state.sessions[session_id] = updated
    save_live_session(updated)
    await manager.broadcast(session_id, "session_status", updated.model_dump(mode="json"))
    return updated


@router.post("/{session_id}/stop", response_model=LiveSession)
async def stop_session(session_id: str) -> LiveSession:
    session = app_state.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="直播会话不存在")

    updated = session.model_copy(
        update={"status": SessionStatus.stopped, "end_time": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}
    )
    app_state.sessions[session_id] = updated
    save_live_session(updated)
    await manager.broadcast(session_id, "session_status", updated.model_dump(mode="json"))
    return updated


@router.post("/{session_id}/manual-product-name", response_model=LiveSession)
async def set_manual_product_name(session_id: str, payload: ManualProductNameUpdate) -> LiveSession:
    session = app_state.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="直播会话不存在")

    updated = session.model_copy(
        update={"manual_product_name": payload.manual_product_name.strip(), "updated_at": datetime.now(timezone.utc)}
    )
    app_state.sessions[session_id] = updated
    save_live_session(updated)
    await manager.broadcast(session_id, "session_status", updated.model_dump(mode="json"))
    return updated


@router.get("/{session_id}/transcripts", response_model=list[TranscriptSegment])
async def list_transcripts(session_id: str) -> list[TranscriptSegment]:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return app_state.transcripts.get(session_id, [])


@router.post("/{session_id}/transcript/manual", response_model=TranscriptSegment)
async def add_manual_transcript(session_id: str, text: str) -> TranscriptSegment:
    return await append_transcript(session_id, text)
