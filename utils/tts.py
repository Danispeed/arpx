import io
import os
import re
import shutil
import struct
import tarfile
import urllib.request
import wave
from pathlib import Path

# Piper voice published as a GitHub release asset (works without HuggingFace).
_VOICE_URL = (
    "https://github.com/rhasspy/piper/releases/download/v0.0.2/"
    "voice-en-us-lessac-medium.tar.gz"
)
_VOICE_FILE = "en-us-lessac-medium.onnx"

# Baked into the Docker image (outside the /arpx bind mount); cache dir is the
# fallback when running outside the container.
_BAKED_DIR = Path(os.getenv("PIPER_VOICE_DIR", "/opt/piper"))
_CACHE_DIR = Path.home() / ".cache" / "arpx-piper"

_voice = None
_unavailable = False


def _find_model():
    for directory in (_BAKED_DIR, _CACHE_DIR):
        candidate = directory / _VOICE_FILE
        if candidate.exists():
            return candidate
    return None


def _download_model():
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    archive = _CACHE_DIR / "voice.tar.gz"
    request = urllib.request.Request(_VOICE_URL, headers={"User-Agent": "arpx-tts"})
    with urllib.request.urlopen(request, timeout=120) as response, open(archive, "wb") as out:
        shutil.copyfileobj(response, out)
    with tarfile.open(archive) as tar:
        tar.extractall(_CACHE_DIR)
    archive.unlink(missing_ok=True)
    return _CACHE_DIR / _VOICE_FILE


def _get_voice():
    global _voice, _unavailable
    if _voice is not None:
        return _voice
    if _unavailable:
        return None
    try:
        from piper.voice import PiperVoice

        model = _find_model() or _download_model()
        _voice = PiperVoice.load(str(model))
        return _voice
    except Exception as exc:  # noqa: BLE001
        print("Piper TTS unavailable:", exc)
        _unavailable = True
        return None


def _split_sentences(text: str) -> list[str]:
    text = text.replace("[ANALOGY_IMAGE]", " ")
    # Split on sentence-ending punctuation followed by whitespace or end
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]


def _silence_frames(params: wave._wave_params, ms: int = 400) -> bytes:
    n_samples = int(params.framerate * ms / 1000) * params.nchannels
    return struct.pack(f"<{n_samples}h", *([0] * n_samples))


def synthesize(text: str):
    """Render `text` to WAV bytes with inter-sentence pauses, or None if TTS unavailable."""
    voice = _get_voice()
    if voice is None or not text:
        return None

    sentences = _split_sentences(text or "")
    if not sentences:
        return None

    chunks: list[bytes] = []
    params = None

    for sentence in sentences:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            voice.synthesize(sentence, wav_file)
        buf.seek(0)
        with wave.open(buf, "rb") as wav_file:
            if params is None:
                params = wav_file.getparams()
            chunks.append(wav_file.readframes(wav_file.getnframes()))
        if params is not None:
            chunks.append(_silence_frames(params, ms=400))

    out = io.BytesIO()
    with wave.open(out, "wb") as wav_out:
        wav_out.setparams(params)
        for chunk in chunks:
            wav_out.writeframes(chunk)
    return out.getvalue()
