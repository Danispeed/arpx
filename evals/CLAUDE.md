# evals/

Eval + DSPy prompt optimization. Runs WITHOUT Docker — bypasses n8n and Weaviate entirely.
Reads PDFs directly with fitz; calls Azure OpenAI via SDK.

## Commands

```bash
python -m evals.run estimate              # dry-run: predict cost
python -m evals.run evaluate             # score all cases, save to evals/reports/
python -m evals.run compare --baseline   # compare latest report to baseline.json
python -m evals.optimize --levels 1,5,7 --budget 5
python -m evals.optimize --optimizer mipro
```

## What changes when you run

- `evaluate`: saves JSON report to `evals/reports/`
- `optimize`: rewrites `n8n_workflows/prompts.yaml` with better system prompts
- Nothing else: no weights, no DB changes

## Eval grid

`evals/cases.yaml` — 3 papers × 10 levels = 30 cases.
Add paper: drop PDF in `evals/papers/`, add entry with `expected_topics` to `cases.yaml`.

## Three-tier cache (evals/cache/)

| Dir | Key | Invalidate when |
|---|---|---|
| `excerpts/` | PDF SHA-256 (16 hex) | PDF changes |
| `generations/` | hash(model + system + user + temperature) | prompts.yaml changes |
| `judge/` | hash(output + level + judge_model) | output or judge model changes |

Re-running evaluate on unchanged prompts ≈ 0 API calls. Delete cache dir when changing grader logic or judge model.

## Graders

**rubric.py** — LLM-as-judge using `ARPX_JUDGE_MODEL` (default: DeepSeek-V3.2).
4 dimensions × 0-5: faithfulness, level_match, coverage, clarity. Normalized score = total/20.
Uses temperature=0.0. Uses DIFFERENT model from generator to avoid self-fingerprint bias.

**mermaid.py** — deterministic, no LLM. 5 binary rules:
parse_ok (mmdc), node_count ≤10, no subgraph, no `&`/`/` outside quotes, arrow labels ≤3 words.
`mmdc` not installed → parse check skipped (treated as pass).

**rag_metrics.py** — Ragas wrapper (faithfulness, answer_relevancy, context_precision).
NOT wired into main eval loop — standalone use only.

## DSPy optimization (optimize.py)

COPRO (default): breadth=budget, depth=2. Seeds from existing per-level system prompt.
Metric = rubric.grade(normalized). Writes winning instruction string back to `prompts.yaml`.
MIPROv2 via `--optimizer mipro` (experimental, more quota).

Caution: small trainset can produce over-generic prompts. Inspect optimized prompts before committing.
Level 5 regressed on first optimization run.

## Env vars (eval-only)

- `ARPX_GENERATOR_MODEL` — model for generating explanations
- `ARPX_JUDGE_MODEL` — model for rubric grading (use different from generator)
- `ARPX_PROPOSER_MODEL` — model for DSPy COPRO instruction proposals
- `ARPX_EVAL_CONCURRENCY` — parallel API calls (default 3; set to 1 on 429)

Cold cache full optimize all levels budget=5 ≈ 1250 calls, ~2M tokens.
