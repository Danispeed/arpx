"""
Generates Explainer and Mermaid outputs using prompts.yaml + Azure OpenAI directly,
bypassing n8n for eval speed. Caches results to avoid redundant API calls.
"""

import hashlib
import json
import os
import time

import yaml
from openai import AzureOpenAI, UnprocessableEntityError
from tenacity import retry, stop_after_attempt, wait_exponential

from evals.config import (
    AZURE_API_VERSION,
    AZURE_ENDPOINT,
    AZURE_KEY,
    CACHE_DIR,
    GENERATOR_MODEL,
    PROMPTS_PATH,
)

_GEN_CACHE = os.path.join(CACHE_DIR, "generations")

_client = AzureOpenAI(
    api_key=AZURE_KEY,
    api_version=AZURE_API_VERSION,
    azure_endpoint=AZURE_ENDPOINT or None,
)


def _load_prompts() -> dict:
    with open(PROMPTS_PATH) as f:
        return yaml.safe_load(f)


def _get_level_system(prompts: dict, agent: str, level: int) -> str:
    levels = prompts.get(agent, {}).get("levels", {})
    # Try exact int key, then string key
    return levels.get(level) or levels.get(str(level)) or {}


def _constraints_block(prompts: dict) -> str:
    constraints = prompts.get("shared", {}).get("constraints", [])
    if not constraints:
        return ""
    return "\n\nConstraints:\n" + "\n".join(f"- {c}" for c in constraints)


def _cache_key(model: str, system: str, user: str, temperature: float) -> str:
    raw = f"{model}||{system}||{user}||{temperature}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=30))
def _call_azure(system: str, user: str, temperature: float, max_tokens: int) -> dict:
    kwargs = dict(
        model=GENERATOR_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
    )
    try:
        response = _client.chat.completions.create(**kwargs, max_completion_tokens=max_tokens)
    except UnprocessableEntityError:
        # Some deployments (e.g. Mistral) reject max_completion_tokens; fall back to max_tokens
        response = _client.chat.completions.create(**kwargs, max_tokens=max_tokens)
    usage = response.usage or {}
    return {
        "output": response.choices[0].message.content.strip(),
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
    }


def _cached_call(system: str, user: str, temperature: float, max_tokens: int) -> dict:
    os.makedirs(_GEN_CACHE, exist_ok=True)
    key = _cache_key(GENERATOR_MODEL, system, user, temperature)
    cache_file = os.path.join(_GEN_CACHE, f"{key}.json")

    if os.path.exists(cache_file):
        cached = json.load(open(cache_file))
        return {
            "output": cached["output"],
            "prompt_tokens": cached.get("prompt_tokens"),
            "completion_tokens": cached.get("completion_tokens"),
        }

    result = _call_azure(system, user, temperature, max_tokens)

    with open(cache_file, "w") as f:
        json.dump(result, f)

    return result


def generate_explanation(paper_excerpt: str, topics: list, level: int) -> dict:
    """Returns {"text": str, "prompt_tokens": int|None, "completion_tokens": int|None}."""
    prompts = _load_prompts()
    level_data = _get_level_system(prompts, "explainer", level)
    system = (level_data.get("system") or "") + _constraints_block(prompts)
    template = prompts.get("explainer", {}).get("user_template", "")
    user = (
        template
        .replace("{paper_excerpt}", paper_excerpt)
        .replace("{topics}", json.dumps(topics))
        .replace("{level}", str(level))
    )
    result = _cached_call(system, user, temperature=0.5, max_tokens=1200)
    return {"text": result["output"], "prompt_tokens": result["prompt_tokens"], "completion_tokens": result["completion_tokens"]}


def generate_mermaid(paper_excerpt: str, topics: list, level: int = 5) -> dict:
    """Returns {"text": str, "prompt_tokens": int|None, "completion_tokens": int|None}."""
    prompts = _load_prompts()
    system = (prompts.get("mermaid", {}).get("system") or "") + _constraints_block(prompts)
    template = prompts.get("mermaid", {}).get("user_template", "")
    user = (
        template
        .replace("{paper_excerpt}", paper_excerpt)
        .replace("{topics}", json.dumps(topics))
        .replace("{level}", str(level))
    )
    result = _cached_call(system, user, temperature=0.3, max_tokens=900)
    return {"text": result["output"], "prompt_tokens": result["prompt_tokens"], "completion_tokens": result["completion_tokens"]}
