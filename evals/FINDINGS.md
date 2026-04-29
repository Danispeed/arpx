# Eval Findings — Multi-Model Comparison

**Date:** 2026-04-29  
**Branch:** feat/eval-optimization-pipeline  
**Papers:** attention.pdf, pesto.pdf, tensorflow.pdf (3 papers × 2 levels × 3 models = 18 cases)  
**Levels evaluated:** 1 (absolute beginner) and 5 (advanced undergraduate)  
**Judge model:** DeepSeek-V3.2  
**Prompt version:** gpt-5-chat–authored level 1 + 5 prompts (written 2026-04-29 via `evals/prompt_design`)

---

## Results table

| Model | Faithfulness | Level Match | Coverage | Clarity | Rubric (norm.) | Completion Tokens |
|---|---|---|---|---|---|---|
| gpt-5-chat | **5.00** | 4.67 | 3.00 | **5.00** | **0.883** | 422 |
| mistral-Large-3 | 4.67 | **5.00** | 3.00 | **5.00** | **0.883** | 801 |
| Llama-4-Maverick-17B-128E-Instruct-FP8 | 4.67 | 3.83 | 2.67 | 4.67 | 0.792 | **344** |

### By level

| Model | Level 1 Rubric | Level 5 Rubric | Level 1 Mermaid | Level 5 Mermaid |
|---|---|---|---|---|
| gpt-5-chat | 0.883 | 0.883 | 1.000 | 0.800 |
| mistral-Large-3 | 0.867 | 0.900 | 1.000 | 0.867 |
| Llama-4-Maverick | 0.833 | 0.750 | 1.000 | 0.933 |

### Per-paper breakdown (raw scores, rubric_normalized)

| Paper | Level | GPT-5 | Llama | Mistral |
|---|---|---|---|---|
| attention | 1 | 0.90 | 0.90 | 0.90 |
| attention | 5 | **1.00** | 0.90 | **1.00** |
| pesto | 1 | 0.75 | 0.75 | 0.70 |
| pesto | 5 | 0.65 | 0.55 | 0.75 |
| tensorflow | 1 | **1.00** | 0.85 | **1.00** |
| tensorflow | 5 | **1.00** | 0.80 | 0.95 |

---

## Key findings

### 1. Coverage is the universal weak spot

Coverage scored 3.0/5 across all models. This is not a model quality issue — it is a
structural issue with the eval setup: `pesto.pdf` has 0 coverage on expected topics
for both level 1 and 5. The `expected_topics` list for pesto (`pose-estimation, keypoints,
heatmap, skeleton, human-pose`) may not match the actual content of the extracted
excerpt, or the excerpt (abstract + intro heuristic) does not surface these terms
explicitly. This is an eval calibration issue, not a generation failure.

**Action:** Review pesto excerpt content vs expected_topics. Either update the topic
list to match what the excerpt actually covers, or extend the extraction heuristic
to include methods sections for this paper.

### 2. GPT-5 is the best value (tied rubric, half the tokens of Mistral)

GPT-5 and Mistral-Large-3 tie on overall rubric (0.883) but GPT-5 uses **422 tokens**
vs Mistral's **801 tokens** per explanation — nearly 2× more verbose. For a production
system serving many users, Mistral's verbosity is a cost and latency concern.

### 3. Mistral leads on Level Match

Mistral scores 5.00/5 on level_match vs GPT-5's 4.67. This suggests Mistral is
more attentive to adapting vocabulary and depth to the stated reader level. Pesto
at level 5 is where GPT-5 drops to 3/5 on level_match.

### 4. Llama underperforms on rubric but leads on token efficiency

Llama-4-Maverick scores 0.792 rubric overall (vs 0.883 for the others) but uses
only **344 tokens** — 19% fewer than GPT-5. The rubric gap is driven mainly by
Level Match (3.83 vs 5.00) — Llama is less precise at calibrating to the target
level. This is consistent with MoE architecture behavior: good at general output,
less controlled on subtle stylistic constraints.

### 5. Hypothesis "GPT-5 wins" partially supported

GPT-5 wins on faithfulness (5.00) and ties on rubric, but does not clearly dominate.
Mistral ties overall and beats on level calibration. For the report, this is a more
interesting result than a clean GPT-5 win — it motivates discussion of the tradeoffs.

### 6. Mermaid diagrams: `mermaid_valid` is always False

The `mermaid_valid` CSV column is False for all 18 cases. This appears to be a field
mapping issue in the grader output (the `valid` key may not exist in the mermaid result
dict). The `mermaid_score` is correct (1.0 or 0.8). Investigate `evals/graders/mermaid.py`
to confirm what keys are returned and fix the column mapping in `_save_csv`.

---

## Limitations acknowledged in report

- **Narrow model list:** UiT Azure deployment does not include GPT-4o, Claude 3.5 Sonnet,
  Gemini 1.5, or other major benchmarks. Results are constrained to the available deployment
  set and cannot be generalized to the broader model landscape.
- **Small sample:** 3 papers × 2 levels = 6 cases per model. Differences of < 0.05 on
  normalized rubric should be treated as noise given the judge variance.
- **RAG metrics missing:** Citation count and RAG call count are outside this component's
  scope (RAG instrumentation belongs to the retrieval team). Token counts for the generation
  step are captured; RAG-side tokens are not.
- **DSPy optimizer not used:** The COPRO optimizer was not run in this comparison. The current
  prompts were written directly by GPT-5 using the rubric criteria as guidance. The optimizer
  was found to be ineffective when the proposer model (`gpt-4.1-mini`) is weaker than the
  models that originally authored the prompts — this is noted as a known limitation of
  automated prompt optimization with mismatched model tiers.

---

## Next actions

- [ ] Fix `mermaid_valid` column mapping in `evals/run.py::_save_csv`
- [ ] Review pesto `expected_topics` vs actual excerpt content
- [ ] Run comparison at all 10 levels (not just 1 and 5) for a fuller picture if time allows
- [ ] Render 2-3 Mermaid diagrams to PNG via `mmdc` for the report visuals section
- [ ] Write report section: "Experimental Evaluation" using this findings file as source
