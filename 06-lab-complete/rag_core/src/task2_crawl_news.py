"""
Task 2 — Crawl bài báo về nghệ sĩ liên quan tới ma tuý.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from loguru import logger

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"


def setup_directory():
    """Tạo thư mục data/landing/news/ nếu chưa có."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


ARTICLE_URLS = [
    "https://vnexpress.net/ma-tuy-trong-loi-song-showbiz-5074606.html",
    "https://vnexpress.net/nhieu-nguoi-nuoc-ngoai-phe-ma-tuy-trong-khach-san-o-tp-hcm-5082175.html",
    "https://vnexpress.net/ca-si-miu-le-bi-bat-voi-cao-buoc-to-chuc-su-dung-ma-tuy-5074769.html",
    "https://vnexpress.net/anh-em-ca-si-chi-dan-ru-nhieu-nguoi-choi-ma-tuy-nhu-the-nao-4929804.html",
    "https://vnexpress.net/8-nguoi-mo-tiec-ma-tuy-trong-villa-nghi-duong-5074494.html",
]


async def crawl_article(crawler, url: str) -> dict:
    """
    Crawl một bài báo và trả về dict chứa metadata + content.
    """
    try:
        result = await crawler.arun(url=url, magic=True)
        return {
            "url": url,
            "title": result.metadata.get("title", "Unknown Title") if result.metadata else "Unknown Title",
            "date_crawled": datetime.now().isoformat(),
            "content_markdown": result.markdown,
        }
    except Exception as e:
        logger.error(f"Error crawling {url}: {e}")
        return {
            "url": url,
            "title": "Error",
            "date_crawled": datetime.now().isoformat(),
            "content_markdown": f"Failed to crawl: {str(e)}"
        }


async def crawl_all():
    """Crawl toàn bộ bài báo trong ARTICLE_URLS."""
    setup_directory()
    
    from crawl4ai import AsyncWebCrawler
    
    logger.info(f"Bắt đầu crawl {len(ARTICLE_URLS)} bài báo...")
    async with AsyncWebCrawler() as crawler:
        tasks = [crawl_article(crawler, url) for url in ARTICLE_URLS]
        results = await asyncio.gather(*tasks)
        
        for i, article in enumerate(results, 1):
            if article["title"] == "Error":
                continue
                
            filename = f"article_{i:02d}.json"
            filepath = DATA_DIR / filename
            filepath.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding='utf-8')
            logger.success(f"Saved: {filepath.name} - {article['title']}")


if __name__ == "__main__":
    if not ARTICLE_URLS:
        print("⚠ Hãy điền ARTICLE_URLS trước khi chạy!")
    else:
        asyncio.run(crawl_all())


