"""Build the provenance index for one supplied product record.

The index answers exactly one question: *was this text supplied as input?*

Scope rule (load-bearing): the index is built ONLY from the `products[]` payload
of a fixture. The fixture envelope -- `fixture.intent`, `fixture.notes`,
`fixture.provenance` -- is eval metadata written by us, not merchant input.
Including it would let an auditor treat our own description of a bait as though
the merchant had supplied it, which would silently defeat the entire audit.
`build_index` therefore takes a product dict, never a fixture document, and
`index_from_fixture` strips the envelope explicitly.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

# Values that are present in the data but assert nothing (PRD 5.4, 9.4).
PLACEHOLDERS = frozenset(["n/a", "na", "tbd", "-", "--", ".", "xxx", "x", "?", "none", "tba", ""])

_WS_RE = re.compile(r"\s+")
_EDGE_PUNCT_RE = re.compile(r"^[\s\"'`(\[{.,;:!?]+|[\s\"'`)\]}.,;:!?]+$")


def normalize(text):
    # type: (Optional[str]) -> str
    """Case-fold, strip accents, collapse whitespace, unify dash/quote forms."""
    if text is None:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("×", "x")
    text = _WS_RE.sub(" ", text)
    return text.strip().lower()


def strip_edges(text):
    # type: (str) -> str
    return _EDGE_PUNCT_RE.sub("", text)


def word_match(needle, haystack_normalized):
    # type: (str, str) -> bool
    """Word-boundary containment on already-normalized text.

    Plain substring matching lets "ce" match inside "recreation" and "certified"
    match inside an honest question asking what a product is certified to.
    Every containment test in this package goes through here.
    """
    needle = strip_edges(normalize(needle))
    if not needle:
        return False
    return bool(
        re.search(r"(?<![0-9a-z])%s(?![0-9a-z])" % re.escape(needle), haystack_normalized)
    )


def is_placeholder(text):
    # type: (Optional[str]) -> bool
    if text is None:
        return True
    return normalize(text) in PLACEHOLDERS


class ProvenanceIndex:
    """Every string the merchant supplied for one product, with its locator."""

    def __init__(self, product):
        # type: (dict) -> None
        self.product = product
        self.spans = []  # type: List[Tuple[str, str]]   (locator, raw text)
        self._walk(product, [])
        self.corpus = " ␟ ".join(normalize(t) for _, t in self.spans)
        # A whitespace-free view, so "50 ml" in a report matches "50ml" in input.
        self.corpus_tight = re.sub(r"[\s\-_/]", "", self.corpus)

    # -- construction ----------------------------------------------------
    def _walk(self, node, path):
        # type: (Any, List[str]) -> None
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "src":  # locators are structure, not supplied content
                    continue
                self._walk(value, path + [key])
        elif isinstance(node, list):
            for i, value in enumerate(node):
                self._walk(value, path + ["[%d]" % i])
        elif isinstance(node, str):
            if node.strip():
                self.spans.append((".".join(path).replace(".[", "["), node))
        # numbers/bools/None carry no quotable text

    # -- queries ---------------------------------------------------------
    def contains(self, text):
        # type: (Optional[str]) -> bool
        """True if `text` was supplied anywhere in this product record.

        Matching is word-boundary aware: a plain substring test would let "ce"
        match inside "recreation" and quietly excuse a fabricated certification.
        The whitespace-free fallback (so a report saying "50 ml" matches an input
        holding "50ml") is applied only to needles containing a digit, where the
        false-positive risk is low.
        """
        needle = strip_edges(normalize(text))
        if not needle:
            return True  # nothing asserted
        if re.search(r"(?<![0-9a-z])%s(?![0-9a-z])" % re.escape(needle), self.corpus):
            return True
        if not any(ch.isdigit() for ch in needle):
            return False
        tight = re.sub(r"[\s\-_/]", "", needle)
        return bool(tight) and tight in self.corpus_tight

    def locate(self, text):
        # type: (str) -> List[str]
        """Locators of every supplied span containing `text`."""
        needle = strip_edges(normalize(text))
        hits = []
        for locator, raw in self.spans:
            if needle and needle in normalize(raw):
                hits.append(locator)
        return hits

    def value_at_paths(self, path_patterns):
        # type: (List[str]) -> List[Tuple[str, str]]
        """Supplied non-placeholder values whose locator matches any pattern.

        Patterns use `*` as a wildcard segment, e.g. "metafields.*" or
        "variants[*].attributes". Used to detect a false gap: an `absence`
        evidence item claiming nothing was found where something was.
        """
        found = []
        for pattern in path_patterns:
            regex = re.compile(
                "^" + re.escape(pattern).replace(r"\*", "[^.]*").replace(r"\[", r"\[") + r"($|[.\[])"
            )
            for locator, raw in self.spans:
                if regex.match(locator) and not is_placeholder(raw):
                    found.append((locator, raw))
        return found


def index_from_fixture(fixture_doc, product_id=None):
    # type: (dict, Optional[str]) -> Dict[str, ProvenanceIndex]
    """Build one index per product, ignoring the fixture envelope."""
    out = {}
    for product in fixture_doc.get("products", []):
        pid = product.get("product_id")
        if product_id is not None and pid != product_id:
            continue
        out[pid] = ProvenanceIndex(product)
    return out
