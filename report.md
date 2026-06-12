# Final Report - Day 12: Cloud Infrastructure & Deployment

**Student Name:** Trần Hoàng Đạt  
**Student ID:** 2A202600807  
**Date:** 12/06/2026  

---

## 1. Mục tiêu (Objective)
Mục tiêu của bài thực hành Day 12 là thiết kế một **Production-ready API** đạt tiêu chuẩn công nghiệp. Điểm đặc biệt của báo cáo này là hệ thống không dùng Mock LLM cơ bản mà **đã tích hợp thành công toàn bộ RAG Pipeline từ Lab 08** vào làm AI Engine cốt lõi. Hệ thống được bảo vệ bởi các lớp bảo mật (Defense in Depth), đóng gói qua Docker tối ưu, và triển khai thành công lên Cloud (Render).

## 2. Quá trình Triển khai (Implementation Process)

### 2.1. Tích hợp AI Core (RAG Pipeline)
- Di chuyển toàn bộ mã nguồn của Lab 08 (Crawl, Chunking, Weaviate VectorDB, BM25, Generation) vào một internal package `rag_core/`.
- Sửa endpoint `POST /ask` để gọi trực tiếp hàm `generate_with_citation`. Nếu không có API Key của Google/OpenAI, hệ thống sẽ tự động Graceful Fallback trả về câu trả lời Mock kèm theo số lượng tài liệu Context tìm được, đảm bảo server không bao giờ crash.

### 2.2. Refactoring Kiến trúc (Modularization)
Mã nguồn ban đầu được chia nhỏ thành các module độc lập theo nguyên tắc Separation of Concerns:
- **`auth.py`**: Triển khai cơ chế xác thực bằng `X-API-Key` thông qua FastAPI Dependencies. Chặn đứng các truy cập trái phép bằng lỗi `401 Unauthorized`.
- **`rate_limiter.py`**: Xây dựng thuật toán **Sliding Window** in-memory giới hạn 10 requests/phút. Trả về `429 Too Many Requests` nếu client vượt giới hạn, bảo vệ server khỏi các cuộc tấn công DDoS/Spam.
- **`cost_guard.py`**: Xây dựng hệ thống quản lý ngân sách hàng ngày ($5.0/ngày/user). Tự động theo dõi chi phí sử dụng LLM Token và kích hoạt Circuit Breaker (`402 Payment Required`) nếu vượt hạn mức.

### 2.3. Đảm bảo độ ổn định (Reliability)
- Tích hợp endpoint `/health` (liveness) và `/ready` (readiness) để Kubernetes/Docker/Load Balancer có thể theo dõi trạng thái sống còn của application.
- Cập nhật và fix lỗi tương thích liên quan đến thay đổi của thư viện Starlette (`MutableHeaders.pop()`) trong middleware.

### 2.4. Kiểm thử Tự động (Testing)
- Viết script `test_app.py` để verify tự động 100% các cases: Auth failure, Auth success, Rate Limiting triggers (vượt 10 requests), và Cost Guard limits. Tất cả các test đều **PASS** trên môi trường local trước khi deploy.

### 2.5. Đóng gói & Tối ưu hóa (Dockerization)
- Sử dụng chiến lược **Multi-stage Build** với image gốc `python:3.11-slim`.
- Cài đặt dependency vào Virtual Environment (`venv`) ở stage Builder, sau đó copy nguyên vẹn sang stage Runtime để giảm thiểu kích thước file ảnh (< 500MB).
- Thực thi container bằng quyền **Non-root user (`agent`)** để tăng tối đa tính bảo mật.

### 2.6. Triển khai Đám mây (Cloud Deployment)
- Triển khai thành công ứng dụng qua nền tảng **Render** theo kiến trúc Docker.
- Biến môi trường (`ENVIRONMENT`, `AGENT_API_KEY`, `RATE_LIMIT`, `BUDGET`) được cấu hình an toàn, độc lập hoàn toàn khỏi mã nguồn.

---

## 3. Kết quả (Results & Deliverables)

Dự án hiện tại đang chạy Live trên nền tảng đám mây và sẵn sàng để tích hợp vào các frontend application khác.

- **Live Public URL**: [https://batch02-day12-cloud-infras-and-deployment.onrender.com](https://batch02-day12-cloud-infras-and-deployment.onrender.com)
- **Interactive API Docs (Swagger UI)**: [https://batch02-day12-cloud-infras-and-deployment.onrender.com/docs](https://batch02-day12-cloud-infras-and-deployment.onrender.com/docs)
- **Liveness Health Check**: [https://batch02-day12-cloud-infras-and-deployment.onrender.com/health](https://batch02-day12-cloud-infras-and-deployment.onrender.com/health)

### Danh sách các file Nộp bài chính:
1. `06-lab-complete/app/*`: Toàn bộ logic API.
2. `06-lab-complete/Dockerfile`: File cấu hình Container.
3. `MISSION_ANSWERS.md`: Trả lời lý thuyết chi tiết Lab 12.
4. `DEPLOYMENT.md`: Cấu hình deploy và hướng dẫn test API bằng cURL.
5. Thư mục `screenshots/`: Ghi nhận hình ảnh chứng minh hệ thống hoạt động thực tế.

---
*Hoàn thành Lab 12 với 100% tiêu chí đạt chuẩn.*
