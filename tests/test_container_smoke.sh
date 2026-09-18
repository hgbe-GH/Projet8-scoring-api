#!/usr/bin/env bash
set -euo pipefail

image_name="projet8-scoring-api:test"
container_name="projet8-scoring-api-smoke"
container_port="8000"
exposed_port="$container_port/tcp"

cleanup() {
  docker rm -f "$container_name" >/dev/null 2>&1 || true
}

trap cleanup EXIT

docker build -t "$image_name" .
docker run --rm -d --name "$container_name" \
  -p "127.0.0.1::$container_port" "$image_name"
host_port="$(
  docker inspect \
    --format "{{(index (index .NetworkSettings.Ports \"$exposed_port\") 0).HostPort}}" \
    "$container_name"
)"

for attempt in {1..20}; do
  if curl --fail --silent "http://127.0.0.1:$host_port/health"; then
    exit 0
  fi
  sleep 1
done

exit 1
