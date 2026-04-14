import weaviate
import weaviate.classes as wvc

client = weaviate.connect_to_local(
    host="127.0.0.1",
    port=8080
)

# class = name of the table
# vectorizer = None since we are creating the embeddings, this could be changed
# Weaviate stores data objects
# Each data objebt in our database will be PaperChink objects, whic will look like:
# (attribute-1, attribute-2, ..., attribute-n),  vector
# So currently ours will look like: chunk, vector
def create_schema():
    # Check if collection exists
    existing_collections = client.collections.list_all()

    if "PaperChunk" not in existing_collections:
        client.collections.create(
            name="PaperChunk",
            vectorizer_config=wvc.config.Configure.Vectorizer.none(),
            properties=[
                wvc.config.Property(
                    name="text",
                    data_type=wvc.config.DataType.TEXT
                )
            ]
        )
        

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
    collection = client.collections.get("PaperChunk")   # Store this in the "PaperChunk" table
    for chunk, vector in zip(chunks, embeddings):
        # Create a data object corresponding to the schema created (atm only contains one attribute "text")
        collection.data.insert(
            properties={
                "text": chunk
            },
            vector=vector.tolist() # Convert from numpy array to a plain list
        )

# This function
# will now retrieve the top 5 chunks based on the query, this parameter can be changed
def query_chunks(query_embedding, top_k=5):
    collection = client.collections.get("PaperChunk")
    
    response = collection.query.near_vector(
        near_vector=query_embedding.tolist(),   # Similarity search
        limit=top_k     # limit results, only return top_k most relevant chunks
    )
    
    return [obj.properties["text"] for obj in response.objects]
    

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


