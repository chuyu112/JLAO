from fastapi import APIRouter, HTTPException

from app.repositories import list_virtual_customer_events, list_virtual_customers
from app.schemas import VirtualCustomer, VirtualCustomerEvent
from app.state import app_state

router = APIRouter()


@router.get("/sessions/{session_id}/virtual-customers", response_model=list[VirtualCustomer])
async def get_virtual_customers(session_id: str) -> list[VirtualCustomer]:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return list_virtual_customers()


@router.get("/sessions/{session_id}/customer-events", response_model=list[VirtualCustomerEvent])
async def get_customer_events(session_id: str) -> list[VirtualCustomerEvent]:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return list_virtual_customer_events(session_id)


@router.get("/sessions/{session_id}/live-comments", response_model=list[VirtualCustomerEvent])
async def get_live_comments(session_id: str) -> list[VirtualCustomerEvent]:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return app_state.live_comments.get(session_id, [])


@router.get("/sessions/{session_id}/live-comments/status")
async def get_live_comments_status(session_id: str) -> dict:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")
    return app_state.live_comment_ocr_status.get(session_id, {})
