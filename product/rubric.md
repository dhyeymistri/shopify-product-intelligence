# Scoring Rubric — V0

- **Rubric version:** 0.4
- **Date:** 2026-08-25
- **Authority:** This document is normative for scoring. Where it conflicts with a check implementation, this document wins.

**Version history.** `0.4` implements the two D3 structural checks §4/D3 states and this file has always carried: `VARIANT.ATTRIBUTE_COVERAGE` counts a variant covered when every non-inheritable variant-scope attribute for the category is *present* on it, on the wording of §4/D3 (D-030), and is `NOT_APPLICABLE` where that attribute set is empty — for an assigned category or for `uncategorized` — on the precedent §4/D2 already sets (D-029); `VARIANT.MEDIA_LINKED`'s *"visual option existing"* condition is decided by a closed option-name vocabulary of exactly `color`, `colour`, `finish`, `shade`, and defers rather than removing itself where no such option is found (D-031). No check, point allocation, severity or confidence in this document changed. `0.3` applies the P3.2 review decisions: `IDENT.TITLE_DISTINGUISHING` counts only the five kinds §4/D1 names (D-024); variant coverage never falls below the ambiguity credit where every variant carries a value (D-025); a recognition-derived finding never reports `high` confidence (D-026, PRD §9.5); and `unnamed_eco_claim` is withdrawn until the D7 route `taxonomy.md` §5.1 names exists (D-027). No check, point allocation or severity in this document changed. `0.2` implements the first deterministic recognition predicates. No check, point allocation, severity or confidence in this document changed; what changed is that some supplied values now reach `PASS` or `PARTIAL` where they previously produced no finding at all. §1.1 makes `rubric_version` the version of the *scoring function*, not of this file, so a change that moves a score bumps it ([`decisions.md`](./decisions.md) D-023). Variant coverage over mixed verdicts is scored strictly — `satisfied / total` (D-021).

Companions: [`PRD.md`](./PRD.md) · [`taxonomy.md`](./taxonomy.md) · [`decisions.md`](./decisions.md)

---

## 1. What the score means

> **The score answers one question: how much of the information a buyer or an automated agent needs to evaluate this product is present, unambiguous, internally consistent, and correctly structured in the supplied data?**

It is a measurement of **data**, not of the product, the merchant, or their prospects in any channel. It is not a prediction, a ranking, or a quality judgment about the goods.

### 1.1 Non-negotiable properties

| Property | Rule |
| --- | --- |
| **Explainable** | Every point traces to a named check with a fixed maximum. The report contains the full arithmetic. |
| **Deterministic** | Same input + same rubric version → identical score. Enforced by the determinism audit (PRD §12.3). |
| **Arithmetic-only** | No model produces a number that enters the score. The model classifies and recognizes; the arithmetic is mechanical. |
| **No black box** | There is no "AI score", no learned weighting, no undisclosed composite, no proprietary index. |
| **Absence-neutral** | Missing information forfeits its points. It never subtracts. |
| **Category-relative** | The applicable check set depends on the assigned category. |
| **Reproducible by hand** | A reviewer with the report and a calculator can rederive the total. If they cannot, the rubric is broken. |

### 1.2 The scoring formula

```
raw_earned   = Σ check.earned          over applicable checks
raw_max      = Σ check.max             over applicable checks
penalties    = Σ finding.points.penalty
normalized   = (raw_earned / raw_max) * 100        # renormalization for N/A checks
total        = clamp(normalized - penalties, 0, 100)
```

Penalties are applied **after** renormalization so that a conflict costs the same absolute number of points regardless of how many checks were N/A. A conflict is a defect in what is present; its cost must not shrink because other things were inapplicable.

**Note on the 100-point split.** The six earned dimensions (D1–D5, D8) contribute 82 points of `raw_max`, which is renormalized to a 0–100 scale. D6 (10) and D7 (8) are **penalty exposure**, not earned points: their stated maxima are the most that each can subtract from that scale. So a clean product with no conflicts and no unsupported claims can reach 100, and a product can lose at most 18 points to defects in what it does state. The dimension table below reads as "points at stake", which is true for both mechanisms.

---

## 2. Dimensions

