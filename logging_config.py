"""
Structured JSON logging with trace_id and span_id for log correlation.
"""
import json
import logging
import sys
from opentelemetry import trace


class TraceContextFilter(logging.Filter):
    """Inject trace_id and span_id into log records from current OTel context."""

    def filter(self, record):
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
        else:
            record.trace_id = ""
            record.span_id = ""
        return True


class JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON for CloudWatch/Loki."""

    def format(self, record):
        log = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "trace_id") and record.trace_id:
            log["trace_id"] = record.trace_id
        if hasattr(record, "span_id") and record.span_id:
            log["span_id"] = record.span_id
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log)


def setup_logging(level=logging.INFO):
    """Configure root logger with JSON output and trace context."""
    root = logging.getLogger()
    root.setLevel(level)
    if root.handlers:
        for h in root.handlers[:]:
            root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(TraceContextFilter())
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    return root
