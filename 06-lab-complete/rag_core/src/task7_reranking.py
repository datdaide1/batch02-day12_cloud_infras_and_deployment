"""
Task 7 — Reranking Module.
"""

import os
from typing import Optional
import requests
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Jina API key from env
JINA_API_KEY = os.getenv("JINA_API_KEY", "")

def rerank_cross_encoder(
    query: str, candidates: list[dict], top_k: int = 5
) -> list[dict]:
    """
    Rerank candidates sử dụng Jina Reranker v2.
    """
    if not candidates:
        return []
        
    try:
        # Check if the key is default/empty/invalid to avoid useless API calls
        if not JINA_API_KEY or JINA_API_KEY.startswith("YOUR_"):
            raise ValueError("Jina API Key is missing or invalid.")

        response = requests.post(
            "https://api.jina.ai/v1/rerank",
            headers={"Authorization": f"Bearer {JINA_API_KEY}"},
            json={
                "model": "jina-reranker-v2-base-multilingual",
                "query": query,
                "documents": [c["content"] for c in candidates],
                "top_n": min(top_k, len(candidates))
            },
            timeout=15
        )
        response.raise_for_status()
        reranked = response.json()["results"]
        
        return [
            {**candidates[r["index"]], "score": r["relevance_score"], "rerank_fallback": False}
            for r in reranked
        ]
    except Exception as e:
        logger.warning(f"Jina Reranker API failed ({e}). Automatically falling back to local Reciprocal Rank Fusion (RRF).")
        # Return candidates with fallback flag set to True
        fallback_results = []
        for c in candidates[:top_k]:
            item = c.copy()
            item["rerank_fallback"] = True
            fallback_results.append(item)
        return fallback_results


def rerank_rrf(
    ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60, weights: list[float] = None
) -> list[dict]:
    """
    Reciprocal Rank Fusion — gộp kết quả từ nhiều ranker (BM25 + Semantic).
    """
    rrf_scores = {}  
    content_map = {} 
    
    if weights is None:
        weights = [1.0] * len(ranked_lists)
        
    for list_idx, ranked_list in enumerate(ranked_lists):
        w = weights[list_idx] if list_idx < len(weights) else 1.0
        for rank, item in enumerate(ranked_list, 1):
            key = item["content"]
            rrf_scores[key] = rrf_scores.get(key, 0) + w * (1 / (k + rank))
            if key not in content_map:
                content_map[key] = item.copy()
    
    # Sort by RRF score
    sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    
    results = []
    for content, score in sorted_items[:top_k]:
        item = content_map[content]
        item["score"] = score
        results.append(item)
    
    return results


def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
    method: str = "cross_encoder",  # "cross_encoder" | "rrf"
    **kwargs
) -> list[dict]:
    """
    Unified reranking interface.
    """
    if method == "cross_encoder":
        return rerank_cross_encoder(query, candidates, top_k)
    elif method == "rrf":
        ranked_lists = kwargs.get("ranked_lists")
        if not ranked_lists:
            raise ValueError("RRF cần tham số ranked_lists")
        return rerank_rrf(ranked_lists, top_k)
    else:
        raise ValueError(f"Unknown rerank method: {method}")


if __name__ == "__main__":
    # Test with dummy data
    dummy_candidates = [
        {"content": "Điều 248: Tội tàng trữ trái phép chất ma tuý", "score": 0.8, "metadata": {}},
        {"content": "Nghệ sĩ X bị bắt vì sử dụng ma tuý", "score": 0.7, "metadata": {}},
        {"content": "Hình phạt tù từ 2-7 năm cho tội tàng trữ", "score": 0.6, "metadata": {}},
    ]
    results = rerank("hình phạt tàng trữ ma tuý", dummy_candidates, top_k=2)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content']}")
