from fastapi import APIRouter
from app.config import settings

router = APIRouter()


@router.get("/", summary="Liveness probe")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION, "env": settings.APP_ENV}


@router.get("/ready", summary="Readiness probe")
async def ready():
    return {"status": "ready"}
