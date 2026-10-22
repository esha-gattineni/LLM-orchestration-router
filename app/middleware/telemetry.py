"""ASGI middleware keeps the same request ID on success and error responses."""

import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse

from app.services.telemetry import get_telemetry


class TelemetryMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        start = time.perf_counter()
        started = False

        async def send_with_id(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

    #Try method to raise exceptions
        try:
            await self.app(scope, receive, send_with_id)
        except Exception as exc:
            get_telemetry().track_exception(exc)
            if started:
                raise
            response = JSONResponse(
                {"error": "Internal server error", "request_id": request_id}, status_code=500
            )
            await response(scope, receive, send_with_id)
        finally:
            get_telemetry().track_metric(
                "http.request_duration_ms",
                (time.perf_counter() - start) * 1000,
                {"request_id": request_id, "method": scope["method"]},
            )
