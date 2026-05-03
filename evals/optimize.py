"""
DSPy-based automated prompt optimization.

For each level 1..10, runs COPRO to find a better system prompt for the
Explainer agent, then writes the optimized prompts back to prompts.yaml.

Usage:
    python -m evals.optimize                         # optimize all levels, budget=5
    python -m evals.optimize --levels 5              # single level
    python -m evals.optimize --levels 1,2,3          # specific levels
    python -m evals.optimize --budget 10             # more trials per level
    python -m evals.optimize --optimizer mipro       # use MIPROv2 instead of COPRO
"""

import argparse
import json
import os
import sys
import textwrap

import dspy
import yaml
from dspy.teleprompt import COPRO

from evals.config import (
    AZURE_API_VERSION,
    AZURE_ENDPOINT,
    AZURE_KEY,
    GENERATOR_MODEL,
    PROMPTS_PATH,
    PROPOSER_MODEL,
)
from evals.dataset import load_eval_cases
from evals.graders import rubric as rubric_grader


# ── DSPy signatures ──────────────────────────────────────────────────────────

class ExplainerSignature(dspy.Signature):
    """Generate an adaptive explanation of a research paper excerpt calibrated to the reader's level."""

    paper_excerpt: str = dspy.InputField(desc="The relevant excerpt from the research paper.")
    topics: str = dspy.InputField(desc="JSON list of the main topics of the paper.")
    level: int = dspy.InputField(desc="Reader knowledge level, 1 (beginner) to 10 (expert).")
    explanation: str = dspy.OutputField(desc="The adaptive explanation for this reader level.")


class ExplainerModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(ExplainerSignature)

    def forward(self, paper_excerpt, topics, level):
        return self.predict(paper_excerpt=paper_excerpt, topics=topics, level=level)


# ── LM configuration ─────────────────────────────────────────────────────────

def _make_lm(model: str) -> dspy.LM:
    return dspy.LM(
        model=f"azure/{model}",
        api_key=AZURE_KEY,
        api_base=AZURE_ENDPOINT,
        api_version=AZURE_API_VERSION,
        temperature=0.5,
        max_tokens=1200,
    )


# ── Metric ───────────────────────────────────────────────────────────────────

def _make_metric(level: int, expected_topics: list[str]):
    def metric(example, pred, trace=None):
        try:
            scores = rubric_grader.grade(
                paper_excerpt=example.paper_excerpt,
                output=pred.explanation,
                level=level,
                expected_topics=expected_topics,
            )
            return scores["normalized"]
        except Exception as e:
            print(f"  [metric error] {e}")
            return 0.0

    return metric


# ── prompts.yaml read / write ─────────────────────────────────────────────────

def _load_prompts() -> dict:
    with open(PROMPTS_PATH) as f:
        return yaml.safe_load(f)


class _LiteralStr(str):
    """Marker class so pyyaml always uses | (literal block) style for system prompts."""


def _literal_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(_LiteralStr, _literal_representer)


def _literalise(obj):
    """Recursively wrap string values in _LiteralStr so they dump as | blocks.
    Only applies to multi-line strings — single-line strings stay as plain scalars
    so the JS constraints regex (which expects double-quoted strings) still matches.
    """
    if isinstance(obj, dict):
        return {k: _literalise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_literalise(v) for v in obj]
    if isinstance(obj, str) and "\n" in obj:
        return _LiteralStr(obj if obj.endswith("\n") else obj + "\n")
    return obj


def _write_prompts(data: dict) -> None:
    with open(PROMPTS_PATH, "w") as f:
        yaml.dump(_literalise(data), f, allow_unicode=True, sort_keys=False, width=120)


def _set_level_system(data: dict, agent: str, level: int, system: str) -> None:
    if "levels" not in data[agent]:
        data[agent]["levels"] = {}
    # Trailing newline ensures pyyaml chooses | literal block style.
    system = system.rstrip("\n") + "\n"
    data[agent]["levels"][str(level)] = {"system": system}


