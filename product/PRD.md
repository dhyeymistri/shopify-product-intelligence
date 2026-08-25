# Shopify Product Intelligence — Product Requirements Document

- **Spec version:** 0.1.1 (draft, authoritative for V0)
- **Date:** 2026-08-24 (amended 2026-08-25)
- **Status:** Authoritative. This document is the product contract; implementation conforms to it, not the reverse. Phases P1 (eval corpus + fabrication audit) and P2 (the normalizer) are authorized and complete. Later phases remain gated and require explicit approval before any code is written for them — see [`AGENTS.md`](../AGENTS.md) §6.
- **Scope of this document:** V0 only. Post-V0 direction is described only where it constrains V0 decisions.

Amendments since 0.1, all of them documenting behavior P2 already implements rather than changing it:
- §6.1 — the NPR carries `tags[]`. It was absent from the 0.1 skeleton by oversight; [`taxonomy.md`](./taxonomy.md) §2 makes tags the fourth-order category signal, so the record has to hold them.
- §5.1, §6.2 rule 6 — divergent product-level values inside one CSV handle group are preserved with provenance rather than resolved.
- §5.4, §9.6 — claim extraction from prose is a check-phase concern, not a normalization concern.

Companion documents:
- [`rubric.md`](./rubric.md) — scoring model, checks, point allocation, severity/confidence tables
- [`taxonomy.md`](./taxonomy.md) — the five V0 categories and their attribute sets
- [`decisions.md`](./decisions.md) — decision records with rationale and alternatives rejected

---

## 1. Product summary

Shopify Product Intelligence audits ecommerce product data and reports, with evidence, whether that data is **complete, consistent, structured, and useful enough** for a human or an automated system to understand, compare, and make a purchase decision about the product.

V0 is a **local AI skill** — a set of instructions and schemas that an agent (Claude Code) follows against a locally supplied catalog file. It is not a Shopify app, not a service, and not connected to any store.

### 1.1 The core principle

> **NEVER INVENT PRODUCT FACTS.**

The tool reads product data. It does not know the product. If the supplied data does not state a fact, the tool reports **UNKNOWN** — never "no", never "false", never a plausible guess.

This principle outranks every other requirement in this document. A report that is 100% honest and 40% complete is a success. A report that is 100% complete and contains one fabricated attribute value is a **failure of the product**, not a bug.

Three corollaries, binding on all V0 behavior:

1. **Absence is not negation.** A beauty product with no ingredient list is `ingredients: UNKNOWN`. It is not "missing ingredients" in the sense of "contains none", and it is never "fragrance-free".
2. **The tool asks; it does not answer.** Remediation output is a **question to the merchant** ("What is the fabric composition, by percentage?"), never generated marketing copy that supplies the missing fact.
3. **Every finding carries evidence.** Including findings about things that are absent — see §8.

### 1.2 What we explicitly do not claim

We do **not** claim, imply, or market that this tool guarantees, improves, or predicts ranking, citation, visibility, or recommendation in ChatGPT, Gemini, Google AI Overviews, Perplexity, Shopify Catalog, or any other AI or search system. Those systems are third-party, undisclosed, and changing.

What we do claim: we evaluate whether the merchant's product information is **sufficiently complete, consistent, structured, and useful** for AI-powered product discovery and comparison — a property of the merchant's own data, which we can inspect and prove.

Any copy, report header, or future UI that violates this is a spec violation. See [`decisions.md`](./decisions.md) D-002.

---

## 2. Target customer

### 2.1 Primary customer (buyer and user in V0)

**Catalog-responsible operators at Shopify merchants doing $1M–$50M GMV, with 100–5,000 SKUs.**

Typical titles: Ecommerce Manager, Head of Ecommerce, Merchandising Manager, DTC Founder (at the smaller end), Product Content Manager.

Characteristics that matter for V0:
- Owns product page content and is measured on conversion, returns, and traffic.
- Can export a product CSV from Shopify admin without engineering help.
- Cannot personally audit 800 products by hand, and does not trust a vendor that "AI-enhances" descriptions without showing its work.
- Has been burned by content tools that hallucinated specs, and by "SEO scores" that were a black box.

### 2.2 Secondary customer

**Agencies and freelance catalog/PIM consultants** managing catalogs for multiple Shopify merchants. They need a defensible, evidence-backed artifact to hand a client as the justification for a paid content project. Their acceptance bar for evidence is higher than the merchant's, which makes them the useful design constraint.

### 2.3 Explicit non-customers in V0

- Marketplaces and aggregators auditing third-party catalogs at millions-of-SKU scale (throughput requirements we are not designing for).
- Enterprise PIM buyers requiring SSO, audit logs, workflow, and role permissions.
- Consumers or shoppers.

---

## 3. Customer problem

### 3.1 The problem statement

Merchants cannot tell which of their products are **under-described** until the cost shows up somewhere else — as a return, a pre-purchase support ticket, a lost comparison, or an absent recommendation. Product data decays invisibly: a supplier changes a fabric, a variant is added without attributes, a description contradicts a spec table, a claim ("dermatologist tested") outlives the study that supported it.

The merchant's actual question is narrow and practical:

> *"Which of my products are missing information that a buyer — or a machine acting for a buyer — needs in order to choose them, and what exactly is missing?"*

Today they answer it by spot-checking, by intuition, or not at all.

### 3.2 Why existing options fail

| Option | Why it fails for this customer |
| --- | --- |
| Manual audit / spreadsheet | Does not scale past ~100 SKUs; inconsistent between reviewers; no repeatability. |
| SEO audit tools | Score title length, keywords, meta tags. They do not know that a shoe needs a width and a serum needs an INCI list. Category-blind. |
| Generic "AI product description writers" | Invent facts. They will confidently write "made from 100% organic cotton" from a title. This is the exact failure mode our customer fears, and it creates real legal exposure for regulated categories. |
| PIM completeness reports | Check whether a field is non-empty. They cannot detect that the description contradicts the spec field, that a claim is unsupported, or that one variant is described and four are not. |
| Shopify's own admin | Surfaces category metafield suggestions per product, but there is no cross-catalog audit, no consistency checking, and no evidence trail. |

The unoccupied position: **category-aware, evidence-bound, non-inventing catalog audit**.

### 3.3 Why this is worth solving now

Shopify itself has moved product data into the distribution path for AI channels: Shopify Catalog syndicates product data to AI platforms, and Shopify's merchant documentation directs merchants to maintain "complete and well-structured product information in Shopify Catalog" and to map custom fields via metafields and metaobjects.¹ Structured, category-appropriate product attributes have become the substrate for a channel merchants do not control.

That does not mean we can promise placement in that channel (§1.2). It means the merchant's data quality is now load-bearing in more places than their own PDP, and they have no instrument for measuring it.

---

## 4. Exact V0 use case

**One use case. Everything outside it is out of scope for V0.**

### 4.1 The use case

