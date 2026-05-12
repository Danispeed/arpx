# ARPX Image Service

FastAPI service that generates visual analogy images using SDXL Turbo on a GPU node.
Called by n8n during the explain workflow.

## One-time setup (on ificluster)

```bash
ssh ificluster
ssh c6-4           # or any GPU node: c6-4, c6-8, c6-5, c6-12
cd ~/arpx/image_service

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Pre-download model (~6.5 GB, cached in ~/hf_cache):
HF_HOME=~/hf_cache python -c \
  "from diffusers import AutoPipelineForText2Image; \
   AutoPipelineForText2Image.from_pretrained('stabilityai/sdxl-turbo', variant='fp16')"
```

## Per-session usage

```bash
# Start (auto-finds free port):
./start.sh c6-4

# Output shows the URL — set it in n8n:
#   Settings > Variables > IMAGE_SERVICE_URL = http://c6-4:<port>

# Stop when done:
./stop.sh
```

## API

### `GET /health`

Returns service status, GPU info, model state.

### `POST /generate`

Request:
```json
{
  "prompt": "a library with glowing books and a robot librarian, digital art",
  "steps": 4,
  "width": 1024,
  "height": 1024
}
```

Response:
```json
{
  "image": "<base64 encoded PNG>",
  "prompt": "a library with glowing books..."
}
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `IMAGE_MODEL` | `stabilityai/sdxl-turbo` | HuggingFace model ID |
| `HF_HOME` | `~/hf_cache` | Model cache directory |

## GPU nodes with CUDA

| Node | GPU | VRAM |
|------|-----|------|
| c6-4 | RTX 3090 | 24 GB |
| c6-8 | RTX 3090 | 24 GB |
| c6-5 | RTX 2080 Ti | 11 GB |
| c6-12 | RTX 2080 SUPER | 8 GB |
