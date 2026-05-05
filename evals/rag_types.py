from rag.rag_types import retrieve_chunks_naive, retrieve_chunks_llm_query, retrieve_chunks_fusion
from datasets import Dataset
import os
from rag.embeddings import embed_chunks
import numpy as np
from dotenv import load_dotenv
from openai import AzureOpenAI
import pandas as pd
import matplotlib.pyplot as plt

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

rag_methods = {
    "naive": retrieve_chunks_naive,
    "llm_query": retrieve_chunks_llm_query,
    "fusion": retrieve_chunks_fusion
}

# Specified for Pesto paper
questions = [
    "What problem does Pesto solve?",
    "Why are SMR-based BFT systems inefficient?",
    "How does Pesto ensure serializability without total ordering?",
    "What is the snapshot protocol used for?",
    "How does Pesto handle concurrency control?",
    "What performance improvements does Pesto achieve?"
]

def set_up_rag_experiment(chat_id):
    results = []
    
    for rag_name, retrieve_func in rag_methods.items():
        for question in questions:
            chunks = retrieve_func(question, chat_id)
            
            from agents.supervisor import generate_message_response
            response = generate_message_response(
                question,
                5,
                chat_id,
                [],
                retrieve_func
            )
            
            answer = response["text_explanation"]
            
            results.append({
                "rag_type": rag_name,
                "question": question,
                "answer": answer,
                "contexts": chunks
            })
    
    return results

def evaluate_rag(results):
    rows = []
    
    for result in results:
        faith = compute_faithfulness(result["answer"], result["contexts"])
        relevancy = compute_answer_relevancy(result["question"], result["answer"])
        context_score = compute_context_precision(result["question"], result["contexts"])
        
        rows.append({
            "rag_type": result["rag_type"],
            "faithfulness": faith,
            "answer_relevancy": relevancy,
            "context_precision": context_score
        })
    
    return pd.DataFrame(rows)
        

def compute_faithfulness(answer, contexts):
    claims = extract_claims(answer)
    
    if not claims:
        return 0.0
    
    supported = 0
    
    for claim in claims:
        supported += check_claim_support(claim, contexts)
    
    return supported / len(claims)

def extract_claims(answer):
    prompt = f"""
    Break the following answer into a list of atomic factual claims.
    
    Rules:
    - Each claim must be a single verifiable statement
    - Do not combine multiple ideas
    - Return ONLY a Python list of strings
    
    Answer:
    {answer}
    """
    
    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[{"role": "user", "content": prompt}]
    )
    
    content = response.choices[0].message.content.strip()
    
    # clean output
    content = content.replace("```python", "").replace("```", "").strip()

    import ast
    try:
        claims = ast.literal_eval(content)
        return claims if isinstance(claims, list) else []
    except:
        return []

def check_claim_support(claim, contexts):
    context = '\n\n'.join(contexts)
    prompt = f"""
    You are verifying whether a claim is supported by the given context.
    
    Context:
    {context}
    
    Claim:
    {claim}
    
    Answer ONLY with:
    1 = supported
    0 = not supported
    """
    
    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[{"role": "user", "content": prompt}]
    )
    
    text = response.choices[0].message.content.strip()
    text = text.strip()
    return 1 if "1" in text else 0

def compute_answer_relevancy(question, answer):
    generated_questions = generate_questions_from_answer(answer)
    
    if not generated_questions:
        return 0.0
    
    similarities = []
    
    for generated_question in generated_questions:
        similarity = compute_similarity(question, generated_question)
        similarities.append(similarity)
    
    return sum(similarities) / len(similarities)

def compute_similarity(q1, q2):
    embedding = embed_chunks([q1, q2])
    
    a, b = embedding[0], embedding[1]
    
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def generate_questions_from_answer(answer, n=3):
    prompt = f"""
    Generate {n} questions that could be answered by the following text.
    
    Rules:
    - Questions should capture the main ideas
    - Each questions should be distinct
    - Do NOT include explanations
    - Return ONLY a Python list of strings
    
    Text:
    {answer}
    """
    
    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[{"role": "user", "content": prompt}]
    )
    
    content = response.choices[0].message.content.strip()
    content = content.replace("```python", "").replace("```", "").strip()

    import ast
    try:
        questions = ast.literal_eval(content)
        return questions if isinstance(questions, list) else []
    except:
        return []
    
    
def compute_context_precision(question, contexts):
    if not contexts:
        return 0.0
    
    query_embedding = embed_chunks([question])[0]
    context_embeddings = embed_chunks(contexts)
    
    similarities = []
    for c in context_embeddings:
        similarity = np.dot(query_embedding, c) / (np.linalg.norm(query_embedding) * np.linalg.norm(c))
        similarities.append(similarity)
    
    return sum(similarities) / len(similarities)


def summarize_results(df):
    return df.groupby("rag_type").mean().reset_index()

def save_rag_results_table(summary, filename="rag_evaluation.csv"):
    save_path = os.path.join("evals", filename)
    
    # Round values for readability
    summary_rounded = summary.round(3)
    
    summary_rounded.to_csv(save_path, index=False)

def run_rag_evaluation(chat_id):
    results = set_up_rag_experiment(chat_id)
    
    df = evaluate_rag(results)
    
    summary = summarize_results(df)
    
    save_rag_results_table(summary)
    
    return

