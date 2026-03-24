import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.services.telemetry import get_telemetry


class TelemetryMiddleware(BaseHTTPMiddleware):
    """Emits per-request duration and status metrics to Application Insights."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        t0 = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - t0) * 1000
        telemetry = get_telemetry()
        telemetry.track_metric(
            "http.request_duration_ms",
            duration_ms,
            {
                "path": request.url.path,
                "method": request.method,
                "status_code": str(response.status_code),
                "request_id": request_id,
            },
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Duration-Ms"] = str(round(duration_ms, 2))
        return response
