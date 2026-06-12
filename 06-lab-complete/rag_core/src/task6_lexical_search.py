"""
Task 6 — Lexical Search Module (BM25).
"""

from pathlib import Path
import numpy as np
from loguru import logger
import chromadb
from rank_bm25 import BM25Okapi
from underthesea import word_tokenize

# Global cache cho BM25 index
_bm25_index = None
_corpus_docs = []
_corpus_metas = []

def _get_or_build_index():
    global _bm25_index, _corpus_docs, _corpus_metas
    
    if _bm25_index is not None:
        return _bm25_index
        
    db_path = str(Path(__file__).parent.parent / "data" / "chroma_db")
    client = chromadb.PersistentClient(path=db_path)
    
    try:
        collection = client.get_collection("rag_pipeline")
        all_data = collection.get(include=["documents", "metadatas"])
        
        _corpus_docs = all_data["documents"]
        _corpus_metas = all_data["metadatas"]
        
        if not _corpus_docs:
            return None
            
        logger.info(f"Building BM25 index cho {len(_corpus_docs)} chunks...")
        
        # Tokenize bằng underthesea (tách từ tiếng Việt chuẩn xác)
        tokenized_corpus = [word_tokenize(doc.lower()) for doc in _corpus_docs]
        _bm25_index = BM25Okapi(tokenized_corpus)
        logger.success("BM25 index đã sẵn sàng!")
        return _bm25_index
        
    except Exception as e:
        logger.error(f"Failed to build BM25 index: {e}")
        return None

def lexical_search(query: str, top_k: int = 10, filter_dict: dict = None) -> list[dict]:
    """
    Tìm kiếm từ khóa sử dụng BM25 + underthesea tokenizer.
    """
    bm25 = _get_or_build_index()
    if not bm25:
        return []
        
    norm_query = query.lower().replace("tuý", "túy").replace("hoà", "hòa")
    tokenized_query = word_tokenize(norm_query)
    scores = bm25.get_scores(tokenized_query)
    
    results = []
    for idx in range(len(scores)):
        if scores[idx] > 0:
            meta = _corpus_metas[idx]
            if filter_dict:
                match = True
                for k, v in filter_dict.items():
                    if meta.get(k) != v:
                        match = False
                        break
                if not match:
                    continue
            results.append({
                "content": _corpus_docs[idx],
                "score": float(scores[idx]),
                "metadata": meta
            })
            
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


if __name__ == "__main__":
    results = lexical_search("Điều 248 tàng trữ trái phép chất ma tuý", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")

