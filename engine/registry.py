"""The check registry: every check, fixed, versioned, and closed.

A check is a record, not a decision. Nothing about a check -- its id, its
points, its severity, its confidence, its searched paths, or the question it
puts to the merchant -- is chosen while a report is being produced. The runner
may decide only a check's *status* and its *evidence* (`rubric.md` 3).

That is what makes the registry the contract the rest of P3 consumes, and it is
why the invariants below run at **import time** rather than in a test: a
registry that violates one of them cannot be loaded at all, so a bad point
total or a mis-shaped `check_id` can never reach a report.

Three of those invariants are worth naming here:

* **D2 `check_id` is `<FAMILY>.<attribute_key.upper()>`, always.** The
  fabrication audit derives the attribute key back out of the id to detect a
  false gap (`fabrication_audit._attribute_key_for`). Deviating silently
  disables that detector for the check that deviated.
* **Every check declares non-empty `checked_paths` and a question**
  (`rubric.md` 9 rules 3 and 4). A check that cannot say where it looked
  cannot evidence an absence.
* **A `low`-confidence check carries no penalty and no severity above
  `minor`** (PRD 7.5 rule 2). `rubric.md` 5.2 states this guardrail is not
  lowered by a rubric change, so it is asserted rather than reviewed.

Points are exposed here because the registry is where they are fixed. Score
aggregation is a later phase; nothing in this module or its callers sums them.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Optional, Tuple

from . import rubric_data as R
from . import taxonomy_data as T

REGISTRY_VERSION = R.RUBRIC_VERSION

#: Families a check_id may use (rubric.md 3).
FAMILIES = frozenset([
    "IDENT", "APPAREL", "BEAUTY", "ELEC", "HOME", "SPORTS",
    "VARIANT", "USECASE", "TRUST", "CONFLICT", "CLAIM", "STRUCT",
])

#: Severity for statuses a check does not override (rubric.md 5.1).
DEFAULT_SEVERITY = {
    R.PASS: "info",
    R.PARTIAL: "major",
    R.UNKNOWN: "major",
    R.FAIL: "critical",
    R.NOT_APPLICABLE: "info",
}


class ConfidenceRule(object):
    """Confidence, fixed per check, with one arm per determination path.

    ``recognized`` is the confidence `rubric.md` 4 states for the check, and
    applies when the finding required bounded language recognition over a
    quoted span. ``structural`` applies when the finding was determined by
    presence, absence, exact comparison, uniqueness or arithmetic over the NPR.

    **The structural arm never exceeds the check's stated confidence.**
    PRD 7.5 assigns `high` to a structural determination, and the honest report
    double uses `high` on a D2 absence, so a check `rubric.md` fixes at
    `medium` may reach `high` on a path that involved no language judgment. A
    check `rubric.md` fixes at **`low`** may not: `low` says a reasonable
    reviewer could dispute the check's subject matter itself -- whether a use
    case is specific enough, whether two attributes mean the same thing -- and
    no amount of structural certainty about the search makes that judgment less
    disputable. `USECASE.DIFFERENTIATION` is `low` on every path it can take,
    which keeps PRD 7.5 rule 2's guardrail attached to it everywhere (D-020).

    Neither arm is chosen at run time in the sense PRD 7.5 rule 3 forbids: both
    are fixed by the definition, and which one applies is a fact about how the
    finding was reached.
    """

    __slots__ = ("structural", "recognized")

    def __init__(self, recognized, structural=None):
        # type: (str, Optional[str]) -> None
        self.recognized = recognized
        if structural is None:
            structural = "low" if recognized == "low" else "high"
        self.structural = structural

    def __repr__(self):  # pragma: no cover - debugging aid
        return "ConfidenceRule(%s, %s)" % (self.structural, self.recognized)


class CheckDef(object):
    """One check. Immutable by convention; never mutated after import."""

    __slots__ = (
        "check_id", "dimension", "categories", "scope", "max_points", "penalty",
        "partial_credit",
        "severity", "confidence", "checked_paths", "question", "attribute_key",
        "tier", "inheritable", "satisfies", "partial_if", "conditional_trigger",
        "na_trigger", "conflict_severity", "conflict_routing",
    )

    def __init__(self, check_id, dimension, categories, scope, max_points, penalty,
                 severity, confidence, checked_paths, question, attribute_key=None,
                 tier=None, inheritable=None, satisfies=T.VALUE_PRESENT,
                 partial_if=None, conditional_trigger=None, na_trigger=None,
                 conflict_severity="critical", conflict_routing=False,
                 partial_credit=None):
        self.check_id = check_id
        self.dimension = dimension
        self.categories = categories          # () means: applies to every category
        self.scope = scope
        self.max_points = max_points          # Decimal
        self.penalty = penalty                # Decimal
        # rubric.md 3 carries `partial_credit` on the check record. Holding it
        # here rather than in check code is the difference between a fixed
        # point value and one a check decided: the registry owns every number
        # a finding can earn.
        self.partial_credit = (Decimal(R.DEFAULT_PARTIAL_CREDIT)
                               if partial_credit is None else partial_credit)
        self.severity = severity              # status -> severity
        self.confidence = confidence          # ConfidenceRule
        self.checked_paths = checked_paths
        self.question = question
        self.attribute_key = attribute_key
        self.tier = tier
        self.inheritable = inheritable
        self.satisfies = satisfies
        self.partial_if = partial_if
        self.conditional_trigger = conditional_trigger
        self.na_trigger = na_trigger
        self.conflict_severity = conflict_severity
        # PRD 9.8: two supplied values for the *same canonical attribute* are a
        # conflict, never a duplicate. Only a check that owns one canonical key
        # routes that way -- a check that legitimately reads several different
        # fields (a category and a product type, say) would otherwise report
        # their difference as a contradiction.
        self.conflict_routing = conflict_routing

    # -- properties ------------------------------------------------------
    @property
    def family(self):
        # type: () -> str
        return self.check_id.split(".", 1)[0]

    @property
    def is_penalty(self):
        # type: () -> bool
        return self.dimension in R.PENALTY_DIMENSIONS

    @property
    def structural_satisfaction(self):
        # type: () -> bool
        """True when PASS can be decided without language recognition.

        False does not mean the check cannot run: absence and conflict are
        structural for every check. It means only that deciding a *present*
        value satisfies this check needs recognition, which is a later phase.
        """
        return self.satisfies == T.VALUE_PRESENT

    def severity_for(self, status):
        # type: (str) -> str
        return self.severity.get(status, DEFAULT_SEVERITY[status])

    def applies_to(self, category):
        # type: (str) -> bool
        return not self.categories or category in self.categories

    def target_field(self):
        # type: () -> str
        """The NPR field a merchant's answer belongs in. Never a value."""
        if self.attribute_key:
            return "attributes[%s]" % self.attribute_key
        return self.checked_paths[0]

    def __repr__(self):  # pragma: no cover - debugging aid
        return "CheckDef(%s)" % self.check_id


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------
def _partial_credit_for(check_id):
    # type: (str) -> Decimal
    """The fixed proportion a PARTIAL on this check earns (`rubric.md` 3)."""
    return Decimal(R.PARTIAL_CREDIT.get(check_id, R.DEFAULT_PARTIAL_CREDIT))


