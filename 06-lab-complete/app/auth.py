"""
Authentication module — API Key verification.

Cung cấp FastAPI dependency `verify_api_key` để bảo vệ các endpoint.
Key được đọc từ environment variable AGENT_API_KEY.
"""
from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    FastAPI dependency: kiểm tra API key trong header X-API-Key.

    Returns:
        api_key (str) nếu hợp lệ

    Raises:
        HTTPException 401 nếu thiếu hoặc sai key
    """
    if not api_key or api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key: <key>",
        )
    return api_key
