"""Deterministic check execution against the canonical record.

Every function here decides a **status** and produces **evidence**, and does
nothing else. It does not choose points, severity, confidence or wording; those
come from the registry. It does not read the world; the only thing it may look
at is the NPR and the source the NPR came from.

The line this module is built around is `rubric.md` 3.1's:

> `FAIL` requires something present to be wrong. If nothing is present, it is
> `UNKNOWN`. A check that emits `FAIL` on absence is a spec violation.

So every code path capable of emitting `FAIL` takes a non-empty list of
supplied values as a required argument. Absence reaches `UNKNOWN` and nothing
else, and `UNKNOWN` earns zero and costs zero (D-003).

**Deferral.** A check whose satisfaction needs language recognition over prose
does not guess. It determines absence and conflict structurally -- both of
which are exact -- and, where something is present that it cannot read, emits
no finding at all and records the deferral. Under-recognition can only deflate
a score while carrying honest evidence; a guess in either direction can state
something false about a product. Only one of those is recoverable.

**No winner is ever chosen.** A conflict produces two evidence items, one per
location, and a question that quotes both back. The tool has no rule that
prefers a metafield to a description or the longer value to the shorter.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from . import facts
from . import lexicon
from . import registry
from . import rubric_data as R
from . import taxonomy_data as T
from .findings import (DO_NOT_GENERATE, NOT_STATED, Evidence, EvidenceError,
                       Finding, Remediation, REMEDIATION_CORRECTION,
                       REMEDIATION_QUESTION, REMEDIATION_STRUCTURE)

ZERO = Decimal("0")

#: rubric.md 4/D6: numeric values within this tolerance are not a conflict.
NUMERIC_TOLERANCE = Decimal("0.02")

#: One magnitude followed by one unit, where the unit may be written as several
#: tokens ("1.7 fl oz", "12 fl. oz."). The unit group deliberately excludes
#: digits, so a dimension triple ("2 x 3 cm") does not parse as a number with a
#: unit and falls through to the categorical branch instead.
_NUMBER_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([^0-9]*)$")
_WS_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _norm(text):
    # type: (str) -> str
    return _WS_RE.sub(" ", text.strip().lower())


def _numeric(text):
    # type: (str) -> Optional[Tuple[Decimal, str]]
    """(magnitude, unit) when the whole value is one number with one unit.

    The unit is compared as written, with whitespace and full stops removed so
    that "fl oz", "fl. oz." and "floz" are recognized as the same spelling of
    the same unit. That is a formatting normalization, not a conversion: no
    table here says a millilitre relates to a fluid ounce, and none may. Two
    values in units this function reports as different are simply not
    comparable, which is why `_conflict_kind` emits nothing for them.
    """
    match = _NUMBER_RE.match(text)
    if not match:
        return None
    unit = _WS_RE.sub("", match.group(2)).replace(".", "").lower()
    return Decimal(match.group(1)), unit


def _label(check):
    # type: (Any) -> str
    """The controlled label a finding's title uses. Never product text."""
    return check.attribute_key or check.check_id


def _question_remediation(check):
    # type: (Any) -> Remediation
    """The registry's question, unchanged (PRD 7.6)."""
    return Remediation(REMEDIATION_QUESTION, check.question, check.target_field(),
                       DO_NOT_GENERATE)


def _correction_remediation(check, excerpts):
    # type: (Any, List[str]) -> Remediation
    """A question built from a fixed frame and verified excerpts only.

    PRD 7.6 permits -- and PRD 9.2 requires -- quoting a supplied value back to
    the merchant. Both slots below are excerpts that were byte-verified against
    the input, so this frame cannot introduce a value the data does not hold.
    """
    quoted = " or ".join('"%s"' % e for e in excerpts)
    return Remediation(REMEDIATION_CORRECTION,
                       "Which is correct — %s?" % quoted,
                       check.target_field(), DO_NOT_GENERATE)


def _defer_for_recognition(check, ctx, verdict=None):
    # type: (Any, Any, Any) -> List[Finding]
    """A value is supplied and judging it needs recognition (D-019).

    Two reason strings, in one place, so that every path which abstains for
    the same reason is recorded identically and the deferral ledger stays a
    usable measurement of the recall gap.

    The two are kept apart because they measure different things (PRE-6).
    *No evaluator* is a coverage gap: the predicate is declared and nothing
    implements it, and writing one would close the case. *Ran and abstained*
    is the residue proper: an evaluator looked at this value and could not say.
    D-019 asks for that residue to be measured rather than assumed, and an
    undifferentiated bucket cannot measure it.

    Either way the check emits nothing. Which reason applies changes what the
    ledger records, never what the merchant sees.
    """
    if verdict is registry.UNDECIDED:
        reason = ("A value is supplied and the recognition predicate (%s) "
                  "ran and could not decide it." % check.satisfies)
    else:
        reason = ("A value is supplied, and deciding whether it satisfies "
                  "this check needs the recognition predicate (%s), which "
                  "has no evaluator in this build." % check.satisfies)
    ctx.ledger.defer(check.check_id, reason)
    return []


def _finding(check, status, evidence, earned, confidence_arm="structural",
             title=None, detail=None, scope_level=None, scope_ref=None,
             remediation=None, penalty=ZERO, severity=None, max_points=None):
    # type: (...) -> Finding
    confidence = (check.confidence.recognition_arm
                  if confidence_arm == "recognized"
                  else check.confidence.structural)
    return Finding(
        check_id=check.check_id,
        dimension=check.dimension,
        status=status,
        severity=severity or check.severity_for(status),
        confidence=confidence,
        title=title,
        detail=detail,
        evidence=evidence,
        earned=earned,
        max_points=check.max_points if max_points is None else max_points,
        penalty=penalty,
        scope_level=scope_level or check.scope,
        scope_ref=scope_ref,
        remediation=remediation,
        confidence_arm=confidence_arm,
    )


# ---------------------------------------------------------------------------
# statuses
# ---------------------------------------------------------------------------
def unknown(check, builder, gathered):
    # type: (Any, Any, Any) -> Finding
    """Nothing was found at any checked path (PRD 9.1).

    The absence evidence carries the same path tuple the search walked, and any
    placeholder found on the way is quoted beside it: a placeholder is absent
    for this check's purposes, and PRD 9.4 requires the literal to be shown
    rather than silently dropped.
    """
    evidence = [builder.absence(gathered.searched_paths)]
    for candidate in gathered.placeholders:
        try:
            evidence.append(builder.field_value(
                candidate,
                note="A placeholder occupies this field, so it states no value "
                     "(PRD 9.4)."))
        except EvidenceError:
            continue
    return _finding(
        check, R.UNKNOWN, evidence, ZERO,
        title="%s: not stated in the supplied data" % _label(check),
        detail="%s No value was found at the checked paths listed in the "
               "evidence." % NOT_STATED,
        remediation=_question_remediation(check))


def present(check, builder, candidate, note=None, recognized=False):
    # type: (Any, Any, Any, Optional[str], bool) -> Finding
    """A stated value satisfies the check.

    `recognized` selects the confidence arm (D-020). A predicate decision is
    recognition even when its mechanism is exact -- the tool read a value and
    judged its shape -- so it reports the check's `recognized` confidence, not
    the structural arm reserved for presence, absence and arithmetic.
    """
    evidence = [builder.field_value(candidate, note=note)]
    return _finding(
        check, R.PASS, evidence, check.max_points,
        confidence_arm="recognized" if recognized else "structural",
        title="%s: stated in the supplied data" % _label(check),
        detail="A value is supplied at the locator quoted in the evidence.",
        scope_level=candidate.scope, scope_ref=candidate.ref)


