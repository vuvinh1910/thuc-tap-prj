# RAG Q&A Bot — Chatbot hỏi đáp tài liệu pháp lý

Hệ thống cho phép upload tài liệu PDF (nghị định, thông tư, văn bản pháp luật) và đặt câu hỏi bằng tiếng Việt. Hệ thống tìm kiếm các đoạn liên quan trong tài liệu, gọi LLM để trả lời kèm trích dẫn nguồn cụ thể (tên file, số trang). Nếu không tìm thấy ngữ cảnh phù hợp, hệ thống **từ chối trả lời** thay vì bịa đặt.

---

## Kiến trúc tổng quan

```
Người dùng
    │
    ▼
FastAPI (API Layer)
    │
    ├── Upload PDF ──► Celery Worker ──► Parse ──► Chunk ──► Embed ──► Qdrant
    │
    └── Đặt câu hỏi ──► Embed câu hỏi ──► Tìm kiếm Qdrant ──► Gọi LLM ──► Trả lời + Citations
                                                                      │
                                                                      └── Lưu PostgreSQL (lịch sử)
```

## Tech stack

| Thành phần | Công nghệ |
|---|---|
| API Framework | FastAPI |
| LLM | Anthropic Claude 3.5 Haiku / OpenAI GPT-4o-mini / Ollama |
| Embedding | OpenAI `text-embedding-3-small` |
| Vector Database | Qdrant |
| Relational Database | PostgreSQL + SQLAlchemy async |
| Task Queue | Celery + Redis |
| File Parsing | pypdf, unstructured |
| Rate Limiting | slowapi |

---

## Yêu cầu trước khi cài đặt

1. **Docker Desktop** — tải tại https://www.docker.com/products/docker-desktop/
2. **API Keys** (cần ít nhất một trong hai):
   - **OpenAI API Key** (bắt buộc — dùng cho embedding): https://platform.openai.com/api-keys
   - **Anthropic API Key** (dùng cho LLM mặc định): https://console.anthropic.com/

---

## Cài đặt và chạy (Docker — khuyến nghị)

### Bước 1 — Clone repo

```bash
git clone https://github.com/vuvinh1910/thuc-tap-prj.git
cd thuc-tap-prj
```

### Bước 2 — Tạo file cấu hình

```bash
cp .env.example .env
```

Mở file `.env` và điền API key:

```env
# Bắt buộc
OPENAI_API_KEY=sk-...

# Chọn một trong hai:
ANTHROPIC_API_KEY=sk-ant-...   # dùng nếu LLM_PROVIDER=anthropic (mặc định)
# hoặc để trống nếu dùng LLM_PROVIDER=openai

# Cấu hình LLM (mặc định: anthropic)
LLM_PROVIDER=anthropic         # anthropic | openai | ollama
```

### Bước 3 — Khởi động toàn bộ hệ thống

```bash
docker compose up -d
```

Lệnh này khởi động: FastAPI, Celery Worker, PostgreSQL, Redis, Qdrant, Flower.

### Bước 4 — Chạy migration database

```bash
docker compose exec api alembic upgrade head
```

> Chạy một lần duy nhất khi khởi tạo hoặc sau khi có migration mới.

### Bước 5 — Kiểm tra

Mở trình duyệt, truy cập:

| URL | Mô tả |
|---|---|
| http://localhost:8000/docs | API documentation (Swagger UI) |
| http://localhost:8000/health | Trạng thái kết nối DB + Qdrant |
| http://localhost:5555 | Celery Flower — theo dõi task queue |
| http://localhost:6333/dashboard | Qdrant dashboard |

---

## Cách sử dụng

