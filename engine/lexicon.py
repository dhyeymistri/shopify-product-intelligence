"""The recognition vocabulary, in one place, versioned with the rubric.

PRD 9.6: *"a recognition lexicon, when one is written, belongs to the check
that uses it and is versioned with `rubric.md`."* D-022 settles what that
means in code, and this module is the whole of it.

**Ownership.** Every set below is named for the `check_id` that owns it. No
other layer may read a set it does not own, and the normalizer reads none of
them: recognition performed in the input layer would be unlabelled,
unevidenced and unscored (PRD 6.1).

**Versioning.** `LEXICON_VERSION` is asserted equal to `rubric_data
.RUBRIC_VERSION` at import. An entry decides a status, a status decides earned
points, so a lexicon is a scoring artifact and drift is a load failure rather
than a silent scoring change. Adding, removing or editing an entry bumps
`rubric_version` (D-023) and moves every affected expectation file in the same
commit.

**No entry is a product value.** Entries are the vocabulary of *ambiguity*, of
*units* and of *standards*. None of them is a fact about a product, and none
may ever be emitted as though a merchant had stated it. Two assertions guard
that: `assert_no_product_values()` at import, and a corpus test that no
value-shaped entry appears in any finding title, detail or evidence note.

**Two kinds of entry, audited differently.** `VALUE_SHAPED` holds entries a
merchant could write as a whole field value -- vague phrases, size labels,
performance tiers. Those are the leak risk and they are audited over the whole
corpus. `UNIT_TOKENS` holds unit spellings; a unit is a fragment of ordinary
English (`in`, `m`, `l`) rather than a value, so it is not substring-auditable
and is not audited that way. What matters for units is asserted instead: no
entry here relates one unit to another. There is no conversion table in this
module and there may not be one (D-006, and DEC-6 in the P3.2 plan).
"""

from __future__ import annotations

import re
from typing import FrozenSet, Optional, Tuple

from . import rubric_data as R
from . import taxonomy_keys

#: Written out, not derived. A derived version can never disagree with the
#: rubric, which would make the assertion at the foot of this module vacuous.
#: Stated as a literal, bumping `rubric_version` without reviewing this
#: vocabulary is a load failure -- which is exactly what D-022 asks for.
LEXICON_VERSION = "0.8"

_WS_RE = re.compile(r"\s+")


def normalize(text):
    # type: (str) -> str
    """Whole-value normalization for membership tests.

    Strip, collapse internal whitespace, lowercase, and drop one trailing `.`
    or `!`. Formatting only: nothing here changes what a value says, and
    nothing here is a conversion.
    """
    out = _WS_RE.sub(" ", text.strip().lower())
    if out.endswith(".") or out.endswith("!"):
        out = out[:-1].rstrip()
    return out


# ---------------------------------------------------------------------------
# Vague-phrase sets. Each is transcribed from its attribute's own "PARTIAL if"
# column in `taxonomy.md`, plus its nearest neighbours in the same phrasing.
# Membership is tested against the *whole* normalized value. Substring matching
# is prohibited: "everyday" inside a sentence is not the same fact as a value
# that *is* "everyday".
# ---------------------------------------------------------------------------
APPAREL_INTENDED_USE_CONTEXT_VAGUE = frozenset([
    "everyday", "every day", "everyday wear", "daily wear", "all occasions",
])

APPAREL_CARE_INSTRUCTIONS_VAGUE = frozenset([
    "easy care", "easy to care for", "low maintenance",
])

HOME_CARE_AND_CLEANING_VAGUE = frozenset([
    "easy to clean", "easy clean", "wipe clean",
])

BEAUTY_USAGE_DIRECTIONS_VAGUE = frozenset([
    "use as directed", "apply as directed", "as directed",
])

SPORTS_USE_ENVIRONMENT_VAGUE = frozenset([
    "all conditions", "all weather", "any conditions", "all terrain",
])

ELEC_COMPATIBILITY_VAGUE = frozenset([
    "universal", "universal compatibility", "universally compatible",
    "works with everything",
])

