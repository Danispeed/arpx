from agents.retriever import index_paper, retrieve_chunks

def analyze_paper(paper):
    # Index paper (should only happen once)
    index_paper(paper)
    
    # Probably need to be modified
    query = "What are the main topics of this research paper?"
    
    # Retrieve relevant chunks
    topic_chunks = retrieve_chunks(query)
    
    # Send to the explainer agent the relevant chunks + query
    topics = find_topics(topic_chunks, query) 
    
    return topics