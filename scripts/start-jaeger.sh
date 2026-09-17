#!/usr/bin/env bash
# Start Jaeger all-in-one with Prime's UI config (light theme, no dark toggle).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
config="$root/devtools/jaeger-ui.json"
name="${JAEGER_CONTAINER_NAME:-al-prime-jaeger}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required to start Jaeger" >&2
  exit 1
fi

docker rm -f "$name" >/dev/null 2>&1 || true
docker run --rm -d --name "$name" \
  -p 16686:16686 \
  -p 4318:4318 \
  -v "$config:/etc/jaeger/ui-config.json:ro" \
  jaegertracing/all-in-one:latest \
  --query.ui-config=/etc/jaeger/ui-config.json

echo "Jaeger UI (light): http://localhost:16686"
echo "OTLP HTTP:         http://localhost:4318"
echo "export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318"
