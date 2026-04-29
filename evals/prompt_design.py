"""
Generate purpose-built system prompts for levels 1 and 5 using gpt-5-chat (Azure).

Writes directly against the rubric criteria so prompts are optimized for the
same dimensions the eval harness measures.

Usage:
    python -m evals.prompt_design generate          # generate candidates, print them
    python -m evals.prompt_design generate --write  # also write winners to prompts.yaml
"""

import argparse
import os

import yaml
from dotenv import load_dotenv
from openai import AzureOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

from evals.config import AZURE_API_VERSION, AZURE_ENDPOINT, AZURE_KEY, PROMPTS_PATH
from evals.graders.rubric import _LEVEL_CRITERIA

_DESIGN_MODEL = "gpt-5-chat"

_LEVEL_DEFINITIONS = {
    1: (
        "absolute beginner — no technical background, may be a high-school student or curious adult. "
        "No jargon, no equations. Use everyday analogies only."
    ),
    5: (
        "advanced undergraduate in a related field. Comfortable with domain vocabulary and moderate "
        "technical depth. Can handle intuition-first explanations with key equations if every symbol is defined."
    ),
}

_DESIGN_SYSTEM = """You are an expert prompt engineer designing system prompts for an AI research paper explainer.
The explainer receives a research paper excerpt and explains it to a reader at a specific knowledge level.
Your job is to write a system prompt that maximises performance on four evaluation dimensions (scored 0-5 each):

- FAITHFULNESS: every claim is directly supported by the paper excerpt — no hallucination or invented facts
- LEVEL_MATCH: vocabulary and depth exactly match the target reader level (neither too simple nor too complex)
- COVERAGE: all key topics from the paper are addressed
- CLARITY: logical flow, no confusing jumps, coherent end-to-end

The system prompt should be 3-6 sentences. Write for a reader at the specified level only.
Do not include placeholder variables. Output only the system prompt text — no preamble, no explanation."""

_DESIGN_USER_TEMPLATE = """Target reader level: {level} out of 10
Reader profile: {level_def}
Level rubric criteria (what LEVEL_MATCH checks): {level_criteria}

Write the system prompt that will make the AI produce the best possible explanation for this reader level:"""

_client = AzureOpenAI(
    api_key=AZURE_KEY,
    api_version=AZURE_API_VERSION,
    azure_endpoint=AZURE_ENDPOINT or None,
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
def _generate_candidate(level: int) -> str:
    user = _DESIGN_USER_TEMPLATE.format(
        level=level,
        level_def=_LEVEL_DEFINITIONS[level],
        level_criteria=_LEVEL_CRITERIA[level],
    )
    response = _client.chat.completions.create(
        model=_DESIGN_MODEL,
        messages=[
            {"role": "system", "content": _DESIGN_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
        max_completion_tokens=400,
    )
    return response.choices[0].message.content.strip()


def _write_to_prompts_yaml(level: int, system_prompt: str) -> None:
    with open(PROMPTS_PATH) as f:
        data = yaml.safe_load(f)

    levels = data.setdefault("explainer", {}).setdefault("levels", {})
    key = str(level)
    if key not in levels:
        levels[key] = {}
    if isinstance(levels[key], str):
        levels[key] = {"system": levels[key]}
    levels[key]["system"] = system_prompt

    with open(PROMPTS_PATH, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"  Written to prompts.yaml [explainer.levels.{key}.system]")


def cmd_generate(args) -> None:
    target_levels = [1, 5]
    generated = {}

    for level in target_levels:
        print(f"Generating system prompt for level {level} using {_DESIGN_MODEL}...", flush=True)
        candidate = _generate_candidate(level)
        generated[level] = candidate
        print(f"\n--- Level {level} system prompt ---")
        print(candidate)
        print()

    if args.write:
        print("Writing to prompts.yaml...")
        for level, prompt in generated.items():
            _write_to_prompts_yaml(level, prompt)
        print("\nDone. Clear generation cache so new prompts take effect:")
        print("  rm -rf evals/cache/generations/")
    else:
        print("(Dry run — pass --write to update prompts.yaml)")


def main() -> None:
    parser = argparse.ArgumentParser(description="ARPX prompt designer")
    sub = parser.add_subparsers(dest="command")

    gen_p = sub.add_parser("generate", help="Generate level 1 + 5 system prompts using gpt-5-chat")
    gen_p.add_argument("--write", action="store_true", help="Write output to prompts.yaml")

    args = parser.parse_args()

    if args.command == "generate":
        cmd_generate(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
