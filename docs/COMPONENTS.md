# Observability Setup — Component Reference

Detailed explanation of every component in the Prometheus + Grafana + Jaeger + OpenTelemetry stack.

---

## 1. Flask application (`app.py`)

### Role
The instrumented web app: serves traffic, emits RED metrics, writes structured logs, and produces traces.

### Initialization order
1. **`setup_logging()`** — Configures JSON logging with trace context *before* any request is handled.
2. **`configure_otel()`** — Sets up the OpenTelemetry tracer and OTLP exporter so all spans use the same provider.
3. **Flask app** — Created and then wrapped by **FlaskInstrumentor** and **RequestsInstrumentor** so that HTTP server and client calls are auto-traced.

### Instrumentation

| Layer | Library | What it does |
|-------|--------|---------------|
| **HTTP server** | `opentelemetry-instrumentation-flask` | Wraps each incoming request in a span; sets `http.method`, `http.route`, `http.status_code`, URL. |
| **HTTP client** | `opentelemetry-instrumentation-requests` | Wraps `requests.get/post/...` in child spans; adds target URL, method, status. |

So: every request to the app is a root span; any outbound `requests` call (e.g. when `OTEL_HTTP_CLIENT_DEMO=1` on `/`) is a child span in the same trace.

### RED metrics (Prometheus)

Defined with `prometheus_client` and updated in `after_request`:

| Metric | Type | Labels | Meaning |
|--------|------|--------|---------|
| **`http_requests_total`** | Counter | `method`, `endpoint`, `status` | Total requests; **rate** = requests/sec (R in RED). |
| **`http_errors_total`** | Counter | `method`, `endpoint` | Total 5xx responses; **rate** = error rate (E in RED). |
| **`http_request_duration_seconds`** | Histogram | `method`, `endpoint` | Request duration; **quantiles** = latency (D in RED). |

- **`endpoint`** = `request.endpoint` (e.g. `home`, `health`, `simulate_error`) or path/`unknown`.
- **`before_request`** stores `request._start_time`; **`after_request`** computes duration and calls `REQUEST_LATENCY.observe(duration)`.

### Endpoints

| Path | Purpose |
|------|--------|
| `/` | Main response; optionally calls `/health` via `requests` if `OTEL_HTTP_CLIENT_DEMO=1`. |
| `/health` | Liveness/readiness; returns `{"status":"ok"}`. |
| `/metrics` | Prometheus scrape endpoint; returns Prometheus text exposition format. |
| `/simulate-error` | Returns 500; only if `ENABLE_TEST_ROUTES=1` (else 404). |
| `/simulate-slow` | Sleeps `SIMULATE_SLOW_MS` (default 400) then 200; only if test routes enabled. |

### Logging
Each request logs one JSON line in **`after_request`** with `logger.info("request completed", extra={...})`. The logging pipeline (see **logging_config.py**) adds **`trace_id`** and **`span_id`** so logs can be correlated with Jaeger traces.

---

## 2. OpenTelemetry config (`otel_config.py`)

### Role
Configures the global **TracerProvider** and sends spans to Jaeger via **OTLP over HTTP**.

### Pieces

- **Resource**  
  Identifies the service: `service.name` = `OTEL_SERVICE_NAME` (default `docker-lab-flask`). Shows up in Jaeger as the service name.

- **TracerProvider**  
  The SDK object that creates tracers and holds the span processor.

- **OTLPSpanExporter**  
  Sends spans to `OTEL_EXPORTER_OTLP_ENDPOINT/v1/traces` (e.g. `http://jaeger:4318/v1/traces`). Uses OTLP HTTP/protobuf (not gRPC).

- **BatchSpanProcessor**  
  Buffers spans and exports in batches to reduce overhead and network calls.

### Env vars

| Variable | Default | Purpose |
|----------|---------|---------|
| `OTEL_SERVICE_NAME` | `docker-lab-flask` | Service name in traces and Jaeger UI. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://jaeger:4318` | Base URL for OTLP HTTP (no `/v1/traces`; the code appends it). |

---

## 3. Logging config (`logging_config.py`)

### Role
Makes application logs **structured JSON** and adds **trace_id** and **span_id** from the active OpenTelemetry span so logs can be tied to traces (e.g. in CloudWatch or Loki).

### TraceContextFilter
- Runs on every log record.
- Calls **`trace.get_current_span()`** and **`span.get_span_context()`**.
- If the context is valid, sets **`record.trace_id`** and **`record.span_id`** as hex strings (32 and 16 chars).
- These are the same IDs Jaeger shows; you can search logs by `trace_id` to get all log lines for a request.

