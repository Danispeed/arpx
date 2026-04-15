from agents.retriever import index_papers, retrieve_chunks
from agents.explainer import find_topics, explain_text

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

def explain_paper(level):
    query = "Explain the main ideas of this research paper"
    
    explain_chunks = retrieve_chunks(query)
    
    explanation = explain_text(explain_chunks, query, level)
    
    return explanation