def ambiguous(check, builder, candidate):
    # type: (Any, Any, Any) -> Finding
    """A stated value is present and does not resolve the check (PRD 9.3).

    `rubric.md` 3.1: `PARTIAL` earns `max x partial_credit`, and the figure
    comes from the registry rather than from here. The finding asserts exactly
    one thing -- that a value is present and ambiguous -- and quotes it
    verbatim, so the assertion is checkable at its own locator. It states
    nothing about what the value *should* have been, and the remediation is
    the registry's question, which offers the axis of ambiguity without
    proposing a value (D-005).
    """
    evidence = [builder.field_value(
        candidate,
        note="A value is supplied here and it leaves the check's question "
             "open.")]
    return _finding(
        check, R.PARTIAL, evidence, check.max_points * check.partial_credit,
        confidence_arm="recognized",
        title="%s: stated, but leaves the question open" % _label(check),
        detail="A value is supplied at the locator quoted in the evidence, "
               "and it does not settle what the check asks. The supplied "
               "value is quoted rather than interpreted.",
        scope_level=candidate.scope, scope_ref=candidate.ref,
        remediation=_question_remediation(check))


def not_applicable(check, builder, reason):
    # type: (Any, Any, str) -> Finding
    """A structural trigger is absent (`taxonomy.md` 4.4).

    Never because information is missing -- that is `UNKNOWN`, and conflating
    the two is the scoring failure PRD 10.3 names as the most important to
    avoid.
    """
    evidence = [builder.absence(check.checked_paths, note=reason)]
    return _finding(
        check, R.NOT_APPLICABLE, evidence, ZERO, max_points=ZERO,
        title="%s: not applicable to this product" % _label(check),
        detail=reason)


def coverage(check, builder, covered, uncovered, note=None, unresolved=(),
             recognized=False):
    # type: (Any, Any, List[Any], List[str], Optional[str], Any, bool) -> Optional[Finding]
    """Variant coverage, scored strictly and naming what is uncovered.

    `rubric.md` 3.1 and PRD 9.7: partial coverage is `PARTIAL` at
    `covered/total`, and the evidence names the uncovered variant ids
    explicitly -- never "some variants".

    **D-021.** `covered` counts a variant only when its own value *satisfies*
    the check. `unresolved` holds the variants whose value is present and
    ambiguous: they do not count toward `covered`, they are not weighted as
    partial coverage, and they are reported by quoting the supplied value at
    its own locator rather than as an empty field. A value that is there and
    reported as a gap is the false negative PRD 8.3 rule 5 calls
    blocker-severity, so the two groups carry different evidence types on
    purpose.
    """
    unresolved = list(unresolved)
    total = len(covered) + len(uncovered) + len(unresolved)
    if not total:
        return None
    arm = "recognized" if recognized else "structural"
    evidence = []
    for candidate in covered:
        try:
            evidence.append(builder.field_value(candidate, note=note))
        except EvidenceError:
            continue
    for candidate in unresolved:
        try:
            evidence.append(builder.field_value(
                candidate,
                note="A value is supplied for this variant and it leaves the "
                     "check's question open, so the variant is not counted as "
                     "covered (D-021)."))
        except EvidenceError:
            continue
    if not evidence:
        return None
    if not uncovered and not unresolved:
        return _finding(
            check, R.PASS, evidence, check.max_points,
            confidence_arm=arm,
            title="%s: stated for every variant" % _label(check),
            detail="A value is supplied for each of the %d variants, at the "
                   "locators quoted in the evidence." % total)
    if uncovered:
        evidence.append(builder.absence(
            check.checked_paths,
            note="Checked and empty for these variants: %s."
                 % ", ".join(uncovered)))
    earned = check.max_points * Decimal(len(covered)) / Decimal(total)
    if not uncovered:
        # D-025. Every variant carries a value, so `rubric.md` 3.1's *first*
        # `PARTIAL` clause applies as well as its coverage clause: something is
        # present and ambiguous everywhere the check looked. The check takes
        # whichever clause the data supports and never less than the ambiguity
        # credit. No ambiguous variant enters the numerator -- the floor is a
        # separate clause, not a re-weighting of coverage, so D-021's rejection
        # of weighted coverage stands.
        floor = check.max_points * check.partial_credit
        if floor > earned:
            earned = floor
    detail = ("A value that answers this check is supplied for %d of the %d "
              "variants." % (len(covered), total))
    if unresolved:
        detail += (" A further %d carr%s a value that leaves the question "
                   "open; each is quoted at its own locator in the evidence."
                   % (len(unresolved), "ies" if len(unresolved) == 1 else "y"))
    if uncovered:
        detail += (" The variants no value was found for are named in the "
                   "evidence.")
    return _finding(
        check, R.PARTIAL, evidence, earned,
        confidence_arm=arm,
        title="%s: stated for some of the variants" % _label(check),
        detail=detail,
        remediation=_question_remediation(check))


# ---------------------------------------------------------------------------
# conflict (D6) -- present versus present, no winner
# ---------------------------------------------------------------------------
def _conflict_kind(values):
    # type: (List[str]) -> Optional[str]
    """Which D6 check a disagreement belongs to, or None to emit nothing.

    Conservative by design, because D6 is one of only two mechanisms that
    subtract points and `rubric.md` 4/D6 rule 4 makes under-detection the
    required failure direction:

    * two numbers in the **same** unit, differing by more than the tolerance
      -> `CONFLICT.NUMERIC`;
    * two numbers in the same unit within the tolerance -> not a conflict;
    * two numbers in **different** units -> nothing. Without a conversion the
      tool cannot tell an inconsistency from an equivalent restatement, and
      guessing would penalise a merchant who did nothing wrong;
    * two texts where neither contains the other -> `CONFLICT.CATEGORICAL`.
      Containment is refinement, not contradiction: "cotton" inside "100%
      cotton" is one value stated twice at different precisions (D-009).
    """
    numbers = [_numeric(v) for v in values]
    if all(n is not None for n in numbers):
        units = set(n[1] for n in numbers)
        if len(units) > 1:
            return None
        magnitudes = [n[0] for n in numbers]
        low, high = min(magnitudes), max(magnitudes)
        if low > 0 and (high - low) / low <= NUMERIC_TOLERANCE:
            return None
        if low == high:
            return None
        return "CONFLICT.NUMERIC"
    normalized = [_norm(v) for v in values]
    for i, a in enumerate(normalized):
        for j, b in enumerate(normalized):
            if i != j and a in b:
                return None
    return "CONFLICT.CATEGORICAL"


