import asyncio
import os
import sys
import traceback
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

WORKSPACE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(WORKSPACE_DIR / '.env')

from app.api.auth import router as auth_router
from app.api.capture_card import router as capture_card_router
from app.api.capture_control import router as capture_control_router
from app.api.agents import router as agents_router
from app.api.customers import router as customers_router
from app.api.frames import router as frames_router
from app.api.ffmpeg_capture import router as ffmpeg_capture_router
from app.api.jade_yolo_live import router as jade_yolo_live_router
from app.api.native_audio import router as native_audio_router
from app.api.native_stt import router as native_stt_router
from app.api.phone_capture import router as phone_capture_router
from app.api.recording import router as recording_router
from app.api.products import router as products_router
from app.api.replay import router as replay_router
from app.api.runtime_settings import router as runtime_settings_router
from app.api.scrcpy import router as scrcpy_router
from app.api.sessions import router as sessions_router
from app.api.suggestions import router as suggestions_router
from app.api.wiki import router as wiki_router
from app.auth_utils import get_current_user
from app.services.native_audio_service import initialize_native_audio_runtime
from app.services.native_stt_service import initialize_native_stt_runtime
from app.services.capture_resource_service import startup_reset as startup_capture_resource_reset
from app.state import app_state
from app.ws.scrcpy_ws import router as scrcpy_ws_router
from app.ws.session_ws import router as ws_router
from app.ws.stt_ws import router as stt_ws_router

app = FastAPI(title="JLAO API", version="0.1.0")

UPLOADS_DIR = WORKSPACE_DIR / "uploads"
FRONTEND_DIST_DIR = WORKSPACE_DIR / "frontend" / "dist"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://jlao.szkakayiduo.com",
        "https://*.szkakayiduo.com",
        os.getenv("FRONTEND_URL", "http://47.120.41.143"),
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def add_private_network_access_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


@app.on_event("startup")
async def startup() -> None:
    app_state.load_seed_data()
    await startup_capture_resource_reset()
    await initialize_native_audio_runtime()
    await initialize_native_stt_runtime()


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
app.include_router(capture_card_router, prefix="/api", tags=["capture-card"], dependencies=_auth_dep)
app.include_router(capture_control_router, prefix="/api", tags=["capture-control"], dependencies=_auth_dep)
app.include_router(ffmpeg_capture_router, prefix="/api", tags=["ffmpeg-capture"], dependencies=_auth_dep)
app.include_router(jade_yolo_live_router, prefix="/api", tags=["jade-yolo-live"], dependencies=_auth_dep)
app.include_router(scrcpy_router, prefix="/api", tags=["scrcpy"])
app.include_router(phone_capture_router, prefix="/api", tags=["phone-capture"], dependencies=_auth_dep)
app.include_router(native_audio_router, prefix="/api", tags=["native-audio"], dependencies=_auth_dep)
app.include_router(native_stt_router, prefix="/api", tags=["native-stt"], dependencies=_auth_dep)
app.include_router(recording_router, prefix="/api", tags=["recording"], dependencies=_auth_dep)
app.include_router(runtime_settings_router, prefix="/api", tags=["runtime-settings"], dependencies=_auth_dep)
app.include_router(ws_router)
app.include_router(stt_ws_router)
app.include_router(scrcpy_ws_router)


@app.get("/{path:path}", include_in_schema=False)
async def serve_frontend_app(path: str) -> FileResponse:
    first_segment = path.split("/", 1)[0]
    if first_segment in {"api", "ws", "uploads", "health"}:
        raise HTTPException(status_code=404, detail="Not Found")
    if not FRONTEND_DIST_DIR.exists():
        raise HTTPException(status_code=404, detail="前端构建产物不存在，请先运行 npm run build")

    requested = (FRONTEND_DIST_DIR / path).resolve() if path else FRONTEND_DIST_DIR / "index.html"
    try:
        requested.relative_to(FRONTEND_DIST_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="禁止访问")

    if requested.is_file():
        return FileResponse(requested)
    index_file = FRONTEND_DIST_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="前端入口文件不存在，请先运行 npm run build")
    return FileResponse(index_file)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})
