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
from . import rubric_data as R
from .findings import (DO_NOT_GENERATE, NOT_STATED, Evidence, EvidenceError,
                       Finding, Remediation, REMEDIATION_CORRECTION,
                       REMEDIATION_QUESTION, REMEDIATION_STRUCTURE)

ZERO = Decimal("0")

#: Option names that name nothing (`rubric.md` 4/D3). A closed list: an option
#: name is judged against these literals and against emptiness, never against a
#: notion of how meaningful it reads.
RESERVED_OPTION_NAMES = frozenset([
    "title", "default", "default title", "option 1", "option 2", "option 3",
])

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


def _defer_for_recognition(check, ctx):
    # type: (Any, Any) -> List[Finding]
    """A value is supplied and judging it needs recognition (D-019).

    One reason string, in one place, so that every path which abstains for the
    same reason is recorded identically and the deferral ledger stays a usable
    measurement of the recall gap.
    """
    ctx.ledger.defer(
        check.check_id,
        "A value is supplied, and deciding whether it satisfies this "
        "check needs recognition over prose (%s)." % check.satisfies)
    return []


def _finding(check, status, evidence, earned, confidence_arm="structural",
             title=None, detail=None, scope_level=None, scope_ref=None,
             remediation=None, penalty=ZERO, severity=None, max_points=None):
    # type: (...) -> Finding
    confidence = getattr(check.confidence, confidence_arm)
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


def present(check, builder, candidate, note=None):
    # type: (Any, Any, Any, Optional[str]) -> Finding
    """A stated value satisfies a check whose taxonomy row states no PARTIAL."""
    evidence = [builder.field_value(candidate, note=note)]
    return _finding(
        check, R.PASS, evidence, check.max_points,
        title="%s: stated in the supplied data" % _label(check),
        detail="A value is supplied at the locator quoted in the evidence.",
        scope_level=candidate.scope, scope_ref=candidate.ref)


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


def coverage(check, builder, covered, uncovered, note=None):
    # type: (Any, Any, List[Any], List[str], Optional[str]) -> Optional[Finding]
    """Variant coverage, scored proportionally and naming what is uncovered.

    PRD 9.7: partial coverage is `PARTIAL` at `covered/total`, and the evidence
    names the uncovered variant ids explicitly -- never "some variants".
    """
    total = len(covered) + len(uncovered)
    if not total:
        return None
    evidence = []
    for candidate in covered:
        try:
            evidence.append(builder.field_value(candidate, note=note))
        except EvidenceError:
            continue
    if not evidence:
        return None
    if not uncovered:
        return _finding(
            check, R.PASS, evidence, check.max_points,
            title="%s: stated for every variant" % _label(check),
            detail="A value is supplied for each of the %d variants, at the "
                   "locators quoted in the evidence." % total)
    evidence.append(builder.absence(
        check.checked_paths,
        note="Checked and empty for these variants: %s." % ", ".join(uncovered)))
    earned = check.max_points * Decimal(len(covered)) / Decimal(total)
    return _finding(
        check, R.PARTIAL, evidence, earned,
        title="%s: stated for some of the variants" % _label(check),
        detail="A value is supplied for %d of the %d variants. The variants it "
               "was not found for are named in the evidence."
               % (len(covered), total),
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
        if not check.structural_satisfaction:
            return _defer_for_recognition(check, ctx)
        return [present(check, builder, stated[0])]

    # 3. nothing is stated, but prose was found and not read.
    if gathered.unrecognized_prose:
        ctx.ledger.defer(
            check.check_id,
            "Free text was found at a checked path and reading it needs "
            "recognition, so absence cannot be concluded here.")
        return []

    # 4. nothing is stated anywhere that was searched.
    return [unknown(check, builder, gathered)]


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
    if not check.structural_satisfaction:
        # Something covers a variant, and whether it satisfies the check is a
        # recognition question. Coverage is not asserted on an unread value.
        return _defer_for_recognition(check, ctx)
    finding = coverage(check, ctx.builder, covered, uncovered)
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
        signature = tuple(sorted((k, v) for k, v in values.items()
                                 if isinstance(v, str) and v.strip()))
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

    refs = []
    for variant in variants:
        for name in sorted((variant.get("option_values") or {})):
            refs.append("variants[%s].option_values[%s]"
                        % (variant.get("variant_id"), name))
    if len(refs) < 2:
        return []
    try:
        evidence = [ctx.builder.derived(
            refs, "%d variants, %d distinct option-value combinations"
                  % (len(variants), len(signatures)))]
    except EvidenceError:
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
    reserved = [c for c in gathered.stated if _norm(c.value) in RESERVED_OPTION_NAMES]
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
DISPATCH = {
    "IDENT.IDENTIFIER_PRESENT": check_identifier_present,
    "VARIANT.DIFFERENTIATED": check_variant_differentiated,
    "VARIANT.OPTION_NAMES_MEANINGFUL": check_option_names,
    "VARIANT.OPTION_VALUES_CONSISTENT": check_option_values,
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