> An operator has a local file containing product data for between 1 and 200 products. They run the Shopify Product Intelligence skill against that file. They receive (a) a machine-readable JSON report and (b) a human-readable Markdown report containing, per product, a 100-point explainable score, a ranked list of evidence-backed findings, and a list of specific questions to answer to raise the score.

### 4.2 Walkthrough

1. Operator exports products from Shopify admin as CSV (or has a JSON payload from the Admin GraphQL API, or hand-authors the canonical JSON).
2. Operator places the file in `evals/fixtures/` or any local path.
3. Operator invokes the skill, optionally naming a category override.
4. Skill **normalizes** the input into the Normalized Product Record (§6). Normalization is mechanical and lossless-by-reference: every normalized value retains a pointer to its source location.
5. Skill **classifies** each product into one of five V0 categories (§7 of [`taxonomy.md`](./taxonomy.md)), or `uncategorized`.
6. Skill **runs the check set** for that category (see [`rubric.md`](./rubric.md)), producing a findings ledger.
7. Skill **computes the score deterministically** from the ledger — arithmetic only, no model-generated numbers.
8. Skill **writes** `reports/<run-id>/report.json` and `reports/<run-id>/report.md`.
9. Operator reads the Markdown, answers the questions, updates products in Shopify by hand, re-runs, and sees the score move.

### 4.3 Boundaries of the use case

The operator is a human who edits Shopify manually. The skill's output is an **input to their work**, never a write to their store.

**In scope for V0:** read local file, normalize, classify, audit, score, explain, ask.

**Out of scope for V0 (see §14):** anything that touches Shopify, the network, a database, a browser, or a merchant's live catalog.

---

## 5. Input formats

V0 accepts three input formats. All three are converted to the same Normalized Product Record before any check runs. **No check ever reads a raw input format directly** — this is what keeps the check set stable while input support grows.

### 5.1 Format A — Shopify product CSV export (primary)

Shopify's product CSV export uses one row per variant/image, with product-level fields populated only on the first row of a handle group. Documented columns include `Title`, `URL handle`, `Description`, `Vendor`, `Product category`, `Type`, `Tags`, `Status`, `Option1 name` / `Option1 value` (through Option3), `SKU`, `Barcode`, `Price`, `Compare-at price`, `Weight value (grams)`, `Product image URL`, `Image alt text`, `Variant image URL`, `SEO title`, `SEO description`, and metafield columns.² Only `Title` is required to create a product; `URL handle` and `Title` are required to update one.²

Metafield columns appear in exports with the header format `<name> (product.metafields.<namespace>.<key>)`.² The normalizer must parse that header form to recover `namespace` and `key`.

Normalizer obligations for Format A:
- Group rows by `URL handle`; a handle group is one product.
- Carry product-level fields down from the first row of the group; do **not** treat an empty product-level cell on a continuation row as an empty value.
- Rows that contribute only an image are media rows, not variants.
- Preserve the source row number and column name for every extracted value (evidence requirement, §8).
- Split the `Tags` cell into one `tags[]` record per tag, each with its own locator (§6.1).
- Where continuation rows disagree, keep every occurrence. See "Divergent product-level values" below.

**Divergent product-level values.** Carrying down from the first row is a *reading* rule: it says where the product-level value is written, not that the other rows are wrong. When a continuation row in the same handle group carries a **different non-empty value** for a product-level column, the normalizer:

1. takes the first row's value as the canonical one, exactly as the rule above requires;
2. preserves **every** occurrence — the first row's included — in `raw_extras` under the column name, each with its own locator;
3. asserts nothing about which is correct.

The normalizer has no winner-selection mechanism and must not acquire one (§6.2 rule 6, [`decisions.md`](./decisions.md) D-012). Preserved occurrences are ordinary supplied values: a later check may cite two of them as the two sides of a `CONFLICT.*` finding under §9.2, with both locators as separate evidence items. That routing is a check's decision, taken in the check phase, never at normalization time.

### 5.2 Format B — Shopify Admin GraphQL product JSON

A JSON array (or JSONL) of `Product` objects as returned by the Admin GraphQL API. Fields the normalizer consumes, using Shopify's documented names: `title`, `description` / `descriptionHtml`, `vendor`, `productType`, `category` (a `TaxonomyCategory`), `tags`, `handle`, `options`, `variants`, `media`, `seo`, `status`, and `metafields`.³

Notes recorded as platform facts, not as product facts:
- Product option count and variant count have platform ceilings queryable via `Shop.resourceLimits.maxProductOptions` and `Shop.resourceLimits.maxProductVariants`; Shopify's changelog states the variant limit is 2,048 for all merchants.⁴ V0 does not enforce these limits — it has no store context — but the normalizer must not assume a fixed number of options.
- `category` refers to Shopify's Standard Product Taxonomy, an open-source (MIT), calendar-versioned taxonomy of 10,000+ categories and ~2,000 attributes, distributed as JSON and TXT.⁵ Category-linked attributes surface in the admin as **category metafields**, which Shopify's merchant docs also call *product attributes*, and which can be linked to variant options and option values.⁶

### 5.3 Format C — Canonical Product Intelligence Payload (PIP JSON)

Our own input schema: an array of objects already shaped like the Normalized Product Record (§6). This exists for three reasons: to let non-Shopify catalogs be audited without writing a new normalizer, to make eval fixtures readable and diffable, and to keep the normalizer honest by giving us a format where normalization is the identity function.

Locator syntax for this format is defined in §8.2.1.

#### 5.3.1 The fixture envelope

A PIP document may carry an **envelope**: metadata about the file, wrapping the payload.

```jsonc
{
  "pip_version": "0.1",
  "fixture": {                    // the envelope -- metadata, NOT input
    "id": "adv-02-category-implies-attributes",
    "set": "adversarial",
    "intent": "...",              // what this fixture tests
    "provenance": "Synthetic...", // required by §12.1
    "notes": "..."                // may describe baits in plain language
  },
  "products": [ /* the PIP payload proper: NPR-shaped records */ ]
}
```

The envelope is formally supported, and formally **not product data**. Four rules, all normative:

1. **The envelope is not product evidence.** Only `products[]` is supplied input. `pip_version` and everything under `fixture` are metadata about the file.
2. **The provenance index excludes the envelope.** Traceability is computed from a product record, never from a fixture document.
3. **Bait descriptions are never product facts.** A fixture's `intent` and `notes` describe, in plain language, the values a fixture is designed to tempt the tool into inventing — "a bicycle helmet conventionally carries a safety standard and a shell material". Treating that text as supplied data would let our own description of a trap excuse falling into it.
4. **The envelope cannot satisfy an evidence requirement.** No locator may address it (§8.2.1 rule 5), so no finding can cite it, and a fact appearing only in the envelope is fabricated exactly as if it appeared nowhere at all.

Rule 3 is the one with teeth. It is why the provenance index takes a product record rather than a fixture document — an interface that makes the mistake hard to make, rather than a convention that asks people not to make it.

A non-fixture PIP file may omit the envelope entirely; `products[]` is the only required member.

### 5.4 Input handling rules

