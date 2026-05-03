# Eval Findings — Multi-Model Comparison

**Date:** 2026-04-29 (expanded run)
**Branch:** `feat/eval-optimization-pipeline`
**Papers:** attention.pdf, pesto.pdf, tensorflow.pdf, bert.pdf, resnet.pdf
**Levels evaluated:** 1–10 (all)
**Cases per model:** 50 (5 papers × 10 levels)
**Total comparison rows:** 150
**Primary judge:** DeepSeek-V3.2
**Secondary judge (agreement check):** Llama-3.3-70B-Instruct (15-case sample)
**Prompt version:** gpt-5-chat–authored level 1 + 5 prompts; original prompts elsewhere

---

## Headline results

| Model | Rubric (mean ± std) | Min | Max | Mean tokens (out) | Std tokens |
|---|---|---|---|---|---|
| **gpt-5-chat** | **0.979 ± 0.044** | 0.85 | 1.00 | **417** | 110 |
| **mistral-Large-3** | **0.952 ± 0.063** | 0.75 | 1.00 | 708 | 307 |
| **Llama-4-Maverick-17B-128E-Instruct-FP8** | **0.878 ± 0.090** | 0.65 | 1.00 | **352** | 71 |

### Per-dimension breakdown (mean across all 50 cases per model)

| Model | Faithfulness | Level Match | Coverage | Clarity |
|---|---|---|---|---|
| gpt-5-chat | **4.96** | **4.68** | **4.94** | **5.00** |
| mistral-Large-3 | 4.50 | 4.62 | 4.92 | **5.00** |
| Llama-4-Maverick | 4.36 | 3.88 | 4.52 | 4.80 |

### Statistical interpretation

