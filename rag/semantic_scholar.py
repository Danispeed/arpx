import requests
import time
import threading

LAST_REQUEST_TIME = 0
MIN_INTERVAL = 3

def fetch_paper_data(query):
    print(f"Thread ID: {threading.get_ident()}")
    global LAST_REQUEST_TIME
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
        print("Trying to send scholar api request for the resource: ", query)
        now = time.time()
        elapsed = now - LAST_REQUEST_TIME
        
        if elapsed < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL)
        
        print("Sending request to Semantic Scholar")
        LAST_REQUEST_TIME = time.time()
        response = safe_request(url, parameters)
        
        if response == None:
            print("All retries failed")
            return None
        
        if response.status_code != 200:
            print("Semantic Scholar error")
            print("Status code:", response.status_code)
            print("Response text:", response.text)
            return None
        
        data = response.json()
        
        print("The request was successful")
        
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

def safe_request(url, params, retries=3):
    for attempt in range(retries):
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            return response

        if response.status_code == 429:
            wait = 2 ** attempt # exponential backoff
            print(f"Rate limited. Sleeping {wait} seconds")
            time.sleep(wait)
            continue
        
        return response
    
    return None