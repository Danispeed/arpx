# ARPX

Adaptive Research Paper Explainer. Streamlit → local RAG → n8n webhook → LLM → display.

## Two-phase pipeline

Phase 1 `analyze_paper(pdf)` (local, no n8n):
1. Extract text (PyMuPDF), chunk sliding-window (300 words, 50-word overlap), embed (all-MiniLM-L6-v2), store in Weaviate as source="main"
2. Extract references (user-selectable count), fetch via Semantic Scholar, embed+store as source="reference"
3. Retrieve top-4 main + top-1 reference chunks → Azure OpenAI → topic bullet list

Phase 2 `explain_paper(level, topics)` (calls n8n):
1. Ping n8n health check — abort if unreachable
2. Retrieve top-4 main + top-1 reference chunks, POST to N8N_URL with {stage, paper_excerpt, level, topics}, timeout=300s
3. n8n: PlannerAgent → parallel(ExplainerAgent + MermaidAgent + QuizAgent + ImagePromptAgent→CallClusterAPI) → {text_explanation, mermaid_code, quiz, image_prompt, analogy_image, planner_brief}
4. Save to SQLite (all fields), display in Streamlit

## Tech stack

| Component | Detail |
|---|---|
| Frontend | Streamlit, port 8051 |
| LLM | Azure OpenAI — topic extraction + n8n explanation |
| Vector DB | Weaviate, collection `PaperChunk`, fields: text, source, chat_id, vector |
| Orchestration | n8n external via webhook — never called directly except via `api_client.py` |
| Embeddings | sentence-transformers all-MiniLM-L6-v2, loaded once at import |
| Persistence | SQLite `arpx.db` at project root, table `Explanations` (cols: text_explanation, mermaid_code, image_prompt, analogy_image, planner_brief, quiz_json); table `Messages` for chat history |
| TTS | Piper (CPU, runs in `app` container); voice model baked at `/opt/piper`; narrates the explanation |
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
After `docker compose up`, import `n8n_workflows/arpx-mvp.json` manually and activate — see `n8n_workflows/README.md`.
Weaviate needs warm-up after cold start; `create_schema()` is idempotent.

## Explanation levels

Levels 1–10 map to per-level system prompts in `n8n_workflows/prompts.yaml` under:
- `explainer.levels[N].system`
- `chat.levels[N].system`

Mermaid agent has single prompt with level-aware complexity rules embedded.
Shared output constraints in `shared.constraints`.

## Visual Analogy Agent (image generation)

Pipeline: PlannerAgent (LLM brief) → ImagePromptAgent (LLM → image prompt) → CallClusterAPI → base64 PNG.

All orchestrated in n8n. Runs parallel with Explainer + Mermaid inside explain stage.
PlannerAgent produces ~100 word brief shared by all three agents for cohesion.
`image_prompt` and `analogy_image` may be empty if cluster service is unreachable.

Image service: FastAPI on ificluster GPU node, NOT in Docker stack. See `image_service/README.md` for setup, GPU node compatibility, and per-session startup/tunnel commands.

## Key invariants

- Weaviate indexes per `chat_id` — each session's chunks are scoped and isolated at retrieval time
- RAG indexes both main paper AND user-selected references; `source` field distinguishes at retrieval
- Chat uses fusion retrieval (RRF with 3 sub-queries) for follow-up questions; explain/analyze use naive retrieval
- prompts.yaml read by n8n at runtime from `/data/prompts.yaml` — edit and save, no reimport needed
- Semantic Scholar: 3s min interval between requests enforced by global `LAST_REQUEST_TIME`
