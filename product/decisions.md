# Decision Record — Shopify Product Intelligence

- **Date opened:** 2026-08-24
- **Status:** V0 specification phase

Format: each decision states the question, what was decided, why, what was rejected, and what it costs. A decision is not final because it is written down — it is **reversible with a superseding record**, except where marked *Load-bearing*, which means reversing it changes what the product is.

Companions: [`PRD.md`](./PRD.md) · [`rubric.md`](./rubric.md) · [`taxonomy.md`](./taxonomy.md)

---

## D-001 — V0 is a local skill, not a Shopify app

**Status:** Accepted

**Question:** Should V0 integrate with Shopify (OAuth, Admin API) so merchants can audit their live catalog?

**Decision:** No. V0 reads a local file and writes local files. Zero network calls, zero Shopify integration, zero auth, zero persistence beyond `reports/`.

**Why:** The hard, unproven part of this product is the *audit quality* — whether category-aware, evidence-bound, non-inventing analysis produces findings a merchant trusts. OAuth, session storage, billing, and webhook plumbing are well-understood work that would consume the majority of build time while proving nothing about that question. If the audit is not trustworthy, no amount of integration saves it. If it is, integration is a known path.

Making zero network calls is also a load-bearing property of the integrity model: a tool that cannot fetch cannot enrich from the web, which forecloses an entire class of fabrication. See D-006.

**Rejected:**
- *Thin Shopify app with a real audit inside* — front-loads the easy risk and defers the hard one.
- *Read-only Admin API access* — still requires OAuth, app review, and hosting, and opens the enrichment door.

**Cost:** The operator must export a CSV manually. Acceptable — the target customer already does this routinely.

---

## D-002 — We do not claim AI ranking, visibility, or citation benefit

**Status:** Accepted · *Load-bearing*

**Question:** The obvious market pitch is "get your products recommended by ChatGPT". Do we make it?

**Decision:** No, and it is prohibited in every artifact the product produces, including report copy. Automated phrase auditing enforces it (PRD §12.3 audit 4).

We claim exactly this: *we evaluate whether product information is sufficiently complete, consistent, structured, and useful for AI-powered product discovery and comparison.*

**Why:** Three reasons, in order of weight.

1. **We cannot know it.** Ranking and citation behavior in third-party AI systems is undisclosed, changing, and not attributable. Any promise would be unfalsifiable at best.
2. **It is the wrong product.** A tool optimizing for an unobservable external ranking has no ground truth and drifts toward gaming. A tool measuring a merchant's own data quality has ground truth in the data itself, which is exactly why our findings can be evidenced.
3. **It destroys the trust position.** Our differentiator is that we never assert what we cannot show. A ranking promise is the first fabrication, made on the cover page.

Shopify's own merchant documentation does direct merchants toward complete, well-structured product data for agentic channels,¹ which supports the *relevance* of data quality. That is a reason to build this, not a licence to promise placement.

**Rejected:** *"AI-visibility score"* framing. Higher initial conversion; incompatible with the core principle.

**Cost:** Harder positioning. The honest pitch is quieter than the dishonest one.

---

## D-003 — Missing information is UNKNOWN and carries no penalty

**Status:** Accepted · *Load-bearing*

**Question:** Should a missing attribute subtract points, or merely fail to earn them?

**Decision:** Fail to earn. `UNKNOWN` scores 0 earned, 0 penalty. Only conflicts (D6) and unsupported claims (D7) subtract. Absence is never rendered as a negative statement about the product.

**Why:** Two separate reasons that happen to agree.

1. **Semantic.** Penalizing absence encodes "absent means bad about the product". It does not. It means we do not know. Once the tool is allowed to treat absence as negative information, absence-as-negation follows in the report copy, and the core principle is gone.
2. **Arithmetic.** With both forfeiture and penalty, a sparse product is punished twice for the same gap and scores implausibly low, which destroys the score's meaning at the bottom of the range.

Conflicts and unsupported claims are different in kind: something *present* is defective. That is a fact about the data, provable from the data, and it earns a penalty.

**Why this matters more than it looks:** this rule is what makes the scoring system safe to publish. It guarantees that the worst thing a gap can do is cost its own points.

**Rejected:** *Small penalty for Tier A absence* — rejected on both grounds above.

