"""Source locators: parse, and resolve back to the supplied input.

PRD 8.2 is the single authoritative definition of locator syntax. Two forms are
in scope for P2:

    Format A -- Shopify product CSV : ``row<N>.<Column Name>`` with an optional
                                      ``[start:end]`` character span.
    Format C -- PIP JSON            : the grammar in PRD 8.2.1.

Row numbering for Format A is the **1-based CSV record index**, header included:
the header is ``row1`` and the first data record is ``row2``. Record index, not
physical line number, because a quoted cell may contain newlines and a locator
must stay stable under them.

Metafield columns are addressed by their canonical identity
``product.metafields.<namespace>.<key>`` (PRD 8.2 "Metafields"), never by the
human-facing part of the export header, so a locator survives a header rename.

Resolution is deliberately strict (PRD 8.2.1 rules 3 and 4): an absent value
resolves to absent and never to ``""``; a span over an absent value, or a span
running past the end of a value, is an error. Locators fail loudly.

This module is a second, independent implementation of the PIP grammar; the
first lives in ``evals/audits/pip_locator.py``. The duplication is deliberate:
the fabrication audit is the definition of correctness for engine output
(AGENTS.md 6), and an audit that resolved locators with the engine's own
resolver could not catch a resolver bug -- the error would cancel out.
"""

from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

SPAN_RE = re.compile(r"^(\d+):(\d+)$")
CSV_ROW_RE = re.compile(r"^row(\d+)\.(.+)$", re.DOTALL)

# Fields on a keyed collection element that a PIP selector may match against
# (PRD 8.2.1 resolution rule 1).
SELECTOR_FIELDS = ("key", "variant_id", "name", "id", "handle")

# Nodes shaped like a {value, src} pair, plus the equivalent carriers the NPR
# uses for attributes, claims and media.
_TEXT_FIELDS = ("value", "value_raw", "text", "url")


class LocatorError(Exception):
    """Raised when a locator cannot be parsed."""


class Resolution(object):
    """Outcome of resolving a locator against its source."""

    __slots__ = ("ok", "text", "node", "error", "span")

    def __init__(self, ok, text=None, node=None, error=None, span=None):
        self.ok = ok
        self.text = text
        self.node = node
        self.error = error
        self.span = span

    def __repr__(self):  # pragma: no cover - debugging aid
        if self.ok:
            return "Resolution(ok=True, text=%r)" % (self.text,)
        return "Resolution(ok=False, error=%r)" % (self.error,)


def fail(reason):
    # type: (str) -> Resolution
    return Resolution(False, error=reason)


# ---------------------------------------------------------------------------
# Format A -- CSV
# ---------------------------------------------------------------------------

def parse_csv(locator):
    # type: (str) -> Tuple[int, str, Optional[Tuple[int,int]]]
    """Split ``row<N>.<Column>[a:b]`` into (row, column, span).

    The column name may contain dots (metafield columns do), so the split is
    anchored on the ``row<N>.`` prefix and everything after it is the column.
    """
    if not isinstance(locator, str) or not locator.strip():
        raise LocatorError("empty locator")
    match = CSV_ROW_RE.match(locator.strip())
    if not match:
        raise LocatorError("not a Format A locator: %r" % (locator,))
    row = int(match.group(1))
    rest = match.group(2)
    span = None
    if rest.endswith("]"):
        open_at = rest.rfind("[")
        if open_at != -1:
            inner = rest[open_at + 1 : -1]
            span_match = SPAN_RE.match(inner)
            if span_match:
                span = (int(span_match.group(1)), int(span_match.group(2)))
                rest = rest[:open_at]
    column = rest
    if not column:
        raise LocatorError("no column in %r" % (locator,))
    if span and span[0] > span[1]:
        raise LocatorError("inverted span in %r" % (locator,))
    return row, column, span


def csv_locator(row, column, span=None):
    # type: (int, str, Optional[Tuple[int,int]]) -> str
    """Build a Format A locator. The inverse of :func:`parse_csv`."""
    base = "row%d.%s" % (row, column)
    if span is None:
        return base
    return "%s[%d:%d]" % (base, span[0], span[1])


# ---------------------------------------------------------------------------
# Format C -- PIP
# ---------------------------------------------------------------------------

