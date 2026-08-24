# Category Taxonomy — V0

- **Taxonomy version:** 0.1
- **Date:** 2026-08-24
- **Scope:** Exactly five categories. This is a deliberate ceiling, not a starting point for expansion.

Companions: [`PRD.md`](./PRD.md) · [`rubric.md`](./rubric.md) · [`decisions.md`](./decisions.md)

---

## 1. Why five categories

Shopify's Standard Product Taxonomy contains 10,000+ categories and roughly 2,000 associated product attributes, distributed as an open-source (MIT), calendar-versioned dataset.¹ We are not reproducing it and must not drift toward reproducing it.

V0's purpose is to prove that **category-aware auditing produces materially different and more useful findings than category-blind auditing**. Five well-specified categories with genuinely divergent attribute sets prove that. Five hundred shallow ones prove nothing and cannot be maintained by hand.

The five categories were chosen because their information needs differ along *different axes*, which stress-tests the design:

| Category | Dominant information axis | What breaks if it's missing |
| --- | --- | --- |
| `apparel` | Fit and body dimensions | Returns — the buyer cannot predict fit |
| `beauty` | Composition and safety | Harm — allergen and suitability decisions |
| `electronics` | Compatibility and specification | Non-function — the product doesn't work with what they own |
| `home` | Physical dimensions and placement | Non-fit — it doesn't go in the space |
| `sports` | Suitability to user and use | Injury and mismatch — wrong load rating, wrong skill level |

If one attribute schema could serve all five, this product would not need to exist. It cannot: apparel needs a size system, beauty needs an ingredient list, electronics needs compatibility, home needs assembled dimensions, sports needs a load rating. **Uniform attribute schemas are the failure mode we are designed against.**

Relationship to Shopify: our five categories are an **audit-side abstraction**, not a claim to mirror Shopify's taxonomy. Shopify surfaces category-linked attributes in the admin as *category metafields* (also called *product attributes*), which can be linked to variant options and option values.² Our attribute keys map onto those where the merchant uses them, and onto prose or custom metafields where they do not.

---

## 2. How a category is assigned

Assignment is per product, resolved by the first rule that matches. The winning `method` and `confidence` are always reported.

| Order | Method | Source | Confidence |
| --- | --- | --- | --- |
| 1 | `operator_override` | Explicit category supplied at invocation | `high` |
| 2 | `declared_category_map` | Shopify `category` / `Product category` field, mapped via §8 | `high` |
| 3 | `product_type_map` | `productType` / `Type` field, mapped via §8 | `medium` |
| 4 | `tag_map` | Product tags matching a mapping term | `medium` |
| 5 | `title_inference` | Language inference over title + description | `low` |
| 6 | `uncategorized` | Nothing matched, or rules 2–5 disagree | `low` |

Rules:
1. **Ties and disagreements do not get broken by guessing.** If two same-tier signals map to different categories, the result is `uncategorized` with an `info` finding naming both signals.
2. Classification is inference (PRD §9.5) and is always labeled. It never writes a value into `attributes[]`.
3. `uncategorized` products are audited against the **Common Core** (§3) only. D2 is scored against Common Core with `max_applicable` reduced accordingly, and the report states plainly that category-specific auditing did not run and why. We do not fake category coverage for unclassified products.
4. A `low`-confidence assignment adds a `minor` finding recommending the merchant set a product category in Shopify — a real, actionable gap, since the category drives Shopify's own attribute suggestions.²

---

## 3. Common Core attributes

Applies to **all five categories and to `uncategorized`**. These are audited in D1, D5, and D8, not in D2 — D2 is exclusively category-specific, so that the category-relevance of the score is real and not diluted by generic fields.

| Key | Tier | Scope | Inheritable | Notes |
| --- | --- | --- | --- | --- |
| `product_title` | A | product | — | Must identify the thing, not just evoke it (D1). |
| `brand` | A | product | — | Shopify `Vendor`. |
| `product_identifier` | B | variant | no | SKU, MPN, GTIN/barcode. Variant-scoped by nature. |
| `price` | A | variant | no | Value only; V0 makes no pricing judgment. |
| `description_substance` | A | product | — | Measured as informational content, not length (D1/D8). |
| `primary_image_present` | B | product | yes | Metadata presence only; no image analysis. |
| `image_alt_text` | C | product | yes | D8. |
| `country_of_origin` | C | product | yes | |
| `warranty_or_guarantee` | B | product | yes | D5. |
| `returns_policy_reference` | C | product | yes | A reference counts; the policy text need not be in the product record. |
| `certifications` | C | product | yes | Category tiering overrides this where certification is decision-critical. |