**Amendment bar:** Not amendable by a rubric version bump. Requires a superseding decision record ([`rubric.md`](./rubric.md) §9.6).

---

## D-004 — The score is arithmetic, never model output

**Status:** Accepted · *Load-bearing*

**Question:** Should the model assign scores holistically, or should scores be computed?

**Decision:** Computed. The model determines check **status** and gathers **evidence**. Points are fixed per check. The total is arithmetic. No model-generated number enters the score path.

**Why:** Model-assigned scores are non-deterministic, non-auditable, and non-defensible. A merchant asking "why 64?" would receive a rationalization rather than a derivation. Fixed points make the score reproducible by hand, diffable across runs, and legitimately comparable between products — and they make the eval suite meaningful, because a score change means a check outcome changed.

This is the concrete content of "no AI score". It also means score movement is always explainable: some check changed status, and the report names it.

**Rejected:** *Model score with a rubric prompt* — cheaper, unreproducible. *Model-adjusted weights per product* — unauditable tuning surface.

**Cost:** More specification work up front; the rubric must anticipate cases rather than improvise. That is the point.

---

## D-005 — V0 emits questions, not generated copy

**Status:** Accepted · *Load-bearing*

**Question:** Should remediation include suggested description text?

**Decision:** No. V0 generates zero product copy. Remediation is a **question addressed to the merchant**, plus the field it belongs in.

**Why:** Generating copy for a gap requires supplying the missing fact. That is the exact fabrication the product exists to prevent — and it is where every competing "AI product description" tool fails. Writing "made from premium cotton" for a product whose material is unknown is indistinguishable from lying, and in beauty and safety-adjacent categories it is a liability.

Suggesting a *value* is also more dangerous than suggesting nothing, because a merchant under time pressure will accept a plausible suggestion without verifying it. The tool's design must not create that pressure.

**Rejected:** *Templated copy with `[FILL IN]` placeholders* — closer to acceptable, but merchants ship templates with placeholders intact, and it drags us toward a copy tool. *Copy generation from merchant-confirmed facts only* — legitimate, but it is a different product, requiring a confirmation loop V0 does not have. Deferred, not rejected in principle (PRD §14.2).

**Cost:** Less immediately gratifying output. Mitigated by ranking questions by points recoverable, so the merchant always knows where the leverage is.

---

## D-006 — No network access, therefore no external verification

**Status:** Accepted

**Question:** Should the tool fetch referenced certifications, standards, or linked documents to verify claims?

**Decision:** No. V0 makes no network calls. A referenced external source is recorded as `external_reference` evidence, meaning **mentioned in the data** — never fetched, never verified.

**Why:** Fetching would turn "the data references a basis" into "the claim is true", a much stronger assertion requiring judgment about source authority we are not positioned to make. It also opens an enrichment path where fetched content becomes product facts, defeating D-005 and the core principle. And it makes runs non-deterministic, breaking D-004's guarantees.

The distinction the reports must preserve: **referenced ≠ verified**. Every claim-support PASS says a basis is referenced. None says the claim is true.

**Rejected:** *Fetch-and-verify with cached results* — non-determinism, authority judgments, enrichment risk.

**Cost:** We cannot detect a fabricated certification number. Accepted: detecting *unsupported* claims is the valuable and honest 80%.

---

## D-007 — We report data insufficiency, never legal violation

**Status:** Accepted

**Question:** Should the tool flag claims as non-compliant with advertising or labeling regulation?

**Decision:** No. Findings are phrased as *the supplied data does not carry the support this claim implies*. The tool never asserts illegality, non-compliance, or regulatory approval, and never approves a claim as compliant.

**Why:** Compliance is jurisdiction-specific, claim-specific, and fact-specific. We see one product record and no jurisdiction. Asserting a violation would be a legal opinion the tool is unqualified to give and the merchant may act on; asserting compliance would be worse. The data-sufficiency framing is both defensible and more useful — the merchant knows their obligations and needs to know where their record is thin.

**Rejected:** *Jurisdiction-tagged compliance checks* — a different product with different expertise requirements.

**Cost:** Less punchy findings in regulated categories. Correct trade.

---

## D-008 — Five categories, hand-specified, not derived from Shopify's taxonomy

**Status:** Accepted

**Question:** Should we import Shopify's Standard Product Taxonomy (10,000+ categories, ~2,000 attributes, MIT-licensed²) rather than hand-write five?

