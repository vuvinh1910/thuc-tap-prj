"""
UnstructuredParser — uses the 'unstructured' library for complex PDFs.
Handles scanned PDFs (via OCR), tables, and mixed-layout documents.
Use this as a fallback when PdfParser returns insufficient text.
"""

import io
import tempfile

import structlog

logger = structlog.get_logger(__name__)


class UnstructuredParser:
    """
    Parser for complex PDFs: scanned, tables, mixed layout.
    Requires 'unstructured[pdf]' and system dependencies (poppler, tesseract).
    """

    def parse(self, content: bytes, filename: str = "document.pdf") -> str:
        """
        Extract text using unstructured's partition_pdf.

        Args:
            content: Raw PDF bytes.
            filename: Original filename (used for temp file extension).

        Returns:
            Concatenated text from all extracted elements.
        """
        try:
            from unstructured.partition.pdf import partition_pdf

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            elements = partition_pdf(
                filename=tmp_path,
                strategy="hi_res",  # Use OCR for scanned pages
                languages=["vie", "eng"],  # Vietnamese + English
            )

            text = "\n\n".join(str(el) for el in elements if str(el).strip())
            logger.info(
                "unstructured_parsed",
                element_count=len(elements),
                char_count=len(text),
            )
            return text

        except ImportError:
            logger.error("unstructured_not_installed")
            raise RuntimeError(
                "unstructured package not installed. "
                "Install with: pip install 'unstructured[pdf]'"
            )
        except Exception as e:
            logger.error("unstructured_parse_failed", error=str(e))
            raise


def auto_parse(content: bytes, filename: str = "document.pdf") -> str:
    """
    Smart parser: try pypdf first, fall back to unstructured if text is sparse.

    Args:
        content: Raw PDF bytes.
        filename: Original filename.

    Returns:
        Extracted text string.
    """
    from src.infrastructure.parsers.pdf_parser import PdfParser

    pdf_parser = PdfParser()
    text = pdf_parser.parse(content)

    # Fallback threshold: less than 100 chars per page likely means scanned PDF
    from pypdf import PdfReader
    page_count = max(len(PdfReader(io.BytesIO(content)).pages), 1)
    avg_chars_per_page = len(text) / page_count

    if avg_chars_per_page < 100:
        logger.info(
            "pypdf_sparse_fallback_unstructured",
            avg_chars_per_page=avg_chars_per_page,
        )
        unstructured_parser = UnstructuredParser()
        text = unstructured_parser.parse(content, filename)

    return text
