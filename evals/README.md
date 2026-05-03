# ARPX Eval & Prompt Optimization Pipeline

Automated evaluation and DSPy-driven prompt optimization for ARPX's three agents
(Explainer, Mermaid, Chat). No model weights are trained — the process iterates over
plain-text system prompts in `n8n_workflows/prompts.yaml` and writes the best-scoring
variants back into that file.

## Quickstart

```bash
# 1. Activate the eval venv (created inside evals/, no torch required)
source evals/.venv/bin/activate

# 2. Copy your Azure credentials into the project root .env if not already done
#    Required vars: AZURE_OPENAI_KEY, AZURE_OPENAI_ENDPOINT

# 3. Predict cost before spending quota
python -m evals.run estimate

# 4. Generate purpose-built level 1 + 5 system prompts using gpt-5-chat
python -m evals.prompt_design generate --write
rm -rf evals/cache/generations/   # clear cache so new prompts take effect

# 5. Run multi-model comparison (levels 1 and 5, 3 models)
python -m evals.run compare-models --levels 1 5

# 6. Visualize results
python -m evals.visualize --csv "evals/reports/comparison_all_models_*.csv"

# 7. (Optional) Score current prompts.yaml across all levels
python -m evals.run evaluate
```

---

## What this pipeline does

For each combination of paper × reader level (1–10), the pipeline:

1. Extracts a ~3000-char excerpt from the paper PDF (abstract + intro heuristic).
2. Calls the Explainer agent with the current per-level system prompt from `prompts.yaml`.
3. Calls the Mermaid agent with the level-aware diagram prompt.
4. Grades both outputs without human review:
   - Explainer → LLM-as-judge rubric (4 dimensions, 0–5 each)
   - Mermaid → deterministic hard-rule checker (5 binary rules)
5. Saves a JSON + printed summary report.
6. Optionally runs DSPy COPRO to search for a better system prompt for weak levels
   and writes the winning instruction back into `prompts.yaml`.

The optimized artefact is always plain text in `prompts.yaml`. Model weights never change.

---

## prompts.yaml format contract (important)

The n8n workflow currently parses `n8n_workflows/prompts.yaml` with regex-based extraction
for system prompts. That parser expects specific YAML formatting.

Required formatting rules:

- Every per-level system prompt must use block literal style:
  ```yaml
  system: |
    You are ...
  ```
- Do **not** switch system prompts to single-quoted or double-quoted inline scalars.
  Example to avoid:
  ```yaml
  system: "You are ..."
  ```
- Keep `shared.constraints` items double-quoted strings.

If these rules are violated, n8n may fail to extract prompts and the model can fall back
to default generic responses (for example: "Hello there! How can I help you today?").

When generating or optimizing prompts in evals, keep this formatting intact before
committing changes.

---

## Why this is not ML training

Standard fine-tuning updates a model's weights on labelled examples. This pipeline
does neither: the Azure OpenAI weights are frozen and inaccessible. What changes is the
*text* of the system prompts inside `n8n_workflows/prompts.yaml`.

DSPy's COPRO optimizer is a search algorithm: it proposes alternative instruction strings,
scores them with the rubric judge, and keeps the best one. The search space is the space
of English sentences, not weight matrices. The result is a text file you can read,
edit, and version-control — not a model artifact.

---

## Architecture

```
evals/papers/*.pdf
      │
      ▼
evals/dataset.py          ← fitz (PyMuPDF) PDF extraction, excerpt cache
      │
      ├─── explain excerpt (≤3 000 chars)
      └─── topics context (≤800 chars)
              │
              ▼
evals/generate.py         ← direct Azure OpenAI calls, generation cache
      │
      ├─ generate_explanation(excerpt, topics, level)   → text
      └─ generate_mermaid(excerpt, topics, level)       → mermaid syntax
              │
              ▼
evals/graders/
  ├─ rubric.py            ← LLM-as-judge, 4 dims × 0-5, judge cache
  └─ mermaid.py           ← deterministic, 5 binary rules, no LLM needed
              │
              ▼
evals/run.py              ← asyncio runner, regression gate, JSON/CSV report
evals/optimize.py         ← DSPy COPRO per level, writes back to prompts.yaml
```

The harness bypasses n8n and Weaviate entirely — it reads PDFs directly with fitz and
calls Azure OpenAI via the Python SDK. This makes it runnable without Docker.

---

## The eval grid

A *case* is one (paper, level) pair. The current grid:

