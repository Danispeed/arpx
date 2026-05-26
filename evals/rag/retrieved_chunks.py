import time
import pandas as pd
from evals.rag.rag_types import rag_methods, compute_faithfulness, compute_answer_relevancy, compute_context_precision
import matplotlib.pyplot as plt
import os

def run_k_experiment(chat_id, case, k_values=[2, 4, 6, 8, 10], runs=5):
    results = []
    
    for run in range(runs):
        for rag_name, retrieve_func in rag_methods.items():
            for k in k_values:
                for question in case["questions"]:
                    start = time.time()
                    
                    k_ref = max(1, k // 2)
                    chunks = retrieve_func(question, chat_id, k, k_ref)
                    
                    from agents.supervisor import generate_message_response
                    response, _ = generate_message_response(question, 5, chat_id, [], retrieve_func, k, k_ref)
                    
                    end = time.time()
                    latency = end - start
                    
                    answer = response.get("text_explanation", "")
                    
                    # Skip failed backend calls
                    if answer.startswith("Error"):
                        continue
                    
                    # Compute metrics
                    faith = compute_faithfulness(answer, chunks)
                    relevancy = compute_answer_relevancy(question, answer)
                    context_score = compute_context_precision(question, chunks)
                    
                    results.append({
                        "run": run,
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
    summary = (
        df.groupby(["rag_type", "k"])[metrics]
        .agg(["mean", "std"])
    )
    
    summary.columns = [
        "_".join(col).strip("_") for col in summary.columns.values
    ]
    
    return summary.reset_index()

def plot_metric_vs_k(df, filename):
    metrics = ["faithfulness", "answer_relevancy", "context_precision"]
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    for i, metric in enumerate(metrics):
        ax = axes[i]
        
        for rag_type in df["rag_type"].unique():
            subset = df[df["rag_type"] == rag_type].sort_values("k")
            
            ax.errorbar(
                subset["k"],
                subset[f"{metric}_mean"],
                yerr=subset[f"{metric}_std"],
                marker="o",
                capsize=5,
                label=rag_type
            )
                    
        ax.set_title(metric.replace("_", " ").title())
        ax.set_xlabel("k")
        ax.set_ylabel("Score")
        ax.legend()
    
    plt.tight_layout()
    
    save_path = os.path.join("evals", "figures", filename)
    plt.savefig(save_path)
    plt.close()    
    
def plot_latency_vs_k(df, filename):
    plt.figure()
    
    for rag_type in df["rag_type"].unique():
        subset = df[df["rag_type"] == rag_type].sort_values("k")
        
        plt.errorbar(
            subset["k"],
            subset["latency_mean"],
            yerr=subset["latency_std"],
            marker="o",
            capsize=5,
            label=rag_type
        )    
    
    plt.xlabel("k")
    plt.ylabel("Latency (s)")
    plt.title("Latency vs k")
    plt.legend()
    
    save_path = os.path.join("evals", "figures", filename)
    plt.savefig(save_path)
    plt.close()

def plot_tradeoff(df, filename):
    metrics = ["faithfulness", "answer_relevancy", "context_precision"]
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    for i, metric in enumerate(metrics):
        ax = axes[i]
        
        for rag_type in df["rag_type"].unique():
            subset = df[df["rag_type"] == rag_type].sort_values("k")
            
            ax.scatter(
                subset["latency_mean"],
                subset[f"{metric}_mean"],
                label=rag_type
            )
            
            for _, row in subset.iterrows():
                ax.text(
                    row["latency_mean"] + 0.1,
                    row[f"{metric}_mean"] + 0.005,
                    str(int(row["k"])),
                    fontsize=8
                )
        
        ax.set_xlabel("Latency (s)")
        ax.set_ylabel(metric.replace("_", " ").title())
        ax.set_title(f"{metric.replace('_', ' ').title()} vs Latency") 
        ax.legend()
    
    plt.tight_layout()
    
    save_path = os.path.join("evals", "figures", filename)
    plt.savefig(save_path)
    plt.close()  

def run_full_k_experiment(cases):
    all_results = []
    
    for case in cases:
        chat_id = case["chat_id"]
        df = run_k_experiment(chat_id, case)
        df["paper"] = case["name"]

        all_results.append(df)
        
    final_df = pd.concat(all_results, ignore_index=True)
    summary = summarize_k_results(final_df)
    
    plot_metric_vs_k(summary, "metric_vs_k.pdf")
    plot_latency_vs_k(summary, "latency_vs_k.pdf")
    plot_tradeoff(summary, "tradeoff.pdf")
    
    return