**Decision:** Five hand-specified categories, with a conservative mapping from Shopify category/type/tag signals ([`taxonomy.md`](./taxonomy.md) §8).

**Why:** Importing the full taxonomy would give breadth without depth. Shopify's attributes describe *what a product is* (a facet vocabulary for classification and filtering); ours describe *what a buyer needs to know to choose it*, with tiers, scopes, inheritance rules, and per-attribute ambiguity definitions. Those are different artifacts, and the second cannot be mechanically derived from the first.

Five categories are enough to prove the thesis — that category-specific attribute sets produce materially better findings than a generic checklist — and few enough to hand-specify at the depth the rubric needs. Depth is what we are testing; breadth is a later scaling problem with a known solution.

**Rejected:** *Import all Shopify categories with generic attribute sets* — reproduces the PIM completeness-report failure mode at scale. *Two categories* — too thin to demonstrate divergence.

**Cost:** Products outside the five are `uncategorized` and get Common Core auditing only, with the limitation stated plainly in the report.

**Note:** Post-V0, Shopify's taxonomy is the right backbone for expansion, and category metafields are the right target for our attribute keys.³ V0 deliberately does not take that dependency yet.

---

## D-009 — Redundancy is not penalized; contradiction is

**Status:** Accepted

**Question:** Should stating the same fact in a metafield and in prose cost points?

**Decision:** No. Exact and near-duplicates are `info` findings, scored once under the canonical key. Only duplicates **with different values** are penalized — and those are not duplicates, they are conflicts, routed to D6.

**Why:** A merchant stating material in a metafield and in the description is serving both a machine and a human. Penalizing that would push merchants toward removing prose that helps buyers. The real risk in dedupe logic is the opposite one: silently merging two values that disagree, which would *hide* a conflict. Hence the explicit ordering rule — check for value disagreement before merging (PRD §9.8).

**Rejected:** *Penalize prose-only attributes* — already handled correctly and proportionately by `STRUCT.ATTRIBUTES_IN_FIELDS`, which rewards structure without punishing prose.

---

## D-010 — Dimension weights are a stated product judgment, reviewed against evals

**Status:** Accepted

**Question:** How were 15/22/15/12/12/10/8/6 chosen, and how do they change?

**Decision:** They are a product judgment, argued in [`rubric.md`](./rubric.md) §2.1, reviewed at each rubric version against eval outcomes. They are not derived from data we do not have.

**Why:** Pretending the weights are empirically derived would be its own small fabrication. Stating them as judgment makes them arguable, which is the only way they improve. The specific shape encodes: category relevance is the differentiator (D2 largest); identity failure invalidates everything downstream (D1 close behind); variant data is where catalogs quietly break and where automation beats manual review most (D3 larger than intuition suggests); defects in what is present are penalties not earnings (D6/D7); and structure must never compensate for emptiness (D8 deliberately small).

**Review trigger:** if eval results show a dimension that never discriminates between good and bad fixtures, its weight or its checks are wrong.

---

## D-011 — Even point splits within a tier

**Status:** Accepted

**Question:** Should individual attributes carry individually tuned weights?

**Decision:** No. Within a tier, points split evenly. Relative importance is expressed **only** by tier placement.

**Why:** Per-attribute weights are an unauditable tuning surface: dozens of numbers, each defensible alone, collectively unexplainable, and irresistible to fiddle with when a score "looks wrong". Tier placement is a single reviewable judgment per attribute that a merchant can also understand ("this is required for this kind of product"). Even splits keep the arithmetic hand-checkable, which D-004 requires.

**Accepted consequence:** the same attribute is worth different points in different categories, because tier populations differ ([`taxonomy.md`](./taxonomy.md) §6). Correct — the point is category relevance, not cross-category point parity. Scores remain comparable at the /100 level.

---

## D-012 — Conflicts cost twice; the tool still picks no winner

**Status:** Accepted

**Question:** When two supplied values conflict, should the tool resolve the conflict, and how should it score?

**Decision:** No resolution — both values cited, no winner asserted, merchant asked. Scoring: the affected D2 attribute earns 0 **and** a D6 penalty applies.

**Why the double cost:** contradictory data is worse than absent data. Absent data makes a buyer ask a question; contradictory data makes them decide, possibly wrongly, and it makes any automated consumer of the catalog wrong with confidence. The score should say so.

