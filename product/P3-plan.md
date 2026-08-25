# P3 Implementation Plan — Checks & Scoring

**Status:** proposal. No code written, no repository file modified.
**Baseline verified:** 207 tests pass; `python3 evals/run_audits.py --self-test` → 16 cases, 0 unexpected outcomes; `p2-complete` tagged at `a792168`.

Read against: `AGENTS.md`, `product/PRD.md` §5–§12, `product/rubric.md`, `product/taxonomy.md`, `product/decisions.md`, all of `engine/`, all of `evals/audits/`, all 14 fixtures and 14 expectation files.

---

## 0. Summary

P3 turns a Normalized Product Record into an evidence-backed **ledger** of findings plus a **deterministic arithmetic score**. It adds nine modules and one package to `engine/`, three missing audits to `evals/audits/`, and the fixture sets the new checks need in order to have both a pass and a fail path.

**No LLM is required.** Every check, including category classification, prose recognition, conflict detection and claim substantiation, reduces to versioned data tables plus deterministic predicates. §11 states exactly where determinism runs out, why the residual risk is one-directional and safe, and what the smallest model interface would look like if it is ever needed. The recommendation is not to build it.

---

## 1. Two facts about P1/P2 that shape the whole design

### 1.1 Evidence locators are copied, never constructed

`engine/validate.validate_provenance` already proves, for every record that survives normalization, that each `src` parses, resolves against the real input, and byte-reproduces the value stored beside it. A record failing any of those is kept out with a run error.

Therefore:

> **A check never invents a locator. It copies the `src` already on the NPR node it read, optionally composing a character span onto it.**

Consequences:

- Evidence is automatically format-agnostic. The same D2 check emits `row12.Description[27:45]` for a CSV-sourced record and `narrative.description_text[27:45]` for a PIP-sourced one, with no format branching in check code.
- Every evidence locator is resolvable *before* the check runs, because P2 proved the base locator. Only the span composition is new, and it is verified at construction (§5.3).
- This closes the largest fabrication surface with zero new machinery. `FAB002_INVALID_LOCATOR` becomes structurally hard to trigger rather than merely tested for.

### 1.2 `checked_paths` and locators are different namespaces

They look alike and are not.

| | Addresses | Grammar | Example |
|---|---|---|---|
| **locator** (`src`, `evidence.locator`) | the **input file** | PRD §8.2 / §8.2.1 | `row12.Description[27:45]`, `variants[sku:TP-HELM-SM].sku` |
| **`checked_paths`** (absence evidence) | the **NPR**, as a set of path *patterns* | pattern with `*` wildcards | `metafields.*`, `attributes[material_composition]`, `variants[*].attributes` |

PRD §8.1 and both honest report doubles use exactly this. `evals/audits/provenance.value_at_paths` already implements the pattern semantics for the audit side. Conflating the two namespaces is the single easiest way to produce a wrong `FAB011`/`FAB012` outcome, so the plan keeps them in separate modules with separate types.

---

## 2. Architecture

```
                      NPR + SourceDocument            (P2, unchanged)
                              │
        ┌─────────────────────┼──────────────────────┐
        ▼                     ▼                      ▼
   classify.py           registry.py            facts.py
   category +            applicable check       gather candidates
   method +              set for category       at checked_paths
   confidence +          (data, not code)       (+ placeholder → absent)
   evidence                    │                      │
        └─────────────────────┬┴──────────────────────┘
                              ▼
                        checks/*.py            ← recognize.py (spans, never values)
                   candidates → status
                              │
                              ▼
                        evidence.py
              build AND VERIFY each evidence item
                              │
                              ▼
                        ledger.py
        evidence gate · deterministic order · finding ids ·
        unknowns[] · questions_for_merchant[] ranking
                              │
                              ▼
                        scoring.py
        Decimal arithmetic · N/A renormalization · penalties ·
        clamp · grade band · blocker cap on the LABEL only
                              │
                              ▼
                 ProductLedger + Score   → P4 renders
```

Nine modules and one package. Standard library only. No network, no dependency, no model.

### 2.1 The five load-bearing rules

1. **The registry is data, not code.** Every check is a fixed record matching `rubric.md` §3. D2's 11–12 checks per category are *derived* from `taxonomy_data.py` tier populations (`13.2/count(A)`, `6.6/count(B)`, `2.2/count(C)`), never hand-listed. Taxonomy stays authoritative and point totals become self-checking at import time.

2. **Check functions cannot mint product text.** The signature is `(npr, candidates, ctx) -> CheckOutcome(status, evidence[], scope, coverage)`. A check never returns a sentence it authored about the product. All product-specific text enters a finding as a verified evidence excerpt. This satisfies D-017's standing constraint on P3 (*"keep every finding's product-specific content attributable to an evidence item"*) without deciding D-017 itself.

3. **The evidence gate lives inside the engine.** `ledger.add()` drops any finding with an empty evidence array *or* with evidence that fails re-resolution, and emits a `run_error`. PRD §8.3 rule 1 and D-014 mechanism 1 call this structural; a gate that only exists at render time is not structural for the layer that makes findings.

