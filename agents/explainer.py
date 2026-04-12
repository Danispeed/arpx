def find_topics(chunks, query):
    # Combine all the retrieved chunks
    context = "\n\n".join(chunks)
    
    prompt = f""""
    You are an AI assistant helping analyze research papers.
    
    Based on the following content:
    
    {context}
    
    Identify the main topics of the paper.
    
    Return ONLY a short bullet point list of topics.
    """
    
    response = ollama_call()
    
    return response