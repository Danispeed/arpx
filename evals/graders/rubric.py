"""
LLM-as-judge rubric grader for Explainer and Chat outputs.

Grades on four dimensions (0-5 each):
  FAITHFULNESS  - every claim is directly supported by the paper excerpt
  LEVEL_MATCH   - vocabulary and depth are appropriate for the stated reader level
  COVERAGE      - all expected_topics are addressed
  CLARITY       - logical flow and absence of confusion

Uses a different model than the generator to avoid self-fingerprint bias.
Results are cached to evals/cache/judge/.
"""

import hashlib
import json
import os
import re

import yaml
from openai import AzureOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from evals.config import AZURE_API_VERSION, AZURE_ENDPOINT, AZURE_KEY, CACHE_DIR, JUDGE_MODEL, PROMPTS_PATH

_JUDGE_CACHE = os.path.join(CACHE_DIR, "judge")

_client = AzureOpenAI(
    api_key=AZURE_KEY,
    api_version=AZURE_API_VERSION,
    azure_endpoint=AZURE_ENDPOINT or None,
)


def _load_level_criteria() -> dict:
    """Load level criteria from prompts.yaml. Single source of truth shared with explainer."""
    with open(PROMPTS_PATH) as f:
        data = yaml.safe_load(f)
    raw = data.get("shared", {}).get("level_criteria", {})
    return {int(k): v for k, v in raw.items()}


_LEVEL_CRITERIA = _load_level_criteria()

_JUDGE_SYSTEM = """You are an expert evaluator assessing the quality of an AI-generated research paper explanation.
Score the explanation on the four dimensions below. Return ONLY a JSON object with integer scores and brief rationale strings.
Do not include any text outside the JSON object."""

_JUDGE_USER_TEMPLATE = """Paper excerpt:
{paper_excerpt}

Expected topics: {expected_topics}

Reader level: {level} out of 10
Level criteria: {level_criteria}

Generated explanation:
{output}

Score the explanation on each dimension from 0 (completely fails) to 5 (perfect):

FAITHFULNESS: Every claim is directly supported by the paper excerpt. Penalise invented facts or numbers not present in the excerpt.
LEVEL_MATCH: Vocabulary and depth match level {level} exactly. Criteria: {level_criteria}
COVERAGE: All expected topics are meaningfully addressed.
CLARITY: Logical flow; no confusing jumps; explanation is coherent end-to-end.

Return exactly this JSON:
{{
  "faithfulness": <int 0-5>,
  "faithfulness_note": "<one sentence>",
  "level_match": <int 0-5>,
  "level_match_note": "<one sentence>",
  "coverage": <int 0-5>,
  "coverage_note": "<one sentence>",
  "clarity": <int 0-5>,
  "clarity_note": "<one sentence>"
}}"""


def _cache_key(output: str, level: int, expected_topics: list) -> str:
    raw = f"{JUDGE_MODEL}||{output}||{level}||{sorted(expected_topics)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=30))
def _call_judge(system: str, user: str) -> str:
    response = _client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.0,
        max_completion_tokens=600,
    )
    return response.choices[0].message.content.strip()


def _parse_scores(raw: str) -> dict:
    # Strip markdown fences if present
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    return json.loads(cleaned)


def grade(
    paper_excerpt: str,
    output: str,
    level: int,
    expected_topics: list,
) -> dict:
    """
    Grade an explanation output with the LLM judge.

    Returns:
        {
            "faithfulness": int,   # 0-5
            "level_match": int,
            "coverage": int,
            "clarity": int,
            "total": int,          # sum 0-20
            "normalized": float,   # total / 20, range 0-1
            "faithfulness_note": str,
            "level_match_note": str,
            "coverage_note": str,
            "clarity_note": str,
        }
    """
    os.makedirs(_JUDGE_CACHE, exist_ok=True)
    key = _cache_key(output, level, expected_topics)
    cache_file = os.path.join(_JUDGE_CACHE, f"{key}.json")

    if os.path.exists(cache_file):
        with open(cache_file) as f:
            return json.load(f)

    user = _JUDGE_USER_TEMPLATE.format(
        paper_excerpt=paper_excerpt[:2000],
        expected_topics=", ".join(expected_topics),
        level=level,
        level_criteria=_LEVEL_CRITERIA.get(level, ""),
        output=output,
    )

    raw = _call_judge(_JUDGE_SYSTEM, user)
    scores = _parse_scores(raw)

    result = {
        "faithfulness": scores.get("faithfulness", 0),
        "level_match": scores.get("level_match", 0),
        "coverage": scores.get("coverage", 0),
        "clarity": scores.get("clarity", 0),
        "faithfulness_note": scores.get("faithfulness_note", ""),
        "level_match_note": scores.get("level_match_note", ""),
        "coverage_note": scores.get("coverage_note", ""),
        "clarity_note": scores.get("clarity_note", ""),
    }
    result["total"] = sum(result[k] for k in ("faithfulness", "level_match", "coverage", "clarity"))
    result["normalized"] = result["total"] / 20.0

    with open(cache_file, "w") as f:
        json.dump(result, f)

    return result
