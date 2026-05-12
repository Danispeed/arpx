#!/bin/bash
# Start the ARPX image generation service on a GPU node.
#
# Usage:
#   ./start.sh              # default: c6-4, auto port
#   ./start.sh c6-8         # specific node, auto port
#   ./start.sh c6-4 9090    # specific node and port
#
# Run from ificluster frontend or directly on a GPU node.
# Uses shared filesystem — PID/port files readable from any node.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GPU_NODE="${1:-c6-4}"
PREFERRED_PORT="${2:-0}"

# If not on the target GPU node, SSH there and re-run
if [[ "$(hostname)" != "$GPU_NODE" ]]; then
    exec ssh "$GPU_NODE" "cd '$SCRIPT_DIR' && bash start.sh '$GPU_NODE' '$PREFERRED_PORT'"
fi

cd "$SCRIPT_DIR"

# Check for existing running instance
if [[ -f server.pid ]] && kill -0 "$(cat server.pid)" 2>/dev/null; then
    echo "Service already running (PID $(cat server.pid)) on port $(cat server.port)."
    echo "  URL: http://$(hostname):$(cat server.port)"
    echo "Run ./stop.sh first to restart."
    exit 1
fi

# Activate venv
if [[ ! -d venv ]]; then
    echo "Error: venv not found. Run setup first (see README.md)."
    exit 1
fi
source venv/bin/activate

# Find free port
if [[ "$PREFERRED_PORT" == "0" ]]; then
    PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()")
else
    PORT="$PREFERRED_PORT"
fi

export HF_HOME="${HF_HOME:-$HOME/hf_cache}"

nohup uvicorn server:app --host 0.0.0.0 --port "$PORT" > server.log 2>&1 &
echo $! > server.pid
echo "$PORT" > server.port
echo "$(hostname)" > server.host

echo "============================================"
echo "ARPX Image Service started"
echo "  Node: $(hostname)"
echo "  Port: $PORT"
echo "  PID:  $(cat server.pid)"
echo "  Log:  $SCRIPT_DIR/server.log"
echo ""
echo "  URL:  http://$(hostname):$PORT"
echo ""
echo "Set in n8n (Settings > Variables):"
echo "  IMAGE_SERVICE_URL = http://$(hostname):$PORT"
echo "============================================"
