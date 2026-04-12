
# Currently using fixed size chunking stratey
# Could change this later to sentence-based or sliding window
def chunk_text(text, chunk_size=300):
    words = text.split()
    chunks = []
    
    # range(start, stop, step)
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i+chunk_size])
        chunks.append(chunk)
    
    return chunks