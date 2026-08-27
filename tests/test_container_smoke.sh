#!/usr/bin/env bash
set -euo pipefail

image_name="projet8-scoring-api:test"
container_name="projet8-scoring-api-smoke"

cleanup() {
  docker rm -f "$container_name" >/dev/null 2>&1 || true
}

trap cleanup EXIT

docker build -t "$image_name" .
docker run --rm -d --name "$container_name" -p 8000:8000 "$image_name"

for attempt in {1..20}; do
  if curl --fail --silent http://127.0.0.1:8000/health; then
    exit 0
  fi
  sleep 1
done

exit 1
