# n8n_workflows/

n8n is EXTERNAL orchestrator. Python never calls it directly — only via `api_client.py` POST to `N8N_URL`.

## Files

- `arpx-mvp.json` — import into n8n UI. Re-import after structural workflow changes.
- `prompts.yaml` — runtime prompt source of truth. n8n reads `/data/prompts.yaml` on every execution. Edit and save — no reimport needed.

## n8n setup (one-time per environment)

1. `docker compose up -d` → open `http://localhost:5678`
2. Import `arpx-mvp.json`
3. Add credential: Header Auth, name=`api-key`, value=Azure key
4. Assign credential to ExplainerAgent, MermaidAgent, ChatAgent, PlannerAgent, ImagePromptAgent nodes
5. Set variable `IMAGE_SERVICE_URL` (Settings → Variables) to cluster endpoint from `image_service/start.sh` output
5. Publish + toggle Active

## Webhook API contract

Endpoint: `POST http://localhost:5678/webhook/arpx/orchestrate`

### stage: "explain"
Request: `{stage, paper_excerpt: str, level: int 1-10, topics: list[str]}`
Response: `{text_explanation: str, mermaid_code: str, image_prompt: str, analogy_image: str (base64 PNG), planner_brief: str, debug: {stage, route}}`

Explain flow: PlannerAgent → (ExplainerAgent + MermaidAgent + ImagePromptAgent→CallClusterAPI) parallel → MergeAll.
`image_prompt` and `analogy_image` may be empty if cluster service is unreachable.

### stage: "chat"
Request: `{stage, paper_excerpt: str, level: int, query: str, history: [{role, content}...]}`
Response: `{text_explanation: str, mermaid_code: "", debug: {stage, route}}`
History format: `[{role: "user"|"assistant", content: str}]`. Send `[]` for first message.

### stage: "ping"
Request: `{stage: "ping"}`
Response: `{text_explanation: "pong", mermaid_code: <test diagram>}`
Used by `supervisor.py` health check before every explain call.

## prompts.yaml structure

```yaml
shared.constraints[]            # applied to all agents
explainer.user_template         # placeholders: {paper_excerpt}, {topics}, {level}
explainer.levels[1-10].system   # per-level system prompt — DSPy optimization target
mermaid.system                  # single prompt with embedded level-aware complexity rules
mermaid.user_template           # placeholders: {paper_excerpt}, {topics}, {level}
chat.user_template              # placeholders: {paper_excerpt}, {level}, {query}
chat.levels[1-10].system        # per-level chat system prompt
planner.system                  # coordination brief generator
planner.user_template           # placeholders: {paper_excerpt}, {topics}, {level}
image_prompt.system             # visual analogy SD prompt generator
image_prompt.user_template      # placeholders: {planner_brief}, {paper_excerpt}, {topics}, {level}
```

Optimization writes to `explainer.levels[N].system`.
Azure deployment for n8n agents: use course-specific names (e.g. `gpt-5-chat`), never standard OpenAI names.
