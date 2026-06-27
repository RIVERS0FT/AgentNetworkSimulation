#!/usr/bin/env sh
set -eu

: "${OPENCLAW_START_GATEWAY:=1}"
: "${OPENCLAW_GATEWAY_HOST:=127.0.0.1}"
: "${OPENCLAW_GATEWAY_PORT:=18789}"
: "${OPENCLAW_GATEWAY_WS_URL:=ws://${OPENCLAW_GATEWAY_HOST}:${OPENCLAW_GATEWAY_PORT}/gateway}"
: "${OPENCLAW_GATEWAY_READY_TIMEOUT:=60}"

export OPENCLAW_GATEWAY_WS_URL

echo "[openclaw-agent] OPENCLAW_GATEWAY_WS_URL=${OPENCLAW_GATEWAY_WS_URL}"

if [ "${OPENCLAW_START_GATEWAY}" = "1" ]; then
    if [ -n "${OPENCLAW_GATEWAY_CMD:-}" ]; then
        gateway_cmd="${OPENCLAW_GATEWAY_CMD}"
    elif command -v openclaw >/dev/null 2>&1; then
        gateway_cmd="openclaw gateway --host ${OPENCLAW_GATEWAY_HOST} --port ${OPENCLAW_GATEWAY_PORT}"
    else
        echo "[openclaw-agent] ERROR: OPENCLAW_START_GATEWAY=1 but no OpenCLAW gateway command was found." >&2
        echo "[openclaw-agent] Install the OpenCLAW gateway runtime into this image, or set OPENCLAW_GATEWAY_CMD." >&2
        echo "[openclaw-agent] To use an external gateway instead, set OPENCLAW_START_GATEWAY=0 and OPENCLAW_GATEWAY_WS_URL." >&2
        exit 1
    fi

    echo "[openclaw-agent] starting OpenCLAW gateway: ${gateway_cmd}"
    sh -c "${gateway_cmd}" &
    gateway_pid="$!"

    echo "[openclaw-agent] waiting for gateway on ${OPENCLAW_GATEWAY_HOST}:${OPENCLAW_GATEWAY_PORT} ..."
    python3 - <<'PY'
import os
import socket
import sys
import time

host = os.environ.get("OPENCLAW_GATEWAY_HOST", "127.0.0.1")
port = int(os.environ.get("OPENCLAW_GATEWAY_PORT", "18789"))
timeout = int(os.environ.get("OPENCLAW_GATEWAY_READY_TIMEOUT", "60"))
deadline = time.time() + timeout

while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=1):
            print("[openclaw-agent] gateway port is open")
            sys.exit(0)
    except OSError:
        time.sleep(1)

print(f"[openclaw-agent] gateway did not become ready at {host}:{port}", file=sys.stderr)
sys.exit(1)
PY
else
    echo "[openclaw-agent] OPENCLAW_START_GATEWAY=0; using configured gateway URL only."
fi

term_children() {
    if [ -n "${gateway_pid:-}" ]; then
        kill "${gateway_pid}" 2>/dev/null || true
    fi
}
trap term_children INT TERM EXIT

echo "[openclaw-agent] starting AgentNetwork server..."
exec python3 services/agent_server.py
