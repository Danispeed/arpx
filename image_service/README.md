# ARPX Image Service

FastAPI service that generates visual analogy images using SDXL Turbo.
Runs on a UiT ificluster GPU node — **not** inside Docker.

## How it fits into the system

```
Your Mac
  ├── Docker (app + weaviate + n8n)
  │     └── n8n calls CallClusterAPI node
  │               ↓ http://host.docker.internal:8765/generate
  └── SSH tunnel (tunnel.sh keeps this open)
            ↓ forwarded to ificluster
  ificluster GPU node (c6-4)
        └── uvicorn server.py  ← SDXL Turbo generates image → base64 PNG
```

Docker cannot reach ificluster directly. `tunnel.sh` bridges the gap by
forwarding a local port through SSH. n8n reaches it via `host.docker.internal`.

---

## One-time setup (do this once per GPU node)

### 1. SSH to the cluster and pick a GPU node

```bash
ssh dsc019@ificluster.ifi.uit.no
ssh c6-4        # RTX 3090, recommended
```

### 2. Clone / pull the repo and install dependencies

```bash
cd ~/arpx/image_service    # repo must be checked out at ~/arpx

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> `pip install` downloads ~2 GB (PyTorch + CUDA libs). Takes 10–20 min on NFS. Normal.

### 3. Pre-download the model (~6.5 GB)

```bash
HF_HOME=~/hf_cache python -c "from diffusers import AutoPipelineForText2Image; AutoPipelineForText2Image.from_pretrained('stabilityai/sdxl-turbo', variant='fp16')"
```

Model is cached in `~/hf_cache`. Only downloaded once.

---

## Per-session workflow

Every time you want to use the image service:

### Step 1 — Start the service on the cluster

```bash
ssh dsc019@ificluster.ifi.uit.no
ssh c6-4
cd ~/arpx/image_service
source venv/bin/activate
./start.sh c6-4
```

Output confirms the port:
```
ARPX Image Service started
  Node: c6-4
  Port: 37263
  URL:  http://c6-4:37263
```

Verify it's alive:
```bash
curl http://c6-4:37263/health
# {"status":"ok","gpu":"NVIDIA GeForce RTX 3090","model_loaded":false}
```

### Step 2 — Open the SSH tunnel (on your Mac, new terminal)

```bash
cd /path/to/arpx/image_service
./tunnel.sh c6-4
```

The script auto-reads the port from the cluster and prints:
```
SSH tunnel open
  Cluster node : c6-4:37263
  Local port   : 8765

Set in n8n CallClusterAPI node URL:
  http://host.docker.internal:8765/generate
```

**Keep this terminal open.** Closing it kills the tunnel.

### Step 3 — Set the n8n URL (only needed if port changed)

Open n8n → `arpx-mvp` workflow → `CallClusterAPI` node → URL field:

```
{{ $vars?.IMAGE_SERVICE_URL ?? 'http://host.docker.internal:8765/generate' }}
```

The local port is always `8765` (tunnel default), so this URL never changes
between sessions — only update it if you used a different local port.

Publish the workflow after any URL change.

### Step 4 — Stop when done

```bash
# On the cluster:
cd ~/arpx/image_service && ./stop.sh

# Close the tunnel terminal with Ctrl+C
```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `ENOTFOUND c6-4.ifi.uit.no` | n8n can't reach cluster — no tunnel | Run `./tunnel.sh` |
| `ECONNREFUSED 192.168.65.254:8765` | Tunnel closed (Mac slept / idle timeout) | Re-run `./tunnel.sh` |
| `404 Not Found` | Wrong URL in n8n — double `/generate` | Check URL has exactly one `/generate` |
| `503 Model load failed` | GPU OOM or CUDA error | Check `server.log` on cluster, restart |
| `image_prompt` and `analogy_image` empty | Service unreachable — n8n continues without image | Fix tunnel, re-run explanation |

### Check if service is still running

```bash
ssh dsc019@ificluster.ifi.uit.no
ssh c6-4
cat ~/arpx/image_service/server.pid && ps aux | grep uvicorn
```

---

## API reference

### `GET /health`

```json
{"status": "ok", "gpu": "NVIDIA GeForce RTX 3090", "model": "stabilityai/sdxl-turbo", "model_loaded": false}
```

`model_loaded` is `false` until first `/generate` call (lazy load).

### `POST /generate`

```json
{
  "prompt": "clean simple illustration, single beehive with glowing cells, centered, flat cartoon style",
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
| `IMAGE_MODEL` | `stabilityai/sdxl-turbo` | HuggingFace model ID |
| `HF_HOME` | `~/hf_cache` | Model cache directory |
| `ARPX_CLUSTER_USER` | `dsc019` | Override SSH username in `tunnel.sh` |
| `ARPX_CLUSTER_HOST` | `ificluster.ifi.uit.no` | Override cluster hostname in `tunnel.sh` |

---

## GPU nodes

| Node | GPU | VRAM | Notes |
|------|-----|------|-------|
| c6-4 | RTX 3090 | 24 GB | Recommended |
| c6-8 | RTX 3090 | 24 GB | Good fallback |
| c6-5 | RTX 2080 Ti | 11 GB | Works but slower |
| c6-12 | RTX 2080 SUPER | 8 GB | Minimum viable |

Check node load before picking: `/share/ifi/list-nodes-by-load.sh`
