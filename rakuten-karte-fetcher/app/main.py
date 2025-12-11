"""
Rakuten Karte Fetcher - FastAPI Application Entry Point

This service provides:
1. Automated CSV download from Rakuten RMS 店舗カルテ
2. CSV to JSON parsing and aggregation
3. REST API for querying shop data
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Rakuten Karte Fetcher",
    description="乐天店舗カルテ数据自动化抓取与API服务",
    version="0.1.0"
)


@app.get("/health", tags=["System"])
async def health_check():
    """
    健康检查端点
    
    Returns:
        dict: 服务状态信息
    """
    return {"status": "ok", "service": "rakuten-karte-fetcher"}


@app.get("/", tags=["System"])
async def root():
    """
    根路径 - 返回服务基本信息
    """
    return {
        "service": "Rakuten Karte Fetcher",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health"
    }


# TODO: 后续阶段添加以下路由
# from .api.routers import router as api_router
# app.include_router(api_router, prefix="/rakuten")
