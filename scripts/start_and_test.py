"""
Script khởi động và test RAG Bot.
Chạy: python scripts/start_and_test.py
"""

import subprocess
import sys
import time
import httpx


def run(cmd: str, check=True) -> subprocess.CompletedProcess:
    print(f"\n▶ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=False, text=True)
    if check and result.returncode != 0:
        print(f"❌ Lỗi! Exit code: {result.returncode}")
        sys.exit(1)
    return result


def wait_for_api(url: str, max_wait: int = 60) -> bool:
    print(f"\n⏳ Chờ API khởi động tại {url}...")
    for i in range(max_wait):
        try:
            r = httpx.get(url, timeout=2)
            if r.status_code == 200:
                print(f"✅ API sẵn sàng sau {i+1}s")
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main():
    print("=" * 60)
    print("  RAG Q&A Bot — Startup & Test Script")
    print("=" * 60)

    # 1. Kiểm tra .env
    import os
    if not os.path.exists(".env"):
        print("❌ Chưa có file .env! Chạy: Copy-Item .env.example .env")
        sys.exit(1)

    from dotenv import dotenv_values
    env = dotenv_values(".env")
    if env.get("OPENAI_API_KEY", "").startswith("sk-...") or not env.get("OPENAI_API_KEY"):
        print("❌ Chưa điền OPENAI_API_KEY trong .env!")
        sys.exit(1)
    if env.get("ANTHROPIC_API_KEY", "").startswith("sk-ant-...") or not env.get("ANTHROPIC_API_KEY"):
        print("❌ Chưa điền ANTHROPIC_API_KEY trong .env!")
        sys.exit(1)
    print("✅ .env OK")

    # 2. Khởi động Docker stack
    print("\n📦 Khởi động Docker Compose...")
    run("docker compose up -d --build")

    # 3. Chờ services healthy
    time.sleep(10)

    # 4. Chạy migrations
    print("\n🗄️  Chạy Alembic migrations...")
    run("docker compose exec api alembic upgrade head")

    # 5. Kiểm tra API health
    if not wait_for_api("http://localhost:8000/health"):
        print("❌ API không khởi động được. Xem logs: docker compose logs api")
        sys.exit(1)

    # 6. Test health endpoint
    r = httpx.get("http://localhost:8000/health")
    print(f"\n🏥 Health check: {r.json()}")

    print("\n" + "=" * 60)
    print("✅ Hệ thống đã sẵn sàng!")
    print("=" * 60)
    print("""
📌 Các URL quan trọng:
   • API Swagger:  http://localhost:8000/docs
   • ReDoc:        http://localhost:8000/redoc
   • Flower:       http://localhost:5555
   • Qdrant UI:    http://localhost:6333/dashboard

📌 Lệnh test nhanh (copy vào terminal):

1) Upload tài liệu PDF:
   curl -X POST http://localhost:8000/api/v1/documents/upload -F "file=@path/to/your.pdf"

2) Kiểm tra trạng thái:
   curl http://localhost:8000/api/v1/documents/{document_id}/status

3) Đặt câu hỏi:
   curl -X POST http://localhost:8000/api/v1/ask \\
     -H "Content-Type: application/json" \\
     -d '{"question": "Mức phạt vi phạm tốc độ là bao nhiêu?"}'

📌 Xem logs:
   docker compose logs -f api
   docker compose logs -f worker

📌 Dừng hệ thống:
   docker compose down
""")


if __name__ == "__main__":
    main()