**Why no resolution:** picking a winner requires either world knowledge (prohibited by PRD §9.4 — we do not correct merchants about their own products) or a source-priority heuristic. A priority heuristic looks principled and is not: metafields are not reliably more current than descriptions, and a wrong auto-resolution is worse than a flagged conflict because it terminates the merchant's inquiry.

**Rejected:** *Prefer structured over prose* — plausible, unfounded, and it hides the problem it claims to solve.

---

## D-013 — Batch ceiling of 200 products

**Status:** Accepted

**Question:** How many products per run?

**Decision:** 200, with a warning and truncation above that.

**Why:** A scope control, not a technical limit. V0's purpose is audit quality, and quality is evaluated per product. A large-catalog run would shift attention to throughput and reporting ergonomics — real problems, but not V0's. 200 is enough to surface systemic gaps across a real catalog.

**Cost:** Merchants with 3,000 SKUs must sample or batch. Acceptable for V0; systemic gaps show up in the first 200 anyway.

---

## D-014 — Evidence gate is enforced, not advisory

**Status:** Accepted · *Load-bearing*

**Question:** How is "never invent" enforced rather than merely instructed?

**Decision:** Three mechanisms, all mandatory:
1. **Structural:** a finding with an empty `evidence` array is dropped at report assembly and logged as a `run_error`. Emitting a finding without evidence is not possible.
2. **Verificational:** the evidence integrity audit re-derives every `quote` byte-for-byte from the input and independently re-searches every `absence` path list (PRD §12.3).
3. **Adversarial:** the fixture corpus includes inputs designed to bait invention — evocative titles with no facts, famous model numbers, categories that strongly imply attributes, and a description that explicitly asks the tool to fill gaps.

**Why:** An instruction not to hallucinate is a hope. A structural gate is a guarantee. The `absence` evidence type is the load-bearing piece: it forces a claim about *nothing being there* to enumerate where it looked, which makes false gaps — the failure mode that would most quickly destroy merchant trust — detectable by machine.

**Cost:** More output volume, more implementation work. This is the product's core value; it is not optional.

---

## D-015 — Two report artifacts, JSON authoritative

**Status:** Accepted

**Question:** One report or two?

**Decision:** `report.json` (authoritative) and `report.md` (rendered from it). The Markdown may contain no assertion absent from the JSON.

**Why:** The human artifact is what the merchant reads; the machine artifact is what evals, audits, and future integrations consume. Deriving one from the other guarantees they cannot diverge — and divergence is where a careless rendering could smuggle in a claim the JSON never made.

**Cost:** Some duplication. Trivial next to the guarantee.

---

## D-016 — Report questions are ranked by points recoverable, not by severity

**Status:** Accepted

**Question:** What order should merchant questions appear in?

**Decision:** Descending by points recoverable, with `blocker` findings pinned to the top regardless.

**Why:** The merchant's scarce resource is time, and the question they are actually asking is "what do I fix first?". Severity ordering answers a different question and buries a 6-point systemic gap under three 1-point minors that happen to be `major`. Blockers are pinned because a misleading data point is not a scoring matter — it needs to be fixed whether or not it moves the number.

---

## D-017 — Structural assembly of finding text (design note, P4)

**Status:** Proposed — **not implemented, not a current implementation requirement.** Recorded so P2 and P3 do not foreclose it.

**Question:** The fabrication audit detects invented facts by pattern-matching fact-bearing tokens against a hand-built lexicon of materials, units, standards, compatibility terms and claim shapes. Its recall is therefore bounded by that lexicon: an exotic fabricated term — an unusual alloy, a niche interface, a standard nobody listed — can pass stage 2 undetected. Should report text eventually be *constructed* so that fabrication is impossible, rather than *scanned* so that fabrication is usually caught?

**Proposed architecture.** Finding text would no longer be free model-authored prose. Each of `title`, `detail`, and every merchant-facing question would be assembled from four constrained sources:

| Source | Contributes | Constraint |
| --- | --- | --- |
| **Fixed templates** | Sentence frames, one per check outcome | Authored by us, versioned with the rubric, containing no product-specific content |
| **Controlled labels** | Attribute keys, category names, statuses, severities, dimension names | Drawn from a closed vocabulary defined in `taxonomy.md` and `rubric.md` |
| **Evidence excerpts** | Any product-specific string | Verbatim, byte-exact, carrying its own locator |
| **Structured fields** | Counts, points, variant IDs, coverage ratios | Computed arithmetically from the ledger |

