"""Text extraction for uploaded brand-plan documents (PDF / DOCX / plain text).

Lets the user attach an existing brand plan (or any working doc) in the chat instead of
retyping brand/therapy/lifecycle/budget by hand -- the extracted text is fed through the
same `interpret_message` seam as a normal chat turn, so it's picked up by whichever engine
(rules or Claude/Foundry) is currently active.
"""
from __future__ import annotations

import io

MAX_CHARS = 8000  # keep the extracted text within a sane size for one chat/LLM turn

_SUPPORTED = {"pdf", "docx", "pptx", "txt", "md"}


def extract_text(filename: str, content: bytes, max_chars: int = MAX_CHARS) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _SUPPORTED:
        raise ValueError(f"Unsupported file type: .{ext or 'unknown'} (supported: .pdf, .docx, .pptx, .txt, .md)")

    if ext == "pdf":
        text = _extract_pdf(content)
    elif ext == "docx":
        text = _extract_docx(content)
    elif ext == "pptx":
        text = _extract_pptx(content)
    else:
        text = content.decode("utf-8", errors="ignore")

    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[...truncated...]"
    return text


def _extract_pdf(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(content: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs)


def _extract_pptx(content: bytes) -> str:
    """Slide by slide, keeping the slide number so extracted facts can cite it."""
    from pptx import Presentation

    out = []
    for n, slide in enumerate(Presentation(io.BytesIO(content)).slides, 1):
        parts = []
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                parts.append(shape.text_frame.text.strip())
            if getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    parts.append(" | ".join(c.text.strip() for c in row.cells))
        if parts:
            out.append(f"[Slide {n}]\n" + "\n".join(parts))
    return "\n\n".join(out)
