import weaviate
import weaviate.classes as wvc

client = weaviate.connect_to_custom(
    http_host="weaviate",
    http_port=8080,
    http_secure=False,
    grpc_host="weaviate",
    grpc_port=50051,
    grpc_secure=False,
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
                ),
                wvc.config.Property(
                    name="source",
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
def store_chunks(chunks, embeddings, source):
    # Iterate through the chunks with its corresponding vector
    # We assume that the corresponding chunks and vector are stored at the same index
    # e.g., chunks[0] belongs to embeddings[0]
    collection = client.collections.get("PaperChunk")   # Store this in the "PaperChunk" table
    for chunk, vector in zip(chunks, embeddings):
        # Create a data object corresponding to the schema created (atm only contains one attribute "text")
        collection.data.insert(
            properties={
                "text": chunk,
                "source": source
            },
            vector=vector.tolist() # Convert from numpy array to a plain list
        )

# This function
# will now retrieve the top 5 chunks based on the query, this parameter can be changed
def query_chunks(query_embedding, top_k_main=5, top_k_ref=2):
    collection = client.collections.get("PaperChunk")
    
    # Chunks from the main paper (the paper that was uploaded by the user)
    main_results = collection.query.near_vector(
        near_vector=query_embedding.tolist(),   # Similarity search
        limit=top_k_main,     # limit results, only return top_k most relevant chunks
        filters=wvc.query.Filter.by_property("source").equal("main")
    )
    
    reference_results = collection.query.near_vector(
        near_vector=query_embedding.tolist(),
        limit=top_k_ref,
        filters=wvc.query.Filter.by_property("source").equal("reference")
    )
    
    # Combine results
    combined = main_results.objects + reference_results.objects
    
    return [obj.properties["text"] for obj in combined]
    

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

# Clear database
def clear():
    # Cleares eveything in the database
    client.collections.delete("PaperChunk")


