"""
Eval runner.

Usage:
    python -m evals.run evaluate                              # score current prompts.yaml
    python -m evals.run evaluate --model mistral-Large-3     # override generator model
    python -m evals.run evaluate --levels 1 5                # restrict to specific levels
    python -m evals.run estimate                             # dry-run cost estimate
    python -m evals.run compare-models                       # run all comparison models, save CSV
    python -m evals.run check-baseline                       # compare latest report to baseline
"""

import argparse
import asyncio
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from evals.config import CONCURRENCY, GENERATOR_MODEL, REPORTS_DIR
from evals.dataset import load_eval_cases
from evals.generate import generate_explanation, generate_mermaid
from evals.graders import mermaid as mermaid_grader
from evals.graders import rubric as rubric_grader

_REGRESSION_THRESHOLD = 0.2
_COMPARISON_MODELS = [
    "gpt-5-chat",
    "Llama-4-Maverick-17B-128E-Instruct-FP8",
    "mistral-Large-3",
]


def _run_one_case(case: dict) -> dict:
    paper_excerpt = case["paper_excerpt"]
    topics = case["expected_topics"]
    level = case["level"]

    expl = generate_explanation(paper_excerpt, topics, level)
    diag = generate_mermaid(paper_excerpt, topics, level)

    rubric_result = rubric_grader.grade(
        paper_excerpt=paper_excerpt,
        output=expl["text"],
        level=level,
        expected_topics=topics,
    )
    mermaid_result = mermaid_grader.grade(diag["text"])

    return {
        "paper": case["paper_path"],
        "level": level,
        "model": GENERATOR_MODEL,
        "explanation": expl["text"],
        "diagram": diag["text"],
        "prompt_tokens": expl["prompt_tokens"],
        "completion_tokens": expl["completion_tokens"],
        "rubric": rubric_result,
        "mermaid": mermaid_result,
    }


async def _run_all_async(cases: list[dict]) -> list[dict]:
    sem = asyncio.Semaphore(CONCURRENCY)
    loop = asyncio.get_event_loop()

    async def guarded(case):
        async with sem:
            return await loop.run_in_executor(None, _run_one_case, case)

    return await asyncio.gather(*[guarded(c) for c in cases])


def _aggregate(results: list[dict]) -> dict:
    by_level: dict[int, list] = {}
    for r in results:
        by_level.setdefault(r["level"], []).append(r)

    summary = {}
    for level, rows in sorted(by_level.items()):
        rubric_scores = [r["rubric"]["normalized"] for r in rows]
        mermaid_scores = [r["mermaid"]["score"] for r in rows]
        summary[level] = {
            "rubric_mean": round(sum(rubric_scores) / len(rubric_scores), 3),
            "mermaid_mean": round(sum(mermaid_scores) / len(mermaid_scores), 3),
            "n": len(rows),
        }

    all_rubric = [r["rubric"]["normalized"] for r in results]
    all_mermaid = [r["mermaid"]["score"] for r in results]
    summary["overall"] = {
        "rubric_mean": round(sum(all_rubric) / len(all_rubric), 3) if all_rubric else 0,
        "mermaid_mean": round(sum(all_mermaid) / len(all_mermaid), 3) if all_mermaid else 0,
        "n": len(results),
    }

    return summary


def _save_report(results: list[dict], summary: dict) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(REPORTS_DIR, f"report_{ts}.json")

    with open(path, "w") as f:
        json.dump({"timestamp": ts, "summary": summary, "results": results}, f, indent=2)

    return path


