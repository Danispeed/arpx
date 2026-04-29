"""
Inter-judge agreement check for the rubric grader.

Re-judges a random sample of explanations with a second judge model
(Llama-3.3-70B-Instruct by default) and computes Spearman rank correlation
against the primary judge (DeepSeek-V3.2) per rubric dimension.

A high ρ (≥ 0.7) means the rubric is measuring something real, not just
one model's idiosyncrasies. A low ρ means the rubric is anecdotal.

Usage:
    python -m evals.judge_agreement --csv evals/reports/comparison_all_models_*.csv
    python -m evals.judge_agreement --csv ... --sample 15 --secondary Llama-3.3-70B-Instruct
"""

import argparse
import csv
import glob
import hashlib
import json
import os
import random
import re
from pathlib import Path

import yaml
from openai import AzureOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from evals.config import AZURE_API_VERSION, AZURE_ENDPOINT, AZURE_KEY, CACHE_DIR, REPORTS_DIR
from evals.graders.rubric import _JUDGE_SYSTEM, _JUDGE_USER_TEMPLATE, _LEVEL_CRITERIA

_AGREE_CACHE = os.path.join(CACHE_DIR, "judge_agreement")

_DIMS = ["faithfulness", "level_match", "coverage", "clarity"]

_client = AzureOpenAI(
    api_key=AZURE_KEY,
    api_version=AZURE_API_VERSION,
    azure_endpoint=AZURE_ENDPOINT or None,
)


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=30))
def _call_judge(model: str, system: str, user: str) -> str:
    try:
        response = _client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
            max_completion_tokens=600,
        )
    except Exception:
        # Some deployments (Mistral, etc.) reject max_completion_tokens
        response = _client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
            max_tokens=600,
        )
    return response.choices[0].message.content.strip()