def conflict(check, conflict_check, builder, candidates):
    # type: (Any, Any, Any, List[Any]) -> Tuple[Optional[Finding], Optional[Finding]]
    """One D6 finding plus the zeroed attribute (PRD 9.2, D-012).

    Both locations become separate evidence items. The severity of the D6
    finding is the attribute's own conflict severity -- `blocker` where the
    attribute is safety-, allergen-, compatibility- or compliance-relevant for
    its category, `critical` otherwise -- and that relevance is a fixed
    property of the taxonomy row, not a judgment made here.
    """
    evidence = []
    excerpts = []
    for candidate in candidates:
        try:
            item = builder.field_value(candidate)
        except EvidenceError:
            continue
        evidence.append(item)
        excerpts.append(item.excerpt)
    if len(evidence) < 2:
        # rubric.md 4/D6 rule 4: a conflict that cannot be evidenced on both
        # sides is not emitted at all.
        return None, None

    remediation = _correction_remediation(conflict_check, excerpts)
    severity = check.conflict_severity if conflict_check.penalty else "info"
    d6 = _finding(
        conflict_check, R.FAIL, evidence, ZERO,
        confidence_arm="structural",
        title="%s: two supplied values disagree" % _label(check),
        detail="Two locations in the supplied data state different values for "
               "this attribute. Both are quoted in the evidence, and the tool "
               "does not choose between them.",
        penalty=conflict_check.penalty,
        severity=severity,
        remediation=remediation)

    zeroed = _finding(
        check, R.FAIL, list(evidence), ZERO,
        title="%s: two supplied values disagree" % _label(check),
        detail="This attribute earns nothing while two supplied values "
               "disagree. Both are quoted in the evidence.",
        remediation=remediation)
    return d6, zeroed


# ---------------------------------------------------------------------------
# the generic attribute check
# ---------------------------------------------------------------------------
def attribute_check(check, ctx):
    # type: (Any, Any) -> List[Finding]
    """Presence, absence, conflict -- in that order (PRD 9.8).

    Disagreement is tested **before** anything merges two values, because
    deduplicating a contradiction away is the one ordering mistake that turns a
    conflict into a silent, confident wrong answer.
    """
    builder = ctx.builder
    gathered = facts.gather(ctx.npr, check)
    stated = gathered.stated

    # 1. conflict, on the same subject only. Two variants stating different
    #    colours are two facts, not a contradiction.
    if check.conflict_routing:
        for group in _by_subject(stated):
            values = [c.value for c in group]
            if len(set(_norm(v) for v in values)) < 2:
                continue
            kind = _conflict_kind(values)
            if kind is None:
                ctx.ledger.defer(
                    check.check_id,
                    "Two supplied values differ but cannot be shown to be "
                    "incompatible without a conversion or an incompatibility "
                    "table (rubric.md 4/D6 rule 4).")
                return []
            conflict_check = ctx.registry.get(kind)
            d6, zeroed = conflict(check, conflict_check, builder, group)
            return [f for f in (d6, zeroed) if f is not None]

    # 2. something is stated.
    if stated:
        # Scope is decided before satisfaction, and the order matters. A
        # non-inheritable attribute stated only at product scope covers no
        # variant whatever the value turns out to say (`taxonomy.md` 4.3), so
        # D-018's arithmetic does not depend on a recognition predicate.
        # Gating it on one made D-018 unreachable for every such attribute
        # that declares a predicate -- the value was never even looked at for
        # scope. `_variant_coverage` still defers the branches that genuinely
        # need recognition.
        if check.scope == "variant" and check.inheritable is False:
            return _variant_coverage(check, ctx, stated)
        if check.structural_satisfaction:
            return [present(check, builder, stated[0])]
        verdict, candidate = _best_verdict(check, stated)
        if verdict is registry.SATISFIED:
            return [present(check, builder, candidate, recognized=True)]
        if verdict is registry.AMBIGUOUS:
            return [ambiguous(check, builder, candidate)]
        return _defer_for_recognition(check, ctx, verdict)

    # 3. nothing is stated, but prose was found and not read.
    if gathered.unrecognized_prose:
        ctx.ledger.defer(
            check.check_id,
            "Free text was found at a checked path and reading it needs "
            "recognition, so absence cannot be concluded here.")
        return []

    # 4. nothing is stated anywhere that was searched.
    return [unknown(check, builder, gathered)]


def _best_verdict(check, candidates):
    # type: (Any, List[Any]) -> Tuple[Any, Any]
    """The strongest verdict any supplied value reaches, and the value itself.

    Strongest wins because more information may not earn less than less
    (D-021): a record that states the same attribute twice, once satisfyingly
    and once vaguely, has stated the satisfying value, and the finding cites
    the value that decided it.

    Returns `(None, None)` when the check has no evaluator at all, which is a
    different fact from a predicate that ran and abstained (PRE-6).
    """
    if not check.has_recognition:
        return None, None
    verdict, chosen = registry.UNDECIDED, candidates[0]
    for candidate in candidates:
        current = check.recognize(candidate.value)
        if current is registry.SATISFIED:
            return current, candidate
        if current is registry.AMBIGUOUS and verdict is registry.UNDECIDED:
            verdict, chosen = current, candidate
    return verdict, chosen


def _by_subject(candidates):
    # type: (List[Any]) -> List[List[Any]]
    """Group candidates by what they are about: (scope, variant or option)."""
    groups = {}  # type: Dict[Tuple[str, Optional[str]], List[Any]]
    order = []
    for candidate in candidates:
        key = (candidate.scope, candidate.ref)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(candidate)
    return [groups[k] for k in order]


def unresolved_scope(check, builder, candidate, uncovered=()):
    # type: (Any, Any, Any, Any) -> Optional[Finding]
    """A value is stated, but not at the scope the check needs (PRD 9.7).

    **Earns nothing.** `rubric.md` 3.1 scores a coverage check at
    `max x (covered / total)`, and a product-scope value covers no variant of a
    non-inheritable attribute (`taxonomy.md` 4.3), so `covered` is 0 and the
    arithmetic gives 0. Awarding half credit here would pay for per-variant
    data the record does not hold, which is the shape of fabrication that
    inheritance rules exist to prevent (D-018).

    **Is not `UNKNOWN`.** Something *was* found, at a path this check declares
    it searched. Reporting that as absence would manufacture a gap that is not
    there -- the false negative PRD 8.3 rule 5 calls a blocker-severity bug,
    and the one the fabrication audit catches as `FAB012`. The supplied value
    is quoted instead, so the merchant sees exactly what was found and why it
    does not answer the check.
    """
    try:
        evidence = [builder.field_value(
            candidate,
            note="Stated once for the product. This attribute is not "
                 "inheritable, so the value does not resolve to a specific "
                 "variant.")]
    except EvidenceError:
        return None
    names = [v for v in uncovered if v]
    detail = ("A value is supplied at the locator quoted in the evidence, at "
              "product scope. This attribute has to resolve per variant.")
    if names:
        evidence.append(builder.absence(
            check.checked_paths,
            note="Checked and empty for these variants: %s." % ", ".join(names)))
        detail += (" It therefore covers 0 of the %d variants, and the "
                   "variants it was not found for are named in the evidence."
                   % len(names))
    return _finding(
        check, R.PARTIAL, evidence, ZERO,
        title="%s: stated for the product, not per variant" % _label(check),
        detail=detail,
        remediation=_question_remediation(check))


