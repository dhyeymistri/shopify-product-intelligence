"""Format C -- PIP JSON -> Normalized Product Record.

PRD 5.3 describes Format C as the format where "normalization is the identity
function", and that is the point of it: it keeps the normalizer honest by giving
us an input whose correct output we already know.

So this module maps and completes; it does not transform. Members present in the
record are carried through verbatim, members absent from the record are filled
with the empty skeleton (PRD 6.1), and top-level members the NPR does not define
are preserved in ``raw_extras`` rather than dropped (PRD 5.4).

The fixture envelope is not input. ``pip_version`` and everything under
``fixture`` are metadata about the file (PRD 5.3.1), and a fact appearing only
there is fabricated exactly as if it appeared nowhere. Nothing in this module
reads them, and `PipSource` cannot resolve a locator into them.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from . import errors, model
from .sources import PipSource

#: Members of the NPR (PRD 6.1). Anything else on a record is unknown.
KNOWN_MEMBERS = frozenset(model.TOP_LEVEL_FIELDS)

BATCH_CEILING = 200  # PRD 5.4 / decisions.md D-013


def normalize(document, file=None):
    # type: (dict, Optional[str]) -> Tuple[List[dict], List[errors.RunError], PipSource]
    """Normalize a PIP document into NPRs.

    Raises ``NormalizationRefused`` when the document is not a PIP file. PRD 5.4
    refuses an unrecognized format rather than guessing a mapping.
    """
    if not isinstance(document, dict):
        raise errors.NormalizationRefused(
            "not a PIP document: top level is %s, expected an object with a "
            "'products' member (PRD 5.3.1)" % type(document).__name__)
    if "products" not in document:
        raise errors.NormalizationRefused(
            "not a PIP document: no 'products' member (PRD 5.3.1)")
    records = document.get("products")
    if not isinstance(records, list):
        raise errors.NormalizationRefused(
            "not a PIP document: 'products' is %s, expected a list"
            % type(records).__name__)

    source = PipSource(document, file=file)
    run_errors = []  # type: List[errors.RunError]
    products = []  # type: List[dict]
    seen = set()  # type: set

    if len(records) > BATCH_CEILING:
        run_errors.append(errors.RunError(
            errors.BATCH_CEILING, file or "<input>",
            "%d products supplied; the V0 batch ceiling is %d, so the first %d "
            "were processed (decisions.md D-013)"
            % (len(records), BATCH_CEILING, BATCH_CEILING)))
        records = records[:BATCH_CEILING]

    for position, record in enumerate(records):
        where = "products[%d]" % position
        if not isinstance(record, dict):
            run_errors.append(errors.RunError(
                errors.MALFORMED_RECORD, where,
                "record is %s, expected an object" % type(record).__name__))
            continue
        product_id = record.get("product_id")
        if not isinstance(product_id, str) or not product_id.strip():
            run_errors.append(errors.RunError(
                errors.MISSING_IDENTITY, where,
                "no usable 'product_id'; the record cannot be addressed by a "
                "locator and so cannot carry evidence (PRD 8.2)"))
            continue
        if product_id in seen:
            run_errors.append(errors.RunError(
                errors.DUPLICATE_PRODUCT_ID, where,
                "product_id %r is already used by an earlier record; the record "
                "was skipped rather than merged" % product_id))
            continue
        seen.add(product_id)
        npr, record_errors = _build(record, product_id, where, file)
        run_errors.extend(record_errors)
        products.append(npr)

    return products, run_errors, source


def _build(record, product_id, where, file):
    # type: (dict, str, str, Optional[str]) -> Tuple[dict, List[errors.RunError]]
    run_errors = []  # type: List[errors.RunError]
    supplied_source = record.get("source")
    npr = model.new_npr(
        product_id, model.FORMAT_PIP, file, "products[%s]" % product_id)
    if isinstance(supplied_source, dict):
        # The record's own account of where it came from is supplied data; keep
        # it, and only fill in what it does not state.
        merged = dict(npr["source"])
        merged.update(supplied_source)
        if not merged.get("file"):
            merged["file"] = file
        npr["source"] = merged

    npr["npr_version"] = record.get("npr_version") or model.NPR_VERSION

    identity = record.get("identity")
    if isinstance(identity, dict):
        for field in model.IDENTITY_FIELDS:
            if field in identity:
                npr["identity"][field] = identity[field]
        for field in identity:
            if field not in model.IDENTITY_FIELDS:
                run_errors.extend(_stash(npr, "identity.%s" % field,
                                         identity[field], where))

    narrative = record.get("narrative")
    if isinstance(narrative, dict):
        for field in model.NARRATIVE_VALUE_FIELDS:
            if field in narrative:
                npr["narrative"][field] = narrative[field]
        if isinstance(narrative.get("structure"), dict):
            npr["narrative"]["structure"] = narrative["structure"]
        for field in narrative:
            if field not in model.NARRATIVE_VALUE_FIELDS and field != "structure":
                run_errors.extend(_stash(npr, "narrative.%s" % field,
                                         narrative[field], where))

    for member in ("attributes", "options", "variants", "media", "metafields",
                   "tags", "claims"):
        supplied = record.get(member)
        if isinstance(supplied, list):
            npr[member] = list(supplied)
        elif supplied is not None:
            run_errors.append(errors.RunError(
                errors.MALFORMED_RECORD, "%s.%s" % (where, member),
                "%r is %s, expected a list; the member was left empty and the "
                "supplied value preserved in raw_extras"
                % (member, type(supplied).__name__)))
            run_errors.extend(_stash(npr, member, supplied, where))

    supplied_extras = record.get("raw_extras")
    if isinstance(supplied_extras, dict):
        npr["raw_extras"].update(supplied_extras)
    elif supplied_extras is not None:
        run_errors.extend(_stash(npr, "raw_extras", supplied_extras, where))

    for field in record:
        if field in KNOWN_MEMBERS:
            continue
        run_errors.extend(_stash(npr, field, record[field], where))

    return npr, run_errors


def _stash(npr, key, val, where):
    # type: (dict, str, object, str) -> List[errors.RunError]
    """Preserve an unknown member verbatim (PRD 5.4). Never interpret, never drop."""
    if key in npr["raw_extras"] and npr["raw_extras"][key] != val:
        return [errors.RunError(
            errors.RAW_EXTRAS_COLLISION, "%s.%s" % (where, key),
            "unknown member %r cannot be preserved: raw_extras already holds a "
            "different value under that name, and overwriting it would discard "
            "supplied data" % key)]
    npr["raw_extras"][key] = val
    return []