# ── Optimization per level ────────────────────────────────────────────────────

def optimize_level(level: int, all_cases: list[dict], budget: int, optimizer_name: str) -> str | None:
    """
    Run DSPy optimization for a single level.
    Returns the best instruction string, or None on failure.
    """
    cases = [c for c in all_cases if c["level"] == level]
    if not cases:
        print(f"  [level {level}] No cases found — skipping.")
        return None

    print(f"\n  [level {level}] Optimizing with {len(cases)} training cases, budget={budget}...")

    # Build DSPy Examples
    trainset = [
        dspy.Example(
            paper_excerpt=c["paper_excerpt"],
            topics=json.dumps(c["expected_topics"]),
            level=level,
        ).with_inputs("paper_excerpt", "topics", "level")
        for c in cases
    ]

    metric = _make_metric(level, cases[0]["expected_topics"])
    module = ExplainerModule()

    # Seed the module with the existing per-level system prompt so COPRO refines
    # from the hand-tuned rules rather than the generic signature docstring.
    prompts = _load_prompts()
    existing = (
        prompts.get("explainer", {})
        .get("levels", {})
        .get(str(level), {})
        .get("system", "")
        .strip()
    )
    if existing:
        module.predict.signature = module.predict.signature.with_instructions(existing)

    if optimizer_name == "mipro":
        try:
            from dspy.teleprompt import MIPROv2
            optimizer = MIPROv2(
                metric=metric,
                prompt_model=_make_lm(PROPOSER_MODEL),
                num_candidates=budget,
                num_trials=budget,
                verbose=False,
            )
            compiled = optimizer.compile(module, trainset=trainset)
        except ImportError:
            print("  MIPROv2 not available — falling back to COPRO")
            optimizer_name = "copro"

    if optimizer_name != "mipro":
        optimizer = COPRO(
            metric=metric,
            prompt_model=_make_lm(PROPOSER_MODEL),
            breadth=budget,
            depth=2,
            verbose=False,
        )
        compiled = optimizer.compile(module, trainset=trainset, eval_kwargs={"num_threads": 1})

    instruction = compiled.predict.signature.instructions
    print(f"  [level {level}] Best instruction ({len(instruction)} chars):")
    print(textwrap.indent(instruction[:300] + ("..." if len(instruction) > 300 else ""), "    "))

    return instruction


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="ARPX prompt optimizer")
    parser.add_argument("--levels", default="1,2,3,4,5,6,7,8,9,10",
                        help="Comma-separated levels to optimize (default: all)")
    parser.add_argument("--budget", type=int, default=5,
                        help="Number of candidates/trials per level (default: 5)")
    parser.add_argument("--optimizer", choices=["copro", "mipro"], default="copro",
                        help="DSPy optimizer to use (default: copro)")
    parser.add_argument("--agent", choices=["explainer", "chat", "both"], default="explainer",
                        help="Which agent to optimize (default: explainer)")

    args = parser.parse_args()

    levels = [int(x.strip()) for x in args.levels.split(",")]

    # Configure DSPy
    generator_lm = _make_lm(GENERATOR_MODEL)
    dspy.configure(lm=generator_lm)

    print(f"Loading eval cases...")
    all_cases = load_eval_cases()
    if not all_cases:
        print("No cases loaded. Add PDFs to evals/papers/.")
        sys.exit(1)

    print(f"Loaded {len(all_cases)} cases. Optimizing levels: {levels}")

    prompts = _load_prompts()
    updated = False

    for level in levels:
        instruction = optimize_level(level, all_cases, args.budget, args.optimizer)
        if instruction:
            _set_level_system(prompts, "explainer", level, instruction)
            if args.agent in ("chat", "both"):
                _set_level_system(prompts, "chat", level, instruction)
            updated = True

    if updated:
        _write_prompts(prompts)
        print(f"\nWrote optimized prompts to {PROMPTS_PATH}")
        print("Run 'python -m evals.run evaluate' to score the new prompts.")
    else:
        print("No levels updated.")


if __name__ == "__main__":
    main()
