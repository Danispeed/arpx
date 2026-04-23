# ARPX Orchestration Engine

This folder contains the n8n workflow export (`arpx-mvp.json`).

## Setup for Team Members

### 1) Start n8n in Docker

Run these commands from your project root:

```bash
docker compose up -d
```

Then open `http://localhost:5678`.

### 2) Import the workflow

In n8n: **Workflows** -> **Import from File** -> select [`arpx-mvp.json`](arpx-mvp.json).

### 3) Add Azure OpenAI credentials

Create one credential in n8n:
- **Credentials** -> **Add Credential** -> **Header Auth**
- Header name: `api-key`
- Header value: your Azure OpenAI API key

Then open each node and select that credential:
- `ExplainerAgent`
- `MermaidAgent`
- `ChatAgent`

### 4) Publish and activate

For n8n 2.x, production webhooks require both actions:
1. Click **Publish** in the workflow editor.
2. Toggle the workflow to **Active**.

## Prompt workflow

Prompt source of truth lives in [`prompts.yaml`](prompts.yaml). The workflow reads this file at runtime on every execution.

1. Edit prompt content in `n8n_workflows/prompts.yaml`.
2. Trigger a webhook request (test or production URL).
3. The workflow reads `/data/prompts.yaml`, parses prompt sections, and uses them for `ExplainerAgent`, `MermaidAgent`, and `ChatAgent`.

No workflow recompile or JSON re-import is required for prompt-only changes.

## API Contract (Frontend -> n8n)

- **Method:** `POST`
- **URL:** `http://localhost:5678/webhook/arpx/orchestrate`
- **Header:** `Content-Type: application/json`

### Stage: `explain` (default)

Request body:

```json
{
  "paper_excerpt": "Text chunks from Weaviate",
  "level": 3,
  "topics": ["Topic A", "Topic B"],
  "stage": "explain"
}
```

Field notes:
- `paper_excerpt` (string): source text to explain.
- `level` (number): 1–10, where 1 is beginner and 10 is expert.
- `topics` (array): topic labels used as extra context.
- `stage` (string): `"explain"` is the default; omitting it also routes here.

Response body:

```json
{
  "text_explanation": "Adaptive summary text...",
  "mermaid_code": "flowchart TD\nA[Concept] --> B[Detail]",
  "debug": {
    "stage": "explain",
    "route": "orchestrate"
  }
}
```

### Stage: `chat`

Used to ask follow-up questions about the paper. The frontend is responsible for maintaining conversation history and sending it back on every request.

Request body:

```json
{
  "stage": "chat",
  "paper_excerpt": "Text chunks from Weaviate",
  "level": 3,
  "query": "What does the attention mechanism actually do here?",
  "history": [
    { "role": "user", "content": "Can you explain the model architecture?" },
    { "role": "assistant", "content": "The model uses a transformer-based..." }
  ]
}
```

Field notes:
- `stage` (string): must be `"chat"`.
- `paper_excerpt` (string): same excerpt used in the current session — injected into the chat user template.
- `level` (number): 1–10 — selects the level-specific chat system prompt and is injected into the user template.
- `query` (string): the user's current question.
- `history` (array): all previous turns in the conversation, each as `{ "role": "user"|"assistant", "content": "..." }`. The workflow inserts this between the system prompt and the current user message, giving the model full conversation context. Send an empty array `[]` for the first message.

How the workflow builds the message list sent to the model:

```
[system prompt (level-specific)]
...history (previous turns, oldest first)
[user: rendered chat template with paper_excerpt, level, and query filled in]
```

Response body:

```json
{
  "text_explanation": "The attention mechanism computes...",
  "mermaid_code": "",
  "debug": {
    "stage": "chat",
    "route": "orchestrate"
  }
}
```

Note: `mermaid_code` is always an empty string for chat responses. After receiving a response the frontend should append `{ "role": "user", "content": query }` and `{ "role": "assistant", "content": text_explanation }` to its local history array before the next request.

## Health Check

Use this to verify the workflow is reachable without triggering full generation:

```bash
curl -sS -X POST "http://localhost:5678/webhook/arpx/orchestrate" \
  -H "Content-Type: application/json" \
  -d '{"stage":"ping"}'
```

Expected response includes:
- `text_explanation: "pong"`
- `mermaid_code` with a simple test diagram
- `debug.route: "ping"`

## Notes

- Azure endpoint used by both nodes: `https://gpt-course.cognitiveservices.azure.com`.
- Explainer deployment/model: `gpt-5-chat`.
- Mermaid deployment/model: `gpt-5-chat`.
- Keep API keys only in n8n credentials, never in git.
- If node version warnings appear on import, re-save the workflow in n8n and export again.
