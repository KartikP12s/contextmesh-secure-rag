import io
import re
import zipfile
from pathlib import Path

from docx import Document
from pypdf import PdfReader

MAX_BYTES = 8 * 1024 * 1024


def extract(filename: str, data: bytes) -> str:
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Document must contain 1 byte to 8 MiB")
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md"}:
        text = data.decode("utf-8")
        if "\x00" in text:
            raise ValueError("Binary content is not a text document")
    elif suffix == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("Invalid PDF signature")
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted or len(reader.pages) > 200:
            raise ValueError("Encrypted or oversized PDF")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif suffix == ".docx":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(x.file_size for x in archive.infolist()) > 32 * 1024 * 1024:
                raise ValueError("Expanded DOCX exceeds limit")
            if "word/document.xml" not in archive.namelist():
                raise ValueError("Invalid DOCX")
        text = "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    else:
        raise ValueError("Allowed document types: PDF, TXT, Markdown, DOCX")
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) < 8:
        raise ValueError("No usable text; scanned PDFs require an external OCR preprocessing step")
    if len(text) > 500000:
        raise ValueError("Extracted text exceeds 500,000 characters")
    return text


def chunk(text: str) -> list[str]:
    words = text.split()
    return [" ".join(words[start : start + 180]) for start in range(0, len(words), 150)]
