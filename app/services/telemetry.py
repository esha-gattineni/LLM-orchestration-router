"""Optional Application Insights logs. Telemetry failures do not break requests."""

import logging

from app.config import settings

logger = logging.getLogger(__name__)


class Telemetry:
    def __init__(self):
        self.logger = logging.getLogger("router.telemetry")
        self.logger.setLevel(logging.INFO)
        if settings.APPLICATIONINSIGHTS_CONNECTION_STRING:
            try:
                from opencensus.ext.azure.log_exporter import AzureLogHandler

                self.logger.addHandler(
                    AzureLogHandler(
                        connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING
                    )
                )
            except Exception:
                logger.warning("Application Insights initialization failed")

    def track_event(self, name, properties=None):
        try:
            self.logger.info(name, extra={"custom_dimensions": properties or {}})
        except Exception:
            logger.warning("Telemetry export failed")

    def track_metric(self, name, value, properties=None):
        self.track_event("metric", {"metric_name": name, "value": value, **(properties or {})})

    def track_exception(self, exc):
        # Log type only: provider exception messages may contain request content.
        self.track_event("exception", {"exception_type": type(exc).__name__})

    def flush(self):
        for handler in self.logger.handlers:
            try:
                handler.flush()
            except Exception:
                logger.warning("Telemetry flush failed")


_telemetry = None


def get_telemetry():
    global _telemetry
    if _telemetry is None:
        _telemetry = Telemetry()
    return _telemetry
