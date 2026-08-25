"""Machine-readable transcription of ``product/taxonomy.md``.

Transcribed, never derived. `taxonomy.md` is authoritative (AGENTS.md 3); this
module is the copy the check registry reads, and every row here corresponds to
a row of `taxonomy.md` 5.1-5.5 plus the mapping table of 8.

Five properties travel with every attribute, because each one changes what a
check may conclude:

``tier``          A/B/C -- drives the D2 point split (`taxonomy.md` 4.1, 6).
``scope``         product | variant (4.2).
``inheritable``   whether a product-scope value satisfies a variant
                  requirement (4.3). Non-inheritable keys are the ones where
                  inheriting would let a merchant appear to hold per-variant
                  data they do not hold.
``satisfies``     the named predicate that decides PASS. ``VALUE_PRESENT`` is
                  structural -- the taxonomy row states no PARTIAL condition,
                  so any stated value satisfies it. Any other id names a
                  *recognition* predicate transcribed from the "Satisfied by"
                  column; those are declared here and are not implemented in
                  P3.1 (see ``registry.RECOGNITION_PREDICATES``).
``partial_if``    the recognition predicate from the "PARTIAL if" column.

``conflict_severity`` is the severity a D6 conflict on this key carries: PRD
9.2 makes it `blocker` where the attribute is safety-, allergen-,
compatibility- or compliance-relevant for the category, `critical` otherwise.
That relevance is a per-attribute product judgment, so it is recorded per row
rather than guessed at run time.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

TAXONOMY_VERSION = "0.1"

#: The satisfies-predicate that needs no language recognition: the taxonomy row
#: declares no PARTIAL condition, so a stated non-placeholder value satisfies.
VALUE_PRESENT = "value_present"

TIER_A, TIER_B, TIER_C = "A", "B", "C"
SCOPE_PRODUCT, SCOPE_VARIANT = "product", "variant"

#: taxonomy.md 4.1 -- the D2 pools, split evenly within a tier (D-011).
TIER_POOLS = {TIER_A: "13.2", TIER_B: "6.6", TIER_C: "2.2"}
D2_TOTAL = "22.0"

#: rubric.md 5.1 -- severity of an UNKNOWN, by tier.
TIER_UNKNOWN_SEVERITY = {TIER_A: "critical", TIER_B: "major", TIER_C: "minor"}


class Attribute(object):
    """One row of a `taxonomy.md` 5.x table."""

    __slots__ = ("key", "tier", "scope", "inheritable", "satisfies", "partial_if",
                 "conditional_trigger", "conflict_severity")

    def __init__(self, key, tier, scope, inheritable, satisfies, partial_if=None,
                 conditional_trigger=None, conflict_severity="critical"):
        # type: (str, str, str, bool, str, Optional[str], Optional[str], str) -> None
        self.key = key
        self.tier = tier
        self.scope = scope
        self.inheritable = inheritable
        self.satisfies = satisfies
        self.partial_if = partial_if
        self.conditional_trigger = conditional_trigger
        self.conflict_severity = conflict_severity

    @property
    def structural(self):
        # type: () -> bool
        """True when PASS can be decided without language recognition."""
        return self.satisfies == VALUE_PRESENT

    def __repr__(self):  # pragma: no cover - debugging aid
        return "Attribute(%s, %s, %s)" % (self.key, self.tier, self.scope)


A = Attribute  # local shorthand; the tables below are the readable form

# -- taxonomy.md 5.1 ---------------------------------------------------------
APPAREL = (
    A("size_system", TIER_A, SCOPE_VARIANT, False,
      "named_size_standard_with_value", "bare_size_label"),
    A("material_composition", TIER_A, SCOPE_PRODUCT, True,
      "material_with_proportions", "material_without_proportions"),
    A("fit_and_cut", TIER_A, SCOPE_PRODUCT, True,
      "fit_descriptor_with_cut", "fit_implied_by_style_name"),
    A("garment_measurements", TIER_A, SCOPE_VARIANT, False,
      "measurements_per_size", "chart_without_variant_mapping"),
    A("care_instructions", TIER_B, SCOPE_PRODUCT, True,
      "care_method_stated", "care_without_method"),
    A("color_finish", TIER_B, SCOPE_VARIANT, False,
      "named_color_per_variant", "unnamed_color_group"),
    A("closure_and_construction", TIER_B, SCOPE_PRODUCT, True, VALUE_PRESENT),
    A("intended_use_context", TIER_B, SCOPE_PRODUCT, True,
      "use_context_stated", "generic_everyday_only"),
    A("country_of_origin", TIER_C, SCOPE_PRODUCT, True, VALUE_PRESENT),
    A("sustainability_credentials", TIER_C, SCOPE_PRODUCT, True,
      "named_standard_with_basis", "unnamed_eco_claim"),
    A("model_reference_measurements", TIER_C, SCOPE_PRODUCT, True,
      "model_height_and_size_worn", "height_without_size_worn"),
)

# -- taxonomy.md 5.2 ---------------------------------------------------------
BEAUTY = (
    A("ingredients_full", TIER_A, SCOPE_VARIANT, False,
      "complete_ingredient_list", "key_ingredients_only", conflict_severity="blocker"),
    A("net_content", TIER_A, SCOPE_VARIANT, False,
      "quantity_with_unit", "unitless_quantity"),
    A("usage_directions", TIER_A, SCOPE_PRODUCT, True,
      "usage_method_stated", "use_as_directed_only"),
    A("suitability", TIER_A, SCOPE_PRODUCT, True,
      "suitability_with_basis", "all_types_without_basis", conflict_severity="blocker"),
    A("warnings_and_restrictions", TIER_A, SCOPE_PRODUCT, True,
      "warnings_stated_or_explicit_none", "caution_referenced_not_stated",
      conflict_severity="blocker"),
    A("key_actives_and_concentration", TIER_B, SCOPE_PRODUCT, True,
      "actives_with_concentration", "actives_without_concentration",
      conflict_severity="blocker"),
    A("formulation_format", TIER_B, SCOPE_PRODUCT, True, VALUE_PRESENT),
    A("fragrance_status", TIER_B, SCOPE_PRODUCT, True,
      "scent_profile_or_fragrance_free", "scented_without_profile",
      conflict_severity="blocker"),
    A("shelf_life_or_pao", TIER_B, SCOPE_PRODUCT, True, VALUE_PRESENT),
    A("color_shade", TIER_B, SCOPE_VARIANT, False,
      "named_shade_per_variant", "shade_code_without_name"),
    A("certifications_and_testing", TIER_C, SCOPE_PRODUCT, True,
      "named_body_with_basis", "claim_without_named_body", conflict_severity="blocker"),
    A("application_tools_included", TIER_C, SCOPE_PRODUCT, True, VALUE_PRESENT),
)

# -- taxonomy.md 5.3 ---------------------------------------------------------
ELECTRONICS = (
    A("model_identifier", TIER_A, SCOPE_VARIANT, False,
      "manufacturer_model_number", "marketing_name_only"),
    A("core_specifications", TIER_A, SCOPE_PRODUCT, True,
      "specs_with_units", "specs_without_units"),
    A("compatibility", TIER_A, SCOPE_PRODUCT, True,
      "named_compatible_targets", "universal_without_list", conflict_severity="blocker"),
    A("connectivity_and_ports", TIER_A, SCOPE_PRODUCT, True,
      "standard_with_version", "standard_without_version", conflict_severity="blocker"),
    A("power_requirements", TIER_A, SCOPE_PRODUCT, True,
      "voltage_with_plug_type", "voltage_without_plug_type", conflict_severity="blocker"),
    A("physical_dimensions_weight", TIER_B, SCOPE_VARIANT, False,
      "dimensions_with_units", "dimensions_without_units"),
    A("battery", TIER_B, SCOPE_PRODUCT, True,
      "battery_with_test_conditions", "runtime_without_conditions"),
    A("in_the_box", TIER_B, SCOPE_PRODUCT, True,
      "enumerated_contents", "contents_unenumerated"),
    A("warranty_term", TIER_B, SCOPE_PRODUCT, True,
      "duration_with_coverage", "duration_without_coverage"),
    A("software_requirements", TIER_C, SCOPE_PRODUCT, True, VALUE_PRESENT,
      conflict_severity="blocker"),
    A("regulatory_certifications", TIER_C, SCOPE_PRODUCT, True,
      "mark_with_identifier", "mark_without_identifier", conflict_severity="blocker"),
    A("color_finish", TIER_C, SCOPE_VARIANT, False, VALUE_PRESENT),
)

# -- taxonomy.md 5.4 ---------------------------------------------------------
HOME = (
    A("assembled_dimensions", TIER_A, SCOPE_VARIANT, False,
      "three_dimensions_with_units", "partial_dimensions_or_no_units"),
    A("materials_and_finish", TIER_A, SCOPE_PRODUCT, True,
      "materials_with_finish", "generic_material_term"),
    A("capacity_or_load", TIER_A, SCOPE_PRODUCT, True,
      "capacity_with_unit_and_basis", "number_without_unit_or_basis",
      conditional_trigger="load_bearing_element_indicated", conflict_severity="blocker"),
    A("care_and_cleaning", TIER_B, SCOPE_PRODUCT, True,
      "cleaning_method_stated", "easy_to_clean_only"),
    A("assembly", TIER_B, SCOPE_PRODUCT, True,
      "assembly_with_detail", "assembly_without_detail"),
    A("indoor_outdoor_use", TIER_B, SCOPE_PRODUCT, True,
      "use_with_durability_basis", "outdoor_without_basis"),
    A("room_or_placement", TIER_B, SCOPE_PRODUCT, True, VALUE_PRESENT),
    A("color_finish", TIER_B, SCOPE_VARIANT, False, VALUE_PRESENT),
    A("packaged_dimensions_weight", TIER_C, SCOPE_PRODUCT, True, VALUE_PRESENT),
    A("mounting_and_hardware", TIER_C, SCOPE_PRODUCT, True,
      "mounting_method_stated", conditional_trigger="mounting_indicated"),
    A("safety_and_compliance", TIER_C, SCOPE_PRODUCT, True,
      "named_standard_reference", "named_without_standard_reference",
      conflict_severity="blocker"),
)

# -- taxonomy.md 5.5 ---------------------------------------------------------
SPORTS = (
    A("sport_or_activity", TIER_A, SCOPE_PRODUCT, True,
      "specific_activity", "broad_family_only"),
    A("user_fit_specification", TIER_A, SCOPE_VARIANT, False,
      "fit_specification_per_variant", "single_range_for_lineup"),
    A("load_or_capacity_rating", TIER_A, SCOPE_PRODUCT, True,
      "rated_load_with_units", "number_without_unit_or_basis",
      conflict_severity="blocker"),
    A("skill_or_intensity_level", TIER_A, SCOPE_PRODUCT, True,
      "defined_performance_tier", "implied_by_marketing_tone"),
    A("materials_and_construction", TIER_B, SCOPE_PRODUCT, True,
      "materials_with_component_mapping", "material_without_component_mapping"),
    A("dimensions_and_weight", TIER_B, SCOPE_VARIANT, False, VALUE_PRESENT),
    A("use_environment", TIER_B, SCOPE_PRODUCT, True,
      "environment_stated", "all_conditions_only"),
    A("safety_certification", TIER_B, SCOPE_PRODUCT, True,
      "named_standard_with_identifier", "certification_without_standard_number",
      conditional_trigger="protective_equipment_indicated", conflict_severity="blocker"),
    A("included_accessories", TIER_C, SCOPE_PRODUCT, True, VALUE_PRESENT),
    A("maintenance_requirements", TIER_C, SCOPE_PRODUCT, True, VALUE_PRESENT),
    A("age_or_user_suitability", TIER_C, SCOPE_PRODUCT, True,
      "age_range_with_basis", "age_without_basis", conflict_severity="blocker"),
)

CATEGORIES = ("apparel", "beauty", "electronics", "home", "sports")
UNCATEGORIZED = "uncategorized"

BY_CATEGORY = {
    "apparel": APPAREL,
    "beauty": BEAUTY,
    "electronics": ELECTRONICS,
    "home": HOME,
    "sports": SPORTS,
}  # type: Dict[str, Tuple[Attribute, ...]]

#: check_id family per category (rubric.md 3: <FAMILY>.<CHECK>).
FAMILY = {
    "apparel": "APPAREL",
    "beauty": "BEAUTY",
    "electronics": "ELEC",
    "home": "HOME",
    "sports": "SPORTS",
}


def attributes_for(category):
    # type: (str) -> Tuple[Attribute, ...]
    """The D2 attribute set for a category. `uncategorized` has none.

    taxonomy.md 6 and rubric.md 4/D2 both put D2 at 0 for `uncategorized`,
    with the whole dimension removed and renormalized.
    """
    return BY_CATEGORY.get(category, ())


def attribute(category, key):
    # type: (str, str) -> Optional[Attribute]
    for row in attributes_for(category):
        if row.key == key:
            return row
    return None


# ---------------------------------------------------------------------------
# taxonomy.md 8 -- category mapping
# ---------------------------------------------------------------------------
#: Row order is normative: several terms may match one signal, and the first
#: matching row wins (`taxonomy.md` 8, "the mapping table is evaluated in the
#: order above, so `apparel` wins" for activewear).
CATEGORY_MAP = (
    ("apparel", ("apparel", "clothing", "shirt", "dress", "pants", "outerwear",
                 "footwear", "shoes", "socks", "underwear", "activewear",
                 "swimwear", "hat", "scarf", "glove")),
    ("beauty", ("beauty", "cosmetic", "skincare", "haircare", "makeup",
                "fragrance", "perfume", "serum", "moisturizer", "shampoo",
                "personal care")),
    ("electronics", ("electronics", "computer", "phone", "audio", "headphone",
                     "earbud", "earbuds", "camera", "charger", "cable",
                     "monitor", "speaker", "wearable tech", "smart home device")),
    ("home", ("home", "furniture", "kitchen", "bedding", "decor", "storage",
              "lighting", "rug", "cookware", "bath")),
    ("sports", ("sport", "fitness", "outdoor", "camping", "cycling",
                "running gear", "yoga", "athletic equipment", "exercise")),
)
