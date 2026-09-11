import json
import logging
import os
import time
from datetime import datetime, timezone
from fastapi import FastAPI, Response


class JsonLogFormatter(logging.Formatter):
    """Minimal JSON log formatter for structured logs."""

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "service": self.service_name,
            "level": record.levelname,
            "message": record.getMessage(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(service_name: str) -> None:
    """Configure root logger with JSON output to stdout."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter(service_name))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def setup_metrics(app: FastAPI, service_name: str) -> None:
    """Attach basic Prometheus metrics and /metrics endpoint."""
    enable_metrics = os.getenv("ENABLE_METRICS", "1").lower() not in {"0", "false", "no"}
    if not enable_metrics:
        return

    from prometheus_client import Counter, Histogram, CONTENT_TYPE_LATEST, generate_latest

    request_counter = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["service", "method", "endpoint", "status"],
    )
    request_latency = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["service", "method", "endpoint"],
    )

    @app.middleware("http")
    async def _metrics_middleware(request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        endpoint = request.url.path
        request_counter.labels(
            service=service_name,
            method=request.method,
            endpoint=endpoint,
            status=response.status_code,
        ).inc()
        request_latency.labels(
            service=service_name,
            method=request.method,
            endpoint=endpoint,
        ).observe(elapsed)
        return response

    @app.get("/metrics")
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
