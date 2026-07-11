"""Renders the composed Brand Engagement Plan (plan_document.py's markdown output) to a real
Word (.docx) or PDF file, so the plan can leave the browser as a shareable document.

Deliberately built from `plan_markdown`, not `plan_html`: the HTML uses CSS custom
properties, a grid layout, and collapsible <details> sections that neither a docx writer nor
a lightweight PDF renderer would faithfully reproduce. The markdown is a clean, already-
structured source (headings, tables, bullet lists) that both converters parse the same way
via `_parse_blocks()`, so the two exports stay visually consistent with each other.

python-docx and reportlab are both pure-Python (no system libraries like wkhtmltopdf/cairo),
so this works unmodified on a minimal host such as Render.
"""
from __future__ import annotations

import io
import re

NAVY = "0B3D91"   # matches --indegene-navy
MAGENTA = "C6007E"  # matches --tk-magenta, used for H1


# --------------------------------------------------------------------- markdown parsing ---

def _parse_blocks(markdown: str) -> list[dict]:
    """Turn the plan's markdown into an ordered list of simple blocks:
      {"type": "heading", "level": 1-4, "text": str}
      {"type": "para", "text": str}
      {"type": "bullets", "items": [str, ...]}
      {"type": "table", "header": [str, ...], "rows": [[str, ...], ...]}
      {"type": "hr"}
    Handles exactly the shapes plan_document.py emits: '#'..'####' headings, '| a | b |'
    GitHub-style tables with a '|---|---|' separator row, '- ' bullets, '---' rules, and
    blank-line-separated paragraphs. Anything else is treated as a plain paragraph line.
    """
    lines = markdown.replace("\r\n", "\n").split("\n")
    blocks: list[dict] = []
    i, n = 0, len(lines)
    para_buf: list[str] = []

    def flush_para():
        if para_buf:
            text = " ".join(s.strip() for s in para_buf if s.strip())
            if text:
                blocks.append({"type": "para", "text": text})
            para_buf.clear()

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_para()
            i += 1
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            flush_para()
            blocks.append({"type": "heading", "level": len(m.group(1)), "text": m.group(2).strip()})
            i += 1
            continue

        if re.match(r"^-{3,}\s*$", stripped):
            flush_para()
            blocks.append({"type": "hr"})
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < n and re.match(r"^\|?\s*:?-{2,}.*\|", lines[i + 1].strip()):
            flush_para()
            header = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2  # skip the |---|---| separator row
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            blocks.append({"type": "table", "header": header, "rows": rows})
            continue

        if re.match(r"^[-*]\s+", stripped):
            flush_para()
            items = []
            while i < n and re.match(r"^[-*]\s+", lines[i].strip()):
                items.append(re.sub(r"^[-*]\s+", "", lines[i].strip()))
                i += 1
            blocks.append({"type": "bullets", "items": items})
            continue

        para_buf.append(stripped)
        i += 1

    flush_para()
    return blocks


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")


def _strip_markup(text: str) -> str:
    """Plain text with **bold**/*italic* markers removed (for contexts with no rich text)."""
    return _ITALIC_RE.sub(r"\1", _BOLD_RE.sub(r"\1", text))


# --------------------------------------------------------------------- docx (Word) --------

