from rag.weaviate_db import is_indexed
from agents.retriever import index_papers
from rag.utils import find_num_references

def ensure_indexed(case):
    chat_id = case["chat_id"]
    paper_path = case["paper_path"]
    
    if not is_indexed(chat_id):
        with open(paper_path, "rb") as paper:
            num_references = find_num_references(paper)
            
            paper.seek(0)
            
            index_papers(
                paper=paper,
                chat_id=chat_id,
                num_references=num_references
            )

    