| # | Dimension | Points | Mechanism | Answers |
| --- | --- | --- | --- | --- |
| D1 | Product identity clarity | 15 | Earned | Can you tell what this product actually is? |
| D2 | Category-relevant attribute completeness | 22 | Earned | Are the facts this *kind* of product needs present? |
| D3 | Variant clarity and consistency | 15 | Earned | Can you tell the variants apart and buy the right one? |
| D4 | Use-case information | 12 | Earned | Do you know who it's for and when to use it? |
| D5 | Decision and trust information | 12 | Earned | Is there enough to commit to a purchase? |
| D6 | Factual consistency | 10 | Penalty | Does the data contradict itself? |
| D7 | Claim substantiation | 8 | Penalty | Do the claims carry the support they imply? |
| D8 | Coverage and machine readability | 6 | Earned | Is it structured so a machine can use it? |
| | **Total** | **100** | | |

### 2.1 Why this allocation

- **D2 is the largest single earned block (22)** because category relevance is the product's core differentiator. Ceding that to generic identity checks would make us an SEO tool.
- **D1 (15) is nearly as large** because identity failure invalidates everything downstream: if you can't tell what the product is, no attribute helps.
- **D3 (15) is large relative to intuition** because variant data is where catalogs quietly break, it is nearly invisible in manual review, and it is where automated auditing has the biggest advantage over a human spot-check.
- **D6 and D7 are penalty-only (18 combined)** because they measure *defects in what is present*. A product with no claims deserves full D7; it has done nothing wrong. Making them earned would reward verbosity.
- **D8 is small (6)** deliberately. Structure matters, but a beautifully structured product with no facts is still useless, and a large D8 would let formatting compensate for emptiness.

The allocation is a product judgment, recorded so it can be argued with. It is reviewed against eval outcomes each rubric version ([`decisions.md`](./decisions.md) D-010).

---

## 3. Check definition

Every check is a fixed record. Nothing about a check is decided at runtime except its status and evidence.

```jsonc
{
  "check_id":   "APPAREL.MATERIAL_COMPOSITION",  // stable, namespaced, permanent
  "dimension":  "D2_category_attributes",
  "applies_to": { "categories": ["apparel"], "condition": null },
  "scope":      "product",                        // product | variant | option | catalog
  "max_points": 3.30,
  "severity":   { "FAIL": "critical", "UNKNOWN": "major", "PARTIAL": "major" },
  "confidence": "medium",                         // fixed per check, per PRD §7.5
  "partial_credit": 0.5,
  "checked_paths": ["metafields.*", "attributes[material_composition]",
                    "narrative.description_text", "variants[*].attributes"],
  "question": "What is the fabric composition, by percentage?"
}
```

`check_id` naming: `<FAMILY>.<CHECK>` where FAMILY is `IDENT`, `APPAREL`, `BEAUTY`, `ELEC`, `HOME`, `SPORTS`, `VARIANT`, `USECASE`, `TRUST`, `CONFLICT`, `CLAIM`, or `STRUCT`. IDs are permanent; a retired check keeps its ID reserved.

### 3.1 Status semantics

| Status | Meaning | Earned | Penalty |
| --- | --- | --- | --- |
| `PASS` | Requirement satisfied by evidenced data. | `max_points` | 0 |
| `PARTIAL` | Present but ambiguous or incompletely covered (PRD §9.3, §9.7). | `max × partial_credit`, or `max × (covered/total)` for coverage | 0 |
| `UNKNOWN` | Not found in any `checked_paths`. | 0 | **0** |
| `FAIL` | Present and defective — conflict, unsupported claim, undifferentiated variants, broken structure. | 0 | per §7 (D6/D7 only) |
| `NOT_APPLICABLE` | Structural trigger absent (§5.4 of taxonomy). | removed from numerator **and** denominator | 0 |

**The `UNKNOWN` vs `FAIL` boundary is the most important line in this rubric.** `FAIL` requires something present to be wrong. If nothing is present, it is `UNKNOWN`. A check that emits `FAIL` on absence is a spec violation.

---

## 4. Dimension specifications

### D1 — Product identity clarity (15 pts, earned)

*Can a reader determine what this product is, from whom, and in what form?*

