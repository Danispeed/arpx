# evals/

Two eval suites under one entry point (`evals/run.py`):
- **`evals/chatbot/`** — chatbot/explanation eval (LLM rubric + Mermaid grading + DSPy optimization). No Docker needed.
- **`evals/rag/`** — RAG evaluation (faithfulness, retrieval k-sweep, chunking comparison). Requires Docker + Weaviate.

Shared at top level: `config.py` (models, paths, keys), `dataset.py` (PDF loading), `cases.yaml`.

## Commands

Chatbot eval (no Docker):
```bash
python -m evals.run estimate              # dry-run: predict cost
python -m evals.run evaluate              # score all cases, save to evals/reports/
python -m evals.run check-baseline        # compare latest report to baseline.json
python -m evals.run compare-models        # multi-model comparison
python -m evals.chatbot.optimize --levels 1,5,7 --budget 5
```

RAG eval (Docker stack must be running):
```bash
python -m evals.run index                 # index papers into Weaviate
python -m evals.run rag-eval              # faithfulness / relevancy / precision
python -m evals.run k-sweep               # retrieval k sweep
python -m evals.run reference-ratio       # main vs reference chunk ratio
python -m evals.run chunking              # chunking strategy comparison
```

## What changes when you run

- `evaluate`: saves JSON report to `evals/reports/`
- `optimize`: rewrites `n8n_workflows/prompts.yaml` with better system prompts
- RAG commands: write CSVs to `evals/` and PDFs to `evals/figures/`
- Nothing else: no weights, no DB changes

## Eval grid

`evals/cases.yaml` — 5 papers × 10 levels = 50 cases. See README.md to add papers.

## Graders

**`chatbot/graders/rubric.py`** — LLM-as-judge using `ARPX_JUDGE_MODEL` (default: DeepSeek-V3.2).
4 dimensions × 0-5: faithfulness, level_match, coverage, clarity. Normalized score = total/20.
Uses temperature=0.0. Uses DIFFERENT model from generator to avoid self-fingerprint bias.

**`chatbot/graders/mermaid.py`** — deterministic, no LLM. 5 binary rules:
parse_ok (mmdc), node_count ≤10, no subgraph, no `&`/`/` outside quotes, arrow labels ≤3 words.
`mmdc` not installed → parse check skipped (treated as pass).

**`rag/rag_types.py`** — custom RAG evaluation (faithfulness, answer_relevancy, context_precision)
with three retrieval strategies (naive, LLM-query, fusion). Requires Docker. Run via `rag-eval` command.

## DSPy optimization (chatbot/optimize.py)

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