```yaml
# evals/cases.yaml
papers:
  - path: evals/papers/attention.pdf        # "Attention Is All You Need"
    expected_topics: [transformer, attention, self-attention, ...]
  - path: evals/papers/pesto.pdf            # Pesto system paper
    expected_topics: [pose-estimation, keypoints, heatmap, ...]
  - path: evals/papers/tensorflow.pdf       # TensorFlow system paper
    expected_topics: [tensorflow, dataflow-graph, tensor, ...]
levels: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
```

3 papers × 10 levels = **30 cases** per run. 

To add a paper: drop the PDF into `evals/papers/`, add an entry to `cases.yaml`
with its expected_topics, and re-run evaluate. The excerpt cache keyed on the
PDF hash means existing papers are not re-extracted.

---

## Graders explained

### Mermaid grader (`evals/graders/mermaid.py`)

Fully deterministic — no LLM involved. Runs five binary rules:

| Rule | What it enforces |
|---|---|
| **parse_ok** | `mmdc -i diagram.mmd -o /dev/null` exits 0 — syntactically valid Mermaid |
| **node_count_ok** | ≤ 10 unique node IDs — keeps diagrams readable |
| **no_subgraph** | `subgraph` keyword absent — subgraphs break the visual layout in streamlit-mermaid |
| **no_special_chars** | No `&` or `/` outside quoted labels — these break Mermaid's parser |
| **arrow_labels_ok** | Every `\|label\|` is ≤ 3 whitespace-separated words — prevents unreadable edge clutter |

Score = fraction of rules passed (0.0, 0.2, 0.4, 0.6, 0.8, or 1.0).
If `mmdc` is not installed the parse check is skipped with a warning (score treats it as passed).

### Rubric grader (`evals/graders/rubric.py`)

LLM-as-judge using **DeepSeek-V3.2** (a different model family from the generator
`gpt-5-chat`, which prevents the judge from rewarding its own stylistic fingerprint).
Judge temperature is 0.0 for reproducibility.

Four dimensions, each scored 0–5:

| Dimension | What it measures |
|---|---|
| **faithfulness** | Every claim in the output is directly supported by the excerpt. Invented facts or numbers score 0. |
| **level_match** | Vocabulary and depth match the stated level. The judge is given per-level criteria (e.g. "level 1: no technical terms, everyday analogies, no equations"). |
| **coverage** | All `expected_topics` from `cases.yaml` are meaningfully addressed. |
| **clarity** | Logical flow; no confusing jumps; coherent end-to-end. |

Total = sum (0–20). Normalized score = total / 20 (0.0–1.0).
Results are cached keyed on `(output_hash, level, judge_model)`, so re-running
evaluate on unchanged prompts is essentially free.

### RAG metrics (`evals/graders/rag_metrics.py`)

Optional Ragas wrapper (faithfulness, answer_relevancy, context_precision).
Not currently wired into the main eval loop — available for standalone use.

---

## How to run

### `python -m evals.run estimate`

Dry-run. Prints predicted call counts and token estimates without touching the API.
Useful before a full optimization run to gauge quota impact.

```
Eval estimate for 30 cases:
  Explanation generation: ~30 calls, ~90,000 tokens
  Mermaid generation:     ~30 calls, ~24,000 tokens
  Rubric judging:         ~30 calls, ~90,000 tokens
  Total:                  ~90 calls, ~204,000 tokens
```

### `python -m evals.run evaluate`

Scores all 30 cases against the current `prompts.yaml`. Saves:
- `evals/reports/report_<timestamp>.json` — full per-case scores
- Printed summary table + regression check against the most recent previous report

Example output (actual baseline run, 2026-04-23):

```
--- Eval summary ---
Level      Rubric   Mermaid    N
----------------------------------
L1          0.833     1.000    3
L2          0.883     1.000    3
L3          0.917     1.000    3
L4          0.917     0.800    3
L5          0.783     0.800    3
L6          0.883     0.800    3
L7          0.867     0.800    3
L8          0.917     0.800    3
L9          0.900     0.800    3
L10         0.983     0.800    3
overall     0.888     0.860   30
```

### `python -m evals.run compare-models [--models M1 M2 ...] [--levels L1 L2 ...]`

Runs the eval across multiple generator models and saves a merged comparison CSV.
Defaults to levels 1 and 5 and the three configured comparison models.
Per-model CSVs are saved after each model completes, so a crash on a later model does
not lose earlier results.

```bash
# Default: gpt-5-chat, Llama-4-Maverick, mistral-Large-3 at levels 1 and 5
python -m evals.run compare-models

# Custom model list
python -m evals.run compare-models --models gpt-5-chat DeepSeek-V3.2 --levels 1 5
```

Output: `evals/reports/comparison_all_models_<timestamp>.csv`

