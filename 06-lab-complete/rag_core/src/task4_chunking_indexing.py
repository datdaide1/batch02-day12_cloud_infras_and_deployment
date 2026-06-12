"""
Task 4 — Chunking & Indexing vào Vector Store.
"""

import json
from pathlib import Path
from loguru import logger

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"

# =============================================================================
# CONFIGURATION 
# =============================================================================

# Chunking Strategy: Kết hợp MarkdownHeaderTextSplitter để giữ context của từng 
# điều/chương trong văn bản luật, và RecursiveCharacterTextSplitter để chia nhỏ 
# các chunk quá dài.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "markdown_header + recursive"

# Embedding Model: Sử dụng local model từ path đã cho để tiết kiệm resource
EMBEDDING_MODEL = r"E:\VINUNI\2A202600807-TranHoangDat-Day07\model\models--sentence-transformers--all-MiniLM-L6-v2\snapshots\c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
EMBEDDING_DIM = 1024 # dim của bge-m3

# Vector Store: Dùng ChromaDB vì không có Docker.
VECTOR_STORE = "chromadb"


# =============================================================================
# IMPLEMENTATION
# =============================================================================

def load_documents() -> list[dict]:
    """
    Đọc toàn bộ markdown files từ data/standardized/.
    """
    documents = []
    if not STANDARDIZED_DIR.exists():
        logger.warning(f"{STANDARDIZED_DIR} không tồn tại.")
        return documents

    for md_file in STANDARDIZED_DIR.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        doc_type = "legal" if "legal" in str(md_file) else "news"
        documents.append({
            "content": content,
            "metadata": {"source": md_file.name, "type": doc_type}
        })
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Chunk documents theo strategy đã chọn.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
    
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    
    rec_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    chunks = []
    for doc in documents:
        # Tách theo markdown header trước
        md_splits = md_splitter.split_text(doc["content"])
        
        # Nếu không có header nào, md_splits sẽ gộp hết, ta tách tiếp bằng recursive
        for i, split in enumerate(md_splits):
            rec_splits = rec_splitter.split_text(split.page_content)
            for j, chunk_text in enumerate(rec_splits):
                # Gộp metadata của header vào chung với metadata gốc
                merged_meta = {**doc["metadata"], **split.metadata, "chunk_index": f"{i}_{j}"}
                chunks.append({
                    "content": chunk_text,
                    "metadata": merged_meta
                })
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Embed toàn bộ chunks bằng model đã chọn.
    """
    from sentence_transformers import SentenceTransformer
    
    logger.info(f"Loading embedding model từ: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)
    texts = [c["content"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=True)
    
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb.tolist()
    return chunks


def index_to_vectorstore(chunks: list[dict]):
    """
    Lưu chunks vào vector store đã chọn.
    """
    import chromadb
    
    db_path = str(Path(__file__).parent.parent / "data" / "chroma_db")
    client = chromadb.PersistentClient(path=db_path)
    
    # Reset collection nếu chạy lại
    try:
        client.delete_collection("rag_pipeline")
    except Exception:
        pass
        
    collection = client.create_collection(
        name="rag_pipeline",
        metadata={"hnsw:space": "cosine"}
    )
    
    ids = [f"chunk_{i}" for i in range(len(chunks))]
    embeddings = [c["embedding"] for c in chunks]
    documents = [c["content"] for c in chunks]
    # ChromaDB metadata values must be str, int, float, or bool
    metadatas = []
    for c in chunks:
        meta = c["metadata"].copy()
        # Chuẩn hoá metadata
        for k, v in meta.items():
            if not isinstance(v, (str, int, float, bool)):
                meta[k] = str(v)
        metadatas.append(meta)
        
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )
    logger.success(f"Đã lưu {len(chunks)} chunks vào ChromaDB tại {db_path}")


def run_pipeline():
    """Chạy toàn bộ pipeline: load → chunk → embed → index."""
    logger.info("=" * 50)
    logger.info("Task 4: Chunking & Indexing")
    logger.info(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    logger.info(f"  Embedding: {EMBEDDING_MODEL}")
    logger.info(f"  Vector Store: {VECTOR_STORE}")
    logger.info("=" * 50)

    docs = load_documents()
    logger.info(f"Loaded {len(docs)} documents")

    chunks = chunk_documents(docs)
    logger.info(f"Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    logger.info(f"Embedded {len(chunks)} chunks")

    index_to_vectorstore(chunks)


if __name__ == "__main__":
    run_pipeline()