---

## 4. Tiers, scope, and inheritance

Every attribute carries three properties that drive scoring and variant logic.

### 4.1 Tier

| Tier | Meaning | Share of the category's D2 points |
| --- | --- | --- |
| **A — Required** | A buyer cannot responsibly choose this product without it. Absence is `critical`. | 60% of D2, split evenly across the category's Tier A attributes |
| **B — Important** | Materially improves comparison. Absence is `major`. | 30%, split evenly |
| **C — Enriching** | Adds useful differentiation. Absence is `minor`. | 10%, split evenly |

Even splitting within a tier is deliberate: it keeps the arithmetic explainable and stops per-attribute weights from becoming an unauditable tuning surface. Relative importance is expressed by **tier placement**, which is a reviewable product judgment, not by hidden coefficients ([`decisions.md`](./decisions.md) D-011).

### 4.2 Scope

- `product` — asserted once for the product.
- `variant` — must be resolvable **per variant**. Partial coverage scores proportionally and names the uncovered variants (PRD §9.7).

### 4.3 Inheritable

- `yes` — a product-scope value satisfies the requirement for all variants (e.g. `material_composition` on a tee that comes in three colors).
- `no` — must be variant-specific; a product-level value does **not** satisfy it (e.g. `garment_measurements`, `net_content`, `color_finish`). Inheriting these would let a merchant appear to have per-variant data they do not have.

### 4.4 Conditional applicability

Some attributes apply only when a structural trigger is present in the data (e.g. `assembly_required` details only matter once assembly is indicated). A conditional attribute whose trigger is absent is `NOT_APPLICABLE` and leaves the denominator (PRD §10.3). **A trigger is structural, never assumed** — we never decide an attribute is inapplicable because the product "probably" doesn't need it.

---

## 5. Category definitions

Each category lists its attributes with key, tier, scope, inheritance, what satisfies the check, and what counts as `PARTIAL` (ambiguous, per PRD §9.3).

---

### 5.1 `apparel`

Clothing, footwear, and worn accessories. **Dominant risk: fit uncertainty → returns.**

| Key | Tier | Scope | Inherit | Satisfied by | PARTIAL if |
| --- | --- | --- | --- | --- | --- |
| `size_system` | A | variant | no | A named sizing standard and value (US 10, EU 42, UK 8, or a stated numeric measure) | A bare size label with no system ("Large", "10") |
| `material_composition` | A | product | yes | Fiber content with percentages ("60% cotton, 40% polyester") | Material named without proportions ("cotton blend") |
| `fit_and_cut` | A | product | yes | Fit descriptor ("relaxed", "slim", "true to size") plus the cut/silhouette | Fit implied only by a style name |
| `garment_measurements` | A | variant | no | Measured dimensions per size (chest, length, inseam, waist, or a size chart resolvable per variant) | A single chart with no per-variant mapping |
| `care_instructions` | B | product | yes | Washing/drying/ironing guidance or a care symbol reference | "Easy care" with no method |
| `color_finish` | B | variant | no | A named color per variant | "Assorted", "various" |
| `closure_and_construction` | B | product | yes | Closure type, seam/knit construction, lining | |
| `intended_use_context` | B | product | yes | Season, activity, or occasion the garment is made for | Generic "everyday" only |
| `country_of_origin` | C | product | yes | Manufacturing country | |
| `sustainability_credentials` | C | product | yes | A named standard or certified material claim **with a referenced basis** (PRD §9.6) | Unnamed "eco-friendly" → routes to D7 as unsupported |
| `model_reference_measurements` | C | product | yes | Model height and size worn, enabling fit inference | Height without size worn |

Apparel-specific rules:
- `garment_measurements` is `variant`-scope, non-inheritable **by design**. A size chart that cannot be resolved to a specific variant is `PARTIAL`, not `PASS` — it is the single most common apparel fit failure.
- Footwear substitutes width and length-in-cm into `size_system` and `garment_measurements`; the keys do not change.
- Never infer fit from price, brand, or category norms.

