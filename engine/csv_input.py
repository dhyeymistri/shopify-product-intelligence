"""Format A -- Shopify product CSV -> Normalized Product Record.

The obligations are PRD 5.1's, and they are the whole of this module:

  * group rows by ``URL handle``; a handle group is one product;
  * carry product-level fields down from the first row of the group, and never
    read an empty cell on a continuation row as an empty value;
  * a row contributing only an image is a media row, not a variant;
  * preserve the source row number and column name for every extracted value.

What this module refuses to do is as load-bearing as what it does. It does not
copy a value from one variant onto another (`taxonomy.md` 4.3 makes inheritance
a per-attribute property that only a check may apply). It does not read meaning
into a metafield key. It does not resolve a disagreement between two rows. And
it does not drop a column it was not told about -- PRD 5.4 requires unknown
fields preserved verbatim in ``raw_extras``.

Column vocabulary is exactly PRD 5.1's documented set. Legacy export headers are
deliberately absent: adding an alias we have not verified against a primary
source would be inventing a Shopify fact (AGENTS.md 7).
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any, Dict, List, Optional, Tuple

from . import errors, htmltext, model, taxonomy_keys
from .locators import csv_locator
from .sources import CsvSource

# -- documented columns (PRD 5.1) -------------------------------------------
COL_TITLE = "Title"
COL_HANDLE = "URL handle"
COL_DESCRIPTION = "Description"
COL_VENDOR = "Vendor"
COL_CATEGORY = "Product category"
COL_TYPE = "Type"
COL_TAGS = "Tags"
COL_STATUS = "Status"
COL_SKU = "SKU"
COL_BARCODE = "Barcode"
COL_PRICE = "Price"
COL_COMPARE_AT = "Compare-at price"
COL_WEIGHT = "Weight value (grams)"
COL_PRODUCT_IMAGE = "Product image URL"
COL_IMAGE_ALT = "Image alt text"
COL_VARIANT_IMAGE = "Variant image URL"
COL_SEO_TITLE = "SEO title"
COL_SEO_DESCRIPTION = "SEO description"

OPTION_NAME_COLUMNS = ["Option%d name" % n for n in (1, 2, 3)]
OPTION_VALUE_COLUMNS = ["Option%d value" % n for n in (1, 2, 3)]

#: Columns whose value belongs to the product, read from the group's first row.
PRODUCT_COLUMNS = (
    [COL_TITLE, COL_HANDLE, COL_DESCRIPTION, COL_VENDOR, COL_CATEGORY, COL_TYPE,
     COL_TAGS, COL_STATUS, COL_SEO_TITLE, COL_SEO_DESCRIPTION]
    + OPTION_NAME_COLUMNS
)

#: A row carrying any of these is a variant row (PRD 5.1: image-only rows are not).
VARIANT_SIGNAL_COLUMNS = (
    OPTION_VALUE_COLUMNS + [COL_SKU, COL_BARCODE, COL_PRICE, COL_COMPARE_AT, COL_WEIGHT]
)

MEDIA_SIGNAL_COLUMNS = [COL_PRODUCT_IMAGE, COL_IMAGE_ALT, COL_VARIANT_IMAGE]

#: Documented columns the NPR (PRD 6.1) has no member for. Preserved verbatim
#: rather than mapped: `Weight value (grams)` is a weight, but which taxonomy
#: attribute it satisfies depends on the category, and choosing one here would
#: be normalization making a check's decision.
UNMAPPED_DOCUMENTED_COLUMNS = (COL_STATUS, COL_COMPARE_AT, COL_WEIGHT)

KNOWN_COLUMNS = frozenset(
    PRODUCT_COLUMNS + VARIANT_SIGNAL_COLUMNS + MEDIA_SIGNAL_COLUMNS
)

#: Metafield export header form, per PRD 5.1:
#: ``<name> (product.metafields.<namespace>.<key>)``
METAFIELD_HEADER_RE = re.compile(
    r"^(?P<label>.*?)\s*\(product\.metafields\.(?P<namespace>[^.()]+)\.(?P<key>[^()]+)\)$"
)

BATCH_CEILING = 200  # PRD 5.4 / decisions.md D-013


def _blank(text):
    # type: (Optional[str]) -> bool
    """Empty or whitespace-only. NOT the same as a placeholder (PRD 5.4)."""
    return text is None or text.strip() == ""


class _MetafieldColumn(object):
    __slots__ = ("header", "namespace", "key", "canonical")

    def __init__(self, header, namespace, key):
        self.header = header
        self.namespace = namespace
        self.key = key
        # PRD 8.2: metafields are addressed by <namespace>.<key> appended to the
        # owning path, so the locator survives a rename of the human-facing label.
        self.canonical = "product.metafields.%s.%s" % (namespace, key)


def _metafield_columns(header):
    # type: (List[str]) -> Dict[str, _MetafieldColumn]
    out = {}
    for name in header:
        match = METAFIELD_HEADER_RE.match(name)
        if match:
            out[name] = _MetafieldColumn(name, match.group("namespace"), match.group("key"))
    return out


def read_rows(text):
    # type: (str) -> Tuple[List[str], List[Tuple[int, List[str]]], List[errors.RunError]]
    """Parse CSV text into a header and numbered records.

    Row numbers are record indices with the header as row 1. A record whose
    cell count disagrees with the header is malformed: padding it would invent
    empty values and truncating it would discard supplied ones, so it is
    skipped with a run error (PRD 5.4).
    """
    reader = csv.reader(io.StringIO(text, newline=""))
    run_errors = []  # type: List[errors.RunError]
    header = None  # type: Optional[List[str]]
    rows = []  # type: List[Tuple[int, List[str]]]
    number = 0
    for cells in reader:
        number += 1
        if header is None:
            header = [cell.strip() for cell in cells]
            continue
        if len(cells) != len(header):
            run_errors.append(errors.RunError(
                errors.MALFORMED_RECORD, "row%d" % number,
                "row has %d cells, header declares %d" % (len(cells), len(header))))
            continue
        rows.append((number, cells))
    return header or [], rows, run_errors


def _split_tags(cell):
    # type: (str) -> List[Tuple[str, int, int]]
    """Split a Tags cell into (tag, start, end) with exact offsets into the cell.

    Offsets, not just values, because each tag must be individually quotable at
    a locator that a human can check (PRD 8.2).
    """
    out = []
    position = 0
    for piece in cell.split(","):
        start = position
        position += len(piece) + 1
        stripped = piece.strip()
        if not stripped:
            continue
        offset = start + piece.index(stripped)
        out.append((stripped, offset, offset + len(stripped)))
    return out


class _Group(object):
    """One handle group: the rows that make up a single product."""

    def __init__(self, handle):
        self.handle = handle
        self.rows = []  # type: List[Tuple[int, List[str]]]


def normalize(text, file=None):
    # type: (str, Optional[str]) -> Tuple[List[dict], List[errors.RunError], CsvSource]
    """Normalize a Shopify product CSV into NPRs.

    Raises ``NormalizationRefused`` when the file does not carry the two columns
    the format is defined by. PRD 5.4: an unrecognized format is refused, never
    guessed at.
    """
    header, rows, run_errors = read_rows(text)
    if not header:
        raise errors.NormalizationRefused("empty CSV: no header row")
    missing = [c for c in (COL_TITLE, COL_HANDLE) if c not in header]
    if missing:
        raise errors.NormalizationRefused(
            "not a Shopify product CSV: missing required column(s) %s"
            % ", ".join(repr(c) for c in missing))

    source = CsvSource(header, rows, file=file)
    metafields = _metafield_columns(header)
    for column in metafields.values():
        source.add_alias(column.canonical, column.header)

    index = dict((name, i) for i, name in enumerate(header))

    def get(cells, column):
        # type: (List[str], str) -> str
        position = index.get(column)
        if position is None or position >= len(cells):
            return ""
        return cells[position]

    # -- group by URL handle (PRD 5.1) --------------------------------------
    groups = []  # type: List[_Group]
    by_handle = {}  # type: Dict[str, _Group]
    for number, cells in rows:
        handle = get(cells, COL_HANDLE).strip()
        if not handle:
            run_errors.append(errors.RunError(
                errors.MALFORMED_RECORD, "row%d" % number,
                "no %r: the row cannot be assigned to a product" % COL_HANDLE))
            continue
        group = by_handle.get(handle)
        if group is None:
            group = _Group(handle)
            by_handle[handle] = group
            groups.append(group)
        group.rows.append((number, cells))

    if len(groups) > BATCH_CEILING:
        run_errors.append(errors.RunError(
            errors.BATCH_CEILING, file or "<input>",
            "%d products supplied; the V0 batch ceiling is %d, so the first %d "
            "were processed (decisions.md D-013)"
            % (len(groups), BATCH_CEILING, BATCH_CEILING)))
        groups = groups[:BATCH_CEILING]

    products = []
    for group in groups:
        record, group_errors = _build_product(group, get, index, metafields, source, file)
        run_errors.extend(group_errors)
        if record is not None:
            products.append(record)
    return products, run_errors, source


def _build_product(group, get, index, metafields, source, file):
    # type: (...) -> Tuple[Optional[dict], List[errors.RunError]]
    run_errors = []  # type: List[errors.RunError]
    first_row, first_cells = group.rows[0]
    row_numbers = [n for n, _ in group.rows]

    title = get(first_cells, COL_TITLE)
    if _blank(title):
        run_errors.append(errors.RunError(
            errors.MISSING_IDENTITY, "handle:%s (rows %s)"
            % (group.handle, ", ".join(str(n) for n in row_numbers)),
            "no %r on the first row of the handle group; PRD 5.1 makes Title the "
            "one column a product cannot exist without" % COL_TITLE))
        return None, run_errors

    npr = model.new_npr(
        "handle:%s" % group.handle, model.FORMAT_CSV, file,
        source.record_locator(row_numbers))

    def product_value(column):
        # type: (str) -> Dict[str, Any]
        cell = get(first_cells, column)
        if _blank(cell):
            return model.absent()
        return model.value(cell, csv_locator(first_row, column))

    # -- identity ------------------------------------------------------------
    npr["identity"]["title"] = product_value(COL_TITLE)
    npr["identity"]["brand"] = product_value(COL_VENDOR)
    npr["identity"]["handle"] = product_value(COL_HANDLE)
    npr["identity"]["product_type"] = product_value(COL_TYPE)
    npr["identity"]["declared_category"] = product_value(COL_CATEGORY)
    # `model_or_mpn` has no documented CSV column. It stays absent rather than
    # being read out of the title or the SKU, which would be inference.

    # -- narrative -----------------------------------------------------------
    description = get(first_cells, COL_DESCRIPTION)
    if not _blank(description):
        locator = csv_locator(first_row, COL_DESCRIPTION)
        npr["narrative"]["description_html"] = model.value(description, locator)
        npr["narrative"]["description_text"] = model.value(
            htmltext.to_text(description), locator)
        npr["narrative"]["structure"] = htmltext.structure(description)
    npr["narrative"]["seo_title"] = product_value(COL_SEO_TITLE)
    npr["narrative"]["seo_description"] = product_value(COL_SEO_DESCRIPTION)

    # -- tags ----------------------------------------------------------------
    tags_cell = get(first_cells, COL_TAGS)
    if not _blank(tags_cell):
        for tag, start, end in _split_tags(tags_cell):
            npr["tags"].append(model.value(
                tag, csv_locator(first_row, COL_TAGS, (start, end))))

    # -- options (names are product-level, values are per variant row) --------
    option_names = []  # type: List[Tuple[int, str, str]]
    for position, column in enumerate(OPTION_NAME_COLUMNS):
        name = get(first_cells, column).strip()
        if name:
            option_names.append((position, name, csv_locator(first_row, column)))
    seen_names = set()
    declared = []  # type: List[Tuple[int, str, str]]
    for position, name, locator in option_names:
        if name in seen_names:
            run_errors.append(errors.RunError(
                errors.CONTRADICTORY_VARIANT_STRUCTURE, locator,
                "option name %r is declared twice; option names must be distinct "
                "(PRD 9.7 option integrity)" % name))
            continue
        seen_names.add(name)
        declared.append((position, name, locator))

    option_values = dict((name, []) for _, name, _ in declared)  # type: Dict[str, List[str]]

    # -- rows ----------------------------------------------------------------
    variant_ids = set()
    for number, cells in group.rows:
        is_variant = any(not _blank(get(cells, column)) for column in VARIANT_SIGNAL_COLUMNS)
        if is_variant:
            variant, variant_errors = _build_variant(
                number, cells, get, declared, option_values, variant_ids)
            run_errors.extend(variant_errors)
            if variant is not None:
                npr["variants"].append(variant)
                _attach_variant_image(npr, variant, number, cells, get)
        _attach_product_media(npr, number, cells, get)
        _collect_metafields(npr, number, cells, get, metafields, index)
        _collect_raw_extras(npr, number, cells, get, index, metafields,
                            is_first=(number == first_row))

    for _, name, locator in declared:
        npr["options"].append(model.option(name, option_values[name], locator))

    _record_product_column_divergence(npr, group, get, first_row)
    return npr, run_errors


def _build_variant(number, cells, get, declared, option_values, variant_ids):
    # type: (...) -> Tuple[Optional[dict], List[errors.RunError]]
    run_errors = []  # type: List[errors.RunError]
    sku = get(cells, COL_SKU)
    # A SKU makes a stable, human-recognizable id (PRD 6.1). Without one the row
    # number is the only identity the file supplies; inventing a sequence number
    # would produce an id that does not appear in the input.
    variant_id = "sku:%s" % sku.strip() if not _blank(sku) else "row:%d" % number
    if variant_id in variant_ids:
        run_errors.append(errors.RunError(
            errors.DUPLICATE_VARIANT_ID, csv_locator(number, COL_SKU),
            "variant id %r is already used by an earlier row in this product; the "
            "row was skipped rather than merged, because two rows sharing an "
            "identifier do not state which one a later finding would cite"
            % variant_id))
        return None, run_errors
    variant_ids.add(variant_id)

    values = {}
    for position, name, _ in declared:
        cell = get(cells, OPTION_VALUE_COLUMNS[position])
        if _blank(cell):
            # Absent on this row means absent for this variant. A value present
            # on a sibling row describes that sibling (PRD 9.7, taxonomy.md 4.3).
            continue
        values[name] = cell
        if cell not in option_values[name]:
            option_values[name].append(cell)

    declared_positions = set(position for position, _, _ in declared)
    for position, column in enumerate(OPTION_VALUE_COLUMNS):
        if position in declared_positions:
            continue
        cell = get(cells, column)
        if not _blank(cell):
            run_errors.append(errors.RunError(
                errors.CONTRADICTORY_VARIANT_STRUCTURE, csv_locator(number, column),
                "%r holds %r but the product declares no %r; the value is kept in "
                "raw_extras rather than attached to an option that does not exist"
                % (column, cell, OPTION_NAME_COLUMNS[position])))

    barcode = get(cells, COL_BARCODE)
    price = get(cells, COL_PRICE)
    return model.variant(
        variant_id,
        option_values=values,
        sku=model.value(sku, csv_locator(number, COL_SKU)) if not _blank(sku) else model.absent(),
        barcode=(model.value(barcode, csv_locator(number, COL_BARCODE))
                 if not _blank(barcode) else model.absent()),
        price=(model.price_value(price, csv_locator(number, COL_PRICE))
               if not _blank(price) else model.price_value(None, None)),
    ), run_errors


def _attach_variant_image(npr, variant, number, cells, get):
    url = get(cells, COL_VARIANT_IMAGE)
    if _blank(url):
        return
    alt = get(cells, COL_IMAGE_ALT)
    npr["media"].append(model.media(
        url,
        alt=(model.value(alt, csv_locator(number, COL_IMAGE_ALT))
             if not _blank(alt) else model.absent()),
        scope="variant:%s" % variant["variant_id"],
        src=csv_locator(number, COL_VARIANT_IMAGE)))
    variant["media_refs"].append(url)


def _attach_product_media(npr, number, cells, get):
    url = get(cells, COL_PRODUCT_IMAGE)
    if _blank(url):
        return
    alt = get(cells, COL_IMAGE_ALT)
    npr["media"].append(model.media(
        url,
        alt=(model.value(alt, csv_locator(number, COL_IMAGE_ALT))
             if not _blank(alt) else model.absent()),
        scope="product",
        src=csv_locator(number, COL_PRODUCT_IMAGE)))


def _collect_metafields(npr, number, cells, get, metafields, index):
    """Every metafield column, preserved; only an exact taxonomy key promoted.

    Promotion to ``attributes[]`` is exact-match only (PRD 6.2 rule 5). Reading
    `custom.material` as `material_composition` is near-duplicate detection,
    permitted to a check as labelled inference and never to the normalizer.
    """
    for header_name, column in metafields.items():
        cell = get(cells, header_name)
        if _blank(cell):
            continue
        locator = csv_locator(number, column.canonical)
        npr["metafields"].append(model.metafield(
            column.namespace, column.key, cell, locator))
        if taxonomy_keys.is_attribute_key(column.key):
            npr["attributes"].append(model.attribute(
                column.key, cell, model.origin_for(cell, structured=True),
                locator, scope="product"))


def _collect_raw_extras(npr, number, cells, get, index, metafields, is_first):
    """Preserve every column the NPR has no member for (PRD 5.4).

    Occurrences accumulate as a list because a column can hold a different value
    on every row of a handle group, and collapsing them would discard data.
    """
    for name in index:
        if name in KNOWN_COLUMNS or name in metafields:
            continue
        cell = get(cells, name)
        if _blank(cell):
            continue
        npr["raw_extras"].setdefault(name, []).append(
            {"value": cell, "src": csv_locator(number, name)})
    for name in UNMAPPED_DOCUMENTED_COLUMNS:
        cell = get(cells, name)
        if _blank(cell):
            continue
        npr["raw_extras"].setdefault(name, []).append(
            {"value": cell, "src": csv_locator(number, name)})


def _record_product_column_divergence(npr, group, get, first_row):
    """Keep every occurrence when rows of one group disagree on a product field.

    PRD 5.1 says the product-level value is the one on the group's first row, so
    that is what `identity` carries -- but that is a reading rule, not a
    resolution rule. Two rows stating different titles disagree, and PRD 6.2
    rule 6 forbids the normalizer from choosing between them: every occurrence
    is preserved with its own locator so a D6 conflict check can cite both.
    Nothing is merged and no winner is asserted here.
    """
    for column in PRODUCT_COLUMNS:
        seen = []
        for number, cells in group.rows:
            cell = get(cells, column)
            if _blank(cell):
                continue
            seen.append((number, cell))
        distinct = set(cell for _, cell in seen)
        if len(distinct) > 1:
            npr["raw_extras"].setdefault(column, [])
            npr["raw_extras"][column] = [
                {"value": cell, "src": csv_locator(number, column)}
                for number, cell in seen
            ]
