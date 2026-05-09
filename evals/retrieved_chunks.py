import time
import pandas as pd
from evals.rag_types import rag_methods, questions, compute_faithfulness, compute_answer_relevancy, compute_context_precision
import matplotlib.pyplot as plt
import os

def run_k_experiment(chat_id, k_values=[2, 4, 6, 8, 10]):
    results = []
    
    for rag_name, retrieve_func in rag_methods.items():
        for k in k_values:
            for question in questions:
                start = time.time()
                
                chunks = retrieve_func(question, chat_id, k)
                
                from agents.supervisor import generate_message_response
                response = generate_message_response(question, 5, chat_id, [], retrieve_func, k)
                
                end = time.time()
                latency = end - start
                
                answer = response["text_explanation"]
                
                # Compute metrics
                faith = compute_faithfulness(answer, chunks)
                relevancy = compute_answer_relevancy(question, answer)
                context_score = compute_context_precision(question, chunks)
                
                results.append({
                    "rag_type": rag_name,
                    "k": k,
                    "question": question,
                    "faithfulness": faith,
                    "answer_relevancy": relevancy,
                    "context_precision": context_score,
                    "latency": latency
                })
    return pd.DataFrame(results)

def summarize_k_results(df):
    metrics = ["faithfulness", "answer_relevancy", "context_precision", "latency"]
    return df.groupby(["rag_type", "k"])[metrics].mean().reset_index()

def plot_metric_vs_k(df, filename="metric_vs_k.pdf"):
    metrics = ["faithfulness", "answer_relevancy", "context_precision"]
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    for i, metric in enumerate(metrics):
        ax = axes[i]
        
        for rag_type in df["rag_type"].unique():
            subset = df[df["rag_type"] == rag_type].sort_values("k")
            
            ax.plot(
                subset["k"],
                subset[metric],
                marker="o",
                label=rag_type
            )
        
        ax.set_title(metric.replace("_", " ").title())
        ax.set_xlabel("k")
        ax.set_ylabel("Score")
        ax.legend()
    
    plt.tight_layout()
    
    save_path = os.path.join("evals", filename)
    plt.savefig(save_path)
    plt.close()    
    
def plot_latency_vs_k(df, filename="latency_vs_k.pdf"):
    plt.figure()
    
    for rag_type in df["rag_type"].unique():
        subset = df[df["rag_type"] == rag_type].sort_values("k")
        
        plt.plot(
            subset["k"],
            subset["latency"],
            marker="o",
            label=rag_type
        )    
    
    plt.xlabel("k")
    plt.ylabel("Latency (s)")
    plt.title("Latency vs k")
    plt.legend()
    
    save_path = os.path.join("evals", filename)
    plt.savefig(save_path)
    plt.close()

def plot_tradeoff(df, filename="tradeoff.pdf"):
    metrics = ["faithfulness", "answer_relevancy", "context_precision"]
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    for i, metric in enumerate(metrics):
        ax = axes[i]
        
        for rag_type in df["rag_type"].unique():
            subset = df[df["rag_type"] == rag_type].sort_values("k")
            
            ax.scatter(
                subset["latency"],
                subset[metric],
                label=rag_type
            )
            
            for _, row in subset.iterrows():
                ax.text(
                    row["latency"],
                    row[metric],
                    str(int(row["k"])),
                    fontsize=8
                )
        
        ax.set_xlabel("Latency (s)")
        ax.set_ylabel(metric.replace("_", " ").title())
        ax.set_title(f"{metric.replace('_', ' ').title()} vs Latency") 
        ax.legend()
    
    plt.tight_layout()
    
    save_path = os.path.join("evals", filename)
    plt.savefig(save_path)
    plt.close()  

def run_full_k_experiment(chat_id):
    df = run_k_experiment(chat_id)
    
    summary = summarize_k_results(df)
    
    plot_metric_vs_k(summary)
    plot_latency_vs_k(summary)
    plot_tradeoff(summary)
    
    return