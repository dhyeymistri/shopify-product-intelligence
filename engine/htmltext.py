"""Plain-text extraction and structure signals for description HTML.

PRD 5.4: "HTML in descriptions -- text extracted for analysis; original HTML
retained for evidence offsets. Structure (lists, tables, headings) is recorded
as a signal for the machine-readability check."

PRD 8.2: spans are character offsets into the **plain-text extraction**. The
extraction is therefore part of the provenance contract, and must be a pure,
deterministic function of the input: same HTML in, same offsets out, always.

Extraction adds nothing. It unescapes entities, drops tags, and inserts a single
newline at a block boundary so that list items do not run together into a word
that was never written. It never reflows, summarizes, or reorders.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Dict, List

_BLOCK_TAGS = frozenset([
    "p", "div", "br", "li", "ul", "ol", "tr", "td", "th", "table", "section",
    "article", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre",
])
_LIST_TAGS = frozenset(["ul", "ol", "li"])
_HEADING_TAGS = frozenset(["h1", "h2", "h3", "h4", "h5", "h6"])
_TABLE_TAGS = frozenset(["table", "tr", "td", "th", "thead", "tbody"])
_DROP_CONTENT = frozenset(["script", "style"])

_HTML_HINT = re.compile(r"<[a-zA-Z/!]")
_MULTI_NEWLINE = re.compile(r"\n{2,}")
_TRAILING_WS = re.compile(r"[ \t]+\n")


class _Extractor(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.parts = []  # type: List[str]
        self.has_lists = False
        self.has_tables = False
        self.has_headings = False
        self._suppress = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _DROP_CONTENT:
            self._suppress += 1
            return
        if tag in _LIST_TAGS:
            self.has_lists = True
        if tag in _TABLE_TAGS:
            self.has_tables = True
        if tag in _HEADING_TAGS:
            self.has_headings = True
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _DROP_CONTENT:
            self._suppress = max(0, self._suppress - 1)
            return
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._suppress:
            self.parts.append(data)


def looks_like_html(text):
    # type: (object) -> bool
    return isinstance(text, str) and bool(_HTML_HINT.search(text))


def to_text(html):
    # type: (object) -> str
    """Deterministic plain-text extraction. Non-HTML input is returned unchanged."""
    if not isinstance(html, str):
        return ""
    if not looks_like_html(html):
        return html
    parser = _Extractor()
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts)
    text = _TRAILING_WS.sub("\n", text)
    text = _MULTI_NEWLINE.sub("\n", text)
    return text.strip()


def structure(html):
    # type: (object) -> Dict[str, object]
    """The `narrative.structure` block of the NPR (PRD 6.1).

    `word_count` counts whitespace-separated tokens in the plain-text
    extraction. It is a signal for D8, never a quality judgment: PRD and
    AGENTS.md 7 both forbid scoring length.
    """
    text = to_text(html)
    if isinstance(html, str) and looks_like_html(html):
        parser = _Extractor()
        parser.feed(html)
        parser.close()
        lists, tables, headings = parser.has_lists, parser.has_tables, parser.has_headings
    else:
        lists = tables = headings = False
    return {
        "has_lists": lists,
        "has_tables": tables,
        "has_headings": headings,
        "word_count": len(text.split()),
    }
