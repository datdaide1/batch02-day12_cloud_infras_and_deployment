"""
Task 8 — PageIndex Vectorless RAG.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"


def upload_documents():
    """
    Upload toàn bộ markdown documents lên PageIndex.
    """
    if not PAGEINDEX_API_KEY:
        logger.warning("Không có PAGEINDEX_API_KEY. Bỏ qua upload.")
        return
        
    try:
        from pageindex import PageIndex
        pi = PageIndex(api_key=PAGEINDEX_API_KEY)
        
        for md_file in STANDARDIZED_DIR.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            pi.upload(
                content=content,
                metadata={"filename": md_file.name, "type": md_file.parent.name}
            )
            logger.info(f"Uploaded to PageIndex: {md_file.name}")
    except Exception as e:
        logger.error(f"Lỗi khi upload lên PageIndex: {e}")


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Vectorless retrieval sử dụng PageIndex.
    """
    if not PAGEINDEX_API_KEY:
        logger.warning("Không có PAGEINDEX_API_KEY. Trả về list rỗng.")
        return []
        
    try:
        from pageindex import PageIndex
        pi = PageIndex(api_key=PAGEINDEX_API_KEY)
        results = pi.query(query=query, top_k=top_k)
        
        return [
            {
                "content": r.text,
                "score": getattr(r, "score", 0.0), # Phòng trường hợp API trả về khác
                "metadata": getattr(r, "metadata", {}),
                "source": "pageindex"
            }
            for r in results
        ]
    except Exception as e:
        logger.error(f"Lỗi PageIndex search: {e}")
        return []


if __name__ == "__main__":
    if not PAGEINDEX_API_KEY:
        print("⚠ Hãy set PAGEINDEX_API_KEY trong file .env")
    else:
        print("Uploading documents...")
        upload_documents()

        print("\nTest query:")
        results = pageindex_search("hình phạt sử dụng ma tuý", top_k=3)
        for r in results:
            print(f"[{r['score']:.3f}] {r['content'][:100]}...")

