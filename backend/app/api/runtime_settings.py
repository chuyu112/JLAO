from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import runtime_settings_service

router = APIRouter()


class SttRuntimeSettingsUpdate(BaseModel):
    local_stt_device: str | None = None
    stt_provider: str | None = None


@router.get("/runtime/stt")
async def get_stt_runtime_settings() -> dict:
    return runtime_settings_service.get_stt_runtime_settings()


@router.post("/runtime/stt")
async def update_stt_runtime_settings(payload: SttRuntimeSettingsUpdate) -> dict:
    try:
        return runtime_settings_service.update_stt_runtime_settings(
            local_stt_device=payload.local_stt_device,
            stt_provider=payload.stt_provider,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
