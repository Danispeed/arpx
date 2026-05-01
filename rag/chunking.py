from openai import AzureOpenAI
from rag.utils import split_into_sentences
import os
from dotenv import load_dotenv
import ast

load_dotenv()

_AZURE_API_VERSION = (os.getenv("AZURE_OPENAI_API_VERSION") or "").strip() or "2024-10-21"
_AZURE_ENDPOINT = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip().rstrip("/")

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=_AZURE_API_VERSION,
    azure_endpoint=_AZURE_ENDPOINT or None,
)
# Currently using fixed size chunking stratey
# Could change this later to sentence-based or sliding window
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

    Your task is to split the following text into semantically meaningful chunks.

    Requirements:
    - Each chunk must represent ONE coherent idea or concept
    - Do NOT break sentences in the middle
    - Combine related sentences into the same chunk
    - Keep chunks reasonably sized (around {chunk_size} words long)
    - Avoid redundancy

    Output format:
    - Return ONLY a Python list of strings
    - Do NOT include explanations
    - Do NOT include numbering
    - Do NOT include markdown

    Example:
    ["Chunk 1 text...", "Chunk 2 text..."]

    Text:
    {text}
    """
    
    response = client.chat.completions.create(
        model=(os.getenv("AZURE_OPENAI_DEPLOYMENT") or "").strip(),
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    content = response.choices[0].message.content.strip()
    
    # Remove markdown if present
    content = content.replace("```python", "").replace("```", "").strip()
    
    try:
        chunks = ast.literal_eval(content)
        
        if not isinstance(chunks, list):
            raise ValueError("Output is not a list")
        
        if not all(isinstance(chunk, str) for chunk in chunks):
            raise ValueError("Chunks are not all strings")

        return chunks

    except Exception as e:
        print("LLM chunking failed:", e)
        return [text] # fallback