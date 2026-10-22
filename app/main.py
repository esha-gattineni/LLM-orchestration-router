from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.middleware.telemetry import TelemetryMiddleware
from app.routers import chat, health, metrics
from app.services.telemetry import get_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_telemetry().track_event("AppStarted", {"version": settings.APP_VERSION})
    yield
    get_telemetry().track_event("AppStopped", {})
    get_telemetry().flush()


app = FastAPI(title="LLM Orchestration Router", version=settings.APP_VERSION, lifespan=lifespan)
app.add_middleware(TelemetryMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["X-Request-ID"],
)
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["Metrics"])


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(
        {"detail": exc.detail, "request_id": request.state.request_id},
        status_code=exc.status_code,
        headers=exc.headers,
    )
