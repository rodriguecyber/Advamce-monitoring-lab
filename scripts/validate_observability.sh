#!/usr/bin/env bash
# Simulate load and errors to validate alert → trace → log correlation.
# Run with ENABLE_TEST_ROUTES=1. Then check Grafana, Jaeger, and logs.

set -e
BASE="${1:-http://localhost:5000}"

echo "=== Sending normal traffic ==="
for i in $(seq 1 20); do curl -s -o /dev/null -w "%{http_code}" "$BASE/"; done
echo ""

echo "=== Triggering errors (5xx) ==="
for i in $(seq 1 15); do curl -s -o /dev/null -w "%{http_code}" "$BASE/simulate-error"; done
echo ""

echo "=== Triggering slow requests (>300ms) ==="
for i in $(seq 1 10); do curl -s -o /dev/null -w "%{http_code}\n" "$BASE/simulate-slow"; done

echo "=== Done. Wait ~5m for rates to stabilize, then 10m for alerts. Check: ==="
echo "  - Prometheus: http://localhost:9090 (alerts)"
echo "  - Grafana: http://localhost:3000 (admin/admin)"
echo "  - Jaeger: http://localhost:16686 (service: docker-lab-flask)"
