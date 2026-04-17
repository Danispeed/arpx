from openai import AzureOpenAI
from dotenv import load_dotenv
import os

load_dotenv()
_api_version = os.getenv("AZURE_OPENAI_API_VERSION") or "2024-02-01"
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=_api_version,
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

def find_topics(chunks, query):
    # Combine all the retrieved chunks
    context = "\n\n".join(chunks)
    
    prompt = f"""
    You are an AI assistant helping analyze research papers.
    
    Based on the following content:
    
    {context}
    
    Identify the main topics of the paper.
    
    Return ONLY a short bullet point list of topics.
    """
    
    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return response.choices[0].message.content.strip()
