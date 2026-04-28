# ARPX

Adaptive Research Paper Explainer. Streamlit → local RAG → n8n webhook → LLM → display.

## Two-phase pipeline

Phase 1 `analyze_paper(pdf)` (local, no n8n):
1. Extract text (PyMuPDF), chunk sliding-window, embed (all-MiniLM-L6-v2), store in Weaviate as source="main"
2. Extract references (max 3), fetch via Semantic Scholar, embed+store as source="reference"
3. Retrieve top-5 main + top-2 reference chunks → Azure OpenAI → topic bullet list

Phase 2 `explain_paper(level, topics)` (calls n8n):
1. Ping n8n health check — abort if unreachable
2. Retrieve top-5+2 chunks, POST to N8N_URL with {stage, paper_excerpt, level, topics}, timeout=300s
3. n8n runs ExplainerAgent + MermaidAgent → {text_explanation, mermaid_code}
4. Save to SQLite, display in Streamlit

## Tech stack

| Component | Detail |
|---|---|
| Frontend | Streamlit, port 8051 |
| LLM | Azure OpenAI — topic extraction + n8n explanation |
| Vector DB | Weaviate, collection `PaperChunk`, fields: text, source, vector |
| Orchestration | n8n external via webhook — never called directly except via `api_client.py` |
| Embeddings | sentence-transformers all-MiniLM-L6-v2, loaded once at import |
| Persistence | SQLite `arpx.db` at project root, table `Explanations` |
| PDF | PyMuPDF (fitz) |

## Env vars (.env at root)

- `AZURE_OPENAI_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION`
- `N8N_URL` — docker-compose sets to `http://n8n:5678/webhook/arpx/orchestrate`

Azure deployment names are course-specific (e.g. `gpt-5-chat`, `gpt-4.1-mini`). NOT standard OpenAI names.

Eval-only vars: see `evals/CLAUDE.md`.

## Docker stack

3 containers: `app` (Streamlit), `weaviate`, `n8n`.
n8n mounts `./n8n_workflows` → `/data` inside container.
After `docker compose up`, import `n8n_workflows/arpx-mvp.json` manually and activate — see `n8n_workflows/setup-n8n.md`.
Weaviate needs warm-up after cold start; `create_schema()` is idempotent.

## Explanation levels

Levels 1–10 map to per-level system prompts in `n8n_workflows/prompts.yaml` under:
- `explainer.levels[N].system`
- `chat.levels[N].system`

Mermaid agent has single prompt with level-aware complexity rules embedded.
Shared output constraints in `shared.constraints`.

## Key invariants

- Weaviate cleared on every `analyze_paper()` — single-paper-at-a-time design
- RAG indexes both main paper AND up to 3 references; `source` field distinguishes at retrieval
- prompts.yaml read by n8n at runtime from `/data/prompts.yaml` — edit and save, no reimport needed
- Semantic Scholar: 3s min interval between requests enforced by global `LAST_REQUEST_TIME`
