"""
Generate report charts from eval CSV files.

Usage:
    python -m evals.visualize --csv evals/reports/comparison_all_models_*.csv
    python -m evals.visualize --csv evals/reports/comparison_all_models_*.csv --out evals/figures/
"""

import argparse
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

_RUBRIC_DIMS = ["faithfulness", "level_match", "coverage", "clarity"]
_DIM_LABELS = ["Faithfulness", "Level Match", "Coverage", "Clarity"]

_MODEL_SHORT = {
    "gpt-5-chat": "GPT-5",
    "Llama-4-Maverick-17B-128E-Instruct-FP8": "Llama-4-Mav",
    "mistral-Large-3": "Mistral-Large-3",
    "DeepSeek-V3.2": "DeepSeek-V3",
}


def _short(model: str) -> str:
    return _MODEL_SHORT.get(model, model[:20])


def plot_rubric_by_model(df: pd.DataFrame, out_dir: str) -> None:
    """Grouped bar chart: mean rubric score per dimension, grouped by model."""
    models = df["model"].unique().tolist()
    means = {m: [df[df["model"] == m][d].mean() for d in _RUBRIC_DIMS] for m in models}

    x = range(len(_RUBRIC_DIMS))
    width = 0.8 / max(len(models), 1)
    offsets = [i * width - (len(models) - 1) * width / 2 for i in range(len(models))]

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, model in enumerate(models):
        ax.bar([xi + offsets[i] for xi in x], means[model], width=width * 0.9, label=_short(model))

    ax.set_xticks(list(x))
    ax.set_xticklabels(_DIM_LABELS)
    ax.set_ylabel("Mean Score (0–5)")
    ax.set_ylim(0, 5.5)
    ax.set_title("Rubric Scores by Model")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    path = os.path.join(out_dir, "rubric_by_model.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_tokens_by_model(df: pd.DataFrame, out_dir: str) -> None:
    """Bar chart: mean completion tokens per model."""
    if "completion_tokens" not in df.columns or df["completion_tokens"].isna().all():
        print("No token data — skipping token chart.")
        return

    models = df["model"].unique().tolist()
    means = [df[df["model"] == m]["completion_tokens"].mean() for m in models]
    labels = [_short(m) for m in models]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(labels, means, color="steelblue", edgecolor="white")
    ax.bar_label(bars, fmt="%.0f", padding=3)
    ax.set_ylabel("Mean Completion Tokens")
    ax.set_title("Token Usage by Model")
    ax.grid(axis="y", alpha=0.3)

    path = os.path.join(out_dir, "tokens_by_model.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def plot_rubric_by_level(df: pd.DataFrame, out_dir: str) -> None:
    """Line chart: mean normalized rubric score by level, one line per model."""
    if "level" not in df.columns:
        return

    models = df["model"].unique().tolist()
    levels = sorted(df["level"].unique().tolist())

    fig, ax = plt.subplots(figsize=(8, 4))
    for model in models:
        sub = df[df["model"] == model]
        ys = [sub[sub["level"] == lv]["rubric_normalized"].mean() for lv in levels]
        ax.plot(levels, ys, marker="o", label=_short(model))

    ax.set_xlabel("Reader Level (1–10)")
    ax.set_ylabel("Normalized Rubric Score (0–1)")
    ax.set_title("Rubric Score by Level and Model")
    ax.set_xticks(levels)
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.grid(alpha=0.3)

    path = os.path.join(out_dir, "rubric_by_level.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


def print_summary_table(df: pd.DataFrame) -> None:
    models = df["model"].unique().tolist()
    print("\n--- Comparison table ---")
    header = f"{'Model':<35} {'Faith':>6} {'Level':>6} {'Cover':>6} {'Clarity':>8} {'Rubric':>7} {'Tokens':>7}"
    print(header)
    print("-" * len(header))
    for model in models:
        sub = df[df["model"] == model]
        faith = sub["faithfulness"].mean()
        level = sub["level_match"].mean()
        cover = sub["coverage"].mean()
        clar = sub["clarity"].mean()
        norm = sub["rubric_normalized"].mean()
        tok = sub["completion_tokens"].mean() if "completion_tokens" in sub.columns else float("nan")
        print(f"{_short(model):<35} {faith:>6.2f} {level:>6.2f} {cover:>6.2f} {clar:>8.2f} {norm:>7.3f} {tok:>7.0f}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="ARPX eval visualizer")
    parser.add_argument("--csv", required=True, help="Path to comparison CSV")
    parser.add_argument("--out", default="evals/figures", help="Output directory for charts")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        # Try glob
        matches = sorted(Path(".").glob(args.csv))
        if not matches:
            print(f"No CSV found: {args.csv}")
            raise SystemExit(1)
        csv_path = matches[-1]

    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows from {csv_path}")

    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)

    print_summary_table(df)
    plot_rubric_by_model(df, out_dir)
    plot_tokens_by_model(df, out_dir)
    plot_rubric_by_level(df, out_dir)

    print(f"\nAll charts saved to {out_dir}/")


if __name__ == "__main__":
    main()
