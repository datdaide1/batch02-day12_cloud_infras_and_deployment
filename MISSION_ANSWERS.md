# Day 12 Lab — Mission Answers

> **Student Name:** Trần Hoàng Đạt
> **Student ID:** 2A202600807
> **Date:** 12/06/2026

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns trong `01-localhost-vs-production/develop/app.py`

Tìm được **6 vấn đề** (nhiều hơn yêu cầu 5):

| # | Vị trí | Anti-pattern | Nguy cơ |
|---|--------|-------------|---------|
| 1 | Line 17 | `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` | Key lộ khi push GitHub |
| 2 | Line 18 | `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"` | Credentials DB lộ |
| 3 | Line 21 | `DEBUG = True` hardcode | Debug mode chạy trong production → lộ stack trace |
| 4 | Line 33–34 | `print(f"Using key: {OPENAI_API_KEY}")` | Log ra secret key |
| 5 | Lines 44–45 | Không có `/health` endpoint | Platform không biết khi nào restart container |
| 6 | Lines 51–53 | `host="localhost"`, `port=8000`, `reload=True` hardcode | Không chạy được trong container; reload=True tốn tài nguyên |

### Exercise 1.2: Quan sát khi chạy basic version

```bash
cd 01-localhost-vs-production/develop
pip install -r requirements.txt
python app.py
curl -X POST "http://localhost:8000/ask?question=hello"
```

**Nhận xét:** App chạy được nhưng **không production-ready** vì:
- Nếu crash → platform không biết để restart (thiếu `/health`)
- Secrets trong code → push GitHub là lộ ngay
- `host=localhost` → không nhận request từ bên ngoài container

### Exercise 1.3: So sánh develop vs production

| Feature | Develop (`develop/app.py`) | Production (`production/app.py`) | Tại sao quan trọng? |
|---------|---------------------------|----------------------------------|---------------------|
| **Config** | Hardcode (`DEBUG=True`, port 8000) | Đọc từ env vars qua `config.py` | Linh hoạt, không lộ secrets khi push code |
| **Secrets** | Hardcode trong code | Đọc từ `.env` / environment | Bảo mật — không commit secrets lên Git |
| **Health check** | ❌ Không có | ✅ `GET /health` + `GET /ready` | Platform biết khi nào restart, load balancer biết khi nào route traffic |
| **Logging** | `print()` thô | JSON structured logging | Dễ parse, search, alert trong log aggregator (Datadog, Loki...) |
| **Graceful shutdown** | ❌ Kill ngay lập tức | ✅ SIGTERM handler + lifespan | Request đang xử lý không bị mất khi deploy mới |
| **Host binding** | `localhost` (chỉ local) | `0.0.0.0` (nhận từ mọi interface) | Bắt buộc để nhận request bên ngoài container |
| **Port** | Hardcode `8000` | `int(os.getenv("PORT", 8000))` | Railway/Render inject `PORT` env var tự động |
| **CORS** | ❌ Không có | ✅ Cấu hình qua `ALLOWED_ORIGINS` | Kiểm soát ai được gọi API từ browser |

---

## Part 2: Docker

### Exercise 2.1: Phân tích `02-docker/develop/Dockerfile`

1. **Base image là gì?**
   `python:3.11` — full Python distribution (~1 GB), bao gồm pip, build tools, development headers.

2. **Working directory là gì?**
   `/app` — tất cả lệnh `COPY`, `RUN` đều chạy trong thư mục này.

3. **Tại sao COPY `requirements.txt` TRƯỚC khi COPY toàn bộ code?**
   **Docker layer caching.** Mỗi instruction tạo một layer. Nếu `requirements.txt` không thay đổi, Docker reuse layer `pip install` từ cache → build nhanh hơn nhiều. Nếu COPY code trước, mỗi lần thay đổi code 1 dòng → phải chạy lại `pip install` từ đầu.

