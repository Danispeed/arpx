#!/bin/bash
# Open SSH tunnel from local machine to the image service on ificluster.
#
# Why this is needed:
#   n8n runs inside Docker (isolated network). It cannot reach ificluster
#   directly. This script forwards a local port through SSH so Docker can
#   reach the cluster via host.docker.internal.
#
#   Docker (n8n) → host.docker.internal:LOCAL_PORT
#                → SSH tunnel on host Mac
#                → ificluster.ifi.uit.no
#                → GPU node:REMOTE_PORT
#
# Usage (run on your local Mac, NOT on the cluster):
#   ./tunnel.sh                  # default: c6-4, local port 8765
#   ./tunnel.sh c6-8             # different GPU node
#   ./tunnel.sh c6-4 9000        # custom local port
#
# Prerequisites: image service must already be running on the GPU node.
# Run ./start.sh on the cluster first.

set -euo pipefail

GPU_NODE="${1:-c6-4}"
LOCAL_PORT="${2:-8765}"
CLUSTER_USER="${ARPX_CLUSTER_USER:-dsc019}"
CLUSTER_HOST="${ARPX_CLUSTER_HOST:-ificluster.ifi.uit.no}"
PORT_FILE="/mnt/users/$CLUSTER_USER/arpx/image_service/server.port"

echo "Fetching image service port from $GPU_NODE..."
REMOTE_PORT=$(ssh "$CLUSTER_USER@$CLUSTER_HOST" "ssh $GPU_NODE 'cat $PORT_FILE 2>/dev/null || echo MISSING'")

if [[ "$REMOTE_PORT" == "MISSING" || -z "$REMOTE_PORT" ]]; then
    echo ""
    echo "Error: image service not running on $GPU_NODE."
    echo "SSH to the cluster and run:"
    echo "  ssh $CLUSTER_USER@$CLUSTER_HOST"
    echo "  ssh $GPU_NODE"
    echo "  cd ~/arpx/image_service && source venv/bin/activate && ./start.sh $GPU_NODE"
    exit 1
fi

echo ""
echo "============================================"
echo "SSH tunnel open"
echo "  Cluster node : $GPU_NODE:$REMOTE_PORT"
echo "  Local port   : $LOCAL_PORT"
echo ""
echo "Set in n8n CallClusterAPI node URL:"
echo "  http://host.docker.internal:$LOCAL_PORT/generate"
echo ""
echo "Press Ctrl+C to close tunnel"
echo "============================================"

ssh -N -L "$LOCAL_PORT:$GPU_NODE.ifi.uit.no:$REMOTE_PORT" "$CLUSTER_USER@$CLUSTER_HOST"
