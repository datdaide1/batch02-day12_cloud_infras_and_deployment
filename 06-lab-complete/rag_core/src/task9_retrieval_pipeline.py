"""
Task 9 — Retrieval Pipeline Hoàn Chỉnh (Bonus: HyDE).
"""

import os
from .task5_semantic_search import semantic_search
from .task6_lexical_search import lexical_search
from .task7_reranking import rerank, rerank_rrf
from .task8_pageindex_vectorless import pageindex_search
from loguru import logger
import threading

# =============================================================================
# CONFIGURATION
# =============================================================================

SCORE_THRESHOLD = 0.5   # Nếu best score < threshold → fallback PageIndex
DEFAULT_TOP_K = 5
RERANK_METHOD = "cross_encoder"  # "cross_encoder" | "rrf"
USE_HYDE = True

# Thử load OpenAI key cho HyDE
from dotenv import load_dotenv
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

def generate_hyde_document(query: str) -> str:
    """
    Sinh ra một tài liệu giả định (HyDE) để cải thiện semantic search.
    """
    if not OPENAI_API_KEY:
        return query
        
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a legal expert in Vietnam. Write a concise factual snippet that directly answers the user's query about drug laws or related news."},
                {"role": "user", "content": query}
            ],
            temperature=0.3,
            max_tokens=150
        )
        fake_doc = response.choices[0].message.content.strip()
        logger.info("HyDE document generated successfully.")
        return fake_doc
    except Exception as e:
        logger.warning(f"HyDE generation failed: {e}. Falling back to raw query.")
        return query


def route_query(query: str) -> dict:
    """
    Classify query into 'legal', 'news' or None (both)
    """
    legal_keywords = ["luật", "nghị định", "pháp luật", "quy định", "điều", "pháp lệnh", "thông tư", "hình phạt", "tội", "xử phạt", "cai nghiện bắt buộc", "chất cấm"]
    news_keywords = ["nghệ sĩ", "ca sĩ", "diễn viên", "người mẫu", "bị bắt", "an tây", "andrea aybar", "chi dân", "trúc phương", "miu lê", "showbiz", "villa", "khách sạn"]
    
    query_lower = query.lower()
    
    is_legal = any(kw in query_lower for kw in legal_keywords)
    is_news = any(kw in query_lower for kw in news_keywords)
    
    if is_legal and not is_news:
        return {"type": "legal"}
    elif is_news and not is_legal:
        return {"type": "news"}
    return None


def route_query(query: str) -> dict:
    """
    Classify query into 'legal', 'news' or None (both)
    """
    legal_keywords = ["luật", "nghị định", "pháp luật", "quy định", "điều", "pháp lệnh", "thông tư", "hình phạt", "tội", "xử phạt", "cai nghiện bắt buộc", "chất cấm"]
    news_keywords = ["nghệ sĩ", "ca sĩ", "diễn viên", "người mẫu", "bị bắt", "an tây", "andrea aybar", "chi dân", "trúc phương", "miu lê", "showbiz", "villa", "khách sạn"]
    
    query_lower = query.lower()
    
    is_legal = any(kw in query_lower for kw in legal_keywords)
    is_news = any(kw in query_lower for kw in news_keywords)
    
    if is_legal and not is_news:
        return {"type": "legal"}
    elif is_news and not is_legal:
        return {"type": "news"}
    return None


def expand_query(query: str) -> str:
    """
    Normalize spelling variations and expand query with synonyms to fix vocabulary mismatch.
    """
    query_lower = query.lower()
    expanded = query
    if "nghệ sĩ" in query_lower or "nghệ sỹ" in query_lower:
        expanded += " ca sĩ diễn viên người mẫu tiktoker"
    expanded = expanded.replace("tuý", "túy").replace("hoà", "hòa")
    return expanded


