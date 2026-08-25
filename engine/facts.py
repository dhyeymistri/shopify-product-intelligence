"""Gather the candidate values a check is allowed to look at.

A check never walks the NPR itself. It declares `checked_paths` and this module
walks them, which is what keeps two things true at once:

* the paths a finding claims to have searched are exactly the paths that were
  searched, so absence evidence cannot drift away from the search that produced
  it (PRD 8.3 rule 5); and
* every candidate carries the `src` the normalizer already proved resolvable
  (`validate.validate_provenance`), so a check copies a locator and never
  constructs one.

The path grammar here addresses the **NPR**, not the input file. It is a
different namespace from a locator (PRD 8.2), which addresses the input, and
the two are kept apart deliberately: they look alike, and conflating them is
the easiest way to produce a false gap.

Matching a metafield to an attribute is **exact key equality**. Deciding that
`custom.material` "means" `material_composition` is near-duplicate detection,
which PRD 9.5 permits only as a labelled inference inside a check -- never
silently while gathering facts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import htmltext
from .model import is_placeholder

#: Narrative fields that hold prose. A value stated only in prose has to be
#: recognized before it can be credited, and recognition is not part of this
#: phase -- so these paths are searched for *text*, and their contents are
#: reported as unrecognized rather than silently treated as empty.
PROSE_PATHS = ("narrative.description_text", "narrative.description_html",
               "narrative.seo_description", "narrative.seo_title")


class Candidate(object):
    """One supplied value found at a searched path."""

    __slots__ = ("value", "src", "origin", "scope", "ref", "npr_path", "key",
                 "text")

    def __init__(self, value, src, origin, npr_path, scope="product", ref=None,
                 key=None, text=None):
        # type: (str, Optional[str], str, str, str, Optional[str], Optional[str], Optional[str]) -> None
        self.value = value
        self.src = src
        self.origin = origin
        self.scope = scope
        self.ref = ref
        self.npr_path = npr_path
        self.key = key
        #: The plain-text reading of `value`, when the two differ. PRD 5.4
        #: extracts text from description HTML for analysis and retains the
        #: markup for evidence offsets, so a candidate carries both: `value`
        #: is what gets quoted at the locator, `text` is what gets judged.
        #: Everything else passes `None` and the two are the same string.
        self.text = value if text is None else text

    @property
    def is_placeholder(self):
        # type: () -> bool
        """PRD 9.4: a placeholder is present but asserts nothing.

        It is absent for the purpose of every check except the one whose job is
        to quote it (`STRUCT.NO_PLACEHOLDER_VALUES`).

        Decided on `text`, not on `value`. A description of `<p>N/A</p>` states
        exactly what a description of `N/A` states; letting the markup hide the
        placeholder made a field that asserts nothing read as unread prose, and
        that in turn suppressed an `UNKNOWN` the merchant should have been
        asked about. Detection stays literal (PRD 9.4) -- extraction is what
        moved, not the vocabulary.
        """
        return is_placeholder(self.text)

    def __repr__(self):  # pragma: no cover - debugging aid
        return "Candidate(%r at %s)" % (self.value, self.src)


class Gathered(object):
    """The result of walking one check's `checked_paths`."""

    __slots__ = ("candidates", "unrecognized_prose", "searched_paths")

    def __init__(self, candidates, unrecognized_prose, searched_paths):
        # type: (List[Candidate], List[Candidate], Tuple[str, ...]) -> None
        self.candidates = candidates
        #: Prose that was found at a searched path and not read. Its presence
        #: is why a check may not conclude UNKNOWN: something is there, and
        #: this phase cannot say whether it answers the check.
        self.unrecognized_prose = unrecognized_prose
        self.searched_paths = searched_paths

    @property
    def stated(self):
        # type: () -> List[Candidate]
        """Candidates that assert something. Placeholders are not among them."""
        return [c for c in self.candidates if not c.is_placeholder]

    @property
    def placeholders(self):
        # type: () -> List[Candidate]
        return [c for c in self.candidates if c.is_placeholder]


