from agents.retriever import index_papers, retrieve_chunks
from agents.analyzer import find_topics
from api_client import call_orchestrator

def analyze_paper(paper):    
    # Index paper (should only happen once)
    index_papers(paper)
    
    # Probably need to be modified
    query = "What are the main topics of this research paper?"
    
    # Retrieve relevant chunks
    topic_chunks = retrieve_chunks(query)
    
    # Send to the explainer agent the relevant chunks + query
    topics = find_topics(topic_chunks, query) 
    
    return topics

def explain_paper(level, topics):
    # Health check
    ping = call_orchestrator(stage="ping")
    
    if not ping or ping.get("text_explanation") != "pong":
        return {
            "text_explanation": "Error Backend (n8n) is not reachable.",
            "mermaid_code": ""
        }
    
    query = "Explain the main ideas of this research paper"
    explain_chunks = retrieve_chunks(query)
    paper_excerpt = "\n\n".join(explain_chunks)
    
    result = call_orchestrator("explain", paper_excerpt, level, topics)
    
    if not result:
        return {
            "text_explanation": "Error: Failed to generate explanation",
            "mermaid_code": ""
        }
    
    return result