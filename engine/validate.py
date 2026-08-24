"""Validation: structural, and provenance.

Two questions, kept separate because they fail for different reasons.

``validate_npr`` asks whether the record is shaped like an NPR (PRD 6.1, 6.2):
every value a ``{value, src}`` pair, absence expressed only as ``null``, variant
identifiers unique, option names and values non-empty and distinct, scopes
naming variants that exist.

``validate_provenance`` asks the harder question -- whether the record is *true
to its input*: does every ``src`` resolve, and does what it resolves to match
the value stored next to it, byte for byte. A value whose locator resolves
somewhere else, or to something else, is a fabricated fact with a citation
attached, which is worse than one without.

Both return run errors rather than raising. PRD 5.4 requires a bad record to be
named and skipped, not to end the run.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import errors, model
from .locators import LocatorError, parse_csv, parse_pip

_VALUE_KEYS = ("value", "src")


def _is_pair(node):
    # type: (Any) -> bool
    return isinstance(node, dict) and "value" in node and "src" in node


def _pair_errors(where, node, record):
    # type: (str, Any, str) -> List[errors.RunError]
    if not _is_pair(node):
        return [errors.RunError(
            errors.INVALID_NPR, record,
            "%s is not a {value, src} pair; a bare scalar in the NPR is a spec "
            "violation (PRD 6.2 rule 1)" % where)]
    out = []
    if node["value"] is None and node["src"] is not None:
        out.append(errors.RunError(
            errors.INVALID_PROVENANCE, record,
            "%s is absent but carries a locator; an absent value has no location "
            "(PRD 6.2 rules 1 and 2)" % where))
    if node["value"] is not None and node["src"] is None:
        out.append(errors.RunError(
            errors.INVALID_PROVENANCE, record,
            "%s has a value with no locator, so nothing it supports could be "
            "evidenced (PRD 6.2 rule 1)" % where))
    if node["value"] is not None and not isinstance(node["value"], (str, int, float, bool)):
        out.append(errors.RunError(
            errors.MALFORMED_VALUE, record,
            "%s holds %s, expected a scalar or null"
            % (where, type(node["value"]).__name__)))
    return out


def validate_npr(npr):
    # type: (dict) -> List[errors.RunError]
    """Structural validation of one NPR. Returns run errors; never raises."""
    out = []  # type: List[errors.RunError]
    record = npr.get("product_id") or "<unidentified record>"

    for field in model.TOP_LEVEL_FIELDS:
        if field not in npr:
            out.append(errors.RunError(
                errors.INVALID_NPR, record,
                "missing NPR member %r; members are never omitted, because an "
                "omitted member and an absent value are different states "
                "(PRD 6.1)" % field))

    source = npr.get("source")
    if not isinstance(source, dict) or source.get("format") not in model.FORMATS:
        out.append(errors.RunError(
            errors.INVALID_NPR, record,
            "source.format must be one of %s (PRD 6.1)"
            % ", ".join(sorted(model.FORMATS))))

    identity = npr.get("identity") or {}
    for field in model.IDENTITY_FIELDS:
        out.extend(_pair_errors("identity.%s" % field, identity.get(field), record))
    title = identity.get("title")
    if not (title.get("value") if isinstance(title, dict) else None):
        out.append(errors.RunError(
            errors.MISSING_IDENTITY, record,
            "identity.title is absent; a product with no title cannot be "
            "identified in a report (PRD 5.1, rubric.md D1)"))

    narrative = npr.get("narrative") or {}
    for field in model.NARRATIVE_VALUE_FIELDS:
        out.extend(_pair_errors("narrative.%s" % field, narrative.get(field), record))
    structure = narrative.get("structure")
    if not isinstance(structure, dict):
        out.append(errors.RunError(
            errors.INVALID_NPR, record, "narrative.structure must be an object"))

    variant_ids = []  # type: List[str]
    for position, variant in enumerate(npr.get("variants") or []):
        where = "variants[%d]" % position
        if not isinstance(variant, dict):
            out.append(errors.RunError(
                errors.INVALID_NPR, record, "%s is not an object" % where))
            continue
        variant_id = variant.get("variant_id")
        if not isinstance(variant_id, str) or not variant_id.strip():
            out.append(errors.RunError(
                errors.INVALID_NPR, record,
                "%s has no variant_id, so no locator can address it "
                "(PRD 8.2.1)" % where))
        elif variant_id in variant_ids:
            out.append(errors.RunError(
                errors.DUPLICATE_VARIANT_ID, record,
                "variant_id %r appears more than once; a locator selecting it "
                "would be ambiguous (PRD 8.2.1 rule 1)" % variant_id))
        else:
            variant_ids.append(variant_id)
        for field in ("sku", "barcode"):
            out.extend(_pair_errors("%s.%s" % (where, field), variant.get(field), record))
        price = variant.get("price")
        if not isinstance(price, dict) or "value" not in price or "src" not in price:
            out.append(errors.RunError(
                errors.INVALID_NPR, record,
                "%s.price must be a {value, currency, src} carrier" % where))
        if not isinstance(variant.get("option_values"), dict):
            out.append(errors.RunError(
                errors.INVALID_NPR, record,
                "%s.option_values must be an object" % where))

    seen_options = set()
    for position, opt in enumerate(npr.get("options") or []):
        where = "options[%d]" % position
        name = (opt or {}).get("name") if isinstance(opt, dict) else None
        if not isinstance(name, str) or not name.strip():
            out.append(errors.RunError(
                errors.INVALID_NPR, record,
                "%s has an empty option name (PRD 9.7 option integrity)" % where))
            continue
        if name in seen_options:
            out.append(errors.RunError(
                errors.CONTRADICTORY_VARIANT_STRUCTURE, record,
                "option name %r is declared twice (PRD 9.7)" % name))
        seen_options.add(name)
        values = opt.get("values")
        if not isinstance(values, list):
            out.append(errors.RunError(
                errors.INVALID_NPR, record, "%s.values must be a list" % where))
            continue
        seen_values = set()
        for item in values:
            if not isinstance(item, str) or not item.strip():
                out.append(errors.RunError(
                    errors.INVALID_NPR, record,
                    "%s holds an empty option value (PRD 9.7)" % where))
            elif item in seen_values:
                out.append(errors.RunError(
                    errors.CONTRADICTORY_VARIANT_STRUCTURE, record,
                    "option %r lists the value %r twice (PRD 9.7)" % (name, item)))
            seen_values.add(item)

    for position, attribute in enumerate(npr.get("attributes") or []):
        out.extend(_scope_errors("attributes[%d]" % position, attribute,
                                 variant_ids, record))
    for position, item in enumerate(npr.get("media") or []):
        if isinstance(item, dict):
            out.extend(_scope_errors("media[%d]" % position, item, variant_ids, record))

    for position, tag in enumerate(npr.get("tags") or []):
        out.extend(_pair_errors("tags[%d]" % position, tag, record))

    if not isinstance(npr.get("raw_extras"), dict):
        out.append(errors.RunError(
            errors.INVALID_NPR, record, "raw_extras must be an object (PRD 6.1)"))
    return out


def _scope_errors(where, node, variant_ids, record):
    # type: (str, Any, List[str], str) -> List[errors.RunError]
    out = []
    if not isinstance(node, dict):
        return [errors.RunError(errors.INVALID_NPR, record, "%s is not an object" % where)]
    if "origin" in node and node.get("origin") not in model.ORIGINS:
        out.append(errors.RunError(
            errors.INVALID_NPR, record,
            "%s.origin %r is not one of %s (PRD 9.4)"
            % (where, node.get("origin"), ", ".join(sorted(model.ORIGINS)))))
    scope = node.get("scope")
    if scope is None:
        return out
    if scope == "product":
        return out
    if not isinstance(scope, str) or not scope.startswith("variant:"):
        out.append(errors.RunError(
            errors.INVALID_NPR, record,
            "%s.scope %r must be 'product' or 'variant:<id>' (PRD 9.7)"
            % (where, scope)))
        return out
    target = scope.split(":", 1)[1]
    if target not in variant_ids:
        out.append(errors.RunError(
            errors.CONTRADICTORY_VARIANT_STRUCTURE, record,
            "%s is scoped to variant %r, which this product does not contain; a "
            "scope that names nothing cannot be resolved per variant (PRD 9.7)"
            % (where, target)))
    return out


# ---------------------------------------------------------------------------
# provenance
# ---------------------------------------------------------------------------

def iter_locators(npr):
    # type: (dict) -> List[tuple]
    """Every ``(path, value, locator)`` triple the record asserts.

    ``value`` is what the NPR claims is at ``locator``. `None` means the value
    is not a text assertion (a media URL carrier, say) and only the locator's
    resolvability is checked.
    """
    out = []

    def pair(path, node, expected_key="value"):
        if _is_pair(node) and node.get("src"):
            out.append((path, node.get(expected_key), node["src"]))

    for field, node in (npr.get("identity") or {}).items():
        pair("identity.%s" % field, node)
    narrative = npr.get("narrative") or {}
    for field in model.NARRATIVE_VALUE_FIELDS:
        pair("narrative.%s" % field, narrative.get(field))
    for position, tag in enumerate(npr.get("tags") or []):
        pair("tags[%d]" % position, tag)
    for position, attribute in enumerate(npr.get("attributes") or []):
        if isinstance(attribute, dict) and attribute.get("src"):
            out.append(("attributes[%d]" % position, attribute.get("value_raw"),
                        attribute["src"]))
    for position, field in enumerate(npr.get("metafields") or []):
        if isinstance(field, dict) and field.get("src"):
            out.append(("metafields[%d]" % position, field.get("value"), field["src"]))
    for position, item in enumerate(npr.get("claims") or []):
        if isinstance(item, dict) and item.get("src"):
            out.append(("claims[%d]" % position, item.get("text"), item["src"]))
    for position, item in enumerate(npr.get("media") or []):
        if isinstance(item, dict) and item.get("src"):
            out.append(("media[%d]" % position, item.get("url"), item["src"]))
        if isinstance(item, dict):
            pair("media[%d].alt" % position, item.get("alt"))
    for position, opt in enumerate(npr.get("options") or []):
        if isinstance(opt, dict) and opt.get("src"):
            out.append(("options[%d].name" % position, None, opt["src"]))
    for position, variant in enumerate(npr.get("variants") or []):
        if not isinstance(variant, dict):
            continue
        where = "variants[%d]" % position
        pair("%s.sku" % where, variant.get("sku"))
        pair("%s.barcode" % where, variant.get("barcode"))
        price = variant.get("price")
        if isinstance(price, dict) and price.get("src"):
            out.append(("%s.price" % where, price.get("value"), price["src"]))
        for attr_position, attribute in enumerate(variant.get("attributes") or []):
            if isinstance(attribute, dict) and attribute.get("src"):
                out.append(("%s.attributes[%d]" % (where, attr_position),
                            attribute.get("value_raw"), attribute["src"]))
    return out


def validate_locator_syntax(locator, source_format):
    # type: (str, str) -> Optional[str]
    """Parse-only check. Returns a reason string, or None if the locator parses."""
    try:
        if source_format == model.FORMAT_CSV:
            parse_csv(locator)
        else:
            parse_pip(locator)
    except LocatorError as exc:
        return str(exc)
    return None


def validate_provenance(npr, source):
    # type: (dict, Any) -> List[errors.RunError]
    """Prove every locator resolves and reproduces the value stored beside it."""
    out = []  # type: List[errors.RunError]
    record = npr.get("product_id") or "<unidentified record>"
    source_format = (npr.get("source") or {}).get("format")
    product_id = npr.get("product_id")

    for path, expected, locator in iter_locators(npr):
        if not isinstance(locator, str):
            out.append(errors.RunError(
                errors.INVALID_PROVENANCE, record,
                "%s has a non-string locator %r" % (path, locator)))
            continue
        reason = validate_locator_syntax(locator, source_format)
        if reason:
            out.append(errors.RunError(
                errors.BROKEN_LOCATOR, record,
                "%s: locator %r does not parse: %s" % (path, locator, reason)))
            continue
        # A locator on a node with no text of its own (an option element) is
        # still provenance: it must resolve, but it has nothing to reproduce.
        view = None if isinstance(expected, str) else "node"
        resolution = source.resolve(locator, product_id=product_id, view=view)
        if not resolution.ok:
            out.append(errors.RunError(
                errors.BROKEN_LOCATOR, record,
                "%s: locator %r does not resolve: %s"
                % (path, locator, resolution.error)))
            continue
        if expected is None or not isinstance(expected, str):
            continue
        if resolution.text == expected:
            continue
        # PRD 8.2: a span is an offset into the plain-text extraction while the
        # HTML is retained, so a description value legitimately matches the
        # extracted view rather than the raw cell. Both are the same input.
        alternate = source.resolve(locator, product_id=product_id, view="text")
        if alternate.ok and alternate.text == expected:
            continue
        out.append(errors.RunError(
            errors.NON_REPRODUCIBLE_EXCERPT, record,
            "%s: %r is not what %r resolves to (%r); a value that cannot be "
            "reproduced at its locator cannot be evidenced (PRD 8.3 rule 4)"
            % (path, expected, locator, resolution.text)))
    return out