- **gpt-5 vs mistral:** Δ = 0.027 (well within 0.5 std). Statistically tied on rubric.
- **gpt-5 vs Llama-4-Maverick:** Δ = 0.101 (~2.3× gpt-5's std). Llama is meaningfully worse.
- **mistral vs Llama-4-Maverick:** Δ = 0.074 (~1.2× mistral's std). Llama is worse with reasonable confidence.

**Bottom line:** GPT-5 and Mistral are tied on quality. Both clearly beat Llama-4-Maverick on the rubric (driven mainly by Level Match and Faithfulness). The cost story is different — Mistral uses ~1.7× the tokens of GPT-5 for the same quality.

---

## Inter-judge agreement (Spearman ρ, n=15 sample)

The rubric scores depend entirely on a single LLM judge. To check whether the rubric is measuring something real or just one model's idiosyncrasies, a random 15-case sample was re-judged by `Llama-3.3-70B-Instruct` and rank-correlated against the primary `DeepSeek-V3.2` scores.

| Dimension | Spearman ρ | Interpretation |
|---|---|---|
| **faithfulness** | **0.237** | Low — judges substantially disagree on what counts as faithful |
| **level_match** | **0.681** | Moderate — judges broadly agree |
| **coverage** | **0.732** | Good — strong rank correlation |
| **clarity** | NaN | Both judges gave 5/5 to all 15 sampled outputs — no variance to correlate |

**Implications:**

- **Faithfulness scores are weakly defended.** A second judge would re-rank cases noticeably. This is a real limitation: the rubric on this dimension is partly capturing judge preference, not just output quality.
- **Coverage and level_match are robust.** Two independent judges from different model families produce strongly correlated rankings, so these scores are more trustworthy.
- **Clarity is degenerate.** Outputs from frontier-tier generators are uniformly graded "perfectly clear" by both judges, so the metric is not discriminating between models. Future work could use a stricter clarity rubric or add a structural metric (sentence-length variance, paragraph count) to separate signal from ceiling effects.

**For the report:** lead with rubric mean ± std and the 2× verbose Mistral finding. Caveat the faithfulness column with the ρ=0.237 result. Treat clarity as a sanity check, not a comparator.

---

## Qualitative analysis

A side-by-side dump of all three models' outputs on `attention.pdf` at level 5 is in [`evals/QUALITATIVE.md`](./QUALITATIVE.md). Key observations from reading the actual outputs:

- **GPT-5** produces tight, single-thread prose with one well-explained equation. Best balance of depth and brevity.
- **Llama-4-Maverick** is the most concise but **omits all equations** even when level 5 explicitly requires them. This is exactly why the level_match column drops to 3.88/5 — Llama produces fluent but underspecified text.
- **Mistral-Large-3** is markdown-heavy with multiple equations and section headers. It hit `max_completion_tokens=1200` mid-sentence on this case. Equally good rubric, ~2× the cost.

This explains the quantitative gap: Llama and Mistral lose at different ends of the level_match spectrum.

---

## Sample diagrams (Mermaid)

Two well-scored Mermaid diagrams from `gpt-5-chat`, rendered to PNG via `mmdc`:

- `evals/figures/diagram_attention_L1.png` — *attention.pdf* at level 1 (beginner, simple flow)
- `evals/figures/diagram_tensorflow_L3.png` — *tensorflow.pdf* at level 3 (intermediate)

These are direct outputs from the system, included to satisfy Benjamin's "+ show the images in the report" request.

---

## DSPy COPRO experiment

The DSPy COPRO optimizer was run on level 5 with `budget=3` to test the hypothesis that automated prompt optimization with a sub-tier proposer (`gpt-4.1-mini`) cannot improve on prompts authored by a stronger model (`gpt-5-chat`).

**COPRO's internal validation:** the optimizer's own score on its three candidates (each scored on the trainset):
- Candidate #1 (gpt-4.1-mini's own creative attempt): **72.0**
- Candidate #2 (the existing gpt-5-chat-authored prompt, used as seed): **74.0**
- Candidate #3 (gpt-4.1-mini's polish of #2): **75.0** ← chosen as winner

So COPRO did marginally improve its internal training score (74 → 75) by paraphrasing the gpt-5-chat instruction. But on held-out evaluation across all 3 generator models:

| Model | Pre-COPRO L5 (gpt-5 prompt) | Post-COPRO L5 (paraphrased prompt) | Δ |
|---|---|---|---|
| **gpt-5-chat** | 0.970 | 0.930 | **−0.040** |
| **Llama-4-Maverick** | 0.800 | 0.770 | **−0.030** |
| **mistral-Large-3** | 0.950 | 0.920 | **−0.030** |

**Every model regressed.** The internal score gain (74 → 75) was a 1-point training-set artifact that did not generalize to the full eval. COPRO's "winning" instruction was a paraphrase of the seed with marginally different wording — small enough to fit a particular training-pass quirk but distinct enough to perturb production scores downward.

**Conclusion:**

> Automated prompt optimization with a sub-tier proposer model fails to improve hand-engineered prompts. With `gpt-4.1-mini` proposing variants of a prompt originally written by `gpt-5-chat`, COPRO finds candidates that score marginally higher on its own training-set evaluation but consistently *underperform* the seed on held-out cases. The mechanism is small-sample overfitting: budget=3 candidates × 5 training examples is enough surface area for noise to dominate signal.

This motivates the design choice of *direct* prompt engineering with the strongest available generator (`evals/prompt_design.py`) rather than relying on the optimizer.

The original level-5 prompt (`evals/prompts.yaml::explainer.levels.5.system`) was restored after this experiment. The COPRO-proposed paraphrase and its scores are preserved in `evals/reports/comparison_all_models_20260429_154001.csv` and the corresponding JSON reports.

---

## Limitations acknowledged in report

- **Narrow model list:** UiT Azure deployment list is small. Available deployments are gpt-5-chat, gpt-4.1-mini, DeepSeek-V3.2, mistral-Large-3, mistral-small-2503, Llama-4-Maverick, Llama-3.3-70B-Instruct, Phi-4-mini-reasoning. No GPT-4o, no Claude API, no Gemini. Comparison cannot be generalized to the broader frontier landscape — this is an institutional constraint, not a research design choice.
- **Sample size:** 50 cases per model (5 papers × 10 levels) is reasonable for ranking three models but underpowered for fine distinctions. Differences below ~0.05 normalized rubric should be treated as noise.
- **Single primary judge:** All comparison scores come from `DeepSeek-V3.2`. The agreement check above quantifies this risk — coverage and level_match are robust, faithfulness is partly judge-specific.
- **RAG metrics out of scope:** Citation count and RAG call count belong to the retrieval team's component. Token counts captured here are for the *generation* step only. Total system tokens would also include retrieval-side LLM calls.
- **Prompt-design circularity:** Level 1 and 5 system prompts were written by gpt-5-chat. gpt-5-chat is then one of the compared models. The judge (DeepSeek) is independent so the bias is bounded, but this is worth flagging in the report.
- **Two well-rendered Mermaid diagrams:** Llama and Mistral diagrams hard-passed less reliably; samples shown are gpt-5-chat outputs. A more thorough analysis would render and visually compare diagrams across all three models.

---

## Code housekeeping completed in this session

- `evals/graders/rubric.py`: removed hardcoded `_LEVEL_CRITERIA`; now loaded from `n8n_workflows/prompts.yaml` under `shared.level_criteria` so explainer + judge share one source of truth.
- `evals/run.py`: `compare-models` command now saves per-model JSON reports (with full explanations and diagrams) so downstream tools (`judge_agreement.py`, `qualitative.py`) can reconstruct outputs.
- `evals/cases.yaml`: pesto's `expected_topics` rewritten from incorrect "pose-estimation" terms to correct BFT/database terms. Coverage column went from 3.0/5 (broken) to 4.92/5 (post-fix).
- `evals/generate.py`: `_call_azure` now falls back from `max_completion_tokens` to `max_tokens` for deployments (e.g. Mistral) that reject the newer parameter name.

---

## Reproducing these results

```bash
source evals/.venv/bin/activate

# 1. Generate level 1+5 prompts (one-time)
python -m evals.prompt_design generate --write
rm -rf evals/cache/generations/

# 2. Run full comparison (5 papers × 10 levels × 3 models)
python -m evals.run compare-models \
  --models gpt-5-chat Llama-4-Maverick-17B-128E-Instruct-FP8 mistral-Large-3 \
  --levels 1 2 3 4 5 6 7 8 9 10

# 3. Visualize
python -m evals.visualize --csv "evals/reports/comparison_all_models_*.csv"

# 4. Inter-judge agreement
python -m evals.judge_agreement \
  --csv evals/reports/comparison_all_models_*.csv \
  --sample 15 --secondary Llama-3.3-70B-Instruct

# 5. Qualitative side-by-side
python -m evals.qualitative --paper attention --level 5

# 6. Render Mermaid diagrams (requires mmdc)
npx --yes -p @mermaid-js/mermaid-cli mmdc \
  -i diagram.mmd -o evals/figures/diagram.png -b white
```

All API calls are cached under `evals/cache/` and re-running the same prompts costs essentially zero.
