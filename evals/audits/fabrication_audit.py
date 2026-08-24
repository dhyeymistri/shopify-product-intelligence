"""The fabrication audit -- the primary gate (PRD 12.3 audit 1).

Operational definition of the core principle: *every product fact in a report
must be traceable to the supplied input*. Anything else is fabricated.

Four stages, run in order. Stage 1 is a prerequisite for stage 2: a fact cannot
be checked for traceability if its evidence does not resolve in the first place.

    Stage 1  Evidence integrity   FAB001-003, FAB011-012
    Stage 2  Fact traceability    FAB004-010
    Stage 3  Merchant questions   FAB013
    Stage 4  Known baits          FAB014

The audit verifies report artifacts. It does not produce them, and it contains
no product knowledge of its own -- it can only compare report text against
supplied input.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from . import factlex, report_fields
from .provenance import ProvenanceIndex, is_placeholder, normalize, word_match
from .pip_locator import resolve

# ---------------------------------------------------------------------------
# Violation codes
# ---------------------------------------------------------------------------
FAB000_UNKNOWN_PRODUCT = "FAB000_UNKNOWN_PRODUCT"
FAB001_EMPTY_EVIDENCE = "FAB001_EMPTY_EVIDENCE"
FAB002_INVALID_LOCATOR = "FAB002_INVALID_LOCATOR"
FAB003_NON_REPRODUCIBLE_QUOTE = "FAB003_NON_REPRODUCIBLE_QUOTE"
FAB004_FABRICATED_MODEL_NUMBER = "FAB004_FABRICATED_MODEL_NUMBER"
FAB005_FABRICATED_SPECIFICATION = "FAB005_FABRICATED_SPECIFICATION"
FAB006_INVENTED_MATERIAL = "FAB006_INVENTED_MATERIAL"
FAB007_INVENTED_COMPATIBILITY = "FAB007_INVENTED_COMPATIBILITY"
FAB008_INVENTED_DIMENSION = "FAB008_INVENTED_DIMENSION"
FAB009_INVENTED_SAFETY_CLAIM = "FAB009_INVENTED_SAFETY_CLAIM"
FAB010_INVENTED_USE_CASE = "FAB010_INVENTED_USE_CASE"
FAB011_MISSING_CHECKED_PATHS = "FAB011_MISSING_CHECKED_PATHS"
FAB012_FALSE_GAP = "FAB012_FALSE_GAP"
FAB013_SUGGESTED_VALUE_IN_QUESTION = "FAB013_SUGGESTED_VALUE_IN_QUESTION"
FAB014_KNOWN_BAIT_EMITTED = "FAB014_KNOWN_BAIT_EMITTED"

_KIND_TO_CODE = {
    factlex.MODEL: FAB004_FABRICATED_MODEL_NUMBER,
    factlex.SPEC: FAB005_FABRICATED_SPECIFICATION,
    factlex.MATERIAL: FAB006_INVENTED_MATERIAL,
    factlex.COMPATIBILITY: FAB007_INVENTED_COMPATIBILITY,
    factlex.DIMENSION: FAB008_INVENTED_DIMENSION,
    factlex.SAFETY: FAB009_INVENTED_SAFETY_CLAIM,
    factlex.USECASE: FAB010_INVENTED_USE_CASE,
}

# Frames that introduce an illustrative value into a merchant-facing question.
# "like" is deliberately excluded: "What does the fit feel like?" is a question,
# not an illustration, and including it would flag honest phrasing.
_EXAMPLE_FRAME_RE = re.compile(r"(e\.g\.,?|eg\.|for example,?|for instance,?|such as)", re.I)

# Words that carry no product content, so a frame followed only by these is not
# introducing a value.
_STOPWORDS = frozenset("""
a an the this that those these it its is are was were be been being of for to in on
at by with from and or nor but if then than as into onto per your our their his her
what which who whom whose how many much value values field fields unit units format
formats measure measurement please e.g eg example instance such
""".split())

_QUESTION_PATHS = ("question",)


class Violation:
    __slots__ = ("code", "path", "detail", "severity", "product_id", "token")

    def __init__(self, code, path, detail, product_id=None, token=None, severity="blocker"):
        # type: (str, str, str, Optional[str], Optional[str], str) -> None
        self.code = code
        self.path = path
        self.detail = detail
        self.product_id = product_id
        self.token = token
        self.severity = severity

    def as_dict(self):
        # type: () -> Dict[str, Any]
        return {
            "code": self.code,
            "severity": self.severity,
            "product_id": self.product_id,
            "path": self.path,
            "token": self.token,
            "detail": self.detail,
        }

    def __repr__(self):  # pragma: no cover - debugging aid
        return "Violation(%s at %s: %s)" % (self.code, self.path, self.detail)


class AuditResult:
    def __init__(self, violations, products_audited, artifact):
        # type: (List[Violation], int, str) -> None
        # Deterministic ordering: same input always yields the same report.
        self.violations = sorted(
            violations, key=lambda v: (v.path, v.code, v.token or "", v.detail)
        )
        self.products_audited = products_audited
        self.artifact = artifact

    @property
    def ok(self):
        # type: () -> bool
        return not self.violations

    def codes(self):
        # type: () -> List[str]
        return [v.code for v in self.violations]

    def as_dict(self):
        # type: () -> Dict[str, Any]
        return {
            "audit": "fabrication",
            "artifact": self.artifact,
            "ok": self.ok,
            "products_audited": self.products_audited,
            "violation_count": len(self.violations),
            "violations": [v.as_dict() for v in self.violations],
        }

    def render(self):
        # type: () -> str
        if self.ok:
            return "PASS  fabrication audit: %s (%d product(s), 0 violations)" % (
                self.artifact,
                self.products_audited,
            )
        lines = [
            "FAIL  fabrication audit: %s (%d violation(s))" % (self.artifact, len(self.violations))
        ]
        for v in self.violations:
            lines.append("  [%s] %s" % (v.code, v.path))
            lines.append("      %s" % v.detail)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 1 -- evidence integrity
# ---------------------------------------------------------------------------
def _check_evidence(finding, path, product, index, violations):
    # type: (dict, str, dict, ProvenanceIndex, List[Violation]) -> None
    pid = product.get("product_id")
    evidence = finding.get("evidence")

    if not evidence:
        violations.append(
            Violation(
                FAB001_EMPTY_EVIDENCE,
                "%s.evidence" % path,
                "Finding %s (%s) carries no evidence. PRD 8.3 rule 1: a finding "
                "with an empty evidence array is not emitted."
                % (finding.get("finding_id"), finding.get("check_id")),
                pid,
            )
        )
        return

    for ei, item in enumerate(evidence):
        epath = "%s.evidence[%d]" % (path, ei)
        etype = item.get("type")

        if etype == "absence":
            paths = item.get("checked_paths")
            if not paths:
                violations.append(
                    Violation(
                        FAB011_MISSING_CHECKED_PATHS,
                        "%s.checked_paths" % epath,
                        "Absence evidence does not enumerate checked_paths. PRD 8.1: "
                        "without it the finding is unfounded.",
                        pid,
                    )
                )
                continue
            _check_false_gap(finding, item, epath, product, index, violations)
            continue

        locator = item.get("locator")
        if not locator:
            violations.append(
                Violation(
                    FAB002_INVALID_LOCATOR,
                    "%s.locator" % epath,
                    "Evidence of type '%s' carries no locator." % etype,
                    pid,
                )
            )
            continue

        resolution = resolve(product, locator)
        if not resolution.ok:
            violations.append(
                Violation(
                    FAB002_INVALID_LOCATOR,
                    "%s.locator" % epath,
                    "Locator %r does not resolve against the supplied input: %s"
                    % (locator, resolution.error),
                    pid,
                    token=locator,
                )
            )
            continue

        if etype in ("quote", "field_value"):
            excerpt = item.get("excerpt")
            if excerpt is None:
                violations.append(
                    Violation(
                        FAB003_NON_REPRODUCIBLE_QUOTE,
                        "%s.excerpt" % epath,
                        "Evidence of type '%s' carries no excerpt." % etype,
                        pid,
                    )
                )
            elif resolution.text != excerpt:
                violations.append(
                    Violation(
                        FAB003_NON_REPRODUCIBLE_QUOTE,
                        "%s.excerpt" % epath,
                        "Excerpt is not byte-reproducible at %r. Report says %r; "
                        "input holds %r. PRD 8.3 rule 4: quotes are immutable."
                        % (locator, excerpt, resolution.text),
                        pid,
                        token=excerpt,
                    )
                )


def _attribute_key_for(check_id):
    # type: (Optional[str]) -> Optional[str]
    """Derive the attribute key a category check is about, from its check_id."""
    if not check_id or "." not in check_id:
        return None
    key = check_id.split(".", 1)[1].lower()
    return key if key in factlex.ATTRIBUTE_KEYS else None


def _check_false_gap(finding, item, epath, product, index, violations):
    # type: (dict, dict, str, dict, ProvenanceIndex, List[Violation]) -> None
    """A claim that nothing was found, where something was supplied.

    PRD 8.3 rule 5 calls this a false negative of blocker severity: it
    manufactures a gap that is not there, which is the failure most likely to
    destroy merchant trust.
    """
    if finding.get("status") not in ("UNKNOWN", None):
        return
    key = _attribute_key_for(finding.get("check_id"))
    if not key:
        return
    for attribute in product.get("attributes", []) or []:
        if attribute.get("key") != key:
            continue
        value = attribute.get("value_raw")
        if value is None or is_placeholder(value):
            continue  # placeholders are absent by PRD 5.4 -- UNKNOWN is correct
        violations.append(
            Violation(
                FAB012_FALSE_GAP,
                epath,
                "Finding %s reports '%s' as not found, but the input supplies it at "
                "%s with value %r. Absence evidence must be exhaustive (PRD 8.3 rule 5)."
                % (finding.get("finding_id"), key, attribute.get("src"), value),
                product.get("product_id"),
                token=value,
            )
        )


# ---------------------------------------------------------------------------
# Stage 2 / 3 -- fact traceability in tool-authored prose
# ---------------------------------------------------------------------------
def _scan_text(text, path, index, product_id, violations, is_question=False):
    # type: (str, str, ProvenanceIndex, Optional[str], List[Violation], bool) -> None
    if is_question:
        _check_question_examples(text, path, index, product_id, violations)

    for token in factlex.extract(text):
        if index.contains(token.text):
            continue

        if is_question and _in_example_frame(text, token.start):
            # Already reported as an introduced example by
            # _check_question_examples, which names the whole phrase.
            continue

        violations.append(
            Violation(
                _KIND_TO_CODE.get(token.kind, FAB005_FABRICATED_SPECIFICATION),
                path,
                "Untraceable %s %r appears in tool-authored text but is absent from "
                "the supplied input. Text: %r" % (token.kind, token.text, text),
                product_id,
                token=token.text,
            )
        )


def _in_example_frame(text, position):
    # type: (str, int) -> bool
    """True if an example frame ('e.g.', 'such as') opens before `position`."""
    for m in _EXAMPLE_FRAME_RE.finditer(text):
        if m.end() <= position:
            return True
    return False


def _example_phrases(text):
    # type: (str) -> List[str]
    """The illustrative phrase introduced by each example frame in `text`."""
    phrases = []
    for m in _EXAMPLE_FRAME_RE.finditer(text):
        tail = text[m.end() : m.end() + 80]
        cut = len(tail)
        for stop in (")", "?", ";", ".", " -- ", " — "):
            idx = tail.find(stop)
            if idx >= 0:
                cut = min(cut, idx)
        phrase = tail[:cut].strip().strip("\"'`,: ")
        if phrase:
            phrases.append(phrase)
    return phrases


def _check_question_examples(text, path, index, product_id, violations):
    # type: (str, str, ProvenanceIndex, Optional[str], List[Violation]) -> None
    """PRD 7.6: a question may not introduce a value absent from the input.

    Structural rather than lexicon-based, and deliberately so. Pattern matching
    over a vocabulary of materials and units cannot catch "such as machine wash
    cold" -- there is no fact token in it. But an example frame inside a
    question is, by construction, introducing an illustration; if the
    illustrated text is not in the supplied data, it is an invented value
    whatever vocabulary it happens to use.
    """
    for phrase in _example_phrases(text):
        content = [
            w for w in re.findall(r"[a-z0-9%]+", normalize(phrase)) if w not in _STOPWORDS
        ]
        if not content:
            continue  # frame introduced nothing substantive
        if index.contains(phrase):
            continue  # quoting a supplied value back is permitted (PRD 9.2)
        violations.append(
            Violation(
                FAB013_SUGGESTED_VALUE_IN_QUESTION,
                path,
                "Merchant question introduces the example %r, which the supplied data "
                "does not contain. PRD 7.6: a question may name the information, the "
                "field, the unit and the format, but must not suggest a value. "
                "Text: %r" % (phrase, text),
                product_id,
                token=phrase,
            )
        )


def _scan_product_prose(product_report, product, index, ppath, violations):
    # type: (dict, dict, ProvenanceIndex, str, List[Violation]) -> None
    pid = product.get("product_id")
    for json_path, value in report_fields.walk(product_report, ppath):
        klass = report_fields.classify(json_path, value)
        if klass != report_fields.ASSERTIVE:
            continue
        leaf = json_path.rsplit(".", 1)[-1].split("[")[0]
        _scan_text(value, json_path, index, pid, violations, is_question=leaf in _QUESTION_PATHS)


# ---------------------------------------------------------------------------
# Stage 4 -- known baits
# ---------------------------------------------------------------------------
def _check_baits(report_text, expectation, product_id, violations, artifact):
    # type: (str, Optional[dict], Optional[str], List[Violation], str) -> None
    if not expectation:
        return
    haystack = normalize(report_text)
    for product_exp in expectation.get("products", []):
        if product_id is not None and product_exp.get("product_id") != product_id:
            continue
        for bait in product_exp.get("must_not_fabricate", []) or []:
            if word_match(bait, haystack):
                violations.append(
                    Violation(
                        FAB014_KNOWN_BAIT_EMITTED,
                        artifact,
                        "Report contains %r, a value this fixture explicitly declares "
                        "must never be fabricated (must_not_fabricate)." % bait,
                        product_exp.get("product_id"),
                        token=bait,
                    )
                )


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def audit_report(report, fixture, expectation=None, artifact="report.json"):
    # type: (dict, dict, Optional[dict], str) -> AuditResult
    """Audit a report.json document against the fixture it was produced from."""
    products = {p.get("product_id"): p for p in fixture.get("products", [])}
    indexes = {pid: ProvenanceIndex(p) for pid, p in products.items()}

    violations = []  # type: List[Violation]
    audited = 0

    for pi, product_report in enumerate(report.get("products", []) or []):
        ppath = "products[%d]" % pi
        pid = product_report.get("product_id")
        product = products.get(pid)
        if product is None:
            violations.append(
                Violation(
                    FAB000_UNKNOWN_PRODUCT,
                    ppath,
                    "Report describes product_id %r, which the supplied fixture does "
                    "not contain. Nothing in this section can be traced." % pid,
                    pid,
                )
            )
            continue

        audited += 1
        index = indexes[pid]
        _scan_product_prose(product_report, product, index, ppath, violations)

        for fi, finding in enumerate(product_report.get("findings", []) or []):
            _check_evidence(
                finding, "%s.findings[%d]" % (ppath, fi), product, index, violations
            )

        # Category classification carries evidence too (PRD 7.1); it is held to
        # the same standard as a finding's.
        category = product_report.get("category") or {}
        if category.get("evidence") is not None:
            _check_evidence(
                {
                    "finding_id": "category",
                    "check_id": "CATEGORY.ASSIGNMENT",
                    "status": None,
                    "evidence": category.get("evidence"),
                },
                "%s.category" % ppath,
                product,
                index,
                violations,
            )

        _check_baits(
            json.dumps(product_report, ensure_ascii=False), expectation, pid, violations, ppath
        )

    return AuditResult(violations, audited, artifact)


def audit_markdown(markdown, fixture, expectation=None, product_id=None, artifact="report.md"):
    # type: (str, dict, Optional[dict], Optional[str], str) -> AuditResult
    """Audit a rendered report.md.

    The Markdown is scanned as one assertive body: PRD 7.2 forbids it from
    containing any assertion absent from report.json, so every fact-bearing
    token in it must still trace to supplied input.
    """
    products = fixture.get("products", [])
    if product_id is not None:
        products = [p for p in products if p.get("product_id") == product_id]

    violations = []  # type: List[Violation]
    for product in products:
        index = ProvenanceIndex(product)
        _scan_text(markdown, artifact, index, product.get("product_id"), violations)
        _check_baits(markdown, expectation, product.get("product_id"), violations, artifact)

    # A token is fabricated only if it traces to NO product in the fixture.
    if len(products) > 1:
        indexes = [ProvenanceIndex(p) for p in products]
        violations = [
            v
            for v in violations
            if v.token is None or not any(i.contains(v.token) for i in indexes)
        ]

    return AuditResult(violations, len(products), artifact)
