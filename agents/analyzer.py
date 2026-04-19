from openai import AzureOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

# Empty AZURE_OPENAI_API_VERSION is common in .env; Azure often returns 404 for a bad or missing api-version.
_AZURE_API_VERSION = (os.getenv("AZURE_OPENAI_API_VERSION") or "").strip() or "2024-10-21"
_AZURE_ENDPOINT = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip().rstrip("/")

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=_AZURE_API_VERSION,
    azure_endpoint=_AZURE_ENDPOINT or None,
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
        model=(os.getenv("AZURE_OPENAI_DEPLOYMENT") or "").strip(),
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return response.choices[0].message.content.strip()