| Situation | Required behavior |
| --- | --- |
| Unrecognized format | Refuse the run with a clear error. Never guess a mapping. |
| Unknown extra columns/fields | Preserve verbatim in `raw_extras`, do not interpret, do not score. |
| Malformed row/record | Skip that record, emit a `run_error` entry naming the record and reason, continue the run. Never silently drop. |
| Empty vs whitespace vs `"N/A"` / `"-"` / `"TBD"` | All treated as **absent**, and the literal placeholder text is recorded in evidence so the report can say what was found. |
| HTML in descriptions | Text extracted for analysis; original HTML retained for evidence offsets. Structure (lists, tables, headings) is recorded as a signal for the machine-readability check. |
| More than 200 products | Warn and process the first 200; the batch ceiling is a V0 scope control, not a technical limit. |
| Claim-like language in prose | Not extracted at normalization time. The text is retained in `narrative` with its locator; recognizing a claim in it is a check-phase judgment (§9.6). |

---

## 6. Normalized Product Record (NPR)

The NPR is the single representation every check operates on. It is deliberately **thinner than Shopify's product model**: it carries only what is needed to reason about product information quality, plus the provenance needed to prove it.

### 6.1 Structure

```jsonc
{
  "npr_version": "0.1",
  "product_id": "handle:cotton-crew-tee",      // stable within the run
  "source": {
    "format": "shopify_csv",                    // shopify_csv | shopify_graphql | pip_json
    "file": "evals/fixtures/apparel_basic.csv",
    "locator": "rows 12-19"                     // for traceability of the whole record
  },

  "identity": {
    "title":        { "value": "Cotton Crew Tee", "src": "row12.Title" },
    "brand":        { "value": "Northgate", "src": "row12.Vendor" },
    "model_or_mpn": { "value": null, "src": null },
    "handle":       { "value": "cotton-crew-tee", "src": "row12.URL handle" },
    "product_type": { "value": "T-Shirts", "src": "row12.Type" },
    "declared_category": { "value": "Apparel & Accessories > Clothing > Shirts & Tops",
                           "src": "row12.Product category" }
  },

  "narrative": {
    "description_text": { "value": "…plain text…", "src": "row12.Description" },
    "description_html": { "value": "<p>…</p>",     "src": "row12.Description" },
    "structure": { "has_lists": true, "has_tables": false, "has_headings": false,
                   "word_count": 84 },
    "seo_title":       { "value": null, "src": null },
    "seo_description": { "value": null, "src": null }
  },

  "attributes": [                                // one entry per extracted attribute
    {
      "key": "material_composition",             // taxonomy.md attribute key
      "value_raw": "100% combed ring-spun cotton",
      "origin": "merchant_structured",           // see §9.4
      "src": "row12.product.metafields.custom.material",
      "scope": "product"                         // product | variant:<variant_id>
    }
  ],

  "options": [
    { "name": "Size",  "values": ["S","M","L"], "src": "row12.Option1 name" },
    { "name": "Color", "values": ["Black","White"], "src": "row12.Option2 name" }
  ],

  "variants": [
    {
      "variant_id": "sku:NG-TEE-BLK-M",
      "option_values": { "Size": "M", "Color": "Black" },
      "sku":     { "value": "NG-TEE-BLK-M", "src": "row13.SKU" },
      "barcode": { "value": null, "src": null },
      "price":   { "value": "28.00", "currency": null, "src": "row13.Price" },
      "media_refs": [],
      "attributes": []                            // variant-scoped attributes only
    }
  ],

  "media": [
    { "url": "https://…/tee-black.jpg", "alt": { "value": null, "src": null },
      "scope": "product", "src": "row12.Product image URL" }
  ],

  "metafields": [
    { "namespace": "custom", "key": "material", "value": "100% combed ring-spun cotton",
      "type": null, "src": "row12.product.metafields.custom.material" }
  ],

  "tags": [                                       // one record per source tag
    { "value": "everyday", "src": "row12.Tags[5:13]" },
    { "value": "unisex",   "src": "row12.Tags[15:21]" }
  ],

  "claims": [                                     // populated by the check phase, not by
    { "text": "Dermatologist tested",             // normalization -- see below
      "src": "row12.Description[210:230]" }
  ],

  "raw_extras": { }                               // preserved, uninterpreted
}
```

**`tags[]`.** One `{value, src}` record per source tag, carrying provenance exactly as every other canonical value does (§6.2 rule 1). A tag list arrives as a single delimited cell or array, so each tag gets its own locator — a character span into the source cell for Format A, an element locator for Formats B and C — and each is therefore individually quotable and byte-exact reproducible. The member exists because [`taxonomy.md`](./taxonomy.md) §2 makes `tag_map` the fourth-order category signal: a record without tags cannot be classified by rule 4. Splitting is on the delimiter and nothing else — whitespace around a tag is trimmed, the tag's own text is never altered, and an empty segment is dropped rather than recorded as an empty tag.

**`claims[]`.** Populated by the check phase, not by normalization. §9.6's four claim classes are illustrated by example patterns — "best", "clinically proven", "reduces wrinkles in 7 days" — and those examples are illustrative, not a normative extraction lexicon. Deriving one and applying it during normalization would put a check's judgment in the input layer, where it could not be labelled, evidenced, or scored, and where a false positive would be indistinguishable from supplied data. Normalization therefore retains the prose verbatim in `narrative` with its locators, and claim recognition happens where §9.6 says it happens. Format C input carries `claims[]` through unchanged, because in that format it is supplied data.

### 6.2 NPR design rules

1. **Every value is a `{value, src}` pair.** A bare scalar in the NPR is a spec violation. `src` is a source locator string (§8.2) and must resolve back to the input file.
2. **`null` means absent in the source.** There is no other representation of absence, and absence is never coerced to `false`, `0`, or `""`.
3. **The NPR is not a merge.** If two source locations disagree, both are recorded (as two `attributes[]` entries with the same `key`) and the conflict is resolved by a check, not by the normalizer. See §9.2.
4. **Normalization never enriches.** It maps, groups, extracts, and preserves. It does not infer a material from a title or a category from a description. Inference happens only in classification and in explicitly-labeled inference checks (§9.5).
5. **Attribute keys come from `taxonomy.md`.** An extracted value whose meaning does not map to a defined attribute key stays in `raw_extras`.
6. **Divergence is preserved, never resolved.** Where the input states a product-level value more than once and the statements disagree, the normalizer records all of them with their locators (§5.1) and picks no winner. This is rule 3 applied to the one case where a format-level reading rule — "carry down from the first row" — could otherwise be mistaken for a resolution rule. The normalizer has no mechanism for choosing between two supplied values, and adding one would violate the standing rule that the tool never picks a winner in a conflict (§9.2, [`decisions.md`](./decisions.md) D-012).

---

## 7. Output format

Two artifacts per run, written to `reports/<run-id>/`. The JSON is the source of truth; the Markdown is rendered from it and must not contain any assertion absent from the JSON.

### 7.1 `report.json`