4. **`FAIL` is unreachable from an empty candidate set — by construction.** Every code path capable of emitting `FAIL` takes a non-empty candidate list as a *required* argument, so "FAIL on absence" is a type error rather than a discipline. Only these have such a path: D6 `CONFLICT.*` (two present values), D7 `CLAIM.*` (a present claim), `VARIANT.DIFFERENTIATED`, `VARIANT.IDENTIFIER_UNIQUE`, `STRUCT.NO_PLACEHOLDER_VALUES`. This matches the corpus, where `adv-03`'s placeholder FAIL is the only legitimate FAIL across all 14 fixtures.

5. **`decimal.Decimal`, never `float`.** `13.2/3` and `2.2/3` are non-terminating in binary; AC-Q1 requires byte-identical output across runs and AC-F6 requires an independent recomputation to reproduce the total *exactly*. A fixed `decimal.Context`, quantized only at render per rubric §6.2, gives both. Floats give neither reliably.

---

## 3. Check registry and schema

### 3.1 Record shape

Exactly `rubric.md` §3, with three additions the spec implies but does not spell out:

```python
CheckDef(
    check_id        = "APPAREL.MATERIAL_COMPOSITION",
    dimension       = "D2_category_attributes",
    applies_to      = Applicability(categories=("apparel",), trigger=None),
    scope           = "product",              # product | variant | option | catalog
    max_points      = Decimal("3.30"),
    severity        = {"FAIL": "critical", "UNKNOWN": "major", "PARTIAL": "major"},
    confidence      = ConfidenceRule(structural="high", recognized="medium"),   # ← addition, see Q2
    partial_credit  = Decimal("0.5"),
    checked_paths   = ("attributes[material_composition]", "metafields.*",
                       "narrative.description_text", "variants[*].attributes"),
    question        = "What is the fabric composition, stated as a percentage per fibre?",
    satisfies       = "material_with_proportions",   # ← addition: predicate id
    partial_if      = "material_without_proportions",# ← addition: predicate id
)
```

- `confidence` as a rule rather than a scalar reconciles PRD §7.5 (confidence follows *how the finding was determined*: structural absence is `high`, prose recognition is `medium`) with rubric §5.2 (*"fixed per check, never improvised"*). It is still fixed by definition — it just has two declared arms rather than one. The honest report double `honest-adv-02-helmet.report.json` already uses `high` on a D2 absence, which a single fixed `medium` cannot produce. **Raised as Q2.**
- `satisfies` / `partial_if` name predicates from `predicates.py`, transcribed from `taxonomy.md` §5's "Satisfied by" and "PARTIAL if" columns. Naming them rather than inlining lambdas keeps the taxonomy tables reviewable next to their source.

### 3.2 `check_id` naming is a hard constraint, not a convention

`evals/audits/fabrication_audit._attribute_key_for` derives the attribute key from `check_id.split(".",1)[1].lower()` and uses it to detect false gaps (`FAB012`). Every expectation file already follows it: `SPORTS.SAFETY_CERTIFICATION`, `ELEC.MODEL_IDENTIFIER`, `HOME.MATERIALS_AND_FINISH`, `BEAUTY.KEY_ACTIVES_AND_CONCENTRATION`.

> **D2 `check_id` = `<FAMILY>.<attribute_key.upper()>`, always.** Deviating silently disables the false-gap detector for that check.

Enforced by a registry import-time assertion, not by review.

### 3.3 Import-time invariants (fail loudly, not in a test)

`registry.py` asserts at import:

1. `check_id`s unique; families ⊆ `{IDENT, APPAREL, BEAUTY, ELEC, HOME, SPORTS, VARIANT, USECASE, TRUST, CONFLICT, CLAIM, STRUCT}`.
2. Earned dimensions sum to exactly 82: D1 15 + D2 22 + D3 15 + D4 12 + D5 12 + D8 6. *(Verified by hand against rubric §4: D1 = 4+2+2+2.5+2+2.5 = 15 ✓; D3 = 5+2+2+3+1.5+1.5 = 15 ✓; D4 = 3+3.5+2.5+1.5+1.5 = 12 ✓; D5 = 3+2+2+1.5+2+1.5 = 12 ✓; D8 = 2.5+1+1+0.5+1 = 6 ✓.)*
3. D6 maxima sum ≤ 10, D7 ≤ 8.
4. Every D2 category's tier pools sum to 22.0 exactly.
5. Every check has non-empty `checked_paths` and a non-empty `question` — `rubric.md` §9 rule 3 and 4.
6. No check with `confidence == "low"` carries a penalty or a severity above `minor` — PRD §7.5 rule 2, the guardrail rubric §5.2 says must never be violated by a rubric change.

### 3.4 Question lint — a new, cheap, high-value guard

Every `question` string in the registry is run through `evals/audits/factlex.extract()` against an **empty** provenance index. Any fact-bearing token means the registry itself ships a fabrication into every report that check ever emits. Same for `_EXAMPLE_FRAME_RE` — a registry question containing "e.g." or "such as" is a permanent `FAB013`.

This is a single test over ~50 strings and it makes a whole class of defect impossible to ship.

---

## 4. Category selection

`classify.py`. Fully deterministic. Signals resolved in `taxonomy.md` §2's order, first match wins:

| Order | Method | Signal read from NPR | Confidence |
|---|---|---|---|
| 1 | `operator_override` | invocation parameter | `high` |
| 2 | `declared_category_map` | `identity.declared_category` | `high` |
| 3 | `product_type_map` | `identity.product_type` | `medium` |
| 4 | `tag_map` | `tags[*].value` | `medium` |
| 5 | `title_inference` | `identity.title` + `narrative.description_text` | `low` |
| 6 | `uncategorized` | nothing matched, or same-tier disagreement | `low` |