| check_id | Max | Scope | PASS when | Conf. |
| --- | --- | --- | --- | --- |
| `IDENT.TITLE_SPECIFIC` | 4.0 | product | Title names the product type, not only a brand/style name. "Northgate Cotton Crew Tee" passes; "The Sunday" does not. | medium |
| `IDENT.TITLE_DISTINGUISHING` | 2.0 | product | Title carries at least one distinguishing attribute (material, size, model, capacity, count). | medium |
| `IDENT.BRAND_PRESENT` | 2.0 | product | `Vendor`/brand is populated and is not a placeholder. | high |
| `IDENT.PRODUCT_TYPE_OR_CATEGORY` | 2.5 | product | A Shopify product category or product type is set. | high |
| `IDENT.IDENTIFIER_PRESENT` | 2.0 | variant | Each variant has a SKU, barcode/GTIN, or MPN. Coverage-scored. | high |
| `IDENT.DESCRIPTION_SUBSTANCE` | 2.5 | product | Description contains ≥3 distinct informational statements about the product (attribute, use, or construction). Counts statements, never words. | medium |

Notes: `IDENT.DESCRIPTION_SUBSTANCE` scores information, not length, on purpose — a 400-word description of brand mood is worth less than three factual sentences. No check in D1 measures character counts or keyword presence; that is SEO theater, not intelligence.

### D2 — Category-relevant attribute completeness (22 pts, earned)

One check per attribute in the assigned category's set ([`taxonomy.md`](./taxonomy.md) §5). Points derive from tier ([`taxonomy.md`](./taxonomy.md) §6):

```
tier_A_pool = 13.2   per-attribute = 13.2 / count(A)
tier_B_pool =  6.6   per-attribute =  6.6 / count(B)
tier_C_pool =  2.2   per-attribute =  2.2 / count(C)
```