---

### `python -m evals.prompt_design generate [--write]`

Uses `gpt-5-chat` (the strongest available UiT Azure deployment) to write purpose-built
system prompts for levels 1 and 5. Prompts are anchored to the rubric dimensions so the
model is explicitly asked to maximise faithfulness, level_match, coverage, and clarity.

Without `--write`, prints the generated prompts as a dry run.
With `--write`, updates `n8n_workflows/prompts.yaml` directly.

```bash
python -m evals.prompt_design generate           # dry run
python -m evals.prompt_design generate --write   # write to prompts.yaml
rm -rf evals/cache/generations/                  # clear cache after writing
```

---

### `python -m evals.visualize --csv <path> [--out <dir>]`

Generates three PNG charts from a comparison CSV and prints a summary table to stdout.
Requires `matplotlib` and `pandas` (included in the eval venv).

```bash
python -m evals.visualize --csv "evals/reports/comparison_all_models_*.csv" --out evals/figures/
```

Outputs:
- `rubric_by_model.png` — grouped bar chart, one bar per rubric dimension per model
- `tokens_by_model.png` — mean completion tokens per model
- `rubric_by_level.png` — line chart of normalized rubric score by level per model

---

### `python -m evals.run evaluate [--model M] [--levels L1 L2 ...]`

Scores all cases (or a subset) against the current `prompts.yaml`. Saves a JSON report
and a CSV. Supports overriding the generator model inline without editing `.env`.

```bash
python -m evals.run evaluate                        # all levels, default model
python -m evals.run evaluate --model mistral-Large-3 --levels 1 5
```

---

### `python -m evals.optimize [--levels N] [--budget N] [--optimizer copro|mipro]`

Runs DSPy COPRO (default) or MIPROv2 per specified level. For each level:

1. Filters the trainset to cases at that level.
2. Runs the optimizer with `breadth=budget, depth=2` candidate proposals.
3. Evaluates each candidate against the rubric metric.
4. Writes the best-scoring instruction string into `prompts.yaml` under
   `explainer.levels[N].system`.

After completion, re-run `evaluate` to confirm improvement.

Common invocations:

```bash
# Optimize the three weakest levels from the baseline
python -m evals.optimize --levels 1,5,7 --budget 5

# Full optimization pass, all levels
python -m evals.optimize --budget 5

# Higher budget for more thorough search (more expensive)
python -m evals.optimize --levels 5 --budget 10

# Use MIPROv2 instead of COPRO (experimental, requires more quota)
python -m evals.optimize --levels 5 --budget 5 --optimizer mipro
```

---

## Interpreting a report

The JSON report at `evals/reports/report_<timestamp>.json` contains one object per case:

```json
{
  "paper": "evals/papers/attention.pdf",
  "level": 9,
  "explanation": "The central novelty here is...",
  "diagram": "flowchart LR\n  A[...",
  "rubric": {
    "faithfulness": 5,
    "level_match": 4,
    "coverage": 4,
    "clarity": 5,
    "total": 18,
    "normalized": 0.9,
    "faithfulness_note": "All claims grounded in excerpt.",
    "level_match_note": "Peer-level discourse, appropriate formalism.",
    ...
  },
  "mermaid": {
    "parse_ok": true,
    "node_count": 8,
    "node_count_ok": true,
    "no_subgraph": true,
    "no_special_chars": true,
    "arrow_labels_ok": false,
    "arrow_label_lengths": [2, 4, 2, 3],
    "hard_pass": false,
    "score": 0.8
  }
}
```

**Reading the summary table:**
- `Rubric` is the mean normalized rubric score across all 3 papers for that level (0–1).
- `Mermaid` is the mean deterministic score.
- A drop > 0.20 from the previous report triggers a regression warning and exits with code 2.

**What "good" looks like:** rubric ≥ 0.90 across all levels, mermaid = 1.00 across all levels.
The baseline shows mermaid consistently at 0.80 for levels 4–10 — one hard rule (most likely
arrow label length) fails on complex diagrams. This is a systematic prompt issue, not a
level-specific one; optimization won't fix it since the mermaid grader is deterministic.

---

## Model configuration

Set via environment variables (`.env` in project root):

| Variable | Default | Role |
|---|---|---|
| `ARPX_GENERATOR_MODEL` | `gpt-5-chat` | Generates explanations and diagrams during eval |
| `ARPX_JUDGE_MODEL` | `DeepSeek-V3.2` | Scores rubric dimensions — different family from generator to avoid self-reward bias |
| `ARPX_PROPOSER_MODEL` | `gpt-4.1-mini` | DSPy proposes new prompt variants — cheap/fast, same family as generator is acceptable here |
| `ARPX_EVAL_CONCURRENCY` | `3` | Max parallel API calls (asyncio.Semaphore) |

