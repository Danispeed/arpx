"""
Loads eval cases and extracts paper excerpts from PDFs.

Does NOT use Weaviate (Docker-only). Extracts text directly via fitz (PyMuPDF)
and applies a heuristic to find the abstract + introduction as the excerpt.
Results are cached to evals/cache/excerpts/ so retrieval only runs once per paper.
"""

import hashlib
import json
import os
from pathlib import Path

import fitz
import yaml

from evals.config import CACHE_DIR, CASES_PATH

_EXCERPT_CACHE = os.path.join(CACHE_DIR, "excerpts")


def _load_cases() -> dict:
    with open(CASES_PATH) as f:
        return yaml.safe_load(f)


def _cache_key(pdf_path: str) -> str:
    return hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()[:16]


def _extract_text(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    return "".join(page.get_text() for page in doc)


def _find_excerpt(text: str, max_chars: int = 3000) -> str:
    """Return abstract + intro section heuristic, up to max_chars."""
    lower = text.lower()

    # Try to find abstract start
    for marker in ["abstract", "abstract—", "abstract:"]:
        idx = lower.find(marker)
        if idx != -1:
            return text[idx: idx + max_chars].strip()

    # Fallback: start of document
    return text[:max_chars].strip()


def _find_topics_context(text: str, max_chars: int = 800) -> str:
    """Short context for topic extraction (abstract only)."""
    return _find_excerpt(text, max_chars=max_chars)


def get_excerpts(pdf_path: str) -> dict:
    """Return {'explain': str, 'topics': str}, loading from cache if available."""
    os.makedirs(_EXCERPT_CACHE, exist_ok=True)
    key = _cache_key(pdf_path)
    cache_file = os.path.join(_EXCERPT_CACHE, f"{key}.json")

    if os.path.exists(cache_file):
        with open(cache_file) as f:
            return json.load(f)

    text = _extract_text(pdf_path)
    result = {
        "explain": _find_excerpt(text, max_chars=3000),
        "topics": _find_topics_context(text, max_chars=800),
    }

    with open(cache_file, "w") as f:
        json.dump(result, f)

    return result


def load_eval_cases() -> list[dict]:
    """
    Return a flat list of eval cases, one per (paper, level) combination.

    Each case:
    {
        "paper_path": str,
        "expected_topics": list[str],
        "level": int,
        "paper_excerpt": str,
        "topics_context": str,
    }
    """
    spec = _load_cases()
    levels = spec.get("levels", list(range(1, 11)))
    cases = []

    for paper in spec["papers"]:
        path = paper["path"]
        if not os.path.exists(path):
            print(f"  [skip] {path} not found — add the PDF to evals/papers/")
            continue

        excerpts = get_excerpts(path)

        for level in levels:
            cases.append({
                "paper_path": path,
                "expected_topics": paper.get("expected_topics", []),
                "level": int(level),
                "paper_excerpt": excerpts["explain"],
                "topics_context": excerpts["topics"],
            })

    return cases
