"""
ChunkingService — splits raw text into overlapping chunks for embedding.
Supports multiple strategies configurable via settings.
"""

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

import tiktoken

from src.core.entities.chunk import Chunk


class ChunkingStrategy(str, Enum):
    FIXED_SIZE = "fixed_size"
    SENTENCE = "sentence"
    RECURSIVE = "recursive"


@dataclass
class ChunkingConfig:
    """Configuration for the chunking strategy."""

    strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE
    chunk_size: int = 512        # Target tokens per chunk
    overlap: int = 50            # Overlap tokens between consecutive chunks
    min_chunk_size: int = 50     # Discard chunks smaller than this


class ChunkingService:
    """
    Splits document text into chunks suitable for embedding.

    Design note: Strategies are implemented as internal methods to keep
    the class cohesive. For more complex strategies, extract to Strategy objects.
    """

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self._config = config or ChunkingConfig()
        # tiktoken for accurate token counting (matches OpenAI's tokenizer)
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    def split(self, text: str, document_id: UUID, page_number: int = 0) -> list[Chunk]:
        """
        Split text into chunks using the configured strategy.

        Args:
            text: The full document text.
            document_id: UUID of the parent document.
            page_number: Page number hint (used for simple single-page text).

        Returns:
            Ordered list of Chunk objects.
        """
        text = text.strip()
        if not text:
            return []

        strategy = self._config.strategy
        if strategy == ChunkingStrategy.FIXED_SIZE:
            raw_chunks = self._fixed_size_split(text)
        elif strategy == ChunkingStrategy.SENTENCE:
            raw_chunks = self._sentence_split(text)
        else:  # RECURSIVE (default)
            raw_chunks = self._recursive_split(text)

        # Filter and build Chunk entities
        chunks: list[Chunk] = []
        char_cursor = 0

        for i, content in enumerate(raw_chunks):
            content = content.strip()
            if not content:
                continue

            token_count = len(self._tokenizer.encode(content))
            if token_count < self._config.min_chunk_size:
                continue

            # Find char position in original text
            char_start = text.find(content, char_cursor)
            if char_start == -1:
                char_start = char_cursor
            char_end = char_start + len(content)
            char_cursor = max(char_cursor, char_start)

            chunks.append(
                Chunk(
                    document_id=document_id,
                    content=content,
                    chunk_index=i,
                    page_number=page_number,
                    char_start=char_start,
                    char_end=char_end,
                    token_count=token_count,
                )
            )

        return chunks

    def split_with_pages(
        self, pages: list[tuple[int, str]], document_id: UUID
    ) -> list[Chunk]:
        """
        Split page-aware text into chunks, preserving page_number metadata.
        Use this when parsing with pdf_parser.parse_with_pages().

        Args:
            pages: List of (page_number, page_text) tuples.
            document_id: UUID of the parent document.

        Returns:
            Ordered list of Chunk objects with accurate page numbers.
        """
        all_chunks: list[Chunk] = []
        global_index = 0

        for page_num, page_text in pages:
            page_chunks = self.split(page_text, document_id, page_number=page_num)
            for chunk in page_chunks:
                # Re-index globally across all pages
                all_chunks.append(
                    Chunk(
                        id=chunk.id,
                        document_id=chunk.document_id,
                        content=chunk.content,
                        chunk_index=global_index,
                        page_number=page_num,
                        char_start=chunk.char_start,
                        char_end=chunk.char_end,
                        token_count=chunk.token_count,
                    )
                )
                global_index += 1

        return all_chunks

    # ── Private Strategy Implementations ────────────────────────────────────

    def _fixed_size_split(self, text: str) -> list[str]:
        """
        Split by fixed token count with overlap.
        Simple but effective for uniform documents.
        """
        tokens = self._tokenizer.encode(text)
        chunks: list[str] = []
        step = self._config.chunk_size - self._config.overlap

        for i in range(0, len(tokens), step):
            chunk_tokens = tokens[i : i + self._config.chunk_size]
            chunk_text = self._tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)

        return chunks

    def _sentence_split(self, text: str) -> list[str]:
        """
        Split on sentence boundaries, grouping into target-size chunks.
        Better for preserving semantic meaning than fixed-size.
        """
        import re

        # Vietnamese-aware sentence splitting (handles both . and newlines)
        sentences = re.split(r"(?<=[.!?।\n])\s+", text)
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_tokens = len(self._tokenizer.encode(sentence))

            if current_tokens + sentence_tokens > self._config.chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                # Keep overlap sentences
                overlap_chunks = current_chunk[-2:] if len(current_chunk) > 2 else current_chunk
                current_chunk = overlap_chunks
                current_tokens = sum(
                    len(self._tokenizer.encode(s)) for s in current_chunk
                )

            current_chunk.append(sentence)
            current_tokens += sentence_tokens

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _recursive_split(self, text: str, depth: int = 0) -> list[str]:
        """
        Recursive character splitting — tries paragraph → sentence → word splits.
        Best for Vietnamese legal documents with varied structure.
        """
        max_depth = 3
        separators = ["\n\n", "\n", ". ", " "]

        token_count = len(self._tokenizer.encode(text))
        if token_count <= self._config.chunk_size:
            return [text] if text.strip() else []

        if depth >= max_depth:
            return self._fixed_size_split(text)

        separator = separators[min(depth, len(separators) - 1)]
        splits = text.split(separator)

        chunks: list[str] = []
        current_parts: list[str] = []
        current_tokens = 0

        for part in splits:
            part_tokens = len(self._tokenizer.encode(part))

            if current_tokens + part_tokens > self._config.chunk_size:
                if current_parts:
                    combined = separator.join(current_parts)
                    chunks.append(combined)
                    # Overlap: keep last part(s)
                    overlap_tokens = 0
                    overlap_parts: list[str] = []
                    for p in reversed(current_parts):
                        p_tok = len(self._tokenizer.encode(p))
                        if overlap_tokens + p_tok <= self._config.overlap:
                            overlap_parts.insert(0, p)
                            overlap_tokens += p_tok
                        else:
                            break
                    current_parts = overlap_parts
                    current_tokens = overlap_tokens

                if part_tokens > self._config.chunk_size:
                    # Recursively split oversized parts
                    sub_chunks = self._recursive_split(part, depth + 1)
                    chunks.extend(sub_chunks)
                    current_parts = []
                    current_tokens = 0
                    continue

            current_parts.append(part)
            current_tokens += part_tokens

        if current_parts:
            chunks.append(separator.join(current_parts))

        return [c for c in chunks if c.strip()]