Rules implemented:

- **Matching** is case-insensitive containment of a §8 term in the signal string.
- **Within one signal**, several terms may match different categories (`"Electronics > Lighting"` hits both `electronics` and `home`). Resolved by §8 row order — the mechanism the activewear note already relies on. **Q5b asks for this to be stated normatively.**
- **Across two same-tier signals** mapping to different categories → `uncategorized` plus an `info` finding naming both (§2 rule 1).
- Evidence is a `field_value` item citing the signal's own `src`. `fabrication_audit` already holds classification evidence to finding-grade standard, so this is not optional.
- A `low`-confidence assignment adds the `minor` finding of §2 rule 4 recommending the merchant set a product category.
- Classification never writes into `attributes[]` (§2 rule 2).

**Verified against the corpus:** 12 of 14 fixtures classify correctly by table lookup alone, including `sparse-apparel-01` → `apparel` via `title_inference` (`"T-Shirt"` contains `shirt`), matching its expectation's `title_inference` / `low`. The exception is `sparse-electronics-01` — see Q5a, a real gap.

---

## 5. Fact and evidence extraction

### 5.1 `facts.py` — candidate gathering

```python
Candidate(value: str, src: str, origin: str, scope: str, npr_path: str, is_placeholder: bool)
```

`gather(npr, checked_paths) -> [Candidate]` walks the NPR once, matching each declared path pattern, and returns every value found with the `src` already attached. Rules:

- **Placeholders are absent, with the placeholder quoted.** `model.is_placeholder` already exists (`n/a`, `tbd`, `-`, `.`, `xxx`). A placeholder candidate is returned with `is_placeholder=True` so that D2 treats it as absent (→ `UNKNOWN`) while `STRUCT.NO_PLACEHOLDER_VALUES` can quote it (→ `FAIL`). `adv-03` requires exactly this split: `IDENT.BRAND_PRESENT` is `UNKNOWN` on `"TBD"` while `STRUCT.NO_PLACEHOLDER_VALUES` is `FAIL` citing three locators.
- **Inheritance is applied here, never in P2.** `taxonomy.md` §4.3 makes it a per-attribute property. A product-scope candidate satisfies a variant requirement only when the attribute is `inheritable: yes`. `garment_measurements`, `net_content`, `color_finish`, `user_fit_specification`, `assembled_dimensions` are `no` and must resolve per variant.
- **No merging.** Two candidates with the same key and different values are returned as two candidates and routed to §6.

### 5.2 `recognize.py` — versioned span recognizers

Only needed where a value lives in prose. Note that for **Format C input the extraction is already supplied data** — the fixtures carry `attributes[]` entries with `origin: merchant_prose` and prose spans as `src` (`sparse-apparel-02` supplies `material_composition = "soft cotton jersey"` at `narrative.description_text[27:45]`). For **Format A (CSV)** nobody pre-extracts, so recognizers are what stand between the description and a false gap.

Recognizers return `[(start, end)]` **spans, never values**. Lexicons are versioned with `rubric.md`, which is the mechanism PRD §9.6 already authorizes verbatim: *"A recognition lexicon, when one is written, belongs to the check that uses it and is versioned with rubric.md."*

Families needed: materials/species, ingredients, units and quantities, dimension triples, durations, percentages, standards and certifying bodies, care/washing terms, size-system markers, generic-term lists (the `"wood"` → PARTIAL case), conditional triggers, use-case frames, claim classes.

`evals/audits/factlex.py` is a working, tested reference for the shape of these patterns — but it must **not** be imported. The engine and the audit must fail independently, exactly as `engine/locators.py` and `evals/audits/pip_locator.py` already do deliberately.

### 5.3 `evidence.py` — construct **and verify**

```python
quote(candidate, span=None)      # excerpt sliced from the SOURCE, not from the NPR
field_value(candidate)
absence(checked_paths)           # checked_paths REQUIRED and non-empty
derived(refs, operation)         # ≥2 referenced items + stated operation
external_reference(candidate)    # recorded as mentioned — never fetched, never verified
```

Every constructor resolves its locator through `engine.sources.SourceDocument.resolve` and asserts byte-equality **before returning**. A failure raises, the finding is dropped, a `run_error` is logged. `span_of(src, start, end)` composes `[a:b]` onto an existing locator and is valid in both grammars.

Excerpt text is sliced out of the *resolved source*, never copied from the NPR. Byte-exactness (PRD §8.3 rule 4, `FAB003`) then holds by construction instead of by convention.

---

## 6. Presence, absence, conflict

The decision procedure every attribute-style check runs, in this fixed order. The ordering is normative — PRD §9.8 requires disagreement to be checked *before* deduplication so a contradiction is never merged away.

```
candidates = facts.gather(npr, check.checked_paths)
non_placeholder = [c for c in candidates if not c.is_placeholder]

1. none                          → UNKNOWN, absence evidence with checked_paths
2. ≥2 and values disagree        → route to D6: FAIL, both cited, no winner
                                   AND zero the D2 attribute (D-012 double cost)
3. ≥2 and values agree           → info merge finding, score once (§9.8)
4. one, satisfies predicate      → PASS
5. one, partial predicate        → PARTIAL (50%, or covered/total for coverage)
6. variant scope, 0 of N covered → UNKNOWN          ← see Q9
7. variant scope, k of N covered → PARTIAL, max × k/N, evidence NAMES the
                                   uncovered variant ids, never "some variants"
```

