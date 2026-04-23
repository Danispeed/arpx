import requests
import os

N8N_url = os.getenv("N8N_URL")

def call_orchestrator(stage, paper_excerpt, level, topics):
    payload = {"stage": stage}
    
    if stage == "explain":
        payload.update({
            "paper_excerpt": paper_excerpt,
            "level": level,
            "topics": topics,
        })
    
    try:
        response = requests.post(
            N8N_url,
            json=payload,
            timeout=300
        )
        
        # Checks the response code and throws an error is something went wrong
        response.raise_for_status()
        return response.json()

    except Exception as e:
        print("Error calling n8n:", e)
        return None