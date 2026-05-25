import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
from app.state import WORKSPACE_DIR, app_state
from app.ws.scrcpy_ws import router as scrcpy_ws_router
from app.ws.session_ws import router as ws_router
from app.ws.stt_ws import router as stt_ws_router


app = FastAPI(title="JLAO API", version="0.1.0")
app.mount("/uploads", StaticFiles(directory=WORKSPACE_DIR / "uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://47.120.41.143",
        "http://47.120.41.143:80",
        "http://jlao.szkakayiduo.com",
        "https://jlao.szkakayiduo.com",
        "http://JLAO.szkakayiduo.com",
        "https://JLAO.szkakayiduo.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    app_state.load_seed_data()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "JLAO API"}


app.include_router(sessions_router, prefix="/api/sessions", tags=["sessions"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(agents_router, prefix="/api", tags=["agents"])
app.include_router(customers_router, prefix="/api", tags=["customers"])
app.include_router(products_router, prefix="/api/products", tags=["products"])
app.include_router(suggestions_router, prefix="/api/suggestions", tags=["suggestions"])
app.include_router(wiki_router, prefix="/api", tags=["wiki"])
app.include_router(replay_router, prefix="/api", tags=["replay"])
app.include_router(frames_router, prefix="/api", tags=["frames"])
app.include_router(ffmpeg_capture_router, prefix="/api", tags=["ffmpeg-capture"])
app.include_router(scrcpy_router, prefix="/api", tags=["scrcpy"])
app.include_router(phone_capture_router, prefix="/api", tags=["phone-capture"])
app.include_router(ws_router)
app.include_router(stt_ws_router)
app.include_router(scrcpy_ws_router)