Notes:

- **Absence evidence is exhaustive by construction**, because the same `checked_paths` tuple drives both the search and the evidence. They cannot drift apart, which is what makes `FAB011`/`FAB012` structurally hard to trigger.
- **Numeric near-values are not conflicts.** `±2%` or an exact unit conversion → `info` `CONFLICT.UNIT_INCONSISTENCY`, penalty 0.0 (rubric §4/D6).
- **Categorical incompatibility uses a closed table** (`machine wash` ⊥ `dry clean only`, `fragrance-free` ⊥ a fragrance ingredient, `waterproof` ⊥ `not water resistant`). Under-detection is the safe failure direction, and rubric §4/D6 rule 4 already mandates it: *"A suspected conflict that cannot be evidenced on both sides is not emitted at all."*
- **No winner, ever.** Both locations become separate evidence items; the remediation question quotes both supplied values back — which PRD §7.6 explicitly permits and §9.2 requires.
- **Severity is `blocker`** when the conflicted attribute is safety-, allergen-, compatibility- or compliance-relevant for the category. That relevance is a per-attribute flag in `taxonomy_data.py`, transcribed from the category-specific rules in `taxonomy.md` §5.2/§5.4/§5.5.

---

## 7. Finding schema

Exactly PRD §7.3. `ledger.py` owns:

- **`finding_id`** — `F-%04d`, assigned after a deterministic sort. Sort key: `(dimension_order, check_id, scope.level, scope.ref or "")`. Never insertion order, or AC-Q1 fails the moment a check is reordered.
- **The evidence gate** — §2.1 rule 3.
- **`unknowns[]`** — one entry per `UNKNOWN` finding: `attribute`, `checked_paths` (the same tuple), `question` (from the registry).
- **`questions_for_merchant[]`** — ranked per D-016: **`blocker` findings pinned to the top**, then descending by points recoverable. Points recoverable for a conflict is `d2_points_zeroed + d6_penalty` — the worked example's *"recovers 1.65 + 3.0 penalty = 4.65"*. Ties break on `check_id` ascending, because D-016 does not specify a tie-break and AC-Q1 needs one.
- **Fixed absence language.** PRD §9.1 fixes it: *"Not stated in the supplied data."* This is on `factlex`'s allowlist already and is the phrase the negation-language audit will be written around.

All finding text is assembled from four sources only — fixed templates, controlled labels (attribute keys, statuses, category names), verified evidence excerpts, and arithmetic from the ledger. That is D-017's structural-assembly model, adopted for P3 output because it is free here: every registry `question` is already a fixed string and every product-specific token is already an evidence excerpt. **P3 does not decide D-017** — that is a P4 question about `report.md` prose — it simply does not foreclose it, as D-017 asks.

---

## 8. Confidence handling

- Assigned by the check definition via `ConfidenceRule` (§3.1), never improvised at runtime.
- `structural` arm (`high`): presence/absence across all checked paths, exact match, arithmetic, uniqueness.
- `recognized` arm (`medium`): bounded recognition over a quoted span. The span is always in the evidence, so a human can overrule it.
- `low`: interpretive judgment a reviewer could dispute — `USECASE.DIFFERENTIATION`, `USECASE.COMPLEMENTARY_CONTEXT`, near-duplicate proposals, `CLAIM.VAGUE_QUALIFIER`.
- **Guardrail, asserted at registry import:** a `low`-confidence finding never carries a penalty and never exceeds `minor` severity (PRD §7.5 rule 2). `CLAIM.VAGUE_QUALIFIER`'s nominal 0.5 is therefore recorded as `info` with penalty 0.0 in V0 — rubric §4/D7 rule 5 states this is deliberate and not an inconsistency.
- **Confidence never hedges a fabrication.** There is no confidence level at which a fact absent from the input may be stated. Enforced by §2.1 rule 2, not by the confidence value.

---

## 9. Remediation questions under §7.6

Three surfaces are bound by §7.6: `remediation.question`, `unknowns[].question`, `questions_for_merchant[].question`. All three read the **same** registry string for a given check, so there is exactly one place a violation could be introduced.

Permitted content is assembled from: the information requested · the target field · the expected unit · the expected format · the axis of an ambiguity · **a value quoted from the supplied data**.

Prohibited: any illustrative value, plausible default, or value inferred from category/brand/price/model.

Three enforcement layers:

1. **Registry lint** (§3.4) — no fact token, no example frame, in any registry question. Catches the defect at import.
2. **Conflict and disambiguation questions** are template + verified excerpt: `"Which is correct — {excerpt_a} or {excerpt_b}?"`. Introducing a value is impossible because both slots are byte-verified excerpts.
3. **`FAB013`** already covers the runtime path and has a regression double (`v13-suggested-value-in-question.report.json`).

`remediation.note` is the fixed string `"Do not generate a value. This must be supplied by the merchant or supplier."` — already on the allowlist, already in both honest doubles.

---

## 10. Deterministic scoring

`scoring.py`, implementing rubric §6.1 with `Decimal`:

