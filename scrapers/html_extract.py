"""Shared HTML to text extraction for the page-scraping modules.

Naive tag-stripping keeps a site's nav menu, skip-links, and footer link farm
as "content" right alongside the actual article text -- on a lot of sites
that boilerplate outweighs the real content. This strips script/style/nav/
header/footer/aside blocks first, and prefers the <main> region when the
page has one, before flattening what's left to text.
"""
from __future__ import annotations

import html as html_lib
import re

_SCRIPT_STYLE_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_CHROME_RE = re.compile(r"<(nav|header|footer|aside)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_MAIN_RE = re.compile(r"<main\b[^>]*>(.*?)</main>", re.IGNORECASE | re.DOTALL)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")
_BLANKLINES_RE = re.compile(r"\n{3,}")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def html_to_text(raw_html: str) -> str:
    body = raw_html
    main_match = _MAIN_RE.search(body)
    if main_match:
        body = main_match.group(1)
    no_script = _SCRIPT_STYLE_RE.sub(" ", body)
    no_chrome = _CHROME_RE.sub(" ", no_script)
    no_tags = _ANY_TAG_RE.sub("\n", no_chrome)
    text = html_lib.unescape(no_tags)
    text = _WS_RE.sub(" ", text)
    text = _BLANKLINES_RE.sub("\n\n", text)
    return text.strip()


def extract_title(raw_html: str, fallback: str = "") -> str:
    match = _TITLE_RE.search(raw_html)
    if not match:
        return fallback
    title = html_lib.unescape(_ANY_TAG_RE.sub("", match.group(1))).strip()
    return title.split(" | ")[0].strip() or fallback
