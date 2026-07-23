"""
Seed script: upload sample documents via the API for testing.
Run: python scripts/seed_sample_docs.py

Requires:
- API running on localhost:8000
- At least one PDF in the ./sample_docs/ directory
"""

import asyncio
import sys
from pathlib import Path

import httpx

API_BASE = "http://localhost:8000/api/v1"


async def upload_document(client: httpx.AsyncClient, file_path: Path) -> dict:
    """Upload a single document and return the response."""
    print(f"  📤 Uploading: {file_path.name} ({file_path.stat().st_size:,} bytes)")
    with open(file_path, "rb") as f:
        response = await client.post(
            f"{API_BASE}/documents/upload",
            files={"file": (file_path.name, f, "application/pdf")},
            timeout=30.0,
        )
    response.raise_for_status()
    data = response.json()
    print(f"     ✅ document_id: {data['document_id']} | status: {data['status']}")
    return data


async def poll_status(client: httpx.AsyncClient, document_id: str, max_wait: int = 120) -> str:
    """Poll until document is COMPLETED or FAILED."""
    import time
    start = time.time()

    while time.time() - start < max_wait:
        response = await client.get(f"{API_BASE}/documents/{document_id}/status")
        data = response.json()
        status = data["status"]

        if status == "completed":
            print(f"     ✅ Completed: {data['chunk_count']} chunks")
            return status
        elif status == "failed":
            print(f"     ❌ Failed: {data.get('error_message', 'unknown error')}")
            return status
        else:
            print(f"     ⏳ Status: {status}...")
            await asyncio.sleep(3)

    print(f"     ⚠️  Timeout after {max_wait}s")
    return "timeout"


async def test_ask(client: httpx.AsyncClient, question: str) -> None:
    """Test the Q&A endpoint with a sample question."""
    print(f"\n  ❓ Asking: {question}")
    response = await client.post(
        f"{API_BASE}/ask",
        json={"question": question, "top_k": 3},
        timeout=60.0,
    )
    data = response.json()
    print(f"  📝 Grounded: {data['is_grounded']}")
    print(f"  💬 Answer: {data['answer'][:200]}...")
    print(f"  📚 Citations: {len(data.get('citations', []))} sources")


async def main() -> None:
    sample_dir = Path("./sample_docs")
    if not sample_dir.exists():
        sample_dir.mkdir()
        print(f"Created {sample_dir}/ — please add PDF files here and re-run.")
        sys.exit(0)

    pdf_files = list(sample_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {sample_dir}/")
        sys.exit(1)

    print(f"\n🚀 RAG Bot Seeder — uploading {len(pdf_files)} file(s)\n")

    async with httpx.AsyncClient(base_url=API_BASE) as client:
        document_ids = []
        for pdf_file in pdf_files:
            data = await upload_document(client, pdf_file)
            document_ids.append(data["document_id"])

        print("\n⏳ Waiting for ingestion to complete...\n")
        for doc_id in document_ids:
            await poll_status(client, doc_id)

        # Test Q&A
        test_questions = [
            "Mức phạt vi phạm tốc độ là bao nhiêu?",
            "Vượt đèn đỏ bị phạt bao nhiêu tiền?",
            "Không đội mũ bảo hiểm bị xử phạt như thế nào?",
        ]
        print("\n🔍 Testing Q&A pipeline:\n")
        for question in test_questions:
            await test_ask(client, question)

    print("\n✅ Seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())