def _variant_coverage(check, ctx, stated):
    # type: (Any, Any, List[Any]) -> List[Finding]
    """A non-inheritable variant attribute must resolve per variant.

    `taxonomy.md` 4.3: inheriting one of these would let a merchant appear to
    hold per-variant data they do not hold, so a product-scope value does not
    cover a variant here -- but it is still a supplied value, and it is quoted
    rather than treated as though nothing were there.

    Two of the branches below are decidable without recognition and two are
    not, and they are separated deliberately:

    * **0 of N covered, with a product-scope value** is D-018. Coverage is 0
      because the value sits at the wrong scope, which is true whatever the
      value says, so no predicate is consulted.
    * **Some variant covered** needs recognition to say whether those values
      satisfy the check, so a check that declares a predicate defers -- and
      defers *without* emitting anything, exactly as before.

    No branch here reports absence while a value is stated: where a value was
    found and cannot be judged, the check says nothing (D-019).
    """
    variants = ctx.npr.get("variants") or []
    product_scope = [c for c in stated if c.scope != "variant"]
    if not variants:
        if product_scope:
            finding = unresolved_scope(check, ctx.builder, product_scope[0])
            return [finding] if finding else []
        if not check.structural_satisfaction:
            return _defer_for_recognition(check, ctx)
        return [unknown(check, ctx.builder, facts.gather(ctx.npr, check))]

    by_variant = dict((c.ref, c) for c in stated if c.scope == "variant" and c.ref)
    covered, uncovered = [], []
    for variant in variants:
        vid = variant.get("variant_id")
        if vid in by_variant:
            covered.append(by_variant[vid])
        else:
            uncovered.append(vid)
    if not covered:
        if product_scope:
            # D-018: zero earned, `PARTIAL`, the supplied value quoted, every
            # uncovered variant named. Decidable without recognition.
            finding = unresolved_scope(check, ctx.builder, product_scope[0],
                                       uncovered)
            return [finding] if finding else []
        if not check.structural_satisfaction:
            return _defer_for_recognition(check, ctx)
        return [unknown(check, ctx.builder, facts.gather(ctx.npr, check))]
    if check.structural_satisfaction:
        finding = coverage(check, ctx.builder, covered, uncovered)
        return [finding] if finding else []
    if not check.has_recognition:
        # Something covers a variant, and whether it satisfies the check is a
        # recognition question. Coverage is not asserted on an unread value.
        return _defer_for_recognition(check, ctx)

    # D-021, strict: `coverage = satisfied_variants / total_variants`.
    satisfied, unresolved = [], []
    for candidate in covered:
        verdict = check.recognize(candidate.value)
        if verdict is registry.SATISFIED:
            satisfied.append(candidate)
        elif verdict is registry.AMBIGUOUS:
            unresolved.append(candidate)
        else:
            # A verdict the predicate could not reach is not a verdict against
            # the variant. Counting it as uncovered would assert its value
            # fails to satisfy the check -- exactly what the predicate declined
            # to say -- and naming it as empty would be a false gap. The whole
            # check says nothing instead, forfeiting points the record may
            # deserve, which is the permitted direction of failure (D-019).
            return _defer_for_recognition(check, ctx, registry.UNDECIDED)
    finding = coverage(check, ctx.builder, satisfied, uncovered,
                       unresolved=unresolved, recognized=True)
    return [finding] if finding else []


# ---------------------------------------------------------------------------
# structural checks with their own logic
# ---------------------------------------------------------------------------
def _variant_ids(npr):
    # type: (dict) -> List[str]
    return [v.get("variant_id") for v in (npr.get("variants") or [])]


def _variant_identifier(variant):
    # type: (dict) -> Tuple[Optional[str], Optional[str]]
    """(value, locator) of the first identifier a variant carries."""
    for field in ("sku", "barcode"):
        node = variant.get(field) or {}
        value = node.get("value")
        if isinstance(value, str) and value.strip():
            return value, node.get("src")
    return None, None


def check_identifier_present(check, ctx):
    # type: (Any, Any) -> List[Finding]
    """Every variant carries a SKU, barcode or MPN. Coverage-scored."""
    variants = ctx.npr.get("variants") or []
    if not variants:
        return [unknown(check, ctx.builder, facts.gather(ctx.npr, check))]
    covered, uncovered = [], []
    for variant in variants:
        vid = variant.get("variant_id")
        value, src = _variant_identifier(variant)
        if value is None or not src:
            uncovered.append(vid)
            continue
        covered.append(facts.Candidate(value, src, "merchant_structured",
                                       "variants[%s]" % vid, scope="variant",
                                       ref=vid))
    if not covered:
        # A product-level MPN is a supplied identifier; `product_identifier` is
        # non-inheritable (`taxonomy.md` 3), so it does not cover a variant --
        # but it is quoted rather than reported as nothing.
        gathered = facts.gather(ctx.npr, check)
        product_scope = [c for c in gathered.stated if c.scope != "variant"]
        if product_scope:
            finding = unresolved_scope(check, ctx.builder, product_scope[0],
                                       uncovered)
            return [finding] if finding else []
        return [unknown(check, ctx.builder, gathered)]
    finding = coverage(check, ctx.builder, covered, uncovered)
    return [finding] if finding else []


def check_variant_differentiated(check, ctx):
    # type: (Any, Any) -> List[Finding]
    """Every variant is told apart by at least one option value (PRD 9.7).

    A `FAIL` here needs two variants that are actually present and actually
    identical, so it can never fire on a product whose data is merely thin.
    """
    variants = ctx.npr.get("variants") or []
    signatures = {}  # type: Dict[Tuple, List[dict]]
    for variant in variants:
        values = variant.get("option_values") or {}
        # D-033: the value lives in the pair. The comparison itself is
        # unchanged -- `rubric.md` 4/D3 decides this check and nothing here
        # touches what it decides, only where the value is read from.
        signature = tuple(sorted(
            (k, (v or {}).get("value")) for k, v in values.items()
            if isinstance((v or {}).get("value"), str)
            and (v or {}).get("value").strip()))
        signatures.setdefault(signature, []).append(variant)

    collisions = [group for signature, group in sorted(signatures.items())
                  if len(group) > 1 or not signature]
    if collisions:
        evidence = []
        for group in collisions:
            for variant in group:
                value, src = _variant_identifier(variant)
                if value is None or not src:
                    continue
                candidate = facts.Candidate(
                    value, src, "merchant_structured",
                    "variants[%s]" % variant.get("variant_id"),
                    scope="variant", ref=variant.get("variant_id"))
                try:
                    evidence.append(ctx.builder.field_value(
                        candidate,
                        note="This variant carries the same option values as "
                             "another variant of the same product."))
                except EvidenceError:
                    continue
        if len(evidence) < 2:
            ctx.ledger.defer(
                check.check_id,
                "Variants share option values, and fewer than two of them "
                "carry a quotable identifier to evidence it with.")
            return []
        return [_finding(
            check, R.FAIL, evidence, ZERO,
            title="%s: variants are not told apart by an option value"
                  % _label(check),
            detail="Two or more variants carry the same option values. Each is "
                   "quoted in the evidence.",
            remediation=_question_remediation(check))]

    # D-033. The locator is *copied* from the record, never composed here: a
    # composed string cannot be format-neutral, and this function does not know
    # the format. `variants[<vid>].option_values[<name>]` resolves under
    # Format C and does not parse under Format A, which is how this check came
    # to emit nothing at all on every multi-variant CSV product.
    refs, unprovenanced = [], []
    for variant in variants:
        values = variant.get("option_values") or {}
        for name in sorted(values):
            src = (values.get(name) or {}).get("src")
            if src:
                refs.append(src)
            else:
                unprovenanced.append("%s/%s" % (variant.get("variant_id"), name))
    if unprovenanced:
        # The contract is unmet, so the check says so rather than vanishing
        # (D-033, PRD 8.3 rule 1). `validate_npr` has already emitted the
        # run error naming the record; this is the check's half of it.
        ctx.ledger.defer(
            check.check_id,
            "An option value carries no locator, so the distinct combinations "
            "cannot be evidenced at their own sources (%s)."
            % ", ".join(sorted(unprovenanced)[:5]))
        return []
    if len(refs) < 2:
        return []
    try:
        evidence = [ctx.builder.derived(
            refs, "%d variants, %d distinct option-value combinations"
                  % (len(variants), len(signatures)))]
    except EvidenceError as exc:
        ctx.ledger.error("CHECK.EVIDENCE", str(exc), check.check_id)
        return []
    return [_finding(
        check, R.PASS, evidence, check.max_points,
        title="%s: every variant is told apart by an option value" % _label(check),
        detail="Each of the %d variants carries a distinct combination of "
               "option values." % len(variants))]