---

### 5.2 `beauty`

Cosmetics, skincare, haircare, fragrance, personal care. **Dominant risk: harm and suitability.** This category carries the strictest evidence handling.

| Key | Tier | Scope | Inherit | Satisfied by | PARTIAL if |
| --- | --- | --- | --- | --- | --- |
| `ingredients_full` | A | variant | no | A complete ingredient list (INCI-style) | "Key ingredients" only, or a truncated list |
| `net_content` | A | variant | no | Quantity with unit per variant (50 ml, 1.7 fl oz) | Unit-less number, or one size stated for a multi-size product |
| `usage_directions` | A | product | yes | How, how much, when, where to apply | "Use as directed" |
| `suitability` | A | product | yes | Skin/hair type, concern, or user suitability | "For all skin types" with no basis stated |
| `warnings_and_restrictions` | A | product | yes | Allergens, cautions, patch-test guidance, age/pregnancy restrictions, or an explicit statement of none | A caution referenced but not stated |
| `key_actives_and_concentration` | B | product | yes | Named actives with concentration | Actives named without concentration |
| `formulation_format` | B | product | yes | Serum, cream, balm, oil, powder, aerosol | |
| `fragrance_status` | B | product | yes | Scent profile, or an explicit fragrance-free statement | "Lightly scented" with no profile |
| `shelf_life_or_pao` | B | product | yes | Expiry or period-after-opening | |
| `color_shade` | B | variant | no | Named shade per variant, with undertone or swatch reference | Shade code with no name or description |
| `certifications_and_testing` | C | product | yes | Named certification or testing body **with a referenced basis** | Claim with no named body → D7 |
| `application_tools_included` | C | product | yes | Applicator, spatula, dropper | |

Beauty-specific rules:
- **`warnings_and_restrictions` absence is `UNKNOWN`, never "no warnings".** This is the highest-consequence place in the entire product where absence-as-negation would be dangerous, and it is a required adversarial eval fixture.
- An ingredient list that contradicts a claim (`fragrance-free` + a fragrance ingredient; `vegan` + an animal-derived ingredient) is a **`blocker` conflict** (PRD §9.2), not a claim finding, because two supplied values disagree.
- `net_content` and `color_shade` are non-inheritable: a size or shade stated only at product level does not describe a multi-variant lineup.
- The tool never assesses ingredient safety, efficacy, or regulatory status — only whether the supplied data is complete, internally consistent, and carries the support its claims imply.

---

### 5.3 `electronics`

Consumer electronics, components, accessories. **Dominant risk: incompatibility.**

| Key | Tier | Scope | Inherit | Satisfied by | PARTIAL if |
| --- | --- | --- | --- | --- | --- |
| `model_identifier` | A | variant | no | Manufacturer model number / MPN per variant | A marketing name only |
| `core_specifications` | A | product | yes | The category's defining measurable specs (capacity, resolution, wattage, speed, sensor, throughput) with units | Specs stated without units or ranges |
| `compatibility` | A | product | yes | Named compatible devices, standards, OS versions, or sockets | "Universal compatibility" with no list |
| `connectivity_and_ports` | A | product | yes | Port types, counts, wireless standards and versions | Standard named without version ("Bluetooth") |
| `power_requirements` | A | product | yes | Voltage/wattage, plug type or power source | Voltage without plug type for an international listing |
| `physical_dimensions_weight` | B | variant | no | Dimensions with units and weight | Dimensions without units |
| `battery` | B | product | yes | Chemistry, capacity, rated runtime with test conditions | Runtime with no conditions ("up to 12 hours") |
| `in_the_box` | B | product | yes | Enumerated contents | "Accessories included" |
| `warranty_term` | B | product | yes | Duration and coverage | Duration with no coverage scope |
| `software_requirements` | C | product | yes | Required app, account, subscription, or OS minimum | |
| `regulatory_certifications` | C | product | yes | Named marks/IDs (FCC ID, CE, UKCA, IP rating) | Mark named without identifier |
| `color_finish` | C | variant | no | Color per variant | |

Electronics-specific rules:
- `compatibility` absence is `critical`: the buyer cannot determine whether the product works with what they own.
- "Up to" performance figures without stated test conditions are `PARTIAL` under §5.3 **and** a `comparative`/`outcome` claim under PRD §9.6 if framed competitively. The two findings are distinct and both are emitted; they are not double-scored, because they land in different dimensions measuring different things.
- The tool never fills in a spec from a known model number, even when the model is famous. This is an explicit adversarial fixture.