def _save_csv(results: list[dict], filename: str) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, filename)

    fieldnames = [
        "paper", "level", "model",
        "faithfulness", "level_match", "coverage", "clarity",
        "rubric_total", "rubric_normalized",
        "mermaid_valid", "mermaid_score",
        "prompt_tokens", "completion_tokens",
    ]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "paper": Path(r["paper"]).stem,
                "level": r["level"],
                "model": r.get("model", GENERATOR_MODEL),
                "faithfulness": r["rubric"]["faithfulness"],
                "level_match": r["rubric"]["level_match"],
                "coverage": r["rubric"]["coverage"],
                "clarity": r["rubric"]["clarity"],
                "rubric_total": r["rubric"]["total"],
                "rubric_normalized": r["rubric"]["normalized"],
                "mermaid_valid": r["mermaid"].get("hard_pass", False),
                "mermaid_score": r["mermaid"]["score"],
                "prompt_tokens": r.get("prompt_tokens"),
                "completion_tokens": r.get("completion_tokens"),
            })

    return path


def _load_baseline() -> dict | None:
    path = os.path.join(REPORTS_DIR, "baseline.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _print_summary(summary: dict) -> None:
    print("\n--- Eval summary ---")
    print(f"{'Level':<8} {'Rubric':>8} {'Mermaid':>9} {'N':>4}")
    print("-" * 34)
    for key, s in summary.items():
        label = f"L{key}" if isinstance(key, int) else key
        print(f"{label:<8} {s['rubric_mean']:>8.3f} {s['mermaid_mean']:>9.3f} {s['n']:>4}")
    print()


def _check_regressions(summary: dict, baseline: dict) -> bool:
    regressions = []
    for level, s in summary.items():
        b = baseline.get("summary", {}).get(level)
        if b is None:
            continue
        for metric in ("rubric_mean", "mermaid_mean"):
            delta = s[metric] - b[metric]
            if delta < -_REGRESSION_THRESHOLD:
                regressions.append((level, metric, b[metric], s[metric], delta))

    if regressions:
        print("REGRESSIONS DETECTED:")
        for level, metric, old, new, delta in regressions:
            print(f"  Level {level} {metric}: {old:.3f} -> {new:.3f}  (Δ {delta:+.3f})")
        return True

    print("No regressions detected (threshold=%.2f)." % _REGRESSION_THRESHOLD)
    return False


def cmd_estimate(args) -> None:
    cases = load_eval_cases()
    if not cases:
        print("No cases loaded. Add PDFs to evals/papers/ and configure cases.yaml.")
        return

    n_cases = len(cases)
    explain_gen_tokens = n_cases * 1500
    mermaid_gen_tokens = n_cases * 800
    judge_tokens = n_cases * 1000

    print(f"\nEval estimate ({n_cases} cases, concurrency={CONCURRENCY}):")
    print(f"  Explanation generation: ~{n_cases} calls, ~{explain_gen_tokens:,} tokens")
    print(f"  Mermaid generation:     ~{n_cases} calls, ~{mermaid_gen_tokens:,} tokens")
    print(f"  Rubric judging:         ~{n_cases} calls, ~{judge_tokens:,} tokens")
    print(f"  Total:                  ~{n_cases * 3} calls, ~{explain_gen_tokens + mermaid_gen_tokens + judge_tokens:,} tokens")
    print("\nNote: cached results skip API calls. Run once to warm the cache.")


def cmd_evaluate(args) -> None:
    if args.model:
        os.environ["ARPX_GENERATOR_MODEL"] = args.model
        # Reload config in generate module so GENERATOR_MODEL picks up the override
        import evals.config as cfg
        import evals.generate as gen
        cfg.GENERATOR_MODEL = args.model
        gen.GENERATOR_MODEL = args.model

    cases = load_eval_cases()
    if not cases:
        print("No cases loaded. Add PDFs to evals/papers/ and configure cases.yaml.")
        sys.exit(1)

    if args.levels:
        cases = [c for c in cases if c["level"] in args.levels]
        print(f"Filtered to levels {args.levels}: {len(cases)} cases.")

    model = args.model or GENERATOR_MODEL
    print(f"Running eval on {len(cases)} cases (model={model}, concurrency={CONCURRENCY})...")
    results = asyncio.run(_run_all_async(cases))
    summary = _aggregate(results)

    report_path = _save_report(results, summary)
    print(f"Report saved: {report_path}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model = model.replace("/", "_").replace(":", "_")
    csv_path = _save_csv(results, f"eval_{safe_model}_{ts}.csv")
    print(f"CSV saved:    {csv_path}")

    _print_summary(summary)

    baseline = _load_baseline()
    if baseline:
        had_regression = _check_regressions(summary, baseline)
        if had_regression:
            sys.exit(2)
    else:
        print("No baseline.json found. Copy your first report to evals/reports/baseline.json.")


def cmd_compare_models(args) -> None:
    """Run eval across multiple models and save a merged comparison CSV."""
    models = args.models or _COMPARISON_MODELS
    levels = args.levels or [1, 5]

    all_results = []
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    for model in models:
        os.environ["ARPX_GENERATOR_MODEL"] = model
        import evals.config as cfg
        import evals.generate as gen
        cfg.GENERATOR_MODEL = model
        gen.GENERATOR_MODEL = model

        cases = load_eval_cases()
        if not cases:
            print("No cases loaded.")
            sys.exit(1)

        cases = [c for c in cases if c["level"] in levels]
        print(f"\n[{model}] Running {len(cases)} cases (levels={levels})...")

        try:
            results = asyncio.run(_run_all_async(cases))
        except Exception as e:
            print(f"[{model}] FAILED: {e}")
            continue

        for r in results:
            r["model"] = model
        all_results.extend(results)

        summary = _aggregate(results)
        print(f"[{model}] Done.")
        _print_summary(summary)

        # Save per-model CSV immediately so results aren't lost on later failure
        safe_model = model.replace("/", "_").replace(":", "_")
        _save_csv(results, f"eval_{safe_model}_{ts}.csv")

    if not all_results:
        print("No results collected.")
        sys.exit(1)

    csv_path = _save_csv(all_results, f"comparison_all_models_{ts}.csv")
    print(f"\nComparison CSV saved: {csv_path}")
    print(f"Total rows: {len(all_results)}")


def cmd_check_baseline(args) -> None:
    reports = sorted(Path(REPORTS_DIR).glob("report_*.json"))
    if len(reports) < 1:
        print("No reports found. Run 'evaluate' first.")
        sys.exit(1)

    latest = json.loads(reports[-1].read_text())
    baseline = _load_baseline()

    if not baseline:
        print("No baseline.json. Copy a report to evals/reports/baseline.json.")
        sys.exit(1)

    print(f"Comparing {reports[-1].name} vs baseline:")
    _print_summary(latest["summary"])
    had_regression = _check_regressions(latest["summary"], baseline)
    if had_regression:
        sys.exit(2)


def main() -> None:
    parser = argparse.ArgumentParser(description="ARPX eval runner")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("estimate", help="Dry-run cost estimate")

    eval_p = sub.add_parser("evaluate", help="Run full eval and save report")
    eval_p.add_argument("--model", help="Override generator model (env: ARPX_GENERATOR_MODEL)")
    eval_p.add_argument("--levels", type=int, nargs="+", help="Restrict to specific levels (e.g. --levels 1 5)")

    cmp_p = sub.add_parser("compare-models", help="Run eval across multiple models, save merged CSV")
    cmp_p.add_argument("--models", nargs="+", help=f"Models to compare (default: {_COMPARISON_MODELS})")
    cmp_p.add_argument("--levels", type=int, nargs="+", default=[1, 5], help="Levels to evaluate (default: 1 5)")

    sub.add_parser("check-baseline", help="Compare latest report to baseline")

    args = parser.parse_args()

    if args.command == "estimate":
        cmd_estimate(args)
    elif args.command == "evaluate":
        cmd_evaluate(args)
    elif args.command == "compare-models":
        cmd_compare_models(args)
    elif args.command == "check-baseline":
        cmd_check_baseline(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
