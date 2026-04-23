"""
Ragas-based RAG quality metrics.

Three metrics:
  faithfulness        - claims in the output are supported by retrieved context
  answer_relevancy    - output addresses the implicit question
  context_precision   - retrieved chunks were relevant (catches RAG regressions)

Requires: pip install ragas
Ragas makes its own LLM calls (configurable via RAGAS_* env vars or by passing llm=).
We point it at the same Azure endpoint to avoid a second API key.
"""

from typing import Optional

from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import answer_relevancy, context_precision, faithfulness

try:
    from langchain_openai import AzureChatOpenAI

    from evals.config import AZURE_API_VERSION, AZURE_ENDPOINT, AZURE_KEY, JUDGE_MODEL

    _llm = AzureChatOpenAI(
        azure_deployment=JUDGE_MODEL,
        azure_endpoint=AZURE_ENDPOINT,
        api_key=AZURE_KEY,
        api_version=AZURE_API_VERSION,
        temperature=0,
    )
    _ragas_llm = LangchainLLMWrapper(_llm)
    _ragas_available = True
except Exception:
    _ragas_available = False


def grade(
    question: str,
    answer: str,
    contexts: list[str],
    ground_truth: Optional[str] = None,
) -> dict:
    """
    Run Ragas metrics for one (question, answer, contexts) triple.

    Returns:
        {
            "faithfulness": float or None,
            "answer_relevancy": float or None,
            "context_precision": float or None,
            "ragas_available": bool,
        }
    """
    if not _ragas_available:
        return {
            "faithfulness": None,
            "answer_relevancy": None,
            "context_precision": None,
            "ragas_available": False,
        }

    from datasets import Dataset

    data = {
        "question": [question],
        "answer": [answer],
        "contexts": [contexts],
    }
    if ground_truth:
        data["ground_truth"] = [ground_truth]

    dataset = Dataset.from_dict(data)

    metrics = [faithfulness, answer_relevancy, context_precision]
    for m in metrics:
        if hasattr(m, "llm"):
            m.llm = _ragas_llm

    result = evaluate(dataset, metrics=metrics)
    row = result.to_pandas().iloc[0]

    return {
        "faithfulness": float(row.get("faithfulness", 0) or 0),
        "answer_relevancy": float(row.get("answer_relevancy", 0) or 0),
        "context_precision": float(row.get("context_precision", 0) or 0),
        "ragas_available": True,
    }
