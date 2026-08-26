"""Machine-readable transcription of ``product/rubric.md``.

Every number here is copied from `rubric.md` 4, which is normative for scoring
(AGENTS.md 3). Nothing in this module is computed from anything except the
tier pools of `taxonomy.md` 6, and nothing here is decided at run time: a check
carries fixed points, a fixed severity per status, and a fixed confidence per
determination path (`rubric.md` 5, PRD 7.5 rule 3).

Two conventions that are easy to misread:

* **Penalty dimensions carry no earned points.** D6 and D7 are penalty
  exposure (`rubric.md` 1.2), so their checks have ``max_points`` of 0 and a
  fixed ``penalty``. The stated dimension maximum is a cap on the total each
  dimension may subtract, not a sum of its checks -- the individual penalties
  deliberately add to more than the cap.
* **Confidence has two arms**, not one. PRD 7.5 assigns `high` to a
  structural presence/absence determination and `medium` to bounded language
  recognition over a quoted span, while `rubric.md` 5.2 requires confidence to
  be fixed per check rather than improvised. A two-armed rule satisfies both:
  the arms are fixed by the definition, and which arm applies is decided by how
  the finding was determined, never by how sure the tool feels.
"""

from __future__ import annotations

from .taxonomy_data import VALUE_PRESENT

RUBRIC_VERSION = "0.9"

# -- rubric.md 2 -------------------------------------------------------------
D1, D2 = "D1_identity", "D2_category_attributes"
D3, D4, D5 = "D3_variant", "D4_usecase", "D5_trust"
D6, D7, D8 = "D6_consistency", "D7_claims", "D8_structure"

DIMENSION_MAX = {
    D1: "15.0", D2: "22.0", D3: "15.0", D4: "12.0", D5: "12.0",
    D6: "10.0", D7: "8.0", D8: "6.0",
}
#: Dimensions that contribute to `raw_max` (rubric.md 1.2: they total 82).
EARNED_DIMENSIONS = (D1, D2, D3, D4, D5, D8)
PENALTY_DIMENSIONS = (D6, D7)
EARNED_TOTAL = "82.0"

DIMENSION_ORDER = (D1, D2, D3, D4, D5, D6, D7, D8)

# -- rubric.md 6.4 -----------------------------------------------------------
GRADE_BANDS = (
    ("agent_ready", 90), ("strong", 75), ("adequate", 60), ("weak", 40),
    ("insufficient", 0),
)

# -- rubric.md 3.1 -----------------------------------------------------------
PASS, PARTIAL, UNKNOWN, FAIL, NOT_APPLICABLE = (
    "PASS", "PARTIAL", "UNKNOWN", "FAIL", "NOT_APPLICABLE")
STATUSES = (PASS, PARTIAL, UNKNOWN, FAIL, NOT_APPLICABLE)

SEVERITIES = ("blocker", "critical", "major", "minor", "info")
CONFIDENCES = ("high", "medium", "low")

#: PRD 9.3 and `rubric.md` 3.1: an ambiguous-but-present value earns half its
#: check's points unless the check declares otherwise. It is a fixed property
#: of a check, so it lives here beside the points rather than in check code.
DEFAULT_PARTIAL_CREDIT = "0.5"

#: Per-check overrides of `DEFAULT_PARTIAL_CREDIT`. Empty in rubric version 0.1:
#: `rubric.md` 4 states no per-check figure, and inventing one would be a
#: scoring change without a rubric version bump.
PARTIAL_CREDIT = {}

#: Structural triggers that remove a check from numerator and denominator
#: (`taxonomy.md` 4.4, `rubric.md` 4/D3). A trigger is structural, never
#: assumed: a check is never NOT_APPLICABLE because information is missing.
NA_SINGLE_VARIANT = "single_variant"
NA_NO_CATEGORY = "no_category_assigned"
#: D-029. The category requires nothing per variant, so there is no
#: per-variant requirement for a variant to have failed. Covers both ways
#: the set can be empty: an assigned category whose `taxonomy.md` 5 set holds
#: no non-inheritable variant-scope row, and `uncategorized`, which holds no
#: rows at all. The reason string names which, because they are different
#: facts about the record.
NA_EMPTY_VARIANT_SCOPE_SET = "no_variant_scope_attribute"

# ---------------------------------------------------------------------------
# Fixed checks, verbatim from rubric.md 4
# ---------------------------------------------------------------------------
# Row shape:
#   (check_id, dimension, scope, max_points, penalty, satisfies,
#    recognized_confidence, severity_overrides, checked_paths, question,
#    na_trigger)
#
# `severity_overrides` supplies the per-status severities that differ from the
# defaults in `registry.DEFAULT_SEVERITY`.

