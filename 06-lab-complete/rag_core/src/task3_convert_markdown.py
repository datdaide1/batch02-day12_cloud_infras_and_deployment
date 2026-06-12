"""
Task 3 — Convert toàn bộ file trong data/landing/ thành Markdown.
"""

import json
from pathlib import Path
from loguru import logger
from markitdown import MarkItDown

LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"


def convert_legal_docs():
    """Convert PDF/DOCX files trong data/landing/legal/ sang markdown."""
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)

    md = MarkItDown()

    for filepath in legal_dir.iterdir():
        if filepath.suffix.lower() in (".pdf", ".docx", ".doc"):
            logger.info(f"Converting legal document: {filepath.name}")
            try:
                result = md.convert(str(filepath))
                output_path = output_dir / f"{filepath.stem}.md"
                output_path.write_text(result.text_content, encoding="utf-8")
                logger.success(f"Saved markdown: {output_path.name}")
            except Exception as e:
                logger.error(f"Failed to convert {filepath.name}: {e}")


def convert_news_articles():
    """Convert JSON crawled articles trong data/landing/news/ sang markdown."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)

    for filepath in news_dir.iterdir():
        if filepath.suffix.lower() == ".json":
            logger.info(f"Converting news article: {filepath.name}")
            try:
                data = json.loads(filepath.read_text(encoding="utf-8"))
                output_path = output_dir / f"{filepath.stem}.md"
                
                # Thêm metadata header
                header = f"# {data.get('title', 'Unknown')}\n\n"
                header += f"**Source:** {data.get('url', 'N/A')}\n"
                header += f"**Crawled:** {data.get('date_crawled', 'N/A')}\n\n---\n\n"
                
                content = header + data.get("content_markdown", "")
                output_path.write_text(content, encoding="utf-8")
                logger.success(f"Saved markdown: {output_path.name}")
            except Exception as e:
                logger.error(f"Failed to process news json {filepath.name}: {e}")


def convert_all():
    """Convert toàn bộ files."""
    logger.info("=" * 50)
    logger.info("Task 3: Convert to Markdown (MarkItDown)")
    logger.info("=" * 50)

    logger.info("--- Legal Documents ---")
    convert_legal_docs()

    logger.info("--- News Articles ---")
    convert_news_articles()

    logger.info(f"Done! Output tại: {OUTPUT_DIR}")


if __name__ == "__main__":
    convert_all()