APPAREL_SUSTAINABILITY_CREDENTIALS_VAGUE = frozenset([
    "eco-friendly", "eco friendly", "sustainable", "environmentally friendly",
    "green",
])

APPAREL_COLOR_FINISH_VAGUE = frozenset([
    "assorted", "assorted colors", "assorted colours", "multi-color",
    "multi-colour", "various", "various colors", "various colours",
    "color pack", "colour pack", "mixed", "mixed colors", "mixed colours",
])

SPORTS_SPORT_OR_ACTIVITY_VAGUE = frozenset([
    "fitness", "sport", "sports", "training", "exercise", "outdoor",
    "activity",
])

# ---------------------------------------------------------------------------
# Controlled vocabulary, positive arms.
# ---------------------------------------------------------------------------
#: `taxonomy.md` 5.1 -- a size *system* is named, not merely a label.
APPAREL_SIZE_SYSTEM_STANDARDS = frozenset([
    "us", "uk", "eu", "eur", "jp", "au", "it", "fr",
])

#: `taxonomy.md` 5.1's PARTIAL column, plus PRD 9.3's canonical ambiguous
#: value, "one size".
APPAREL_SIZE_SYSTEM_BARE_LABELS = frozenset([
    "xxs", "xs", "s", "m", "l", "xl", "xxl", "xxxl",
    "small", "medium", "large", "extra small", "extra large", "one size",
])

SPORTS_SKILL_OR_INTENSITY_LEVEL_TIERS = frozenset([
    "beginner", "intermediate", "advanced", "expert", "entry level",
    "entry-level", "professional", "recreational", "competition",
])

# ---------------------------------------------------------------------------
# Attribute keys, not values. `rubric.md` 4/D1 fixes `IDENT.TITLE_DISTINGUISHING`
# at "material, size, model, capacity, count", and D-024 reads that parenthesis
# as a closed list. These are the `taxonomy.md` keys that *are* one of the five
# kinds -- keys, never values, so the set is excluded from `VALUE_SHAPED` and
# from the corpus leak scan, and asserted instead to be taxonomy keys.
#
# No taxonomy key is a *count*. The kind is reachable only once one exists.
# Held out deliberately: `garment_measurements` and `user_fit_specification`
# are fit measurements rather than a size, and `color_finish` is a colour,
# which the rubric does not list (D-024).
# ---------------------------------------------------------------------------
IDENT_TITLE_DISTINGUISHING_KEYS = frozenset([
    # material
    "material_composition", "materials_and_finish", "materials_and_construction",
    # size
    "size_system", "assembled_dimensions", "physical_dimensions_weight",
    "dimensions_and_weight", "packaged_dimensions_weight",
    # model
    "model_identifier", "product_identifier",
    # capacity
    "capacity_or_load", "load_or_capacity_rating", "net_content",
])

# ---------------------------------------------------------------------------
# Option names, not option values. Two closed vocabularies, each owned by the
# check named in its identifier, each matched against a *whole* normalized
# option name -- never as a substring, and never against an option's values.
#
# Both are excluded from `VALUE_SHAPED` and therefore from the corpus leak
# scan, on the precedent `APPAREL_SIZE_SYSTEM_STANDARDS` already sets. The
# reason is specific to what these entries are: an option name is a structure
# the merchant supplied, and PRD 9.7 requires a finding to name the structure
# it is talking about, so "Color" has to be quotable in evidence at its own
# locator. A scan forbidding every lexicon string from generated text would
# forbid these two checks from doing their job. `VALUE_SHAPED` stays what it
# is -- the vocabulary of *ambiguity*, entries that could stand in for a
# merchant's answer to a check (D-031).
# ---------------------------------------------------------------------------
#: `rubric.md` 4/D3: option names that name nothing. A closed list -- a name is
#: judged against these literals and against emptiness, never against a notion
#: of how meaningful it reads. Held in `engine/checks.py` from P3.1 until
#: D-031 moved it here: D-022 puts every scoring vocabulary in this module, and
#: leaving one option-name set outside it while adding another beside it would
#: have made the split arbitrary. The move is behaviour-neutral.
#:
#: Note `option 1` carries a digit, so this set could not join `VALUE_SHAPED`
#: even if the leak scan wanted it. That is the digit assertion working: a
#: reserved platform default is a structural name, not a vague value.
VARIANT_OPTION_NAMES_RESERVED = frozenset([
    "title", "default", "default title", "option 1", "option 2", "option 3",
])