FIXED_CHECKS = (
    # -- D1, rubric.md 4/D1 (15.0) ------------------------------------------
    ("IDENT.TITLE_SPECIFIC", D1, "product", "4.0", "0.0",
     "title_names_product_type", "medium",
     {UNKNOWN: "critical", PARTIAL: "major"},
     ("identity.title",),
     "What kind of product is this, stated as a product type in the title?",
     None),
    ("IDENT.TITLE_DISTINGUISHING", D1, "product", "2.0", "0.0",
     "title_carries_distinguishing_attribute", "medium",
     {UNKNOWN: "major", PARTIAL: "major"},
     ("identity.title",),
     "Which distinguishing attribute of this product belongs in the title?",
     None),
    ("IDENT.BRAND_PRESENT", D1, "product", "2.0", "0.0",
     VALUE_PRESENT, "high",
     {UNKNOWN: "critical"},
     ("identity.brand",),
     "Which brand or vendor should be recorded for this product?",
     None),
    ("IDENT.PRODUCT_TYPE_OR_CATEGORY", D1, "product", "2.5", "0.0",
     VALUE_PRESENT, "high",
     {UNKNOWN: "major"},
     ("identity.declared_category", "identity.product_type"),
     "Which product category or product type should be set for this product?",
     None),
    ("IDENT.IDENTIFIER_PRESENT", D1, "variant", "2.0", "0.0",
     VALUE_PRESENT, "high",
     {UNKNOWN: "major", PARTIAL: "major"},
     ("variants[*].sku", "variants[*].barcode", "identity.model_or_mpn"),
     "Which stock keeping unit, barcode, or manufacturer part number applies to "
     "each variant?",
     None),
    ("IDENT.DESCRIPTION_SUBSTANCE", D1, "product", "2.5", "0.0",
     "three_informational_statements", "medium",
     {UNKNOWN: "critical", PARTIAL: "major"},
     ("narrative.description_text", "narrative.description_html"),
     "Which factual statements about this product belong in the description?",
     None),

    # -- D3, rubric.md 4/D3 (15.0) ------------------------------------------
    ("VARIANT.DIFFERENTIATED", D3, "product", "5.0", "0.0",
     VALUE_PRESENT, "high",
     {FAIL: "critical", UNKNOWN: "critical"},
     ("variants[*].option_values", "options[*]"),
     "Which option value distinguishes each variant from the others?",
     NA_SINGLE_VARIANT),
    ("VARIANT.OPTION_NAMES_MEANINGFUL", D3, "option", "2.0", "0.0",
     VALUE_PRESENT, "high",
     {FAIL: "major", UNKNOWN: "major"},
     ("options[*].name",),
     "What does each option name refer to, stated as the attribute it varies?",
     None),
    ("VARIANT.OPTION_VALUES_CONSISTENT", D3, "option", "2.0", "0.0",
     VALUE_PRESENT, "high",
     {FAIL: "major"},
     ("options[*].values",),
     "Which single convention should the values of each option follow?",
     NA_SINGLE_VARIANT),
    ("VARIANT.ATTRIBUTE_COVERAGE", D3, "variant", "3.0", "0.0",
     "variant_scope_attributes_covered", "high",
     {UNKNOWN: "major", PARTIAL: "major"},
     ("variants[*].attributes",),
     "Which variant-scope attribute values apply to each variant?",
     (NA_SINGLE_VARIANT, NA_EMPTY_VARIANT_SCOPE_SET)),
    ("VARIANT.IDENTIFIER_UNIQUE", D3, "variant", "1.5", "0.0",
     VALUE_PRESENT, "high",
     {FAIL: "critical", UNKNOWN: "major"},
     ("variants[*].sku", "variants[*].barcode"),
     "Which distinct identifier applies to each variant?",
     None),
    ("VARIANT.MEDIA_LINKED", D3, "variant", "1.5", "0.0",
     "visual_variants_have_media", "medium",
     {UNKNOWN: "minor", PARTIAL: "minor"},
     ("variants[*].media_refs", "media[*]"),
     "Which image belongs to each visually distinct variant?",
     NA_SINGLE_VARIANT),

    # -- D4, rubric.md 4/D4 (12.0) ------------------------------------------
    ("USECASE.INTENDED_USER", D4, "product", "3.0", "0.0",
     "intended_user_stated", "medium", {UNKNOWN: "major"},
     ("narrative.description_text", "narrative.seo_description"),
     "Who is this product intended for, stated as a user or user context?",
     None),
    ("USECASE.PRIMARY_USE", D4, "product", "3.5", "0.0",
     "concrete_use_situation", "medium", {UNKNOWN: "major"},
     ("narrative.description_text", "narrative.seo_description"),
     "In what situation is this product used?",
     None),
    ("USECASE.DIFFERENTIATION", D4, "product", "2.5", "0.0",
     "factual_differentiator", "low", {UNKNOWN: "minor", PARTIAL: "minor"},
     ("narrative.description_text", "narrative.seo_description"),
     "Which factual difference separates this product from adjacent options?",
     None),
    ("USECASE.NOT_FOR", D4, "product", "1.5", "0.0",
     "stated_limitation", "medium", {UNKNOWN: "minor"},
     ("narrative.description_text", "narrative.seo_description"),
     "Which uses, users, or conditions is this product not suitable for?",
     None),
    ("USECASE.COMPLEMENTARY_CONTEXT", D4, "product", "1.5", "0.0",
     "complementary_context_stated", "low", {UNKNOWN: "minor"},
     ("narrative.description_text", "narrative.seo_description"),
     "What is this product used alongside, or what does it require?",
     None),

    # -- D5, rubric.md 4/D5 (12.0) ------------------------------------------
    ("TRUST.WARRANTY_OR_GUARANTEE", D5, "product", "3.0", "0.0",
     "warranty_with_duration_or_scope", "high", {UNKNOWN: "major"},
     ("attributes[warranty_or_guarantee]", "attributes[warranty_term]",
      "metafields.*", "narrative.description_text"),
     "What warranty or guarantee applies, stated with its duration and its scope?",
     None),
    ("TRUST.RETURNS_REFERENCE", D5, "product", "2.0", "0.0",
     "returns_terms_or_reference", "high", {UNKNOWN: "minor"},
     ("attributes[returns_policy_reference]", "metafields.*",
      "narrative.description_text"),
     "What are the returns or exchange terms, or where are they published?",
     None),
    ("TRUST.SHIPPING_OR_LEADTIME", D5, "product", "2.0", "0.0",
     "dispatch_or_leadtime_stated", "medium", {UNKNOWN: "minor"},
     ("narrative.description_text",),
     "What is the dispatch time or lead time for this product?",
     None),
    ("TRUST.SUPPORT_OR_CONTACT", D5, "product", "1.5", "0.0",
     "support_path_stated", "high", {UNKNOWN: "minor"},
     ("narrative.description_text",),
     "Where should a buyer go for support or documentation for this product?",
     None),
    ("TRUST.CERTIFICATION_REFERENCED", D5, "product", "2.0", "0.0",
     "named_body_or_standard_referenced", "medium", {UNKNOWN: "minor"},
     ("attributes[certifications]", "metafields.*", "narrative.description_text"),
     "Which certifying body, standard, or certificate identifier is referenced "
     "for this product?",
     None),
    ("TRUST.PROVENANCE", D5, "product", "1.5", "0.0",
     "origin_or_sourcing_stated", "high", {UNKNOWN: "minor"},
     ("attributes[country_of_origin]", "metafields.*",
      "narrative.description_text"),
     "In which country is this product manufactured or sourced?",
     None),

    # -- D6, rubric.md 4/D6 (penalty exposure, cap 10.0) --------------------
    ("CONFLICT.NUMERIC", D6, "product", "0.0", "3.0",
     "numeric_values_incompatible", "high", {FAIL: "critical"},
     ("attributes[*]", "variants[*].attributes", "metafields.*"),
     "Which of the supplied values quoted in the evidence is correct?",
     None),
    ("CONFLICT.CATEGORICAL", D6, "product", "0.0", "3.0",
     "categorical_values_incompatible", "medium", {FAIL: "critical"},
     ("attributes[*]", "variants[*].attributes", "metafields.*"),
     "Which of the supplied values quoted in the evidence is correct?",
     None),
    ("CONFLICT.CLAIM_VS_ATTRIBUTE", D6, "product", "0.0", "5.0",
     "claim_contradicted_by_attribute", "high", {FAIL: "critical"},
     ("claims[*]", "attributes[*]", "narrative.description_text"),
     "Which of the supplied statements quoted in the evidence is correct?",
     None),
    ("CONFLICT.VARIANT_VS_PRODUCT", D6, "variant", "0.0", "2.0",
     "variant_value_outside_product_assertion", "high", {FAIL: "critical"},
     ("variants[*].attributes", "variants[*].price", "attributes[*]"),
     "Which of the supplied values quoted in the evidence is correct?",
     None),
    ("CONFLICT.TITLE_VS_BODY", D6, "product", "0.0", "2.0",
     "title_contradicted_by_body", "medium", {FAIL: "critical"},
     ("identity.title", "narrative.description_text"),
     "Which of the supplied statements quoted in the evidence is correct?",
     None),
    # rubric.md 4/D6: info only, no penalty.
    ("CONFLICT.UNIT_INCONSISTENCY", D6, "product", "0.0", "0.0",
     "same_value_different_units", "high", {FAIL: "info"},
     ("attributes[*]", "variants[*].attributes", "metafields.*"),
     "Which unit should the values quoted in the evidence be stated in?",
     None),

    # -- D7, rubric.md 4/D7 (penalty exposure, cap 8.0) ---------------------
    ("CLAIM.UNSUPPORTED_SUPERLATIVE", D7, "product", "0.0", "1.5",
     "superlative_with_named_basis", "medium", {FAIL: "major"},
     ("claims[*]", "narrative.description_text", "identity.title"),
     "What named and dated basis supports the statement quoted in the evidence?",
     None),
    ("CLAIM.UNSUPPORTED_COMPARATIVE", D7, "product", "0.0", "2.0",
     "comparative_with_target_and_basis", "medium", {FAIL: "major"},
     ("claims[*]", "narrative.description_text", "identity.title"),
     "What is the comparison target and the measurement basis for the statement "
     "quoted in the evidence?",
     None),
    ("CLAIM.UNSUPPORTED_CERTIFICATION", D7, "product", "0.0", "3.0",
     "certification_with_named_body", "medium", {FAIL: "major"},
     ("claims[*]", "narrative.description_text", "identity.title"),
     "Which body, standard, or certificate identifier supports the statement "
     "quoted in the evidence?",
     None),
    ("CLAIM.UNSUPPORTED_EFFICACY", D7, "product", "0.0", "2.5",
     "efficacy_with_referenced_study", "medium", {FAIL: "major"},
     ("claims[*]", "narrative.description_text", "identity.title"),
     "Which study, test, or stated qualifier supports the statement quoted in "
     "the evidence?",
     None),
    # rubric.md 4/D7 rule 5: `low` confidence may carry no penalty (PRD 7.5
    # rule 2), so its nominal 1.5/0.5 is recorded as info with penalty 0.0 in
    # V0. Deliberate, and not an inconsistency.
    ("CLAIM.VAGUE_QUALIFIER", D7, "product", "0.0", "0.0",
     "qualifier_with_stated_conditions", "low", {FAIL: "info"},
     ("claims[*]", "narrative.description_text", "identity.title"),
     "Under what stated conditions does the figure quoted in the evidence hold?",
     None),

    # -- D8, rubric.md 4/D8 (6.0) -------------------------------------------
    ("STRUCT.ATTRIBUTES_IN_FIELDS", D8, "product", "2.5", "0.0",
     VALUE_PRESENT, "high", {UNKNOWN: "minor", PARTIAL: "minor"},
     ("attributes[*]", "variants[*].attributes", "metafields.*"),
     "Which of the attributes stated in prose should also be held in a "
     "structured field?",
     None),
    ("STRUCT.DESCRIPTION_PARSEABLE", D8, "product", "1.0", "0.0",
     VALUE_PRESENT, "high", {UNKNOWN: "minor", FAIL: "minor"},
     ("narrative.structure",),
     "Which parts of the description belong in a list, a table, or under a "
     "heading?",
     None),
    ("STRUCT.MEDIA_ALT_TEXT", D8, "product", "1.0", "0.0",
     VALUE_PRESENT, "high", {UNKNOWN: "minor", PARTIAL: "minor"},
     ("media[*].alt",),
     "What does each image show, stated as alt text?",
     None),
    ("STRUCT.SEO_FIELDS_POPULATED", D8, "product", "0.5", "0.0",
     VALUE_PRESENT, "high", {UNKNOWN: "minor", PARTIAL: "minor"},
     ("narrative.seo_title", "narrative.seo_description"),
     "What should the search engine listing title and description hold?",
     None),
    ("STRUCT.NO_PLACEHOLDER_VALUES", D8, "product", "1.0", "0.0",
     VALUE_PRESENT, "high", {FAIL: "minor"},
     ("identity.*", "narrative.description_text", "attributes[*]",
      "variants[*].attributes", "metafields.*"),
     "What value should replace each placeholder quoted in the evidence?",
     None),
)
