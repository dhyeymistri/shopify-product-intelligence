"""Identify tokens in report text that assert a product fact.

The fabrication audit cannot demand that every word of report prose trace to the
input -- honest reports contain framing language ("Not stated in the supplied
data"). It demands that every *fact-bearing* token trace. This module decides
which tokens are fact-bearing.

Two design rules keep this honest:

1. **Specific, never generic.** "cotton" is a material claim; "fabric" is not.
   "EN 1078" is a standard; "certification" is not. Generic category vocabulary
   belongs in the allowlist so that a report can name what it is *asking for*
   without being accused of asserting it.

2. **The allowlist is structural vocabulary only.** It contains check IDs,
   attribute keys, statuses and fixed spec phrases -- never a product value.
   A value may only clear the audit by being traceable to input, never by
   appearing on a list. `assert_allowlist_has_no_values` enforces this.
"""

from __future__ import annotations

import re
from typing import List, Optional, Set

from .provenance import normalize, strip_edges

# ---------------------------------------------------------------------------
# Fact-token kinds -> violation codes are mapped in fabrication_audit.py
# ---------------------------------------------------------------------------
MODEL = "model_number"
SPEC = "specification"
MATERIAL = "material"
COMPATIBILITY = "compatibility"
DIMENSION = "dimension"
SAFETY = "safety_claim"
USECASE = "use_case"

_UNITS = (
    r"mm|cm|m|km|in|inch|inches|ft|feet|g|kg|lb|lbs|oz|ml|l|litre|liter|fl\s?oz|"
    r"w|kw|v|mv|a|mah|wh|hz|khz|mhz|ghz|mp|mpx|gb|tb|mb|kb|dpi|ppi|bar|psi|rpm|"
    r"denier|gsm|thread\s?count|nits|lumens|db|°c|°f|celsius|fahrenheit"
)
_DURATION = r"hours?|hrs?|minutes?|mins?|seconds?|secs?|days?|weeks?|months?|years?"

DIMENSION_TRIPLE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:x|by)\s*\d+(?:\.\d+)?\s*(?:x|by)\s*\d+(?:\.\d+)?\s*(?:%s)?\b" % _UNITS,
    re.I,
)
DIMENSION_PAIR_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:x|by)\s*\d+(?:\.\d+)?\s*(?:%s)\b" % _UNITS, re.I
)
QUANTITY_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%s)\b" % _UNITS, re.I)
DURATION_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%s)\b" % _DURATION, re.I)
PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s*%")
STANDARD_RE = re.compile(
    r"\b(?:EN|ISO|ASTM|IEC|UL|ANSI|CPSC|AS/NZS|BS|DIN|JIS)\s?\d{2,}(?:[-:]\d+)?\b"
    r"|\bIP\d{2}\b|\bFCC\s?ID\b|\bUKCA\b|\bOEKO-TEX\b|\bGOTS\b",
    re.I,
)
# Letters+digits, e.g. WH-1000XM5, A2338, EN1078. Requires at least one of each.
MODEL_RE = re.compile(r"\b(?=[A-Za-z0-9-]*[A-Za-z])(?=[A-Za-z0-9-]*\d)[A-Z0-9]+(?:-[A-Z0-9]+)*\b")

USECASE_RE = re.compile(
    r"\b(?:ideal|perfect|great|excellent|well[- ]suited|designed|built|made|intended|suitable)"
    r"\s+for\s+([a-z][a-z0-9\s,'\-]{2,50})",
    re.I,
)

MATERIALS = frozenset("""
cotton polyester wool merino cashmere silk linen nylon elastane spandex lycra rayon viscose
modal bamboo hemp acrylic polyamide polypropylene leather suede nubuck denim canvas fleece
corduroy velvet satin chiffon tweed jersey twill poplin gore-tex neoprene latex
oak walnut maple birch pine teak beech mahogany bamboo rattan wicker plywood mdf particleboard
veneer marble granite quartz ceramic porcelain terracotta stoneware glass borosilicate
steel stainless aluminium aluminum brass copper bronze titanium zinc iron cast-iron
abs polycarbonate polyurethane silicone rubber eva pvc acetate carbon-fibre carbon-fiber
fiberglass melamine formica cork jute sisal seagrass down feather memory-foam
""".split())

