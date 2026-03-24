"""
Telemetry Service — Azure Application Insights
-----------------------------------------------
Wraps opencensus-ext-azure to emit custom events, metrics, and exceptions.
Falls back gracefully to a no-op logger when the connection string is absent
(e.g., local development).
"""

import logging

from app.config import settings

logger = logging.getLogger(__name__)


class _NoOpTelemetry:
    """Fallback when Application Insights is not configured."""

    def track_event(self, name: str, properties: dict = None):
        logger.debug("[telemetry:event] %s %s", name, properties or {})

    def track_metric(self, name: str, value: float, properties: dict = None):
        logger.debug("[telemetry:metric] %s=%.4f %s", name, value, properties or {})

    def track_exception(self, exc: Exception):
        logger.exception("[telemetry:exception]", exc_info=exc)

    def flush(self):
        pass


class AppInsightsTelemetry:
    """Real Application Insights telemetry via opencensus-ext-azure."""

    def __init__(self, connection_string: str):
        from opencensus.ext.azure.log_exporter import AzureLogHandler

        self._logger = logging.getLogger("app.insights")
        self._logger.setLevel(logging.INFO)
        self._logger.addHandler(
            AzureLogHandler(connection_string=connection_string)
        )

    def track_event(self, name: str, properties: dict = None):
        self._logger.info(
            name,
            extra={"custom_dimensions": properties or {}},
        )

    def track_metric(self, name: str, value: float, properties: dict = None):
        self._logger.info(
            "metric",
            extra={"custom_dimensions": {"metric_name": name, "value": value, **(properties or {})}},
        )

    def track_exception(self, exc: Exception):
        self._logger.exception("Unhandled exception", exc_info=exc)

    def flush(self):
        for handler in self._logger.handlers:
            handler.flush()


_telemetry = None


def get_telemetry() -> _NoOpTelemetry | AppInsightsTelemetry:
    global _telemetry
    if _telemetry is None:
        cs = settings.APPLICATIONINSIGHTS_CONNECTION_STRING
        if cs:
            try:
                _telemetry = AppInsightsTelemetry(cs)
                logger.info("Application Insights telemetry initialised.")
            except Exception as e:
                logger.warning("Failed to init App Insights: %s — using no-op.", e)
                _telemetry = _NoOpTelemetry()
        else:
            _telemetry = _NoOpTelemetry()
    return _telemetry