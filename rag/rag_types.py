from agents.retriever import retrieve_chunks
from openai import AzureOpenAI
from dotenv import load_dotenv
import os
import ast

load_dotenv()

# Empty AZURE_OPENAI_API_VERSION is common in .env; Azure often returns 404 for a bad or missing api-version.
_AZURE_API_VERSION = (os.getenv("AZURE_OPENAI_API_VERSION") or "").strip() or "2024-10-21"
_AZURE_ENDPOINT = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip().rstrip("/")

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=_AZURE_API_VERSION,
    azure_endpoint=_AZURE_ENDPOINT or None,
)

def retrieve_chunks_naive(user_query, chat_id, k=5):
    return retrieve_chunks(user_query, chat_id)


def retrieve_chunks_llm_query(user_query, chat_id, k=5):
    new_query = generate_search_query(user_query)
    return retrieve_chunks(new_query, chat_id)

def generate_search_query(user_query):
    prompt = f"""
    You are generating a semantic search query for retrieving relevant information from a research paper.

    Context:
    - The user is asking a follow-up question about a research paper.
    - The system will use your query to retrieve relevant chunks using embeddings.

    Your task is to convert the question into an effective semantic search query.

    Guidelines:
    - Focus on the core concepts, methods, or entities in the question
    - Remove conversational or vague wording
    - Use technical terms ONLY if they are present or clearly implied in the question
    - Keep it concise (output should be a short phrase, around the same length as the original question)
    - Do NOT answer the question
    - Do NOT include explanations

    Question:
    {user_query}

    Return ONLY the search query.
    """
    response = client.chat.completions.create(
        model=(os.getenv("AZURE_OPENAI_DEPLOYMENT") or "").strip(),
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return response.choices[0].message.content.strip()

def retrieve_chunks_fusion(user_query, chat_id, k=5):
    queries = generate_multiple_queries(user_query, 3)
    
    chunk_ranks = {}
    for query in queries:
        retrieved = retrieve_chunks(query, chat_id)
        
        for rank, chunk in enumerate(retrieved):
            if chunk not in chunk_ranks:
                chunk_ranks[chunk] = []
            chunk_ranks[chunk].append(rank)
    
    rrf = 60 # smoothing constant
    
    chunk_scores = {}
    
    for chunk, ranks in chunk_ranks.items():
        score = 0
        for rank in ranks:
            score += 1 / (rrf + rank + 1)
        chunk_scores[chunk] = score
    
    # Sort by score
    ranked_chunks = sorted(
        chunk_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    # return top-k chunks
    return [chunk for chunk in _ in ranked_chunks[:k]]
        

def generate_multiple_queries(user_query, n):
    prompt = f"""
    You are generating multiple semantic search queries for retrieving relevant information from a research paper.
    
    Context:
    - The user is asking a follow-up question about a research paper.
    
    Your task is to generate {n} different search queries that:
    - capture different aspects of the question
    - use different wording or focus
    - remain concise keyword-style phrases
    
    Do NOT answer the question.
    Do NOT include explanations.
    
    Return the query as a Python list of strings.
    
    Example:
    ["query 1", "query 2", "query 3", ..., "query n"]
    """
    
    content = client.chat.completions.create(
        model=(os.getenv("AZURE_OPENAI_DEPLOYMENT") or "").strip(),
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    try:
        queries = ast.literal_eval(content)
        if isinstance(queries, list):
            return queries
    
    except:
        pass
    
    return [user_query] # fallback
    
    