### 1. Upload tài liệu PDF

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@/path/to/nghi-dinh.pdf"
```

Response:
```json
{
  "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "filename": "nghi-dinh.pdf",
  "status": "pending"
}
```

Hệ thống trả về `202 Accepted` ngay lập tức. Việc xử lý (parse PDF, tạo embedding, lưu Qdrant) chạy nền qua Celery.

### 2. Kiểm tra trạng thái xử lý

```bash
curl http://localhost:8000/api/v1/documents/{document_id}/status
```

```json
{
  "document_id": "...",
  "filename": "nghi-dinh.pdf",
  "status": "completed",   // pending | processing | completed | failed
  "chunk_count": 147,
  "file_size_bytes": 2048000
}
```

Polling đến khi `status` là `completed` thì có thể đặt câu hỏi.

### 3. Đặt câu hỏi

```bash
curl -X POST http://localhost:8000/api/v1/query/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Mức phạt vi phạm tốc độ trên đường cao tốc là bao nhiêu?",
    "top_k": 5,
    "score_threshold": 0.35
  }'
```

Response:
```json
{
  "answer": "Theo Nghị định 100/2019/NĐ-CP, Điều 5...",
  "is_grounded": true,
  "citations": [
    {
      "filename": "nghi-dinh.pdf",
      "page_number": 12,
      "chunk_index": 34,
      "excerpt": "Phạt tiền từ 800.000 đồng đến 1.200.000 đồng..."
    }
  ],
  "model_used": "claude-3-5-haiku-20241022",
  "usage_tokens": 842
}
```

Nếu không tìm thấy thông tin: `"is_grounded": false`, hệ thống trả lời từ chối, không gọi LLM.

### 4. Xem lịch sử hỏi-đáp

```bash
curl "http://localhost:8000/api/v1/query/history?limit=10&offset=0"
```

---

## Tất cả API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/api/v1/documents/upload` | Upload PDF, trả về 202 + document_id ngay |
| `GET` | `/api/v1/documents/{id}/status` | Polling trạng thái xử lý |
| `GET` | `/api/v1/documents/` | Danh sách tài liệu đã upload |
| `DELETE` | `/api/v1/documents/{id}` | Xóa tài liệu (DB + Qdrant + file) |
| `POST` | `/api/v1/query/ask` | Đặt câu hỏi, nhận trả lời + citations (giới hạn 20 req/phút) |
| `GET` | `/api/v1/query/history` | Lịch sử hỏi-đáp, mới nhất trước |
| `GET` | `/health` | Trạng thái hệ thống (PostgreSQL + Qdrant) |

---

## Chạy local (không Docker)

> Yêu cầu: PostgreSQL, Redis, Qdrant đang chạy sẵn trên máy.

```bash
# Tạo virtualenv
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# Cài dependencies
pip install -r requirements.txt

# Chạy API
uvicorn src.api.main:app --reload --port 8000

# Chạy Celery worker (terminal riêng)
celery -A src.workers.celery_app worker --loglevel=info -Q ingest

# Chạy migration
alembic upgrade head
```

---

## Chạy Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (dùng SQLite in-memory, không cần PostgreSQL)
pytest tests/integration/ -v

# Tất cả tests + coverage report
pytest --cov=src --cov-report=term-missing
```

---

## Biến môi trường (.env)

| Biến | Mô tả | Mặc định |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key (bắt buộc cho embedding) | — |
| `ANTHROPIC_API_KEY` | Anthropic API key | — |
| `LLM_PROVIDER` | Provider LLM: `anthropic` / `openai` / `ollama` | `anthropic` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `QDRANT_URL` | Qdrant server URL | `http://localhost:6333` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `CHUNK_SIZE` | Kích thước mỗi chunk (số token) | `512` |
| `CHUNK_OVERLAP` | Overlap giữa các chunk | `50` |
| `RETRIEVAL_TOP_K` | Số chunk truy xuất mỗi query | `5` |
| `RETRIEVAL_SCORE_THRESHOLD` | Ngưỡng similarity tối thiểu (0–1) | `0.35` |
| `MAX_FILE_SIZE_MB` | Kích thước file tối đa | `50` |
| `ALLOWED_ORIGINS` | CORS origins (JSON array) | `["*"]` |
