"""Manual alert scan and status endpoints."""

from fastapi import APIRouter

from ...alerts.service import alert_service

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("/status")
async def alert_status():
    return alert_service.status()


@router.post("/scan")
async def scan_alerts():
    return await alert_service.scan_once()