# ---------------------------------------------------------------------------
# path handlers
# ---------------------------------------------------------------------------
def _pair(node, src_default=None):
    # type: (Any, Optional[str]) -> Tuple[Optional[str], Optional[str]]
    """A ``{value, src}`` carrier's contents, or (None, None)."""
    if not isinstance(node, dict):
        return None, None
    value = node.get("value")
    if not isinstance(value, str) or not value.strip():
        return None, None
    return value, node.get("src") or src_default


def _product_attributes(npr, key):
    # type: (dict, Optional[str]) -> List[Candidate]
    out = []
    for item in npr.get("attributes") or []:
        if key is not None and item.get("key") != key:
            continue
        value = item.get("value_raw")
        if not isinstance(value, str) or not value.strip():
            continue
        out.append(Candidate(
            value, item.get("src"), item.get("origin") or "merchant_structured",
            "attributes[%s]" % item.get("key"),
            scope=item.get("scope") or "product", key=item.get("key")))
    return out


def _variant_attributes(npr, key):
    # type: (dict, Optional[str]) -> List[Candidate]
    out = []
    for variant in npr.get("variants") or []:
        vid = variant.get("variant_id")
        for item in variant.get("attributes") or []:
            if key is not None and item.get("key") != key:
                continue
            value = item.get("value_raw")
            if not isinstance(value, str) or not value.strip():
                continue
            out.append(Candidate(
                value, item.get("src"),
                item.get("origin") or "merchant_structured",
                "variants[%s].attributes" % vid, scope="variant", ref=vid,
                key=item.get("key")))
    return out


def _metafields(npr, key):
    # type: (dict, Optional[str]) -> List[Candidate]
    """Metafields whose key *is* the attribute key. No aliasing, ever."""
    out = []
    for item in npr.get("metafields") or []:
        if key is not None and item.get("key") != key:
            continue
        value = item.get("value")
        if not isinstance(value, str) or not value.strip():
            continue
        out.append(Candidate(
            value, item.get("src"), "merchant_structured",
            "metafields.%s.%s" % (item.get("namespace"), item.get("key")),
            key=item.get("key")))
    return out


def _identity(npr, field):
    # type: (dict, Optional[str]) -> List[Candidate]
    out = []
    identity = npr.get("identity") or {}
    fields = [field] if field and field != "*" else sorted(identity)
    for name in fields:
        value, src = _pair(identity.get(name))
        if value is None:
            continue
        out.append(Candidate(value, src, "merchant_structured",
                             "identity.%s" % name))
    return out


def _narrative(npr, field):
    # type: (dict, Optional[str]) -> List[Candidate]
    value, src = _pair((npr.get("narrative") or {}).get(field))
    if value is None:
        return []
    # PRD 5.4: text is extracted for analysis, the markup is retained for
    # evidence offsets. The quote still comes from `value` at its locator.
    text = htmltext.to_text(value) if htmltext.looks_like_html(value) else value
    return [Candidate(value, src, "merchant_prose", "narrative.%s" % field,
                      text=text)]


def _variant_field(npr, field):
    # type: (dict, str) -> List[Candidate]
    out = []
    for variant in npr.get("variants") or []:
        vid = variant.get("variant_id")
        node = variant.get(field)
        value, src = _pair(node)
        if value is None:
            continue
        out.append(Candidate(value, src, "merchant_structured",
                             "variants[%s].%s" % (vid, field),
                             scope="variant", ref=vid))
    return out


def _variant_option_values(npr):
    # type: (dict) -> List[Candidate]
    out = []
    for variant in npr.get("variants") or []:
        vid = variant.get("variant_id")
        for name, value in sorted((variant.get("option_values") or {}).items()):
            if not isinstance(value, str) or not value.strip():
                continue
            out.append(Candidate(
                value, "variants[%s].option_values[%s]" % (vid, name),
                "merchant_structured",
                "variants[%s].option_values" % vid, scope="variant", ref=vid,
                key=name))
    return out


def _options(npr, part):
    # type: (dict, Optional[str]) -> List[Candidate]
    out = []
    for option in npr.get("options") or []:
        name = option.get("name")
        if part in (None, "name") and isinstance(name, str) and name.strip():
            out.append(Candidate(name, option.get("src"), "merchant_structured",
                                 "options[%s].name" % name, scope="option",
                                 ref=name, key=name))
        if part == "values":
            for value in option.get("values") or []:
                if not isinstance(value, str) or not value.strip():
                    continue
                out.append(Candidate(
                    value, "options[%s].values" % name, "merchant_structured",
                    "options[%s].values" % name, scope="option", ref=name,
                    key=name))
    return out


