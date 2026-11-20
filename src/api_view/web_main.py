"""
FastAPI 应用入口
CORS 全开、路由注册、startup/shutdown 事件
"""
import sys
import os
from pathlib import Path
from contextlib import asynccontextmanager

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .api.chat import router as chat_router
from .api.alerts import router as alerts_router
from .api.history import router as history_router
from ..alerts.service import alert_scheduler
from .web_config import close_mongo_client
from ..agent.log_utils import web_logger
from ..agent.env_utils import get_env
from ..security import UnsafePathError, safe_join


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    web_logger.info("Starting ERP Agent Web Server...")
    alert_scheduler.start()
    yield
    # Shutdown
    web_logger.info("Shutting down ERP Agent Web Server...")
    await alert_scheduler.stop()
    await close_mongo_client()


app = FastAPI(
    title="汽车零部件智能采购助手",
    description="基于 Harness Engineering 架构的汽车零部件采购智能助手 API",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins = [
    origin.strip()
    for origin in get_env("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# 注册路由
app.include_router(chat_router)
app.include_router(history_router)
app.include_router(alerts_router)

# 文件下载目录（图表等生成文件）
DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "download"
DOWNLOAD_DIR.mkdir(exist_ok=True)


@app.get("/api/download/{filename}")
async def download_file(filename: str):
    """提供生成文件（图表PNG等）的HTTP下载"""
    try:
        file_path = safe_join(DOWNLOAD_DIR, filename)
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"文件不存在: {filename}")
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@app.get("/")
async def root():
    return {"message": "汽车零部件智能采购助手 API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=get_env("API_HOST", "127.0.0.1"),
        port=int(get_env("API_PORT", "8000")),
    )