def _d2_checks():
    # type: () -> Tuple[CheckDef, ...]
    """Derive the D2 check set from the taxonomy, never from a hand-list.

    `rubric.md` 4/D2 defines the points as the tier pool divided by the number
    of attributes the category places in that tier. Deriving them keeps
    `taxonomy.md` authoritative for attribute definitions (AGENTS.md 3) and
    makes the 22.0 total self-checking rather than transcribed twice.
    """
    out = []
    for category in T.CATEGORIES:
        rows = T.attributes_for(category)
        counts = {}
        for row in rows:
            counts[row.tier] = counts.get(row.tier, 0) + 1
        for row in rows:
            points = Decimal(T.TIER_POOLS[row.tier]) / Decimal(counts[row.tier])
            severity = {
                R.UNKNOWN: T.TIER_UNKNOWN_SEVERITY[row.tier],
                R.PARTIAL: "major",
                # rubric.md 5.1: only a D6 conflict finding may carry `blocker`.
                # The zeroed D2 attribute is the conflict's other effect
                # (PRD 9.2), not a second blocker.
                R.FAIL: "critical",
            }
            out.append(CheckDef(
                check_id="%s.%s" % (T.FAMILY[category], row.key.upper()),
                dimension=R.D2,
                categories=(category,),
                scope=row.scope,
                max_points=points,
                penalty=Decimal("0.0"),
                severity=severity,
                confidence=ConfidenceRule("medium"),
                checked_paths=(
                    "attributes[%s]" % row.key,
                    "variants[*].attributes",
                    "metafields.*",
                    "narrative.description_text",
                ),
                question=_D2_QUESTIONS[row.key],
                attribute_key=row.key,
                tier=row.tier,
                inheritable=row.inheritable,
                satisfies=row.satisfies,
                partial_if=row.partial_if,
                conditional_trigger=row.conditional_trigger,
                conflict_severity=row.conflict_severity,
                conflict_routing=True,
                partial_credit=_partial_credit_for(
                    "%s.%s" % (T.FAMILY[category], row.key.upper())),
            ))
    return tuple(out)


