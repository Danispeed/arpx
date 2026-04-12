import weaviate

client = weaviate.Client("http://localhost:8080")

# class = name of the table
# vectorizer = None since we are creating the embeddings, this could be changed
# Weaviate stores data objects
# Each data objebt in our database will be PaperChink objects, whic will look like:
# (attribute-1, attribute-2, ..., attribute-n),  vector
# So currently ours will look like: chunk, vector
def create_schema():
    schema = {
        "class": "PaperChunk",
        "vectorizer": "none",
        "properties": [
            {"name": "text", "dataType": ["text"]},
        ]
    }
    
    # Register the schema if it does not exist yet
    if not client.schema.exists("PaperChunk"):
        client.schema.create_class(schema)
        

# Each iteration creates:
# PaperChunk object:
# text:
#   "Gradient descent minimizes loss..."
#
# vector:
#   [0.12, -0.44, 0.91, ...]
def store_chunks(chunks, embeddings):
    # Iterate through the chunks with its corresponding vector
    # We assume that the corresponding chunks and vector are stored at the same index
    # e.g., chunks[0] belongs to embeddings[0]
    for chunk, vector in zip(chunks, embeddings):
        # Create a data object corresponding to the schema created (atm only contains one attribute "text")
        client.data_object.create(
            {
                "text": chunk
            },
            "PaperChunk", # Store this in the "PaperChunk" table
            vector=vector.tolist() # Convert from numpy array to a plain list
        )

# This function will now retrieve the top 5 chunks based on the query, this parameter can be changed
def query_chunks(query_embedding, top_k=5):
    result = (
        client.query
        .get("PaperChunk", ["text"])    # Search in the PaperChunk class and return the text field
        # Similarity search
        .with_near_vector({
            "vector": query_embedding.tolist()
        })
        .with_limit(top_k) # limit results, only return top_k most relevant chunks
        .do()   # send request to server
    )
    
    return [item["text"] for item in result["data"]["Get"]["PaperChunk"]]
    

# Weaviate returns:
# {
#   "data": {
#     "Get": {
#       "PaperChunk": [
#         {"text": "..."},
#         {"text": "..."}
#       ]
#     }
#   }
# }


