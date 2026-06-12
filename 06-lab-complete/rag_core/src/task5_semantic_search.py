"""
Task 5 — Semantic Search Module.
"""

from pathlib import Path

def semantic_search(query: str, top_k: int = 10, filter_dict: dict = None) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa sử dụng vector similarity (ChromaDB).
    """
    import chromadb
    from sentence_transformers import SentenceTransformer
    
    # Load model
    model_path = r"E:\VINUNI\2A202600807-TranHoangDat-Day07\model\models--sentence-transformers--all-MiniLM-L6-v2\snapshots\c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
    model = SentenceTransformer(model_path)
    query_embedding = model.encode(query).tolist()
    
    # Kết nối ChromaDB
    db_path = str(Path(__file__).parent.parent / "data" / "chroma_db")
    client = chromadb.PersistentClient(path=db_path)
    
    try:
        collection = client.get_collection(name="rag_pipeline")
    except Exception:
        # Nếu chưa có collection thì trả về list rỗng
        return []
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=filter_dict,
        include=["documents", "metadatas", "distances"]
    )
    
    output = []
    if not results["documents"] or not results["documents"][0]:
        return output
        
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        # dist là cosine distance (0 đến 2). Similarity = 1 - dist
        score = 1.0 - dist
        output.append({
            "content": doc,
            "score": float(score),
            "metadata": meta
        })
    
    # Đảm bảo sorted descending
    output.sort(key=lambda x: x["score"], reverse=True)
    return output


if __name__ == "__main__":
    results = semantic_search("hình phạt cho tội tàng trữ ma tuý", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")