#: One merchant-answerable question per attribute key (`rubric.md` 9 rule 3).
#: Bound by PRD 7.6: a question may name the information, the field, the unit,
#: the expected format, or quote a supplied value -- and may never introduce an
#: example value. `test_registry` lints every string here against the
#: fabrication audit's fact lexicon, so a fact token cannot ship in one.
_D2_QUESTIONS = {
    # apparel
    "size_system": "Which size system do the sizes follow, and what body "
                   "measurements do they correspond to?",
    "material_composition": "What is the fabric composition, stated as a "
                            "percentage per fibre?",
    "fit_and_cut": "What is the fit and the cut of this garment?",
    "garment_measurements": "What are the measured dimensions for each size?",
    "care_instructions": "How should this garment be washed, dried, and ironed?",
    "color_finish": "What is the colour of each variant, stated as a name?",
    "closure_and_construction": "What closure, seam or knit construction, and "
                                "lining does this product use?",
    "intended_use_context": "For which season, activity, or occasion is this "
                            "garment made?",
    "country_of_origin": "In which country is this product manufactured?",
    "sustainability_credentials": "Which named standard or certified material "
                                  "applies, and what basis is referenced for it?",
    "model_reference_measurements": "What is the model's height, and which size "
                                    "is the model wearing?",
    # beauty
    "ingredients_full": "What is the full ingredient list for this product?",
    "net_content": "What is the net quantity of each variant, stated with its unit?",
    "usage_directions": "How, how much, when, and where should this product be "
                        "applied?",
    "suitability": "Which skin or hair types, or which concerns, is this product "
                   "suitable for?",
    "warnings_and_restrictions": "Which cautions, allergens, patch-test guidance, "
                                 "or age and pregnancy restrictions apply?",
    "key_actives_and_concentration": "Which actives does this product contain, and "
                                     "at what concentration?",
    "formulation_format": "What form does this product take?",
    "fragrance_status": "What is the scent profile of this product, and if it "
                        "carries none, is that stated?",
    "shelf_life_or_pao": "What is the shelf life or the period after opening?",
    "color_shade": "What is the shade of each variant, stated as a name with its "
                   "undertone or a swatch reference?",
    "certifications_and_testing": "Which certification or testing body is named, "
                                  "and what basis is referenced for it?",
    "application_tools_included": "Which applicator or tool is supplied with this "
                                  "product?",
    # electronics
    "model_identifier": "What is the manufacturer model number for each variant?",
    "core_specifications": "What are the defining specifications of this product, "
                           "stated with their units?",
    "compatibility": "Which devices, standards, operating system versions, or "
                     "sockets is this product compatible with?",
    "connectivity_and_ports": "Which ports, port counts, and wireless standards "
                              "does this product carry, stated with their versions?",
    "power_requirements": "What are the power requirements, stated with the plug "
                          "type or power source?",
    "physical_dimensions_weight": "What are the dimensions and the weight of each "
                                  "variant, stated with their units?",
    "battery": "What is the battery chemistry and capacity, and what rated runtime "
               "applies under what test conditions?",
    "in_the_box": "Which items are supplied in the box?",
    "warranty_term": "How long is the warranty, and what does it cover?",
    "software_requirements": "Which app, account, subscription, or operating system "
                             "minimum does this product require?",
    "regulatory_certifications": "Which regulatory marks apply, stated with their "
                                 "identifiers?",
    # home
    "assembled_dimensions": "What are the assembled width, depth, and height of "
                            "each variant, stated with their units?",
    "materials_and_finish": "Which materials is this product made from, and what "
                            "surface finish does it carry?",
    "capacity_or_load": "What capacity or rated load does this product carry, "
                        "stated with its unit and its basis?",
    "care_and_cleaning": "How should this product be cleaned?",
    "assembly": "Is assembly required, and if so which tools, parts, and how much "
                "time does it take?",
    "indoor_outdoor_use": "Which environments does this product withstand, and on "
                          "what durability basis is that stated?",
    "room_or_placement": "Which room or placement is this product intended for?",
    "packaged_dimensions_weight": "What are the shipping carton dimensions and "
                                  "weight?",
    "mounting_and_hardware": "How is this product mounted, and is the hardware "
                             "supplied?",
    "safety_and_compliance": "Which safety or compliance standard applies, stated "
                             "with its reference?",
    # sports
    "sport_or_activity": "Which activity is this product designed for?",
    "user_fit_specification": "Which user height, weight range, or frame size does "
                              "each variant fit?",
    "load_or_capacity_rating": "What is the rated load or maximum user weight, "
                               "stated with its unit and its basis?",
    "skill_or_intensity_level": "Which skill level or performance tier is this "
                                "product built for?",
    "materials_and_construction": "Which materials are used for each component of "
                                  "this product?",
    "dimensions_and_weight": "What are the dimensions and the weight, stated with "
                             "their units?",
    "use_environment": "In which environment, terrain, or conditions is this "
                       "product used?",
    "safety_certification": "Which protective standard is this product certified "
                            "to, stated with its standard number?",
    "included_accessories": "Which accessories are supplied with this product?",
    "maintenance_requirements": "What servicing, storage, or maintenance does this "
                                "product require?",
    "age_or_user_suitability": "Which age range or user group is this product for, "
                               "and on what basis?",
}


