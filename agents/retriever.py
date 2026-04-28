from rag.utils import extract_text_from_pdf, extract_references
from rag.chunking import chunk_text_fixed, chunk_text_sentence, chunk_text_sliding, chunk_text_llm
from rag.embeddings import embed_chunks
from rag.weaviate_db import create_schema, store_chunks, query_chunks
from rag.semantic_scholar import fetch_paper_data
import requests
import io

# Index both the main paper and the referenced papers
def index_papers(paper, chat_id, num_refernces):
    # Begin with main paper
    # Extract text
    text = extract_text_from_pdf(paper)  
    
    # Chunk text
    chunks = chunk_text_sliding(text)
    
    # Create embeddings
    embeddings = embed_chunks(chunks)
    
    # Ensure schema exists
    create_schema()
    
    # Store in weaviate
    store_chunks(chunks, embeddings, "main", chat_id)
    
    # Referenced papers
    references = extract_references(text, num_refernces)
    
    for reference in references:
        data = fetch_paper_data(reference)
        
        if not data:
            print("No data found for this reference")
            continue
            
        # First, try to use the pdf
        if data["pdf_url"]:
            try:
                print("Trying PDF:", data["pdf_url"])
                
                # Download the PDF file (as bytes)
                # .content contain the binary data of the file
                pdf_response = requests.get(data["pdf_url"], timeout=5)
                pdf_file = io.BytesIO(pdf_response.content) # convert it to a file-like object
                
                reference_text = extract_text_from_pdf(pdf_file)
                
                reference_chunks = chunk_text_sliding(reference_text)
                reference_embeddings = embed_chunks(reference_chunks)
                
                store_chunks(reference_chunks, reference_embeddings, "reference", chat_id)
                
                print(f"Stored {len(reference_chunks)} reference chunks (PDF)")
                continue
            
            except Exception as e:
                print("PDF failed:", e)
        
        # Fallback: abstract
        if data["abstract"]:
            print("Using abstract")
            abstract_chunks = chunk_text_sliding(data["abstract"])
            abstract_embeddings = embed_chunks(abstract_chunks)
            
            store_chunks(abstract_chunks, abstract_embeddings, "reference", chat_id)
        

def retrieve_chunks(query, chat_id):
    # Embed query
    query_embedding = embed_chunks([query])[0]
    
    # Retrieve relevant chunks
    retrieved_chunks = query_chunks(query_embedding, chat_id)
    
    return retrieved_chunks
     