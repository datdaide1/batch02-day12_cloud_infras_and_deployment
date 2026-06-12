# Deployment Information — Day 12 Lab

## Public URL

```
https://your-agent.railway.app
```

> ⚠️ **TODO:** Thay URL này sau khi deploy thành công lên Railway/Render

## Platform

- **Primary:** Railway
- **Alternative:** Render

## Environment Variables Set

| Variable                  | Value                        |
| ------------------------- | ---------------------------- |
| `PORT`                  | `8000`                     |
| `ENVIRONMENT`           | `production`               |
| `AGENT_API_KEY`         | _(secret, không publish)_ |
| `DAILY_BUDGET_USD`      | `5.0`                      |
| `RATE_LIMIT_PER_MINUTE` | `10`                       |

## Test Commands

### 1. Health Check (liveness)

```bash
curl https://your-agent.railway.app/health
# Expected:
# {"status":"ok","version":"1.0.0","environment":"production","uptime_seconds":42.1,...}
```

### 2. Readiness Check

```bash
curl https://your-agent.railway.app/ready
# Expected:
# {"ready":true}
```

### 3. Authentication Required (no key)

```bash
curl -X POST https://your-agent.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Expected: HTTP 401
# {"detail":"Invalid or missing API key. Include header: X-API-Key: <key>"}
```

### 4. API Test (with authentication)

```bash
curl -X POST https://your-agent.railway.app/ask \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Docker?"}'
# Expected: HTTP 200
# {"question":"What is Docker?","answer":"...","model":"gpt-4o-mini","timestamp":"..."}
```

### 5. Rate Limiting Test

```bash
# Gọi 15 lần liên tục — sẽ nhận 429 sau ~10 requests
for i in $(seq 1 15); do
  echo "Request $i:"
  curl -s -o /dev/null -w "%{http_code}" -X POST https://your-agent.railway.app/ask \
    -H "X-API-Key: YOUR_API_KEY_HERE" \
    -H "Content-Type: application/json" \
    -d '{"question": "test"}'
  echo ""
done
# Expected: 200 200 200... 429 429
```

### 6. Metrics (protected)

```bash
curl https://your-agent.railway.app/metrics \
  -H "X-API-Key: YOUR_API_KEY_HERE"
# Expected:
# {"uptime_seconds":..., "total_requests":..., "daily_cost_usd":..., ...}
```

## Screenshots

| File                                                              | Mô tả                                                       |
| ----------------------------------------------------------------- | ------------------------------------------------------------- |
| [`screenshots/01-root.png`](screenshots/01-root.png)               | Root endpoint — app info + endpoints list                    |
| [`screenshots/02-health.png`](screenshots/02-health.png)           | `/health` → `{"status":"ok","uptime_seconds":143.7,...}` |
| [`screenshots/03-ready.png`](screenshots/03-ready.png)             | `/ready` → `{"ready":true}`                              |
| [`screenshots/04-swagger.png`](screenshots/04-swagger.png)         | Swagger UI — tất cả endpoints                              |
| [`screenshots/05-ask-no-auth.png`](screenshots/05-ask-no-auth.png) | POST `/ask` không có key                                  |
| [`screenshots/06-ask-401.png`](screenshots/06-ask-401.png)         | Swagger Try it out → 401 Unauthorized (auth required)        |

## Deploy Steps (Railway)

```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Login
railway login

# 3. Init project (chạy trong thư mục 06-lab-complete/)
cd 06-lab-complete
railway init

# 4. Set environment variables
railway variables set PORT=8000
railway variables set ENVIRONMENT=production
railway variables set AGENT_API_KEY=<your-secret-key>
railway variables set DAILY_BUDGET_USD=5.0
railway variables set RATE_LIMIT_PER_MINUTE=10

# 5. Deploy
railway up

# 6. Get public URL
railway domain
```