def _media(npr, part):
    # type: (dict, Optional[str]) -> List[Candidate]
    out = []
    for index, item in enumerate(npr.get("media") or []):
        if part == "alt":
            value, src = _pair(item.get("alt"))
            if value is None:
                continue
            out.append(Candidate(value, src, "merchant_structured",
                                 "media[%d].alt" % index, ref=str(index)))
        else:
            url = item.get("url")
            if isinstance(url, str) and url.strip():
                out.append(Candidate(url, item.get("src"), "merchant_structured",
                                     "media[%d]" % index, ref=str(index)))
    return out


def _claims(npr):
    # type: (dict) -> List[Candidate]
    out = []
    for index, item in enumerate(npr.get("claims") or []):
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            out.append(Candidate(text, item.get("src"), "merchant_prose",
                                 "claims[%d]" % index, ref=str(index)))
    return out


def _tags(npr):
    # type: (dict) -> List[Candidate]
    out = []
    for index, item in enumerate(npr.get("tags") or []):
        value, src = _pair(item)
        if value is None:
            continue
        out.append(Candidate(value, src, "merchant_structured",
                             "tags[%d]" % index, ref=str(index)))
    return out


def _resolve_path(npr, pattern, key):
    # type: (dict, str, Optional[str]) -> List[Candidate]
    """One `checked_paths` pattern -> the candidates found at it.

    The grammar is closed on purpose. An unknown pattern raises rather than
    returning an empty list, because "searched and found nothing" and "never
    searched" must never be the same value.
    """
    if pattern.startswith("attributes["):
        inner = pattern[len("attributes["):-1]
        return _product_attributes(npr, None if inner == "*" else inner)
    if pattern == "variants[*].attributes":
        return _variant_attributes(npr, key)
    if pattern == "metafields.*":
        return _metafields(npr, key)
    if pattern.startswith("identity."):
        return _identity(npr, pattern.split(".", 1)[1])
    if pattern == "narrative.structure":
        return []          # read directly by STRUCT.DESCRIPTION_PARSEABLE
    if pattern.startswith("narrative."):
        return _narrative(npr, pattern.split(".", 1)[1])
    if pattern == "variants[*].option_values":
        return _variant_option_values(npr)
    if pattern.startswith("variants[*]."):
        return _variant_field(npr, pattern.split(".", 1)[1])
    if pattern.startswith("options[*]"):
        rest = pattern[len("options[*]"):]
        return _options(npr, rest[1:] if rest.startswith(".") else None)
    if pattern.startswith("media[*]"):
        rest = pattern[len("media[*]"):]
        return _media(npr, rest[1:] if rest.startswith(".") else None)
    if pattern == "claims[*]":
        return _claims(npr)
    if pattern == "tags[*]":
        return _tags(npr)
    raise ValueError("unsupported checked_path pattern %r" % (pattern,))


def gather(npr, check):
    # type: (dict, Any) -> Gathered
    """Walk one check's declared paths and return what is there.

    Prose is separated from structured values because reading it needs
    recognition (D-019) -- but a prose field holding a *placeholder* is not
    unread prose. It asserts nothing (PRD 9.4), so it is absent for every
    check's satisfaction purpose and quotable by the one check whose job is to
    quote it. Dropping it entirely was wrong twice over: it left
    `STRUCT.NO_PLACEHOLDER_VALUES` unable to report a placeholder at a path it
    declares it searched, and it let a placeholder description count as
    something unread, which suppressed the `UNKNOWN` that field should raise.
    """
    candidates = []  # type: List[Candidate]
    prose = []  # type: List[Candidate]
    seen = set()
    for pattern in check.checked_paths:
        found = _resolve_path(npr, pattern, check.attribute_key)
        is_prose = pattern in PROSE_PATHS
        for candidate in found:
            fingerprint = (candidate.npr_path, candidate.src, candidate.value)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            if is_prose and not candidate.is_placeholder:
                prose.append(candidate)
            else:
                candidates.append(candidate)
    return Gathered(candidates, prose, tuple(check.checked_paths))