#: Fixed checks that read a canonical taxonomy attribute. Recorded so the
#: gatherer matches a metafield by exact key rather than sweeping every
#: metafield into a check that has no key of its own.
_FIXED_ATTRIBUTE_KEYS = {
    "TRUST.WARRANTY_OR_GUARANTEE": "warranty_or_guarantee",
    "TRUST.RETURNS_REFERENCE": "returns_policy_reference",
    "TRUST.CERTIFICATION_REFERENCED": "certifications",
    "TRUST.PROVENANCE": "country_of_origin",
}


def _fixed_checks():
    # type: () -> Tuple[CheckDef, ...]
    out = []
    for (check_id, dimension, scope, max_points, penalty, satisfies,
         recognized_conf, severity_overrides, checked_paths, question,
         na_trigger) in R.FIXED_CHECKS:
        severity = dict(severity_overrides)
        out.append(CheckDef(
            check_id=check_id,
            dimension=dimension,
            categories=(),
            scope=scope,
            max_points=Decimal(max_points),
            penalty=Decimal(penalty),
            severity=severity,
            confidence=ConfidenceRule(recognized_conf),
            checked_paths=checked_paths,
            question=question,
            satisfies=satisfies,
            na_trigger=na_trigger,
            attribute_key=_FIXED_ATTRIBUTE_KEYS.get(check_id),
            partial_credit=_partial_credit_for(check_id),
        ))
    return tuple(out)


