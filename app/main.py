import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.middleware.telemetry import TelemetryMiddleware
from app.routers import chat, health, metrics
from app.services.telemetry import get_telemetry
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    telemetry = get_telemetry()
    telemetry.track_event("AppStarted", {"version": settings.APP_VERSION})
    yield
    telemetry.track_event("AppStopped", {})


app = FastAPI(
    title="LLM Orchestration Platform",
    description="Intelligent routing layer between GPT-4 and Claude based on query complexity, latency budget, and token cost.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TelemetryMiddleware)

app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["Metrics"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    telemetry = get_telemetry()
    telemetry.track_exception(exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "request_id": str(uuid.uuid4())},
    )