#: `rubric.md` 4/D3 states `VARIANT.MEDIA_LINKED` as *"Where variants differ
#: visually (color/finish/shade), each has linked media. Conditional on a
#: visual option existing."* Three of these four are that parenthesis,
#: transcribed; D-024 reads a `rubric.md` parenthesis as a closed list rather
#: than an illustration, and the same reading applies here. `colour` is an
#: orthographic variant of a listed word, not a new kind.
#:
#: `tone` and `pattern` are **deliberately absent**. Neither is in `rubric.md`,
#: and adding them would widen a check the rubric closed -- the change D-024
#: rejected. Under-detection is the permitted direction, and a colour axis
#: named outside this list simply leaves the check deferred (D-031).
VARIANT_MEDIA_LINKED_VISUAL_OPTION_NAMES = frozenset([
    "color", "colour", "finish", "shade",
])

# ---------------------------------------------------------------------------
# Unit vocabulary. Spellings only. Nothing here says a millilitre relates to a
# fluid ounce, and nothing here may (D-006; DEC-6).
# ---------------------------------------------------------------------------
LENGTH_UNITS = frozenset(["mm", "cm", "m", "in", "inch", "inches", "ft"])
MASS_UNITS = frozenset(["g", "kg", "oz", "lb", "lbs"])
VOLUME_UNITS = frozenset(["ml", "l", "cl", "floz"])
TIME_UNITS = frozenset(["day", "days", "week", "weeks", "month", "months",
                        "year", "years", "yr", "yrs"])

UNIT_TOKENS = LENGTH_UNITS | MASS_UNITS | VOLUME_UNITS | TIME_UNITS

#: A number followed by a time unit, anywhere in a normalized value. Used by
#: the two warranty predicates. Longest spellings first so that "years" is not
#: matched as "year" with a stray "s".
_TIME_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%s)\b"
    % "|".join(sorted(TIME_UNITS, key=len, reverse=True)))

