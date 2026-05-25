from fastapi import APIRouter, HTTPException

from app.repositories import save_replay_report
from app.schemas import ReplayReport
from app.services.replay_service import build_replay_report
from app.state import app_state

router = APIRouter()


@router.post("/sessions/{session_id}/replay", response_model=ReplayReport)
async def create_replay(session_id: str) -> ReplayReport:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")

    report = build_replay_report(
        session_id=session_id,
        transcripts=app_state.transcripts.get(session_id, []),
        suggestions=app_state.suggestions.get(session_id, []),
    )
    app_state.reports[session_id] = report
    save_replay_report(report)
    return report


@router.get("/sessions/{session_id}/report", response_model=ReplayReport)
async def get_replay(session_id: str) -> ReplayReport:
    report = app_state.reports.get(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="复盘报告不存在，请先生成复盘")
    return report

