from rag.utils import extract_text_from_pdf
from rag.chunking import chunk_text
from rag.embeddings import embed_chunks
from rag.weaviate_db import create_schema, store_chunks, query_chunks

def index_paper(paper):
    # Extract text
    text = extract_text_from_pdf(paper)  
    
    # Chunk text
    chunks = chunk_text(text)
    
    # Create embeddings
    embeddings = embed_chunks(chunks)
    
    # Ensure schema exists
    create_schema()
    
    # Store in weaviate
    store_chunks(chunks, embeddings)

def retrieve_chunks(query):
    # Embed query
    query_embedding = embed_chunks([query])[0]
    
    # Retrieve relevant chunks
    retrieved_chunks = query_chunks(query_embedding)
    
    return retrieved_chunks
     