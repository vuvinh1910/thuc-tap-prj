# RAG Q&A Bot - Chatbot hỏi đáp tài liệu pháp lý

Project thực tập: xây dựng hệ thống cho phép upload tài liệu PDF (nghị định xử phạt vi phạm hành chính) và hỏi đáp dựa trên nội dung tài liệu đó, có trích dẫn nguồn.

## Mô tả

Người dùng upload file PDF lên, hệ thống sẽ tự động xử lý (cắt đoạn, tạo embedding, lưu vào vector database). Sau đó có thể đặt câu hỏi bằng tiếng Việt, hệ thống tìm các đoạn liên quan trong tài liệu rồi gọi LLM để trả lời kèm trích dẫn. Nếu không tìm thấy thông tin phù hợp thì từ chối trả lời thay vì bịa.

Kiến trúc theo hướng RAG (Retrieval-Augmented Generation).

## Tech stack

- API: FastAPI
- LLM: Anthropic Claude 3.5 Haiku (hoặc OpenAI GPT-4o-mini, Ollama)
- Embedding: OpenAI text-embedding-3-small
- Vector DB: Qdrant
- Database: PostgreSQL + SQLAlchemy (lưu metadata tài liệu)
- Task queue: Celery + Redis (xử lý upload bất đồng bộ)
- File parsing: pypdf, unstructured

## Cài đặt

**Yêu cầu:** Docker Desktop đã cài và đang chạy.

```bash
git clone https://github.com/vuvinh1910/thuc-tap-prj.git
cd thuc-tap-prj
cp .env.example .env
```

Mở file `.env`, điền API key vào:
```
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

Khởi động:
```bash
docker compose up -d
docker compose exec api alembic upgrade head
```

Kiểm tra tại:
- API docs: http://localhost:8000/docs
- Celery monitor: http://localhost:5555
- Qdrant: http://localhost:6333/dashboard

## Sử dụng

Upload tài liệu:
```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@nghi-dinh.pdf"
```

Trả về `document_id`, dùng để kiểm tra trạng thái xử lý:
```bash
curl http://localhost:8000/api/v1/documents/{document_id}/status
```

Khi status là `completed` thì có thể đặt câu hỏi:
```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Mức phạt vi phạm tốc độ là bao nhiêu?"}'
```

Response trả về câu trả lời, `is_grounded` (có dựa trên tài liệu không), và danh sách trích dẫn (file, trang, đoạn văn).

## Cấu trúc thư mục

```
src/
├── api/            # FastAPI routes, schemas, dependency injection
├── core/
│   ├── entities/   # Domain models (Document, Chunk, LLMResponse...)
│   ├── interfaces/ # Abstract interface cho LLM, vector store, storage...
│   └── services/   # Business logic (chunking, ingestion, query)
├── infrastructure/ # Implementation cụ thể (OpenAI, Qdrant, Postgres, pypdf)
└── workers/        # Celery task xử lý ingest bất đồng bộ
```

## Chạy local (không Docker)

```bash
pip install -e ".[dev]"
uvicorn src.api.main:app --reload

# Worker riêng
celery -A src.workers.celery_app worker --loglevel=info -Q ingest

# Test
pytest --cov=src
```
