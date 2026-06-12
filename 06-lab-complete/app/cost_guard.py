"""
Cost Guard — Bảo vệ budget LLM.

Theo dõi chi phí token mỗi ngày theo từng user.
Reset lúc 0h UTC mỗi ngày.

Giá token mặc định (GPT-4o-mini):
  - Input:  $0.15 / 1M tokens  → $0.00015 / 1K
  - Output: $0.60 / 1M tokens  → $0.00060 / 1K

Trong production thật sự: dùng Redis để persist qua restarts.
"""
import time
import logging
from dataclasses import dataclass, field

from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

PRICE_PER_1K_INPUT = 0.00015   # USD per 1K input tokens
PRICE_PER_1K_OUTPUT = 0.00060  # USD per 1K output tokens


@dataclass
class _DailyUsage:
    """Record chi phí của một user trong ngày."""
    user_id: str
    day: str = field(default_factory=lambda: time.strftime("%Y-%m-%d"))
    input_tokens: int = 0
    output_tokens: int = 0
    request_count: int = 0

    @property
    def total_cost_usd(self) -> float:
        return round(
            (self.input_tokens / 1000) * PRICE_PER_1K_INPUT +
            (self.output_tokens / 1000) * PRICE_PER_1K_OUTPUT,
            6,
        )


# In-memory store: user_id -> DailyUsage
_usage_store: dict[str, _DailyUsage] = {}
# Global daily cost counter
_global_cost = 0.0
_global_reset_day = time.strftime("%Y-%m-%d")


def _get_usage(user_id: str) -> _DailyUsage:
    """Lấy hoặc tạo mới record cho user, reset nếu sang ngày mới."""
    today = time.strftime("%Y-%m-%d")
    record = _usage_store.get(user_id)
    if not record or record.day != today:
        _usage_store[user_id] = _DailyUsage(user_id=user_id, day=today)
    return _usage_store[user_id]


def check_budget(user_id: str) -> None:
    """
    Kiểm tra budget trước khi gọi LLM.

    Args:
        user_id: identifier của user

    Raises:
        HTTPException 402 nếu user vượt daily budget
        HTTPException 503 nếu global budget cạn kiệt
    """
    global _global_cost, _global_reset_day

    # Reset global counter nếu sang ngày mới
    today = time.strftime("%Y-%m-%d")
    if today != _global_reset_day:
        _global_cost = 0.0
        _global_reset_day = today

    # Kiểm tra global budget
    if _global_cost >= settings.daily_budget_usd * 2:  # global = 2x per-user budget
        logger.critical(f"GLOBAL DAILY BUDGET EXHAUSTED: ${_global_cost:.4f}")
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable due to global budget limits. Try again tomorrow.",
        )

    # Kiểm tra per-user budget
    record = _get_usage(user_id)
    if record.total_cost_usd >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Daily budget exceeded",
                "used_usd": record.total_cost_usd,
                "budget_usd": settings.daily_budget_usd,
                "resets_at": "midnight UTC",
            },
        )

    # Cảnh báo khi dùng > 80% budget
    usage_pct = record.total_cost_usd / settings.daily_budget_usd
    if usage_pct >= 0.8:
        logger.warning(
            f"User {user_id} at {usage_pct*100:.0f}% daily budget "
            f"(${record.total_cost_usd:.4f} / ${settings.daily_budget_usd})"
        )


def record_usage(user_id: str, input_tokens: int, output_tokens: int) -> dict:
    """
    Ghi nhận token usage sau khi LLM trả về.

    Args:
        user_id: identifier của user
        input_tokens: số tokens input
        output_tokens: số tokens output

    Returns:
        dict với thông tin usage hiện tại
    """
    global _global_cost

    record = _get_usage(user_id)
    record.input_tokens += input_tokens
    record.output_tokens += output_tokens
    record.request_count += 1

    call_cost = (
        (input_tokens / 1000) * PRICE_PER_1K_INPUT +
        (output_tokens / 1000) * PRICE_PER_1K_OUTPUT
    )
    _global_cost += call_cost

    logger.info(
        f"cost_record user={user_id} req={record.request_count} "
        f"cost=${record.total_cost_usd:.4f}/{settings.daily_budget_usd}"
    )

    return {
        "user_id": user_id,
        "date": record.day,
        "requests": record.request_count,
        "cost_usd": record.total_cost_usd,
        "budget_usd": settings.daily_budget_usd,
        "remaining_usd": max(0, settings.daily_budget_usd - record.total_cost_usd),
    }
