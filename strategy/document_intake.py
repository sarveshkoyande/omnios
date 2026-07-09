"""Text extraction for uploaded brand-plan documents (PDF / DOCX / plain text).

Lets the user attach an existing brand plan (or any working doc) in the chat instead of
retyping brand/therapy/lifecycle/budget by hand -- the extracted text is fed through the
same `interpret_message` seam as a normal chat turn, so it's picked up by whichever engine
(rules or Claude/Foundry) is currently active.
"""
from __future__ import annotations

import io

MAX_CHARS = 8000  # keep the extracted text within a sane size for one chat/LLM turn

_SUPPORTED = {"pdf", "docx", "txt", "md"}


def extract_text(filename: str, content: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _SUPPORTED:
        raise ValueError(f"Unsupported file type: .{ext or 'unknown'} (supported: .pdf, .docx, .txt, .md)")

    if ext == "pdf":
        text = _extract_pdf(content)
    elif ext == "docx":
        text = _extract_docx(content)
    else:
        text = content.decode("utf-8", errors="ignore")

    text = text.strip()
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[...truncated...]"
    return text


def _extract_pdf(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(content: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs)
