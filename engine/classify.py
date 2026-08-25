"""Assign one of the five categories, or none, and show the working.

`taxonomy.md` 2 orders the signals and fixes the confidence each one carries.
This module implements that order literally: the first tier that produces a
match wins, and a tier whose signals disagree produces `uncategorized` rather
than a tie-break. Nothing here guesses, and nothing here writes a value into
`attributes[]` (`taxonomy.md` 2 rule 2).

Classification is inference (PRD 9.5 site 1), so it is labelled with its
`method` and `confidence` and it carries evidence held to the same standard as
a finding's -- the fabrication audit already audits the category block that
way, which is the correct standard rather than an optional courtesy.

Matching is case-insensitive containment of a `taxonomy.md` 8 term in the
signal string, and **row order resolves several matches within one signal**:
that is the mechanism the activewear note already relies on ("the mapping table
is evaluated in the order above, so `apparel` wins"). Disagreement *between two
distinct signals of the same tier* is a different thing, and yields
`uncategorized` (`taxonomy.md` 2 rule 1).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .findings import EvidenceError
from .taxonomy_data import CATEGORY_MAP, UNCATEGORIZED

OPERATOR_OVERRIDE = "operator_override"
DECLARED_CATEGORY_MAP = "declared_category_map"
PRODUCT_TYPE_MAP = "product_type_map"
TAG_MAP = "tag_map"
TITLE_INFERENCE = "title_inference"

#: taxonomy.md 2 -- the signal tiers, in resolution order, with the confidence
#: each carries. The tuple order is normative.
METHOD_CONFIDENCE = (
    (OPERATOR_OVERRIDE, "high"),
    (DECLARED_CATEGORY_MAP, "high"),
    (PRODUCT_TYPE_MAP, "medium"),
    (TAG_MAP, "medium"),
    (TITLE_INFERENCE, "low"),
)

#: The NPR paths each tier reads. Doubles as the `checked_paths` of the
#: absence evidence an `uncategorized` assignment carries.
SIGNAL_PATHS = {
    DECLARED_CATEGORY_MAP: ("identity.declared_category",),
    PRODUCT_TYPE_MAP: ("identity.product_type",),
    TAG_MAP: ("tags[*]",),
    TITLE_INFERENCE: ("identity.title", "narrative.description_text"),
}
ALL_SIGNAL_PATHS = ("identity.declared_category", "identity.product_type",
                    "tags[*]", "identity.title", "narrative.description_text")


class Match(object):
    """A mapping term found in a signal, with the span it was found at."""

    __slots__ = ("category", "term", "locator", "start", "end")

    def __init__(self, category, term, locator, start, end):
        self.category = category
        self.term = term
        self.locator = locator
        self.start = start
        self.end = end


class Classification(object):
    __slots__ = ("assigned", "method", "confidence", "evidence", "note")

    def __init__(self, assigned, method, confidence, evidence, note=None):
        self.assigned = assigned
        self.method = method
        self.confidence = confidence
        self.evidence = evidence
        self.note = note

    def as_dict(self):
        # type: () -> Dict[str, Any]
        """The category block of PRD 7.1.

        `note` is serialized when there is one. `taxonomy.md` 2 rule 1 requires
        a same-tier disagreement to be *reported*, naming both signals; this
        class already recorded it and the serialization dropped it, so the
        statement never reached the block a reader sees. Q-11 stands open on
        whether that belongs on a `CATEGORY.*` finding instead, and emitting
        the note here settles nothing about that: it carries no check_id, no
        points, no severity and no confidence of its own, and the two signals
        it refers to are the evidence items already beside it.
        """
        out = {"assigned": self.assigned, "method": self.method,
               "confidence": self.confidence,
               "evidence": [e.as_dict() for e in self.evidence]}
        if self.note:
            out["note"] = self.note
        return out


def _match_in(text, locator):
    # type: (str, str) -> Optional[Match]
    """The first mapping row whose term appears in `text`.

    Row order decides, and within a row the earliest occurrence in the text
    decides, so the result does not depend on the term list's internal order.
    """
    lowered = text.lower()
    for category, terms in CATEGORY_MAP:
        best = None  # type: Optional[Tuple[int, str]]
        for term in terms:
            index = lowered.find(term)
            if index >= 0 and (best is None or index < best[0]):
                best = (index, term)
        if best is not None:
            index, term = best
            return Match(category, term, locator, index, index + len(term))
    return None


def _signals(npr, tier):
    # type: (dict, str) -> List[Tuple[str, str]]
    """(text, locator) for every signal this tier reads."""
    identity = npr.get("identity") or {}
    narrative = npr.get("narrative") or {}

    def pair(node, locator):
        if isinstance(node, dict) and isinstance(node.get("value"), str) \
                and node["value"].strip():
            return [(node["value"], node.get("src") or locator)]
        return []

    if tier == DECLARED_CATEGORY_MAP:
        return pair(identity.get("declared_category"), "identity.declared_category")
    if tier == PRODUCT_TYPE_MAP:
        return pair(identity.get("product_type"), "identity.product_type")
    if tier == TAG_MAP:
        out = []
        for index, tag in enumerate(npr.get("tags") or []):
            out.extend(pair(tag, "tags[%d].value" % index))
        return out
    if tier == TITLE_INFERENCE:
        return (pair(identity.get("title"), "identity.title")
                + pair(narrative.get("description_text"),
                       "narrative.description_text"))
    return []


def classify(npr, builder, override=None):
    # type: (dict, Any, Optional[str]) -> Classification
    """Assign a category to one NPR.

    `override` is the operator's explicit choice (`taxonomy.md` 2 order 1). It
    is evidenced as an absence over the signal paths, because the input is not
    where it came from and pretending otherwise would be a fabricated locator.
    """
    if override:
        evidence = [builder.absence(
            ALL_SIGNAL_PATHS,
            note="Category supplied at invocation by the operator (interpreted).")]
        return Classification(override, OPERATOR_OVERRIDE, "high", evidence)

    for method, confidence in METHOD_CONFIDENCE[1:]:
        matches = []  # type: List[Match]
        for text, locator in _signals(npr, method):
            match = _match_in(text, locator)
            if match is not None:
                matches.append(match)
        if not matches:
            continue

        categories = sorted(set(m.category for m in matches))
        if len(categories) > 1:
            # taxonomy.md 2 rule 1: same-tier disagreement is not tie-broken.
            evidence = _evidence_for(builder, matches)
            return Classification(
                UNCATEGORIZED, UNCATEGORIZED, "low", evidence,
                note="Two signals of the same tier map to different categories "
                     "(interpreted). Both are quoted in the evidence.")

        evidence = _evidence_for(builder, matches[:1])
        if not evidence:
            continue
        return Classification(categories[0], method, confidence, evidence)

    evidence = [builder.absence(
        ALL_SIGNAL_PATHS,
        note="No category mapping term was found at any signal path.")]
    return Classification(UNCATEGORIZED, UNCATEGORIZED, "low", evidence)


def _evidence_for(builder, matches):
    # type: (Any, List[Match]) -> List[Any]
    """Quote the matched term itself, at a verified span of the signal.

    The span is the smallest honest citation: it shows the reader the exact
    text that drove the assignment, and it resolves back to the input.
    """
    out = []
    for match in matches:
        note = "Category inferred from a mapping term in the supplied data "\
               "(interpreted)."
        try:
            out.append(builder.span(match.locator, match.start, match.end, note))
        except EvidenceError:
            try:
                out.append(builder.quote(match.locator, note))
            except EvidenceError:
                continue
    return out
