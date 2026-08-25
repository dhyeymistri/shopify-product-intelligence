"""The finding contract: PRD 7.3 and 8.1, and nothing besides.

This module is deliberately close to the specification. Every field of
``Finding`` is a field PRD 7.3 names, every field of ``Evidence`` is a field
PRD 8.1 names, and no field has been added for the engine's convenience --
a report is read by a merchant and audited by tooling that was written against
the PRD, so a helpful extra key is a divergence, not a feature.

Two rules are enforced here rather than left to callers:

1. **No evidence, no finding.** ``FindingLedger.add`` drops a finding with an
   empty ``evidence`` array and records a run error (PRD 8.3 rule 1, D-014).
   The gate lives where findings are made, not only where they are rendered:
   a gate that only exists at render time is not structural for this layer.
2. **Absence enumerates where it looked.** An ``absence`` item without
   ``checked_paths`` cannot be constructed (PRD 8.1); the constructor refuses.

Finding ids are assigned after a deterministic sort, never in insertion order,
so the same input yields byte-identical ids however the checks are scheduled.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from . import rubric_data as R

QUOTE, FIELD_VALUE, ABSENCE, DERIVED, EXTERNAL_REFERENCE = (
    "quote", "field_value", "absence", "derived", "external_reference")
EVIDENCE_TYPES = (QUOTE, FIELD_VALUE, ABSENCE, DERIVED, EXTERNAL_REFERENCE)

REMEDIATION_QUESTION, REMEDIATION_CORRECTION, REMEDIATION_STRUCTURE = (
    "question", "correction", "structure")

#: PRD 9.1 fixes the language for an unknown. It is a constant, not a template
#: parameter: every report says this and no report says anything stronger.
NOT_STATED = "Not stated in the supplied data."

#: PRD 7.3's remediation note, verbatim. The one sentence that keeps a question
#: a question (D-005).
DO_NOT_GENERATE = ("Do not generate a value. This must be supplied by the "
                   "merchant or supplier.")


class EvidenceError(Exception):
    """Raised when an evidence item cannot be constructed as specified."""


class Evidence(object):
    """One evidence item (PRD 8.1)."""

    __slots__ = ("type", "locator", "excerpt", "checked_paths", "note")

    def __init__(self, type, locator=None, excerpt=None, checked_paths=None,
                 note=None):
        # type: (str, Optional[str], Optional[str], Optional[Tuple[str, ...]], Optional[str]) -> None
        if type not in EVIDENCE_TYPES:
            raise EvidenceError("unknown evidence type %r" % (type,))
        if type == ABSENCE:
            if not checked_paths:
                raise EvidenceError(
                    "absence evidence must enumerate checked_paths (PRD 8.1)")
            if locator is not None or excerpt is not None:
                raise EvidenceError("absence evidence carries no locator or excerpt")
        else:
            if not locator:
                raise EvidenceError("%s evidence needs a locator" % type)
            if type in (QUOTE, FIELD_VALUE) and excerpt is None:
                raise EvidenceError("%s evidence needs an excerpt" % type)
        self.type = type
        self.locator = locator
        self.excerpt = excerpt
        self.checked_paths = tuple(checked_paths) if checked_paths else None
        self.note = note

    def as_dict(self):
        # type: () -> Dict[str, Any]
        return {
            "type": self.type,
            "locator": self.locator,
            "excerpt": self.excerpt,
            "checked_paths": list(self.checked_paths) if self.checked_paths else None,
            "note": self.note,
        }


class Remediation(object):
    """A merchant-facing ask (PRD 7.3, bound by PRD 7.6).

    The question is never composed here from anything except a registry string
    and verified evidence excerpts. That is the whole mechanism by which a
    remediation cannot introduce a value the supplied data does not hold.
    """

    __slots__ = ("type", "question", "target_field", "note")

    def __init__(self, type, question, target_field, note=DO_NOT_GENERATE):
        self.type = type
        self.question = question
        self.target_field = target_field
        self.note = note

    def as_dict(self):
        return {"type": self.type, "question": self.question,
                "target_field": self.target_field, "note": self.note}


class Finding(object):
    """One finding (PRD 7.3). ``finding_id`` is assigned by the ledger."""

    __slots__ = ("check_id", "dimension", "scope_level", "scope_ref", "status",
                 "severity", "confidence", "title", "detail", "evidence",
                 "earned", "max_points", "penalty", "remediation", "finding_id",
                 "confidence_arm")

    def __init__(self, check_id, dimension, status, severity, confidence, title,
                 detail, evidence, earned, max_points, penalty,
                 scope_level="product", scope_ref=None, remediation=None,
                 confidence_arm="structural"):
        # type: (...) -> None
        self.check_id = check_id
        self.dimension = dimension
        self.scope_level = scope_level
        self.scope_ref = scope_ref
        self.status = status
        self.severity = severity
        self.confidence = confidence
        self.title = title
        self.detail = detail
        self.evidence = list(evidence)
        self.earned = earned            # Decimal
        self.max_points = max_points    # Decimal
        self.penalty = penalty          # Decimal
        self.remediation = remediation
        self.finding_id = None          # type: Optional[str]
        #: Which of D-020's two arms produced `confidence`, serialized as
        #: `determination`. PRD 9.5 requires an *(interpreted)* tag in the
        #: Markdown report, and P4 cannot render one from a field that does
        #: not exist; the confidence value alone cannot carry it, because a
        #: `low` check reports `low` on both arms (D-020, D-026).
        self.confidence_arm = confidence_arm

    # -- serialization ---------------------------------------------------
    def as_dict(self, quantize=True):
        # type: (bool) -> Dict[str, Any]
        """PRD 7.3's object. Points are rendered at 2dp (`rubric.md` 6.2)."""
        def points(value):
            if not quantize:
                return float(value)
            return float(value.quantize(Decimal("0.01")))

        return {
            "finding_id": self.finding_id,
            "check_id": self.check_id,
            "dimension": self.dimension,
            "scope": {"level": self.scope_level, "ref": self.scope_ref},
            "status": self.status,
            "severity": self.severity,
            "confidence": self.confidence,
            "determination": self.confidence_arm,
            "title": self.title,
            "detail": self.detail,
            "evidence": [e.as_dict() for e in self.evidence],
            "points": {"earned": points(self.earned),
                       "max": points(self.max_points),
                       "penalty": points(self.penalty)},
            "remediation": self.remediation.as_dict() if self.remediation else None,
        }


