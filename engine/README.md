# `engine/` — the product engine

Phase P2 of [`AGENTS.md`](../AGENTS.md): the **normalizer**. Input becomes one
Normalized Product Record per product (PRD §6.1), with locators that resolve
back to the file the values came from (PRD §8.2).

Python 3.9+, standard library only. No network, no dependencies, no persistence.

## What it does

| Module | Responsibility |
| --- | --- |
| `normalize.py` | Public surface: `normalize_file`, `normalize_document`, `detect_format`. |
| `model.py` | The canonical representation. The only place an NPR is built. |
| `csv_input.py` | Format A — Shopify product CSV (PRD §5.1). |
| `pip_input.py` | Format C — PIP JSON (PRD §5.3). |
| `locators.py` | Locator grammar for both formats: parse, build, resolve. |
| `sources.py` | The supplied input, kept resolvable, so provenance can be *checked*. |
| `validate.py` | Structural validation, and proof that every value reproduces at its locator. |
| `htmltext.py` | Plain-text extraction and structure signals for description HTML. |
| `taxonomy_keys.py` | The attribute keys from `taxonomy.md`, for exact matching only. |

Format B (Shopify Admin GraphQL JSON, PRD §5.2) is not implemented. It is
refused by name rather than guessed at.

## What it refuses to do

Normalization maps, groups, extracts and preserves. It does not enrich (PRD §6.2
rule 4), and the refusals are the substance of the layer:

- **No inheritance between scopes.** A value stated on one variant describes that
  variant. `taxonomy.md` §4.3 makes inheritance a per-attribute property that
  only a check may apply, so the normalizer never applies it.
- **No semantic key mapping.** A metafield becomes an `attributes[]` entry only
  when its key is *literally* a taxonomy attribute key. Reading `custom.material`
  as `material_composition` is near-duplicate detection, which PRD §9.5 permits
  to a labelled check and never here.
- **No merging and no winners.** Two rows of a handle group that disagree keep
  both values with both locators (PRD §6.2 rule 3, AGENTS.md §5 rule 10).
- **No classification.** Category assignment is inference (`taxonomy.md` §2).
- **No claim extraction.** PRD §6.1 and §9.6 place claim recognition in the check
  phase: §9.6's patterns are illustrative, not a normative lexicon, and applying
  a guessed one here would put a check's judgment in the input layer where it
  could not be labelled or evidenced. `claims[]` is carried through from PIP
  input and left empty for CSV.
- **No repair.** A malformed record is skipped and named in a run error
  (PRD §5.4). A meaning-changing repair is indistinguishable from an invented
  fact once the input file is out of view.

## Provenance is checked, not asserted

`NormalizationResult` carries the source document alongside the records, and
every record is validated before it is returned: each `src` must parse, must
resolve, and must resolve to the value stored next to it. A record that fails is
kept out with a run error. A value that cannot be reproduced at its locator
cannot be evidence (PRD §8.3 rule 4), and one that carries a locator resolving
somewhere else is worse than one with no locator at all — it looks sourced.

## Locators

Defined normatively in PRD §8.2 / §8.2.1; not restated here.

- **Format A:** `row<N>.<Column Name>` with an optional `[start:end]` span.
  `<N>` is the 1-based **CSV record index** with the header as `row1`, so a
  quoted cell containing newlines cannot desync every locator after it.
  Metafield columns are addressed by their canonical identity
  `product.metafields.<namespace>.<key>`, never by the export header's label.
- **Format C:** the grammar in PRD §8.2.1, resolved against one product record.

`evals/audits/pip_locator.py` implements the same PIP grammar independently.
That duplication is deliberate: the fabrication audit is the definition of
correctness for engine output (AGENTS.md §6), and an audit resolving locators
with the engine's own resolver could not catch a resolver bug.

## Points where P2 asked the specification a question

All three were raised with P2 and answered by spec 0.1.1; this layer implements
what the PRD now says, and none of them changed its behavior.

- **`tags[]`** — absent from PRD §6.1's original skeleton, though `taxonomy.md`
  §2 makes `tag_map` the fourth-order category signal. §6.1 now carries the
  member: one `{value, src}` record per tag, each with its own locator.
- **Divergent product-level values** in one CSV handle group. PRD §5.1's
  carry-down rule reads the product-level value off the first row; §6.2 rule 6
  now states plainly that this is a reading rule and not a resolution rule, and
  that every occurrence is preserved in `raw_extras` for a check to cite.
- **Claim extraction** — PRD §9.6's patterns are illustrative, not a lexicon.
  §6.1 and §9.6 now place claim recognition in the check phase, where it is
  labelled and evidenced.
