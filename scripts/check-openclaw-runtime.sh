#!/usr/bin/env sh
set -eu

SERVICE="${1:-ag-o1}"

echo "[check-openclaw] service=${SERVICE}"

docker compose ps "${SERVICE}"

echo "[check-openclaw] checking backend and strict env ..."
docker compose exec -T "${SERVICE}" sh -lc '
  set -eu
  echo "AGENT_BACKEND=${AGENT_BACKEND:-}"
  echo "AGENT_STRICT_BACKEND_SDK=${AGENT_STRICT_BACKEND_SDK:-}"
  test "${AGENT_BACKEND:-}" = "openclaw"
  test "${AGENT_STRICT_BACKEND_SDK:-}" = "1"
'

echo "[check-openclaw] checking gateway command ..."
docker compose exec -T "${SERVICE}" sh -lc '
  set -eu
  if command -v openclaw >/dev/null 2>&1; then
    command -v openclaw
  elif [ -n "${OPENCLAW_GATEWAY_CMD:-}" ]; then
    echo "OPENCLAW_GATEWAY_CMD=${OPENCLAW_GATEWAY_CMD}"
  else
    echo "No openclaw binary and no OPENCLAW_GATEWAY_CMD configured" >&2
    exit 1
  fi
'

echo "[check-openclaw] checking openclaw-sdk import ..."
docker compose exec -T "${SERVICE}" python3 - <<'PY'
from openclaw_sdk import OpenClawClient
print("openclaw_sdk import ok")
print("OpenClawClient:", OpenClawClient)
PY

echo "[check-openclaw] checking gateway port ..."
docker compose exec -T "${SERVICE}" python3 - <<'PY'
import os
import socket

host = os.environ.get("OPENCLAW_GATEWAY_HOST", "127.0.0.1")
port = int(os.environ.get("OPENCLAW_GATEWAY_PORT", "18789"))
with socket.create_connection((host, port), timeout=3):
    print(f"gateway port open: {host}:{port}")
PY

echo "[check-openclaw] checking HTTP status endpoint ..."
curl -fsS "http://localhost:8000/status" | python3 -m json.tool

echo "[check-openclaw] ensuring logs do not show direct LLM fallback ..."
if docker compose logs --no-color "${SERVICE}" | grep -Ei 'openclaw-direct-llm|direct_llm|fallback'; then
  echo "Found direct LLM/fallback markers in ${SERVICE} logs" >&2
  exit 1
fi

echo "[check-openclaw] recent OpenCLAW logs:"
docker compose logs --no-color --tail=120 "${SERVICE}" | grep -Ei 'openclaw|gateway|sdk|Agent OpenCLAW' || true

echo "[check-openclaw] OK: strict OpenCLAW runtime checks passed."
