#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================="
echo "  AI Agent Simulation Platform - Quick Start"
echo "============================================="

# --- 1. Build frontend if not yet built ---
if [ ! -f "web/dist/index.html" ]; then
    echo "[1/4] Building frontend..."
    cd web
    npx vite build
    cd "$SCRIPT_DIR"
    echo "  Frontend build complete"
else
    echo "[1/4] Frontend already built (skip)"
fi

# --- 2. Start Message Bus ---
echo "[2/4] Starting Message Bus (port 9000)..."
python3 message_bus.py &
BUS_PID=$!
sleep 2

# --- 3. Start Main Server ---
echo "[3/4] Starting Main Server (port 8000)..."
python3 server.py &
SERVER_PID=$!
sleep 3

# --- 4. Done ---
echo "[4/4] Startup complete"
echo ""
echo "  > Console:       http://localhost:8000/"
echo "  > Tactical Map:  http://localhost:8000/tactical-map"
echo "  > API Docs:      http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop all services..."

# Trap to clean up on exit
cleanup() {
    echo ""
    echo "Stopping services..."
    kill "$BUS_PID" 2>/dev/null || true
    kill "$SERVER_PID" 2>/dev/null || true
    echo "All services stopped"
}
trap cleanup EXIT INT TERM

# Wait for both processes
wait