A model would still decide *which* template applies and *which* span to quote — that is the recognition work of §9.5, and it remains inference. What it would no longer do is author a sentence containing a product fact.

**The guarantee this buys.** Fabrication moves from *detected* to *structurally impossible*. If the only product-specific text that can enter a report is an evidence excerpt, and every excerpt is verified byte-exact against a resolvable locator, then an untraceable product fact has no route into the artifact. The lexicon-recall gap closes by construction rather than by enumeration, and the fabrication audit becomes a defence-in-depth check on the assembler rather than the sole barrier.

**The cost, stated honestly.**

- **Lower expressive freedom.** Every phrasing a report can produce must be anticipated as a template. Novel situations get an awkward generic frame or no frame at all.
- **Less natural reports.** Templated prose reads as templated. A report that says the same eleven sentences about eleven products is more monotonous than one written for each — and monotony has a real cost, because a report nobody reads carefully is a report whose findings do not get acted on.
- **Template maintenance becomes a real surface.** Templates need versioning, review, and their own eval coverage; a badly worded template is now a systematic defect across every report rather than a one-off.
- **Some legitimate output gets harder.** Explaining an unusual conflict, or the precise axis of an ambiguity, is exactly where free prose earns its keep.

**Why it is not being decided now.** The trade is between a guarantee and readability, and we do not yet know how much readability costs us in practice — that needs real reports and real merchant reaction (Q-4). Deciding now would be choosing under exactly the kind of uncertainty this repo asks us to name rather than resolve by guessing.

**Constraint this places on P2/P3:** do not build anything that makes structural assembly impossible later. Concretely: keep every finding's product-specific content attributable to an evidence item, and do not let checks accumulate product facts in prose that has no corresponding evidence entry. That discipline is required by PRD §8.3 regardless, so this note asks for nothing new — only that it not be quietly eroded.

**Revisit when:** V0 has produced reports over the full fixture corpus and either (a) the fabrication audit misses a fabrication a human reviewer catches, or (b) merchant feedback shows the trust cost of free prose exceeds its readability benefit.

---

## Open questions

Deliberately unresolved. Each is recorded so V0 does not foreclose it, and none blocks V0.

| # | Question | Why deferred | What would resolve it |
| --- | --- | --- | --- |
| Q-1 | How are multi-language / multi-locale catalogs audited? Is a translated description a separate product record? | No locale fixtures; V0 assumes single-locale input. | Merchant interviews + a locale fixture set. |
| Q-2 | How do market-specific prices and availability affect D5? | Requires market context V0 has no access to. | Post-integration data. |
| Q-3 | Bundles, kits, and Shopify combined listings — one record or several? | Structurally distinct; would need its own attribute logic. | Primary Shopify documentation review + real bundle fixtures. |
| Q-4 | Should the merchant see a raw score or a banded grade only? Does a number invite gaming? | Needs real merchant reaction. | User testing on V0 reports. |
| Q-5 | Is 200 the right batch ceiling, and how should catalog-level systemic reporting work at 3,000 SKUs? | Depends on whether merchants act per-product or per-pattern. | Observation of V0 usage. |
| Q-6 | Should `uncategorized` products get an expanded Common Core so their scores are less deflated? | Risks encouraging bad category hygiene, which is itself a real finding. | Eval data on how often `uncategorized` occurs in real exports. |
| Q-7 | How should the tool treat merchant data that is stale rather than absent (a spec that no longer matches the shipped product)? | Undetectable without external state; possibly permanently out of scope. | Whether merchants report this as a felt problem. |
| Q-8 | Post-V0: do attribute keys map onto Shopify category metafields, and does that change tiering? | Requires taxonomy dependency V0 avoids (D-008). | Shopify taxonomy review at integration time. |

---

## Sources

1. [Shopify Catalog and product discovery for agentic storefronts — Shopify Help Center](https://help.shopify.com/en/manual/online-sales-channels/agentic-storefronts/products)
2. [Shopify/product-taxonomy — GitHub](https://github.com/Shopify/product-taxonomy)
3. [Category metafields — Shopify Help Center](https://help.shopify.com/en/manual/custom-data/metafields/category-metafields)
