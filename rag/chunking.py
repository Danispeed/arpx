from openai import AzureOpenAI
from rag.utils import split_into_sentences
import os
from dotenv import load_dotenv
import json

os.environ["TOKENIZERS_PARALLELISM"] = "false"

load_dotenv()

_AZURE_API_VERSION = (os.getenv("AZURE_OPENAI_API_VERSION") or "").strip() or "2024-10-21"
_AZURE_ENDPOINT = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip().rstrip("/")

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=_AZURE_API_VERSION,
    azure_endpoint=_AZURE_ENDPOINT or None,
)

def chunk_text_fixed(text, chunk_size):
    words = text.split()
    chunks = []
    
    # range(start, stop, step)
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i+chunk_size])
        
        # Avoid empty chunks
        if chunk:
            chunks.append(chunk)
    
    return chunks

def chunk_text_sentence(text, chunk_size):
    sentences = split_into_sentences(text)
    chunks = []
    
    # Chunk size = number of sentences in each chunk
    for i in range(0, len(sentences), chunk_size):
        chunk = " ".join(sentences[i:i + chunk_size])
        
        if chunk:
            chunks.append(chunk)
    
    return chunks

def chunk_text_sliding(text, chunk_size, overlap):
    # Chunk size = number of words per chunk
    # overlap = number of words overlapping between chunks
    words = text.split()
    chunks = []
    
    step = chunk_size - overlap
    
    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i+chunk_size])
        
        # Avoid empty chunks
        if chunk:
            chunks.append(chunk)
    
    return chunks

def chunk_text_llm(text, chunk_size):
    prompt = f"""
    You are an expert in analyzing academic research papers.

    Split the text into semantically meaningful chunks.

    Requirements:
    - Each chunk must represent ONE coherent idea
    - Do NOT split sentences
    - Combine related sentences
    - Aim for about {chunk_size} words per chunk
    - Avoid redundancy

    Return ONLY valid JSON.

    Format:
    {{
    "chunks": [
        "chunk text 1",
        "chunk text 2"
    ]
    }}

    Text:
    {text}
    """
    
    response = client.chat.completions.create(
        model=(os.getenv("AZURE_OPENAI_DEPLOYMENT") or "").strip(),
        response_format={"type": "json_object"},
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    content = response.choices[0].message.content.strip()
    
    # Remove markdown if present
    content = content.replace("```json", "").replace("```python", "").replace("```", "").strip()
    
    try:
        data = json.loads(content)
        chunks = data["chunks"]

        if not isinstance(chunks, list):
            raise ValueError("chunks is not a list")

        if not all(isinstance(chunk, str) for chunk in chunks):
            raise ValueError("chunks must contain only strings")

        return chunks

    except Exception as e:
        print("RAW OUTPUT:", repr(content))
        print("LLM chunking failed:", e)
        return [text]