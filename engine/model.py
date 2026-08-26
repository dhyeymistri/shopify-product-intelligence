"""The canonical internal product representation: the Normalized Product Record.

PRD 6.1 defines the shape; this module is the constructor for it, and the only
place an NPR is built. Records are plain JSON-serializable dicts. That is a
deliberate choice, not laziness: PIP input is already NPR-shaped (PRD 5.3, where
"normalization is the identity function"), the fabrication audit consumes JSON,
and a dict keeps round-tripping honest -- what the engine holds is exactly what
a human reads in the file.

PRD 6.2 design rules, restated because they are what this module enforces:

  1. Every value is a ``{value, src}`` pair. A bare scalar is a spec violation.
  2. ``null`` means absent in the source. Never coerced to ``false``/``0``/``""``.
  3. The NPR is not a merge. Two disagreeing sources become two `attributes[]`
     entries with the same ``key``; the conflict is a check's problem (PRD 9.2).
  4. Normalization never enriches. Map, group, extract, preserve. Nothing else.
  5. Attribute keys come from ``taxonomy.md``; anything else stays raw.

Tags
----
``tags`` is a first-class member: one ``{value, src}`` record per source tag,
each with its own locator so it is individually quotable. PRD 6.1's original
0.1 skeleton omitted it -- an oversight, since `taxonomy.md` 2 makes `tag_map`
the fourth-order category signal and a record without tags cannot be classified
by that rule. Spec 0.1.1 amends 6.1 to carry it, and this module implements
what that section now specifies.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

#: D-033 moved this to 0.2: `variants[*].option_values` carries `{value, src}`
#: pairs rather than bare scalars, so that a variant's option value can be
#: evidenced at its own locator (PRD 6.2 rule 1).
NPR_VERSION = "0.2"

#: Origins a value may carry (PRD 9.4).
ORIGIN_STRUCTURED = "merchant_structured"
ORIGIN_PROSE = "merchant_prose"
ORIGIN_PLACEHOLDER = "merchant_placeholder"
ORIGINS = frozenset([ORIGIN_STRUCTURED, ORIGIN_PROSE, ORIGIN_PLACEHOLDER])

#: Input formats (PRD 5).
FORMAT_CSV = "shopify_csv"
FORMAT_GRAPHQL = "shopify_graphql"
FORMAT_PIP = "pip_json"
FORMATS = frozenset([FORMAT_CSV, FORMAT_GRAPHQL, FORMAT_PIP])

#: Present-but-asserting-nothing values, enumerated by PRD 5.4 and 9.4.
#: Treated as absent by checks, with the literal text kept here so evidence can
#: report what was actually found. Compared case-insensitively after stripping.
PLACEHOLDERS = frozenset(["n/a", "tbd", "-", ".", "xxx"])

IDENTITY_FIELDS = (
    "title", "brand", "model_or_mpn", "handle", "product_type", "declared_category",
)
NARRATIVE_VALUE_FIELDS = (
    "description_text", "description_html", "seo_title", "seo_description",
)
TOP_LEVEL_FIELDS = (
    "npr_version", "product_id", "source", "identity", "narrative", "attributes",
    "options", "variants", "media", "metafields", "tags", "claims", "raw_extras",
)


# ---------------------------------------------------------------------------
# value carriers
# ---------------------------------------------------------------------------

def value(text, src):
    # type: (Optional[str], Optional[str]) -> Dict[str, Any]
    """A ``{value, src}`` pair. Absent input yields ``{"value": None, "src": None}``.

    A value that is absent has no location, so carrying a locator for it would
    be a locator that resolves to nothing -- PRD 6.2 rule 2 with rule 1.
    """
    if text is None:
        return {"value": None, "src": None}
    return {"value": text, "src": src}


def absent():
    # type: () -> Dict[str, Any]
    return {"value": None, "src": None}


def is_placeholder(text):
    # type: (Optional[str]) -> bool
    """True for a value that is present but asserts nothing (PRD 9.4)."""
    if not isinstance(text, str):
        return False
    return text.strip().lower() in PLACEHOLDERS


def origin_for(text, structured):
    # type: (Optional[str], bool) -> str
    """Assign an origin (PRD 9.4). Placeholder detection is literal, not semantic."""
    if is_placeholder(text):
        return ORIGIN_PLACEHOLDER
    return ORIGIN_STRUCTURED if structured else ORIGIN_PROSE


def attribute(key, value_raw, origin, src, scope="product"):
    # type: (str, Optional[str], str, Optional[str], str) -> Dict[str, Any]
    return {"key": key, "value_raw": value_raw, "origin": origin, "src": src, "scope": scope}


def option(name, values, src):
    # type: (str, List[str], Optional[str]) -> Dict[str, Any]
    return {"name": name, "values": list(values), "src": src}


def variant(variant_id, option_values=None, sku=None, barcode=None, price=None,
            media_refs=None, attributes=None):
    # type: (...) -> Dict[str, Any]
    """``option_values`` maps option name to a ``{value, src}`` pair (D-033).

    Not a bare scalar: an option value is merchant-supplied data that a check
    reasons over and must be able to quote, so PRD 6.2 rule 1 reaches it like
    any other value. Callers build the pair with :func:`value`, which is what
    keeps the locator beside the thing it locates.
    """
    return {
        "variant_id": variant_id,
        "option_values": dict(option_values or {}),
        "sku": sku if sku is not None else absent(),
        "barcode": barcode if barcode is not None else absent(),
        "price": price if price is not None else price_value(None, None),
        "media_refs": list(media_refs or []),
        "attributes": list(attributes or []),
    }


def price_value(text, src, currency=None):
    # type: (Optional[str], Optional[str], Optional[str]) -> Dict[str, Any]
    """A price carrier.

    ``currency`` stays ``None`` unless the input states one. The documented
    Shopify CSV columns (PRD 5.1) carry no currency column, and deriving one
    from a store's settings would be inventing a fact the file does not hold.
    """
    if text is None:
        return {"value": None, "currency": currency, "src": None}
    return {"value": text, "currency": currency, "src": src}


def media(url, alt=None, scope="product", src=None):
    # type: (str, Optional[Dict[str, Any]], str, Optional[str]) -> Dict[str, Any]
    return {"url": url, "alt": alt if alt is not None else absent(),
            "scope": scope, "src": src}


def metafield(namespace, key, val, src, type_=None):
    # type: (str, str, Optional[str], Optional[str], Optional[str]) -> Dict[str, Any]
    return {"namespace": namespace, "key": key, "value": val, "type": type_, "src": src}


def claim(text, src):
    # type: (str, Optional[str]) -> Dict[str, Any]
    return {"text": text, "src": src}


def empty_narrative():
    # type: () -> Dict[str, Any]
    return {
        "description_text": absent(),
        "description_html": absent(),
        "structure": {"has_lists": False, "has_tables": False,
                      "has_headings": False, "word_count": 0},
        "seo_title": absent(),
        "seo_description": absent(),
    }


def new_npr(product_id, source_format, source_file, source_locator):
    # type: (str, str, str, Optional[str]) -> Dict[str, Any]
    """An empty NPR with every member present. Members are never omitted.

    A missing member and an absent value are different states, and only one of
    them is expressible (PRD 6.2 rule 2). Emitting the full skeleton means a
    consumer never has to guess which it is looking at.
    """
    return {
        "npr_version": NPR_VERSION,
        "product_id": product_id,
        "source": {"format": source_format, "file": source_file,
                   "locator": source_locator},
        "identity": dict((field, absent()) for field in IDENTITY_FIELDS),
        "narrative": empty_narrative(),
        "attributes": [],
        "options": [],
        "variants": [],
        "media": [],
        "metafields": [],
        "tags": [],
        "claims": [],
        "raw_extras": {},
    }