### JsonFormatter
- Builds a single JSON object per log line: `timestamp`, `level`, `logger`, `message`, optional `trace_id`/`span_id`, optional `exception`.
- One line per record, so log aggregators (CloudWatch, Loki, etc.) can index and search by `trace_id`/`span_id`.

### setup_logging()
- Sets the root logger level.
- Replaces handlers with one **StreamHandler** to stdout.
- Adds **TraceContextFilter** and **JsonFormatter** so all log records go through them.

---

## 4. Prometheus config (`prometheus/prometheus.yml`)

### Role
Tells Prometheus what to scrape and which alert rules to evaluate.

### Sections

- **global**  
  - `scrape_interval: 15s` — default interval between scrapes.  
  - `evaluation_interval: 15s` — how often to run alert rules.

- **alerting**  
  - Placeholder for Alertmanager; `targets: []` means no alerts are sent anywhere until you add an Alertmanager.

- **rule_files**  
  - Loads **`alerts.yml`** so the HighErrorRate and HighLatency rules are active.

- **scrape_configs**  
  - **job_name: "flask-app"**  
  - **targets: ["app:5000"]** — in Docker Compose, `app` is the Flask service hostname.  
  - **metrics_path: /metrics** — Prometheus calls `http://app:5000/metrics`.  
  - **scrape_interval: 10s** — override for this job (more frequent than global).

---

## 5. Alert rules (`prometheus/alerts.yml`)

### Role
Define when Prometheus should consider the app “unhealthy” and set alert state to firing.

### Group: `flask-app-alerts`

**Rule 1: HighErrorRate**
- **Expr:** `(sum(rate(http_errors_total[5m])) by (endpoint) / sum(rate(http_requests_total[5m])) by (endpoint)) > 0.05`
- **Meaning:** For each `endpoint`, error rate over the last 5 minutes &gt; 5%.
- **For:** 10m — condition must hold for 10 minutes before firing.
- **Labels:** `severity: warning`.
- **Annotations:** Summary and description include `endpoint` and current value.

**Rule 2: HighLatency**
- **Expr:** `histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint)) > 0.3`
- **Meaning:** For each `endpoint`, p99 latency over the last 5 minutes &gt; 0.3 s (300 ms).
- **For:** 10m — must stay above threshold for 10 minutes.
- **Labels/annotations:** Same idea as HighErrorRate.

Prometheus evaluates these every `evaluation_interval`; when the expression is true for 10m, the alert goes to “firing” and (if configured) can be sent to Alertmanager.

---

## 6. Docker Compose (`docker-compose.yml`)

### Services

| Service | Image / build | Purpose |
|---------|----------------|---------|
| **app** | `build: .` (Dockerfile) | Flask app with OTel, RED metrics, JSON logs. Exposes 5000. |
| **jaeger** | `jaegertracing/all-in-one:1.52` | All-in-one Jaeger: collector + query + UI. Accepts OTLP on 4317 (gRPC) and 4318 (HTTP). |
| **prometheus** | `prom/prometheus:v2.47.0` | Scrapes `app:5000/metrics`, evaluates `alerts.yml`. |
| **grafana** | `grafana/grafana:10.2.0` | Dashboards and (optionally) alerting; uses provisioned Prometheus datasource. |

### Networking
- All share the default Compose network; **app** and **prometheus** resolve **app**, **jaeger**, **prometheus**, **grafana** by service name.
- **app** sets `OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318` so traces go to Jaeger.
- **prometheus** scrapes **app:5000**; **grafana** talks to **prometheus:9090** via provisioning.

### Ports (host)

| Port | Service | Use |
|------|---------|-----|
| 5000 | app | HTTP API and /metrics. |
| 3000 | grafana | Web UI. |
| 9090 | prometheus | Prometheus UI and API. |
| 16686 | jaeger | Jaeger UI. |
| 4317 / 4318 | jaeger | OTLP gRPC / HTTP (for other clients if needed). |

### App env in Compose
- **OTEL_EXPORTER_OTLP_ENDPOINT**, **OTEL_SERVICE_NAME** — OTel (see §2).
- **ENABLE_TEST_ROUTES=1** — turns on `/simulate-error` and `/simulate-slow` for validation; set to `0` or remove in production.

---

