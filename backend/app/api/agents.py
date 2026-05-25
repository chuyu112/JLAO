from fastapi import APIRouter, HTTPException

from app.repositories import list_agent_profiles, list_agent_utterances
from app.schemas import AgentProfile, AgentUtterance
from app.state import app_state

router = APIRouter()


@router.get("/agents", response_model=list[AgentProfile])
async def get_agents() -> list[AgentProfile]:
    return list_agent_profiles()


@router.get("/sessions/{session_id}/agent-utterances", response_model=list[AgentUtterance])
async def get_agent_utterances(session_id: str) -> list[AgentUtterance]:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return list_agent_utterances(session_id)
