"""
Flask app with OpenTelemetry tracing, RED metrics, and structured logging.
"""
import os
import time
import logging
from flask import Flask

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

from otel_config import configure_otel
from logging_config import setup_logging

# Logging and OTel must run before app routes
setup_logging()
tracer = configure_otel()

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

logger = logging.getLogger(__name__)

# RED metrics: Rate, Errors, Duration
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
ERROR_COUNT = Counter(
    "http_errors_total",
    "Total HTTP errors (5xx)",
    ["method", "endpoint"],
)


@app.after_request
def after_request(response):
    """Record RED metrics and log with trace context after each request."""
    from flask import request
    endpoint = request.endpoint or request.path or "unknown"
    method = request.method
    status = response.status_code
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
    if 500 <= status < 600:
        ERROR_COUNT.labels(method=method, endpoint=endpoint).inc()
    # Latency is tracked via middleware; we use request start time if stored
    if hasattr(request, "_start_time"):
        duration = time.perf_counter() - request._start_time
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)
    logger.info(
        "request completed",
        extra={
            "method": method,
            "path": request.path,
            "status": status,
        },
    )
    return response


@app.before_request
def before_request():
    from flask import request
    request._start_time = time.perf_counter()


@app.route("/")
def home():
    # Optional outbound call to generate HTTP client spans (for demo)
    if os.getenv("OTEL_HTTP_CLIENT_DEMO"):
        import requests
        requests.get("http://localhost:5000/health", timeout=1)
    return "Hello from Docker!"


@app.route("/health")
def health():
    return {"status": "ok"}, 200


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


# Validation-only routes (disable in production via ENABLE_TEST_ROUTES=0)
def _test_routes_enabled():
    return os.getenv("ENABLE_TEST_ROUTES", "0").strip().lower() in ("1", "true", "yes")


@app.route("/simulate-error")
def simulate_error():
    if not _test_routes_enabled():
        return "Not found", 404
    logger.warning("simulated error", extra={"route": "simulate_error"})
    return "Intentional error", 500


@app.route("/simulate-slow")
def simulate_slow():
    if not _test_routes_enabled():
        return "Not found", 404
    delay = float(os.getenv("SIMULATE_SLOW_MS", "400")) / 1000.0
    time.sleep(delay)
    return f"Delayed {delay}s", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
