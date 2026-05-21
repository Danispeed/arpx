import io
import os
import shutil
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


def synthesize(text):
    """Render `text` to WAV bytes, or return None if TTS is unavailable."""
    text = (text or "").replace("[ANALOGY_IMAGE]", " ").strip()
    voice = _get_voice()
    if voice is None or not text:
        return None
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        voice.synthesize(text, wav_file)
    return buffer.getvalue()
