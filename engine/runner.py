"""Run the applicable check set over one normalized product record.

The runner does three things and refuses the fourth. It selects the applicable
checks from the assigned category, executes each one against the canonical
record, and seals the resulting ledger into a deterministic order. It does not
compute a score: no total, no dimension subtotal, no grade, no penalty sum.
Aggregation is a later phase, and building it early would mean building it
against an incomplete set of statuses.

Determinism is a requirement, not a property that happened: checks run in
registry order, the ledger sorts on a fixed total key before assigning ids, and
nothing in the path reads a clock, a hash seed, or a set iteration order.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import checks as check_module
from . import classify as classify_module
from . import registry
from . import rubric_data as R
from .evidence import EvidenceBuilder
from .findings import EvidenceError, FindingLedger
from . import taxonomy_data as T
from .taxonomy_data import UNCATEGORIZED


class CheckContext(object):
    """What a check is allowed to see. Nothing here reaches outside the input."""

    __slots__ = ("npr", "builder", "category", "ledger", "registry")

    def __init__(self, npr, builder, category, ledger):
        self.npr = npr
        self.builder = builder
        self.category = category
        self.ledger = ledger
        self.registry = registry


class ProductResult(object):
    """One product's classification, findings and the checks that deferred."""

    __slots__ = ("product_id", "title", "classification", "ledger")

    def __init__(self, product_id, title, classification, ledger):
        self.product_id = product_id
        self.title = title
        self.classification = classification
        self.ledger = ledger

    @property
    def findings(self):
        return self.ledger.findings

    def status_of(self, check_id):
        # type: (str) -> Optional[str]
        for finding in self.ledger.findings:
            if finding.check_id == check_id:
                return finding.status
        return None

    def as_dict(self):
        # type: () -> Dict[str, Any]
        """The per-product members of `report.json` this phase produces.

        Deliberately no `score` member: PRD 7.1 puts one there and this phase
        does not compute one, and an empty or zeroed score object would read as
        a computed result rather than as work not yet done.
        """
        out = {
            "product_id": self.product_id,
            "title": self.title,
            "category": self.classification.as_dict(),
        }
        out.update(self.ledger.as_dict())
        out["product_id"] = self.product_id
        return out


def _na_reason(check, npr, category):
    # type: (Any, dict, str) -> Optional[str]
    """Structural triggers only (`taxonomy.md` 4.4).

    A check is never removed because information is missing; that is `UNKNOWN`,
    and it keeps its points in the denominator.

    Applicability is decided here rather than inside a check for a reason worth
    keeping: a check that decides its own applicability can decide it from
    something it read, and `taxonomy.md` 4.4's rule is that a trigger is
    structural and never assumed. Everything this function reads is the shape
    of the record and the assigned category -- never a supplied value.
    """
    triggers = check.na_trigger
    if R.NA_SINGLE_VARIANT in triggers:
        if len(npr.get("variants") or []) <= 1:
            return ("A single variant is supplied, so this check has no "
                    "structural trigger.")
    if R.NA_EMPTY_VARIANT_SCOPE_SET in triggers:
        # D-029. Both grounds are structural and neither is a missing value,
        # but they are different facts and the merchant is told which.
        if category == UNCATEGORIZED:
            return ("No category is assigned, so no category attribute "
                    "requires per-variant resolution. The category-specific "
                    "attribute checks did not run either (rubric.md 4/D2); "
                    "setting a product category is what makes both apply.")
        if not T.variant_scope_keys(category):
            return ("No attribute in this product's category has to resolve "
                    "per variant, so there is no per-variant requirement for "
                    "this check to measure.")
    return None


def run_product(npr, source, override=None):
    # type: (dict, Any, Optional[str]) -> ProductResult
    """Classify one record, then run every check that applies to it."""
    product_id = npr.get("product_id")
    ledger = FindingLedger(product_id)
    builder = EvidenceBuilder(source, product_id)

    try:
        classification = classify_module.classify(npr, builder, override)
    except EvidenceError as exc:
        ledger.error("CHECK.CLASSIFICATION_EVIDENCE", str(exc))
        classification = classify_module.Classification(
            UNCATEGORIZED, UNCATEGORIZED, "low", [])

    ctx = CheckContext(npr, builder, classification.assigned, ledger)

    for check in registry.checks_for_category(classification.assigned):
        # A penalty check never runs on its own. D6 fires only where an
        # attribute check found two supplied values that disagree, and D7 fires
        # only on a claim that is present; absence of either is not a finding
        # at all, and a product that makes no claims keeps its full D7
        # (`rubric.md` 4/D7). Running them standalone would turn "nothing
        # wrong here" into an UNKNOWN, which is exactly backwards.
        if check.is_penalty:
            if check.dimension == R.D7:
                ledger.defer(check.check_id,
                             "Recognizing a claim in a quoted span is language "
                             "recognition (PRD 9.6), which this phase does not "
                             "perform.")
            continue

        reason = _na_reason(check, npr, classification.assigned)
        if reason:
            try:
                ledger.add(check_module.not_applicable(check, builder, reason))
            except EvidenceError as exc:
                ledger.error("CHECK.EVIDENCE", str(exc), check.check_id)
            continue
        # A check whose conditional trigger needs recognition never decides
        # applicability by assumption (`taxonomy.md` 4.4).
        if check.conditional_trigger:
            ledger.defer(check.check_id,
                         "Applicability depends on a structural trigger that "
                         "needs recognition (%s)." % check.conditional_trigger)
            continue
        try:
            produced = check_module.run(check, ctx)
        except EvidenceError as exc:
            ledger.error("CHECK.EVIDENCE", str(exc), check.check_id)
            continue
        for finding in produced:
            ledger.add(finding)

    if classification.assigned == UNCATEGORIZED:
        ledger.defer("D2_category_attributes",
                     "No category was assigned, so the category-specific "
                     "attribute checks did not run (rubric.md 4/D2).")

    return ProductResult(npr.get("product_id"),
                         _title_of(npr), classification, ledger.seal())


def _title_of(npr):
    # type: (dict) -> Optional[str]
    node = (npr.get("identity") or {}).get("title") or {}
    value = node.get("value")
    return value if isinstance(value, str) else None


def run_result(result, override=None):
    # type: (Any, Optional[str]) -> List[ProductResult]
    """Run every product of a `NormalizationResult`."""
    return [run_product(npr, result.source, override) for npr in result.products]