```jsonc
{
  "report_version": "0.1",
  "run": {
    "run_id": "2026-08-24T14-05-02Z-a91c",
    "started_at": "2026-08-24T14:05:02Z",
    "input": { "file": "evals/fixtures/apparel_basic.csv", "format": "shopify_csv",
               "products_in": 12, "products_audited": 12 },
    "rubric_version": "0.3",
    "taxonomy_version": "0.1",
    "run_errors": []
  },
  "catalog_summary": {
    "score_mean": 61.4,
    "score_median": 64,
    "grade_distribution": { "agent_ready": 0, "strong": 2, "adequate": 6,
                            "weak": 3, "insufficient": 1 },
    "blocker_count": 1,
    "top_systemic_gaps": [
      { "check_id": "APPAREL.MATERIAL_COMPOSITION", "affected_products": 9,
        "points_lost_total": 45.0 }
    ]
  },
  "products": [
    {
      "product_id": "handle:cotton-crew-tee",
      "title": "Cotton Crew Tee",
      "category": { "assigned": "apparel", "method": "declared_category_map",
                    "confidence": "high",
                    "evidence": [ /* evidence objects */ ] },
      "score": {
        "total": 64.0,
        "max_applicable": 100.0,
        "grade": "adequate",
        "grade_capped_by": null,
        "dimensions": [
          { "dimension": "D1_identity", "earned": 11.0, "max": 15.0,
            "checks": [
              { "check_id": "IDENT.TITLE_SPECIFIC", "status": "PASS",
                "earned": 4.0, "max": 4.0 }
            ]
          }
        ]
      },
      "findings": [ /* Finding objects, §7.3 */ ],
      "unknowns": [
        { "attribute": "care_instructions", "checked_paths": ["metafields.*", "description_text"],
          "question": "What are the care instructions for this garment?" }
      ],
      "questions_for_merchant": [
        { "priority": 1, "question": "What is the fabric composition, by percentage?",
          "unlocks_points": 6.0, "related_findings": ["F-0003"] }
      ]
    }
  ]
}
```

### 7.2 `report.md`

Rendered per product, ordered by *points recoverable* descending (highest-leverage work first, not lowest score first). Required sections per product: header with score, grade and category (with classification method); the findings table; an **Unknowns** section stated as unknowns, never as failures; and the ranked **Questions for the merchant**.

Every finding line in the Markdown must show its evidence excerpt or its checked-and-empty path. A finding rendered without evidence is a rendering bug of severity blocker.

### 7.3 Finding schema

```jsonc
{
  "finding_id": "F-0003",                    // stable within a report
  "check_id": "APPAREL.MATERIAL_COMPOSITION", // stable across reports; see rubric.md
  "dimension": "D2_category_attributes",
  "scope": { "level": "product",              // product | variant | option | catalog
             "ref": null },                   // variant_id / option name when applicable
  "status": "UNKNOWN",                        // PASS | PARTIAL | FAIL | UNKNOWN | NOT_APPLICABLE
  "severity": "major",                        // §7.4
  "confidence": "high",                       // §7.5 — confidence in the FINDING, not the product
  "determination": "structural",              // structural | recognized — which of D-020's two
                                              // arms produced `confidence`. Drives §9.5's
                                              // *(interpreted)* tag in the Markdown report;
                                              // `confidence` alone cannot, because a `low`
                                              // check reports `low` on both arms. See D-026.
  "title": "Fabric composition is not stated",
  "detail": "No fabric or material composition was found in the description, the product metafields, or any variant attribute.",
  "evidence": [ /* §8.1 */ ],
  "points": { "earned": 0.0, "max": 6.0, "penalty": 0.0 },
  "remediation": {
    "type": "question",                       // question | correction | structure
    "question": "What is the fabric composition, stated as a percentage per fibre?",
    "target_field": "metafields.custom.material or a category metafield for the assigned category",
    "note": "Do not generate a value. This must be supplied by the merchant or supplier."
  }
}
```

Field rules:
- `status: "UNKNOWN"` is the default for any attribute-completeness check that finds nothing. `FAIL` is reserved for things that are *present and wrong* (conflicts, unsupported claims, inconsistent variants), never for absence.
- `points.penalty` is non-zero only for `FAIL` findings in penalty dimensions (D6, D7). See [`rubric.md`](./rubric.md).
- `remediation.type: "question"` is mandatory whenever the fix requires a product fact the data does not contain.
- **`remediation.question` MUST NOT contain a concrete example value that is absent from the supplied product data.** See §7.6.

### 7.4 Severity levels

Severity answers: *how much does this hurt the buyer's or agent's ability to choose this product correctly?* It is a property of the check and its scope, assigned by the rubric — not chosen freely at runtime.

| Severity | Definition | Examples |
| --- | --- | --- |
| `blocker` | The data is actively misleading or unsafe. A buyer or agent acting on it could be materially harmed or make a false purchase. | Description contradicts the spec on a safety-relevant fact; ingredient/allergen conflict; regulated claim with a contradicting attribute. |
| `critical` | A fact required to make the purchase decision at all is missing or broken for this category. | No size system on apparel; no ingredient list on beauty; no compatibility on electronics; variants exist but are undifferentiated. |
| `major` | A decision-relevant attribute is absent or a claim is unsupported. Buyer can still transact, but comparison is degraded. | Material composition unknown; no dimensions on furniture; "clinically proven" with no referenced basis. |
| `minor` | Enrichment or structure gap. Marginal effect on comparison. | No alt text; description has no list/table structure; no use-case statement. |
| `info` | Observation with no points attached. Recorded for context. | Near-duplicate attribute detected and merged; category assigned by fallback. |

**Blocker rule:** any `blocker` finding caps the reported **grade label** at `insufficient` regardless of numeric score. The numeric score is still reported unmodified — we do not distort the arithmetic to express severity. `grade_capped_by` names the finding.

### 7.5 Confidence levels

Confidence answers a narrow question: **how sure are we that this finding is correct about the supplied data?** It is never a confidence about the product itself, about the world, or about the merchant's intent.

| Confidence | Assignment rule |
| --- | --- |
| `high` | Determined by exact match, structural presence/absence, or arithmetic over the NPR. No language judgment involved. E.g. field empty across all checked paths; two numeric values disagree; variant count vs option cardinality mismatch. |
| `medium` | Requires bounded language interpretation over a verbatim excerpt — e.g. recognizing "made of cotton" in prose as a material statement, or classifying a sentence as a comparative claim. The excerpt is quoted in evidence so a human can overrule it. |
| `low` | Requires interpretation that a reasonable reviewer could disagree with — e.g. whether a use case is "specific enough", whether two differently-worded attributes are duplicates. |

Hard rules:
1. **Confidence is never used to hedge a fabrication.** There is no confidence level at which the tool may state a product fact the data does not contain. Low confidence attaches to *findings about the data*, never to invented values.
2. `low`-confidence findings carry **at most `minor` severity** and **never carry a penalty**. They may inform but never punish.
3. Confidence is assigned by the check definition, not improvised.

### 7.6 Rules for merchant-facing questions

