"""
Qualitative side-by-side: print all model outputs for a single (paper, level)
case as markdown for inspection in the report.

This complements the quantitative rubric scores — readers can see *what*
each model actually produced, not just what its averaged score was.

Usage:
    python -m evals.qualitative --paper attention --level 5
    python -m evals.qualitative --paper attention --level 5 --out evals/QUALITATIVE.md
"""

import argparse
import json
import os
from pathlib import Path

from evals.config import REPORTS_DIR


def _find_outputs(paper: str, level: int) -> list:
    """Walk all reports, collect (paper, level) entries across models."""
    reports = sorted(Path(REPORTS_DIR).glob("report_*.json"))
    seen = {}  # model -> (timestamp, entry)

    for report_path in reports:
        ts = report_path.stem.replace("report_", "")
        report = json.load(open(report_path))
        for r in report.get("results", []):
            paper_stem = Path(r["paper"]).stem if r["paper"].endswith(".pdf") else r["paper"]
            if paper_stem != paper:
                continue
            if r["level"] != level:
                continue
            model = r.get("model")
            if not model:
                continue  # Skip entries from old reports without model column
            # Keep most recent per model
            if model not in seen or seen[model][0] < ts:
                seen[model] = (ts, r)

    return [entry for _, entry in seen.values()]


def _render(paper: str, level: int, entries: list) -> str:
    md = []
    md.append(f"# Qualitative Comparison — {paper}.pdf at level {level}\n")
    md.append(f"This file shows the actual output text from each model for one fixed case, ")
    md.append(f"to complement the quantitative rubric scores in `FINDINGS.md`. ")
    md.append(f"Reading the outputs side-by-side surfaces stylistic and structural differences ")
    md.append(f"that aggregate scores cannot capture.\n\n")

    md.append(f"**Paper:** `{paper}.pdf`  \n")
    md.append(f"**Reader level:** {level}/10\n\n")
    md.append("---\n\n")

    md.append("## Rubric scores at a glance\n\n")
    md.append("| Model | Faith | Level | Cover | Clarity | Total | Tokens (out) |\n")
    md.append("|---|---|---|---|---|---|---|\n")
    for e in entries:
        r = e["rubric"]
        tok = e.get("completion_tokens", "—")
        model = e.get("model", "unknown")
        md.append(f"| `{model}` | {r['faithfulness']} | {r['level_match']} | {r['coverage']} | {r['clarity']} | {r['total']}/20 | {tok} |\n")
    md.append("\n---\n\n")

    md.append("## Model outputs\n\n")
    for e in entries:
        model = e.get("model", "unknown")
        md.append(f"### `{model}`\n\n")
        md.append("```text\n")
        md.append(e["explanation"].strip())
        md.append("\n```\n\n")
        notes = e["rubric"]
        md.append("**Judge notes:**\n")
        for dim in ("faithfulness", "level_match", "coverage", "clarity"):
            note_key = f"{dim}_note"
            note = notes.get(note_key, "").strip()
            if note:
                md.append(f"- *{dim}* ({notes[dim]}/5): {note}\n")
        md.append("\n---\n\n")

    md.append("## Commentary\n\n")
    md.append("*(Add 3-5 sentences observing where each model differs in style, depth, or structure. ")
    md.append("Examples of useful observations: which model uses more analogies, which over-explains, ")
    md.append("which sticks closest to the source text, which is most concise.)*\n")

    return "".join(md)


def main() -> None:
    parser = argparse.ArgumentParser(description="Qualitative side-by-side")
    parser.add_argument("--paper", required=True, help="Paper stem (e.g. attention)")
    parser.add_argument("--level", type=int, required=True, help="Reader level 1-10")
    parser.add_argument("--out", default="evals/QUALITATIVE.md", help="Output markdown file")
    args = parser.parse_args()

    entries = _find_outputs(args.paper, args.level)
    if not entries:
        print(f"No outputs found for paper={args.paper} level={args.level}")
        print(f"Available reports in {REPORTS_DIR}:")
        for r in sorted(Path(REPORTS_DIR).glob("report_*.json")):
            print(f"  {r.name}")
        raise SystemExit(1)

    print(f"Found {len(entries)} model outputs:")
    for e in entries:
        print(f"  - {e.get('model', 'unknown')}: rubric {e['rubric']['normalized']:.2f}")

    md = _render(args.paper, args.level, entries)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        f.write(md)
    print(f"\nWritten: {args.out}")


if __name__ == "__main__":
    main()