COMPAT_TERMS = frozenset("""
ios android windows macos linux chromeos ipados watchos iphone ipad macbook airpods
usb-c usb-a micro-usb lightning thunderbolt hdmi displayport ethernet aux optical
bluetooth wifi wi-fi zigbee z-wave matter airplay chromecast qi magsafe nfc
alexa siri google-assistant homekit
""".split())

INGREDIENTS = frozenset("""
niacinamide retinol retinal tretinoin hyaluronic salicylic glycolic lactic mandelic azelaic
ascorbic ceramide ceramides squalane panthenol allantoin bakuchiol adapalene benzoyl
parfum fragrance limonene linalool citral geraniol paraben parabens phenoxyethanol
glycerin glycerine dimethicone petrolatum lanolin shea jojoba argan collagen peptide peptides
spf titanium-dioxide zinc-oxide avobenzone octocrylene
""".split())

SAFETY_CLAIMS = frozenset([
    "hypoallergenic", "non-toxic", "nontoxic", "flame retardant", "flame-retardant",
    "fire resistant", "fire-resistant", "food safe", "food-safe", "food grade", "food-grade",
    "bpa free", "bpa-free", "phthalate free", "phthalate-free", "lead free", "lead-free",
    "waterproof", "water resistant", "water-resistant", "shatterproof", "child safe",
    "child-safe", "dermatologist tested", "dermatologist-tested", "clinically proven",
    "clinically tested", "fda approved", "fda-approved", "ce certified", "ce-certified",
    "non-slip", "anti-slip", "sterile", "antimicrobial", "antibacterial", "cruelty free",
    "cruelty-free", "vegan", "organic", "hypoallergenic-tested", "impact tested",
    "impact-tested", "crash tested", "crash-tested",
])

# ---------------------------------------------------------------------------
# Allowlist: structural vocabulary. NEVER a product value.
# ---------------------------------------------------------------------------
_ALLOW_PHRASES = [
    "not stated in the supplied data",
    "a basis is referenced",
    "do not generate a value",
    "this must be supplied by the merchant or supplier",
    "(interpreted)",
    "checked and empty",
    "no value was found",
    "supplied data",
]

_ALLOW_TOKENS = set("""
pass partial fail unknown not_applicable blocker critical major minor info
high medium low product variant option catalog
quote field_value absence derived external_reference
merchant_structured merchant_prose merchant_placeholder
apparel beauty electronics home sports uncategorized
question correction structure
d1 d2 d3 d4 d5 d6 d7 d8
d1_identity d2_category_attributes d3_variant d4_usecase d5_trust
d6_consistency d7_claims d8_structure
pip npr inci sku gtin mpn ean upc seo html json csv url id
n/a tbd xxx
""".split())

# Identifier shapes that are structural, not product facts.
_ALLOW_ID_RE = re.compile(
    r"^(?:F-\d+|D-\d{3}|AC-[A-Z]\d+|Q-\d+|P\d|D\d|V\d+|"
    r"[A-Z]+\.[A-Z0-9_]+|"                      # check_id, e.g. APPAREL.MATERIAL_COMPOSITION
    r"\d+(?:\.\d+)?)$"
)


def _load_attribute_keys():
    # type: () -> Set[str]
    """Attribute keys are structural vocabulary (taxonomy.md), not values."""
    keys = set()
    for group in (
        "product_title brand product_identifier price description_substance",
        "primary_image_present image_alt_text country_of_origin warranty_or_guarantee",
        "returns_policy_reference certifications",
        "size_system material_composition fit_and_cut garment_measurements care_instructions",
        "color_finish closure_and_construction intended_use_context sustainability_credentials",
        "model_reference_measurements",
        "ingredients_full net_content usage_directions suitability warnings_and_restrictions",
        "key_actives_and_concentration formulation_format fragrance_status shelf_life_or_pao",
        "color_shade certifications_and_testing application_tools_included",
        "model_identifier core_specifications compatibility connectivity_and_ports",
        "power_requirements physical_dimensions_weight battery in_the_box warranty_term",
        "software_requirements regulatory_certifications",
        "assembled_dimensions materials_and_finish capacity_or_load care_and_cleaning assembly",
        "indoor_outdoor_use room_or_placement packaged_dimensions_weight mounting_and_hardware",
        "safety_and_compliance",
        "sport_or_activity user_fit_specification load_or_capacity_rating skill_or_intensity_level",
        "materials_and_construction dimensions_and_weight use_environment safety_certification",
        "included_accessories maintenance_requirements age_or_user_suitability",
    ):
        keys.update(group.split())
    return keys


