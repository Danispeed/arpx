# ARPX Image Service

FastAPI service for generating visual analogy images using FLUX.1 Schnell.
Runs on a UiT ificluster GPU node — outside the Docker stack.

## Architecture

```
Docker stack (app + weaviate + n8n)
  └── n8n: CallClusterAPI node
        ↓  http://host.docker.internal:8765/generate
SSH tunnel  (tunnel.sh)
        ↓  forwarded through ificluster
GPU node (c6-4, c6-8, etc.)
  └── uvicorn server:app  →  FLUX.1 Schnell  →  base64 PNG
```

The Docker network has no direct route to ificluster. `tunnel.sh` forwards
a local port through SSH so n8n can reach the service via `host.docker.internal`.

---

## Setup

### One-time (per GPU node)

SSH to a GPU node and install dependencies:

```bash
ssh dsc019@ificluster.ifi.uit.no
ssh c6-4
cd ~/arpx/image_service

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

FLUX.1 Schnell is a gated model. Authenticate with HuggingFace before downloading:

1. Accept the license at https://huggingface.co/black-forest-labs/FLUX.1-schnell
2. Create a token at https://huggingface.co/settings/tokens (read permission)
3. Login on the cluster:

```bash
pip install -U huggingface_hub
huggingface-cli login
```

Pre-download the model (~24 GB, cached in `~/hf_cache`):

```bash
HF_HOME=~/hf_cache python -c "from diffusers import FluxPipeline; FluxPipeline.from_pretrained('black-forest-labs/FLUX.1-schnell', torch_dtype=__import__('torch').bfloat16)"
```

`pip install` downloads ~2 GB (PyTorch + CUDA). Can take long time due to DFS.

FLUX.1 Schnell requires ~24 GB VRAM and uses CPU offload for text encoders. Only RTX 3090 nodes (c6-4, c6-8) have enough VRAM.

### Per session

**1. Start the service on the cluster:**

```bash
ssh dsc019@ificluster.ifi.uit.no && ssh c6-4
cd ~/arpx/image_service && source venv/bin/activate
./start.sh c6-4
```

Verify:
```bash
curl http://c6-4:<port>/health
# {"status":"ok","gpu":"NVIDIA GeForce RTX 3090","model_loaded":false}
```

**2. Open the SSH tunnel (run locally, keep terminal open):**

```bash
./image_service/tunnel.sh c6-4
```

Output:
```
SSH tunnel open
  Cluster node : c6-4:37263
  Local port   : 8765

Set in n8n CallClusterAPI node URL:
  http://host.docker.internal:8765/generate
```

**3. n8n URL:**

The `CallClusterAPI` node URL should be:
```
{{ $vars?.IMAGE_SERVICE_URL ?? 'http://host.docker.internal:8765/generate' }}
```

Local port `8765` is fixed by the tunnel — the URL does not change between sessions.

**4. Stop:**

```bash
# On the cluster:
./stop.sh

# Locally: Ctrl+C in the tunnel terminal
```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `ENOTFOUND c6-4.ifi.uit.no` | n8n cannot resolve cluster hostname | Run `tunnel.sh` |
| `ECONNREFUSED 192.168.65.254:8765` | Tunnel closed (host slept or idle timeout) | Re-run `tunnel.sh` |
| `503 Model load failed` | GPU OOM or CUDA error | Check `server.log`, restart service |
| `analogy_image` empty in response | Service unreachable — n8n continues without image | Fix tunnel, re-run explanation |

Check whether the service is alive:

```bash
ssh dsc019@ificluster.ifi.uit.no
ssh c6-4
cat ~/arpx/image_service/server.pid && ps aux | grep uvicorn
```

---

## API

### `GET /health`

```json
{"status": "ok", "gpu": "NVIDIA GeForce RTX 3090", "model": "black-forest-labs/FLUX.1-schnell", "model_loaded": false}
```

`model_loaded` is `false` until the first `/generate` request (lazy load).

### `POST /generate`

Request:
```json
{
  "prompt": "A friendly illustration of a single beehive with glowing hexagonal cells, centered on a soft white background, in a simple cartoon style.",
  "steps": 4,
  "width": 1024,
  "height": 1024
}
```

Response:
```json
{"image": "<base64 PNG>", "prompt": "..."}
```

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `IMAGE_MODEL` | `black-forest-labs/FLUX.1-schnell` | HuggingFace model ID |
| `HF_HOME` | `~/hf_cache` | Model cache directory |

---

## GPU nodes

| Node | GPU | VRAM |
|------|-----|------|
| c6-4 | RTX 3090 | 24 GB |
| c6-8 | RTX 3090 | 24 GB |
| c6-5 | RTX 2080 Ti | 11 GB |
| c6-12 | RTX 2080 SUPER | 8 GB |
