"""Source documents: the supplied input, kept resolvable.

A locator is only worth writing if something can resolve it. PRD 8.2 requires a
locator to be "resolvable back to the input by a human with the input file
open"; these classes are the machine equivalent, and they are what lets
``validate.validate_provenance`` prove -- rather than assume -- that every value
in an NPR can be reproduced from the file it came from.

The engine keeps the source alongside the records it produced. Normalization
that cannot be checked against its own input is exactly the failure mode the
no-invention rule exists to prevent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import htmltext
from .locators import LocatorError, Resolution, apply_span, fail, parse_csv, resolve_pip


class SourceDocument(object):
    """Base class. ``resolve`` never guesses; it fails loudly (PRD 8.2.1 rule 4)."""

    format = None  # type: Optional[str]

    def __init__(self, file):
        # type: (Optional[str]) -> None
        self.file = file

    def resolve(self, locator, product_id=None, view=None):
        # type: (str, Optional[str], Optional[str]) -> Resolution
        raise NotImplementedError


class PipSource(SourceDocument):
    """A Format C document. Locators address one product record (PRD 8.2.1)."""

    format = "pip_json"

    def __init__(self, document, file=None):
        # type: (dict, Optional[str]) -> None
        SourceDocument.__init__(self, file)
        self.document = document
        # Only `products[]` is supplied input. The fixture envelope is metadata
        # about the file and can never be addressed (PRD 5.3.1 rule 4).
        self.products = {}  # type: Dict[str, dict]
        self.order = []  # type: List[str]
        for record in document.get("products") or []:
            if not isinstance(record, dict):
                continue
            pid = record.get("product_id")
            if isinstance(pid, str) and pid not in self.products:
                self.products[pid] = record
                self.order.append(pid)

    def resolve(self, locator, product_id=None, view=None):
        if product_id is None:
            if len(self.order) != 1:
                return fail("PIP resolution needs a product_id (%d products in file)"
                            % len(self.order))
            product_id = self.order[0]
        record = self.products.get(product_id)
        if record is None:
            return fail("no product %r in this document" % (product_id,))
        return resolve_pip(record, locator, require_text=(view != "node"))


class CsvSource(SourceDocument):
    """A Format A document, indexed by CSV record number.

    Row numbering is the 1-based record index with the header as ``row1``, so a
    quoted cell containing newlines does not shift every locator after it.

    Two views of a cell exist because PRD 8.2 puts spans on the **plain-text
    extraction** while PRD 5.4 retains the original HTML for evidence: ``raw``
    is the cell as the file holds it, ``text`` is its plain-text extraction. For
    a cell with no markup the two are identical.
    """

    format = "shopify_csv"

    def __init__(self, header, rows, file=None):
        # type: (List[str], List[Tuple[int, List[str]]], Optional[str]) -> None
        SourceDocument.__init__(self, file)
        self.header = list(header)
        self.rows = dict(rows)  # row number -> cells
        self.row_numbers = [n for n, _ in rows]
        #: canonical column identity -> position in the header
        self.columns = {}  # type: Dict[str, int]
        for index, name in enumerate(self.header):
            self.columns.setdefault(name, index)
        #: extra aliases (metafield canonical names) -> position
        self.aliases = {}  # type: Dict[str, int]

    def add_alias(self, canonical, header_name):
        # type: (str, str) -> None
        if header_name in self.columns:
            self.aliases[canonical] = self.columns[header_name]

    def _column_index(self, column):
        # type: (str) -> Optional[int]
        if column in self.aliases:
            return self.aliases[column]
        return self.columns.get(column)

    def cell(self, row, column):
        # type: (int, str) -> Tuple[bool, Optional[str]]
        cells = self.rows.get(row)
        if cells is None:
            return False, None
        index = self._column_index(column)
        if index is None or index >= len(cells):
            return False, None
        return True, cells[index]

    def resolve(self, locator, product_id=None, view=None):
        try:
            row, column, span = parse_csv(locator)
        except LocatorError as exc:
            return fail(str(exc))
        found, raw = self.cell(row, column)
        if not found:
            if row not in self.rows:
                return fail("no row %d in this file" % row)
            return fail("no column %r in this file" % (column,))
        if raw == "":
            # An empty cell is absent, not an empty string (PRD 6.2 rule 2).
            return apply_span(None, span, node=raw)
        if view == "text" or (view is None and span is not None
                              and htmltext.looks_like_html(raw)):
            return apply_span(htmltext.to_text(raw), span, node=raw)
        return apply_span(raw, span, node=raw)

    def record_locator(self, row_numbers):
        # type: (List[int]) -> str
        """The whole-record locator for `source.locator` (PRD 6.1)."""
        if not row_numbers:
            return "rows -"
        low, high = min(row_numbers), max(row_numbers)
        return "row%d" % low if low == high else "rows %d-%d" % (low, high)