#: A magnitude with a unit attached, for splitting dimension segments.
_MAGNITUDE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([a-z\"']*)\s*$")

#: `us 10`, `eu42`, `uk 8.5`.
_SIZE_STANDARD_RE = re.compile(
    r"^(?:%s)\s*\d+(?:\.\d+)?$" % "|".join(sorted(
        APPAREL_SIZE_SYSTEM_STANDARDS, key=len, reverse=True)))


def states_duration(value):
    # type: (str) -> bool
    """A number and a time unit appear together somewhere in the value."""
    return _TIME_RE.search(normalize(value)) is not None


def is_bare_duration(value):
    # type: (str) -> bool
    """The value is a duration and provably nothing else."""
    text = normalize(value)
    match = _TIME_RE.match(text)
    return match is not None and match.end() == len(text)


def is_size_standard(value):
    # type: (str) -> bool
    return _SIZE_STANDARD_RE.match(normalize(value)) is not None


def magnitude(segment):
    # type: (str) -> Optional[Tuple[str, str]]
    """(magnitude, unit spelling) for one whole segment, or None."""
    match = _MAGNITUDE_RE.match(normalize(segment))
    if not match:
        return None
    return match.group(1), match.group(2)


# ---------------------------------------------------------------------------
# The two audited groupings, and the invariants.
# ---------------------------------------------------------------------------
VALUE_SHAPED = frozenset(
    APPAREL_INTENDED_USE_CONTEXT_VAGUE
    | APPAREL_CARE_INSTRUCTIONS_VAGUE
    | HOME_CARE_AND_CLEANING_VAGUE
    | BEAUTY_USAGE_DIRECTIONS_VAGUE
    | SPORTS_USE_ENVIRONMENT_VAGUE
    | ELEC_COMPATIBILITY_VAGUE
    | APPAREL_SUSTAINABILITY_CREDENTIALS_VAGUE
    | APPAREL_COLOR_FINISH_VAGUE
    | SPORTS_SPORT_OR_ACTIVITY_VAGUE
    | APPAREL_SIZE_SYSTEM_BARE_LABELS
    | SPORTS_SKILL_OR_INTENSITY_LEVEL_TIERS
)  # type: FrozenSet[str]

ALL_ENTRIES = (VALUE_SHAPED | UNIT_TOKENS | APPAREL_SIZE_SYSTEM_STANDARDS
               | VARIANT_OPTION_NAMES_RESERVED
               | VARIANT_MEDIA_LINKED_VISUAL_OPTION_NAMES)

#: Tokens a lexicon entry may never contain. A lexicon describes the *shape* of
#: an answer; a digit or a unit inside an entry would make the entry itself a
#: measurement, which is a product fact.
_DIGIT_RE = re.compile(r"\d")


def assert_no_product_values():
    # type: () -> None
    """No entry is a fact about a product. Mirrors the audit's own allowlist
    assertion (`evals/audits/factlex.assert_allowlist_has_no_values`).

    Three properties, each a different way the module could fail open:

    * **No value-shaped entry carries a digit.** A measurement, a proportion,
      a model number or a duration is a product fact. A vague phrase is not.
    * **No entry is empty or unnormalized**, so membership cannot be satisfied
      by an accident of whitespace.
    * **No unit relates to another unit.** There is no mapping here, only a
      set of spellings, and the assertion is that the module exposes no
      pair-shaped structure that could hold a conversion.
    """
    for entry in VALUE_SHAPED:
        assert entry, "empty lexicon entry"
        assert entry == normalize(entry), "unnormalized entry %r" % entry
        assert not _DIGIT_RE.search(entry), (
            "lexicon entry %r carries a digit, which makes it a measurement "
            "rather than a vocabulary term" % entry)
    for entry in ALL_ENTRIES:
        assert entry and entry == normalize(entry), "bad entry %r" % entry
    # D-024: this set holds attribute *keys*. A value here would be a product
    # fact wearing a key's clothes, and it would silently widen a check the
    # rubric closed.
    # D-031: the two option-name sets are names, never values. Asserting the
    # disjointness is what keeps "excluded from the leak scan" a property of
    # what these entries *are* rather than a convenience.
    for name in VARIANT_OPTION_NAMES_RESERVED | VARIANT_MEDIA_LINKED_VISUAL_OPTION_NAMES:
        assert name not in VALUE_SHAPED, (
            "%r is an option name and a value-shaped entry; one of the two is "
            "wrong" % name)
    assert not (VARIANT_OPTION_NAMES_RESERVED
                & VARIANT_MEDIA_LINKED_VISUAL_OPTION_NAMES), (
        "an option name cannot be both a reserved default and a visual axis")
    for key in IDENT_TITLE_DISTINGUISHING_KEYS:
        assert taxonomy_keys.is_attribute_key(key), (
            "%r is not a taxonomy attribute key" % key)
        assert key not in VALUE_SHAPED, "%r is a value, not a key" % key
    for name, value in sorted(globals().items()):
        if name.startswith("_") or not isinstance(value, dict):
            continue
        raise AssertionError(
            "%s is a mapping; a lexicon holds sets of spellings, never a "
            "table relating one term to another (D-006)" % name)


assert LEXICON_VERSION == R.RUBRIC_VERSION, (
    "LEXICON_VERSION %s does not match RUBRIC_VERSION %s; a lexicon is a "
    "scoring artifact and is versioned with the rubric (D-022)"
    % (LEXICON_VERSION, R.RUBRIC_VERSION))
assert_no_product_values()
