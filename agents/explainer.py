from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

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
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return response.choices[0].message.content.strip()