Every question the tool addresses to the merchant — `remediation.question`, `unknowns[].question`, and `questions_for_merchant[].question` — is bound by one rule:

> **A question MUST NOT contain a concrete example value that is absent from the supplied product data.**

A question **may** state:

| Permitted | Example |
| --- | --- |
| The information requested | "What is the fabric composition?" |
| The field it belongs in | "...in `attributes[material_composition]` or a category metafield." |
| The expected unit | "What are the assembled dimensions, in centimetres?" |
| The expected format or structure | "...stated as width x depth x height." |
| The axis of an ambiguity (§9.3) | "'Large' is stated without a size system — against which standard?" |
| A value **quoted from the supplied data** | "Which is correct — 'Machine wash cold' or 'Dry clean only'?" |

A question **must not** state:

| Prohibited | Why |
| --- | --- |
| An illustrative value the data does not contain — `(e.g. '60% cotton, 40% polyester')` | It is an invented product fact, in the one field the merchant is most likely to copy from. |
| A plausible default | Same, with the added risk of being accepted unread. |
| A value inferred from category, brand, price, or model | Prohibited independently by §9.5. |

**Rationale.** A merchant under time pressure will accept a plausible suggestion without verifying it, which converts a question into a fabrication with the merchant's name on it. The tool also cannot distinguish, at audit time, between "this is a format illustration" and "this is what your value should be" — and neither can the reader. Describing the *shape* of the answer carries the entire practical benefit of an example without asserting anything about this product.

Note the asymmetry with §9.2: quoting a supplied value back to the merchant is not only permitted but required when reporting a conflict. The rule prohibits *introducing* values, not *citing* them.

**Enforcement.** The fabrication audit rejects an untraceable fact token in any question (`FAB013_SUGGESTED_VALUE_IN_QUESTION` when it sits inside an example frame such as "e.g." or "such as"; the kind-specific codes `FAB004`–`FAB010` otherwise). Both paths are covered by regression tests.

---

## 8. Evidence and provenance rules

Evidence is the mechanism that makes the no-invention principle enforceable rather than aspirational. **A finding without evidence is not emitted.** This is a hard gate, not a quality guideline.

### 8.1 Evidence object

```jsonc
{
  "type": "quote",              // quote | field_value | absence | derived | external_reference
  "locator": "row12.Description[210:230]",
  "excerpt": "Dermatologist tested",
  "checked_paths": null,        // required when type = "absence"
  "note": null
}
```

| Type | Meaning | Requirements |
| --- | --- | --- |
| `quote` | Verbatim span from free text. | `excerpt` must appear byte-identically in the source at `locator`. No paraphrase, no ellipsis-editing, no case changes. |
| `field_value` | Whole value of a structured field. | `locator` names the field; `excerpt` is the value verbatim. |
| `absence` | The evidence *is* the search. | `checked_paths` MUST enumerate every path searched (e.g. `["metafields.*", "description_text", "variants[*].attributes"]`). Without it the finding is unfounded. |
| `derived` | A computed comparison over other evidence. | Must reference at least two other evidence items in `note` and state the operation ("14 variants, options yield 6 combinations"). |
| `external_reference` | A merchant-supplied external pointer (a linked test report, a certification number) that the data *mentions*. | Recorded as **mentioned**, never fetched, never verified. V0 makes no network calls. Its presence may satisfy "a basis is referenced"; it never establishes that the claim is true. |

### 8.2 Source locators

A locator must be resolvable back to the input by a human with the input file open. **This section is the single authoritative definition of locator syntax.** No other document may define it; other documents reference this section.

Per input format (§5):

- **Format A — CSV:** `row<N>.<Column Name>`, optionally `[start:end]` for a character span within the cell.
- **Format B — GraphQL JSON:** `products[<i>].<field path>`, e.g. `products[3].variants.nodes[7].sku`.
- **Format C — PIP JSON:** the grammar in §8.2.1.
- **Metafields:** `<namespace>.<key>` appended to the owning path.
- **Spans** are character offsets into the **plain-text extraction**, with the HTML retained so a renderer can highlight.

#### 8.2.1 Format C (PIP) locator grammar

```
locator  := segment ( "." segment )*  span?
segment  := ident ( "[" selector "]" )?
selector := integer | free-text key (may contain "." and ":")
span     := "[" int ":" int "]"      -- valid only as the final bracket group
```

| Locator | Resolves to |
| --- | --- |
| `identity.title` | the title value |
| `identity.title[10:27]` | a character span of that value |
| `narrative.description_text[27:45]` | a character span of the description |
| `attributes[material_composition].value_raw` | that attribute's raw value |
| `metafields[custom.material].value` | a metafield, selected by `namespace.key` |
| `tags[0].value` | a tag, selected positionally |
| `variants[sku:HL-TEE-M].sku` | a variant, selected by `variant_id` |
| `variants[sku:HL-TEE-M].option_values[Size]` | a variant's option value |
| `options[Size].values` | an option's value list |
| `media[0].alt` | positional selection |

Resolution rules:

1. A selector matches a list element on `key`, `variant_id`, `name`, `id`, `handle`, or `namespace.key`; an integer selector indexes positionally; against a dict, it is a key lookup.
2. A node shaped like a `{value, src}` pair resolves to its `value`.
3. A `null` value resolves to **absent**, never to `""` (§6.2 rule 2). A span over an absent value is an error, not an empty string.
4. A span whose end exceeds the value length is an error. Locators fail loudly; they never resolve approximately.
5. Locators address the product record only. They cannot address the fixture envelope (§5.3.1).

### 8.3 Provenance rules

1. **No evidence, no finding.** Enforced at report assembly; a finding with an empty `evidence` array is dropped and logged as a `run_error`.
2. **No cross-product evidence.** A finding about product A may not cite product B's data. Catalog-scope findings are aggregations of per-product findings and cite them by `finding_id`.
3. **No world knowledge as evidence.** "Cotton is breathable" is not evidence. The model's background knowledge may inform *which checks are relevant to a category*; it may never be the basis for asserting a fact about a specific product.
4. **Quotes are immutable.** If the excerpt cannot be reproduced verbatim, the finding is invalid.
5. **Absence must be exhaustive.** An `absence` evidence item that omits a path where the value actually exists is a **false negative bug of blocker severity** — it is the failure mode most likely to make the tool untrustworthy, because it manufactures a gap that isn't there.

---

## 9. Handling rules for hard cases

These eight rules are normative. [`rubric.md`](./rubric.md) implements them as checks.

### 9.1 Missing information

Report as `status: UNKNOWN`, earned points 0, **no penalty**. Emit an `unknowns[]` entry and a merchant question. Attach `absence` evidence enumerating checked paths.

Never: state or imply the negative ("does not include a warranty"), infer from category norms ("most tees are cotton"), or infer from price. The report's language for unknowns is fixed: *"Not stated in the supplied data."*

### 9.2 Contradictory information

Two source locations assert incompatible values for the same attribute. Detected only where both values are extractable and comparable.

