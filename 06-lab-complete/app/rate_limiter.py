"""
Rate Limiter — Sliding Window Algorithm (in-memory).

Giới hạn số request/phút mỗi API key.
Trong production thật sự: dùng Redis để share state giữa nhiều instances.

Algorithm: Sliding window — xóa timestamps cũ hơn 60s khỏi deque,
nếu còn lại >= limit thì raise 429.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException

from app.config import settings

# Key → deque of timestamps trong 60 giây gần nhất
_rate_windows: dict[str, deque] = defaultdict(deque)


def check_rate_limit(key: str) -> None:
    """
    Kiểm tra rate limit theo sliding window.

    Args:
        key: identifier của user/API key (dùng 8 ký tự đầu của API key)

    Raises:
        HTTPException 429 nếu vượt limit
    """
    now = time.time()
    window = _rate_windows[key]

    # Loại bỏ timestamps cũ hơn 60 giây
    while window and window[0] < now - 60:
        window.popleft()

    if len(window) >= settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {settings.rate_limit_per_minute} requests/minute. Retry after 60s.",
            headers={"Retry-After": "60"},
        )

    window.append(now)


def get_rate_limit_status(key: str) -> dict:
    """Trả về trạng thái rate limit hiện tại của key (dùng cho metrics)."""
    now = time.time()
    window = _rate_windows[key]
    while window and window[0] < now - 60:
        window.popleft()

    used = len(window)
    limit = settings.rate_limit_per_minute
    return {
        "limit": limit,
        "used": used,
        "remaining": max(0, limit - used),
        "reset_in_seconds": 60,
    }