4. **CMD vs ENTRYPOINT khác nhau thế nào?**

   | | `CMD` | `ENTRYPOINT` |
   |---|---|---|
   | Mục đích | Command mặc định, **có thể override** khi `docker run` | Process chính, **khó override** |
   | Override | `docker run image <new-command>` | Cần `--entrypoint` flag |
   | Use case | Flexible default | Fixed executable (binary, script) |
   | Ví dụ | `CMD ["python", "app.py"]` → có thể `docker run image bash` | `ENTRYPOINT ["python"]` + `CMD ["app.py"]` |

   Trong Dockerfile develop: `CMD ["python", "app.py"]` — cho phép override dễ dàng khi debug.

### Exercise 2.2: Quan sát image size

```bash
# Build
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker images my-agent:develop
```

| Image | Size ước tính |
|-------|--------------|
| `my-agent:develop` | ~1.0–1.1 GB |

**Nguyên nhân lớn:** Base image `python:3.11` đã ~1 GB + toàn bộ build tools.

### Exercise 2.3: Multi-stage build — phân tích `02-docker/production/Dockerfile`

**Stage 1 (`builder`):**
- Base: `python:3.11-slim` (nhỏ hơn `python:3.11`)
- Cài `gcc`, `libpq-dev` để compile các packages cần C extensions
- `pip install --user` → packages vào `/root/.local`
- Mục đích: **build environment** — cần tools nhưng không cần deploy

**Stage 2 (`runtime`):**
- Base: `python:3.11-slim` (fresh, không có gcc/build tools)
- `COPY --from=builder /root/.local ...` — chỉ lấy packages đã compile
- Tạo **non-root user** (`appuser`) — security best practice
- Không có gcc, libpq-dev → image nhỏ và ít attack surface hơn

**Tại sao image nhỏ hơn:**
- Không có build tools (`gcc`, `libpq-dev`)
- Dùng `python:3.11-slim` thay vì full `python:3.11`
- Không có pip cache, không có `.pyc` từ quá trình compile

| Image | Size ước tính |
|-------|--------------|
| `my-agent:develop` | ~1.0 GB |
| `my-agent:advanced` | ~200–350 MB |
| **Chênh lệch** | ~65–80% nhỏ hơn |

### Exercise 2.4: Docker Compose architecture

```
docker compose up
```

**Services được start:**

| Service | Image | Port | Vai trò |
|---------|-------|------|---------|
| `agent` | build từ Dockerfile | Internal | FastAPI AI agent |
| `redis` | `redis:7-alpine` | Internal | Cache session, rate limiting |
| `qdrant` | `qdrant/qdrant:v1.9.0` | Internal | Vector database cho RAG |
| `nginx` | `nginx:alpine` | 80, 443 | Reverse proxy, load balancer |

**Architecture diagram:**

```
Internet
    │
    ▼
┌────────────┐  port 80/443
│   Nginx    │─────────────────────────────────────┐
│ (LB/Proxy) │                                     │
└─────┬──────┘                                     │
      │ internal network                           │
      ├──────────────┐                             │
      ▼              ▼                             │
  ┌───────┐      ┌───────┐                         │
  │Agent 1│      │Agent 2│  (scale với --scale)    │
  └───┬───┘      └───┬───┘                         │
      │              │                             │
      └──────┬───────┘                             │
             ▼                                     │
         ┌───────┐                                 │
         │ Redis │ ← Session, Rate limit           │
         └───────┘                                 │
         ┌────────┐                                │
         │ Qdrant │ ← Vector store                 │
         └────────┘                                │
```

**Services communicate qua internal Docker network** (bridge) — không expose trực tiếp ra ngoài, chỉ qua Nginx.

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway Deployment

**Steps thực hiện:**

```bash
npm i -g @railway/cli
railway login
cd 03-cloud-deployment/railway
railway init
railway variables set PORT=8000
railway variables set AGENT_API_KEY=my-secret-key-lab12
railway up
railway domain
```

- **Platform:** Railway
- **URL:** _(điền sau khi deploy)_
- **Screenshot:** [Xem `screenshots/railway-dashboard.png`]

