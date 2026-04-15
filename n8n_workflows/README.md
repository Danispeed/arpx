# ARPX Orchestration Engine

This folder contains the n8n workflow export (`arpx-mvp.json`).

## Setup for Team Members

### 1) Start n8n in Docker

Run these commands from your project root:

```bash
docker volume create n8n_data
docker run -d --name n8n \
  -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  docker.n8n.io/n8nio/n8n
```

Then open `http://localhost:5678`.

### 2) Import the workflow

In n8n: **Workflows** -> **Import from File** -> select [`arpx-mvp.json`](arpx-mvp.json).

### 3) Add Azure OpenAI credentials

Create one credential in n8n:
- **Credentials** -> **Add Credential** -> **Header Auth**
- Header name: `api-key`
- Header value: your Azure OpenAI API key

Then open both nodes and select that credential:
- `ExplainerAgent`
- `MermaidAgent`

### 4) Publish and activate

For n8n 2.x, production webhooks require both actions:
1. Click **Publish** in the workflow editor.
2. Toggle the workflow to **Active**.

## Prompt workflow

Prompt source of truth lives in [`prompts.yaml`](prompts.yaml). Do not manually edit prompt strings in [`arpx-mvp.json`](arpx-mvp.json) unless debugging.

1. Edit prompt content in `n8n_workflows/prompts.yaml`.
2. Compile prompts into the workflow JSON:

```bash
python3 scripts/build_workflow.py
```

3. Import the regenerated `n8n_workflows/arpx-mvp.json` into n8n.
4. Publish + activate the workflow again.

The compiler updates only prompt text fields in `ExplainerAgent` and `MermaidAgent`.

## API Contract (Frontend -> n8n)

- **Method:** `POST`
- **URL:** `http://localhost:5678/webhook/arpx/orchestrate`
- **Header:** `Content-Type: application/json`

### Request body

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
- `level` (number): 1 to 10, where 1 is beginner and 10 is expert.
- `topics` (array): topic labels used as extra context.
- `stage` (string): use `explain` for normal flow, `ping` for health checks.

### Response body (normal flow)

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
- Mermaid deployment/model: `gpt-4.1-mini`.
- Keep API keys only in n8n credentials, never in git.
- If node version warnings appear on import, re-save the workflow in n8n and export again.