## 7. Grafana datasource provisioning (`grafana/provisioning/datasources/datasources.yml`)

### Role
Automatically add a Prometheus datasource when Grafana starts so dashboards can query metrics without manual setup.

### Content
- **name: Prometheus** — name in the UI.
- **type: prometheus**
- **url: http://prometheus:9090** — Prometheus HTTP API from inside Docker.
- **isDefault: true** — new panels use this by default.
- **editable: false** — prevents accidental changes in the UI.

Grafana reads this from **GF_PATHS_PROVISIONING** (e.g. `/etc/grafana/provisioning`); the Compose volume mounts the repo’s `provisioning/datasources` there.

---

## 8. Grafana dashboard provisioning (`grafana/provisioning/dashboards/dashboard.yml`)

### Role
Tells Grafana to load dashboard JSON files from a directory so the observability dashboard appears without import.

### Content
- **provider type: file**
- **path: /var/lib/grafana/dashboards** — directory to scan for JSON.
- **updateIntervalSeconds: 30** — rescan for new/updated dashboards.
- **allowUiUpdates: true** — changes in the UI can be saved (optional; can set false for immutable config).

Compose mounts **./grafana/dashboards** at **/var/lib/grafana/dashboards**, so **observability.json** in that folder is loaded.

---

## 9. Grafana dashboard (`grafana/dashboards/observability.json`)

### Role
Single dashboard for RED metrics, latency vs alert threshold, and a link to Jaeger for trace → log correlation.

### Dashboard-level settings
- **refresh: 10s** — auto-refresh.
- **time:** last 1 hour; timezone from browser.
- **link:** “Jaeger” → `http://localhost:16686/search?service=docker-lab-flask` (for the user’s browser).

### Panels

| Panel | Query / content | Purpose |
|-------|------------------|---------|
| **Request rate (RED - Rate)** | `sum(rate(http_requests_total[5m])) by (endpoint, status)` | Requests per second by endpoint and status. |
| **Error rate (RED - Errors)** | `sum(rate(http_errors_total[5m])) by (endpoint) / sum(rate(http_requests_total[5m])) by (endpoint)` | Fraction of requests that are 5xx; threshold line at 5%. |
| **Latency (RED - Duration)** | `histogram_quantile(0.50/0.95/0.99, sum(rate(..._bucket[5m])) by (le, endpoint))` | p50, p95, p99 latency by endpoint. |
| **p99 Latency (alert threshold 300ms)** | Same p99 query; threshold at 0.3 s | Highlights when the latency alert would fire. |
| **Trace & log correlation** | Markdown text | Instructions: use Jaeger, copy `trace_id`, search logs. |

All panels use the default Prometheus datasource (provisioned above). The dashboard UID is **flask-observability** so it can be linked or overwritten on re-import.

---

## 10. End-to-end data flow

```
[Client] → HTTP → [Flask app]
                    │
                    ├─ FlaskInstrumentor → span per request
                    ├─ before_request → _start_time
                    ├─ route handler (optional: RequestsInstrumentor → child span on requests.get)
                    ├─ after_request → RED metrics (Counter/Histogram), one log line (with trace_id/span_id)
                    │
                    ├─ /metrics ← [Prometheus] scrapes every 10s
                    │                  │
                    │                  ├─ stores series, evaluates alerts (alerts.yml)
                    │                  └─ [Grafana] queries Prometheus, shows dashboard
                    │
                    └─ OTLP (BatchSpanProcessor) → [Jaeger] (HTTP :4318)
                                                         │
                                                         └─ UI :16686 — search by service / trace_id
```

**Correlation:** When an alert fires (e.g. HighErrorRate or HighLatency), you open Jaeger for that time range and service, find a trace, copy **trace_id**, then search logs (CloudWatch/Loki or container stdout) for that **trace_id** to see the exact log lines for that request and identify root cause.

---

## 11. Files not covered above

- **requirements.txt** — Python deps: Flask, OpenTelemetry packages, prometheus-client, requests.
- **Dockerfile** — Builds app image: install deps from requirements.txt, copy app code, run `python app.py`.
- **scripts/validate_observability.sh** — Sends normal traffic plus calls to `/simulate-error` and `/simulate-slow` to trigger errors and latency for validation.
- **screenshots/README.md** — What screenshots to capture (Grafana, Jaeger, logs, alerts).
- **REPORT.md** — Template for the 2-page symptom → trace → root cause report.

These support the components above; the core behavior is in the sections 1–9 and the flow in §10.