def markdown_to_docx(markdown: str, title: str) -> bytes:
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    navy = RGBColor.from_string(NAVY)

    def add_runs(paragraph, text: str):
        """Split on **bold** markers and add each segment as its own run."""
        pos = 0
        for m in _BOLD_RE.finditer(text):
            if m.start() > pos:
                paragraph.add_run(_strip_markup(text[pos:m.start()]))
            run = paragraph.add_run(_strip_markup(m.group(1)))
            run.bold = True
            pos = m.end()
        if pos < len(text):
            paragraph.add_run(_strip_markup(text[pos:]))

    title_p = doc.add_heading(title, level=0)
    for run in title_p.runs:
        run.font.color.rgb = navy

    for block in _parse_blocks(markdown):
        t = block["type"]
        if t == "heading":
            level = min(max(block["level"], 1), 4)
            h = doc.add_heading("", level=level)
            add_runs(h, block["text"])
            for run in h.runs:
                run.font.color.rgb = navy
        elif t == "para":
            p = doc.add_paragraph()
            add_runs(p, block["text"])
        elif t == "bullets":
            for item in block["items"]:
                p = doc.add_paragraph(style="List Bullet")
                add_runs(p, item)
        elif t == "table" and block["rows"]:
            cols = len(block["header"])
            table = doc.add_table(rows=1, cols=cols)
            table.style = "Light Grid Accent 1"
            for c, text in enumerate(block["header"]):
                cell_p = table.rows[0].cells[c].paragraphs[0]
                run = cell_p.add_run(_strip_markup(text))
                run.bold = True
            for row in block["rows"]:
                cells = table.add_row().cells
                for c, text in enumerate(row[:cols]):
                    add_runs(cells[c].paragraphs[0], text)
        elif t == "hr":
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run("• • •")
            run.font.color.rgb = RGBColor.from_string("999999")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# --------------------------------------------------------------------- PDF ----------------

def markdown_to_pdf(markdown: str, title: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (HRFlowable, ListFlowable, ListItem, Paragraph,
                                     SimpleDocTemplate, Spacer, Table, TableStyle)

    navy = colors.HexColor(f"#{NAVY}")
    magenta = colors.HexColor(f"#{MAGENTA}")
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("PlanTitle", parent=base["Title"], textColor=magenta, fontSize=20, spaceAfter=14),
        "h1": ParagraphStyle("H1", parent=base["Heading1"], textColor=navy, fontSize=14, spaceBefore=14, spaceAfter=6),
        "h2": ParagraphStyle("H2", parent=base["Heading2"], textColor=navy, fontSize=12, spaceBefore=10, spaceAfter=5),
        "h3": ParagraphStyle("H3", parent=base["Heading3"], textColor=navy, fontSize=10.5, spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontSize=9.5, leading=13.5, spaceAfter=6),
        "cell": ParagraphStyle("Cell", parent=base["BodyText"], fontSize=8.5, leading=11.5),
        "cell_head": ParagraphStyle("CellHead", parent=base["BodyText"], fontSize=8.5, leading=11.5,
                                    textColor=colors.white, fontName="Helvetica-Bold"),
    }

    def rl_markup(text: str) -> str:
        """**bold**/*italic* -> reportlab's small inline-markup subset; escape raw '<'/'&' first."""
        t = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        t = _BOLD_RE.sub(r"<b>\1</b>", t)
        t = _ITALIC_RE.sub(r"<i>\1</i>", t)
        return t

    story = [Paragraph(title, styles["title"]), Spacer(1, 4)]
    heading_style = {1: "h1", 2: "h1", 3: "h2", 4: "h3"}

    for block in _parse_blocks(markdown):
        t = block["type"]
        if t == "heading":
            story.append(Paragraph(rl_markup(block["text"]), styles[heading_style.get(block["level"], "h3")]))
        elif t == "para":
            story.append(Paragraph(rl_markup(block["text"]), styles["body"]))
        elif t == "bullets":
            items = [ListItem(Paragraph(rl_markup(x), styles["body"]), leftIndent=6) for x in block["items"]]
            story.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=14))
            story.append(Spacer(1, 4))
        elif t == "table" and block["rows"]:
            header = [Paragraph(rl_markup(h), styles["cell_head"]) for h in block["header"]]
            rows = [[Paragraph(rl_markup(c), styles["cell"]) for c in row] for row in block["rows"]]
            data = [header] + rows
            avail = LETTER[0] - 1.6 * inch
            col_w = avail / max(len(block["header"]), 1)
            table = Table(data, colWidths=[col_w] * len(block["header"]), repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), navy),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
            ]))
            story.append(table)
            story.append(Spacer(1, 8))
        elif t == "hr":
            story.append(Spacer(1, 4))
            story.append(HRFlowable(width="100%", color=colors.HexColor("#DDDDDD")))
            story.append(Spacer(1, 8))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                            leftMargin=0.8 * inch, rightMargin=0.8 * inch, title=title)
    doc.build(story)
    return buf.getvalue()
