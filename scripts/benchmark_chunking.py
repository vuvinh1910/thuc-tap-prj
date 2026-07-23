"""
Benchmark script: compare chunking strategies and measure overlap/size effects.
Run: python scripts/benchmark_chunking.py --file path/to/document.pdf

Outputs a table showing:
- Strategy name
- Chunk count
- Avg token count
- Min / Max token count
- Avg overlap ratio
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def benchmark_strategy(text: str, strategy_name: str, chunk_size: int, overlap: int) -> dict:
    from src.core.services.chunking_service import (
        ChunkingConfig,
        ChunkingService,
        ChunkingStrategy,
    )

    doc_id = uuid.uuid4()
    config = ChunkingConfig(
        strategy=ChunkingStrategy(strategy_name),
        chunk_size=chunk_size,
        overlap=overlap,
    )
    service = ChunkingService(config)
    chunks = service.split(text, doc_id)

    if not chunks:
        return {"strategy": strategy_name, "chunk_size": chunk_size, "overlap": overlap,
                "count": 0, "avg_tokens": 0, "min_tokens": 0, "max_tokens": 0}

    token_counts = [c.token_count for c in chunks]
    return {
        "strategy": strategy_name,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "count": len(chunks),
        "avg_tokens": sum(token_counts) / len(token_counts),
        "min_tokens": min(token_counts),
        "max_tokens": max(token_counts),
    }


def run_benchmarks(file_path: str) -> None:
    from src.infrastructure.parsers.pdf_parser import PdfParser

    print(f"\n📄 Loading: {file_path}")
    with open(file_path, "rb") as f:
        content = f.read()

    parser = PdfParser()
    text = parser.parse(content)
    print(f"📝 Extracted {len(text):,} characters\n")

    configs = [
        # (strategy, chunk_size, overlap)
        ("fixed_size", 256, 25),
        ("fixed_size", 512, 50),
        ("fixed_size", 1024, 100),
        ("sentence", 256, 25),
        ("sentence", 512, 50),
        ("recursive", 256, 25),
        ("recursive", 512, 50),
        ("recursive", 1024, 100),
    ]

    results = []
    for strategy, size, overlap in configs:
        result = benchmark_strategy(text, strategy, size, overlap)
        results.append(result)
        print(
            f"  {strategy:12} | size={size:4} | overlap={overlap:3} | "
            f"chunks={result['count']:4} | "
            f"avg_tok={result['avg_tokens']:6.1f} | "
            f"min={result['min_tokens']:4} | max={result['max_tokens']:4}"
        )

    print("\n✅ Benchmark complete.")
    print("\n💡 Recommendation:")
    best = max(results, key=lambda r: r["count"] if r["avg_tokens"] > 50 else 0)
    print(f"   Best balance: {best['strategy']} (size={best['chunk_size']}, overlap={best['overlap']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark chunking strategies")
    parser.add_argument("--file", required=True, help="Path to PDF file")
    args = parser.parse_args()
    run_benchmarks(args.file)
