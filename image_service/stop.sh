#!/bin/bash
# Stop the ARPX image generation service.
# Works from any cluster node (shared filesystem).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f server.pid ]]; then
    echo "No server.pid found — service not running."
    exit 0
fi

PID=$(cat server.pid)
HOST=$(cat server.host 2>/dev/null || echo "localhost")

if [[ "$(hostname)" != "$HOST" && "$(hostname -s)" != "$HOST" ]]; then
    ssh "$HOST" "kill $PID 2>/dev/null" || true
else
    kill "$PID" 2>/dev/null || true
fi

rm -f server.pid server.port server.host
echo "Image service stopped (was PID $PID on $HOST)."