- Emit **one** `FAIL` finding with `check_id` in the `CONFLICT.*` family, citing **both** locations as separate evidence items.
- **The tool does not pick a winner.** It does not privilege metafield over description or vice versa. It reports the conflict and asks which is correct.
- Severity: `blocker` if the conflicting attribute is safety-, allergen-, compatibility-, or compliance-relevant for the category; otherwise `critical`.
- The conflicted attribute scores **0 earned in D2** for that attribute, *and* the D6 penalty applies. This double effect is intentional: contradictory data is worse than absent data, because it actively misleads.
- Numeric near-values within a stated tolerance (`±2%` or an explicit unit-conversion match) are **not** conflicts; they are `info` findings for unit inconsistency.

### 9.3 Ambiguous information

A value is present but does not resolve to a usable fact — "one size", "various colors", "large", "eco-friendly materials", "up to 12 hours".

- `status: PARTIAL`, partial credit as defined per check (default: 50% of the attribute's points).
- Confidence `medium` or `low`; severity capped at `major`.
- Evidence must quote the ambiguous span verbatim.
- Remediation is a **disambiguating question**, which must offer the axis of ambiguity without proposing a value: *"'Large' is stated without a size system — what are the measured dimensions, and against which size standard?"*
- The tool never resolves the ambiguity itself, including when only one resolution seems plausible.

### 9.4 Merchant-provided facts

Every value in the NPR carries an `origin`:

| Origin | Meaning | Trust |
| --- | --- | --- |
| `merchant_structured` | A dedicated structured field: metafield, option, SKU, price, taxonomy category. | Highest. Treated as the merchant's assertion of fact. |
| `merchant_prose` | Extracted from free-text description or SEO fields. | Treated as the merchant's assertion, with `medium` confidence on the extraction itself. |
| `merchant_placeholder` | Present but a non-value: `N/A`, `TBD`, `-`, `.`, `xxx`. | Treated as **absent**, with the placeholder quoted in evidence. |

Rules: the tool **never contradicts a merchant-provided fact using world knowledge.** If a merchant states a wool sweater is machine washable, that is not a finding. Only two things generate findings about a stated fact: it conflicts with another *supplied* value (§9.2), or it is a claim requiring support that the supplied data does not carry (§9.6). We audit the data's internal integrity, not the merchant's truthfulness about the world.

### 9.5 AI inference

Inference is permitted in exactly three places, and its output is always labeled and never written into `attributes[].value_raw` as a merchant fact:

1. **Category classification** (§4.2 step 5) — assigning one of five categories. Labeled with `method` and `confidence`; the operator can override.
2. **Language recognition over quoted spans** — recognizing that a quoted sentence states a material, a use case, or a claim. The span is always quoted; the recognition is the inference, the span is the evidence.
3. **Near-duplicate detection** (§9.8) — proposing that two attributes are the same attribute.

Everywhere else inference is prohibited. Specifically prohibited: inferring attribute values from category norms, brand, price, image filenames, competitor knowledge, or the model's product knowledge. Inferred content is never permitted in `remediation.question` as a suggested value, and never in generated copy — V0 generates no product copy at all ([`decisions.md`](./decisions.md) D-005).

Every inference-derived finding carries `confidence` of `medium` or `low` and is marked in the Markdown report with an explicit *(interpreted)* tag.

### 9.6 Unsupported marketing claims

A **claim** is a statement that asserts a property whose truth a buyer would rely on and which requires a basis. V0 recognizes four claim classes:

| Class | Pattern | Required support in the supplied data |
| --- | --- | --- |
| `superlative` | "best", "#1", "world's leading" | A named, quoted basis (award, ranking source, date). |
| `comparative` | "40% stronger", "lasts twice as long" | The comparison target and the measurement basis. |
| `certification_or_test` | "clinically proven", "dermatologist tested", "FDA approved", "CE certified", "organic" | A referenced certification body, standard number, study, or certificate identifier present in the data (`external_reference` counts as referenced, not as verified). |
| `outcome_or_efficacy` | "reduces wrinkles in 7 days", "eliminates odor" | A referenced study, test, or explicit qualifier ("in a consumer study of N=…"). |

The patterns in that table are **illustrative examples, not a normative extraction lexicon.** They show what each class looks like; they do not enumerate it. Consequently:

- **Claim extraction is a check-phase concern.** The normalizer does not scan prose for claims (§6.1, `claims[]`). It retains the description verbatim with its locators and stops there. Recognizing that a quoted span states a claim is language inference, permitted under §9.5 rule 2 precisely because it happens over a quoted span inside a check, where it is labelled, evidenced, confidence-rated, and visible in the report. The same recognition performed silently during normalization would be none of those things.
- A recognition lexicon, when one is written, belongs to the check that uses it and is versioned with [`rubric.md`](./rubric.md). Format C input is the exception: a `claims[]` entry supplied in a PIP file is supplied data and is carried through unchanged.

Handling:
- Present without support → `FAIL`, `check_id` `CLAIM.UNSUPPORTED_*`, penalty in D7, severity `major` (or `blocker` where a regulated-claim pattern is combined with a contradicting supplied attribute — e.g. "fragrance-free" alongside a fragrance ingredient).
- Present with a referenced basis → `PASS`. **We report that a basis is referenced. We never assert the claim is true or the basis is valid.** This distinction must survive into report wording.
- The tool does **not** provide legal or regulatory advice, and does not assert that a claim violates any law. It reports that the supplied data does not carry the support the claim implies. ([`decisions.md`](./decisions.md) D-007.)
- Absence of claims is never penalized. A plainly-written product scores full D7.

### 9.7 Variant-specific information

- Attributes are scoped: `product` or `variant:<id>`. A variant-scoped attribute never satisfies a product-scope requirement, and a product-scope attribute satisfies a variant requirement **only** for attributes declared `inheritable` in [`taxonomy.md`](./taxonomy.md) (e.g. `material_composition` is inheritable; `size_measurements` is not).
- **Differentiation check:** if a product has N > 1 variants, the data must let a buyer tell them apart. Options with distinct values satisfy this. If variants exist with identical or empty option values, `FAIL`, severity `critical`.
- **Coverage check:** an attribute required at variant scope must be present for **every** variant. Partial coverage → `PARTIAL`, scored proportionally (`covered / total`), with evidence naming the uncovered variant IDs explicitly — never "some variants".
- **Consistency check:** variant-scoped values must be consistent with product-scope values where both exist (a variant priced outside a stated product price range is a D6 conflict).
- **Option integrity:** option names must be non-empty and distinct; option values must be non-empty and distinct within an option; variant count should be consistent with the option-value cross-product (a mismatch is `info` unless variants are undifferentiated, since intentional partial matrices are legitimate).
- Reports never aggregate away variant detail. "3 of 12 variants lack a color value" must name the three.

### 9.8 Duplicate and near-duplicate attributes

Two attributes are **duplicates** when they carry the same meaning for the same scope.

- **Exact duplicate** (same key, same normalized value, different locations): merge, emit `info`, score once. Not a penalty.
- **Near-duplicate** (different keys or wordings, same meaning — `material` vs `fabric`; `Colour` vs `Color`): propose a merge as an `info` finding with `confidence: low`, listing both locators. Score once, under the canonical key from [`taxonomy.md`](./taxonomy.md).
- **Duplicate with different values**: this is *not* a duplicate — it is a conflict. Route to §9.2. This ordering matters: never dedupe away a contradiction.
- **Never** score the same underlying fact twice. Attribute coverage is measured over canonical keys, so redundancy cannot inflate a score.
- Redundancy is not itself penalized in V0. A merchant repeating the material in prose and in a metafield is doing something reasonable. ([`decisions.md`](./decisions.md) D-009.)

---

## 10. Scoring system (summary)

Full specification, per-check point allocation, and worked examples: [`rubric.md`](./rubric.md).

### 10.1 Design constraints

1. **Explainable by construction.** The score is `sum(earned points across all applicable checks) − sum(penalties)`, clamped to `[0, 100]`. Every point traces to a named check with a fixed maximum. There is no model-generated number anywhere in the score path.
2. **No "AI score".** No opaque composite, no learned weighting, no vibes. If a merchant asks "why 64?", the report already contains the full arithmetic.
3. **Deterministic.** Same input + same rubric version → same score, byte-identical. Non-determinism is a test failure ([`decisions.md`](./decisions.md) D-004).
4. **Unknown ≠ penalty.** Missing information forfeits its points and stops there. Only conflicts and unsupported claims subtract.
5. **Category-relative.** The applicable check set differs by category. A tee is not scored against "battery life".

### 10.2 Dimension allocation

| # | Dimension | Points | Mechanism |
| --- | --- | --- | --- |
| D1 | Product identity clarity | 15 | Earned |
| D2 | Category-relevant attribute completeness | 22 | Earned (category-specific) |
| D3 | Variant clarity and consistency | 15 | Earned (N/A if single-variant → renormalized) |
| D4 | Use-case information | 12 | Earned |
| D5 | Decision and trust information | 12 | Earned |
| D6 | Factual consistency (conflicts) | 10 | Starts full, penalties subtract |
| D7 | Claim substantiation | 8 | Starts full, penalties subtract |
| D8 | Coverage and machine readability | 6 | Earned |
| | **Total** | **100** | |

### 10.3 Not-applicable and renormalization

A check may be `NOT_APPLICABLE` only for a **structural** reason derivable from the data: single-variant products skip variant-differentiation checks; a product with no claims skips claim-support checks (D7 stays full). N/A checks are removed from the denominator and the total is renormalized to 100, with `max_applicable` and the renormalization factor printed in the report.

**A check is never N/A because the information is missing.** That is UNKNOWN. Conflating the two would let a bad catalog score well by having less data — the single most important scoring failure to avoid.

### 10.4 Grade bands

| Score | Grade | Meaning |
| --- | --- | --- |
| 90–100 | `agent_ready` | Complete, consistent, structured, category-appropriate. |
| 75–89 | `strong` | Minor gaps; comparison is possible on all key axes. |
| 60–74 | `adequate` | Transactable; comparison degraded on some axes. |
| 40–59 | `weak` | Major decision facts absent or inconsistent. |
| 0–39 | `insufficient` | Cannot support an informed purchase decision. |

Any `blocker` finding caps the label at `insufficient` (§7.4).

---

## 11. Acceptance criteria for V0

V0 ships when all of the following hold. Criteria are written to be testable.

### 11.1 Functional

| ID | Criterion |
| --- | --- |
| AC-F1 | The skill ingests all three input formats (§5) and produces an NPR conforming to §6 for each. |
| AC-F2 | Every NPR value is a `{value, src}` pair with a resolvable locator. Validator reports zero bare scalars. |
| AC-F3 | Each product is assigned one of the five categories or `uncategorized`, with `method`, `confidence`, and evidence. |
| AC-F4 | The full applicable check set runs for the assigned category; no check silently skips. |
| AC-F5 | `report.json` validates against the report schema; `report.md` contains no assertion absent from `report.json`. |
| AC-F6 | Scores are computed by arithmetic from the findings ledger; recomputing from the ledger independently reproduces `score.total` exactly. |
| AC-F7 | A run of 200 products completes and writes both artifacts, with per-product errors isolated to `run_errors`. |

### 11.2 Integrity — the gating criteria

| ID | Criterion |
| --- | --- |
| AC-I1 | **Zero fabricated product facts** across the entire eval set. Any attribute value, spec, claim, or measurement in either artifact that does not appear in the input is a release blocker. Measured by the fabrication audit (§12.3). |
| AC-I2 | Every finding has ≥1 evidence item. Zero exceptions. |
| AC-I3 | Every `quote` excerpt is byte-reproducible from the input at its locator. Automated verification, 100% pass. |
| AC-I4 | Every `absence` evidence item enumerates `checked_paths`, and the value is genuinely absent from all of them (no false gaps). |
| AC-I5 | No finding states or implies a negative fact from absence. Verified by the negation-language audit against a prohibited-phrase list ("does not contain", "is not", "lacks a ...", "no warranty"). |
| AC-I6 | Missing information yields `UNKNOWN` with zero penalty in 100% of adversarial-absence fixtures. |
| AC-I7 | No output text claims or implies AI ranking, visibility, or citation benefit (§1.2). Automated phrase audit. |
| AC-I8 | Every conflict finding cites **both** conflicting locations and asserts no winner. |

### 11.3 Quality

| ID | Criterion |
| --- | --- |
| AC-Q1 | Determinism: three runs on the same fixture produce byte-identical `report.json` modulo `run_id` and timestamps. |
| AC-Q2 | Category classification accuracy ≥ 95% on the labeled fixture set; misclassifications are `low` confidence, not confident errors. |
| AC-Q3 | False-FAIL rate ≤ 2% on the "complete product" fixtures (well-described products must not be told they are broken). |
| AC-Q4 | Conflict detection recall ≥ 90% on the seeded-conflict fixtures. |
| AC-Q5 | Unsupported-claim detection recall ≥ 85% and precision ≥ 90% on the seeded-claim fixtures. |
| AC-Q6 | Every `UNKNOWN` produces a merchant question that is answerable without the tool proposing a value. Human review, 100%. |
| AC-Q7 | A domain reviewer, given only `report.md` and the input file, can verify every finding without asking a clarifying question. |

---

## 12. Evaluation methodology

### 12.1 Fixture corpus

Fixtures live in `evals/fixtures/`, expected outcomes in `evals/expected/`. Target: **50 products minimum** for V0 sign-off.

| Set | Count | Purpose |
| --- | --- | --- |
| `complete/` | 10 (2 per category) | Well-described products. Tests false positives (AC-Q3). Expected score ≥ 85. |
| `sparse/` | 10 | Title + price only. Tests that everything becomes UNKNOWN, nothing becomes FAIL (AC-I6). |
| `conflict/` | 8 | Seeded contradictions incl. safety-relevant ones. Tests D6 and blocker capping (AC-Q4). |
| `claims/` | 8 | Supported and unsupported claims, mixed. Tests D7 precision (AC-Q5). |
| `variants/` | 6 | Undifferentiated variants, partial variant coverage, option anomalies. Tests D3. |
| `ambiguous/` | 4 | "One size", "various", "eco-friendly". Tests §9.3 PARTIAL. |
| `duplicates/` | 4 | Exact and near-duplicate attributes; one duplicate-with-different-values trap. Tests §9.8 and its routing to §9.2. |
| `adversarial/` | 4 | Inputs that bait invention: an evocative title with no facts; a category strongly implying attributes; placeholder text; a description that *asks* the tool to fill in gaps. Tests AC-I1. |

Every fixture ships with a **provenance note** stating whether it is synthetic or derived from public data, and no fixture may contain a real merchant's private data.

### 12.2 Expected-outcome format

Each fixture has an expectation file asserting, per product: assigned category; the set of `check_id`s expected `PASS` / `FAIL` / `UNKNOWN` / `PARTIAL` / `N/A`; expected score within a tolerance band (±2 points, tightening to ±0 once the rubric stabilizes); and, for seeded defects, the exact locators the evidence must cite.

Expectations assert **check outcomes and evidence locators**, not report prose. Prose is checked by the audits in §12.3.

### 12.3 Audits (run every eval)

1. **Fabrication audit (primary gate).** Extract every value-bearing token from both artifacts that is presented as a product fact; assert each is traceable to an input span. Any untraceable product fact fails the build. This audit is the operational definition of the core principle and must be built before the first check.
2. **Evidence integrity audit.** Verify every `quote` byte-matches its locator; verify every `absence` path list is complete by independently re-searching the NPR.
3. **Negation-language audit.** Grep both artifacts for prohibited absence-as-negation phrasing (AC-I5).
4. **Claim-scope audit.** Grep for prohibited ranking/visibility promises (AC-I7).
5. **Determinism audit.** Triple-run diff (AC-Q1).
6. **Arithmetic audit.** Independently recompute every score from the ledger (AC-F6).

### 12.4 Human review protocol

Before sign-off, two reviewers independently audit 10 randomly sampled product reports, scoring each finding as `correct` / `unfounded` / `misleading`. Sign-off requires zero `unfounded` findings and zero `misleading` findings. Inter-reviewer disagreement on a finding is itself a signal that the check's confidence level is too high.

### 12.5 Regression policy

Fixtures are append-only. Any rubric change that moves a fixture score requires updating the expectation file **in the same commit**, with the rationale in the commit message and, if the change alters scoring semantics, a new decision record in [`decisions.md`](./decisions.md) and a `rubric_version` bump.

---

## 13. Metrics (post-V0 instrumentation intent)

V0 collects no telemetry (no network). These are the metrics the product should eventually be judged on, recorded here so V0 does not foreclose them:

- **Trust:** rate at which merchants dispute a finding as unfounded. Target < 2%.
- **Actionability:** proportion of merchant questions that get answered.
- **Movement:** score delta between first and second run on the same catalog.
- **Leverage:** points recovered per merchant-hour spent.

Explicitly **not** a success metric: AI-channel traffic or placement. We do not control it and will not be judged on it (§1.2).

---

## 14. Non-goals

### 14.1 Not in V0 (deliberately deferred)

- Shopify OAuth or any authentication
- Shopify Admin API / Storefront API integration, or any network call whatsoever
- Billing, plans, entitlements
- Web UI, dashboard, or hosted service
- Deployment, containers, CI/CD infrastructure
- Any database or persistent store beyond files in `reports/`
- Automatic modification of any Shopify resource
- Multi-tenancy, user accounts, permissions, audit logs
- Scheduled or continuous monitoring
- Catalogs larger than 200 products per run

### 14.2 Not in the product at all (permanent non-goals)

- **Generating product facts, specs, or attribute values.** Permanent. This is the product's identity.
- **Writing marketing copy.** V0 emits questions, not content. Any future copy assistance must operate strictly over merchant-confirmed facts and must be a separately-named capability.
- **Guaranteeing or predicting AI ranking, visibility, or citation** (§1.2).
- **Legal, regulatory, or compliance certification.** We report that supplied data does not carry the support a claim implies. We never assert a legal violation or approve a claim as compliant.
- **Judging whether a merchant's stated facts are true about the world.** We audit internal integrity and sufficiency, not veracity.
- **Competitive intelligence** — scraping or comparing against other merchants' catalogs.
- **Image or video content analysis.** V0 reasons about media *metadata* (presence, alt text, variant linkage) only.

### 14.3 Deliberately deferred decisions

Recorded in [`decisions.md`](./decisions.md) §"Open questions" rather than guessed at here: multi-language/locale handling, currency and market variance, B2B catalogs, bundles and combined listings, and the merchant-facing packaging of the score.

---

## 15. Glossary

| Term | Definition |
| --- | --- |
| **NPR** | Normalized Product Record — the single internal representation all checks read (§6). |
| **PIP** | Product Intelligence Payload — our canonical JSON input format (§5.3). |
| **Check** | A named, deterministic test with a fixed `check_id`, dimension, max points, severity, and confidence. |
| **Finding** | The result of one check against one scope, with evidence (§7.3). |
| **Ledger** | The complete set of findings for a product; the sole input to scoring. |
| **Dimension** | One of D1–D8; a scoring bucket (§10.2). |
| **Attribute key** | A canonical attribute name defined in [`taxonomy.md`](./taxonomy.md). |
| **Origin** | Where a value came from and how much structural weight it carries (§9.4). |
| **Locator** | A resolvable pointer into the input file (§8.2). |
| **Claim** | A statement asserting a property that requires a basis (§9.6). |

---

## 16. Sources

Shopify behavior described in this document is drawn from primary Shopify sources, retrieved 2026-08-24. No Shopify API, capability, or behavior is asserted here that is not present in one of these.

1. [Shopify Catalog and product discovery for agentic storefronts — Shopify Help Center](https://help.shopify.com/en/manual/online-sales-channels/agentic-storefronts/products)
2. [Using CSV files to import and export products — Shopify Help Center](https://help.shopify.com/en/manual/products/import-export/using-csv)
3. [Product — GraphQL Admin API](https://shopify.dev/docs/api/admin-graphql/latest/objects/Product)
4. [The product variant limit is now 2048 for all merchants — Shopify developer changelog](https://shopify.dev/changelog/the-product-variant-limit-is-now-2048-for-all-merchants) and [ShopResourceLimits — GraphQL Admin API](https://shopify.dev/docs/api/admin-graphql/latest/objects/shopresourcelimits)
5. [Shopify/product-taxonomy — GitHub](https://github.com/Shopify/product-taxonomy) and [Shopify's Standard Product Taxonomy — Shopify Help Center](https://help.shopify.com/en/manual/products/details/product-category)
6. [Category metafields — Shopify Help Center](https://help.shopify.com/en/manual/custom-data/metafields/category-metafields)
7. [Agentic commerce — shopify.dev](https://shopify.dev/docs/agents)
