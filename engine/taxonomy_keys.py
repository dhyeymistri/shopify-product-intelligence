"""Attribute keys defined by ``product/taxonomy.md``.

Transcribed, not derived. `taxonomy.md` is authoritative (AGENTS.md 3); this is
the machine-readable copy the normalizer needs, and `test_normalizer.py` is not
the place that keeps it honest -- `taxonomy.md` 7 rule 5 makes these permanent
identifiers, so drift is a breaking change either way.

The normalizer uses this set for exactly one purpose: deciding whether a
supplied metafield key is *literally* a taxonomy attribute key. Matching is
exact. Deciding that `custom.material` "means" `material_composition` is
near-duplicate detection, which PRD 9.5 permits only as labelled inference in a
check -- never in normalization (PRD 6.2 rule 4).
"""

from __future__ import annotations

# taxonomy.md 3 -- Common Core
COMMON_CORE = (
    "product_title",
    "brand",
    "product_identifier",
    "price",
    "description_substance",
    "primary_image_present",
    "image_alt_text",
    "country_of_origin",
    "warranty_or_guarantee",
    "returns_policy_reference",
    "certifications",
)

# taxonomy.md 5.1 -- 5.5
APPAREL = (
    "size_system", "material_composition", "fit_and_cut", "garment_measurements",
    "care_instructions", "color_finish", "closure_and_construction",
    "intended_use_context", "country_of_origin", "sustainability_credentials",
    "model_reference_measurements",
)
BEAUTY = (
    "ingredients_full", "net_content", "usage_directions", "suitability",
    "warnings_and_restrictions", "key_actives_and_concentration",
    "formulation_format", "fragrance_status", "shelf_life_or_pao", "color_shade",
    "certifications_and_testing", "application_tools_included",
)
ELECTRONICS = (
    "model_identifier", "core_specifications", "compatibility",
    "connectivity_and_ports", "power_requirements", "physical_dimensions_weight",
    "battery", "in_the_box", "warranty_term", "software_requirements",
    "regulatory_certifications", "color_finish",
)
HOME = (
    "assembled_dimensions", "materials_and_finish", "capacity_or_load",
    "care_and_cleaning", "assembly", "indoor_outdoor_use", "room_or_placement",
    "color_finish", "packaged_dimensions_weight", "mounting_and_hardware",
    "safety_and_compliance",
)
SPORTS = (
    "sport_or_activity", "user_fit_specification", "load_or_capacity_rating",
    "skill_or_intensity_level", "materials_and_construction",
    "dimensions_and_weight", "use_environment", "safety_certification",
    "included_accessories", "maintenance_requirements", "age_or_user_suitability",
)

BY_CATEGORY = {
    "apparel": APPAREL,
    "beauty": BEAUTY,
    "electronics": ELECTRONICS,
    "home": HOME,
    "sports": SPORTS,
}

ATTRIBUTE_KEYS = frozenset(COMMON_CORE + APPAREL + BEAUTY + ELECTRONICS + HOME + SPORTS)


def is_attribute_key(key):
    # type: (object) -> bool
    """Exact membership. No normalization, no fuzzy matching, no inference."""
    return isinstance(key, str) and key in ATTRIBUTE_KEYS