def _parse_scores(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    return json.loads(cleaned)


def _cache_key(model: str, output: str, level: int, expected_topics: list) -> str:
    raw = f"{model}||{output}||{level}||{sorted(expected_topics)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def _judge_with_model(model: str, paper_excerpt: str, output: str, level: int, expected_topics: list) -> dict:
    os.makedirs(_AGREE_CACHE, exist_ok=True)
    key = _cache_key(model, output, level, expected_topics)
    cache_file = os.path.join(_AGREE_CACHE, f"{key}.json")
    if os.path.exists(cache_file):
        return json.load(open(cache_file))

    user = _JUDGE_USER_TEMPLATE.format(
        paper_excerpt=paper_excerpt[:2000],
        expected_topics=", ".join(expected_topics),
        level=level,
        level_criteria=_LEVEL_CRITERIA.get(level, ""),
        output=output,
    )
    raw = _call_judge(model, _JUDGE_SYSTEM, user)
    scores = _parse_scores(raw)
    result = {dim: int(scores.get(dim, 0)) for dim in _DIMS}
    with open(cache_file, "w") as f:
        json.dump(result, f)
    return result


def _spearman(x: list, y: list) -> float:
    """Spearman rank correlation, no scipy dependency."""
    n = len(x)
    if n < 2:
        return float("nan")

    def rank(vals):
        sorted_vals = sorted((v, i) for i, v in enumerate(vals))
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and sorted_vals[j + 1][0] == sorted_vals[i][0]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[sorted_vals[k][1]] = avg
            i = j + 1
        return ranks

    rx, ry = rank(x), rank(y)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    dy = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    if dx * dy == 0:
        return float("nan")
    return num / (dx * dy)


def _load_latest_report(csv_path: str) -> dict:
    """Find the JSON report matching this CSV (same timestamp suffix)."""
    name = Path(csv_path).stem  # eval_<model>_<ts> or comparison_all_models_<ts>
    parts = name.split("_")
    ts = "_".join(parts[-2:])  # YYYYMMDD_HHMMSS
    json_path = os.path.join(REPORTS_DIR, f"report_{ts}.json")
    if os.path.exists(json_path):
        return json.load(open(json_path))
    # Fallback: most recent report
    reports = sorted(Path(REPORTS_DIR).glob("report_*.json"))
    if reports:
        return json.load(open(reports[-1]))
    return {}


def _build_case_index_from_results(results: list) -> dict:
    """Index results by (paper, level, model) for output lookup."""
    return {(r["paper"], r["level"], r.get("model", "")): r for r in results}


def cmd_run(args) -> None:
    csv_paths = glob.glob(args.csv) if "*" in args.csv else [args.csv]
    if not csv_paths:
        print(f"No CSV match: {args.csv}")
        raise SystemExit(1)
    csv_path = sorted(csv_paths)[-1]
    print(f"Using CSV: {csv_path}")

    rows = list(csv.DictReader(open(csv_path)))
    print(f"Loaded {len(rows)} rows.")

    # Load corresponding JSON to recover full explanations + paper excerpts
    cases_yaml_path = os.path.join(os.path.dirname(__file__), "cases.yaml")
    with open(cases_yaml_path) as f:
        cases_yaml = yaml.safe_load(f)
    paper_topics = {Path(p["path"]).stem: p["expected_topics"] for p in cases_yaml["papers"]}

    # Use the most recent report JSON to get explanation text
    reports = sorted(Path(REPORTS_DIR).glob("report_*.json"), reverse=True)
    if not reports:
        print("No report JSON found — agreement check needs explanation text.")
        raise SystemExit(1)

    # Build a map (paper_stem, level, model) → explanation
    expl_map = {}
    excerpt_map = {}
    for report_path in reports:
        report = json.load(open(report_path))
        for r in report.get("results", []):
            paper_stem = Path(r["paper"]).stem
            key = (paper_stem, r["level"], r.get("model", ""))
            if key not in expl_map:
                expl_map[key] = r["explanation"]
            excerpt_map[paper_stem] = excerpt_map.get(paper_stem, "")  # placeholder

    # Get excerpts directly via dataset.py
    from evals.dataset import get_excerpts
    for paper_stem in paper_topics:
        path = f"evals/papers/{paper_stem}.pdf"
        if os.path.exists(path):
            excerpt_map[paper_stem] = get_excerpts(path)["explain"]

    # Sample
    random.seed(42)
    available = [r for r in rows if (Path(r["paper"]).stem if r["paper"].endswith(".pdf") else r["paper"], int(r["level"]), r["model"]) in expl_map]
    sample = random.sample(rows, min(args.sample, len(rows)))
    print(f"Sampling {len(sample)} cases for re-judging by {args.secondary}...")

    primary_scores = {dim: [] for dim in _DIMS}
    secondary_scores = {dim: [] for dim in _DIMS}
    detail_rows = []

    for i, row in enumerate(sample):
        paper_stem = Path(row["paper"]).stem if row["paper"].endswith(".pdf") else row["paper"]
        level = int(row["level"])
        model = row["model"]
        topics = paper_topics.get(paper_stem, [])
        expl = expl_map.get((paper_stem, level, model))
        excerpt = excerpt_map.get(paper_stem, "")
        if not expl or not excerpt:
            print(f"  [{i+1}/{len(sample)}] skip {paper_stem} L{level} {model} — missing data")
            continue

        try:
            sec = _judge_with_model(args.secondary, excerpt, expl, level, topics)
        except Exception as e:
            print(f"  [{i+1}/{len(sample)}] skip — secondary judge error: {e}")
            continue

        for dim in _DIMS:
            primary_scores[dim].append(int(row[dim]))
            secondary_scores[dim].append(sec[dim])

        detail_rows.append({
            "paper": paper_stem, "level": level, "model": model,
            **{f"primary_{d}": int(row[d]) for d in _DIMS},
            **{f"secondary_{d}": sec[d] for d in _DIMS},
        })
        print(f"  [{i+1}/{len(sample)}] {paper_stem} L{level} {model[:25]}: P={[int(row[d]) for d in _DIMS]} S={[sec[d] for d in _DIMS]}")

    if not detail_rows:
        print("No usable samples.")
        raise SystemExit(1)

    print(f"\n--- Inter-judge agreement (Spearman ρ, n={len(detail_rows)}) ---")
    print(f"  Primary judge:   DeepSeek-V3.2")
    print(f"  Secondary judge: {args.secondary}")
    print()
    print(f"{'Dimension':<15} {'ρ':>8}")
    print("-" * 25)
    rhos = {}
    for dim in _DIMS:
        rho = _spearman(primary_scores[dim], secondary_scores[dim])
        rhos[dim] = rho
        print(f"{dim:<15} {rho:>8.3f}")
    overall = sum(rhos.values()) / len(rhos)
    print(f"{'mean':<15} {overall:>8.3f}")
    print()

    # Save detail CSV
    ts = re.search(r"(\d{8}_\d{6})", csv_path).group(1) if re.search(r"\d{8}_\d{6}", csv_path) else "agreement"
    out_path = os.path.join(REPORTS_DIR, f"judge_agreement_{ts}.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=detail_rows[0].keys())
        writer.writeheader()
        writer.writerows(detail_rows)

    summary_path = os.path.join(REPORTS_DIR, f"judge_agreement_{ts}_summary.json")
    json.dump({
        "primary_judge": "DeepSeek-V3.2",
        "secondary_judge": args.secondary,
        "n": len(detail_rows),
        "spearman_per_dim": rhos,
        "spearman_mean": overall,
    }, open(summary_path, "w"), indent=2)

    print(f"Detail CSV: {out_path}")
    print(f"Summary:    {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inter-judge agreement check")
    parser.add_argument("--csv", required=True, help="Comparison CSV (glob OK)")
    parser.add_argument("--sample", type=int, default=15, help="Number of cases to re-judge (default 15)")
    parser.add_argument("--secondary", default="Llama-3.3-70B-Instruct", help="Secondary judge model")
    args = parser.parse_args()
    cmd_run(args)


if __name__ == "__main__":
    main()
