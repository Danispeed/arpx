from evals.rag_types import rag_methods, compute_faithfulness, compute_answer_relevancy, compute_context_precision
import pandas as pd
import matplotlib.pyplot as plt
import os

retrieval_configs = [
    (10, 0),
    (8, 2),
    (6, 4),
    (4, 6),
    (2, 8)
]

def run_reference_ratio_experiment(chat_id, case):
    results = []
    
    for rag_name, retrieve_func in rag_methods.items():
        for k_main, k_ref in retrieval_configs:
            ref_ratio = k_ref / (k_main + k_ref)
            for question in case["questions"]:
                chunks = retrieve_func(question, chat_id, k_main, k_ref)

                from agents.supervisor import generate_message_response
                
                response, _ = generate_message_response(
                    question,
                    5,
                    chat_id,
                    [],
                    retrieve_func,
                    k_main,
                    k_ref
                )

                answer = response.get("text_explanation", "")
                
                # Skip failed backend calls
                if answer.startswith("Error"):
                    print(f"[skip] {rag_name} | {question} -> {answer}")
                    continue
                
                faithfulness = compute_faithfulness(answer, chunks)
                answer_relevancy = compute_answer_relevancy(question, answer)
                context_precision = compute_context_precision(question, chunks)
                
                results.append({
                    "rag_type": rag_name,
                    "k_main": k_main,
                    "k_ref": k_ref,
                    "ref_ratio": ref_ratio,
                    "question": question,
                    "faithfulness": faithfulness,
                    "answer_relevancy": answer_relevancy,
                    "context_precision": context_precision
                })
    
    return pd.DataFrame(results)


def summarize_reference_results(df):
    metrics = ["faithfulness", "answer_relevancy", "context_precision"]
    
    summary = df.groupby(["rag_type", "ref_ratio"])[metrics].agg(["mean", "std"])
    
    summary.columns = ["_".join(col).strip("_") for col in summary.columns.values]
    
    return summary.reset_index()

def plot_reference_results(df, filename):
    metrics = ["faithfulness", "answer_relevancy", "context_precision"]
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    for i, metric in enumerate(metrics):
        ax = axes[i]
        
        mean_col = f"{metric}_mean"
        std_col = f"{metric}_std"
        
        for rag_type in df["rag_type"].unique():
            subset = df[df["rag_type"] == rag_type].sort_values("ref_ratio")
            
            ax.errorbar(
                subset["ref_ratio"],
                subset[mean_col],
                yerr=subset[std_col],
                marker="o",
                capsize=5,
                label=rag_type
            )
        
        ax.set_title(metric.replace("_", " ").title())
        ax.set_xlabel("Reference Ratio")
        ax.set_ylabel("Score")
        
        ax.legend()
    
    plt.tight_layout()
    
    save_path = os.path.join("evals", "figures", filename)
    plt.savefig(save_path)
    plt.close()
    
def run_full_reference_ratio_experiment(cases):
    all_results = []
    
    for case in cases:
        chat_id = case["chat_id"]
        print("Doing ratio experiment on paper:", case["name"])
        df = run_reference_ratio_experiment(chat_id, case)
        df["paper"] = case["name"]
        all_results.append(df)
    
    final_df = pd.concat(all_results, ignore_index=True)
    summary = summarize_reference_results(final_df)
    plot_reference_results(summary, "reference_ratio.pdf")
    