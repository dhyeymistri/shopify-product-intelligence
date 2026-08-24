"""Resolve PIP (Format C) source locators back to the supplied input.

PRD 8.2 defines locator syntax for Shopify CSV and Shopify GraphQL JSON but not
for Format C (PIP JSON). This module implements the PIP locator grammar used by
the eval corpus. See evals/README.md "PIP locator grammar" and the spec-gap note
reported with P1.

Grammar
-------
    locator  := segment ( "." segment )*  span?
    segment  := ident ( "[" selector "]" )?
    selector := integer | free-text key (may contain ".", e.g. custom.material)
    span     := "[" int ":" int "]"      -- only valid as the final bracket group

Examples
--------
    identity.title
    narrative.description_text[32:50]
    attributes[material_composition].value_raw
    metafields[custom.material].value
    variants[sku:NG-CREW-001].sku
    variants[sku:HL-TEE-S].option_values[Size]
    options[Size].values
    media[0].alt

Resolution returns the *text* a human would see at that locator. A node shaped
like a {value, src} pair resolves to its "value"; PRD 6.2 rule 2 means a null
value resolves to absent, not to an empty string.
"""

from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

SPAN_RE = re.compile(r"^(\d+):(\d+)$")

# Fields on a keyed collection element that a selector may match against.
_SELECTOR_FIELDS = ("key", "variant_id", "name", "id", "handle")


class LocatorError(Exception):
    """Raised when a locator cannot be parsed."""


class Resolution:
    """Outcome of resolving a locator against a product record."""

    def __init__(self, ok, text=None, node=None, error=None, span=None):
        # type: (bool, Optional[str], Any, Optional[str], Optional[Tuple[int,int]]) -> None
        self.ok = ok
        self.text = text
        self.node = node
        self.error = error
        self.span = span

    def __repr__(self):  # pragma: no cover - debugging aid
        if self.ok:
            return "Resolution(ok=True, text=%r)" % (self.text,)
        return "Resolution(ok=False, error=%r)" % (self.error,)


def parse(locator):
    # type: (str) -> Tuple[List[Tuple[str, Optional[str]]], Optional[Tuple[int,int]]]
    """Split a locator into (segments, span).

    Each segment is (ident, selector-or-None). Bracket contents are scanned with
    depth tracking so that keys containing dots survive intact.
    """
    if not isinstance(locator, str) or not locator.strip():
        raise LocatorError("empty locator")

    segments = []  # type: List[Tuple[str, Optional[str]]]
    span = None  # type: Optional[Tuple[int,int]]

    ident_chars = []  # type: List[str]
    i = 0
    n = len(locator)
    pending_selectors = []  # type: List[str]

    def flush():
        ident = "".join(ident_chars).strip()
        ident_chars[:] = []
        if pending_selectors:
            if ident:
                segments.append((ident, pending_selectors[0]))
            else:
                # bracket group with no preceding ident, e.g. ".[0]"
                segments.append(("", pending_selectors[0]))
            for extra in pending_selectors[1:]:
                segments.append(("", extra))
            pending_selectors[:] = []
        elif ident:
            segments.append((ident, None))

    while i < n:
        ch = locator[i]
        if ch == "[":
            depth = 1
            j = i + 1
            while j < n and depth:
                if locator[j] == "[":
                    depth += 1
                elif locator[j] == "]":
                    depth -= 1
                j += 1
            if depth:
                raise LocatorError("unbalanced '[' in %r" % locator)
            inner = locator[i + 1 : j - 1]
            m = SPAN_RE.match(inner)
            is_last = locator[j:].strip() == ""
            if m and is_last:
                span = (int(m.group(1)), int(m.group(2)))
            else:
                pending_selectors.append(inner)
            i = j
            continue
        if ch == ".":
            # A dot inside a pending selector was already consumed above, so any
            # dot here is a real segment separator.
            flush()
            i += 1
            continue
        ident_chars.append(ch)
        i += 1

    flush()
    if not segments:
        raise LocatorError("no segments in %r" % locator)
    if span and span[0] > span[1]:
        raise LocatorError("inverted span in %r" % locator)
    return segments, span


def _apply_selector(node, selector):
    # type: (Any, str) -> Tuple[bool, Any]
    """Apply one bracket selector to a node."""
    if isinstance(node, list):
        if selector.isdigit():
            idx = int(selector)
            if idx < len(node):
                return True, node[idx]
            return False, None
        for element in node:
            if not isinstance(element, dict):
                continue
            for field in _SELECTOR_FIELDS:
                if element.get(field) == selector:
                    return True, element
            ns, key = element.get("namespace"), element.get("key")
            if ns is not None and key is not None:
                if "%s.%s" % (ns, key) == selector:
                    return True, element
        return False, None
    if isinstance(node, dict):
        if selector in node:
            return True, node[selector]
        return False, None
    return False, None


def _node_text(node):
    # type: (Any) -> Tuple[bool, Optional[str]]
    """Extract the human-visible text of a resolved node."""
    if node is None:
        return True, None
    if isinstance(node, str):
        return True, node
    if isinstance(node, bool):
        return True, "true" if node else "false"
    if isinstance(node, (int, float)):
        return True, str(node)
    if isinstance(node, dict):
        # {value, src} pair, or a metafield/attribute element.
        for field in ("value", "value_raw", "text", "url"):
            if field in node:
                return _node_text(node[field])
        return False, None
    if isinstance(node, list):
        if all(isinstance(x, str) for x in node):
            return True, ", ".join(node)
        return False, None
    return False, None


def resolve(product, locator):
    # type: (dict, str) -> Resolution
    """Resolve a locator against one PIP product record."""
    try:
        segments, span = parse(locator)
    except LocatorError as exc:
        return Resolution(False, error=str(exc))

    node = product  # type: Any
    walked = []  # type: List[str]
    for ident, selector in segments:
        if ident:
            walked.append(ident)
            if isinstance(node, dict):
                if ident not in node:
                    return Resolution(
                        False, error="no such field '%s' at '%s'" % (ident, ".".join(walked))
                    )
                node = node[ident]
            else:
                return Resolution(
                    False, error="cannot descend into non-object at '%s'" % ".".join(walked)
                )
        if selector is not None:
            walked.append("[%s]" % selector)
            ok, node = _apply_selector(node, selector)
            if not ok:
                return Resolution(
                    False, error="selector '%s' matched nothing at '%s'" % (selector, ".".join(walked))
                )

    ok, text = _node_text(node)
    if not ok:
        return Resolution(False, node=node, error="locator does not address text content")

    if span is not None:
        if text is None:
            return Resolution(False, node=node, error="span given but value is absent (null)")
        start, end = span
        if end > len(text):
            return Resolution(
                False,
                node=node,
                error="span [%d:%d] exceeds value length %d" % (start, end, len(text)),
            )
        return Resolution(True, text=text[start:end], node=node, span=span)

    return Resolution(True, text=text, node=node)
