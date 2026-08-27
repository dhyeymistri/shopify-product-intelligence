"""Deterministic recognition predicates.

A predicate answers exactly one question: **does this one supplied value have
the shape the taxonomy row describes?** It reads that value and nothing else.
It consults no category norms, no other product, no world knowledge and no
network. It returns a boolean; it never returns a status, a point figure, or a
string that could reach a report.

Four rules hold for every predicate in this module, and they are the reason it
can exist at all under AGENTS.md 2:

1. **Structured values only.** Predicates are wired to `facts.Gathered.stated`,
   which excludes `PROSE_PATHS` by construction (D-019). Nothing here reads a
   description.
2. **No negative arm.** A predicate that does not fire says *undecided*, never
   *absent* and never *wrong*. The check then defers and emits nothing, which
   is the permitted direction of failure.
3. **No value is invented.** The only strings that leave this module are the
   merchant's own, quoted by the evidence builder at their own locators. The
   lexicon's own vocabulary never appears in output (D-022).
4. **No penalty.** No predicate here is owned by a D6 or D7 check, and the
   registry refuses to load if one ever is.

**The load-bearing assumption, stated once.** A value found at an
exactly-keyed attribute path is the merchant's assertion *about that
attribute*. `material_with_proportions` does not verify that a fibre was
named; it verifies that a proportion was stated at a field the merchant keyed
as material composition. P3.1 already relies on this for every `VALUE_PRESENT`
check -- recognition does not introduce the assumption, it inherits it.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional, Tuple

from . import lexicon as X

# ---------------------------------------------------------------------------
# shared shape helpers
# ---------------------------------------------------------------------------
_PROPORTION_RE = re.compile(r"\d+(?:\.\d+)?\s*%")
_DIGIT_RE = re.compile(r"\d")
_DIMENSION_SPLIT_RE = re.compile(r"[x×]")
_CONTENTS_SPLIT_RE = re.compile(r"[,;\n•]")
_SHADE_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-_ ]*$")
_INTEGER_RE = re.compile(r"^\d+$")
_WORD_RE = re.compile(r"[^\W\d_]{3,}", re.UNICODE)


def _dimensions(value):
    # type: (str) -> Optional[Tuple[int, bool]]
    """(count of magnitudes, a length unit is present) for an `x`-joined value.

    `None` when any segment is not a bare magnitude. That is deliberate: a
    labelled form such as `"W 80cm D 24cm H 9cm"` is dimension *prose*, and
    parsing it is recognition over language rather than over shape. The
    conservative reading -- the one that earns less -- is to say nothing.
    """
    segments = [s for s in _DIMENSION_SPLIT_RE.split(X.normalize(value))
                if s.strip()]
    if len(segments) < 2:
        return None
    units = set()
    for segment in segments:
        parsed = X.magnitude(segment)
        if parsed is None:
            return None
        unit = parsed[1]
        if unit:
            units.add(unit)
    if units - X.LENGTH_UNITS:
        return None
    return len(segments), bool(units)


def _quantity(value):
    # type: (str) -> Optional[Tuple[str, str]]
    return X.magnitude(value)


# ---------------------------------------------------------------------------
# Slice A -- closed vague-phrase vocabulary. Whole-value membership only.
# ---------------------------------------------------------------------------
def _member_of(phrases):
    # type: (frozenset) -> Callable[[str], bool]
    def predicate(value):
        # type: (str) -> bool
        return X.normalize(value) in phrases
    return predicate


#: `taxonomy.md` 5.1 APPAREL.COLOR_FINISH partial_if = unnamed_color_group.
#: Recognizes ambiguity vocabulary -- vague group terms only, never product-value
#: color names. D-034: named_color_per_variant remains deferred because a
#: positive lexicon would enumerate product facts (D-022).
def unnamed_color_group(value):
    # type: (str) -> bool
    return X.normalize(value) in X.APPAREL_COLOR_FINISH_VAGUE


#: `taxonomy.md` 5.1 APPAREL.CARE_INSTRUCTIONS satisfies = care_method_stated.
#: D-036: whole-value membership against a closed vocabulary of composite
#: structural phrases. No delimiter splitting, no prose recognition.
def care_method_stated(value):
    # type: (str) -> bool
    return X.normalize(value) in X.APPAREL_CARE_METHODS


#: `taxonomy.md` 5.1 APPAREL.INTENDED_USE_CONTEXT satisfies = use_context_stated.
#: D-036: whole-value membership against a closed vocabulary of composite
#: structural phrases. No delimiter splitting, no prose recognition.
def use_context_stated(value):
    # type: (str) -> bool
    return X.normalize(value) in X.APPAREL_USE_CONTEXTS


#: `taxonomy.md` 5.5 SPORTS.use_environment satisfies = environment_stated.
#: D-037: whole-value membership against SPORTS_ENVIRONMENTS (ISO ICS 97.220
#: environment classes). No delimiter splitting, no prose recognition, no
#: substring matching. Exact normalized membership only.
def environment_stated(value):
    # type: (str) -> bool
    return X.normalize(value) in X.SPORTS_ENVIRONMENTS


# ---------------------------------------------------------------------------
# Slice B -- numeric, unit and delimiter shape
# ---------------------------------------------------------------------------
def material_with_proportions(value):
    # type: (str) -> bool
    return _PROPORTION_RE.search(value) is not None


def material_without_proportions(value):
    # type: (str) -> bool
    """No proportion, and no digit that could be one stated differently."""
    return ("%" not in value) and not _DIGIT_RE.search(value)


def quantity_with_unit(value):
    # type: (str) -> bool
    parsed = _quantity(value)
    return parsed is not None and parsed[1] in (X.VOLUME_UNITS | X.MASS_UNITS)


def unitless_quantity(value):
    # type: (str) -> bool
    parsed = _quantity(value)
    return parsed is not None and not parsed[1]


def dimensions_with_units(value):
    # type: (str) -> bool
    parsed = _dimensions(value)
    return parsed is not None and parsed[0] >= 2 and parsed[1]


def dimensions_without_units(value):
    # type: (str) -> bool
    parsed = _dimensions(value)
    return parsed is not None and parsed[0] >= 2 and not parsed[1]


def three_dimensions_with_units(value):
    # type: (str) -> bool
    parsed = _dimensions(value)
    return parsed is not None and parsed[0] == 3 and parsed[1]


def partial_dimensions_or_no_units(value):
    # type: (str) -> bool
    """`taxonomy.md` 5.4, literally: two of three dimensions, or no units."""
    parsed = _dimensions(value)
    if parsed is None:
        return False
    count, has_unit = parsed
    return (count == 2) or (count == 3 and not has_unit)


def duration_without_coverage(value):
    # type: (str) -> bool
    """A duration is stated and provably nothing accompanies it.

    The satisfying arm -- a duration *with* a coverage scope -- stays deferred.
    Recognizing what a warranty covers is reading language, not shape.
    """
    return X.is_bare_duration(value)


def warranty_with_duration_or_scope(value):
    # type: (str) -> bool
    """The predicate name is a disjunction, and a stated duration settles the
    first disjunct outright. No judgment about scope is made or needed."""
    return X.states_duration(value)


def enumerated_contents(value):
    # type: (str) -> bool
    """Enumeration is a structural property of the value, not a judgment about
    what the items are."""
    return len(_segments(value)) >= 2


def contents_unenumerated(value):
    # type: (str) -> bool
    return len(_segments(value)) == 1


def _segments(value):
    # type: (str) -> List[str]
    return [s for s in _CONTENTS_SPLIT_RE.split(value) if s.strip()]


def shade_code_without_name(value):
    # type: (str) -> bool
    """A shade code with no name (`taxonomy.md` 5.2's own PARTIAL condition).

    Case is read as supplied: `"N-24"` is a code, `"Warm Sand"` is a name, and
    the difference between them is exactly the difference this predicate can
    see. Deciding that a string *is* a shade name needs a lexicon of shade
    names, which would be a lexicon of product values -- so that arm stays
    deferred permanently rather than pending.
    """
    text = value.strip()
    return bool(text) and bool(_SHADE_CODE_RE.match(text)) \
        and bool(_DIGIT_RE.search(text))


def number_without_unit_or_basis(value):
    # type: (str) -> bool
    """`taxonomy.md` 5.4 and 5.5 PARTIAL condition for capacity_or_load and
    load_or_capacity_rating: a number with no recognized unit token.

    D-035: only the structurally decidable "no unit" sub-case is recognized.
    The "no basis" portion (determining what the number represents) is NOT
    implemented -- values with a recognized unit remain UNDECIDED.

    A value is AMBIGUOUS iff it parses as a magnitude (via lexicon.magnitude)
    and the extracted unit spelling is empty or not a member of the recognized
    unit sets (LENGTH_UNITS | MASS_UNITS | VOLUME_UNITS | TIME_UNITS).
    """
    parsed = X.magnitude(value)
    if parsed is None:
        return False
    _, unit = parsed
    return not unit or unit not in X.UNIT_TOKENS


def rated_load_with_units(value):
    # type: (str) -> bool
    """`taxonomy.md` 5.5 SPORTS.load_or_capacity_rating satisfies predicate:
    a magnitude with a recognized mass unit.

    D-035: structural boundary -- magnitude parsed, unit token recognized.
    Uses existing MASS_UNITS vocabulary; no product-value vocabulary.
    """
    parsed = X.magnitude(value)
    return parsed is not None and parsed[1] in X.MASS_UNITS


def actives_with_concentration(value):
    # type: (str) -> bool
    """`taxonomy.md` 5.2 BEAUTY.key_actives_and_concentration satisfies
    predicate: a proportion is stated somewhere in the value.

    D-038: an unanchored search over the supplied value -- not whole-value
    membership, and not delimiter splitting. The *named actives* half of the
    cell is not verified and needs no verification here: a value at this key
    is the merchant's assertion about actives, which is this module's own
    load-bearing assumption, stated above. No vocabulary is added.
    """
    return _PROPORTION_RE.search(value) is not None


def actives_without_concentration(value):
    # type: (str) -> bool
    """`taxonomy.md` 5.2's PARTIAL cell: actives named without concentration.

    D-038: no `%`, and no digit that could be a concentration stated in some
    other notation. The digit condition is what makes this arm *provable*
    rather than merely unmatched -- a value carrying a digit that is not a
    proportion may be stating a concentration this phase cannot read, so it
    stays UNDECIDED and the check defers (D-019).
    """
    return ("%" not in value) and not _DIGIT_RE.search(value)


# ---------------------------------------------------------------------------
# Slice E -- controlled vocabulary, positive arm
# ---------------------------------------------------------------------------
def named_size_standard_with_value(value):
    # type: (str) -> bool
    """`taxonomy.md` 5.1: a named standard with a value, *or* a stated numeric
    measure -- the footwear rule puts a length in cm into this same key."""
    if X.is_size_standard(value):
        return True
    parsed = _quantity(value)
    return parsed is not None and parsed[1] in X.LENGTH_UNITS


def bare_size_label(value):
    # type: (str) -> bool
    text = X.normalize(value)
    return text in X.APPAREL_SIZE_SYSTEM_BARE_LABELS \
        or bool(_INTEGER_RE.match(text))


# ---------------------------------------------------------------------------
# Slice C -- relations between two supplied fields. No lexicon at all.
# ---------------------------------------------------------------------------
def _occurs(needle, haystack):
    # type: (str, str) -> bool
    if not needle:
        return False
    return re.search(r"(?<!\w)%s(?!\w)" % re.escape(needle), haystack) \
        is not None


def _occurs_with_plural(needle, haystack):
    # type: (str, str) -> bool
    """Word-boundary occurrence, tolerating a single trailing `s`.

    The trailing-`s` pair is the only soft edge in slice C and it is kept
    mechanical on purpose: `"Shirts"` matches `"shirt"`, and `"T-Shirts"` does
    not match `"tee"`. Anything richer is stemming, which is language.
    """
    forms = {needle}
    if needle.endswith("s"):
        forms.add(needle[:-1])
    else:
        forms.add(needle + "s")
    return any(_occurs(form, haystack) for form in forms if form)


def title_names_product_type(title, others):
    # type: (str, List[str]) -> Optional[str]
    """The title names a type the merchant stated elsewhere in the record.

    Returns the matched value, so the finding can cite it at its own locator.
    There is no negative arm: a title may name a product type that is stated
    nowhere else, and concluding otherwise would be an unfounded finding about
    a title the tool simply could not corroborate.
    """
    normalized_title = X.normalize(title)
    for other in others:
        candidate = X.normalize(other)
        if candidate and _occurs_with_plural(candidate, normalized_title):
            return other
    return None


def title_carries_distinguishing_attribute(title, others):
    # type: (str, List[str]) -> Optional[str]
    """The title repeats an attribute value the record states elsewhere.

    A whole value counts, and so does any of its alphabetic tokens of three
    characters or more. The three-character floor is a stop against matching
    `"a"` or `"of"`; it is arbitrary in the way a threshold always is, which is
    why it is recorded here rather than tuned.
    """
    normalized_title = X.normalize(title)
    for other in others:
        candidate = X.normalize(other)
        if not candidate:
            continue
        if _occurs(candidate, normalized_title):
            return other
        for token in _WORD_RE.findall(candidate):
            if _occurs(token, normalized_title):
                return other
    return None


# ---------------------------------------------------------------------------
# The two registries the check registry consumes (PRE-5, D-022).
# ---------------------------------------------------------------------------
def unnamed_eco_claim(value):
    # type: (str) -> bool
    """Written, and deliberately **not registered** below (D-027).

    `taxonomy.md` 5.1 states this cell as *'Unnamed "eco-friendly" -> routes to
    D7 as unsupported'*. That is one behaviour with two effects pointing in
    opposite directions: the `PARTIAL` awards credit, the D7 route subtracts
    it. Claim recognition is not implemented, so shipping this arm alone would
    not under-detect -- it would pay a merchant for a claim the specification
    singles out as unsupported. It stays here, unregistered, so the pair can
    ship together.
    """
    return _member_of(X.APPAREL_SUSTAINABILITY_CREDENTIALS_VAGUE)(value)


#: `predicate_id -> (value) -> bool`. A property of one supplied value.
VALUE_PREDICATES = {
    # Slice A
    "generic_everyday_only":
        _member_of(X.APPAREL_INTENDED_USE_CONTEXT_VAGUE),
    "care_without_method":
        _member_of(X.APPAREL_CARE_INSTRUCTIONS_VAGUE),
    "easy_to_clean_only":
        _member_of(X.HOME_CARE_AND_CLEANING_VAGUE),
    "use_as_directed_only":
        _member_of(X.BEAUTY_USAGE_DIRECTIONS_VAGUE),
    "all_conditions_only":
        _member_of(X.SPORTS_USE_ENVIRONMENT_VAGUE),
    "universal_without_list":
        _member_of(X.ELEC_COMPATIBILITY_VAGUE),
    "broad_family_only":
        _member_of(X.SPORTS_SPORT_OR_ACTIVITY_VAGUE),
    "unnamed_color_group": unnamed_color_group,
    "care_method_stated": care_method_stated,
    "use_context_stated": use_context_stated,
    "environment_stated": environment_stated,
    # Slice B
    "material_with_proportions": material_with_proportions,
    "material_without_proportions": material_without_proportions,
    "quantity_with_unit": quantity_with_unit,
    "unitless_quantity": unitless_quantity,
    "dimensions_with_units": dimensions_with_units,
    "dimensions_without_units": dimensions_without_units,
    "three_dimensions_with_units": three_dimensions_with_units,
    "partial_dimensions_or_no_units": partial_dimensions_or_no_units,
    "duration_without_coverage": duration_without_coverage,
    "warranty_with_duration_or_scope": warranty_with_duration_or_scope,
    "enumerated_contents": enumerated_contents,
    "contents_unenumerated": contents_unenumerated,
    "shade_code_without_name": shade_code_without_name,
    "number_without_unit_or_basis": number_without_unit_or_basis,
    "rated_load_with_units": rated_load_with_units,
    "actives_with_concentration": actives_with_concentration,
    "actives_without_concentration": actives_without_concentration,
    # Slice E
    "named_size_standard_with_value": named_size_standard_with_value,
    "bare_size_label": bare_size_label,
    "defined_performance_tier":
        _member_of(X.SPORTS_SKILL_OR_INTENSITY_LEVEL_TIERS),
}  # type: Dict[str, Callable[[str], bool]]

#: `predicate_id -> (title, others) -> matched value or None`. A relation
#: between two supplied fields, so it cannot be a property of one value and is
#: invoked by its own check handler rather than by `attribute_check`.
RELATION_PREDICATES = {
    "title_names_product_type": title_names_product_type,
    "title_carries_distinguishing_attribute":
        title_carries_distinguishing_attribute,
}  # type: Dict[str, Callable[[str, List[str]], Optional[str]]]