def parse_pip(locator):
    # type: (str) -> Tuple[List[Tuple[str, Optional[str]]], Optional[Tuple[int,int]]]
    """Split a PIP locator into (segments, span) per PRD 8.2.1.

    Bracket contents are scanned with depth tracking, so a selector containing
    ``.`` or ``:`` (``metafields[custom.material]``, ``variants[sku:NG-1]``)
    survives segment splitting intact.
    """
    if not isinstance(locator, str) or not locator.strip():
        raise LocatorError("empty locator")

    segments = []  # type: List[Tuple[str, Optional[str]]]
    span = None  # type: Optional[Tuple[int,int]]
    ident_chars = []  # type: List[str]
    pending = []  # type: List[str]
    i, n = 0, len(locator)

    def flush():
        ident = "".join(ident_chars).strip()
        ident_chars[:] = []
        if pending:
            segments.append((ident, pending[0]))
            for extra in pending[1:]:
                segments.append(("", extra))
            pending[:] = []
        elif ident:
            segments.append((ident, None))

    while i < n:
        char = locator[i]
        if char == "[":
            depth, j = 1, i + 1
            while j < n and depth:
                if locator[j] == "[":
                    depth += 1
                elif locator[j] == "]":
                    depth -= 1
                j += 1
            if depth:
                raise LocatorError("unbalanced '[' in %r" % (locator,))
            inner = locator[i + 1 : j - 1]
            match = SPAN_RE.match(inner)
            if match and locator[j:].strip() == "":
                span = (int(match.group(1)), int(match.group(2)))
            else:
                pending.append(inner)
            i = j
            continue
        if char == ".":
            flush()
            i += 1
            continue
        ident_chars.append(char)
        i += 1

    flush()
    if not segments:
        raise LocatorError("no segments in %r" % (locator,))
    if span and span[0] > span[1]:
        raise LocatorError("inverted span in %r" % (locator,))
    return segments, span


def _select(node, selector):
    # type: (Any, str) -> Tuple[bool, Any]
    if isinstance(node, list):
        if selector.isdigit():
            index = int(selector)
            if index < len(node):
                return True, node[index]
            return False, None
        for element in node:
            if not isinstance(element, dict):
                continue
            for field in SELECTOR_FIELDS:
                if element.get(field) == selector:
                    return True, element
            namespace, key = element.get("namespace"), element.get("key")
            if namespace is not None and key is not None:
                if "%s.%s" % (namespace, key) == selector:
                    return True, element
        return False, None
    if isinstance(node, dict):
        if selector in node:
            return True, node[selector]
        return False, None
    return False, None


def node_text(node):
    # type: (Any) -> Tuple[bool, Optional[str]]
    """The human-visible text at a resolved node, or (False, None) if it has none."""
    if node is None:
        return True, None
    if isinstance(node, str):
        return True, node
    if isinstance(node, bool):
        return True, "true" if node else "false"
    if isinstance(node, (int, float)):
        return True, str(node)
    if isinstance(node, dict):
        for field in _TEXT_FIELDS:
            if field in node:
                return node_text(node[field])
        return False, None
    if isinstance(node, list):
        if all(isinstance(x, str) for x in node):
            return True, ", ".join(node)
        return False, None
    return False, None


def apply_span(text, span, node=None):
    # type: (Optional[str], Optional[Tuple[int,int]], Any) -> Resolution
    """Apply a span to resolved text under PRD 8.2.1 rules 3 and 4."""
    if span is None:
        return Resolution(True, text=text, node=node)
    if text is None:
        return Resolution(False, node=node, error="span given but value is absent (null)")
    start, end = span
    if end > len(text):
        return Resolution(
            False, node=node,
            error="span [%d:%d] exceeds value length %d" % (start, end, len(text)),
        )
    return Resolution(True, text=text[start:end], node=node, span=span)


def resolve_pip(product, locator, require_text=True):
    # type: (dict, str, bool) -> Resolution
    """Resolve a PIP locator against one product record (PRD 8.2.1).

    ``require_text=False`` addresses a node that carries no text of its own --
    an `options[Size]` element, say, whose content is a list of values rather
    than a value. The locator must still resolve; only the demand that it end
    on quotable text is relaxed.
    """
    try:
        segments, span = parse_pip(locator)
    except LocatorError as exc:
        return fail(str(exc))

    node = product  # type: Any
    walked = []  # type: List[str]
    for ident, selector in segments:
        if ident:
            walked.append(ident)
            if not isinstance(node, dict):
                return fail("cannot descend into non-object at '%s'" % ".".join(walked))
            if ident not in node:
                return fail("no such field '%s' at '%s'" % (ident, ".".join(walked)))
            node = node[ident]
        if selector is not None:
            walked.append("[%s]" % selector)
            ok, node = _select(node, selector)
            if not ok:
                return fail("selector '%s' matched nothing at '%s'"
                            % (selector, ".".join(walked)))

    ok, text = node_text(node)
    if not ok:
        if require_text or span is not None:
            return Resolution(False, node=node,
                              error="locator does not address text content")
        return Resolution(True, text=None, node=node)
    return apply_span(text, span, node)