```
applicable  = [c for c in checks if c.status != NOT_APPLICABLE]
raw_earned  = Σ earned over applicable earned-dimension checks
raw_max     = Σ max    over applicable earned-dimension checks     # base 82, see Q1
normalized  = raw_earned / raw_max × 100
penalties   = min(Σ D6 penalties, 10) + min(Σ D7 penalties, 8)
total       = clamp(normalized − penalties, 0, 100)
grade       = band(total)
label       = "insufficient" if any blocker finding else grade     # LABEL only
```

- **Penalties apply after renormalization** so a conflict costs the same absolute points regardless of how many checks were N/A (rubric §1.2).
- **D6/D7 are penalty exposure, not earned points** — they never enter `raw_max`.
- **N/A is structural only.** Single-variant → `VARIANT.DIFFERENTIATED` (5.0) + `OPTION_VALUES_CONSISTENT` (2.0) + `ATTRIBUTE_COVERAGE` (3.0) + `MEDIA_LINKED` (1.5) = **11.5** removed, matching rubric §6.3's stated figure exactly. `uncategorized` → all of D2 removed. **A check is never N/A because information is missing** — that is `UNKNOWN`, and conflating them is the scoring failure PRD §10.3 names as the most important to avoid.
- **Rounding only at render** (§6.2): 2dp per check, 1dp for subtotals and total. Where rounded rows cannot sum to the rounded total, the report shows the unrounded total and marks the residual row. Never silently adjust.
- **`max_applicable` and the renormalization factor are reported**, with the list of N/A checks and their structural reasons.

**Q1 is a genuine specification contradiction and must be settled before this is written.** See §13.

---

## 11. Boundary between deterministic code and model reasoning

### 11.1 Conclusion: no model is necessary for V0

Working each of PRD §9.5's three permitted inference sites:

| Permitted site | Deterministic realization | Residual risk |
|---|---|---|
| Category classification | `taxonomy.md` §8 table, row-ordered containment, over four signal tiers | Table gaps — Q5a |
| Language recognition over quoted spans | Versioned recognizer lexicons owned by the check, versioned with `rubric.md` (the mechanism PRD §9.6 authorizes verbatim) | Bounded recall on CSV prose |
| Near-duplicate detection | Closed key-alias table, `info` + `low` confidence | None material — info carries no points |

### 11.2 Why the residual risk is one-directional and acceptable

Two independent reasons, which happen to agree:

1. **Under-recognition cannot lie.** A missed material yields `UNKNOWN` → 0 earned, 0 penalty (D-003). Worst case is a conservatively deflated score carrying honest absence evidence. It cannot produce a false fact.
2. **Only D6 and D7 subtract**, and both are restricted to closed tables where the failure mode is under-detection. That is the correct direction for a penalty mechanism, and rubric §4/D6 rule 4 already mandates it. AC-Q4 (≥90% conflict recall) and AC-Q5 (≥85% recall / ≥90% precision) are measured against fixtures we author to the recognizers' documented coverage.

**The one honest limitation, which belongs in a decision record rather than a comment:** on Format A input nobody pre-extracts prose attributes, so recognizer recall bounds how much prose-stated data can be credited. This is the same class of limit as D-017's lexicon-recall note and should be recorded the same way — named, bounded, and revisited when real reports exist.

### 11.3 If a model is ever needed, the smallest interface is

```python
recognize(text: str, attribute_key: str) -> list[tuple[int, int]]     # SPANS ONLY
```

- Returns spans, never values. The engine slices the span out of the **source** and verifies byte-exactness before use, so the model cannot introduce a token that is not already in the input.
- Sits outside the score path — points stay fixed per check (D-004).
- Sits outside the fact path — it selects, it never supplies.
- Would still be labelled `medium`/`low` confidence with the span quoted, per §9.5 rule 2.

**Recommendation: do not build it in P3.** It is not needed to satisfy any acceptance criterion, and adding it would place a non-deterministic component directly behind AC-Q1's byte-identical requirement.

---

## 12. Modules and files

### 12.1 Create — `engine/`

| File | Responsibility |
|---|---|
| `taxonomy_data.py` | Full transcription of `taxonomy.md` §3–§5 and §8: per attribute — tier, scope, inheritable, conditional trigger, satisfied-by / partial-if predicate ids, safety-relevance flag, severity override. Plus the category mapping table. `taxonomy_keys.py` re-exports from it so existing callers are untouched. |
| `rubric_data.py` | Transcription of `rubric.md` §4: the fixed checks of D1 (6), D3 (6), D4 (5), D5 (6), D6 (6), D7 (5), D8 (5); dimension allocations; grade bands; severity and confidence tables. |
| `registry.py` | Builds the applicable check set for a category; derives D2 checks and points from tier populations; import-time invariants (§3.3). |
| `predicates.py` | Named `satisfies` / `partial_if` predicates from `taxonomy.md` §5's two right-hand columns. Pure, deterministic, individually testable. |
| `classify.py` | Category assignment (§4). |
| `facts.py` | `checked_paths` → candidates; placeholder handling; inheritance (§5.1). |
| `recognize.py` | Versioned deterministic span recognizers (§5.2). |
| `evidence.py` | Evidence constructors that verify against the source; span composition (§5.3). |
| `checks/__init__.py` | Check dispatch table. |
| `checks/ident.py` | D1 — 6 checks. |
| `checks/category_attrs.py` | D2 — table-driven over the assigned category's attribute set. |
| `checks/variant.py` | D3 — 6 checks. |
| `checks/usecase.py` | D4 — 5 checks. |
| `checks/trust.py` | D5 — 6 checks. |
| `checks/conflict.py` | D6 — 6 checks. |
| `checks/claim.py` | D7 — 5 checks. |
| `checks/struct.py` | D8 — 5 checks. |
| `ledger.py` | Finding, ProductLedger, evidence gate, ordering, ids, `unknowns[]`, `questions_for_merchant[]` (§7). |
| `scoring.py` | Decimal arithmetic, renormalization, penalties, grade, blocker cap (§10). |

