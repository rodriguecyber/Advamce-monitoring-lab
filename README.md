# Advanced Observability & Distributed Tracing

Flask app with **OpenTelemetry**, **Prometheus**, **Grafana**, and **Jaeger**: custom RED metrics, structured logs with trace correlation, and distributed tracing. Alerts and dashboards link latency spikes and errors to traces and logs for root cause analysis.

---

## Quick start

```bash
docker compose up -d
```

| Service    | URL                    | Credentials   |
|-----------|------------------------|---------------|
| App       | http://localhost:5000  | —             |
| Grafana   | http://localhost:3000  | admin / admin |
| Prometheus| http://localhost:9090  | —             |
| Jaeger UI | http://localhost:16686 | —             |

- **Grafana:** Dashboards → open **Flask App - Observability (RED + Traces)**.
- **Jaeger:** Service = `docker-lab-flask`.

---

## Architecture

```
                    ┌─────────────┐
                    │   Client    │
                    └──────┬──────┘
                           │ HTTP
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  Flask app (:5000)                                            │
│  • OpenTelemetry (Flask + Requests) → spans                   │
│  • RED metrics → /metrics                                     │
│  • JSON logs (stdout) with trace_id / span_id                 │
└──────┬─────────────────────────────┬─────────────────────────┘
       │ OTLP HTTP                    │ scrape
       ▼                              ▼
┌─────────────┐                 ┌─────────────┐
│   Jaeger    │                 │ Prometheus  │
│   :4318     │                 │   :9090     │
└──────┬──────┘                 └──────┬──────┘
       │                                │ query
       │                                ▼
       │                         ┌─────────────┐
       │                         │   Grafana   │
       └─────────────────────────│   :3000     │
            (trace link)         └─────────────┘
```

- **Traces:** App → OTLP → Jaeger.
- **Metrics:** App `/metrics` ← Prometheus ← Grafana.
- **Logs:** App stdout (JSON); ship to CloudWatch/Loki and search by `trace_id`.

---

## Project layout

```
docker-lab/
├── app.py                      # Flask + OTel + RED metrics + JSON logs
├── otel_config.py              # TracerProvider, OTLP exporter → Jaeger
├── logging_config.py           # JSON formatter, trace_id/span_id in logs
├── requirements.txt
├── Dockerfile
├── docker-compose.yml          # app, Jaeger, Prometheus, Grafana
├── prometheus/
│   ├── prometheus.yml          # Scrape app:5000/metrics, load alerts
│   └── alerts.yml              # HighErrorRate (>5%), HighLatency (p99 >300ms, 10m)
├── grafana/
│   ├── dashboards/
│   │   └── observability.json  # RED panels + Jaeger link
│   └── provisioning/
│       ├── datasources/        # Prometheus datasource
│       └── dashboards/         # Load dashboards from dir
├── scripts/
│   └── validate_observability.sh   # Simulate load + errors
├── screenshots/                # Grafana, Jaeger, logs, alerts (for submission)
├── docs/
│   └── COMPONENTS.md           # Detailed component reference
└── REPORT.md                   # 2-page symptom → trace → root cause report
```

---

## Features

| Area | Implementation |
|------|----------------|
| **Tracing** | OpenTelemetry: Flask (server), Requests (client). OTLP HTTP to Jaeger. |
| **RED metrics** | `http_requests_total`, `http_errors_total`, `http_request_duration_seconds`; exposed at `/metrics`. |
| **Logs** | JSON to stdout with `trace_id` and `span_id` for correlation in CloudWatch/Loki. |
| **Alerts** | Error rate >5% or p99 latency >300ms for 10 minutes (Prometheus). |
| **Dashboard** | Request rate, error rate, latency (p50/p95/p99), link to Jaeger, correlation notes. |

---

## Configuration

### App (env)

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://jaeger:4318` | Jaeger OTLP HTTP base URL. |
| `OTEL_SERVICE_NAME` | `docker-lab-flask` | Service name in traces. |
| `ENABLE_TEST_ROUTES` | `0` | `1` = enable `/simulate-error`, `/simulate-slow` (disable in production). |
| `SIMULATE_SLOW_MS` | `400` | Delay in ms for `/simulate-slow`. |
| `OTEL_HTTP_CLIENT_DEMO` | — | Set to `1` to trigger outbound HTTP span from `/`. |

### Production

- Set `ENABLE_TEST_ROUTES=0` (or unset) so `/simulate-error` and `/simulate-slow` return 404.
- Point `OTEL_EXPORTER_OTLP_ENDPOINT` at your Jaeger/OTLP collector.
- Adjust Prometheus `scrape_configs` if the app runs elsewhere (e.g. ECS/EC2).

---

## Validation (alert → trace → log)

1. **Enable test routes and run stack:**
   ```bash
   ENABLE_TEST_ROUTES=1 docker compose up -d
   ```

2. **Generate load and errors:**
   ```bash
   bash scripts/validate_observability.sh http://localhost:5000
   ```

3. **Wait** ~5–10 minutes for rates to stabilize and alerts to evaluate.

4. **Confirm correlation:**
   - **Prometheus** (Alerts): HighErrorRate or HighLatency firing.
   - **Grafana**: See spike in error rate or p99 latency.
   - **Jaeger**: Search service `docker-lab-flask`, pick a trace, copy `trace_id`.
   - **Logs**: Search by that `trace_id` (e.g. in CloudWatch or container logs) to see the same request.

5. **Document:** Fill `REPORT.md` and add screenshots under `screenshots/`.

---

## Endpoints

| Path | Description |
|------|-------------|
| `/` | Hello response; optional HTTP client span if `OTEL_HTTP_CLIENT_DEMO=1`. |
| `/health` | `{"status":"ok"}`. |
| `/metrics` | Prometheus exposition format (RED metrics). |
| `/simulate-error` | Returns 500 (only if `ENABLE_TEST_ROUTES=1`). |
| `/simulate-slow` | Sleeps then 200 (only if test routes enabled). |

---

## Deliverables (submission)

| Item | Location |
|------|----------|
| App + instrumentation | `app.py`, `otel_config.py`, `logging_config.py` |
| Prometheus config | `prometheus/prometheus.yml`, `prometheus/alerts.yml` |
| Grafana dashboard | `grafana/dashboards/observability.json` |
| Jaeger | `docker-compose.yml` (all-in-one); OTLP on 4318 |
| Screenshots | `screenshots/` (Grafana, Jaeger, logs, alert) |
| Report | `REPORT.md` (symptom → trace → root cause) |

**Evidence:** Alert firing → open trace in Jaeger → search logs by `trace_id` → identify root cause.

---

## Dependencies

- **Python:** Flask, requests, `prometheus-client`, OpenTelemetry SDK + Flask/Requests instrumentors + OTLP HTTP exporter.
- **Stack:** Jaeger (all-in-one), Prometheus, Grafana; optional CloudWatch/Loki for log aggregation.

For per-component details, see **`docs/COMPONENTS.md`**.
