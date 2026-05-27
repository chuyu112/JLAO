from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.repositories import save_suggestion
from app.schemas import Suggestion, SuggestionStatus, SuggestionUpdate
from app.state import app_state
from app.ws.manager import manager

router = APIRouter()


@router.get("/sessions/{session_id}", response_model=list[Suggestion])
async def list_session_suggestions(session_id: str) -> list[Suggestion]:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return app_state.suggestions.get(session_id, [])


@router.post("/{suggestion_id}/accept", response_model=Suggestion)
async def accept_suggestion(suggestion_id: str) -> Suggestion:
    return await _set_status(suggestion_id, SuggestionStatus.accepted)


@router.post("/{suggestion_id}/copy", response_model=Suggestion)
async def copy_suggestion(suggestion_id: str) -> Suggestion:
    return await _set_status(suggestion_id, SuggestionStatus.copied)


@router.post("/{suggestion_id}/used", response_model=Suggestion)
async def used_suggestion(suggestion_id: str) -> Suggestion:
    return await _set_status(suggestion_id, SuggestionStatus.used)


@router.post("/{suggestion_id}/reject", response_model=Suggestion)
async def reject_suggestion(suggestion_id: str) -> Suggestion:
    return await _set_status(suggestion_id, SuggestionStatus.rejected)


@router.post("/{suggestion_id}/edit", response_model=Suggestion)
async def edit_suggestion(suggestion_id: str, payload: SuggestionUpdate) -> Suggestion:
    suggestion, session_id, index = _find_suggestion(suggestion_id)
    updated = suggestion.model_copy(
        update={
            "content": payload.content or suggestion.content,
            "status": SuggestionStatus.edited,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    app_state.suggestions[session_id][index] = updated
    save_suggestion(updated)
    await manager.broadcast(session_id, "suggestion_updated", updated.model_dump(mode="json"))
    return updated


async def _set_status(suggestion_id: str, status: SuggestionStatus) -> Suggestion:
    suggestion, session_id, index = _find_suggestion(suggestion_id)
    updated = suggestion.model_copy(update={"status": status, "updated_at": datetime.now(timezone.utc)})
    app_state.suggestions[session_id][index] = updated
    save_suggestion(updated)
    await manager.broadcast(session_id, "suggestion_updated", updated.model_dump(mode="json"))
    return updated


def _find_suggestion(suggestion_id: str) -> tuple[Suggestion, str, int]:
    for session_id, suggestions in app_state.suggestions.items():
        for index, suggestion in enumerate(suggestions):
            if suggestion.id == suggestion_id:
                return suggestion, session_id, index
    raise HTTPException(status_code=404, detail="AI 建议不存在")