All deployments are UiT Azure OpenAI endpoints. Never use standard model names like
`gpt-4o` or `gpt-3.5-turbo` — they do not exist in this environment.

**Why DeepSeek for judging:** using the same model to generate and judge creates
self-fingerprint bias — the model rewards its own stylistic choices rather than
actual quality. DeepSeek-V3.2 is a different model family with strong instruction
following for structured JSON output.

---

## Rate limits and cost

UiT students do not pay per-token directly, but each Azure deployment has
**TPM** (tokens per minute) and **RPM** (requests per minute) caps that are shared
across the course cohort.

Mitigations built into the harness:

- **Bounded concurrency** — `asyncio.Semaphore(ARPX_EVAL_CONCURRENCY)` (default 3).
  Set `ARPX_EVAL_CONCURRENCY=1` if hitting 429s.
- **Exponential backoff** — `tenacity` retries up to 5× with 2 → 30s backoff on 429/503.
- **Three-tier cache:**
  - `evals/cache/excerpts/` — PDF extraction, keyed on PDF hash. Run once per paper.
  - `evals/cache/generations/` — LLM outputs, keyed on `(model, system_hash, user_hash, temperature)`.
  - `evals/cache/judge/` — rubric scores, keyed on `(output_hash, level, judge_model)`.

  Re-running `evaluate` on unchanged prompts hits the generation and judge caches
  and makes essentially zero API calls.

**Order-of-magnitude call volumes** (cold cache, `--budget 5`, 30 cases):

| Step | Calls | Approx tokens |
|---|---|---|
| Baseline evaluate (30 cases) | ~90 | ~200 000 |
| Optimize 3 levels, budget 5 | ~375 | ~750 000 |
| Post-optimize evaluate | ~0 (cached) | ~0 |
| **Full 10-level optimize, budget 5** | **~1 250** | **~2 000 000** |

If a run hits persistent 429s, reduce concurrency first, then reduce `--budget`.

---

## Extending the pipeline

**Add a new paper:**
1. Drop the PDF into `evals/papers/`.
2. Add an entry to `evals/cases.yaml` with its `expected_topics`.
3. Run `python -m evals.run evaluate` — the new paper is included automatically.

**Add a new rubric dimension:**
1. Add the dimension name and scoring prompt to `_JUDGE_USER_TEMPLATE` in `evals/graders/rubric.py`.
2. Update the `result` dict construction to include the new key.
3. Update the total (currently `/20`) to reflect the new maximum.
4. Note: existing judge cache entries will not include the new dimension —
   delete `evals/cache/judge/` to force re-scoring.

**Swap in a local Ollama generator:**
```python
# In evals/config.py or at the top of a run script:
import dspy
dspy.configure(lm=dspy.LM("ollama/llama3.1:8b", api_base="http://localhost:11434"))
```
The harness, graders, and `prompts.yaml` are unchanged. Only the Azure SDK calls
in `generate.py` would need to switch to the Ollama endpoint — the eval logic is
model-agnostic.

**Raise the optimization budget:**
Increase `--budget` (default 5). Each unit adds one round of breadth candidates.
Budget 10 doubles the call count and search depth. Diminishing returns set in quickly;
5–8 is a practical ceiling for this size of trainset.

---

## Limitations

- **Rubric judge variance:** a single LLM judge has variance even at temperature 0.0.
  Scores are averaged over 3 papers per level to reduce noise, but a single run
  is not a statistically robust benchmark. Treat score differences < 0.05 as noise.
- **Single-turn chat eval only:** the Chat agent is not evaluated here. Multi-turn
  conversation coherence would require a dialogue simulation loop.
- **No golden references:** there are no human-written gold explanations to compare
  against. The rubric catches clear failures (wrong level, invented facts, missing topics)
  but cannot measure subtler qualities like elegance or insight.
- **mmdc dependency:** the Mermaid parse check requires `@mermaid-js/mermaid-cli`
  (`npm install -g @mermaid-js/mermaid-cli`). If not installed, the parse rule is
  skipped and diagrams are scored on 4/5 rules only.
- **Level 5 regression risk:** DSPy optimization with a small trainset can produce
  prompts that are too generic (this happened on the first optimization run for
  level 5 — the optimizer converged to a context-agnostic instruction that
  scored well on the narrow trainset but lost level calibration in production).
  Always compare the optimized prompt text visually before committing.