---

### 5.4 `home`

Furniture, decor, kitchen, bedding, storage, home textiles. **Dominant risk: it doesn't fit the space or the use.**

| Key | Tier | Scope | Inherit | Satisfied by | PARTIAL if |
| --- | --- | --- | --- | --- | --- |
| `assembled_dimensions` | A | variant | no | Width × depth × height with units, per variant | Two of three dimensions, or no units |
| `materials_and_finish` | A | product | yes | Primary materials plus surface finish | "Wood" with no species or engineered/solid distinction |
| `capacity_or_load` | A | product | yes | Weight capacity, seating capacity, volume, or fill — as relevant to the item | A number with no unit or basis |
| `care_and_cleaning` | B | product | yes | Cleaning method, cleanability code, or washability | "Easy to clean" |
| `assembly` | B | product | yes | Whether assembly is required; if so, tools, parts, and time | "Some assembly required" with no detail |
| `indoor_outdoor_use` | B | product | yes | Suitability including weather/UV resistance where outdoor is stated | "Can be used outdoors" with no durability basis |
| `room_or_placement` | B | product | yes | Intended room or placement context | |
| `color_finish` | B | variant | no | Color/finish per variant | |
| `packaged_dimensions_weight` | C | product | yes | Shipping carton size and weight | |
| `mounting_and_hardware` | C | product | yes (conditional) | Mounting method, whether hardware is included | Applicable only when mounting is indicated |
| `safety_and_compliance` | C | product | yes | Flammability standard, stability/tip-over, food-contact safety, as relevant | Named without standard reference |

Home-specific rules:
- `assembled_dimensions` is variant-scoped and non-inheritable: sizes are frequently the variant axis, and one dimension set cannot describe them all.
- `capacity_or_load` is conditionally applicable — it needs a structural trigger (the product has a seat, shelf, container, or stated fill). Absent a trigger it is `NOT_APPLICABLE`, never assumed inapplicable.
- Dimension conflicts between description prose and a spec field are a **`critical` D6 conflict**; if the conflicting dimension is load-bearing or safety-relevant, `blocker`.

---

### 5.5 `sports`

Sporting goods, fitness equipment, outdoor gear. **Dominant risk: user/use mismatch, with injury exposure.**

| Key | Tier | Scope | Inherit | Satisfied by | PARTIAL if |
| --- | --- | --- | --- | --- | --- |
| `sport_or_activity` | A | product | yes | The specific activity the item is designed for | A broad family ("fitness") with no discipline |
| `user_fit_specification` | A | variant | no | Rider/user height, weight range, hand/foot size, or frame size per variant | A single range stated for a multi-size lineup |
| `load_or_capacity_rating` | A | product | yes | Maximum user weight, resistance range, or rated load with units | A number with no unit or no basis |
| `skill_or_intensity_level` | A | product | yes | Beginner / intermediate / advanced, or a defined performance tier | Implied by price or marketing tone only |
| `materials_and_construction` | B | product | yes | Frame, surface, padding, shell materials | Material named with no component mapping |
| `dimensions_and_weight` | B | variant | no | Product dimensions and weight with units | |
| `use_environment` | B | product | yes | Indoor/outdoor, terrain, surface, water/temperature conditions | "All conditions" |
| `safety_certification` | B | product | yes (conditional) | Named standard (helmet, impact, buoyancy) with identifier, where protective equipment is indicated | Certification named without standard number |
| `included_accessories` | C | product | yes | Enumerated contents | |
| `maintenance_requirements` | C | product | yes | Servicing, tensioning, lubrication, storage | |
| `age_or_user_suitability` | C | product | yes | Age range or user group, with basis | Age stated with no basis for a protective item |

Sports-specific rules:
- `load_or_capacity_rating` and `safety_certification` are the highest-consequence keys. A conflict on either is a **`blocker`**.
- `safety_certification` is conditional on the data indicating protective equipment. When the trigger is present and the certification is absent, this is `critical`, not `minor`.
- `user_fit_specification` is non-inheritable for the same reason as apparel's `garment_measurements`.

---

## 6. Attribute count and D2 point derivation

