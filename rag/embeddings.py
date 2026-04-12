from sentence_transformers import SentenceTransformer

# Model is only loaded once, not every time embed_chunks is called
model = SentenceTransformer('all-MiniLM-L6-v2')

def embed_chunks(chunks):
    embeddings = model.encode(chunks)
    return embeddings