def check_option_names(check, ctx):
    # type: (Any, Any) -> List[Finding]
    """Option names are populated and are not a reserved default."""
    gathered = facts.gather(ctx.npr, check)
    if not gathered.stated:
        return [unknown(check, ctx.builder, gathered)]
    reserved = [c for c in gathered.stated if _norm(c.value) in lexicon.VARIANT_OPTION_NAMES_RESERVED]
    if reserved:
        evidence = []
        for candidate in reserved:
            try:
                evidence.append(ctx.builder.field_value(
                    candidate,
                    note="This option name is one of the platform's reserved "
                         "default names."))
            except EvidenceError:
                continue
        if evidence:
            return [_finding(
                check, R.FAIL, evidence, ZERO,
                title="%s: an option name is a reserved default" % _label(check),
                detail="An option name is one of the reserved default names. "
                       "Each is quoted in the evidence.",
                remediation=_question_remediation(check))]
    evidence = []
    for candidate in gathered.stated:
        try:
            evidence.append(ctx.builder.field_value(candidate))
        except EvidenceError:
            continue
    if not evidence:
        return []
    return [_finding(
        check, R.PASS, evidence, check.max_points,
        title="%s: option names are populated" % _label(check),
        detail="Each option name is supplied at the locator quoted in the "
               "evidence, and none is a reserved default.")]


def check_option_values(check, ctx):
    # type: (Any, Any) -> List[Finding]
    """Values within an option are unique and non-empty.

    The rubric also requires one convention across an option's values
    ("not `S`/`Small`/`sm` mixed"), which is language recognition. That arm is
    deferred: uniqueness alone is not enough to declare the check satisfied, so
    a clean option yields no finding rather than an unearned `PASS`.
    """
    duplicates = []
    for option in ctx.npr.get("options") or []:
        name = option.get("name")
        seen = {}
        for value in option.get("values") or []:
            key = _norm(value) if isinstance(value, str) else ""
            if key in seen:
                duplicates.append((name, value))
            seen[key] = value
    if duplicates:
        evidence = []
        for name, value in duplicates:
            candidate = facts.Candidate(value, "options[%s].values" % name,
                                        "merchant_structured",
                                        "options[%s].values" % name,
                                        scope="option", ref=name)
            try:
                evidence.append(ctx.builder.quote(
                    candidate.src,
                    note="This option repeats a value within one option."))
            except EvidenceError:
                continue
        if evidence:
            return [_finding(
                check, R.FAIL, evidence, ZERO,
                title="%s: an option repeats a value" % _label(check),
                detail="An option carries the same value more than once. The "
                       "option's value list is quoted in the evidence.",
                remediation=_question_remediation(check))]
    ctx.ledger.defer(
        check.check_id,
        "Values are unique, and deciding whether they follow one convention "
        "needs recognition (%s)." % check.satisfies)
    return []


def check_identifier_unique(check, ctx):
    # type: (Any, Any) -> List[Finding]
    """Identifiers are present and distinct. Duplicates are present-and-wrong."""
    seen = {}  # type: Dict[str, List[Tuple[str, str, str]]]
    for variant in ctx.npr.get("variants") or []:
        vid = variant.get("variant_id")
        value, src = _variant_identifier(variant)
        if value is None or not src:
            continue
        seen.setdefault(_norm(value), []).append((value, src, vid))
    if not seen:
        return [unknown(check, ctx.builder, facts.gather(ctx.npr, check))]

    duplicates = [rows for _, rows in sorted(seen.items()) if len(rows) > 1]
    if duplicates:
        evidence = []
        for rows in duplicates:
            for value, src, vid in rows:
                candidate = facts.Candidate(value, src, "merchant_structured",
                                            "variants[%s]" % vid,
                                            scope="variant", ref=vid)
                try:
                    evidence.append(ctx.builder.field_value(
                        candidate,
                        note="This identifier is carried by more than one "
                             "variant of this product."))
                except EvidenceError:
                    continue
        if len(evidence) >= 2:
            return [_finding(
                check, R.FAIL, evidence, ZERO,
                title="%s: two variants carry the same identifier" % _label(check),
                detail="More than one variant carries the same identifier. Each "
                       "is quoted in the evidence.",
                remediation=_question_remediation(check))]

    evidence = []
    for rows in sorted(seen.values()):
        value, src, vid = rows[0]
        candidate = facts.Candidate(value, src, "merchant_structured",
                                    "variants[%s]" % vid, scope="variant", ref=vid)
        try:
            evidence.append(ctx.builder.field_value(candidate))
        except EvidenceError:
            continue
    if not evidence:
        return []
    return [_finding(
        check, R.PASS, evidence, check.max_points,
        title="%s: every identifier is distinct" % _label(check),
        detail="Each variant identifier is supplied and distinct from the "
               "others, at the locators quoted in the evidence.")]


def check_no_placeholders(check, ctx):
    # type: (Any, Any) -> List[Finding]
    """Placeholders occupying value fields. Present, and wrong (PRD 9.4)."""
    gathered = facts.gather(ctx.npr, check)
    placeholders = gathered.placeholders
    if placeholders:
        evidence = []
        for candidate in placeholders:
            try:
                evidence.append(ctx.builder.field_value(
                    candidate,
                    note="A placeholder occupies this value field."))
            except EvidenceError:
                continue
        if evidence:
            return [_finding(
                check, R.FAIL, evidence, ZERO,
                title="%s: a placeholder occupies a value field" % _label(check),
                detail="A placeholder occupies a field that a value belongs in. "
                       "Each one found is quoted in the evidence.",
                remediation=Remediation(REMEDIATION_CORRECTION, check.question,
                                        check.target_field(), DO_NOT_GENERATE))]
    return [_finding(
        check, R.PASS, [ctx.builder.absence(
            check.checked_paths,
            note="Checked and empty: no placeholder value was found at these "
                 "paths.")],
        check.max_points,
        title="%s: no placeholder occupies a value field" % _label(check),
        detail="The paths listed in the evidence were searched and hold no "
               "placeholder.")]


