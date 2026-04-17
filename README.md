# arpx - Adaptive Research Paper Explainer

Arpx is a Generative AI system that analyzes resarch papers and generates adaptive explanations based on the user's knowledge level.

The system uses Retrieval-Augmented Generation (RAG), a vector database (Weaviate), and an orchestration layer (n8n) to process and explain academic content. HER: Legg til resten av hva som blir brukt.

## Features
- Upload research papers (PDF)
- Receive the main topics from the paper
- Semantic search using vector embeddings
- Modular architecture with orchestrated agents

## Syetem Arcitecture
The system is composed of x main components:

- Frontend & Application Layer
    - Streamlit app
    - Handles file upload, UI, and user interaction
- Vector Database
    - Weaviate
    - Stores embeddings and enables semantic retrieval
- Orchestration Layer
    - n8n
    - Coordinates LLM calls and generates explanations + diagrams

## Running the Project (Docker)
### Prerequisites
- Docker installed
- Docker Compose installed

1. Start the system
From the project root:

```bash
docker compose up --build
```

2. Open the application
Go to:

http://localhost:8051

3. (Optional) Access Weaviate
http://localhost:8080/v1/meta

## Environment Variables
The following environment variables need to be set:
- OPENAI_KEY
- AZURE_OPENAI_ENDPOINT
- AZURE_OPENAI_DEPLOYMENT

## How it Works
1. User uploads a research paper
2. The paper is processed and split into chunks
3. Embeddings are generated and stored in Weaviate
4. Relevant chunks are retrieved using semantic search
5. The system calls an LLM to find the main topics of the research using the relevant chunks
6. Based on the topics, the user select the knowledge level
7. ...