def filter_diverse_results(results: list[dict], top_k: int = 5, max_per_source: int = 2) -> list[dict]:
    """
    Select results prioritizing unique sources to ensure diverse context and prevent redundant chunks.
    """
    seen_sources = {}
    selected = []
    
    # First pass: take up to max_per_source chunks from each unique source
    for item in results:
        source = item.get("metadata", {}).get("source", "")
        if source:
            count = seen_sources.get(source, 0)
            if count < max_per_source:
                selected.append(item)
                seen_sources[source] = count + 1
                if len(selected) >= top_k:
                    break
                
    # Second pass: if more items are needed, fill in with remaining chunks
    if len(selected) < top_k:
        for item in results:
            if item not in selected:
                selected.append(item)
            if len(selected) >= top_k:
                break
                
    return selected


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
) -> list[dict]:
    """
    Retrieval pipeline hoàn chỉnh với fallback logic và HyDE.
    """
    logger.info(f"Retrieving query: '{query}'")
    
    # 1. Expand query & HyDE
    search_query = expand_query(query)
    if USE_HYDE:
        search_query = generate_hyde_document(search_query)
    
    filter_dict = route_query(query)
    logger.info(f"Query routed with filter: {filter_dict}")
    
    dense_results = []
    sparse_results = []
    
    # Retrieve larger pool for diversification
    candidate_limit = max(top_k * 4, 20)
    
    # 2. Parallel Semantic & Lexical Search
    def run_dense():
        nonlocal dense_results
        dense_results = semantic_search(search_query, top_k=candidate_limit, filter_dict=filter_dict)
        
    def run_sparse():
        nonlocal sparse_results
        sparse_results = lexical_search(search_query, top_k=candidate_limit, filter_dict=filter_dict)
        
    t1 = threading.Thread(target=run_dense)
    t2 = threading.Thread(target=run_sparse)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    # 3. Merge (RRF) with weights to prioritize high-quality BM25 over noisy semantic search
    merged = rerank_rrf([dense_results, sparse_results], top_k=candidate_limit, weights=[0.1, 0.9])
    for item in merged:
        item["source"] = "hybrid"
        
    # 4. Reranking (Jina)
    final_results = merged
    if use_reranking and merged:
        final_results = rerank(query, merged, top_k=candidate_limit, method=RERANK_METHOD)
    else:
        final_results = merged[:candidate_limit]
        
    # Apply diversity filter
    doc_type = filter_dict.get("type") if filter_dict else None
    max_per_src = 3 if doc_type == "legal" else 1
    diverse_results = filter_diverse_results(final_results, top_k=top_k, max_per_source=max_per_src)
    
    # Adjust score threshold dynamically for RRF scores vs Jina relevance scores
    current_threshold = score_threshold
    if final_results and final_results[0]["score"] < 0.1:
        current_threshold = 0.005
        
    # 5. Check threshold → Fallback
    if not diverse_results or final_results[0]["score"] < current_threshold:
        best_score = final_results[0]['score'] if final_results else 0
        logger.warning(f"Hybrid score ({best_score:.3f}) < threshold ({current_threshold}). Fallback → PageIndex")
        
        fallback = pageindex_search(query, top_k=top_k)
        if fallback:
            return filter_diverse_results(fallback, top_k=top_k, max_per_source=max_per_src)
        logger.warning("PageIndex failed/empty. Returning best hybrid results.")
        
    return diverse_results


if __name__ == "__main__":
    test_queries = [
        "Hình phạt cho tội tàng trữ trái phép chất ma tuý",
        "Nghệ sĩ nào bị bắt vì sử dụng ma tuý năm 2024",
        "Luật phòng chống ma tuý 2021 quy định gì về cai nghiện",
    ]

    for q in test_queries:
        print(f"\nQuery: {q}")
        print("-" * 60)
        results = retrieve(q, top_k=3)
        for i, r in enumerate(results, 1):
            print(f"  {i}. [{r.get('score', 0):.3f}] [{r.get('source', 'reranked')}] {r['content'][:80]}...")