### Exercise 3.2: So sánh `render.yaml` vs `railway.toml`

| Aspect | `railway.toml` | `render.yaml` |
|--------|---------------|---------------|
| **Format** | TOML | YAML |
| **Health check path** | `[deploy] healthcheckPath` | `healthCheckPath` trong service |
| **Env vars** | `railway variables set` qua CLI | Định nghĩa trong `envVars` block |
| **Auto-deploy** | Tự động khi push | `autoDeploy: true` |
| **Build command** | Tự detect (Dockerfile) | `buildCommand` explicit |

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication — phân tích

**API key được check ở đâu?**
Trong dependency `verify_api_key()` ở `04-api-gateway/develop/app.py:39`:
```python
def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key:
        raise HTTPException(401, "Missing API key")
    if api_key != API_KEY:
        raise HTTPException(403, "Invalid API key")
    return api_key
```
FastAPI inject dependency này vào mọi endpoint có `_key: str = Depends(verify_api_key)`.

**Điều gì xảy ra nếu sai key?**
- Thiếu key → HTTP 401 Unauthorized
- Sai key → HTTP 403 Forbidden

**Làm sao rotate key?**
Thay giá trị `AGENT_API_KEY` trong environment variable → restart app. Không cần sửa code.

**Test results:**

```bash
# Không có key → 401
curl http://localhost:8000/ask -X POST -H "Content-Type: application/json" -d '{"question": "Hello"}'
# → {"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

# Có key → 200
curl http://localhost:8000/ask -X POST -H "X-API-Key: demo-key-change-in-production" -H "Content-Type: application/json" -d '{"question": "Hello"}'
# → {"question":"Hello","answer":"..."}
```

### Exercise 4.2: JWT Authentication — phân tích `04-api-gateway/production/auth.py`

**JWT Flow:**

```
Client                    Server
  │                         │
  ├── POST /token ────────► │
  │   {username, password}  │
  │                         ├─ verify credentials
  │                         ├─ tạo JWT (sign với SECRET_KEY)
  │ ◄──── {access_token} ───┤
  │                         │
  ├── POST /ask ──────────► │
  │   Authorization: Bearer │
  │   <token>               ├─ decode JWT (verify signature)
  │                         ├─ extract user_id
  │ ◄──── {answer} ─────────┤
```

**Test:**

```bash
python app.py

# Lấy token
TOKEN=$(curl -s http://localhost:8000/token -X POST \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Dùng token
curl http://localhost:8000/ask -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain JWT"}'
```

### Exercise 4.3: Rate Limiting — phân tích `04-api-gateway/production/rate_limiter.py`

**Algorithm:** Sliding Window
- Dùng `deque` lưu timestamps của requests trong 60 giây gần nhất
- Mỗi request: xóa timestamps cũ > 60s, kiểm tra count

**Limit:** 10 requests/minute per user (từ `RATE_LIMIT_PER_MINUTE` env var)

**Bypass cho admin:** Kiểm tra `role == "admin"` trong JWT payload → skip rate limit check

**Test kết quả:**

```bash
# Sau ~10 requests liên tục
# → HTTP 429 Too Many Requests
# → Headers: Retry-After: 60
```

### Exercise 4.4: Cost Guard Implementation

**Approach:** In-memory tracking với daily reset.

```python
# Giải pháp trong 04-api-gateway/production/cost_guard.py

class CostGuard:
    def check_budget(self, user_id: str) -> None:
        record = self._get_record(user_id)
        if record.total_cost_usd >= self.daily_budget_usd:
            raise HTTPException(402, {"error": "Daily budget exceeded", ...})

    def record_usage(self, user_id, input_tokens, output_tokens):
        cost = input_tokens/1000 * 0.00015 + output_tokens/1000 * 0.0006
        self._global_cost += cost
        ...
```

