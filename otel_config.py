"""
OpenTelemetry configuration: trace provider with OTLP export to Jaeger.
"""
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME


def configure_otel():
    """Configure OTLP trace exporter (Jaeger)."""
    resource = Resource.create({
        SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "docker-lab-flask"),
    })
    provider = TracerProvider(resource=resource)
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4318")
    exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return trace.get_tracer(__name__, "1.0.0")
