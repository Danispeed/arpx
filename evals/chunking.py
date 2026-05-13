import numpy as np
from rag.chunking import chunk_text_fixed, chunk_text_llm, chunk_text_sentence, chunk_text_sliding
from itertools import combinations
from rag.utils import split_into_sentences
from rag.embeddings import embed_chunks
import random
import matplotlib.pyplot as plt
import pandas as pd
import os


chunk_sizes = [100, 200, 300, 500]

def chunking_experiment(text, case, runs=5):
    results = []
    for run in range(runs):
        for size in chunk_sizes:
            # Fixed
            chunks = chunk_text_fixed(text, size)
            results.append({
                "run": run,
                "method": "fixed",
                "chunk_size": size,
                "coherence": compute_coherence(chunks),
                "separability": compute_separability(chunks)
            })
            
            # Sliding (overlap is always 1/6 of the chunk size)
            overlap = int(size / 6)
            chunks = chunk_text_sliding(text, size, overlap)
            results.append({
                "run": run,
                "method": "sliding",
                "chunk_size": size,
                "coherence": compute_coherence(chunks),
                "separability": compute_separability(chunks)
            })
            
            # LLM
            chunks = chunk_text_llm(text, size)
            results.append({
                "run": run,
                "method": "llm",
                "chunk_size": size,
                "coherence": compute_coherence(chunks),
                "separability": compute_separability(chunks)
            })
            
            # Sentence
            num_sentences = int(size / 10)
            chunks = chunk_text_sentence(text, num_sentences)
            results.append({
                "run": run,
                "method": "sentence",
                "chunk_size": size,
                "coherence": compute_coherence(chunks),
                "separability": compute_separability(chunks)
            })
    
    df = pd.DataFrame(results)
    summary = summarize_chunking_results(df)
    filename = f"{case['name']}_chunking_evaluation.pdf"
    plot_results(summary, filename)
    return results

def summarize_chunking_results(df):
    metrics = ["coherence", "separability"]
    
    summary = (
        df.groupby(["method", "chunk_size"])[metrics]
        .agg(["mean", "std"])
    )
    
    summary.columns = [
        "_".join(col).strip("_") for col in summary.columns.values
    ]
    
    return summary.reset_index()

def compute_coherence(chunks):
    scores = []
    
    for chunk in chunks:
        sentences = split_into_sentences(chunk)
        
        # Embed sentences
        embeddings = np.array(embed_chunks(sentences))
        
        similarities = []
        # Compute similarity between all pairs of sentences in this chunk
        for a, b in combinations(embeddings, 2):
            # Cosine similarity
            similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
            similarities.append(similarity)
            
        if similarities:
            # Overall score for this chunk
            score = sum(similarities) / len(similarities)
            scores.append(score)
           
    overall_score = sum(scores) / len(scores) if scores else 0
    return overall_score

def compute_separability(chunks, max_pairs=1000):
    embeddings = np.array(embed_chunks(chunks))
    
    # Generate index pairs
    pairs = list(combinations(range(len(embeddings)), 2))
    
    # Sample if too many pairs
    if len(pairs) > max_pairs:
        pairs = random.sample(pairs, max_pairs)
    
    similarities = []
    for i, j in pairs:
        a, b = embeddings[i], embeddings[j]
        similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        similarities.append(similarity)
    
    overall_score = 1 - (sum(similarities) / len(similarities)) if similarities else 0
    return overall_score

def plot_results(df, filename):
    methods = df["method"].unique()
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    metrics = ["coherence", "separability"]
    
    for i, metric in enumerate(metrics):
        ax = axes[i]
        
        mean_col = f"{metric}_mean"
        std_col = f"{metric}_std"
        
        for method in methods:
            subset = df[df["method"] == method].sort_values("chunk_size")
            
            ax.errorbar(
                subset["chunk_size"],
                subset[mean_col],
                yerr=subset[std_col],
                marker="o",
                capsize=5,
                label=method
            )
    
        ax.set_xlabel("Chunk Size")
        ax.set_ylabel(metric.title())
        ax.set_title(f"{metric.title()} vs Chunk Size")
        ax.legend()
        ax.grid(False)
        
    # Save to pdf
    plt.tight_layout()
    save_path = os.path.join("evals", "figures", filename)
    plt.savefig(save_path)
    
    plt.close()
        
        
        