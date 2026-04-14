import requests
import time

def fetch_paper_data(query):
    """
    Search Semantic Scholar for a paper.
    Returns:
        {
            "abstract": str | None,
            "pdf_url": str | None
        }
    """
    
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    
    parameters = {
        "query": query,  # What to search for, for example: "Smith et al. 2020 Deep Learning Optimization"
        "limit": 1, # Return only the best match, we assume the first result is correct
        "fields": "title,abstract,openAccessPdf"    # What data we want back
    }
    
    try:
        print("Trying to send scholar api request")
        time.sleep(5)
        response = requests.get(url, params=parameters, timeout=5)
        
        if response.status_code != 200:
            print("Semantic Scholar error")
            print("Status code:", response.status_code)
            print("Response text:", response.text)
            return None
        
        data = response.json()
        
        if data.get("total", 0) == 0:
            print("Nothing was returned")
            return None
        
        paper = data["data"][0]
        
        pdf_url = None
        if paper.get("openAccessPdf"):
            pdf_url = paper["openAccessPdf"].get("url")
            
        return {
            "abstract": paper.get("abstract"),
            "pdf_url": pdf_url,
        }
    except Exception as e:
        print("Semantic Scholar error:", e)
        return None