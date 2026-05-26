from agents.retriever import index_papers
from agents.analyzer import find_topics
from api_client import call_orchestrator
from rag.rag_types import retrieve_chunks_naive, retrieve_chunks_llm_query, retrieve_chunks_fusion

def analyze_paper(paper, chat_id, num_references):    
    # Index paper (should only happen once)
    index_papers(paper, chat_id, num_references)
    
    query = "What are the main topics of this research paper?"
    
    # Retrieve relevant chunks
    topic_chunks = retrieve_chunks_naive(query, chat_id, 4, 1)
    
    # Send to the explainer agent (local) the relevant chunks + query
    topics = find_topics(
        [chunk["text"] for chunk in topic_chunks],
        query
    )
    
    return (topics, topic_chunks)

def explain_paper(level, topics, chat_id):
    # Health check
    ping = call_orchestrator("ping", None, None, None, None, None)
    
    if not ping or ping.get("text_explanation") != "pong":
        return ({
            "text_explanation": "Error Backend (n8n) is not reachable.",
            "mermaid_code": "",
            "image_prompt": "",
            "analogy_image": "",
            "planner_brief": "",
            "quiz": "",
        }, [])

    query = "Explain the main ideas of this research paper"
    explain_chunks = retrieve_chunks_naive(query, chat_id, 4, 1)
    paper_excerpt = "\n\n".join(
    chunk["text"] for chunk in explain_chunks
)
    
    result = call_orchestrator("explain", paper_excerpt, level, topics, None, None)
    
    if not result:
        return ({
            "text_explanation": "Error: Failed to generate explanation",
            "mermaid_code": "",
            "image_prompt": "",
            "analogy_image": "",
            "planner_brief": "",
            "quiz": "",
        }, [])

    return (result, explain_chunks)

def generate_message_response(question, level, chat_id, history, retrieve_func, k_main, k_ref):
    ping = call_orchestrator("ping", None, None, None, None, None)
    
    if not ping or ping.get("text_explanation") != "pong":
        return ({
            "text_explanation": "Error Backend (n8n) is not reachable.",
            "mermaid_code": ""
        }, [])
    
    relevant_chunks = retrieve_func(question, chat_id, k_main, k_ref)
    paper_excerpt = "\n\n".join(
    chunk["text"] for chunk in relevant_chunks
    )
    
    result = call_orchestrator("chat", paper_excerpt, level, None, question, history)
    
    if not result:
        return ({
            "text_explanation": "Error: Failed to generate response",
            "mermaid_code": ""
        }, [])
    
    return (result, relevant_chunks)
    