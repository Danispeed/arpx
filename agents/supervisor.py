from agents.retriever import index_papers, retrieve_chunks
from agents.analyzer import find_topics
from api_client import call_orchestrator

def analyze_paper(paper, chat_id):    
    # Index paper (should only happen once)
    index_papers(paper, chat_id)
    
    # Probably need to be modified
    query = "What are the main topics of this research paper?"
    
    # Retrieve relevant chunks
    topic_chunks = retrieve_chunks(query, chat_id)
    
    # Send to the explainer agent the relevant chunks + query
    topics = find_topics(topic_chunks, query) 
    
    return topics

def explain_paper(level, topics, chat_id):
    # Health check
    ping = call_orchestrator("ping", None, None, None)
    
    if not ping or ping.get("text_explanation") != "pong":
        return {
            "text_explanation": "Error Backend (n8n) is not reachable.",
            "mermaid_code": ""
        }
    
    query = "Explain the main ideas of this research paper"
    explain_chunks = retrieve_chunks(query, chat_id)
    paper_excerpt = "\n\n".join(explain_chunks)
    
    result = call_orchestrator("explain", paper_excerpt, level, topics)
    
    if not result:
        return {
            "text_explanation": "Error: Failed to generate explanation",
            "mermaid_code": ""
        }
    
    return result