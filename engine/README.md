# `engine/` — the product engine

Two layers so far. **P2, the normalizer:** input becomes one Normalized Product
Record per product (PRD §6.1), with locators that resolve back to the file the
values came from (PRD §8.2). **P3.1, the deterministic check layer:** a versioned
check registry, and a runner that turns an NPR into evidence-backed findings.

Scoring is not here. The registry fixes each check's points, and nothing sums
them: aggregation is a later phase (`AGENTS.md` §6).

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

### P3.1 — checks

| Module | Responsibility |
| --- | --- |
| `taxonomy_data.py` | `taxonomy.md` §3–§6 and §8 as data: tier, scope, inheritance, conditional trigger, satisfying predicate, conflict severity, category mapping. |
| `rubric_data.py` | `rubric.md` §4 as data: the fixed checks of D1 and D3–D8, dimension allocations, grade bands, status vocabulary. |
| `registry.py` | `CheckDef`, the applicable check set per category, D2 derived from tier populations, and the import-time invariants. |
| `findings.py` | The finding and evidence contract (PRD §7.3, §8.1), the evidence gate, deterministic ordering, `unknowns[]`, `questions_for_merchant[]`. |
| `evidence.py` | Evidence constructors that resolve and byte-verify before returning. |
| `facts.py` | `checked_paths` → candidates, with placeholders and scope preserved. |
| `classify.py` | Category assignment (`taxonomy.md` §2), evidenced and labelled. |
| `checks.py` | Status determination: presence, absence, coverage, conflict. |
| `runner.py` | Applicable set → findings → sealed ledger. No score. |

### P3.2 — recognition

| Module | Responsibility |
| --- | --- |
| `lexicon.py` | Every scoring vocabulary: vague-phrase sets, unit spellings, size standards, performance tiers, and the two option-name sets — the reserved platform defaults and the visual axes `VARIANT.MEDIA_LINKED` triggers on. One module, versioned with `rubric.md`, with an import-time assertion that no entry is a product value (D-022, D-031). |
| `recognize.py` | The predicates themselves. Each reads one supplied value and returns a boolean. No prose, no world knowledge, no other product. |

`registry.IMPLEMENTED_PREDICATES`, `IMPLEMENTED_RELATIONS` and
`IMPLEMENTED_STRUCTURAL` are what make "implemented" a registry fact: the
import-time invariants refuse to load a predicate no check declares, or one
owned by a penalty check. The three registries hold the three shapes a
predicate can take — a property of one supplied value, a relation between two
supplied fields, and structural arithmetic over the whole record. Only the
first is reachable through `CheckDef.recognize`; the other two are invoked by
their own dispatched handler.

**25 of the 116 declared predicates are implemented**, across 19 checks:
9.00 points of category-independent `raw_max` (D1 6.00, D5 3.00) plus, per
category, apparel 9.90, sports 8.25, electronics 7.59, beauty 6.60 and home
5.72 — all of it previously unreachable by deferral. The remaining 91 stay
deferred, and the deferral ledger now distinguishes *no evaluator exists* from
*the predicate ran and abstained*, so the residue is measured rather than
assumed (D-019).

### P3.2 slice D — structural coverage over taxonomy data

Two D3 checks that need no lexicon of values and read no prose, implemented as
dispatched handlers rather than value predicates:

- **`VARIANT.ATTRIBUTE_COVERAGE`** (3.00) counts a variant covered when every
  non-inheritable variant-scope attribute *for the category* is **present** on
  it — `rubric.md` §4/D3's own word. The attribute's own recognition predicate
  is never run, so this check does not inherit its uncertainty (D-030). Where
  the category requires nothing per variant — an empty set, or `uncategorized`
  — the runner removes the check as `NOT_APPLICABLE` before it runs, on the
  precedent `rubric.md` §4/D2 sets for the same missing field (D-029).
- **`VARIANT.MEDIA_LINKED`** (1.50) runs only once an option name matches the
  closed visual vocabulary `color`, `colour`, `finish`, `shade`. No match is a
  **deferral, never `NOT_APPLICABLE`**: the axis may be named outside the list,
  and removing points from a denominator on that assumption is what PRD §10.3
  forbids (D-031).

Both determine everything structurally — set membership, presence, arithmetic —
so both report the structural confidence arm (D-020), and neither is on the
recognition path PRD §9.5 caps.

`unnamed_eco_claim` is written and deliberately **not registered**: its
`taxonomy.md` §5.1 cell routes an unnamed eco claim to D7 as unsupported, and
the awarding half may not ship without the subtracting half (D-027).

Format B (Shopify Admin GraphQL JSON, PRD §5.2) is not implemented. It is
refused by name rather than guessed at.

## What the check layer refuses to do

- **`FAIL` needs something present to be wrong.** Every path that can emit one
  takes a non-empty list of supplied values as a required argument, so a `FAIL`
  on absence is a type error rather than a matter of discipline.
- **`UNKNOWN` costs nothing.** Zero earned, zero penalty, always (D-003).
- **No winner in a conflict.** Two locations become two evidence items and a
  question that quotes both back. There is no rule preferring a metafield to a
  description, or the longer value to the shorter.
- **No guess where recognition is needed.** A check that cannot decide a stated
  value deterministically emits *no finding* and records the deferral. Absence
  and conflict are still decided, because both are exact. Under-recognition
  deflates a score and carries honest evidence; a guess can state something
  false about a product.
- **No predicate has a negative arm.** A predicate that does not fire says
  *undecided*, never *absent* and never *wrong*. There is no path from a
  recognition verdict to a `FAIL`, an `UNKNOWN` or a penalty.
- **A variant is covered only when its own value satisfies the check** (D-021).
  An ambiguous variant value is quoted at its own locator and named as
  uncovered; it is never reported as an empty field, and it is never weighted
  as half of a covered variant. One unreadable variant silences the whole
  check rather than being counted against the product. Where *every* variant
  carries a value, `rubric.md` §3.1's ambiguity clause acts as a floor under
  the coverage clause (D-025).
- **Recognition never reports `high` confidence** (D-026, PRD §9.5). The
  finding carries `determination`, so a report can say which arm reached it.
- **A check may not claim more than the rubric defines.**
  `IDENT.TITLE_DISTINGUISHING` reads only attributes that are one of the five
  kinds `rubric.md` §4/D1 names, and reads no option values at all (D-024).
- **No question that answers itself.** Every question is a fixed registry string
  or a fixed frame filled with byte-verified excerpts, so a remediation cannot
  introduce a value the data does not hold (PRD §7.6).

## What normalization refuses to do

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
