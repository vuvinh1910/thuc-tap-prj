# RAG Q&A Bot — Nghị định Xử phạt

Hệ thống hỏi đáp thông minh dựa trên RAG (Retrieval-Augmented Generation) cho tài liệu pháp lý.

## Tính năng

- 📄 Upload PDF / text → tự động chunk → embed → lưu vector store
- 🔍 Hỏi đáp dựa trên nội dung tài liệu với trích dẫn nguồn
- 🚫 Từ chối trả lời khi không có dữ liệu (chống hallucination)
- ⚡ Xử lý bất đồng bộ với Celery cho file lớn
- 🔌 Dễ đổi LLM/Vector DB nhờ kiến trúc interface-based

## Tech Stack

| Component | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| LLM | Anthropic Claude 3.5 Haiku |
| Embedding | OpenAI text-embedding-3-small |
| Vector DB | Qdrant |
| Database | PostgreSQL + SQLAlchemy |
| Queue | Celery + Redis |
| File Parsing | pypdf + unstructured |

## Cài đặt nhanh

### 1. Clone & cấu hình

```bash
git clone <repo>
cd rag-qna-bot
cp .env.example .env
# Điền OPENAI_API_KEY và ANTHROPIC_API_KEY vào .env
```

### 2. Khởi động với Docker

```bash
docker-compose up -d
```

### 3. Chạy migrations

```bash
docker-compose exec api alembic upgrade head
```

### 4. Kiểm tra

- API Docs: http://localhost:8000/docs
- Flower (queue monitor): http://localhost:5555
- Qdrant Dashboard: http://localhost:6333/dashboard

## API Usage

### Upload tài liệu

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@nghi-dinh-xp.pdf"
```

Response:
```json
{
  "document_id": "uuid",
  "status": "pending",
  "message": "File đang được xử lý"
}
```

### Kiểm tra trạng thái

```bash
curl http://localhost:8000/api/v1/documents/{document_id}/status
```

### Đặt câu hỏi

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Mức phạt vi phạm tốc độ là bao nhiêu?"}'
```

Response:
```json
{
  "answer": "Theo Nghị định..., mức phạt vi phạm tốc độ là...",
  "is_grounded": true,
  "citations": [
    {
      "filename": "nghi-dinh-xp.pdf",
      "page_number": 12,
      "excerpt": "..."
    }
  ]
}
```

## Development

```bash
# Chạy local (không Docker)
pip install -e ".[dev]"
uvicorn src.api.main:app --reload

# Chạy Celery worker
celery -A src.workers.celery_app worker --loglevel=info -Q ingest

# Chạy tests
pytest --cov=src

# Lint
ruff check src/
```

## Cấu trúc dự án

```
src/
├── api/           # FastAPI routers, schemas, dependencies
├── core/
│   ├── entities/  # Pure domain models
│   ├── interfaces/ # Abstract contracts (ILLMProvider, IVectorStore...)
│   └── services/  # Business logic
├── infrastructure/ # Concrete implementations (OpenAI, Qdrant, Postgres...)
└── workers/       # Celery async tasks
```