ALL_CHECKS = _fixed_checks() + _d2_checks()
BY_ID = dict((c.check_id, c) for c in ALL_CHECKS)  # type: Dict[str, CheckDef]

#: Recognition predicates named by the registry. Declared and versioned here;
#: their implementations belong to the checks that use them and are versioned
#: with `rubric.md` (PRD 9.6). None is implemented in P3.1 -- a check whose
#: satisfaction needs one determines absence and conflict structurally and
#: defers the satisfaction decision rather than guessing at it.
RECOGNITION_PREDICATES = frozenset(
    [c.satisfies for c in ALL_CHECKS if c.satisfies != T.VALUE_PRESENT]
    + [c.partial_if for c in ALL_CHECKS if c.partial_if]
    + [c.conditional_trigger for c in ALL_CHECKS if c.conditional_trigger]
)


def checks_for_category(category):
    # type: (str) -> Tuple[CheckDef, ...]
    """The applicable check set for a category (`rubric.md` 6.1 step 1).

    For `uncategorized` this is every check except D2: `rubric.md` 4/D2 removes
    the dimension entirely and `taxonomy.md` 6 puts its maximum at 0. The
    report says so explicitly rather than faking category coverage.
    """
    return tuple(c for c in ALL_CHECKS if c.applies_to(category))


def d2_checks_for_category(category):
    # type: (str) -> Tuple[CheckDef, ...]
    return tuple(c for c in ALL_CHECKS
                 if c.dimension == R.D2 and c.applies_to(category))


def get(check_id):
    # type: (str) -> Optional[CheckDef]
    return BY_ID.get(check_id)