class FindingLedger(object):
    """The findings for one product, plus the gate every finding passes.

    Deliberately not a scorer. It holds points because a finding holds points
    (PRD 7.3), and it ranks questions by points recoverable because D-016 says
    that is the ranking -- but it computes no total, no dimension subtotal and
    no grade. Score aggregation is a later phase.
    """

    def __init__(self, product_id):
        # type: (str) -> None
        self.product_id = product_id
        self.findings = []      # type: List[Finding]
        self.run_errors = []    # type: List[Dict[str, str]]
        self.deferred = []      # type: List[Dict[str, str]]
        self._sealed = False

    # -- the gate --------------------------------------------------------
    def add(self, finding):
        # type: (Finding) -> bool
        """Admit a finding, or drop it and log why (PRD 8.3 rule 1)."""
        if not finding.evidence:
            self.run_errors.append({
                "code": "CHECK.EVIDENCE_GATE",
                "record": "%s / %s" % (self.product_id, finding.check_id),
                "reason": ("Finding carries no evidence and was dropped. "
                           "PRD 8.3 rule 1: no evidence, no finding."),
            })
            return False
        for item in finding.evidence:
            if item.type == ABSENCE and not item.checked_paths:
                self.run_errors.append({
                    "code": "CHECK.EVIDENCE_GATE",
                    "record": "%s / %s" % (self.product_id, finding.check_id),
                    "reason": ("Absence evidence does not enumerate checked_paths "
                               "and the finding was dropped (PRD 8.1)."),
                })
                return False
        self.findings.append(finding)
        return True

    def defer(self, check_id, reason):
        # type: (str, str) -> None
        """Record a check that ran but could not conclude in this phase.

        A deferred check emits no finding at all. That is the point: a check
        that cannot decide deterministically must say nothing about the
        product rather than guess in either direction.
        """
        self.deferred.append({"check_id": check_id, "reason": reason})

    def error(self, code, reason, record=None):
        # type: (str, str, Optional[str]) -> None
        self.run_errors.append({"code": code,
                                "record": record or self.product_id,
                                "reason": reason})

    # -- ordering --------------------------------------------------------
    def seal(self):
        # type: () -> FindingLedger
        """Sort deterministically and assign ``finding_id``s.

        Insertion order is whatever order the runner happened to schedule
        checks in; a report that changes when a check moves is not
        reproducible (PRD 11.3, AC-Q1). The sort key is fixed and total.
        """
        order = dict((d, i) for i, d in enumerate(R.DIMENSION_ORDER))
        self.findings.sort(key=lambda f: (
            order.get(f.dimension, 99), f.check_id, f.scope_level,
            f.scope_ref or "", f.status))
        for index, finding in enumerate(self.findings, start=1):
            finding.finding_id = "F-%04d" % index
        self.deferred.sort(key=lambda d: d["check_id"])
        self._sealed = True
        return self

    # -- derived report members -----------------------------------------
    def unknowns(self):
        # type: () -> List[Dict[str, Any]]
        """PRD 7.1 `unknowns[]`: one entry per UNKNOWN finding.

        The `checked_paths` are the same tuple the search used and the
        question is the same registry string the remediation used, so the two
        cannot drift apart.
        """
        out = []
        for finding in self.findings:
            if finding.status != R.UNKNOWN:
                continue
            paths = []
            for item in finding.evidence:
                if item.type == ABSENCE and item.checked_paths:
                    paths = list(item.checked_paths)
                    break
            out.append({
                "attribute": _attribute_label(finding.check_id),
                "checked_paths": paths,
                "question": finding.remediation.question if finding.remediation else None,
            })
        return out

    def questions_for_merchant(self):
        # type: () -> List[Dict[str, Any]]
        """Ranked by points recoverable (D-016), blockers pinned to the top.

        `unlocks_points` is the points this one finding puts back: the earned
        points it forfeits plus the penalty it costs. It is a per-finding
        figure, not a score, and nothing here aggregates one.
        """
        rows = []
        for finding in self.findings:
            if not finding.remediation:
                continue
            recoverable = (finding.max_points - finding.earned) + finding.penalty
            rows.append((0 if finding.severity == "blocker" else 1,
                         -recoverable, finding.check_id, finding, recoverable))
        rows.sort(key=lambda r: (r[0], r[1], r[2]))
        out = []
        for priority, (_, _, _, finding, recoverable) in enumerate(rows, start=1):
            out.append({
                "priority": priority,
                "question": finding.remediation.question,
                "unlocks_points": float(recoverable.quantize(Decimal("0.01"))),
                "related_findings": [finding.finding_id],
            })
        return out

    def as_dict(self):
        # type: () -> Dict[str, Any]
        if not self._sealed:
            self.seal()
        return {
            "product_id": self.product_id,
            "findings": [f.as_dict() for f in self.findings],
            "unknowns": self.unknowns(),
            "questions_for_merchant": self.questions_for_merchant(),
        }


def _attribute_label(check_id):
    # type: (str) -> str
    """The attribute an `unknowns[]` row is about: the check_id's own suffix.

    A controlled label taken from the id, never a phrase written about the
    product.
    """
    return check_id.split(".", 1)[1].lower() if "." in check_id else check_id
