"""Classify report fields by what they are allowed to contain.

Three classes:

* ASSERTIVE   -- prose the tool wrote. Every fact-bearing token must trace to
                 supplied input. This is where fabrication would appear.
* VERBATIM    -- an evidence excerpt. Must be byte-reproducible at its locator
                 (PRD 8.1, 8.3 rule 4). Stricter than ASSERTIVE.
* STRUCTURAL  -- IDs, enums, locators, numbers. Not product facts; skipped by
                 the fact scan and validated by the evidence stage instead.
"""

from __future__ import annotations

from typing import Any, Iterator, Tuple

ASSERTIVE = "assertive"
VERBATIM = "verbatim"
STRUCTURAL = "structural"

# Leaf field names that carry tool-authored prose about the product.
_ASSERTIVE_FIELDS = frozenset([
    "title", "detail", "question", "target_field", "note", "summary",
    "explanation", "recommendation", "label", "heading", "text",
])

# Leaf field names that are enums, identifiers or machine paths.
_STRUCTURAL_FIELDS = frozenset([
    "check_id", "finding_id", "dimension", "status", "severity", "confidence",
    "determination",
    "type", "locator", "checked_paths", "scope", "level", "ref", "product_id",
    "assigned", "method", "grade", "grade_capped_by", "report_version",
    "rubric_version", "taxonomy_version", "npr_version", "pip_version",
    "run_id", "started_at", "file", "format", "attribute", "related_findings",
    "priority", "unlocks_points", "earned", "max", "penalty", "total",
    "max_applicable", "origin", "src", "key", "namespace",
])


def walk(node, path=""):
    # type: (Any, str) -> Iterator[Tuple[str, Any]]
    """Yield (json_path, value) for every leaf in a report document."""
    if isinstance(node, dict):
        for key, value in node.items():
            child = "%s.%s" % (path, key) if path else key
            for item in walk(value, child):
                yield item
    elif isinstance(node, list):
        for i, value in enumerate(node):
            for item in walk(value, "%s[%d]" % (path, i)):
                yield item
    else:
        yield path, node


def classify(json_path, value):
    # type: (str, Any) -> str
    """Decide which class a leaf belongs to, from its path."""
    if not isinstance(value, str) or not value.strip():
        return STRUCTURAL

    leaf = json_path.rsplit(".", 1)[-1]
    leaf = leaf.split("[")[0]

    if leaf == "excerpt":
        return VERBATIM
    if leaf in _STRUCTURAL_FIELDS:
        return STRUCTURAL
    if leaf in _ASSERTIVE_FIELDS:
        return ASSERTIVE
    # Unknown fields are treated as assertive: an audit must fail closed, so a
    # field nobody classified is scanned rather than skipped.
    return ASSERTIVE


def iter_findings(report):
    # type: (dict) -> Iterator[Tuple[str, dict, dict]]
    """Yield (json_path, product, finding) for every finding in a report."""
    for pi, product in enumerate(report.get("products", []) or []):
        for fi, finding in enumerate(product.get("findings", []) or []):
            yield "products[%d].findings[%d]" % (pi, fi), product, finding
