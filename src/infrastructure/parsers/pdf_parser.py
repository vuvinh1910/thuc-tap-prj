"""
PDF parser using pypdf for text-based PDFs.
Falls back gracefully when text extraction returns empty.
"""

import io

import structlog
from pypdf import PdfReader

logger = structlog.get_logger(__name__)


class PdfParser:
    """
    Extracts text from PDF files using pypdf.
    Best suited for digitally-created PDFs (not scanned images).
    For scanned PDFs, use UnstructuredParser instead.
    """

    def parse(self, content: bytes) -> str:
        """
        Extract all text from a PDF file.

        Args:
            content: Raw PDF bytes.

        Returns:
            Concatenated text from all pages, with page separators.
        """
        reader = PdfReader(io.BytesIO(content))
        pages_text: list[str] = []

        for page_num, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
                if text.strip():
                    pages_text.append(f"[Trang {page_num}]\n{text}")
            except Exception:
                logger.warning("pdf_page_extraction_failed", page=page_num)
                continue

        full_text = "\n\n".join(pages_text)
        logger.info(
            "pdf_parsed",
            page_count=len(reader.pages),
            char_count=len(full_text),
        )
        return full_text

    def parse_with_pages(self, content: bytes) -> list[tuple[int, str]]:
        """
        Extract text per page for more granular chunk metadata.

        Returns:
            List of (page_number, page_text) tuples.
        """
        reader = PdfReader(io.BytesIO(content))
        results: list[tuple[int, str]] = []

        for page_num, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
                if text.strip():
                    results.append((page_num, text))
            except Exception:
                logger.warning("pdf_page_extraction_failed", page=page_num)

        return results
