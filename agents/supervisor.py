from agents.retriever import index_papers
from agents.analyzer import find_topics
from api_client import call_orchestrator
from rag.rag_types import retrieve_chunks_naive, retrieve_chunks_llm_query, retrieve_chunks_fusion
from evals.rag_types import run_rag_evaluation
from evals.retrieved_chunks import run_full_k_experiment

def analyze_paper(paper, chat_id, num_references):    
    # Index paper (should only happen once)
    index_papers(paper, chat_id, num_references)
    
    # Probably need to be modified
    query = "What are the main topics of this research paper?"
    
    # Retrieve relevant chunks
    topic_chunks = retrieve_chunks_naive(query, chat_id, 5)
    
    # Send to the explainer agent the relevant chunks + query
    topics = find_topics(topic_chunks, query) 
    
    return topics

def explain_paper(level, topics, chat_id, run_eval=True):
    # Health check
    ping = call_orchestrator("ping", None, None, None, None, None)
    
    if not ping or ping.get("text_explanation") != "pong":
        return {
            "text_explanation": "Error Backend (n8n) is not reachable.",
            "mermaid_code": ""
        }
    
    # Optional, rag types evaluation
    if run_eval:
        #run_rag_evaluation(chat_id)
        run_full_k_experiment(chat_id)
        
    
    query = "Explain the main ideas of this research paper"
    explain_chunks = retrieve_chunks_naive(query, chat_id, 5)
    paper_excerpt = "\n\n".join(explain_chunks)
    
    result = call_orchestrator("explain", paper_excerpt, level, topics, None, None)
    
    if not result:
        return {
            "text_explanation": "Error: Failed to generate explanation",
            "mermaid_code": ""
        }
    
    return result

def generate_message_response(question, level, chat_id, history, retrieve_func, k_main, k_ref):
    ping = call_orchestrator("ping", None, None, None, None, None)
    
    if not ping or ping.get("text_explanation") != "pong":
        return {
            "text_explanation": "Error Backend (n8n) is not reachable.",
            "mermaid_code": ""
        }
    
    relevant_chunks = retrieve_func(question, chat_id, k_main, k_ref)
    paper_excerpt = "\n\n".join(relevant_chunks)
    
    result = call_orchestrator("chat", paper_excerpt, level, None, question, history)
    
    if not result:
        return {
            "text_explanation": "Error: Failed to generate response",
            "mermaid_code": ""
        }
    
    return result
    