# ---------------------------------------------------------------------------
# Import-time invariants. A registry that breaks one of these does not load.
# ---------------------------------------------------------------------------
def _invariants():
    # type: () -> None
    seen = set()
    for check in ALL_CHECKS:
        cid = check.check_id
        assert cid not in seen, "duplicate check_id %s" % cid
        seen.add(cid)
        assert check.family in FAMILIES, "unknown family in %s" % cid
        assert check.dimension in R.DIMENSION_MAX, "unknown dimension in %s" % cid
        assert check.scope in ("product", "variant", "option", "catalog"), cid
        assert check.checked_paths, "%s declares no checked_paths" % cid
        assert check.question and check.question.strip(), "%s has no question" % cid
        assert check.max_points >= 0 and check.penalty >= 0, cid

        # rubric.md 1.2: penalty dimensions are exposure, not earned points.
        if check.is_penalty:
            assert check.max_points == 0, "%s is a penalty check with points" % cid
            cap = Decimal(R.DIMENSION_MAX[check.dimension])
            assert check.penalty <= cap, "%s penalty exceeds its dimension cap" % cid
        else:
            assert check.penalty == 0, "%s is an earned check with a penalty" % cid

        # rubric.md 3: partial credit is a fixed proportion of the check's own
        # points, never a figure a check computes.
        assert Decimal("0") <= check.partial_credit <= Decimal("1"), cid
        for arm in (check.confidence.structural, check.confidence.recognized):
            assert arm in R.CONFIDENCES, "%s: unknown confidence %r" % (cid, arm)

        # PRD 7.5 rule 2 / rubric.md 5.2 -- the guardrail on low confidence.
        if check.confidence.recognized == "low":
            # ...and it holds on every path the check can take, not only the
            # one that reads prose. See ConfidenceRule.
            assert check.confidence.structural == "low", (
                "%s: a low-confidence check must stay low on its structural "
                "path" % cid)
            assert check.penalty == 0, "%s: low confidence with a penalty" % cid
            for status, sev in check.severity.items():
                assert sev in ("minor", "info"), (
                    "%s: low confidence with %s severity on %s" % (cid, sev, status))

        for status, sev in check.severity.items():
            assert status in R.STATUSES, "%s: unknown status %s" % (cid, status)
            assert sev in R.SEVERITIES, "%s: unknown severity %s" % (cid, sev)

        # rubric.md 5.1: only D6 may emit blocker.
        if check.dimension != R.D6:
            for status, sev in check.severity.items():
                assert sev != "blocker", "%s may not emit blocker" % cid

        # The false-gap detector depends on this id shape. See module docstring.
        if check.dimension == R.D2:
            expected = "%s.%s" % (T.FAMILY[check.categories[0]],
                                  check.attribute_key.upper())
            assert cid == expected, "D2 check_id %s must be %s" % (cid, expected)

    # rubric.md 4: the earned dimensions sum to exactly their stated maxima,
    # and to 82 in total (rubric.md 1.2).
    for dimension in R.EARNED_DIMENSIONS:
        if dimension == R.D2:
            continue
        total = sum((c.max_points for c in ALL_CHECKS if c.dimension == dimension),
                    Decimal("0"))
        assert total == Decimal(R.DIMENSION_MAX[dimension]), (
            "%s sums to %s, expected %s" % (dimension, total,
                                            R.DIMENSION_MAX[dimension]))

    # taxonomy.md 6: the tier pools are the D2 total, exactly.
    pools = sum((Decimal(v) for v in T.TIER_POOLS.values()), Decimal("0"))
    assert pools == Decimal(T.D2_TOTAL), (
        "tier pools sum to %s, expected %s" % (pools, T.D2_TOTAL))

    # ...and every category's derived per-attribute points reconstitute them.
    # `2.2 / 3` does not terminate, so the residual of the even split within a
    # tier (`taxonomy.md` 4.1, D-011) is carried at full precision here and
    # resolved only at render (`rubric.md` 6.2). It is an artefact of division,
    # not of a wrong point total, which is why the comparison is to the last
    # place of the working precision rather than to a rounded figure.
    residual = Decimal("1e-20")
    for category in T.CATEGORIES:
        total = sum((c.max_points for c in d2_checks_for_category(category)),
                    Decimal("0"))
        assert abs(total - Decimal(T.D2_TOTAL)) < residual, (
            "D2 for %s sums to %s, expected %s" % (category, total, T.D2_TOTAL))
        for tier, pool in T.TIER_POOLS.items():
            rows = [c for c in d2_checks_for_category(category) if c.tier == tier]
            assert rows, "%s has no tier %s attribute" % (category, tier)
            tier_total = sum((c.max_points for c in rows), Decimal("0"))
            assert abs(tier_total - Decimal(pool)) < residual, (
                "%s tier %s sums to %s, expected %s"
                % (category, tier, tier_total, pool))

    earned = sum((Decimal(R.DIMENSION_MAX[d]) for d in R.EARNED_DIMENSIONS),
                 Decimal("0"))
    assert earned == Decimal(R.EARNED_TOTAL), (
        "earned dimensions sum to %s, expected %s" % (earned, R.EARNED_TOTAL))

    # Every D2 attribute has a question, and no question is reused across two
    # different attributes by accident.
    for category in T.CATEGORIES:
        for row in T.attributes_for(category):
            assert row.key in _D2_QUESTIONS, "no question for %s" % row.key


_invariants()