| Category | Tier A | Tier B | Tier C | D2 max |
| --- | --- | --- | --- | --- |
| `apparel` | 4 | 4 | 3 | 22 |
| `beauty` | 5 | 5 | 2 | 22 |
| `electronics` | 5 | 4 | 3 | 22 |
| `home` | 3 | 5 | 3 | 22 |
| `sports` | 4 | 4 | 3 | 22 |
| `uncategorized` | — | — | — | 0 (D2 removed, renormalized) |

Per-attribute points, for each category:
- Tier A: `13.2 / (count of Tier A attributes)`
- Tier B: `6.6 / (count of Tier B attributes)`
- Tier C: `2.2 / (count of Tier C attributes)`

Apparel worked example: Tier A = 13.2 / 4 = **3.30** each; Tier B = 6.6 / 4 = **1.65** each; Tier C = 2.2 / 3 = **0.733** each. Total = 13.2 + 6.6 + 2.2 = 22.0 (rounding rules in [`rubric.md`](./rubric.md) §6).

Consequence, stated plainly: **the same missing attribute is worth a different number of points in different categories**, because the attribute counts differ. This is correct and intended — the point is category relevance, not cross-category point parity. Cross-category score comparison is valid at the *score* level (all are out of 100), not at the per-attribute level.

---

## 7. Governance of this taxonomy

1. **Five categories is a hard cap for V0.** Adding a sixth requires a decision record and a rubric version bump.
2. **A new attribute must earn its place**: it must be stated in real merchant data often enough to be checkable, must change a buying decision, and must not be a rewording of an existing key.
3. **Every attribute must be answerable by the merchant without research.** If a merchant cannot answer the generated question from their own supplier data, the attribute is a bad check regardless of how ideal it is.
4. **No attribute may be scored that cannot be evidenced.** If a check cannot produce a locator, it is not a check.
5. Attribute keys are stable identifiers. Renaming a key is a breaking change requiring an expectation-file migration (PRD §12.5).

---

## 8. Mapping table (V0)

Mapping from common Shopify `category` / `productType` / tag values to our five categories. Deliberately conservative: **an unmatched value maps to `uncategorized`, never to a nearest guess.**

| Signal contains (case-insensitive) | Maps to |
| --- | --- |
| `apparel`, `clothing`, `shirt`, `dress`, `pants`, `outerwear`, `footwear`, `shoes`, `socks`, `underwear`, `activewear`, `swimwear`, `hat`, `scarf`, `glove` | `apparel` |
| `beauty`, `cosmetic`, `skincare`, `haircare`, `makeup`, `fragrance`, `perfume`, `serum`, `moisturizer`, `shampoo`, `personal care` | `beauty` |
| `electronics`, `computer`, `phone`, `audio`, `headphone`, `camera`, `charger`, `cable`, `monitor`, `speaker`, `wearable tech`, `smart home device` | `electronics` |
| `home`, `furniture`, `kitchen`, `bedding`, `decor`, `storage`, `lighting`, `rug`, `cookware`, `bath` | `home` |
| `sport`, `fitness`, `outdoor`, `camping`, `cycling`, `running gear`, `yoga`, `athletic equipment`, `exercise` | `sports` |

Ambiguity notes, resolved explicitly rather than left to chance:
- **Activewear** → `apparel` (worn garment; fit dominates), even though "athletic" also matches `sports`. The mapping table is evaluated in the order above, so `apparel` wins.
- **Smart watch / fitness tracker** → `electronics` (compatibility and battery dominate).
- **Yoga mat** → `sports`. **Yoga-branded leggings** → `apparel`.
- **Scented candle** → `home`, not `beauty` (not applied to the body).
- **Electric toothbrush** → `beauty` (personal care; suitability and usage dominate), despite the electronics signal. Recorded here because it is a genuine coin-flip; if eval data shows this is wrong, change it here with a decision record.

Two signals of the same tier mapping to different categories → `uncategorized` (§2 rule 1).

---

## 9. Sources

1. [Shopify/product-taxonomy — GitHub](https://github.com/Shopify/product-taxonomy); [Shopify's Standard Product Taxonomy — Shopify Help Center](https://help.shopify.com/en/manual/products/details/product-category)
2. [Category metafields — Shopify Help Center](https://help.shopify.com/en/manual/custom-data/metafields/category-metafields)