### 12.2 Create — `evals/`

| File | Responsibility |
|---|---|
| `audits/arithmetic_audit.py` | **AC-F6.** Independently recomputes every score from the ledger. Must not import `engine.scoring` — same independence discipline as `pip_locator.py`. |
| `audits/language_audit.py` | **AC-I5 + AC-I7.** Prohibited absence-as-negation phrases ("does not contain", "is not", "lacks a", "no warranty") and prohibited ranking/visibility phrasing. **Neither audit exists today**, though `AGENTS.md` §8 lists both in the definition of done for P1+. |
| `audits/evidence_integrity.py` | **AC-I4.** Independently re-searches the whole NPR for each absence claim. Broader than `fabrication_audit._check_false_gap`, which today inspects only `product.attributes[]` and would miss a value supplied in a metafield or on a variant. |
| `harness.py` | Projects a `ProductLedger` into the `report.json` shape so `run_audits.py` can run against engine output. See Q13 — this exists only if `report.json` assembly stays in P4. |
| `tests/test_registry.py` | Invariants, point sums, id conventions, **question lint** (§3.4). |
| `tests/test_classify.py` | All 14 fixtures against `expected_category` / `expected_classification_method` / `classification_confidence`. |
| `tests/test_predicates.py` | Each satisfies/partial predicate at both boundaries. |
| `tests/test_checks_*.py` | Per family, both pass and fail paths. |
| `tests/test_scoring.py` | Rubric §7's worked example reproduced to the digit; renormalization; blocker cap on the label only. |
| `tests/test_expectations.py` | Every fixture through the full engine, asserted against its expectation file. The real integration gate. |
| `tests/test_determinism.py` | **AC-Q1.** Triple run, byte-identical modulo `run_id` and timestamps. |

### 12.3 Create — fixtures

`AGENTS.md` §7 requires every new check to have a fixture exercising **both** its pass and its fail path. The corpus today is 14 products (10 sparse + 4 adversarial) — enough to prove absence handling, and not enough to exercise a single D6 or D7 check, or any PASS path at all.

PRD §12.1's remaining sets: `complete/` (10), `conflict/` (8), `claims/` (8), `variants/` (6), `ambiguous/` (4), `duplicates/` (4) — **40 products plus 40 expectation files.** Fixtures are append-only and each needs a provenance note, an intent, at least one declared bait, and `src` locators that resolve; `tests/test_fixtures.py` enforces all of it.

This is a substantial and unavoidable part of P3, not an afterthought. **Q14 asks whether it sits inside P3's gate.**

### 12.4 Modify

| File | Change |
|---|---|
| `product/rubric.md` | Errata and additions from Q1, Q2, Q3, Q4, Q7, Q9, Q12. A scoring change bumps `rubric_version` and updates every affected expectation file in the same commit. |
| `product/taxonomy.md` | Q5a (mapping gaps), Q5b (intra-signal ordering), Q10 (uncategorized D2). |
| `product/decisions.md` | New records: recognizer lexicons and their bounded recall; the renormalization base; the cross-dimension overlap ruling (Q6). Plus any Open Questions raised. |
| `evals/expected/sparse/sparse-apparel-02.expected.json` | Q11 — `color_finish` is asserted present but is supplied nowhere in the fixture. Needs an owner's correction, **not** a relaxation. |
| `AGENTS.md` | §4 layout, §6 phase table at completion. |
| `engine/README.md`, `evals/README.md` | P3 modules, new audits, new fixture sets. |

---

## 13. Unresolved specification questions

Ordered by how much they change the work. Q1, Q5a and Q11 block code; the rest can be carried as stated assumptions.

### Blocking

**Q1 — The renormalization base contradicts itself.**
`rubric.md` §1.2 states the six earned dimensions contribute **82** points of `raw_max`. §7's worked example uses `raw_max = 15+22+15+12+12+6 = 82.0` and annotates *"(D6/D7 are penalty-only)"*. But §6.3's example computes `raw_max = 100 − 11.5 = 88.5`, treating the base as 100 — which double-counts D6 and D7 as earnable.
My arithmetic check of §4 confirms the earned checks sum to exactly 82, so §6.3's example is the stale one. Under an 82 base, that same single-variant electronics case is `raw_max = 70.5`, not 88.5.
**Recommendation:** base is 82; correct §6.3's example; bump `rubric_version`; record the correction. Every expectation file with a score band must be re-derived in the same commit.

**Q5a — `taxonomy.md` §8 cannot classify `sparse-electronics-01`.**
Its expectation demands `electronics` via `title_inference`, but the title *"Auralite Wireless Earbuds"* matches no §8 electronics term (the list has `headphone`, not `earbud`, and neither `wireless` nor `auralite` appears). `declared_category` and `product_type` are both null, so no earlier rule fires either. Under the table as written the result is `uncategorized`, failing both the expectation and AC-Q2 (≥95% classification accuracy).
**Recommendation:** extend the §8 table with a documented, conservative term list for `title_inference` — a taxonomy change with a decision record. Reaching for a model here is the wrong trade: it would put a non-deterministic component behind AC-Q1 to solve a missing-vocabulary problem.

