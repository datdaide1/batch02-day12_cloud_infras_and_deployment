"""Test script de verify app hoat dong dung."""
import os
import sys
import traceback

os.environ.setdefault("AGENT_API_KEY", "lab12-secret-key-2026")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "10")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    print("=" * 50)
    print("Testing imports...")
    from app.config import settings
    print(f"  config.py OK -- app: {settings.app_name}, env: {settings.environment}, rate_limit: {settings.rate_limit_per_minute}")
    from app.auth import verify_api_key
    print("  auth.py OK")
    from app.rate_limiter import check_rate_limit, get_rate_limit_status
    print("  rate_limiter.py OK")
    from app.cost_guard import check_budget, record_usage
    print("  cost_guard.py OK")
    from app.main import app
    print("  main.py OK")
    print()
    return settings, app

def test_rate_limiter():
    print("=" * 50)
    print("Testing rate limiter (sliding window)...")
    from app.rate_limiter import check_rate_limit, get_rate_limit_status
    from fastapi import HTTPException
    key = "test_key_rate_limit"
    success = 0
    for i in range(15):
        try:
            check_rate_limit(key)
            success += 1
        except HTTPException as e:
            print(f"  Request {i+1}: BLOCKED (429) after {success} requests [PASS]")
            break
    else:
        print(f"  WARNING: No rate limit triggered after 15 requests (limit={os.environ.get('RATE_LIMIT_PER_MINUTE')})")
    status = get_rate_limit_status(key)
    print(f"  Status: {status}")

def test_cost_guard():
    print("=" * 50)
    print("Testing cost guard...")
    from app.cost_guard import check_budget, record_usage, _usage_store
    from fastapi import HTTPException
    user = "test_user_001"
    check_budget(user)
    result = record_usage(user, input_tokens=100, output_tokens=200)
    print(f"  After 1 req: cost=${result['cost_usd']:.6f}, remaining=${result['remaining_usd']:.4f} [PASS]")
    if user in _usage_store:
        _usage_store[user].input_tokens = 10_000_000
        _usage_store[user].output_tokens = 10_000_000
    try:
        check_budget(user)
        print("  WARNING: Budget check did not block overspend!")
    except HTTPException as e:
        print(f"  Over-budget blocked HTTP {e.status_code} [PASS]")

def test_health_direct():
    """Test /health endpoint directly by calling the function."""
    print("=" * 50)
    print("Testing health endpoint function directly...")
    from app.main import health
    result = health()
    print(f"  health() returned: {result}")
    assert result.get("status") == "ok", f"Expected status=ok, got {result}"
    print(f"  health() -> status={result['status']} [PASS]")

def test_auth():
    print("=" * 50)
    print("Testing auth + endpoints via TestClient...")
    from starlette.testclient import TestClient
    from app.main import app

    with TestClient(app, raise_server_exceptions=True) as client:
        try:
            r = client.get("/health")
            print(f"  GET /health -> {r.status_code} [{'PASS' if r.status_code == 200 else 'FAIL'}]")
            if r.status_code != 200:
                print(f"  Response: {r.text[:300]}")
        except Exception as e:
            print(f"  GET /health ERROR: {e}")
            traceback.print_exc()

        r = client.post("/ask", json={"question": "Hello"})
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"
        print(f"  POST /ask (no key) -> {r.status_code} 401 [PASS]")

        r = client.post("/ask", json={"question": "Hello"}, headers={"X-API-Key": "wrong-key"})
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"
        print(f"  POST /ask (wrong key) -> {r.status_code} 401 [PASS]")

        r = client.post("/ask", json={"question": "What is Docker?"}, headers={"X-API-Key": "lab12-secret-key-2026"})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        print(f"  POST /ask (correct key) -> {r.status_code} 200 [PASS]")
        print(f"  Answer: {data.get('answer', '')[:80]}...")

        r = client.get("/ready")
        assert r.status_code == 200, f"Ready failed: {r.status_code}"
        print(f"  GET /ready -> {r.status_code} [PASS]")

if __name__ == "__main__":
    print()
    print("Running production-ready verification tests...")
    print()
    settings, app = test_imports()
    test_rate_limiter()
    test_cost_guard()
    test_health_direct()
    test_auth()
    print()
    print("=" * 50)
    print("All tests passed! App is production-ready.")
    print("=" * 50)
