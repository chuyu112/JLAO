import asyncio
import os
import sys
import traceback

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.auth import router as auth_router
from app.api.agents import router as agents_router
from app.api.customers import router as customers_router
from app.api.frames import router as frames_router
from app.api.ffmpeg_capture import router as ffmpeg_capture_router
from app.api.phone_capture import router as phone_capture_router
from app.api.products import router as products_router
from app.api.replay import router as replay_router
from app.api.scrcpy import router as scrcpy_router
from app.api.sessions import router as sessions_router
from app.api.suggestions import router as suggestions_router
from app.api.wiki import router as wiki_router
from app.auth_utils import get_current_user
from app.state import WORKSPACE_DIR, app_state
from app.ws.scrcpy_ws import router as scrcpy_ws_router
from app.ws.session_ws import router as ws_router
from app.ws.stt_ws import router as stt_ws_router

app = FastAPI(title="JLAO API", version="0.1.0")

UPLOADS_DIR = WORKSPACE_DIR / "uploads"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        os.getenv("FRONTEND_URL", "http://47.120.41.143"),
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.on_event("startup")
async def startup() -> None:
    app_state.load_seed_data()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "JLAO API"}


@app.get("/uploads/{path:path}")
async def serve_uploads(path: str, user: dict = Depends(get_current_user)) -> FileResponse:
    file_path = UPLOADS_DIR / path
    try:
        file_path.resolve().relative_to(UPLOADS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="禁止访问")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path)


# Global auth dependency for all business endpoints
_auth_dep = [Depends(get_current_user)]

app.include_router(sessions_router, prefix="/api/sessions", tags=["sessions"], dependencies=_auth_dep)
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(agents_router, prefix="/api", tags=["agents"], dependencies=_auth_dep)
app.include_router(customers_router, prefix="/api", tags=["customers"], dependencies=_auth_dep)
app.include_router(products_router, prefix="/api/products", tags=["products"], dependencies=_auth_dep)
app.include_router(suggestions_router, prefix="/api/suggestions", tags=["suggestions"], dependencies=_auth_dep)
app.include_router(wiki_router, prefix="/api", tags=["wiki"], dependencies=_auth_dep)
app.include_router(replay_router, prefix="/api", tags=["replay"], dependencies=_auth_dep)
app.include_router(frames_router, prefix="/api", tags=["frames"], dependencies=_auth_dep)
app.include_router(ffmpeg_capture_router, prefix="/api", tags=["ffmpeg-capture"], dependencies=_auth_dep)
app.include_router(scrcpy_router, prefix="/api", tags=["scrcpy"], dependencies=_auth_dep)
app.include_router(phone_capture_router, prefix="/api", tags=["phone-capture"], dependencies=_auth_dep)
app.include_router(ws_router)
app.include_router(stt_ws_router)
app.include_router(scrcpy_ws_router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})
