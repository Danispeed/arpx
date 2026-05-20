import os
import io
import base64
import logging

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("image_service")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="ARPX Image Service")

_MODEL_ID = os.getenv("IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
_pipe = None


class GenerateRequest(BaseModel):
    prompt: str
    steps: int = Field(default=4, ge=1, le=10)
    width: int = Field(default=1024, ge=256, le=1024)
    height: int = Field(default=1024, ge=256, le=1024)


class GenerateResponse(BaseModel):
    image: str
    prompt: str


def _get_pipe():
    global _pipe
    if _pipe is not None:
        return _pipe

    from diffusers import FluxPipeline

    logger.info("Loading %s ...", _MODEL_ID)
    _pipe = FluxPipeline.from_pretrained(
        _MODEL_ID,
        torch_dtype=torch.bfloat16,
    )
    _pipe.enable_model_cpu_offload()
    logger.info("Model loaded on %s", torch.cuda.get_device_name(0))
    return _pipe


@app.get("/health")
def health():
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none"
    return {
        "status": "ok",
        "gpu": gpu,
        "model": _MODEL_ID,
        "model_loaded": _pipe is not None,
    }


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    try:
        pipe = _get_pipe()
    except Exception as e:
        logger.error("Failed to load model: %s", e)
        raise HTTPException(status_code=503, detail=f"Model load failed: {e}")

    try:
        result = pipe(
            prompt=req.prompt,
            num_inference_steps=req.steps,
            guidance_scale=0.0,
            width=req.width,
            height=req.height,
            max_sequence_length=256,
        )
        image = result.images[0]

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        return GenerateResponse(image=b64, prompt=req.prompt)

    except Exception as e:
        logger.error("Generation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")
