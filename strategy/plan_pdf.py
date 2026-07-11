"""Renders the plan EXACTLY as it looks in the app -- real HTML plus the app's own CSS --
via headless Chromium (Playwright), for a pixel-faithful "Download PDF".

Reuses the app's single <style> block verbatim (extracted from app/static/index.html at
call time, not duplicated), so any visual change to the live plan view automatically flows
into the PDF with zero extra maintenance. This is the only reliable way to get true fidelity:
the plan's CSS uses custom properties, CSS grid layouts and collapsible <details> sections
that neither a docx writer nor a lightweight PDF library (reportlab/xhtml2pdf) can faithfully
reproduce -- a real browser engine is the one renderer guaranteed to match what the user sees.

Requires Chromium to be installed (`python -m playwright install chromium`) -- see
requirements.txt / render.yaml. If it's unavailable on a given host, render_plan_pdf() raises
and the caller (app/server.py) falls back to plan_export.markdown_to_pdf(), a plain
reportlab-rendered PDF -- so the export feature degrades gracefully rather than 500ing.
"""
from __future__ import annotations

import functools
import pathlib
import re

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
INDEX_HTML = BASE_DIR / "app" / "static" / "index.html"

_STYLE_RE = re.compile(r"<style>(.*?)</style>", re.S)


@functools.lru_cache(maxsize=1)
def _app_css() -> str:
    """The app's real stylesheet, read once and cached. Not reloaded on edit -- restart the
    server to pick up a CSS change (same as everywhere else static assets are cached)."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    m = _STYLE_RE.search(html)
    return m.group(1) if m else ""


# Overrides the app-shell-only body rules (flex column, overflow:hidden, animated gradient
# background meant for an on-screen glass UI) which would otherwise clip/misflow a printed
# page, and forces every <details> section open -- the live app collapses everything but the
# executive summary by default, but a downloaded document should show the whole plan.
_PRINT_CSS = """
@page { size: Letter; margin: 0.5in; }
html, body { height: auto !important; overflow: visible !important; }
body { display: block !important; background: #fff !important; padding: 0 !important; }
details { display: block !important; }
.plan-doc-body { font-size: 11.5px; }
"""


def _standalone_html(plan_html: str, title: str) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0">
<style>{_app_css()}</style>
<style>{_PRINT_CSS}</style>
</head>
<body><div class="plan-doc-body">{plan_html}</div></body>
</html>"""


def render_plan_pdf(plan_html: str, title: str) -> bytes:
    """Real, pixel-faithful PDF via headless Chromium. Raises (ImportError / playwright's
    own Error) if Chromium isn't installed -- callers should catch and fall back."""
    from playwright.sync_api import sync_playwright

    html = _standalone_html(plan_html, title)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="networkidle")
            page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
            pdf_bytes = page.pdf(
                format="Letter", print_background=True,
                margin={"top": "0.5in", "bottom": "0.5in", "left": "0.5in", "right": "0.5in"},
            )
        finally:
            browser.close()
    return pdf_bytes
