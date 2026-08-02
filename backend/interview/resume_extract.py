"""
Extract raw text from uploaded files — PDF or plain text.
Uses pdfplumber for PDF extraction.
"""

import io


def extract_text_from_file(content: bytes, filename: str) -> str:
    """
    Extract text from file bytes based on extension/type.
    Raises ValueError if the file type is unsupported.
    """
    lower_name = filename.lower()

    if lower_name.endswith(".pdf"):
        return _extract_pdf(content)
    elif lower_name.endswith(".txt") or lower_name.endswith(".md"):
        return content.decode("utf-8", errors="replace")
    else:
        # Attempt text decode as fallback
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError(f"Cannot read file: {filename}. Upload PDF or plain text.")


def _extract_pdf(content: bytes) -> str:
    """Extract text from PDF bytes using pdfplumber."""
    import pdfplumber

    text_parts = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    if not text_parts:
        raise ValueError("PDF contains no extractable text (may be scanned/image-only).")

    return "\n\n".join(text_parts)