def check_seo_fields(check, ctx):
    # type: (Any, Any) -> List[Finding]
    """Presence only. Never a judgment about the words (`rubric.md` 9 rule 5)."""
    gathered = facts.gather(ctx.npr, check)
    stated = gathered.stated
    if not stated:
        return [unknown(check, ctx.builder, gathered)]
    evidence = []
    for candidate in stated:
        try:
            evidence.append(ctx.builder.field_value(candidate))
        except EvidenceError:
            continue
    if not evidence:
        return []
    if len(stated) >= len(check.checked_paths):
        return [_finding(
            check, R.PASS, evidence, check.max_points,
            title="%s: both search listing fields are populated" % _label(check),
            detail="Each field is supplied at the locator quoted in the "
                   "evidence.")]
    evidence.append(ctx.builder.absence(
        check.checked_paths,
        note="Checked and empty for the search listing field that is not "
             "quoted above."))
    return [_finding(
        check, R.PARTIAL, evidence, check.max_points * check.partial_credit,
        title="%s: one search listing field is populated" % _label(check),
        detail="One of the two fields is supplied; the other was checked and "
               "held no value.",
        remediation=_question_remediation(check))]


def check_media_alt_text(check, ctx):
    # type: (Any, Any) -> List[Finding]
    """Alt text coverage across the media the record carries."""
    media = ctx.npr.get("media") or []
    if not media:
        return [unknown(check, ctx.builder, facts.gather(ctx.npr, check))]
    covered, uncovered = [], []
    for index, item in enumerate(media):
        node = item.get("alt") or {}
        value, src = node.get("value"), node.get("src")
        if isinstance(value, str) and value.strip() and src:
            covered.append(facts.Candidate(value, src, "merchant_structured",
                                           "media[%d].alt" % index,
                                           ref=str(index)))
        else:
            uncovered.append("media[%d]" % index)
    if not covered:
        return [unknown(check, ctx.builder, facts.gather(ctx.npr, check))]
    finding = coverage(check, ctx.builder, covered, uncovered)
    return [finding] if finding else []


def check_description_parseable(check, ctx):
    # type: (Any, Any) -> List[Finding]
    """Lists, tables or headings rather than one block.

    The structure flags are recorded by the normalizer from the supplied
    markup, so this is a structural read, not a judgment about the writing.
    """
    narrative = ctx.npr.get("narrative") or {}
    node = narrative.get("description_text") or {}
    text, src = node.get("value"), node.get("src")
    if not isinstance(text, str) or not text.strip() or not src:
        return [unknown(check, ctx.builder, facts.gather(ctx.npr, check))]
    structure = narrative.get("structure") or {}
    marked = [name for name in ("has_lists", "has_tables", "has_headings")
              if structure.get(name)]
    if not marked:
        # Structural markup that is not there is absent, not defective. A
        # plainly written paragraph is not a value that is wrong, and
        # `rubric.md` 3.1 reserves FAIL for something present being wrong.
        return [_finding(
            check, R.UNKNOWN,
            [ctx.builder.absence(
                check.checked_paths,
                note="Checked and empty: the structure recorded for the "
                     "supplied description marks no list, table or heading.")],
            ZERO,
            title="%s: not stated in the supplied data" % _label(check),
            detail="%s No list, table or heading is recorded for the supplied "
                   "description." % NOT_STATED,
            remediation=Remediation(REMEDIATION_STRUCTURE, check.question,
                                    check.target_field(), DO_NOT_GENERATE))]
    end = min(len(text), 40)
    try:
        evidence = [ctx.builder.span(
            src, 0, end,
            note="The opening of the supplied description, quoted so the "
                 "structure recorded for it can be checked against the input.")]
    except EvidenceError:
        return []
    return [_finding(
        check, R.PASS, evidence, check.max_points,
        title="%s: the description carries structural markup" % _label(check),
        detail="The supplied description markup records: %s."
               % ", ".join(sorted(marked)))]


def check_attributes_in_fields(check, ctx):
    # type: (Any, Any) -> List[Finding]
    """How much of what is stated lives in a structured field, not in prose."""
    gathered = facts.gather(ctx.npr, check)
    stated = gathered.stated
    if not stated:
        return [unknown(check, ctx.builder, gathered)]
    structured = [c for c in stated if c.origin == "merchant_structured"]
    prose = [c for c in stated if c.origin != "merchant_structured"]
    evidence = []
    for candidate in (structured or stated):
        try:
            evidence.append(ctx.builder.field_value(candidate))
        except EvidenceError:
            continue
    if not evidence:
        return []
    if not prose:
        return [_finding(
            check, R.PASS, evidence, check.max_points,
            title="%s: every stated attribute is held in a structured field"
                  % _label(check),
            detail="All %d attribute values found are held in structured "
                   "fields, at the locators quoted in the evidence."
                   % len(stated))]
    for candidate in prose:
        try:
            evidence.append(ctx.builder.field_value(
                candidate,
                note="This attribute value is held in prose rather than in a "
                     "structured field."))
        except EvidenceError:
            continue
    earned = check.max_points * Decimal(len(structured)) / Decimal(len(stated))
    return [_finding(
        check, R.PARTIAL, evidence, earned,
        title="%s: some attributes are held only in prose" % _label(check),
        detail="%d of the %d attribute values found are held in structured "
               "fields. Each value is quoted in the evidence."
               % (len(structured), len(stated)),
        remediation=Remediation(REMEDIATION_STRUCTURE, check.question,
                                check.target_field(), DO_NOT_GENERATE))]


#: Checks whose logic is their own. Everything else is the generic attribute
#: check, which is what keeps the D2 family table-driven.
def _title_relation(check, ctx, pairs, note):
    # type: (Any, Any, List[Tuple[str, Any]], str) -> List[Finding]
    """Shared body of the two title checks (slice C).

    Both decide by comparing the title against another value the record
    already states, so both cite **two** locators: the title, and the field it
    repeats. Nothing external is consulted and no vocabulary is involved.

    **Neither check has a negative arm, and that is deliberate.** A title may
    name a product type, or carry a distinguishing attribute, that the record
    states nowhere else. Concluding otherwise would be an assertion about the
    title that the supplied data does not support, so a relation that does not
    hold produces a deferral and no finding.
    """
    gathered = facts.gather(ctx.npr, check)
    stated = gathered.stated
    if not stated:
        return [unknown(check, ctx.builder, gathered)]
    title = stated[0]
    relation = ctx.registry.IMPLEMENTED_RELATIONS.get(check.satisfies)
    if relation is None:
        return _defer_for_recognition(check, ctx)
    matched = relation(title.value, [text for text, _ in pairs])
    if matched is None:
        return _defer_for_recognition(check, ctx, registry.UNDECIDED)
    candidate = next(c for text, c in pairs if text == matched)
    try:
        evidence = [
            ctx.builder.field_value(
                title, note="The title, as supplied."),
            ctx.builder.field_value(candidate, note=note),
        ]
    except EvidenceError:
        return _defer_for_recognition(check, ctx, registry.UNDECIDED)
    return [_finding(
        check, R.PASS, evidence, check.max_points,
        confidence_arm="recognized",
        title="%s: the title repeats a value the record states" % _label(check),
        detail="The title and the second locator quoted in the evidence carry "
               "the same term. Both are supplied values; the tool compares "
               "them and states nothing else about either.")]