ATTRIBUTE_KEYS = _load_attribute_keys()
ALLOWLIST = _ALLOW_TOKENS | ATTRIBUTE_KEYS


def assert_allowlist_has_no_values():
    # type: () -> None
    """Guard: no product-value vocabulary may hide in the allowlist.

    Called by the test suite. If a material, ingredient, compatibility term or
    safety claim ever appears on the allowlist, fabrications of that token would
    pass the audit silently. That is the one way this module could fail open.
    """
    value_vocab = MATERIALS | COMPAT_TERMS | INGREDIENTS | SAFETY_CLAIMS
    leaked = sorted(t for t in ALLOWLIST if t in value_vocab)
    if leaked:
        raise AssertionError("product values leaked into the allowlist: %s" % leaked)


class FactToken:
    __slots__ = ("kind", "text", "start", "end")

    def __init__(self, kind, text, start, end):
        # type: (str, str, int, int) -> None
        self.kind = kind
        self.text = text
        self.start = start
        self.end = end

    def __repr__(self):  # pragma: no cover - debugging aid
        return "FactToken(%s, %r)" % (self.kind, self.text)

    def __eq__(self, other):
        return (
            isinstance(other, FactToken)
            and (self.kind, self.text, self.start, self.end)
            == (other.kind, other.text, other.start, other.end)
        )

    def __hash__(self):
        return hash((self.kind, self.text, self.start, self.end))


def _allowed(fragment):
    # type: (str) -> bool
    raw = strip_edges(fragment.strip())
    if not raw:
        return True
    if _ALLOW_ID_RE.match(raw):
        return True
    return normalize(raw) in ALLOWLIST


def _lexicon_hits(text, lexicon, kind, tokens):
    # type: (str, frozenset, str, List[FactToken]) -> None
    lowered = normalize(text)
    for term in lexicon:
        start = 0
        while True:
            idx = lowered.find(term, start)
            if idx < 0:
                break
            before = lowered[idx - 1] if idx > 0 else " "
            after_i = idx + len(term)
            after = lowered[after_i] if after_i < len(lowered) else " "
            if not before.isalnum() and not after.isalnum():
                tokens.append(FactToken(kind, term, idx, after_i))
            start = idx + len(term)


def extract(text):
    # type: (Optional[str]) -> List[FactToken]
    """Return every fact-bearing token in `text`, allowlist already applied."""
    if not text:
        return []

    tokens = []  # type: List[FactToken]

    for regex, kind in (
        (DIMENSION_TRIPLE_RE, DIMENSION),
        (DIMENSION_PAIR_RE, DIMENSION),
        (STANDARD_RE, SAFETY),
        (QUANTITY_RE, SPEC),
        (DURATION_RE, SPEC),
        (PERCENT_RE, SPEC),
    ):
        for m in regex.finditer(text):
            tokens.append(FactToken(kind, m.group(0), m.start(), m.end()))

    for m in MODEL_RE.finditer(text):
        if not _allowed(m.group(0)):
            tokens.append(FactToken(MODEL, m.group(0), m.start(), m.end()))

    for m in USECASE_RE.finditer(text):
        tokens.append(FactToken(USECASE, m.group(1).strip(), m.start(1), m.end(1)))

    _lexicon_hits(text, MATERIALS, MATERIAL, tokens)
    _lexicon_hits(text, COMPAT_TERMS, COMPATIBILITY, tokens)
    _lexicon_hits(text, INGREDIENTS, MATERIAL, tokens)
    _lexicon_hits(text, SAFETY_CLAIMS, SAFETY, tokens)

    kept = [t for t in tokens if not _allowed(t.text)]
    # Drop tokens fully contained in a longer token of the same span set, so a
    # dimension triple is reported once rather than as three quantities.
    kept.sort(key=lambda t: (t.start, -(t.end - t.start)))
    out = []  # type: List[FactToken]
    for tok in kept:
        if any(o.start <= tok.start and tok.end <= o.end and o is not tok for o in out):
            continue
        out.append(tok)
    return sorted(out, key=lambda t: (t.start, t.kind, t.text))