**Q11 — An expectation file asserts a fact the fixture does not contain.**
`sparse-apparel-02.expected.json` lists `color_finish` in `expected_present_attributes`, but the fixture has one option (`Size: S/M/L`), no color option, no color attribute, no metafields and no media. An engine satisfying that expectation would have to **fabricate a color** — the exact failure the corpus exists to catch.
`evals/README.md` says fields asserted today are final and must not be relaxed to make an implementation pass, so this needs an explicit owner correction with rationale, not a quiet edit. **Flagging rather than fixing.**

### Substantive

**Q2 — Confidence: fixed scalar, or fixed per determination path?**
`rubric.md` §3's example fixes `confidence: "medium"` for a whole check, but `honest-adv-02-helmet.report.json` uses `high` on a D2 absence — correct under PRD §7.5, where structural absence is `high` and prose recognition is `medium`. A single scalar cannot produce both.
**Recommendation:** a two-armed `ConfidenceRule` (§3.1). Still fixed by definition, never improvised.

**Q3 — `IDENT.DESCRIPTION_SUBSTANCE` has no deterministic definition.**
*"≥3 distinct informational statements"* is not implementable as written. Rubric §7's worked example counts 2 and yields `UNKNOWN`, without saying what it counted.
**Recommendation:** define a statement as a sentence containing at least one recognized informational signal (a recognized attribute span, a quantity with a unit, a material, a care instruction, or a use-case frame), with each counted sentence quoted in evidence. Add the definition to `rubric.md`. Note this stays inside `rubric.md` §9 rule 5 — it counts information, never words or characters.

**Q4 — `IDENT.TITLE_SPECIFIC` / `TITLE_DISTINGUISHING` have no defined vocabulary.**
*"Names the product type, not only a brand/style name"* needs a source of product-type nouns.
**Recommendation:** PASS when the title contains a leaf token of `declared_category` / `product_type`, or a §8 mapping term. Verified against `adv-01`: *"The Meridian"* with `product_type: "Outerwear"` → UNKNOWN ✓, matching its expectation. And `sparse-apparel-01`: *"Northgate Crew Neck T-Shirt"* contains `shirt` → PASS.

**Q5b — Intra-signal ordering is unstated.**
`sparse-electronics-02`'s `"Electronics > Lighting"` matches both the `electronics` and `home` rows of the same table from a *single* signal. §2 rule 1 (two same-tier signals disagreeing → `uncategorized`) reads as being about two *distinct* signals, and the activewear note says the table is evaluated in row order. The expectation demands `electronics`, which row order gives.
**Recommendation:** state normatively that row order resolves multiple matches within one signal, and §2 rule 1 governs disagreement between two distinct signals.

**Q6 — Cross-dimension attribute overlap.**
`country_of_origin` is both apparel Tier C in D2 and `TRUST.PROVENANCE` in D5. Likewise `certifications` (D5) vs `BEAUTY.CERTIFICATIONS_AND_TESTING` / `ELEC.REGULATORY_CERTIFICATIONS` / `SPORTS.SAFETY_CERTIFICATION`; `warranty_or_guarantee` (D5) vs `ELEC.WARRANTY_TERM`; `USECASE.PRIMARY_USE` (D4) vs `APPAREL.INTENDED_USE_CONTEXT`. PRD §9.8 says *"Never score the same underlying fact twice."*
This may be intentional — `taxonomy.md` §5.3 already establishes that two findings in different dimensions measuring different things are not double-scoring — but the reading is currently left to the implementer.
**Recommendation:** rule explicitly that a fact may satisfy checks in different dimensions, since §9.8's rule is about redundancy *within* attribute coverage, and record it.

**Q7 — `TRUST.CERTIFICATION_REFERENCED` applicability.**
*"Where the category treats certification as decision-relevant"* does not name the categories.
**Recommendation:** applies to all five (Common Core `certifications` is Tier C for every category); absence is `UNKNOWN`, which never penalizes, so the permissive reading is the safe one.

### Minor

**Q9 — Zero variant coverage: `UNKNOWN` or `PARTIAL` at 0?**
`sparse-sports-02` expects `VARIANT.ATTRIBUTE_COVERAGE` = `UNKNOWN` when neither variant carries the attribute. Rubric §3.1 defines PARTIAL as `max × covered/total`, which at `covered=0` also yields 0 earned.
**Recommendation:** confirm the corpus reading normatively — `covered = 0` → `UNKNOWN`; `0 < covered < total` → `PARTIAL`. The distinction matters because `UNKNOWN` produces an `unknowns[]` entry and `PARTIAL` does not.

**Q8 — `VARIANT.OPTION_NAMES_MEANINGFUL` on a product with no options at all.**
Rubric §4/D3 says it still applies for single-variant products, but `sparse-beauty-01` has `options: []`.
**Recommendation:** `UNKNOWN` with absence evidence over `options[*].name`. N/A is reserved for structural triggers, and `UNKNOWN` never penalizes.

