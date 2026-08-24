"""The normalizer's public surface.

    normalize_file(path)              -> NormalizationResult
    normalize_document(data, format)  -> NormalizationResult
    detect_format(...)                -> "shopify_csv" | "pip_json"

One entry point, two input formats, one output shape (PRD 5: "All three are
converted to the same Normalized Product Record before any check runs. No check
ever reads a raw input format directly.").

Every record that survives normalization has been validated structurally and
proven reproducible against its own source. A record that fails either is
skipped with a run error naming it and the reason (PRD 5.4) -- never silently
repaired, because a repair to a record's meaning is indistinguishable from an
invented fact once the input file is out of view.

Format B (Shopify Admin GraphQL JSON, PRD 5.2) is not implemented in P2. It is
refused by name rather than guessed at.
"""

from __future__ import annotations

import json
import os
from typing import Any, List, Optional

from . import csv_input, errors, pip_input, validate
from .model import FORMAT_CSV, FORMAT_GRAPHQL, FORMAT_PIP, NPR_VERSION  # noqa: F401
from .sources import SourceDocument


class NormalizationResult(object):
    """Products, the errors that kept records out, and the source they came from.

    The source travels with the result on purpose: a locator nobody can resolve
    is not provenance, and keeping the input reachable is what lets a caller --
    or a test -- check rather than trust.
    """

    __slots__ = ("products", "run_errors", "source", "format", "file")

    def __init__(self, products, run_errors, source, format, file):
        # type: (List[dict], List[errors.RunError], SourceDocument, str, Optional[str]) -> None
        self.products = products
        self.run_errors = run_errors
        self.source = source
        self.format = format
        self.file = file

    @property
    def ok(self):
        # type: () -> bool
        return not self.run_errors

    def codes(self):
        # type: () -> List[str]
        return [error.code for error in self.run_errors]

    def as_dict(self):
        return {
            "format": self.format,
            "file": self.file,
            "products": self.products,
            "run_errors": [error.as_dict() for error in self.run_errors],
        }

    def __repr__(self):  # pragma: no cover - debugging aid
        return "NormalizationResult(%d product(s), %d run error(s))" % (
            len(self.products), len(self.run_errors))


def detect_format(text=None, path=None, data=None):
    # type: (Optional[str], Optional[str], Any) -> str
    """Identify the input format, or refuse.

    Detection is structural, not hopeful: a JSON document is Format C only if it
    carries a ``products`` member, and text is Format A only if its header
    carries the two columns PRD 5.1 makes the format's identity. Anything else
    is refused (PRD 5.4) rather than mapped by guesswork.
    """
    if data is not None:
        if isinstance(data, dict) and "products" in data:
            return FORMAT_PIP
        if isinstance(data, list):
            raise errors.NormalizationRefused(
                "a bare JSON array looks like Format B (Shopify Admin GraphQL, "
                "PRD 5.2), which the P2 normalizer does not implement")
        raise errors.NormalizationRefused("unrecognized JSON input: no 'products' member")

    if text is None and path is not None:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    if text is None:
        raise errors.NormalizationRefused("no input supplied")

    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(text)
        except ValueError as exc:
            raise errors.NormalizationRefused("input is not valid JSON: %s" % exc)
        return detect_format(data=parsed)

    header = text.split("\n", 1)[0]
    if csv_input.COL_HANDLE in header and csv_input.COL_TITLE in header:
        return FORMAT_CSV
    raise errors.NormalizationRefused(
        "unrecognized input: not JSON, and the first line does not carry the "
        "%r and %r columns a Shopify product CSV is defined by (PRD 5.1)"
        % (csv_input.COL_TITLE, csv_input.COL_HANDLE))


def normalize_document(data, format=None, file=None, text=None):
    # type: (Any, Optional[str], Optional[str], Optional[str]) -> NormalizationResult
    """Normalize an already-loaded document (parsed JSON, or CSV text)."""
    if format is None:
        format = detect_format(text=text if text is not None else
                               (data if isinstance(data, str) else None),
                               data=None if isinstance(data, str) else data)
    if format == FORMAT_PIP:
        products, run_errors, source = pip_input.normalize(data, file=file)
    elif format == FORMAT_CSV:
        products, run_errors, source = csv_input.normalize(
            data if isinstance(data, str) else text or "", file=file)
    elif format == FORMAT_GRAPHQL:
        raise errors.NormalizationRefused(
            "Format B (Shopify Admin GraphQL JSON, PRD 5.2) is not implemented "
            "in P2")
    else:
        raise errors.NormalizationRefused("unknown format %r" % (format,))

    kept = []
    for npr in products:
        record_errors = validate.validate_npr(npr)
        record_errors.extend(validate.validate_provenance(npr, source))
        if record_errors:
            run_errors.extend(record_errors)
            continue
        kept.append(npr)
    return NormalizationResult(kept, run_errors, source, format, file)


def normalize_file(path):
    # type: (str) -> NormalizationResult
    """Normalize a file on disk, choosing the format from its content."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    format = detect_format(text=text, path=path)
    relative = path
    if os.path.isabs(path):
        relative = os.path.relpath(path)
    if format == FORMAT_PIP:
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise errors.NormalizationRefused("input is not valid JSON: %s" % exc)
        return normalize_document(data, format=format, file=relative)
    return normalize_document(text, format=format, file=relative, text=text)
