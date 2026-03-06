# Observability & Distributed Tracing – Report (2 pages)

## 1. Architecture and Instrumentation

**Stack:** Flask app + OpenTelemetry (OTLP) → Jaeger; RED metrics → Prometheus; dashboards & alerts in Grafana; structured JSON logs with `trace_id`/`span_id` for CloudWatch or Loki.

**Instrumentation:**
- **HTTP server:** OpenTelemetry Flask instrumentor; each request is a span with `http.route`, `http.method`, `http.status_code`.
- **HTTP client:** `opentelemetry-instrumentation-requests`; outbound calls (e.g. to `/health`) produce child spans when `OTEL_HTTP_CLIENT_DEMO=1`.
- **RED metrics:** `http_requests_total` (rate), `http_errors_total` (errors), `http_request_duration_seconds` (duration); exposed at `/metrics` for Prometheus.
- **Logs:** JSON with `timestamp`, `level`, `message`, `trace_id`, `span_id` so logs can be correlated with traces.

**Alert rules (Prometheus):**
- **HighErrorRate:** `(sum(rate(http_errors_total[5m])) / sum(rate(http_requests_total[5m]))) > 0.05` for 10m.
- **HighLatency:** `histogram_quantile(0.99, ...) > 0.3` (p99 > 300ms) for 10m.

---

## 2. Symptom → Trace → Root Cause (Example)

| Step | Observation | Action |
|------|-------------|--------|
| **Symptom** | Grafana shows error rate >5% or latency panel shows p99 >300ms; Prometheus alert fires. | Note alert time window (e.g. 14:00–14:10). |
| **Trace** | Open Jaeger, filter by service `docker-lab-flask` and time range. Find slow or failed requests; open trace and copy `trace_id`. | Identify failing or slow span (e.g. `GET /simulate-error` or `GET /simulate-slow`). |
| **Log** | In CloudWatch or Loki, search for `trace_id:<id>`. Log lines with that `trace_id` (and optional `span_id`) show the same request. | Correlate with trace to see log messages and stack/context for root cause. |
| **Root cause** | e.g. “Intentional 500 from `/simulate-error`” or “Sleep 400ms in `/simulate-slow`”. | Fix or remove test routes; scale or optimize the real dependency. |

**Validation:** With `ENABLE_TEST_ROUTES=1`, call `/simulate-error` and `/simulate-slow` under load. Confirm alert fires, then in Jaeger find the trace and in logs search by `trace_id` to complete the chain: **alert → trace → log → root cause**.

---

*Screenshots to attach: Grafana dashboard (RED + latency), Jaeger trace view, sample JSON log line with trace_id/span_id, Prometheus alert (firing).*