def _stated_at(npr, pattern, key=None):
    # type: (dict, str, Optional[str]) -> List[Any]
    return [c for c in facts.at(npr, pattern, key) if not c.is_placeholder]


def check_title_specific(check, ctx):
    # type: (Any, Any) -> List[Finding]
    """C1. The title names a product type the record states elsewhere.

    A `declared_category` is compared on its final `>`-delimited segment --
    the leaf is the type; the path above it is the hierarchy that contains it.
    The whole field is still what gets quoted, at its own locator.
    """
    pairs = []
    for candidate in _stated_at(ctx.npr, "identity.product_type"):
        pairs.append((candidate.value, candidate))
    for candidate in _stated_at(ctx.npr, "identity.declared_category"):
        pairs.append((candidate.value.rsplit(">", 1)[-1].strip(), candidate))
    return _title_relation(
        check, ctx, pairs,
        "The product type or category this title repeats, as supplied here.")


def check_title_distinguishing(check, ctx):
    # type: (Any, Any) -> List[Finding]
    """C2. The title carries an attribute value the record states elsewhere.

    `rubric.md` 4/D1 fixes `PASS` at "a distinguishing attribute (material,
    size, model, capacity, count)", and D-024 reads that parenthesis as a
    closed list. The candidate set is therefore every structured value held at
    a taxonomy attribute key that *is* one of those five kinds -- product
    attributes, per-variant attributes and exactly-keyed metafields.

    Two exclusions, both narrowing:

    * `identity.brand` never enters, by construction. A title that repeats the
      brand carries no distinguishing attribute, which is the point of the
      check.
    * Variant **option values** never enter either. An option named `Size`
      carrying `Large` is a size, but deciding that an option *name* denotes
      one of the five kinds needs a vocabulary of option names, and that
      vocabulary would be a new scoring artifact. Under-detection is the
      permitted direction until it is decided on its own merits (D-024).
    """
    pairs = []
    for pattern in ("attributes[*]", "variants[*].attributes", "metafields.*"):
        for candidate in _stated_at(ctx.npr, pattern):
            if candidate.key not in lexicon.IDENT_TITLE_DISTINGUISHING_KEYS:
                continue
            pairs.append((candidate.value, candidate))
    return _title_relation(
        check, ctx, pairs,
        "The attribute value this title repeats, as supplied here.")


def check_variant_attribute_coverage(check, ctx):
    # type: (Any, Any) -> List[Finding]
    """D3. Every attribute the category requires per variant is present on each.

    **Presence, not satisfaction (D-030).** `rubric.md` 4/D3 fixes this check's
    `PASS` at "Every non-inheritable variant-scope attribute for the category
    is *present* on every variant", and that word governs. No attribute's
    recognition predicate runs here. The D2 check that owns each key decides
    whether its value is any good; this check decides only whether the record
    resolves per variant, and the two are different questions about the same
    value rather than two answers to one.

    **The coverage unit is the variant, which is why this does not reuse
    `coverage`.** That helper counts one candidate per unit; here a covered
    variant carries one candidate *per key*, so passing them through it would
    compute `satisfied_values / total_values` instead of
    `covered_variants / total_variants`. The arithmetic below is `rubric.md`
    3.1's coverage clause over variants, and nothing else.

    **D-025's floor is not written here, deliberately.** Under presence
    semantics no ambiguity arm runs, so there is no present-but-ambiguous group
    for a floor to be taken over -- and this check's `partial_credit` is 0.0 in
    any case. Raising that figure re-opens D-030, rather than quietly starting
    to bind.

    **`checked_paths` stays `("variants[*].attributes",)`.** A product-scope
    value at one of these keys is outside what this check searched, so no
    D-018 branch fires here and the absence evidence claims only what is true:
    variant attributes were searched and were empty. That value is reported,
    quoted, by its own D2 attribute check under D-018.
    """
    keys = T.variant_scope_keys(ctx.category)
    if not keys:
        # Unreachable in practice: `runner._na_reason` removes the check before
        # it runs (D-029). Kept as a guard so the arithmetic below can assume a
        # non-empty requirement, and so a caller that bypasses the runner
        # cannot silently divide by a requirement that is not there.
        return []
    variants = ctx.npr.get("variants") or []
    gathered = facts.gather(ctx.npr, check)
    if not variants:
        return [_nothing_required_per_variant(check, ctx, keys, 0, gathered)]

    # D-018 and D-021 rule 2: only a value at variant scope, carrying the
    # variant it belongs to, can cover that variant. A product-scope value
    # covers none of them whatever it says. `checked_paths` does not reach
    # product scope at all, so no such value is gathered here in the first
    # place -- the filter is the rule stated where it can be read.
    by_variant = {}  # type: Dict[str, Dict[str, Any]]
    for candidate in gathered.stated:
        if candidate.scope != "variant" or not candidate.ref:
            continue
        if candidate.key in keys:
            by_variant.setdefault(candidate.ref, {}).setdefault(
                candidate.key, candidate)

    covered, missing, quotable = [], [], []
    for variant in variants:
        vid = variant.get("variant_id")
        held = by_variant.get(vid) or {}
        for key in keys:
            if key in held:
                quotable.append((key, held[key]))
        absent = [key for key in keys if key not in held]
        if absent:
            missing.append((vid, absent))
        else:
            covered.append(vid)

    total = len(variants)
    if not quotable:
        # Nothing this check requires is stated for any variant. Only here is
        # absence the whole truth, and the note says what was looked for so the
        # claim is checkable against the record (PRD 8.3 rule 5).
        return [_nothing_required_per_variant(check, ctx, keys, total, gathered)]

    evidence = []
    for key, candidate in quotable:
        try:
            evidence.append(ctx.builder.field_value(
                candidate,
                note="This variant resolves %s, one of the %d attributes this "
                     "category requires per variant." % (key, len(keys))))
        except EvidenceError:
            continue
    if not evidence:
        return []

    if not missing:
        return [_finding(
            check, R.PASS, evidence, check.max_points,
            title="%s: every required variant-scope attribute is present on "
                  "every variant" % _label(check),
            detail="Each of the %d variants carries a value for all %d "
                   "attributes this category requires per variant, at the "
                   "locators quoted in the evidence."
                   % (total, len(keys)))]

    # PRD 9.7 / D-021 rule 4: every uncovered variant named individually, with
    # the keys it is missing. Both are structural names, never product values.
    #
    # This branch covers `covered == 0` as well, and that is deliberate. Some
    # of what the check requires *is* stated, so the record is incomplete
    # rather than empty: `rubric.md` 3.1 reserves `UNKNOWN` for "not found in
    # any checked_paths", and reporting a gap over values that are there is
    # the false negative PRD 8.3 rule 5 calls blocker-severity. The arithmetic
    # is unchanged -- 0 of N covered earns exactly 0.00 -- so nothing is paid
    # for the partial data; it is only reported honestly.
    evidence.append(ctx.builder.absence(
        check.checked_paths,
        note="Checked and empty for these variants: %s."
             % "; ".join("%s (%s)" % (vid, ", ".join(absent))
                         for vid, absent in missing)))
    earned = check.max_points * Decimal(len(covered)) / Decimal(total)
    return [_finding(
        check, R.PARTIAL, evidence, earned,
        title="%s: required variant-scope attributes are present for some of "
              "the variants" % _label(check),
        detail="%d of the %d variants carry a value for all %d attributes this "
               "category requires per variant. The variants that do not, and "
               "the attributes each is missing, are named in the evidence."
               % (len(covered), total, len(keys)),
        remediation=_question_remediation(check))]