**Logic:**
- Mỗi user có budget $1/ngày (global $10/ngày)
- Tính cost: `input_tokens * $0.00015/1K + output_tokens * $0.0006/1K`
- Reset tự động khi sang ngày mới (check `day != today`)
- Cảnh báo log khi > 80% budget

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health Checks — Implementation

```python
@app.get("/health")
def health():
    """Liveness probe — container còn sống không?"""
    uptime = round(time.time() - START_TIME, 1)
    return {
        "status": "ok",
        "uptime_seconds": uptime,
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/ready")
def ready():
    """Readiness probe — sẵn sàng nhận traffic chưa?"""
    if not _is_ready:
        raise HTTPException(503, "Agent not ready yet")
    return {"ready": True, "in_flight_requests": _in_flight_requests}
```

**Test:**
```bash
curl http://localhost:8000/health  # → {"status":"ok","uptime_seconds":5.2,...}
curl http://localhost:8000/ready   # → {"ready":true,"in_flight_requests":0}
```

**Sự khác nhau giữa /health và /ready:**
- `/health` (liveness): "Container có còn process không?" → Platform restart nếu fail
- `/ready` (readiness): "App đã load xong, sẵn sàng nhận request?" → LB không route nếu fail

### Exercise 5.2: Graceful Shutdown Implementation

```python
import signal

def handle_sigterm(signum, frame):
    """Handle SIGTERM từ platform/orchestrator."""
    logger.info(f"Received signal {signum} — uvicorn will handle graceful shutdown")
    # uvicorn + lifespan context manager tự handle:
    # 1. Stop accepting new requests
    # 2. Chờ in-flight requests hoàn thành (timeout_graceful_shutdown=30)
    # 3. Gọi lifespan shutdown code
    # 4. Exit

signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

# uvicorn run với timeout
uvicorn.run(app, timeout_graceful_shutdown=30)
```

**Test:**
```bash
python app.py &
PID=$!
# Gửi request dài
curl http://localhost:8000/ask?question="Long task" &
# Kill ngay
kill -TERM $PID
# Quan sát: request hoàn thành trước khi app exit
```

### Exercise 5.3: Stateless Design

**Anti-pattern (in-memory state):**
```python
conversation_history = {}  # ❌ mất khi restart/scale

@app.post("/ask")
def ask(user_id: str, question: str):
    history = conversation_history.get(user_id, [])
    # ...
    conversation_history[user_id] = history  # ❌ chỉ lưu trong 1 instance
```

**Correct (Redis state):**
```python
@app.post("/ask")
def ask(user_id: str, question: str):
    history = r.lrange(f"history:{user_id}", 0, -1)  # ✅ shared across instances
    # ...
    r.rpush(f"history:{user_id}", response)
    r.expire(f"history:{user_id}", 3600)  # TTL 1 giờ
```

**Tại sao cần stateless:**
Khi scale ra 3 instances, mỗi instance có RAM riêng. Request 1 vào Instance A, request 2 vào Instance B → Instance B không có history của A. Redis là shared store, mọi instance đều đọc/ghi cùng 1 nơi.

### Exercise 5.4: Load Balancing

```bash
docker compose up --scale agent=3
```

**Nginx phân tán requests theo round-robin:**
- Request 1 → Agent container 1
- Request 2 → Agent container 2
- Request 3 → Agent container 3
- Request 4 → Agent container 1 (lặp lại)

**Test:**
```bash
for i in $(seq 1 10); do
  curl http://localhost/ask -X POST -H "Content-Type: application/json" \
    -d "{\"question\": \"Request $i\"}"
done
docker compose logs agent
# Thấy requests được phân tán đều giữa 3 containers
```

**Fault tolerance:** Nếu 1 instance die, Nginx tự loại khỏi pool và route traffic sang 2 instances còn lại.

### Exercise 5.5: Stateless Test

```bash
python test_stateless.py
```

Script verify:
1. Tạo conversation với Instance A
2. Kill Instance A
3. Tiếp tục conversation → Instance B vẫn có history → ✅ Stateless hoạt động