| Situation | Status | Earned |
| --- | --- | --- |
| Attribute present, unambiguous, correctly scoped | `PASS` | full |
| Present but ambiguous (per attribute's PARTIAL column) | `PARTIAL` | 50% |
| Variant-scope attribute covering some variants | `PARTIAL` | `max × covered/total` |
| Not found in any checked path | `UNKNOWN` | 0, no penalty |
| Conditional attribute, trigger absent | `NOT_APPLICABLE` | removed from denominator |
| Two supplied values conflict | `FAIL` | 0 earned **and** a D6 penalty |

`uncategorized` products: D2 is entirely N/A and removed; the report states that category-specific auditing did not run, names the reason, and recommends setting a product category.

### D3 — Variant clarity and consistency (15 pts, earned)

| check_id | Max | Scope | PASS when | Conf. |
| --- | --- | --- | --- | --- |
| `VARIANT.DIFFERENTIATED` | 5.0 | product | Every variant is distinguishable by at least one option value. `FAIL` (severity `critical`) if any two are identical/empty. | high |
| `VARIANT.OPTION_NAMES_MEANINGFUL` | 2.0 | option | Option names are populated and semantic — not `Title`, `Option 1`, `Default`, blank. | high |
| `VARIANT.OPTION_VALUES_CONSISTENT` | 2.0 | option | Values within an option are unique, non-empty, and use one convention (not `S`/`Small`/`sm` mixed). | high |
| `VARIANT.ATTRIBUTE_COVERAGE` | 3.0 | variant | Every non-inheritable variant-scope attribute for the category is present on every variant. Coverage-scored; evidence names uncovered variant IDs. | high |
| `VARIANT.IDENTIFIER_UNIQUE` | 1.5 | variant | SKUs/barcodes present and unique. Duplicates → `FAIL`, `critical`. | high |
| `VARIANT.MEDIA_LINKED` | 1.5 | variant | Where variants differ visually (color/finish/shade), each has linked media. Conditional on a visual option existing. | medium |

Applicability: for single-variant products, `VARIANT.DIFFERENTIATED`, `OPTION_VALUES_CONSISTENT`, `ATTRIBUTE_COVERAGE`, and `MEDIA_LINKED` are `NOT_APPLICABLE` and removed; `OPTION_NAMES_MEANINGFUL` and `IDENTIFIER_UNIQUE` still apply. Renormalization follows §6.3.

### D4 — Use-case information (12 pts, earned)

*Does the data say who it's for and when it's used — the questions a comparison must answer and a spec sheet never does?*

| check_id | Max | Scope | PASS when | Conf. |
| --- | --- | --- | --- | --- |
| `USECASE.INTENDED_USER` | 3.0 | product | The intended user or user context is stated (skill level, skin type, room, activity, device owner). | medium |
| `USECASE.PRIMARY_USE` | 3.5 | product | At least one concrete use situation is described beyond restating the product type. | medium |
| `USECASE.DIFFERENTIATION` | 2.5 | product | The data states what distinguishes this product from adjacent options, in factual terms rather than superlatives. Superlative-only differentiation → `PARTIAL` and routes the phrase to D7. | low |
| `USECASE.NOT_FOR` | 1.5 | product | A stated limitation, exclusion, or unsuitability ("not for machine washing", "not compatible with X", "not for children under 3"). | medium |
| `USECASE.COMPLEMENTARY_CONTEXT` | 1.5 | product | What it works with, pairs with, or is needed alongside. | low |

`USECASE.NOT_FOR` is worth flagging as a design choice: stated limitations are one of the strongest signals that a product record is written for a real buyer rather than for a keyword. Absence is `UNKNOWN` and costs 1.5 points — it is never read as "the product has no limitations".

### D5 — Decision and trust information (12 pts, earned)

| check_id | Max | Scope | PASS when | Conf. |
| --- | --- | --- | --- | --- |
| `TRUST.WARRANTY_OR_GUARANTEE` | 3.0 | product | Warranty/guarantee with a duration or defined scope. | high |
| `TRUST.RETURNS_REFERENCE` | 2.0 | product | Returns/exchange terms stated or referenced. | high |
| `TRUST.SHIPPING_OR_LEADTIME` | 2.0 | product | Dispatch time, lead time, or made-to-order status. | medium |
| `TRUST.SUPPORT_OR_CONTACT` | 1.5 | product | A support path, documentation link, or contact route. | high |
| `TRUST.CERTIFICATION_REFERENCED` | 2.0 | product | Where the category treats certification as decision-relevant, a named body/standard/identifier is referenced. Reports *referenced*, never *verified* (PRD §9.6). | medium |
| `TRUST.PROVENANCE` | 1.5 | product | Country of origin, manufacturing, or sourcing information. | high |

### D6 — Factual consistency (10 pts, penalty-based)

Starts at **10.0**. Each conflict subtracts. Floor is 0; D6 never goes negative and never subtracts from other dimensions.

| check_id | Penalty | Detects | Conf. |
| --- | --- | --- | --- |
| `CONFLICT.NUMERIC` | 3.0 | Same measurable attribute with incompatible numeric values across locations (after unit normalization and ±2% tolerance). | high |
| `CONFLICT.CATEGORICAL` | 3.0 | Same categorical attribute with incompatible values ("machine washable" vs "dry clean only"). | medium |
| `CONFLICT.CLAIM_VS_ATTRIBUTE` | 5.0 | A claim contradicted by a supplied attribute ("fragrance-free" + fragrance ingredient; "waterproof" + "not water resistant"). | high |
| `CONFLICT.VARIANT_VS_PRODUCT` | 2.0 | A variant value outside a stated product-level range or contradicting a product-level assertion. | high |
| `CONFLICT.TITLE_VS_BODY` | 2.0 | Title asserts an attribute the body contradicts. | medium |
| `CONFLICT.UNIT_INCONSISTENCY` | 0.0 | Same value in different units without conversion error. **`info` only — no penalty.** | high |

Rules:
1. Both conflicting locations are cited as separate evidence items. **No winner is chosen** (PRD §9.2).
2. Severity is `blocker` when the attribute is safety-, allergen-, compatibility-, or compliance-relevant for the category; otherwise `critical`. A `blocker` caps the grade label (PRD §7.4).
3. A conflict also zeroes the affected D2 attribute. **This double effect is intentional**: contradictory data is worse than absent data, because absent data makes a buyer ask while contradictory data makes them decide wrongly.
4. Conflicts require both values to be extractable. A suspected conflict that cannot be evidenced on both sides is not emitted at all.

### D7 — Claim substantiation (8 pts, penalty-based)

Starts at **8.0**. A product making no claims keeps all 8 — plainness is never penalized.

| check_id | Penalty | Claim class | Conf. |
| --- | --- | --- | --- |
| `CLAIM.UNSUPPORTED_SUPERLATIVE` | 1.5 | "best", "#1", "world's leading" with no named, dated basis | medium |
| `CLAIM.UNSUPPORTED_COMPARATIVE` | 2.0 | "40% stronger", "twice as long" with no comparison target and basis | medium |
| `CLAIM.UNSUPPORTED_CERTIFICATION` | 3.0 | "clinically proven", "dermatologist tested", "certified organic", "FDA approved" with no named body, standard, or identifier | medium |
| `CLAIM.UNSUPPORTED_EFFICACY` | 2.5 | Outcome claims with no referenced study, test, or qualifier | medium |
| `CLAIM.VAGUE_QUALIFIER` | 0.5 | "up to", "helps", "may" used to carry a performance figure without stated conditions | low |

Rules:
1. Penalties cap at 8.0 total; a claim-heavy product bottoms out at zero D7, never negative.
2. A claim with a referenced basis is `PASS`. The report states **"a basis is referenced"** — never that the claim is true, and never that the basis is valid. `external_reference` evidence is recorded as *mentioned*, never fetched (PRD §8.1).
3. Repeated instances of the same claim are one finding with multiple evidence items and **one** penalty.
4. The tool never asserts a legal or regulatory violation ([`decisions.md`](./decisions.md) D-007).
5. `CLAIM.VAGUE_QUALIFIER` is `low` confidence, so per PRD §7.5 rule 2 it may carry no penalty — its 0.5 is therefore recorded as `info` in V0 and activates only if the check is promoted to `medium` confidence in a later rubric version. **This is deliberate and is not an inconsistency**: it keeps the rule "low confidence never punishes" absolute.

### D8 — Coverage and machine readability (6 pts, earned)

| check_id | Max | PASS when | Conf. |
| --- | --- | --- | --- |
| `STRUCT.ATTRIBUTES_IN_FIELDS` | 2.5 | Category attributes live in structured fields (metafields, options) rather than only in prose. Scored as `structured_attrs / total_found_attrs`. | high |
| `STRUCT.DESCRIPTION_PARSEABLE` | 1.0 | Description uses lists, tables, or headings rather than one undifferentiated block. | high |
| `STRUCT.MEDIA_ALT_TEXT` | 1.0 | Media have alt text. Coverage-scored. | high |
| `STRUCT.SEO_FIELDS_POPULATED` | 0.5 | SEO title and description present. Presence only — never keyword judgment. | high |
| `STRUCT.NO_PLACEHOLDER_VALUES` | 1.0 | No `N/A`, `TBD`, `xxx`, `.`, `-` occupying a value field. Each placeholder found is quoted. | high |

`STRUCT.ATTRIBUTES_IN_FIELDS` is the one that matters. Shopify's own merchant guidance directs merchants toward complete, well-structured product data and toward mapping custom fields via metafields and metaobjects¹ — a fact stated in prose is real information, but it is not addressable, and this check measures exactly that gap without promising any downstream outcome.

---

## 5. Severity and confidence assignment

Severity and confidence are **properties of the check definition**, never chosen at runtime. This is what makes reports comparable across runs and stops severity inflation.

### 5.1 Severity assignment rules

| Rule | Applies |
| --- | --- |
| `blocker` | Only from D6 conflicts on safety/allergen/compatibility/compliance attributes, or a `CONFLICT.CLAIM_VS_ATTRIBUTE` on a regulated claim. No other check may emit `blocker`. |
| `critical` | Tier A attribute `UNKNOWN`; `VARIANT.DIFFERENTIATED` fail; duplicate identifiers; non-safety conflicts. |
| `major` | Tier B attribute `UNKNOWN`; any `PARTIAL`; unsupported claims. |
| `minor` | Tier C attribute `UNKNOWN`; D8 gaps; low-confidence observations. |
| `info` | Zero-point observations: merges, unit inconsistency, classification fallbacks. |

### 5.2 Confidence assignment rules

| Confidence | Check types |
| --- | --- |
| `high` | Structural presence/absence, exact match, arithmetic, uniqueness. |
| `medium` | Bounded language recognition over a quoted span. |
| `low` | Interpretive judgment a reviewer could reasonably dispute. |

**Binding constraint:** a `low`-confidence finding may carry at most `minor` severity and **never** carries a penalty (PRD §7.5). Any rubric change that would violate this must instead raise the check's confidence — and justify it — rather than lower the guardrail.

---

## 6. Score computation

### 6.1 Algorithm

1. Build the applicable check set from the assigned category.
2. Run each check → status + evidence + earned points.
3. Drop `NOT_APPLICABLE` checks from both numerator and denominator.
4. `raw_earned = Σ earned`; `raw_max = Σ max`.
5. `normalized = (raw_earned / raw_max) × 100`.
6. `penalties = Σ penalty` over D6 and D7 findings (D6 capped at 10.0, D7 at 8.0).
7. `total = clamp(normalized − penalties, 0, 100)`.
8. Assign grade band; apply the blocker cap to the **label only**, never the number.

### 6.2 Rounding

- Internal arithmetic uses full precision.
- Per-check earned/max: 2 decimal places in the report.
- Dimension subtotals and `total`: 1 decimal place.
- Rounding happens only at render. Rounded values must sum to the rounded total; where they cannot, the report shows the unrounded total and marks the row that carries the residual. Never silently adjust a number to make a column add up.

### 6.3 Renormalization example

A single-variant electronics product. Four D3 checks are N/A, removing 11.5 points from the denominator.

```
raw_max     = 82.0 − 11.5 = 70.5
raw_earned  = 61.0
normalized  = 61.0 / 70.5 × 100 = 86.5
penalties   = 2.0   (one CLAIM.UNSUPPORTED_COMPARATIVE)
total       = 84.5  → grade: strong
```

The report prints `max_applicable: 70.5`, the renormalization factor `1.4184`, and the list of N/A checks with reasons — so the merchant can see exactly what was and was not assessed.

### 6.4 Grade bands

| Score | Grade | Meaning |
| --- | --- | --- |
| 90–100 | `agent_ready` | Complete, consistent, structured, category-appropriate. |
| 75–89 | `strong` | Minor gaps; comparison possible on all key axes. |
| 60–74 | `adequate` | Transactable; comparison degraded on some axes. |
| 40–59 | `weak` | Major decision facts absent or inconsistent. |
| 0–39 | `insufficient` | Cannot support an informed purchase decision. |

Any `blocker` finding sets the label to `insufficient` and populates `grade_capped_by`. The numeric score is reported unmodified.

---

## 7. Worked example

**Product:** "Northgate Cotton Crew Tee", apparel, 6 variants (Size S/M/L × Color Black/White). Description states 100% combed ring-spun cotton and relaxed fit. No size chart, no care instructions. Description says "the softest tee you'll ever own". A metafield says `Machine wash cold`; the description says `Dry clean only`.

**D1 — 12.5 / 15.0**

| Check | Status | Earned |
| --- | --- | --- |
| `IDENT.TITLE_SPECIFIC` | PASS | 4.00 |
| `IDENT.TITLE_DISTINGUISHING` | PASS ("Cotton") | 2.00 |
| `IDENT.BRAND_PRESENT` | PASS | 2.00 |
| `IDENT.PRODUCT_TYPE_OR_CATEGORY` | PASS | 2.50 |
| `IDENT.IDENTIFIER_PRESENT` | PASS (6/6 SKUs) | 2.00 |
| `IDENT.DESCRIPTION_SUBSTANCE` | UNKNOWN (2 statements) | 0.00 |

**D2 — 8.25 / 22.0** (apparel: A=3.30 ea, B=1.65 ea, C=0.733 ea)

| Attribute | Tier | Status | Earned |
| --- | --- | --- | --- |
| `size_system` | A | PARTIAL — bare labels, no system | 1.65 |
| `material_composition` | A | PASS | 3.30 |
| `fit_and_cut` | A | PARTIAL — fit stated, cut not | 1.65 |
| `garment_measurements` | A | UNKNOWN | 0.00 |
| `care_instructions` | B | **FAIL — conflict** | 0.00 |
| `color_finish` | B | PASS (6/6) | 1.65 |
| `closure_and_construction` | B | UNKNOWN | 0.00 |
| `intended_use_context` | B | UNKNOWN | 0.00 |
| `country_of_origin` | C | UNKNOWN | 0.00 |
| `sustainability_credentials` | C | UNKNOWN | 0.00 |
| `model_reference_measurements` | C | UNKNOWN | 0.00 |

**D3 — 11.0 / 15.0** · **D4 — 3.5 / 12.0** · **D5 — 2.0 / 12.0** · **D8 — 3.5 / 6.0**

**D6 — penalty 3.0** — `CONFLICT.CATEGORICAL`, severity `critical` (care instructions are not safety-relevant for a cotton tee), citing `row12.product.metafields.custom.care` ("Machine wash cold") and `row12.Description[188:203]` ("Dry clean only"). No winner asserted.

**D7 — penalty 1.5** — `CLAIM.UNSUPPORTED_SUPERLATIVE` on "the softest tee you'll ever own", quoted verbatim.

**Total**

```
raw_earned  = 12.5 + 8.25 + 11.0 + 3.5 + 2.0 + 3.5 = 40.75
raw_max     = 15 + 22 + 15 + 12 + 12 + 6           = 82.0   (D6/D7 are penalty-only)
normalized  = 40.75 / 82.0 × 100                    = 49.7
penalties   = 3.0 + 1.5                             = 4.5
total       = 45.2   → grade: weak
```

**Top questions generated** (ranked by points recoverable):
1. Which is correct — "Machine wash cold" or "Dry clean only"? *(recovers 1.65 + 3.0 penalty = 4.65)*
2. What are the chest, length, and shoulder measurements for each size? *(3.30)*
3. Which size system do S/M/L follow, and what body measurements do they correspond to? *(1.65)*

Note what the report does **not** do: it does not decide that machine-washable is correct because the fabric is cotton. That would be world knowledge overriding a merchant-supplied fact — prohibited by PRD §9.4.

---

## 8. Handling-rule → check mapping

| PRD rule | Implemented by |
| --- | --- |
| §9.1 Missing information | `UNKNOWN` status; zero earned, zero penalty; `absence` evidence; `unknowns[]` + question |
| §9.2 Contradictory information | D6 `CONFLICT.*`; both locations cited; D2 attribute zeroed; blocker rule §4/D6 |
| §9.3 Ambiguous information | `PARTIAL` status; 50% credit; disambiguating question; severity capped at `major` |
| §9.4 Merchant-provided facts | `origin` field on every value; placeholders → absent with quote; world knowledge never contradicts a stated fact |
| §9.5 AI inference | Permitted only in classification, span recognition, near-duplicate proposal; `medium`/`low` confidence; *(interpreted)* tag |
| §9.6 Unsupported claims | D7 `CLAIM.*`; supported → PASS as *referenced*, never *verified*; no claims → full D7 |
| §9.7 Variant-specific information | D3 check family; scope + inheritance from taxonomy §4; coverage scoring names uncovered variant IDs |
| §9.8 Duplicates / near-duplicates | Canonical-key scoring (scored once); exact dup → `info`; near-dup → `info`, `low` confidence; different values → routed to D6, never merged |

---

## 9. Rubric governance

1. **Point totals must sum to 100.** A change that breaks this is rejected at review.
2. **Any change that can move a fixture score bumps `rubric_version`** and requires updating every affected expectation file in the same commit (PRD §12.5). A point-allocation change is the obvious case, but it is not the only one: §1.1 versions the *scoring function*, so implementing a recognition predicate or editing `engine/lexicon.py` bumps it too ([`decisions.md`](./decisions.md) D-023, D-022). A behaviour-neutral refactor does not.
3. **New checks require:** a stable `check_id`, `checked_paths`, a fixed severity/confidence, an eval fixture that exercises both its pass and its fail path, and a merchant-answerable question.
4. **No check may be added that cannot produce evidence.** No evidence, no check.
5. **No check may score prose style, keyword density, or character counts.** We measure information, not writing.
6. **The absence-neutral rule is not amendable by a rubric version bump.** Changing it requires a decision record superseding [`decisions.md`](./decisions.md) D-003.

---

## 10. Sources

1. [Shopify Catalog and product discovery for agentic storefronts — Shopify Help Center](https://help.shopify.com/en/manual/online-sales-channels/agentic-storefronts/products); [Category metafields — Shopify Help Center](https://help.shopify.com/en/manual/custom-data/metafields/category-metafields)
