"""Run errors emitted by the normalizer.

PRD 5.4: a malformed record is skipped with a `run_error` naming the record and
the reason -- never silently dropped. PRD 7.1 carries these in `run.run_errors`.

Codes are stable identifiers. Retired codes stay reserved.
"""

from __future__ import annotations

# -- input-level -------------------------------------------------------------
UNRECOGNIZED_FORMAT = "NORM.UNRECOGNIZED_FORMAT"
MALFORMED_INPUT = "NORM.MALFORMED_INPUT"
BATCH_CEILING = "NORM.BATCH_CEILING"

# -- record-level ------------------------------------------------------------
MALFORMED_RECORD = "NORM.MALFORMED_RECORD"
MISSING_IDENTITY = "NORM.MISSING_IDENTITY"
DUPLICATE_VARIANT_ID = "NORM.DUPLICATE_VARIANT_ID"
CONTRADICTORY_VARIANT_STRUCTURE = "NORM.CONTRADICTORY_VARIANT_STRUCTURE"
DUPLICATE_PRODUCT_ID = "NORM.DUPLICATE_PRODUCT_ID"
MALFORMED_VALUE = "NORM.MALFORMED_VALUE"
RAW_EXTRAS_COLLISION = "NORM.RAW_EXTRAS_COLLISION"

# -- provenance-level --------------------------------------------------------
INVALID_PROVENANCE = "NORM.INVALID_PROVENANCE"
BROKEN_LOCATOR = "NORM.BROKEN_LOCATOR"
NON_REPRODUCIBLE_EXCERPT = "NORM.NON_REPRODUCIBLE_EXCERPT"

# -- structural --------------------------------------------------------------
INVALID_NPR = "NORM.INVALID_NPR"


class RunError(object):
    """One skipped or rejected record. Serializes into `run.run_errors`."""

    __slots__ = ("code", "record", "reason")

    def __init__(self, code, record, reason):
        # type: (str, str, str) -> None
        self.code = code
        self.record = record
        self.reason = reason

    def as_dict(self):
        return {"code": self.code, "record": self.record, "reason": self.reason}

    def __eq__(self, other):
        return isinstance(other, RunError) and self.as_dict() == other.as_dict()

    def __hash__(self):
        return hash((self.code, self.record, self.reason))

    def __repr__(self):  # pragma: no cover - debugging aid
        return "RunError(%s, %r, %r)" % (self.code, self.record, self.reason)


class NormalizationRefused(Exception):
    """Raised when the input format is not recognized (PRD 5.4). Never guess."""

    def __init__(self, reason):
        Exception.__init__(self, reason)
        self.reason = reason
        self.code = UNRECOGNIZED_FORMAT
