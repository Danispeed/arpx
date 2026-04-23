"""
Eval runner.

Usage:
    python -m evals.run evaluate            # score current prompts.yaml, save report
    python -m evals.run estimate            # dry-run: predict token/request count
    python -m evals.run compare --baseline  # compare latest report to baseline.json
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from evals.config import CONCURRENCY, REPORTS_DIR
from evals.dataset import load_eval_cases
from evals.generate import generate_explanation, generate_mermaid
from evals.graders import mermaid as mermaid_grader
from evals.graders import rubric as rubric_grader

_REGRESSION_THRESHOLD = 0.2  # drop in normalised score that counts as regression


def _run_one_case(case: dict) -> dict:
    paper_excerpt = case["paper_excerpt"]
    topics = case["expected_topics"]
    level = case["level"]

    explanation = generate_explanation(paper_excerpt, topics, level)
    diagram = generate_mermaid(paper_excerpt, topics, level)

    rubric_result = rubric_grader.grade(
        paper_excerpt=paper_excerpt,
        output=explanation,
        level=level,
        expected_topics=topics,
    )
    mermaid_result = mermaid_grader.grade(diagram)

    return {
        "paper": case["paper_path"],
        "level": level,
        "explanation": explanation,
        "diagram": diagram,
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
    """Return True if any regression exceeds threshold."""
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
    # Rough token estimates
    explain_gen_tokens = n_cases * 1500      # ~1500 tokens per explanation call
    mermaid_gen_tokens = n_cases * 800       # ~800 per diagram
    judge_tokens = n_cases * 1000            # ~1000 per rubric call (4 dimensions)

    print(f"\nEval estimate ({n_cases} cases, concurrency={CONCURRENCY}):")
    print(f"  Explanation generation: ~{n_cases} calls, ~{explain_gen_tokens:,} tokens")
    print(f"  Mermaid generation:     ~{n_cases} calls, ~{mermaid_gen_tokens:,} tokens")
    print(f"  Rubric judging:         ~{n_cases} calls, ~{judge_tokens:,} tokens")
    print(f"  Total:                  ~{n_cases * 3} calls, ~{explain_gen_tokens + mermaid_gen_tokens + judge_tokens:,} tokens")
    print("\nNote: cached results skip API calls. Run once to warm the cache.")


def cmd_evaluate(args) -> None:
    cases = load_eval_cases()
    if not cases:
        print("No cases loaded. Add PDFs to evals/papers/ and configure cases.yaml.")
        sys.exit(1)

    print(f"Running eval on {len(cases)} cases (concurrency={CONCURRENCY})...")
    results = asyncio.run(_run_all_async(cases))
    summary = _aggregate(results)

    report_path = _save_report(results, summary)
    print(f"Report saved: {report_path}")
    _print_summary(summary)

    baseline = _load_baseline()
    if baseline:
        had_regression = _check_regressions(summary, baseline)
        if had_regression:
            sys.exit(2)
    else:
        print("No baseline.json found. Copy your first report to evals/reports/baseline.json.")


def cmd_compare(args) -> None:
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
    sub.add_parser("evaluate", help="Run full eval and save report")
    sub.add_parser("compare", help="Compare latest report to baseline")

    args = parser.parse_args()

    if args.command == "estimate":
        cmd_estimate(args)
    elif args.command == "evaluate":
        cmd_evaluate(args)
    elif args.command == "compare":
        cmd_compare(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