def _nothing_required_per_variant(check, ctx, keys, total, gathered):
    # type: (Any, Any, Tuple[str, ...], int, Any) -> Finding
    """`UNKNOWN` for `VARIANT.ATTRIBUTE_COVERAGE`, saying what was looked for.

    The generic `unknown` constructor reports "no value was found at the
    checked paths". That sentence would be false here whenever a variant
    carries an attribute outside `K`: something *was* found at
    `variants[*].attributes`, just nothing this check requires. Naming the keys
    keeps the absence claim exactly as wide as the search that produced it
    (PRD 8.3 rule 5).
    """
    evidence = [ctx.builder.absence(
        check.checked_paths,
        note="Checked each variant for %s, and none of them is stated for any "
             "variant." % ", ".join(keys))]
    for candidate in gathered.placeholders:
        try:
            evidence.append(ctx.builder.field_value(
                candidate,
                note="A placeholder occupies this field, so it states no value "
                     "(PRD 9.4)."))
        except EvidenceError:
            continue
    return _finding(
        check, R.UNKNOWN, evidence, ZERO,
        title="%s: not stated for any variant" % _label(check),
        detail="%s No value for any of the %d attributes this category "
               "requires per variant was found on any of the %d variants, at "
               "the checked path listed in the evidence."
               % (NOT_STATED, len(keys), total),
        remediation=_question_remediation(check))


def _linked_media(npr, variant):
    # type: (dict, dict) -> Optional[Any]
    """The first media item this variant links to, as a quotable candidate.

    `media_refs` holds urls; `media[]` holds the record with the locator. The
    candidate is built from the media entry so the evidence quotes a locator
    the normalizer already proved resolvable, never one composed here.
    """
    refs = [r for r in (variant.get("media_refs") or [])
            if isinstance(r, str) and r.strip()]
    if not refs:
        return None
    for index, item in enumerate(npr.get("media") or []):
        if item.get("url") in refs and item.get("src"):
            return facts.Candidate(
                item["url"], item["src"], "merchant_structured",
                "media[%d]" % index, scope="variant",
                ref=variant.get("variant_id"))
    return None


def check_media_linked(check, ctx):
    # type: (Any, Any) -> List[Finding]
    """D3. Where a visual option exists, every variant links its own media.

    **The trigger is an option name, from a closed vocabulary (D-031).**
    `rubric.md` 4/D3 makes the check "conditional on a visual option existing"
    and names the axis as "color/finish/shade"; D-024 reads such a parenthesis
    as a closed list. The name is matched whole and normalized, exactly as
    `check_option_names` matches the reserved defaults -- and against option
    *names* only, never against their values.

    **No match is a deferral, never `NOT_APPLICABLE`.** `taxonomy.md` 4.4: a
    trigger is structural and never assumed. Not finding a colour option does
    not establish that the variants do not differ visually -- the axis may be
    named outside the vocabulary, which deliberate under-detection guarantees
    will happen -- and removing 1.5 points from the denominator on that
    assumption is the one thing PRD 10.3 forbids.

    **Determined structurally throughout**, so the finding reports the
    structural arm (D-020): membership in a closed list, then presence or
    absence of a media reference per variant. No supplied value is read for
    what it means, so PRD 9.5's recognition cap is not in play (D-026).
    """
    visual = []
    for option in ctx.npr.get("options") or []:
        name = option.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        if lexicon.normalize(name) in lexicon.VARIANT_MEDIA_LINKED_VISUAL_OPTION_NAMES:
            visual.append(name)
    if not visual:
        ctx.ledger.defer(
            check.check_id,
            "No option name is one this check recognizes as a visual axis, so "
            "the structural trigger is not shown to be present. It is not "
            "shown to be absent either, and the check states nothing rather "
            "than removing itself (taxonomy.md 4.4, D-031).")
        return []

    variants = ctx.npr.get("variants") or []
    gathered = facts.gather(ctx.npr, check)
    if not variants:
        return [unknown(check, ctx.builder, gathered)]

    covered, uncovered = [], []
    for variant in variants:
        candidate = _linked_media(ctx.npr, variant)
        if candidate is None:
            uncovered.append(variant.get("variant_id"))
        else:
            covered.append(candidate)

    if covered:
        finding = coverage(
            check, ctx.builder, covered, uncovered,
            note="This variant links to this media item.")
        return [finding] if finding else []

    # Nothing is linked per variant. Whether that is a gap depends on what the
    # other checked path holds.
    product_media = [c for c in gathered.stated if c.scope != "variant"]
    if product_media:
        # D-018's shape, applied to media: something was found at a path this
        # check declares it searched, so reporting absence would be the false
        # negative PRD 8.3 rule 5 calls blocker-severity. It earns nothing --
        # product media resolves to no variant -- and the value is quoted
        # rather than treated as though nothing were there (D-031).
        try:
            evidence = [ctx.builder.field_value(
                product_media[0],
                note="Supplied for the product. No variant links to it, so it "
                     "does not resolve to a visually distinct variant.")]
        except EvidenceError:
            return [unknown(check, ctx.builder, gathered)]
        evidence.append(ctx.builder.absence(
            check.checked_paths,
            note="Checked and empty for these variants: %s."
                 % ", ".join(v for v in uncovered if v)))
        return [_finding(
            check, R.PARTIAL, evidence, ZERO,
            title="%s: media is supplied for the product, not per variant"
                  % _label(check),
            detail="This product varies on a visual option and media is "
                   "supplied at the locator quoted in the evidence, at product "
                   "scope. It covers 0 of the %d variants, and every variant "
                   "no linked media was found for is named in the evidence."
                   % len(variants),
            remediation=_question_remediation(check))]
    return [unknown(check, ctx.builder, gathered)]


DISPATCH = {
    "IDENT.TITLE_SPECIFIC": check_title_specific,
    "IDENT.TITLE_DISTINGUISHING": check_title_distinguishing,
    "IDENT.IDENTIFIER_PRESENT": check_identifier_present,
    "VARIANT.DIFFERENTIATED": check_variant_differentiated,
    "VARIANT.OPTION_NAMES_MEANINGFUL": check_option_names,
    "VARIANT.OPTION_VALUES_CONSISTENT": check_option_values,
    "VARIANT.ATTRIBUTE_COVERAGE": check_variant_attribute_coverage,
    "VARIANT.MEDIA_LINKED": check_media_linked,
    "VARIANT.IDENTIFIER_UNIQUE": check_identifier_unique,
    "STRUCT.NO_PLACEHOLDER_VALUES": check_no_placeholders,
    "STRUCT.SEO_FIELDS_POPULATED": check_seo_fields,
    "STRUCT.MEDIA_ALT_TEXT": check_media_alt_text,
    "STRUCT.DESCRIPTION_PARSEABLE": check_description_parseable,
    "STRUCT.ATTRIBUTES_IN_FIELDS": check_attributes_in_fields,
}


def run(check, ctx):
    # type: (Any, Any) -> List[Finding]
    return DISPATCH.get(check.check_id, attribute_check)(check, ctx)