**Q10 — `uncategorized` D2 contradicts itself within `taxonomy.md`.**
§2 rule 3 says D2 *"is scored against Common Core"*; §6's table says D2 max is 0 and removed; `rubric.md` §4 agrees with §6.
**Recommendation:** D2 removed entirely (two of three sources agree, and `rubric.md` wins on scoring). Correct §2 rule 3's wording.

**Q12 — `CLAIM.VAGUE_QUALIFIER` ledger presence.**
Rubric §4/D7 rule 5 records it as `info` with no penalty in V0. Confirm it still emits a finding with evidence (so the merchant sees it) while contributing 0.0 to the D7 arithmetic. Reading is clear; noting it so the implementation does not silently drop it.

### Process

**Q13 — Does P3 own `report.json` assembly?**
`AGENTS.md` §6 puts `report.json` in P4. But PRD §8.3 rule 1 and D-014 place the evidence gate *at report assembly*, and `AGENTS.md` §6 requires every report the engine produces to pass `run_audits.py` — which consumes `report.json`.
**Recommendation:** keep the phase boundary. The engine's evidence gate lives in `ledger.py` (satisfying D-014 mechanism 1 where findings are actually made), and a thin `evals/harness.py` projects a ledger into the `report.json` shape so the fabrication audit runs live throughout P3. P4 then owns the real `engine/report.py`, `catalog_summary`, run metadata and `report.md`.
The alternative — moving `report.json` into P3 — is defensible but widens the gate, so it is the owner's call.

**Q14 — Are the six missing fixture sets inside P3's gate?**
40 products plus expectations (§12.3). `AGENTS.md` §7 makes them mandatory for each new check, but `AGENTS.md` §6 describes P1 as the fixture phase.
**Recommendation:** they are P3 work, scheduled per-family alongside the checks that need them (§14), so no check is ever written without a fixture that can fail it.

---

## 14. Recommended implementation order

Each stage ends green: full suite plus `run_audits.py` clean.

| # | Stage | Deliverable | Why here |
|---|---|---|---|
| **P3.0** | **Specification errata** | Resolve Q1, Q2, Q5a, Q10, Q11; record decisions; bump `rubric_version`; re-derive affected expectation files. **No code.** | Q1 changes every score in the corpus and Q11 currently demands a fabrication. Writing `scoring.py` before Q1 is settled means writing it twice. |
| **P3.1** | Data layer | `taxonomy_data.py`, `rubric_data.py`, `predicates.py`, `registry.py` + import-time invariants + **question lint**. | The registry is the contract everything else consumes. Its invariants catch point-total and id errors before any check exists. |
| **P3.2** | Provenance layer | `classify.py`, `facts.py`, `evidence.py`. Test classification against all 14 fixtures. | Classification selects the check set; evidence construction is the gate every finding passes through. Both are testable with zero checks written. |
| **P3.3** | **The missing audits** | `arithmetic_audit.py`, `language_audit.py`, `evidence_integrity.py`, `test_determinism.py`, `evals/harness.py`. | Mirrors `AGENTS.md` §6's own discipline: *"do not write checks before the fabrication audit exists."* Three of the six audits `AGENTS.md` §8 requires do not exist. Building checks against an incomplete gate repeats the mistake the repo was explicitly designed to avoid. |
| **P3.4** | D1 + D8 | `checks/ident.py`, `checks/struct.py`. Fixture set `complete/` (10). | Structural, `high` confidence, no recognition. Exercises the whole pipeline end to end on the easiest checks, and `complete/` gives the corpus its first PASS paths (AC-Q3). |
| **P3.5** | D3 | `checks/variant.py`. Fixture set `variants/` (6). | Structural and self-contained. Coverage scoring and variant-id naming are proven here before D2 depends on them. |
| **P3.6** | D2 | `checks/category_attrs.py`, `recognize.py`. Fixture set `ambiguous/` (4). | The largest block and the first that needs recognition. Everything it depends on is now proven. |
| **P3.7** | D4 + D5 | `checks/usecase.py`, `checks/trust.py`. | Recognition-heavy but low-stakes — earned-only, several `low` confidence, so a recall miss costs points and nothing else. |
| **P3.8** | D6 + D7 | `checks/conflict.py`, `checks/claim.py`. Fixture sets `conflict/` (8), `claims/` (8), `duplicates/` (4). | The only paths that subtract points, and the only ones that can emit `blocker`. Deliberately last among the check families, with the most fixture support behind them. |
| **P3.9** | Scoring | `scoring.py`, grade bands, blocker cap. Rubric §7's worked example reproduced to the digit. Arithmetic audit green over the whole corpus. | Every status now exists to score. AC-F6's independent recomputation is meaningful only against a complete ledger. |
| **P3.10** | Close-out | `AGENTS.md` §6, `engine/README.md`, `evals/README.md`, decision records. Tag `p3-complete`. | |

**Two ordering principles worth stating:** audits precede the checks they gate (P3.3 before P3.4), and the penalty families come last (P3.8), because they are the only ones where a false positive actively harms a merchant.

---

## 15. What P3 explicitly does not do

- No Shopify app, OAuth, API client, billing, web UI, database or deployment config.
- No network call of any kind, for any purpose.
- No LLM dependency and no model-generated number anywhere in the score path.
- No generated product copy — remediation is a question, never a value.
- No AI-ranking, visibility or citation claim in code, docs, reports or commit messages.
- No conflict auto-resolution and no source-priority heuristic.
- No `report.md` (P4), no `SKILL.md` (P5).
- No sixth category and no new attribute key.
