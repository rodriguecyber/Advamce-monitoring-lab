# Docker Lab - Python Flask Application

## Overview
A simple Python Flask web application containerized with Docker. This project demonstrates basic containerization of a Python web service and is ideal for learning Docker fundamentals.

## Project Structure
```
docker-lab/
├── app.py                    # Flask app (OTel, RED metrics, JSON logs)
├── otel_config.py            # OpenTelemetry → Jaeger (OTLP)
├── logging_config.py         # JSON logs with trace_id/span_id
├── requirements.txt
├── Dockerfile
├── docker-compose.yml        # App + Jaeger + Prometheus + Grafana
├── prometheus/
│   ├── prometheus.yml
│   └── alerts.yml            # Error rate >5%, p99 >300ms for 10m
├── grafana/
│   ├── dashboards/observability.json
│   └── provisioning/
├── scripts/validate_observability.sh
├── screenshots/              # Submission screenshots
└── REPORT.md                 # 2-page symptom → trace → root cause report
```

## Purpose
This project is a **minimal Flask web service** that:
- Runs a simple HTTP server on port 5000
- Returns "Hello from Docker!" when accessed
- Demonstrates Docker containerization of Python applications

## Key Components

### app.py
- **Framework**: Flask (lightweight Python web framework)
- **Endpoint**: Single route (`/`) that returns a greeting message
- **Server Config**: 
  - Host: `0.0.0.0` (accessible from any network interface)
  - Port: `5000`

### Dockerfile
- **Base Image**: `python:3.9-slim` - Python 3.9 with minimal dependencies
- **Working Directory**: `/app`
- **Dependencies**: Flask installed via pip
- **Exposed Port**: 5000
- **Entry Point**: Runs `python app.py`

## Usage

### Build the Docker Image
```bash
docker build -t docker-lab-flask .
```

### Run the Container
```bash
docker run -p 5000:5000 docker-lab-flask
```

### Access the Application
```bash
curl http://localhost:5000
# Output: Hello from Docker!
```

### Behind a Proxy
This application is will be used with the nginx-proxy project in the labs:
- The nginx proxy (port 80) forwards requests to this Flask app (port 5000)
- Demonstrates multi-container networking and reverse proxy patterns




## Observability (Prometheus + Grafana + Jaeger)

**Run full stack:**
```bash
docker compose up -d
```
- App: http://localhost:5000  
- Grafana: http://localhost:3000 (admin/admin)  
- Prometheus: http://localhost:9090  
- Jaeger: http://localhost:16686  

**App env (optional):**
- `OTEL_EXPORTER_OTLP_ENDPOINT` – Jaeger OTLP HTTP (default `http://jaeger:4318`)
- `OTEL_SERVICE_NAME` – service name in traces (default `docker-lab-flask`)
- `ENABLE_TEST_ROUTES=1` – enable `/simulate-error` and `/simulate-slow` for validation (set to `0` in production to remove test routes)

**Validation:** With test routes enabled, run `./scripts/validate_observability.sh` to generate errors and slow requests. After ~10m, confirm alerts in Prometheus, then in Jaeger find a trace and in logs (or stdout) search by `trace_id` for correlation. Fill `REPORT.md` and add screenshots under `screenshots/`.

---

## Dependencies
- Flask, requests
- OpenTelemetry (Flask + Requests instrumentors, OTLP exporter)
- prometheus-client
