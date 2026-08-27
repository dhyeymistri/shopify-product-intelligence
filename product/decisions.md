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

## D-018 — A product-level value earns nothing for a variant-scoped requirement

**Status:** Accepted. Implemented in P3.1 (`engine/checks.unresolved_scope`).

**Question:** `taxonomy.md` §4.3 marks some attributes non-inheritable — `garment_measurements`, `net_content`, `color_finish`, `user_fit_specification`, `assembled_dimensions` — meaning a product-scope value does not satisfy the requirement for any variant. What does a check earn when the merchant states one of these once, for the product, on a multi-variant product?

**Decision: zero earned points, status `PARTIAL`, with the supplied value quoted.**

The points follow `rubric.md` §3.1's own coverage arithmetic. A coverage check earns `max × (covered / total)`; a product-scope value covers no variant of a non-inheritable attribute, so `covered` is 0 and the product earns 0. Nothing new is invented to reach that figure — it is the existing formula evaluated at the boundary.

**Rejected: half credit** (`max × partial_credit`), which is what P3.1 originally implemented. Half credit reads the case as PRD §9.3 ambiguity — a value present but not fully resolved — and there is a real argument for it, since `taxonomy.md` §5.1 does call an unmapped size chart `PARTIAL`. It was rejected because it pays for per-variant data the record does not hold. These attributes are non-inheritable *precisely* to stop a merchant appearing to have per-variant data they do not have (§4.3), and awarding points for the appearance re-creates the thing the rule exists to prevent. Where a reading is genuinely open, the one that awards fewer points for less information is the one consistent with D-003.

**Rejected: `UNKNOWN`.** This is the conservative-looking answer and it is wrong, for a mechanical reason worth recording. The value *was* found, at a path the check declares it searched. Reporting it as absent is a false gap — PRD §8.3 rule 5 calls that a false negative of `blocker` severity, and the fabrication audit catches it as `FAB012_FALSE_GAP` on exactly this shape. `rubric.md` §3.1 also defines `UNKNOWN` as *"not found in any `checked_paths`"*, which is not what happened. `PARTIAL` at zero is the only status that reports the truth — something is there, and it does not answer the question — while still earning nothing.

**Consequence:** the merchant sees the value they supplied, quoted at its locator, alongside the named variants it does not cover, and a question asking for the per-variant values. They are not told their data is missing, and they are not paid for data that is not there.

---

## D-019 — A check that cannot read prose says nothing, and never says "absent"

**Status:** Accepted. Implemented in P3.1 (`engine/checks`, `FindingLedger.defer`).

**Question:** Most attributes can be stated in a product description. Recognizing them there is language recognition, permitted by PRD §9.5 rule 2 over a quoted span, and it is not implemented yet. What does a check do when it has searched its declared paths, found no structured value, and found free text it cannot read?

**Decision:** it emits **no finding at all**, and records the check as deferred internally.

Three things follow, and all three are the point:

1. **It does not infer the fact.** No value is supplied, guessed, or carried over from category norms. That is AGENTS.md §2, and no phase of this project may weaken it.
2. **It does not report the attribute as absent.** A description that has not been read may well state the attribute. Claiming a gap there is a false gap — PRD §8.3 rule 5, `blocker` severity — and it is the failure most likely to make a merchant distrust the whole report, because they can see the sentence the tool says is not there.
3. **It does not penalize the product.** A deferred check produces no `UNKNOWN`, no `unknowns[]` row, no question, and no penalty. Nothing about it reaches merchant-facing output.

**Where absence is still decided:** everywhere the search is complete. If the description is empty and no structured value exists, nothing was found anywhere the check looked, and `UNKNOWN` is correct and is emitted with its `checked_paths`. Deferral is not a blanket suppression of absence; it is confined to the case where something unread is present.

**The cost, stated plainly.** Under-recognition deflates a score. A product whose material is stated only in prose earns nothing for it until recognizers exist. This is the acceptable direction of failure and the only one available: an under-credited product carries honest evidence and a recoverable score, while a guess in either direction states something false about a product. The bound is recall, and recall is a lexicon problem that later phases fix by construction — it is not a correctness problem.

**Not a licence to add a model.** V0 adds no LLM and no network call (D-001, D-006). The interface that would close the gap is a span recognizer owned by the check and versioned with `rubric.md`, exactly as PRD §9.6 already authorizes.

**Revisit when:** the recognition phase lands. Deferral should then shrink to the residue no lexicon covers, and that residue should be measured rather than assumed.

---

## D-020 — Confidence is fixed per check, with two declared determination arms

**Status:** Accepted. Supersedes open question Q-9. Implemented in P3.1 (`engine/registry.ConfidenceRule`).

**Question:** `rubric.md` §3's example record fixes `confidence` as a single scalar per check. PRD §7.5 assigns `high` to a structural presence/absence determination and `medium` to bounded recognition over a quoted span — and the honest report double `honest-adv-02-helmet.report.json` carries `high` on a D2 absence, which a single `medium` scalar cannot produce. Which governs?

**Decision:** a check declares **two arms**, both fixed by its definition: `recognized`, which is the confidence `rubric.md` §4 states for the check, and `structural`, which applies when the finding was reached by presence, absence, exact comparison, uniqueness or arithmetic. Which arm applies is a fact about how the finding was determined, not a runtime judgment, so PRD §7.5 rule 3 holds.

**The structural arm never exceeds the check's stated confidence, and a `low` check stays `low` everywhere.** This is the part that matters. `medium` describes the *method* — reading a span — so a check that reached its conclusion without reading anything may legitimately report `high`. `low` describes the *subject matter*: it marks a judgment a reasonable reviewer could dispute, such as whether a use case is specific enough or whether two attributes mean the same thing. Structural certainty about where the tool looked does not make that judgment less disputable. Promoting `USECASE.DIFFERENTIATION` to `high` on its absence path would detach PRD §7.5 rule 2's guardrail — *low confidence never penalizes and never exceeds `minor`* — from the check on the path it most often takes. The guardrail is not amendable that way, so the arm is capped instead. Asserted at registry import.

**Rejected: a single scalar per check.** It cannot express both the honest double's `high` D2 absence and `rubric.md` §4's `medium` D2 column without one of the two being wrong.

**Rejected: `high` on every structural path.** This is what P3.1 shipped first, and it made `USECASE.DIFFERENTIATION` report `high`. It reads as the tool being more certain about an interpretive question than it is, in the one place the specification asks it to be least certain.

**Follow-up owed to the specification:** `rubric.md` §3's example record still shows one scalar. It should show both arms. That is a documentation correction, not a scoring change, and it does not bump `rubric_version`.

---

## D-021 — Variant coverage counts a variant only when its value satisfies the check

**Status:** Accepted, by the project owner, on the strict reading. Implemented in P3.2 (`engine/checks._variant_coverage`).

**Question:** [`rubric.md`](./rubric.md) §3.1 scores a coverage check at `max × (covered/total)`, and an ambiguity at `max × partial_credit`. Once recognition predicates exist, a non-inheritable variant-scope attribute can produce a **mixed** set: some variants carry a value the predicate finds satisfying, others carry a value it finds merely ambiguous. Neither formula covers that case, and the rubric defines no composition of the two.

**Decision — the strict reading:**

```
coverage = satisfied_variants / total_variants
```

Four rules follow from it, and all four are binding:

1. **A variant counts as covered only when its own value satisfies the check.** A value the predicate finds ambiguous does not count toward `covered`.
2. **A product-scope value is never variant coverage.** `taxonomy.md` §4.3 and D-018 already say so; this decision does not create an exception for a value that happens to satisfy the predicate. D-018's `PARTIAL` at zero earned is unchanged and takes precedence.
3. **An ambiguous value is not weighted as partial coverage.** `rubric.md` §3.1's two clauses are alternatives, not terms to be summed, and no authoritative rule composes them. Weighting would need a rule the rubric does not contain.
4. **Uncovered variants are preserved explicitly** — named individually, never "some variants" (PRD §9.7). A variant uncovered *because its value is ambiguous* is named with its value quoted at its own locator, not reported as empty: the value is there, and reporting it as a gap would be the false negative PRD §8.3 rule 5 calls blocker-severity.

**The governing property: less information may never earn more than more complete variant coverage.** Every candidate rule was tested against it. Strict coverage satisfies it by construction — adding a satisfying value can only raise `satisfied`, and no other input can raise the score at all.

**Rejected: weighted coverage** — `max × (satisfied + partial_credit × ambiguous) / total`. It composes both §3.1 clauses and is the most arithmetically natural reading, which is why it needed deciding rather than deriving. It was rejected because the composition is not in the rubric: choosing it would mean writing a new scoring rule inside a predicate, where it could not be read off `rubric.md` by a reviewer with a calculator (§1.1, *"Reproducible by hand"*). Where a reading is genuinely open, D-018 has already recorded the tie-break — the one that awards fewer points for less information is the one consistent with D-003.

**Rejected: presence coverage** — counting every variant that carries any non-placeholder value. This is what P3.1 does for `VALUE_PRESENT` attributes, where no predicate exists to say more. It is wrong here for a specific reason: it would pay full coverage credit for a value the tool has *just determined* to be ambiguous, contradicting §3.1's own `PARTIAL` row and violating the governing property above.

**A verdict the predicate could not reach is not a verdict against the variant.** Where any covered variant's value is `UNDECIDED`, the check defers entirely and emits nothing (D-019). Counting that variant as uncovered would assert its value fails to satisfy the check, which is exactly what the predicate declined to say; naming it as empty would be a false gap. The whole check staying silent forfeits points the record may deserve, and that is the permitted direction of failure.

**Consequence:** the merchant sees which variants carry a satisfying value, which carry an ambiguous one — quoted — and which carry none, with the check's question. They are never told a variant is empty when it is not, and never paid for per-variant data the record does not hold.

---

## D-022 — Recognition lexicons live in one versioned module, owned by their checks

**Status:** Accepted. Derived from PRD §9.6 and AGENTS.md §7; no new product judgment. No code yet — no lexicon exists until the first predicate lands.

**Question:** PRD §9.6 says *"a recognition lexicon, when one is written, belongs to the check that uses it and is versioned with `rubric.md`."* Where do the phrase sets, unit vocabulary, size-standard prefixes and performance tiers actually live, and what does adding an entry require?

**Decision, in three parts.**

1. **One module, `engine/lexicon.py`**, carrying one named immutable set per check that uses one, each named for its owning `check_id`. *"Belongs to the check"* is a statement about authority, not about file layout: no layer may read a set it does not own, and the normalizer reads none of them (PRD §6.1 — recognition performed in the input layer would be unlabelled, unevidenced and unscored). One module is also what makes the no-leak assertion below possible at all: an audit cannot enumerate a vocabulary scattered across nine call sites.
2. **`LEXICON_VERSION` is asserted equal to `rubric_data.RUBRIC_VERSION` at import.** *"Versioned with `rubric.md`"* is not decoration: an entry decides a status, a status decides earned points, so a lexicon is a scoring artifact. The assertion turns drift into a load failure instead of a silent scoring change.
3. **Adding, removing or editing an entry is a scoring-semantics change.** It bumps `rubric_version` (D-023), updates every affected expectation file in the same commit, and names the entry in the commit message. It needs no new decision record unless it changes the *shape* of what the set recognizes.

**No lexicon entry may be a product value.** Entries are the vocabulary of ambiguity, of units and of standards — never a fact about a product, and never a string the tool could emit as though the merchant had stated it. Asserted twice: at import, the way `evals/audits/factlex.assert_allowlist_has_no_values()` already asserts it for the audit's own allowlist; and over the corpus, where no lexicon string may appear in any `title`, `detail`, `question` or evidence `note` in any report. That is the one way this module could fail open.

**Rejected: a lexicon per check module.** Ownership reads more directly, but the version assertion and the no-leak invariant would each have to be repeated per module, and an invariant that is repeated by hand is the failure mode this decision exists to prevent.

**Rejected: no lexicon at all — literals at the call site.** This is how a phrase set grows by accretion until nobody reviews it, and it puts scoring-relevant vocabulary outside the version that `rubric.md` §1.1 promises determines the score.

---

## D-023 — Implementing a recognition predicate bumps `rubric_version`

**Status:** Accepted. Derived from `rubric.md` §1.1 and PRD §12.5. No bump accompanies this record: the preconditions it was written for move no score.

**Question:** the recognition phase implements predicates the rubric already names. No point allocation changes and no table in `rubric.md` is edited — but statuses move from deferred to `PASS`/`PARTIAL`, so scores move. Does that bump `rubric_version`?

**Decision: yes. Every commit that can move a fixture score bumps it.**

`rubric.md` §1.1 states determinism as *"Same input + same rubric version → identical score."* Unconditionally. Two engine builds that both report `rubric_version: 0.1` and score the same fixture differently falsify that sentence — and it is the sentence the report's reproducibility rests on, because a reviewer with the report and a calculator (§1.1, *"Reproducible by hand"*) has no other handle on which rules produced the number. PRD §12.5 agrees from the other direction: a change that *"alters scoring semantics"* requires a decision record and a `rubric_version` bump, and deciding that a supplied value satisfies a check is scoring semantics whether that decision is written in `rubric.md` or in a predicate.

The bump therefore carries its usual companions (AGENTS.md §7): every affected expectation file updated in the same commit, and the moved fixtures named in the commit message. A behaviour-neutral refactor bumps nothing.

**Rejected: no bump, because point allocations are untouched.** This reads `rubric_version` as versioning the *document*. §1.1 defines it as versioning the *scoring function*. The document reading is cheaper by exactly one line per slice and it breaks the only invariant that makes a reported score checkable after the fact.

**Consequence:** each independently shippable recognition slice is a score-moving commit and carries a bump; `rubric.md`'s version header moves with it, while the checks, points, severities and confidences it states do not.

**Scope, settled later by D-032.** This record was written about a recognition predicate, and the question of whether *"can move a fixture score"* also reaches a **conformance repair** — one that moves scores only by restoring a rule the specification already fixed — was left open as Q-18. D-032 answers it: yes, mechanically, and fixture/data corrections are governed identically to engine corrections. The exemption in the paragraph above is neutral with respect to **reported output**, not with respect to intent.

---

## D-024 — `IDENT.TITLE_DISTINGUISHING` counts only the five kinds the rubric names

**Status:** Accepted. Implemented in P3.2 (`engine/lexicon.IDENT_TITLE_DISTINGUISHING_KEYS`, `engine/checks.check_title_distinguishing`). Score-moving; `rubric_version` bumped with it (D-023).

**Question:** [`rubric.md`](./rubric.md) §4/D1 fixes this check's `PASS` as *"Title carries at least one distinguishing attribute (material, size, model, capacity, count)."* The first implementation matched the title against **any** supplied value at any attribute, metafield or option. Which governs?

**Decision: the rubric. The parenthesis is a closed list, not an illustration.**

The check now considers only values held at a taxonomy attribute key that *is* one of those five kinds, transcribed once:

| Kind | Attribute keys |
| --- | --- |
| material | `material_composition`, `materials_and_finish`, `materials_and_construction` |
| size | `size_system`, `assembled_dimensions`, `physical_dimensions_weight`, `dimensions_and_weight`, `packaged_dimensions_weight` |
| model | `model_identifier`, `product_identifier` |
| capacity | `capacity_or_load`, `load_or_capacity_rating`, `net_content` |
| count | *(no taxonomy key is a count; the kind is reachable only once one exists)* |

**Rejected: amend `rubric.md` to match the implementation.** This was the cheaper repair and it is the wrong direction. `rubric.md` is authoritative for scoring (AGENTS.md §3), the enumeration is specific enough to be deliberate, and widening it would have been a scoring change made to accommodate code rather than the other way round.

**What the old behaviour actually did, stated because it is the argument.** On the recognition fixture `rec-02` the engine reported the same supplied value twice and incompatibly: `intended_use_context = "Everyday"` earned a `PARTIAL` for being too vague to answer its own check, and simultaneously earned this check its full 2.00 for being *distinguishing*. A value cannot be both. On `rec-06` the check passed on `in_the_box`. Neither key is material, size, model, capacity or count.

**Option values are excluded, and that is a second narrowing.** An option named `Size` carrying `Large` is a size, but deciding that an option *name* denotes one of the five kinds needs a vocabulary of option names, and that vocabulary would be a new scoring artifact (D-022). Under-detection is the permitted direction, so the check reads attributes only until such a vocabulary is decided on its own merits.

**Borderline keys held out, named so the choice is reviewable:** `garment_measurements` and `user_fit_specification` are fit measurements rather than a size, and `color_finish` is a colour, which the rubric does not list. Each was excluded because it is arguable, not because it is clearly wrong.

---

## D-025 — Where every variant carries a value, coverage never falls below the ambiguity credit

**Status:** Accepted. Extends D-021. Implemented in P3.2 (`engine/checks.coverage`). Score-moving.

**Question:** D-021 decided coverage over a **mixed** set — some variants satisfying, some ambiguous. It did not decide the **uniform** case: every variant carries a value and every one of those values is merely ambiguous. Read literally, D-021 rule 1 gives `satisfied / total = 0`. But `rubric.md` §3.1 states two clauses for `PARTIAL`, and the uniform case is plainly the *first* one — a value is present and ambiguous — which earns `max × partial_credit`.

**The asymmetry that forced the question.** `APPAREL.MATERIAL_COMPOSITION` stating `"Cotton blend"` at product scope earns 1.65 of 3.30. `BEAUTY.COLOR_SHADE` stating a shade code on *every* variant earned 0.00 of 1.32. Same taxonomy shape — a "PARTIAL if" cell matched exactly — and a different answer purely because one key is variant-scope. Nothing in `rubric.md` justifies that difference.

**Decision: when every variant carries a value, the check earns `max × max(satisfied/total, partial_credit)`.**

`rubric.md` §3.1's ambiguity clause acts as a **floor** under the coverage clause; the check takes whichever of the two clauses the data supports, and never less than the ambiguity credit once something is present for every variant. Where any variant carries no value at all, the floor does not apply and strict coverage stands unchanged.

**Rejected: `max × partial_credit` for the uniform case alone.** This is the literal reading of the question and it breaks D-021's own governing property. With three variants, one satisfying and two ambiguous earns `max × 1/3 = 0.333`, while *nothing* satisfying and three ambiguous would earn `max × 0.5`. Less information would earn strictly more. The floor formulation is the smallest change that answers the question without creating that inversion.

**This is not the weighted reading D-021 rejected.** No ambiguous variant is ever added to the numerator: `satisfied / total` is computed exactly as before, and the floor is a separate clause of `rubric.md` §3.1 rather than a re-weighting of coverage. The two readings agree everywhere the floor does not bind.

**The governing property still holds, restated:** less information never earns *more* than more complete variant coverage. It can now earn the *same* — one satisfying and two ambiguous ties with three ambiguous, at the floor. A tie is not an inversion, and the alternative was either the inversion above or the unexplained asymmetry the decision opened with.

---

## D-026 — A recognition-derived finding never reports `high` confidence

**Status:** Accepted. Amends D-020. Implemented in P3.2 (`engine/registry.ConfidenceRule.recognition_arm`, asserted at import).

**Question — a conflict between two authoritative documents, recorded here rather than resolved by whichever one the code happened to read.**

- [`PRD.md`](./PRD.md) §9.5, last line: *"Every inference-derived finding carries `confidence` of `medium` or `low` and is marked in the Markdown report with an explicit *(interpreted)* tag."*
- [`rubric.md`](./rubric.md) §4/D5 fixes `TRUST.WARRANTY_OR_GUARANTEE` at **`high`**.

Under P3.1 the two never met: that check could only ever conclude structurally. P3.2 gave it a recognition predicate, so it now reaches `PASS` by reading a supplied value — at `high`.

**Decision: PRD §9.5 governs the recognition path. The `recognized` arm is capped at `medium`.**

AGENTS.md §3 makes `rubric.md` win over `PRD.md` *"on scoring specifics"*. Confidence is not a scoring specific: it enters no arithmetic, subtracts nothing, and PRD §7.5 — not `rubric.md` — is where confidence semantics are defined. §9.5's rule is a statement about what the tool may claim to know when it has performed inference, and it is unconditional. `rubric.md` §4's column states the check's confidence ceiling; §9.5 states the recognition path's ceiling; the finding takes the lower.

**`rubric.md` §4/D5's `high` is not overridden, and that distinction matters.** It remains the confidence of the check's *structural* arm — presence, absence, conflict — which is how that check reaches almost every conclusion it reaches. Only the recognition path is capped. D-020's rule that the structural arm never exceeds the check's stated confidence is unchanged and still checked against the rubric's figure.

**`confidence_arm` is serialized, as `determination`.** PRD §9.5 requires an *(interpreted)* tag in the Markdown report, and P4 cannot render one from a field that does not exist. Deriving it from the confidence value alone is not sound: a `low`-confidence check reports `low` on both arms (D-020), so `low` cannot distinguish them. The finding object therefore carries `determination: "structural" | "recognized"`, classified as a structural enum by the report-field audit. **This adds one field to PRD §7.3's finding object**, which is a specification change owed to `PRD.md` and recorded here rather than made silently.

**Rejected: leave `high` and treat §9.5 as being about model inference only.** A deterministic shape test is still the tool deciding what a supplied value means, and P3.2 has consistently called that recognition — it selects the `recognized` arm and it is why `USECASE.DIFFERENTIATION` stays `low`. Exempting the one check where the cap costs something would make the category a convenience rather than a rule.

---

## D-027 — `unnamed_eco_claim` is deferred until its D7 route exists

**Status:** Accepted. The predicate is written and **not registered** (`engine/recognize.py`). Score-moving: it removes credit P3.2 briefly awarded.

**Question:** [`taxonomy.md`](./taxonomy.md) §5.1's `sustainability_credentials` row states its `PARTIAL` condition as *'Unnamed "eco-friendly" → **routes to D7 as unsupported**'*. P3.2 implemented the recognition half and awarded `max × partial_credit`; claim recognition, and therefore the D7 route, remains deferred. Is half of that cell a legitimate partial implementation?

**Decision: no. The predicate stays deferred until the D7 route it names exists.**

The cell describes one behaviour with two effects, and the two do not point the same way: the `PARTIAL` **awards** 0.37 while the D7 route **subtracts**. Shipping only the awarding half does not under-detect — it moves the score in the direction the taxonomy says is wrong, on precisely the value the taxonomy singles out as an unsupported claim. Every other deferral in this phase costs the merchant points they might deserve; this one would have paid them for a claim the specification says needs support it does not have.

**Rejected: award the `PARTIAL` and record the D7 half as owed.** This was the P3.2 plan's position and it is defensible for a predicate whose two halves are independent. These halves are not: the same phrase triggers both.

**Revisit when:** claim recognition lands and `CLAIM.UNSUPPORTED_CERTIFICATION` can fire. The predicate and its phrase set stay in the codebase, unregistered, so the pair can ship together.

---

## D-028 — Two predicate semantics that are scoring rules, not implementation details

**Status:** Accepted. Recording existing P3.2 behaviour; no code changed by this record.

Both were written only in docstrings. Anything that decides what a check earns belongs here, whatever file it happens to live in.

**1. `ELEC.IN_THE_BOX` has no deferral path.** `enumerated_contents` and `contents_unenumerated` partition every non-empty value: two or more delimiter-separated segments earn the full 1.65, exactly one earns 0.825. There is no `UNDECIDED` arm, so the check never stays silent once a value is stated.

This is defensible — enumeration is a structural property of the string, not a judgment about what the items are — but it has a consequence worth stating: **a single-item box that is completely and correctly stated can only reach `PARTIAL`.** The tool cannot tell that case from an unenumerated summary such as `"accessories included"` (`taxonomy.md`'s own example), and it resolves the ambiguity against the merchant. That is the permitted direction of failure, and it is the only predicate in the phase that cannot abstain.

**2. The strongest verdict across candidates decides the check.** Where a check gathers several supplied values, each is evaluated and the strongest verdict wins, with the finding citing the value that produced it. More information may not earn less than less.

This is narrower than it sounds. Every D2 attribute check carries `conflict_routing`, so two *differing* values about the same subject become a D6 conflict before any predicate runs. The rule therefore only reaches values about *different* subjects — most often an inheritable attribute stated once for the product and once on a variant. In that case a satisfying variant value decides a product-scope check, and the finding's `scope_level` follows the value that decided it rather than the check's declared scope.

---

## D-029 — `VARIANT.ATTRIBUTE_COVERAGE` is `NOT_APPLICABLE` where the category requires nothing per variant

**Status:** Accepted, by the project owner. Resolves Q-17. Implemented in P3.2 slice D (`engine/rubric_data.NA_EMPTY_VARIANT_SCOPE_SET`, `engine/runner._na_reason`). Score-moving; `rubric_version` bumped to `0.4` with it (D-023).

**Question:** [`rubric.md`](./rubric.md) §4/D3 fixes this check's `PASS` as *"Every non-inheritable variant-scope attribute **for the category** is present on every variant."* What does it do when that attribute set — call it `K` — is empty? §4/D3 gives no rule. Q-17 asked for the two ways `K` can be empty to be decided separately, and they are.

**One status is eliminated by authority before the question is reached.** `rubric.md` §3.1 defines `UNKNOWN` as *"Not found in any `checked_paths`."* With `K` empty, `variants[*].attributes` may be fully populated and nothing was "not found". `UNKNOWN` would misdescribe the record whichever way the rest is decided, so the live alternatives are `NOT_APPLICABLE`, deferral, and a vacuous `PASS`. The third is rejected below rather than passed over, because it is the one reading that moves earned points.

**Decision: `NOT_APPLICABLE` in both cases, with a distinct reason string for each.** The check leaves the numerator and the denominator, and §6.3 renormalization follows.

**Case 1 — an assigned category whose `K` is empty.** Purely structural. `K` is empty as a fact about [`taxonomy.md`](./taxonomy.md) §5, fully determined from the taxonomy alone, with nothing missing from the merchant's record. PRD §10.3's prohibition — *"A check is never N/A because the information is missing"* — has no purchase on it: no information is missing. This is `taxonomy.md` §4.4's structural trigger in its plainest form.

*Currently unreachable, and stated anyway.* Every one of the five categories holds at least two non-inheritable variant-scope attributes (`apparel` 3, `beauty` 3, `electronics` 3, `home` 2, `sports` 2), so this branch moves no score today. It is written because the alternative is an unwritten branch that decides a score the first time a taxonomy edit reaches it.

**Case 2 — `uncategorized`.** `K` is empty because the record carries no category, and that *is* traceable to missing merchant data. This is the harder half and it is decided on an existing precedent rather than on a fresh judgment: `rubric.md` §4/D2 and `taxonomy.md` §2 rule 3 already settle the identical question one dimension over — for `uncategorized`, *"D2 is removed in full: its maximum is 0 and it leaves both the numerator and the denominator."* Twenty-two points of category-derived scoring are removed for exactly this reason. Retaining 3.0 points of D3 for the same missing field, in the same report, would be an inconsistency with no rule behind it.

**Engaging PRD §10.3 directly, because this case is what it warns about.** What is removed here is not a gap in the merchant's variant data — it is a requirement that was never posed. `rubric.md` §4/D3 conditions the requirement on the category (*"for the category"*), and with no category there is no set of attributes the variants could have failed to carry. Scoring 0 of 3.0 would charge the merchant for failing a test the rubric never wrote. The missing category itself is charged, once, where the rubric puts it: `IDENT.PRODUCT_TYPE_OR_CATEGORY` at 2.5 with `UNKNOWN` → `major`, plus `taxonomy.md` §2 rule 4's `minor` finding recommending the category be set. The merchant is told, and told once.

**Renormalization consequences, stated rather than left to be discovered.**

- The check's `max_points` leaves `max_applicable` (`checks.not_applicable` emits `max_points = 0`), so D3's applicable maximum falls from 15.0 to 12.0 for an affected multi-variant product, and the reported total is renormalized to 100 by `rubric.md` §6.3 with the factor printed.
- **The effect is not a uniform gain, and the baseline for that claim is stated because the two available baselines disagree.** Renormalization redistributes weight across the checks that remain, so removing a check with maximum `m` and earned `x` from `raw_earned/raw_max` = `E/M` is favourable exactly when `x/m < E/M`.
  - *Against the rejected deferral option*, the gain **is** uniform. Under deferral the check emits nothing and `x = 0` always, so removal is favourable for every affected product with `E > 0`, and neutral at `E = 0`. Nothing about this baseline can make removal unfavourable.
  - *Against the counterfactual where the product carries a category*, the gain is **not** uniform, and this is the baseline the sentence is about. There the check runs and `x` can be anything from 0 to 3.0: for a product that would have earned 0 of 3.0, removal is favourable; for one that would have earned the full 3.0, it is not.
  - The same split governs D2's 22 points, and the aggregate consequence of both removals together is **Q-6a**, below.
- On a **single-variant** product nothing changes: `NA_SINGLE_VARIANT` already removes this check, and the two triggers agree.
- The aggregate question — whether `uncategorized` products end up deflated or flattered once D2's 22 points and this 3.0 are both removed — is **Q-6a**, and this record does not answer it. It is a diagnostic question about the existing scoring function, not a policy choice, and it is answerable only once a score is actually computed. What this record fixes is that the two removals are decided the same way for the same reason. The separate question of whether to *change* the scoring function in response — an expanded Common Core for `uncategorized` — is **Q-6b**, and this record does not reach that either.

**Rejected: `PASS` at the full 3.0, on the ground that an empty requirement is vacuously met.** `K = ∅` does **not** vacuously satisfy `rubric.md` §4/D3, and that is decided here rather than left to the guard in `checks.check_variant_attribute_coverage` that happens to enforce it. The reading is not frivolous: under D-030 a variant is covered when every key in `K` is present on it, and every variant trivially satisfies that over an empty `K`, so `covered/total` = `N/N` and the coverage clause of `rubric.md` §3.1 would award full credit. It is rejected because the arithmetic is only reached once the check is established as applicable, and §4/D3's `PASS` asserts something — that the record resolves per variant — which a product with no per-variant requirement has not demonstrated and could not have. Paying 3.0 for it would credit a merchant for satisfying a test the rubric never wrote, which is the mirror of the error PRD §10.3 names, and on `uncategorized` it would pay for the missing category rather than charge it once as §4/D2 does. Applicability is decided in `runner._na_reason` and never inside a check (`taxonomy.md` §4.4), so the `if not keys: return []` guard in `engine/checks.py` is a backstop for a caller that bypasses the runner, not the rule; the rule is this paragraph.

**Rejected: deferral (the check emits nothing, keeps 3.0 in the denominator, earns 0).** Defensible, and it is the reading PRD §10.3 argues for if "missing" is followed one indirection back to the absent category. It was rejected because it makes the two removals inconsistent for the same missing field, and because a silent 0 of 3.0 tells the merchant nothing — the `NOT_APPLICABLE` finding states the reason where they can read it. Note that this option and `NOT_APPLICABLE` earn exactly 0.00; the disagreement between *these two* is about the denominator and about what the report says, not about earned points. The vacuous `PASS` rejected above is the only reading that moves earned points, which is why it is rejected on its own grounds and not folded in here.

**Rejected: `UNKNOWN`.** Eliminated above by `rubric.md` §3.1's own definition, not by preference.

---

## D-030 — `VARIANT.ATTRIBUTE_COVERAGE` counts presence, not satisfaction

**Status:** Accepted, by the project owner. Scopes D-021. Implemented in P3.2 slice D (`engine/checks.check_variant_attribute_coverage`). Score-moving; `rubric_version` bumped to `0.4` with it (D-023).

**Question:** D-021 fixed variant coverage for a **D2 attribute check** as `satisfied / total`, counting a variant only when its value satisfies that attribute's own recognition predicate. `VARIANT.ATTRIBUTE_COVERAGE` is a **D3** check that also scores coverage over the same attributes. Does it count a variant when the key is present, or only when the value satisfies the key's predicate?

**Decision: presence.** A variant is covered when **every** attribute key in `K` — the category's non-inheritable variant-scope set — carries a stated, non-placeholder, variant-scoped value on that variant. The attribute's recognition predicate is **not run**.

**`rubric.md` §4/D3 fixes it in one word.** *"Every non-inheritable variant-scope attribute for the category is **present** on every variant."* AGENTS.md §3 makes `rubric.md` authoritative on scoring specifics, and D-024 has already settled the shape of this disagreement once — implementation broader than the rubric's own words, resolved *toward the rubric*, with *"amend `rubric.md` to match the implementation"* rejected as the cheaper repair in the wrong direction. The check's registry question agrees: *"Which variant-scope attribute values apply to each variant?"* asks whether the record resolves per variant, not whether the values are good.

**D-021 is scoped to predicate-bearing attribute checks, and stays there.** Its question is stated over *"a value **the predicate** finds satisfying"*; its rule 2 cites `taxonomy.md` §4.3 and D-018, both attribute-scoping rules; it is implemented in `engine/checks._variant_coverage`, reached only from the D2 attribute path. `VARIANT.ATTRIBUTE_COVERAGE` declares no value predicate — `variant_scope_attributes_covered` is the check's coverage arithmetic, not a property of any supplied value.

**What is preserved unchanged.**

- **D-018 / D-021 rule 2** — a product-scope value is never variant coverage. Only candidates at `scope == "variant"` with a variant `ref` are counted, whatever the value says.
- **D-021 rule 4** — uncovered variants are named individually, never *"some variants"* (PRD §9.7). The absence evidence names each uncovered variant **and the keys missing on it**, which are taxonomy keys and never product values.
- **D-021's governing property** — less information may never earn more. It holds trivially here: adding a value can only raise `covered`.

**D-025's floor does not apply, for two independent reasons.** This check's `partial_credit` is `0.0` (`rubric_data.PARTIAL_CREDIT`), so `max × partial_credit` is 0 and the floor could never bind. More fundamentally, the floor exists for the *uniform-ambiguity* case, and under presence semantics no ambiguity arm runs, so there is no group of ambiguous-but-present variants for a floor to be taken over. The floor is therefore not written into this check rather than written and left inert. **If `partial_credit` is ever raised for this check, that is a decision that must re-open this paragraph**, not a number that quietly starts binding.

**The predicate-cascade argument, recorded because it is the strongest one.** Under the satisfaction reading this check would have to run every constituent attribute's predicate — two or three per category — and D-019 requires a check to stay silent where any covered variant's value is `UNDECIDED`. D3's highest-value single item (3.0) would therefore go silent almost everywhere, and would go silent *precisely where recognition is weakest*. A structural check that inherits the full uncertainty of every value predicate measures nothing that its own question asks about.

**This is not the double-credit D-024 rejected.** On `rec-02` a single value earned a `PARTIAL` for being too vague to answer its own check *and* full credit for being distinguishing — two incompatible claims about the same property. Here the two checks assert different properties: the D2 attribute check says whether the value answers its question, and this check says whether the record resolves per variant. A value may be present-per-variant and simultaneously too vague to satisfy its own key, and reporting both is reporting two true things.

**Zero coverage over partial data is `PARTIAL` at `0/N`, never `UNKNOWN`.** Approved explicitly by the project owner, and stated here because it decides a status rather than a point figure — the earned figure is `0.00` either way.

The rule, in the two halves that matter:

- **At least one required key is stated somewhere across the variants, and no variant carries the complete set** → `PARTIAL` at `max × 0/N` = **0.00**. The values that *are* there are quoted at their own locators, and every variant is named with the keys it is missing.
- **None of the required keys is found at the checked path, for any variant** → `UNKNOWN`, and only here. Its absence evidence names the keys that were looked for, so the claim is exactly as wide as the search that produced it.

`rubric.md` §3.1 defines `UNKNOWN` as *"Not found in any `checked_paths`"*, and in the first case something **was** found at `variants[*].attributes` — the record is incomplete, not empty. Reporting a gap over values that are present is the false negative PRD §8.3 rule 5 calls blocker-severity and `FAB012` catches after the fact. It is also the exact shape D-018 already resolved the same way one dimension over: `PARTIAL`, zero earned, the supplied value quoted rather than treated as though nothing were there.

**Nothing is paid for the partial data.** `satisfied / total` is computed unchanged and `0 / N` is `0.00`, so the honest status costs the merchant precisely what the dishonest one would have. What changes is that they are shown what they did supply, instead of being told a field is empty that is not.

**The generic `unknown` constructor is not used for this check**, and that is part of the same rule. Its detail reads *"No value was found at the checked paths"*, which would be false whenever a variant carries an attribute outside `K`: something was found at `variants[*].attributes`, just nothing this check requires. `checks._nothing_required_per_variant` states the narrower claim instead.

**`checked_paths` is unchanged at `("variants[*].attributes",)`, and that decides the zero-coverage branch.** Where no variant carries the full key set and nothing is stated at that path, the check is `UNKNOWN`, and its absence evidence claims only that variant attributes were searched — which is true. A product-scope value at one of those keys is **outside what this check searched**, so no D-018 branch fires here; that value is reported by its own D2 attribute check under D-018, where the merchant sees it quoted. Reaching the D-018 branch on this check would mean adding `attributes[*]` to `checked_paths`, which changes what its absence evidence asserts to have been searched — an evidence-integrity change of the kind Q-15 records as needing its own decision. The P3.2 plan's slice-D entry asked for both at once (structured-only paths *and* a D-018 branch) and could not have had both.

**Rejected: satisfaction, following D-021 literally.** It reads D-021's rule 1 as a general rule about the word "coverage" rather than a rule about the check D-021 was deciding. It would also write, inside a predicate, a stricter rule than the rubric's own sentence — the failure D-024 exists to prevent.

**Consequence:** `K` is read from `taxonomy_data.attributes_for(category)`, which is the category's §5 attribute set. The Common Core (`taxonomy.md` §3) is excluded: it is audited in D1, D5 and D8 and never in D2, and its two variant-scope non-inheritable rows — `product_identifier` and `price` — are already scored per variant by `IDENT.IDENTIFIER_PRESENT` and `VARIANT.IDENTIFIER_UNIQUE`. Counting them again here would charge one gap twice.

---

## D-031 — `VARIANT.MEDIA_LINKED`'s visual trigger is a closed option-name vocabulary

**Status:** Accepted, by the project owner. Implemented in P3.2 slice D (`engine/lexicon.VARIANT_MEDIA_LINKED_VISUAL_OPTION_NAMES`, `engine/checks.check_media_linked`). Score-moving; `rubric_version` bumped to `0.4` with it (D-023).

**Question:** [`rubric.md`](./rubric.md) §4/D3 states this check as *"Where variants differ visually (color/finish/shade), each has linked media. Conditional on **a visual option existing**."* It does not say how the condition is decided.

**Decision, in four parts.**

1. **The trigger is an option name.** `rubric.md` says *"option"*, which is a Shopify structural term addressing `options[*].name`. A name is matched as a **whole normalized value** — the same mechanism `VARIANT.OPTION_NAMES_MEANINGFUL` already uses against the reserved defaults — never as a substring.

2. **The vocabulary is closed at exactly `color`, `colour`, `finish`, `shade`.** Three of the four are `rubric.md`'s own parenthesis, transcribed. D-024 has already read a `rubric.md` parenthesis as a closed list rather than an illustration, and the same reading applies here. `colour` is admitted as an orthographic variant of a listed word, not as a new kind; that admission is stated here rather than assumed. **`tone` and `pattern` are excluded.** The P3.2 plan proposed both; neither is in `rubric.md`, and adding them would be the widening D-024 rejected — a scoring change made to accommodate an implementation. Under-detection is the permitted direction (D-024) and this is it.

3. **Option presence is sufficient; the values need not differ.** `rubric.md` gives two phrasings — *"variants differ visually"* and *"a visual option existing"* — and states the *condition* in the second. The first is read as the motivation, not as a second test. A multi-variant product whose colour option repeats one value is a narrow case, and value-uniqueness within an option is already `VARIANT.OPTION_VALUES_CONSISTENT`'s question, not this one.

4. **No trigger match is a deferral — neither `NOT_APPLICABLE` nor `UNKNOWN`.** Both alternatives were considered and both are wrong, for opposite reasons, and the record states each because the deferral is the only one of the three that asserts nothing.

   **Not `NOT_APPLICABLE`.** `taxonomy.md` §4.4: a trigger is structural, never assumed. That a colour option was not *found* does not establish that the variants do not differ visually — the axis may be named something outside the vocabulary, which deliberate under-detection guarantees will happen. Declaring `NOT_APPLICABLE` would remove 1.5 points from the denominator on an assumption, which is the one thing PRD §10.3 forbids.

   **Not `UNKNOWN`, and this is the half the P3.1 engine got wrong.** `UNKNOWN` is not silence — it is a positive claim that the check's subject matter was searched for and is absent, and it ships a `minor` finding telling the merchant to go and link media per variant. That claim presupposes the check applies. With no trigger established it does not: a product that varies only on `Size` legitimately needs no per-variant media, and telling its owner they have a media gap is asserting a defect that is not there. `rubric.md` §3.1's own definition — *"Not found in any `checked_paths`"* — presupposes a check whose question has been posed, and here it has not been. The distinction is not academic: this is precisely the movement P3.2 slice D produced, with `VARIANT.MEDIA_LINKED` leaving the `UNKNOWN` set on **eleven** corpus products that have no visual option at all.

   **What deferral costs, stated plainly.** Nothing is earned and nothing is removed from the denominator, so a product whose colour axis is named outside the vocabulary forfeits 1.5 points it may deserve. That is D-019's permitted direction of failure, and it is the price of not asserting either of the two false things above.

**Where the vocabulary lives, and `RESERVED_OPTION_NAMES` with it.** D-022 requires one module: both option-name sets now live in `engine/lexicon.py` as `VARIANT_MEDIA_LINKED_VISUAL_OPTION_NAMES` and `VARIANT_OPTION_NAMES_RESERVED`, each named for its owning `check_id`. `RESERVED_OPTION_NAMES` had sat in `engine/checks.py` since P3.1, predating the lexicon; leaving it there while adding a second option-name vocabulary beside it would have made the split arbitrary and the D-022 invariant unenforceable by inspection. Moving it is behaviour-neutral — the same frozenset, the same whole-value match — and it is done in this commit so that no uncontrolled second vocabulary exists.

**Both sets are excluded from `VALUE_SHAPED`, and therefore from the corpus leak scan.** This follows the precedent already set by `APPAREL_SIZE_SYSTEM_STANDARDS` and `IDENT_TITLE_DISTINGUISHING_KEYS`. The reason is specific: these entries are **option names the merchant supplies**, and PRD §9.7 requires a finding to name the structure it is talking about, so `"Color"` must be quotable in evidence at its own locator. A scan forbidding every lexicon string from appearing in generated text would forbid the check from doing its job. `VALUE_SHAPED` remains what it was — the vocabulary of *ambiguity*, entries that could stand in for a merchant's answer — and that is the set the leak scan exists for. The reserved set would in any case fail `VALUE_SHAPED`'s no-digit assertion on `option 1`, which is the assertion doing its work: a reserved default is a structural name, not a vague value.

**Confidence is the structural arm, which reports `high` on a check `rubric.md` fixes at `medium`.** D-020 permits exactly this and states why: PRD §7.5 assigns `high` to a structural determination, and every step here is structural — whole-value membership in a closed list, then presence or absence of a media reference per variant. The precedent is `VARIANT.OPTION_NAMES_MEANINGFUL`, which matches option names against a closed literal list on the structural arm today. **This is not the recognition path and does not reach PRD §9.5's cap (D-026):** no supplied *value* is read to judge what it means. The vocabulary decides whether the check applies; it never decides whether a value satisfies anything.

**Product-scope media does not cover a variant.** Where the trigger is present and no variant links any media, but `media[*]` is non-empty, the check is `PARTIAL` at **zero earned** with the product-scope media quoted — not `UNKNOWN`. Something was found at a path this check declares it searched, and reporting that as a gap is the false negative PRD §8.3 rule 5 calls blocker-severity. This is D-018's shape applied to media, and it follows the branch `IDENT.IDENTIFIER_PRESENT` already takes for a product-level MPN. `UNKNOWN` is reached only where the trigger is present and neither `variants[*].media_refs` nor `media[*]` holds anything.

---

## D-032 — A score-moving conformance repair bumps `rubric_version`

**Status:** Accepted, by the project owner. Resolves Q-18. Score-moving; `rubric_version` bumped to `0.5` with it (D-023). Implemented alongside the repair it governs: 21 Format C fixtures, `engine/validate.iter_locators`, and the expectations for every affected product.

**Question:** does correcting a pre-existing locator/fixture defect that restores an **already-authoritative** check — and therefore moves scores — require a `rubric_version` bump under D-023?

The instance that raised it. `VARIANT.OPTION_NAMES_MEANINGFUL` emitted nothing on all 21 Format C fixtures carrying options: no finding, no deferral, no `run_error`. The cause was provenance, not scoring. Those records supplied an option locator addressing the option *element* (`options[Size]`), which resolves to a node with no text of its own, where [`PRD.md`](./PRD.md) §6.1's own NPR example locates an option at its **name** (`"src": "row12.Option1 name"`) and §6.2 rule 1 requires a `src` to resolve back to the value beside it. `facts._options` copied that locator onto the name candidate, `evidence.field_value` raised, and `checks.check_option_names` returned an empty list — a drop PRD §8.3 rule 1 permits only *"and logged as a `run_error`"*, which did not happen. Repairing it makes all 21 `PASS` at 2.00, adding 2.00 to both numerator and denominator and raising each product's renormalized score by **1.58 to 3.08** points.

**Decision: yes. D-023 applies mechanically. The governing invariant is the reported scoring function — same input + same `rubric_version` → identical score — and it does not ask why two builds disagree.**

D-023's operative sentence carves out no exception: *"Every commit that can move a fixture score bumps it."* The invariant it protects is [`rubric.md`](./rubric.md) §1.1, *"Same input + same rubric version → identical score"*, stated unconditionally. Two builds both reporting `rubric_version: 0.4` while scoring `rec-11` at 24.47 and 27.55 falsify that sentence, and they falsify it identically whether the second build fixed a bug or introduced one. §1.1's companion property — *"Reproducible by hand"* — is what makes this load-bearing rather than pedantic: a reviewer holding a report and a calculator has no handle on which build produced the number except the version it prints. PRD §12.5 agrees from the other side; the reported score is the observable, and it moved.

**Fixture/data corrections and engine corrections are governed identically.** This repair is both — 21 records and one line of `engine/validate.py` — and splitting them would make the rule depend on which side of the input boundary a defect happened to fall. A record whose provenance is wrong produces a wrong score exactly as a check whose arithmetic is wrong does; PRD §5.3 makes Format C *"already shaped like the Normalized Product Record"*, so its `src` is bound by §6.1 and §6.2 like any other, and a corpus defect is a defect in the thing the score is computed from. The score is what is versioned, not the layer the mistake lived in.

**No `corpus_version`, no build identifier, and that is deliberate.** Q-18's resolution column asked for *some* carrier so a score movement is never silent, and the answer is that `rubric_version` is already that carrier. Introducing a second one would mean a reviewer must check two numbers to know whether a score is comparable, and would create precisely the ambiguity D-023 exists to remove: a reader seeing `0.4` on both reports would have to know which class of change had occurred before knowing which identifier to trust. One number, one meaning — *this score came from this scoring function over this corpus.*

**The usual companions apply unchanged** (AGENTS.md §7): every affected expectation file updated in the same commit, and the moved fixtures named in the commit message. Nothing about this record makes a conformance repair cheaper to ship than a semantics change; it makes them the same price.

**Rejected: no bump, because the intended scoring rule never changed.** This was the stronger of the two readings on the merits, and it is worth stating why it loses. It is true that nothing here decides anything new about any supplied value: [`rubric.md`](./rubric.md) §4/D3 already fixes this check at 2.0, `high`, `PASS` when option names are populated and non-reserved, and `check_option_names` already implemented exactly that. On this reading the repair is a *conformance* fix and D-023's *"behaviour-neutral refactor bumps nothing"* exemption covers it. The reading fails on what "behaviour-neutral" is neutral **with respect to**. D-023 settled that question once already, in the same shape: it rejected reading `rubric_version` as versioning the *document* rather than the *scoring function*, and "it only restores intended behaviour" is that same substitution one level further in — versioning **intent** rather than **output**. Intent is not what a reviewer can check. The score is.

**Consequence, stated because it is the cost of choosing A.** Every future provenance or fixture-data correction that moves a score is a `rubric_version` bump with a decision record and an expectation migration. That is more ceremony than a one-token locator fix looks like it deserves, and it is the price of the invariant. A correction that moves **no** score — one where the affected check was already emitting the same status — remains behaviour-neutral and bumps nothing; the test is the reported number, applied per commit, not the size of the diff.

---

## D-033 — `variants[*].option_values` carries `{value, src}` pairs

**Status:** Accepted, by the project owner. Resolves D-A. Score-moving; `rubric_version` bumped `0.5` → `0.6` and `npr_version` `0.1` → `0.2` with it (D-023, D-032). Implemented alongside this record: the pair shape and its validation (`engine/model`, `engine/validate.validate_npr`, which reports a bare scalar rather than absorbing it), the Format A provenance the normalizer is the only layer able to compose (`engine/csv_input._build_variant`), the two call sites changed from composing a locator to copying the supplied one (`engine/facts._variant_option_values`, `engine/checks.check_variant_differentiated`), the Format C fixtures that now supply the pairs, and the expectations for every affected product. The three products this moved are tabulated below and carried into `rubric.md`'s version history.

**Question:** `VARIANT.DIFFERENTIATED` emits nothing at all on every multi-variant Format A record — no finding, no deferral, no `run_error`. Its `PASS` arm composes its own evidence refs, `variants[<vid>].option_values[<name>]`, which resolve under Format C and are *not parseable* under Format A; `builder.derived` raises and `engine/checks.py` returns an empty list. The check has nothing to copy, because [`PRD.md`](./PRD.md) §6.1 defines `option_values` as a bare dict. What provenance does a variant's option value carry?

**[`PRD.md`](./PRD.md) §6.1 and §6.2 contradict each other on this member, and §6.2 rule 1 governs.** §6.1's skeleton states `"option_values": { "Size": "M", "Color": "Black" }` — bare scalars. §6.2 rule 1 states, without qualification, *"Every value is a `{value, src}` pair. A bare scalar in the NPR is a spec violation."* Nothing in either section exempts option values, and `engine/validate.validate_npr` has silently sided with §6.1 by asserting only that the member is an object. **An option value is a merchant-supplied value in every sense §6.2 rule 1 uses the word:** it is stated in the source, it is quotable at a locator in both formats, and a 5.0-point check reasons over it. §6.1's skeleton is an illustration that predates the rule being tested against it, and it is the illustration that is wrong. `option_values` is today the only NPR member carrying merchant values as bare scalars, and it is the only member whose values cannot be evidenced. Those are the same fact.

**Decision: `variants[*].option_values` is a map of option name to `{value, src}` pair. Format C supplies the pairs. Nothing is derived. A bare scalar is a contract violation, reported and never absorbed.**

**Format C must supply the provenance.** PRD §5.3 makes Format C *"already shaped like the Normalized Product Record (§6)"*, so its records are bound by §6.2 rule 1 exactly as any other. A Format C document that states an option value states where it came from, in the same shape every other value uses.

**A bare scalar is visible, always.** `validate_npr` emits a `run_error` naming the record and the option — PRD §5.4's *"Skip that record, emit a `run_error` entry naming the record and reason, continue the run. Never silently drop."* The check then **defers**, with the reason stated, rather than returning an empty list. Today's behaviour is the precise opposite: an unmet contract produces nothing a reader could ever see, which PRD §8.3 rule 1 permits only *"and logged as a `run_error`"*.

**No provenance is derived during normalization, and PRD §5.3 is the reason.** Filling `src` for an option value inside `pip_input` was the one route that appeared to need no contract change. It is excluded: Format C exists so that *"normalization is the identity function"*, and the corpus test that holds that property states the single permitted divergence and its limit — an absent `tags` member *"is completed to the empty list, **never invented**"*. Completing an absent member to `[]` adds no information. Synthesizing `variants[X].option_values[Y]` asserts a provenance the document did not state, which is invention in the sense that clause forbids. The `tags` exemption is not precedent for this; it is the sentence that rules it out.

**`option_value_srcs` is not introduced. The pair is the single representation.** A parallel locator map keyed alongside the values is the cheaper migration and it is rejected on the merits below. The rule this record fixes is that one fact has one representation in the NPR.

**The Format C locator grammar is unchanged and stays valid.** PRD §8.2.1's table entry `variants[sku:HL-TEE-M].option_values[Size]` → *"a variant's option value"* continues to resolve to the value, because §8.2.1 resolution rule 2 already says so: *"A node shaped like a `{value, src}` pair resolves to its `value`."* The grammar was written to accommodate this shape. Both resolvers agree — the engine's (`engine/locators.resolve_pip`) and the deliberately independent one the fabrication audit uses (`evals/audits/pip_locator`) — so no locator in any expectation file, evidence item or document changes meaning. `.value` and `.src` become additionally addressable; nothing that resolved before resolves differently.

**Provenance is copied, never composed.** `engine/facts._variant_option_values` and `engine/checks.check_variant_differentiated` both build `"variants[%s].option_values[%s]"` in code. Both must read the supplied `src` instead. This is the rule `engine/evidence.py` already states — *"Locators are copied, never composed from parts"* — applied where it had not been. **A composed locator cannot be format-neutral, and neither call site knows the format:** the same string resolves under Format C and fails to parse under Format A. The normalizer is the only layer that knows both the format and the coordinates — the CSV row and option column at `_build_variant`, the element path in Format C — so provenance is recorded there and read everywhere else. `facts._variant_option_values` is unreachable today, since `VARIANT.DIFFERENTIATED` is the only check declaring `variants[*].option_values` and it does not call `facts.gather`; it is repaired in the same change because it is the same defect and would become live the moment a second check declares that path.

**Deferral is the failure behaviour, not the schema.** Deferring when provenance is absent is what the engine does with an unmet contract; it is not an answer to what the contract is. Adopted here as the fallback arm and rejected below as a complete solution.

**Scoring semantics for `VARIANT.DIFFERENTIATED` do not change, and that distinction is the point of this record.** [`rubric.md`](./rubric.md) §4/D3 already fixes the check at 5.0, product scope, `high`, `PASS` when *"Every variant is distinguishable by at least one option value"* and `FAIL` (`critical`) if any two are identical or empty. The verdict logic in `check_variant_differentiated` is correct on both formats today and is not touched: the signature computation reads the values, not their locators. What changes is that the verdict can be **evidenced** on Format A. This record is about provenance and evidence; it decides no point, status, severity, confidence or predicate.

**Versions move for two different and separately-derived reasons.**

- **`npr_version` `0.1` → `0.2`.** The record shape changes. This is the NPR's own version (`engine/model.NPR_VERSION`, carried through at `pip_input`) and it has nothing to do with scoring.
- **`rubric_version` `0.5` → `0.6`.** Not because scoring semantics changed — they do not — but because **three existing fixture scores move**, and D-032 fixed that test as mechanical: *"Every commit that can move a fixture score bumps it."* [`rubric.md`](./rubric.md) §1.1's *"Same input + same rubric version → identical score"* is unconditional, and this is the second application of D-032 rather than a fresh judgment.

**The three products that move, measured rather than estimated.** All are Format A; every multi-variant Format C product already emits `PASS` and is unaffected.

| Fixture | Product | Before | After | Δ |
| --- | --- | --- | --- | --- |
| `csv-inheritance-trap.csv` | `handle:studio-chair` | 14.77 | 23.47 | **+8.70** |
| `csv-multi-product.csv` | `handle:cafe-creme-lip-balm` | 62.86 | 71.11 | **+8.25** |
| `csv-variants.csv` | `handle:harbour-line-tee` | 81.09 | 84.38 | **+3.28** |

Each gains `PASS` at 5.00, adding 5.00 to both the numerator and the applicable maximum; the penalty total is 0.00 in both states, and no grade band changes. No other product in the corpus moves.

**Q-6a is not directly blocked, and one condition attaches.** All three affected products are Format A, both `uncategorized` fixtures are Format C, and every multi-variant Format C product already emits correctly — so this defect is disjoint from Q-6a's measurement surface as the corpus stands today. **But the `uncategorized` fixture set Q-6a needs must not be built in a way that sidesteps this.** A Format C-only set would avoid the defect by excluding the format that exhibits it, and would bake that exclusion into the measurement. Q-6a is measured against [`taxonomy.md`](./taxonomy.md) §6's *"Cross-category score comparison is valid at the score level"*; this defect already breaks comparability **across formats**, underneath the cross-category question Q-6a asks. Deciding this record before the fixture set is built is what keeps the set honest.

**Rejected: `option_value_srcs`, a parallel map of option name to locator.** The argument that would have carried it is that a pair shape would break PRD §8.2.1's blessed locator. **That argument is false, and it was tested rather than assumed:** under §8.2.1 rule 2 the locator resolves to the value under both shapes, in both independent resolvers. What remains for the parallel map is that it migrates without breaking existing consumers, which is implementation convenience and not a reason to choose a schema. Against it: it holds one fact in two places with nothing tying them, so a name present in `option_values` and absent from `option_value_srcs` is a schema-valid record that silently loses its evidence — the same failure class D-032 repaired one layer up. It also leaves `option_values` a permanent exception to §6.2 rule 1 rather than resolving the contradiction this record exists to resolve.

**Rejected: deriving the locator during Format C normalization.** Excluded by PRD §5.3's identity-function requirement, as set out above. This was the only option that appeared to need no contract change, and discovering that it does is what makes this a decision rather than a repair.

**Rejected: citing the variant identifier (`row2.SKU`) as the `derived` evidence.** Fully viable — every affected variant carries a resolvable identifier on both formats, and the check's `FAIL` arm already cites exactly these locators — and rejected because the excerpt would be an identifier while the claim is about option values. PRD §8.1 requires `derived` evidence to reference the items compared, and the SKUs are not what was compared. It would buy a passing check by weakening what the evidence asserts, which is the trade this project refuses; it is also the evidence-integrity shape Q-15 is recorded for. That the `FAIL` arm legitimately cites identifiers is not precedent: there the claim *is* about which variants collide, and naming them is naming the subject.

**Rejected: deferral as the complete solution.** Making the check defer instead of vanishing is correct and is adopted above as the fallback arm — it is also the only option that moves no score and therefore bumps no version, which is exactly why it is not sufficient. It makes the gap visible without closing it, leaves Format A structurally unable to earn 5.0 it deserves, and leaves `facts._variant_option_values` composing a locator that is wrong on the primary input format. Visibility is not conformance.

---

## D-034 — APPAREL.COLOR_FINISH: named_color_per_variant remains deferred; unnamed_color_group is distinct

**Status:** Accepted. Governance-only step — no implementation.

**Question:** [`taxonomy.md`](./taxonomy.md) §5.1 fixes APPAREL.COLOR_FINISH with `satisfies = named_color_per_variant` and `partial_if = unnamed_color_group`. The reconnaissance step evaluated whether to implement either path. Should the engine proceed to implement recognition for this attribute?

**Decision: neither path is implemented in this step. The existing taxonomy contract is preserved exactly as-is.**

1. **`named_color_per_variant` remains deferred under D-022.**
   The governing rule is D-022: *"No lexicon entry may be a product value. Entries are the vocabulary of ambiguity, of units and of standards — never a fact about a product."* A positive named-color lexicon would necessarily consist of product-value vocabulary — the set of color names merchants actually state (e.g., "Heather Grey", "Navy", "Sage"). That is precisely what D-022 forbids. The engine cannot ship a lexicon that enumerates product facts without violating the core no-invention principle (AGENTS.md §2) and the lexicon governance that enforces it (D-022, D-023). This is the same structural block that applies to any attribute whose satisfaction requires recognizing a merchant-stated value drawn from an open product-value vocabulary.

2. **Precedent: BEAUTY.COLOR_SHADE / `named_shade_per_variant`.**
   The BEAUTY.COLOR_SHADE attribute (§5.1) uses the identical pattern — `satisfies = named_shade_per_variant` — and its positive lexicon path has been deferred for exactly this reason. The governance principle is consistent: a taxonomy row may declare a satisfaction condition that the current phase cannot honestly implement, and the tool emits no finding for that condition (D-019) rather than shipping a lexicon of product values. The deferral is not a gap in the specification; it is a specification of where the tool's honesty boundary lies.

3. **`unnamed_color_group` is a separate path and remains unimplemented, but it is *not* blocked by D-022.**
   `unnamed_color_group` recognizes ambiguity vocabulary — vague group terms such as "assorted colors", "multi-color", "various shades", "color pack" — not product facts. D-022 permits ambiguity vocabulary ("Entries are the vocabulary of ambiguity"). A future implementation of `unnamed_color_group` would therefore be a legitimate recognition predicate, subject to the normal D-022/D-023 governance: it would live in `engine/lexicon.py` under its owning `check_id`, bump `rubric_version` (D-023), update every affected expectation file in the same commit, and name the entries in the commit message. It would not require a new decision record unless it changes the *shape* of what the set recognizes.

4. **This decision does not alter `taxonomy.md`.** The attribute's `satisfies` and `partial_if` cells are unchanged. The contract between taxonomy and rubric is preserved.

5. **No code, lexicon, fixture, expectation, rubric version, or baseline is changed by this governance-only step.**
   - `RUBRIC_VERSION` remains 0.6
   - `LEXICON_VERSION` remains 0.6
   - `REGISTRY_VERSION` remains 0.6
   - `NPR_VERSION` remains 0.2
   - No entry is added to `engine/lexicon.py`
   - No check is registered in `engine/registry.py`
   - No fixture or expectation file is modified
   - `evals/monotonicity_baseline.json` is not changed
   - Q-6a diagnostic remains byte-identical

6. **Any eventual implementation of `unnamed_color_group` is a separate score-moving change governed by D-023** and must include the required `rubric_version` bump, expectation migration, and baseline update in one transaction. It is not authorized by this record; it is merely not blocked by D-022.

7. **Q-19 is not resolved here.** It remains an open specification-consistency question recorded in `decisions.md` and is not a prerequisite for this governance disposition.

**Rejected:** *Implement a minimal named-color lexicon anyway* — violates D-022's load-bearing prohibition on product-value vocabulary. *Amend taxonomy to remove `named_color_per_variant`* — would silently change the specification's honesty boundary rather than documenting it; the taxonomy states what satisfaction *is*, and deferral is the engine's honest response. *Treat `unnamed_color_group` as blocked by the same rule* — misreads D-022; ambiguity vocabulary is explicitly permitted.

**Cost:** The attribute remains effectively unaudited for its positive condition. A merchant stating `"Color": "Navy"` on every variant earns nothing for it until a recognition path exists that does not enumerate product values. This is the permitted direction of failure — under-crediting honest data rather than inventing a vocabulary the tool cannot justify.

---

## D-037 — SPORTS.use_environment → environment_stated: whole-value membership against a closed SPORTS_ENVIRONMENTS vocabulary

**Status:** Accepted — governance only; no implementation in this record.

**Question:** `taxonomy.md` §5.5 and `taxonomy_data.py` line 201 declare the satisfying predicate for SPORTS.use_environment as `environment_stated`. The ambiguity predicate `all_conditions_only` is already implemented (D-031 vocabulary, `recognize.py` slice A). Should `environment_stated` be implemented, and if so, what is its recognition boundary?

**Decision: authorize `environment_stated` as a whole-value membership check against a closed vocabulary named `SPORTS_ENVIRONMENTS`, with the following governing rules.**

### 1. Whole-value membership against a closed vocabulary
The predicate returns `true` iff `lexicon.normalize(value)` is an exact member of `SPORTS_ENVIRONMENTS`. No substring matching, no delimiter splitting, no automatic decomposition of composite phrases, no hybrid recognition (structured + prose), and no partial matching. A value such as "indoor and outdoor use" matches only if that exact normalized string is in the vocabulary.

### 2. Vocabulary entries are environment classification standards, not product facts (D-022)
`SPORTS_ENVIRONMENTS` contains terms that name *types of use environments* drawn from recognized classification systems (sport governing bodies, retail taxonomies, safety standards). No entry is a fact about a specific product. The same D-022 invariants apply: `assert_no_product_values()` at import, corpus leak scan over `VALUE_SHAPED`, and the no-digit assertion.

### 3. Explicit composite phrases are permitted as individual lexicon entries
Phrases such as "indoor and outdoor", "gym and field", "road and trail" may be admitted as single entries when they represent a recognized combined-environment class. Each composite is an atomic vocabulary term; it is not decomposed at recognition time. The vocabulary is the authority on what constitutes a distinct environment class.

### 4. Prose boundary preserved (D-019)
The predicate is wired to `facts.Gathered.stated`, which excludes `PROSE_PATHS` by construction. A value found only in description prose is never passed to this predicate. The check defers and emits no finding — it does not report `UNKNOWN`, it does not penalize, and it does not infer the fact.

### 5. Scope strictly limited to SPORTS.use_environment → environment_stated
This decision does not extend to any other attribute, category, or predicate. In particular:

- **HOME.indoor_outdoor_use → use_with_durability_basis is explicitly NOT bundled.** That attribute (§5.4) has different predicate semantics: its `PARTIAL` condition is *"Can be used outdoors with no durability basis"*, requiring recognition of a *durability basis* — a language judgment about whether the claim is supported — not a closed environment-class vocabulary. Bundling would conflate two distinct recognition shapes and would require a separate governance decision if ever proposed.

- No other category's environment/conditions attribute (e.g., ELECTRONICS `operating_conditions`, APPAREL `intended_use_context`) is affected.

### 6. Interaction with `all_conditions_only` (the existing ambiguity predicate)
- `all_conditions_only` remains the `partial_if` predicate for this attribute. It fires on vague totalizing phrases: "all conditions", "all weather", "any conditions", "all terrain" (the current `SPORTS_USE_ENVIRONMENT_VAGUE` set).
- `environment_stated` is the `satisfies` predicate. It fires on specific, classifiable environment statements.
- The two predicates are **disjoint in intent**: one recognizes *ambiguity* (vague totalizing claims), the other recognizes *specific environment classes*.
- A value that matches `all_conditions_only` is `AMBIGUOUS` → `PARTIAL` at `max × partial_credit`. A value that matches `environment_stated` is `SATISFIED` → `PASS` at full points. A value that matches neither is `UNDECIDED` → the check defers (D-019).
- **Evaluation order is fixed by the check handler.** `engine/checks.py:489-510` (`_best_verdict`) evaluates the `satisfies` predicate first; if it returns `SATISFIED`, that verdict is returned immediately. Only if no value satisfies does it consider `AMBIGUOUS` from the `partial_if` predicate. Thus `SATISFIED` outranks `AMBIGUOUS` by construction.

### 7. Overlap rule: a term may exist in both vocabularies
If a term is independently established as a recognized environment classification standard **and** also functions as a vague totalizing phrase in merchant data, it may appear in both `SPORTS_ENVIRONMENTS` and `SPORTS_USE_ENVIRONMENT_VAGUE`. When this occurs, the evaluation order above gives `SATISFIED` precedence — the value earns `PASS`. This is not a conflict; it is a deliberate overlap resolved by the fixed evaluation order. **This record does not authorize any specific term for either vocabulary**, including "all terrain". Whether "all terrain" (or any other phrase) meets the classification-standard threshold is decided in the separate implementation decision that admits it.

### 8. Vocabulary contents not decided here
The exact final membership of `SPORTS_ENVIRONMENTS` is **not fixed by this record**. The existing repository evidence establishes only:
- The attribute's `taxonomy.md` description: "Indoor/outdoor, terrain, surface, water/temperature conditions"
- The ambiguity vocabulary already in `lexicon.py`: "all conditions", "all weather", "any conditions", "all terrain"

Candidate vocabulary **categories** suggested by the taxonomy wording include: indoor/outdoor classifications, terrain types (trail, road, track, field, court), surface types, water environments, snow environments. **These are categories of candidate entries, not authorized entries.** Each individual term requires a separate implementation decision that:
- Enumerates candidate entries with their classification-standard sources
- Verifies each candidate against D-022 (no product values, no digits, no unit mappings)
- Bumps `rubric_version` (D-023) and migrates all affected expectation files in the same commit
- Names the admitted entries in the commit message

Until that implementation decision lands, `environment_stated` remains **UNIMPLEMENTED** in `engine/recognize.py` and the check defers on all structured values (D-019).

### 9. No implementation files changed by this governance record
- `RUBRIC_VERSION` remains **0.10**
- `LEXICON_VERSION` remains **0.10**
- `REGISTRY_VERSION` remains **0.10**
- `NPR_VERSION` remains **0.2**
- No entry added to `engine/lexicon.py`
- No predicate registered in `engine/registry.py`
- No fixture or expectation file modified
- `evals/monotonicity_baseline.json` unchanged

**Rejected:**
- *Implement `environment_stated` as a prose recognizer over description* — violates D-019; prose is deferred, never recognized in this phase.
- *Allow delimiter splitting ("indoor, outdoor" → matches "indoor" and "outdoor")* — violates whole-value membership; a composite is either an admitted vocabulary term or it is not recognized.
- *Allow substring matching ("outdoor use" matches "outdoor")* — same violation; the vocabulary is the authority on what constitutes a class.
- *Bundle with HOME.indoor_outdoor_use* — different predicate semantics (durability basis vs. environment class); separate governance required.
- *Treat vocabulary overlap as a conflict* — it is not; fixed evaluation order (SATISFIED before AMBIGUOUS) gives a deterministic, documented outcome.

**Cost:** The satisfying arm remains deferred until `SPORTS_ENVIRONMENTS` is concretely decided and implemented. A merchant stating `"use_environment": "trail"` earns nothing for it until the vocabulary admits "trail". This is the permitted direction of failure (D-003, D-019) — under-crediting honest data rather than inventing a vocabulary the tool cannot justify.

---

## Open questions

Deliberately unresolved. Each is recorded so V0 does not foreclose it, and none blocks V0. Q-18 was resolved by D-032 and is recorded there.

| # | Question | Why deferred | What would resolve it |
| --- | --- | --- | --- |
| Q-1 | How are multi-language / multi-locale catalogs audited? Is a translated description a separate product record? | No locale fixtures; V0 assumes single-locale input. | Merchant interviews + a locale fixture set. |
| Q-2 | How do market-specific prices and availability affect D5? | Requires market context V0 has no access to. | Post-integration data. |
| Q-3 | Bundles, kits, and Shopify combined listings — one record or several? | Structurally distinct; would need its own attribute logic. | Primary Shopify documentation review + real bundle fixtures. |
| Q-4 | Should the merchant see a raw score or a banded grade only? Does a number invite gaming? | Needs real merchant reaction. | User testing on V0 reports. |
| Q-5 | Is 200 the right batch ceiling, and how should catalog-level systemic reporting work at 3,000 SKUs? | Depends on whether merchants act per-product or per-pattern. | Observation of V0 usage. |

---
## D-035 — `number_without_unit_or_basis` recognized only for the structurally decidable "no unit" sub-case

**Status:** Accepted. Governance-only step — no implementation.

**Question:** The reconnaissance step evaluated the shared predicate `number_without_unit_or_basis`, declared as `partial_if` for both `HOME.capacity_or_load` and `SPORTS.load_or_capacity_rating` (`taxonomy.md` §5.4 and §5.5). Each taxonomy row states its PARTIAL condition as *"A number with no unit or basis"* (Home) and *"A number with no unit or no basis"* (Sports). Should the engine proceed to implement recognition for this predicate, and if so, what is its boundary?

**Decision: the predicate is initially recognized ONLY for the structurally decidable sub-case — a numeric/magnitude value with no recognized unit token. The "no basis" portion is NOT implemented in this slice.**

1. **Shared predicate — one implementation for both declarations.**
   The predicate ID `number_without_unit_or_basis` is a single entry in `taxonomy_data.RECOGNITION_PREDICATES` (frozenset deduplicates) and will be a single evaluator in `registry.IMPLEMENTED_PREDICATES`. It applies to:
   - `HOME.capacity_or_load` (Tier A, product scope, inheritable, conditional on `load_bearing_element_indicated`)
   - `SPORTS.load_or_capacity_rating` (Tier A, product scope, inheritable, no trigger)
   One evaluator, one boundary, both categories. No Sports-only or Home-only variant.

2. **Structurally decidable scope: "no recognized unit token."**
   The ambiguity arm fires when a supplied value parses as a magnitude (via `lexicon.magnitude`) and the extracted unit spelling is **empty** or **not a member of the recognized unit sets** (`LENGTH_UNITS | MASS_UNITS | VOLUME_UNITS | TIME_UNITS`, extended per this decision to include `VOLTAGE_UNITS` for electronics predicates).
   - Examples that become `AMBIGUOUS`: `"50"`, `"300"`, `"2.5"`, `"100 lbs"` (if "lbs" not in `MASS_UNITS`), `"150 kg"` (if "kg" not in `MASS_UNITS`).
   - Examples that do NOT become `AMBIGUOUS` (remain `UNDECIDED`): `"50 kg weight capacity"`, `"300 L volume"`, `"seats 4"`, `"150 kg max user weight"`, `"10-50 kg resistance range"` — these have a unit token; whether they also state a "basis" is a language question.

3. **"No basis" is explicitly excluded from this slice.**
   Determining whether a number *represents* a weight capacity, volume, seating count, user weight, resistance range, or rated load requires reading the surrounding text for basis-indicating terms. That is language recognition, not structural shape detection. Values whose ambiguity depends on missing basis remain `UNDECIDED` → the check defers (D-019) and emits no finding. This is the permitted direction of failure (under-detection).

4. **No product-value vocabulary, no heuristic language recognition.**
   - No lexicon of capacity types ("weight capacity", "volume", "seating", "user weight", "resistance", "rated load") is added. Such a lexicon would be product-adjacent and risks D-022 violation.
   - No NLP, stemming, or keyword matching for "basis" terms is implemented.
   - The predicate boundary is exactly: *magnitude parsed, unit token absent or unrecognized*.

5. **This decision does NOT authorize implementation of any of the following:**
   - `HOME.load_bearing_element_indicated` (trigger predicate — remains UNIMPLEMENTED; Home check defers on trigger detection per D-019)
   - `capacity_with_unit_and_basis` (satisfies predicate for Home — remains UNIMPLEMENTED)
   - `rated_load_with_units` (satisfies predicate for Sports — remains UNIMPLEMENTED)
   - `specs_without_units` / `specs_with_units` (Electronics core_specifications)
   - `voltage_without_plug_type` / `voltage_with_plug_type` (Electronics power_requirements)
   - Any taxonomy change (the `partial_if` cells remain exactly as written)
   - Any prose recognition (D-019 deferral on unread prose stands)

6. **No code, lexicon, fixture, expectation, rubric version, or baseline is changed by this governance-only step.**
   - `RUBRIC_VERSION` remains 0.7
   - `LEXICON_VERSION` remains 0.7
   - `REGISTRY_VERSION` remains 0.7
   - `NPR_VERSION` remains 0.2
   - No entry is added to `engine/lexicon.py` (not even `VOLTAGE_UNITS` — that is deferred to the implementation step)
   - No evaluator is added to `engine/recognize.py`
   - No check is registered in `engine/registry.py`
   - No fixture or expectation file is modified
   - `evals/monotonicity_baseline.json` is not changed
   - Q-6a diagnostic remains byte-identical

7. **Any eventual implementation of this predicate is a separate score-moving change governed by D-023** and must include the required `rubric_version` bump, expectation migration, and baseline update in one transaction. It is not authorized by this record; it is merely governance-cleared for the boundary defined here.

**Rejected:** *Implement "no basis" detection via keyword matching* — violates D-022 (product-adjacent vocabulary) and D-019 (language recognition over prose requires a predicate, not a heuristic). *Implement Sports-only to avoid Home's trigger* — violates the shared predicate ID contract; one registry entry, one evaluator. *Amend taxonomy to split the predicate* — would silently change the specification rather than documenting the implementation boundary.

**Cost:** The predicate's coverage is narrower than the taxonomy wording. A merchant stating `"300 lbs"` (unit recognized) but no basis earns nothing for the ambiguity arm until a language-recognition path exists. This is the permitted direction of failure — under-detecting ambiguity rather than over-detecting it or inventing basis vocabulary.

---
## D-036 — Tier-B "guidance" attributes use whole-value recognition; composite structural phrases authorized for two predicates

**Status:** Accepted

**Question:** `taxonomy.md` §5.1 declares two Tier-B Apparel attributes whose `satisfies` predicates are unimplemented:

- `care_instructions`: Satisfied by *"Washing/drying/ironing guidance or a care symbol reference"*
- `intended_use_context`: Satisfied by *"Season, activity, or occasion the garment is made for"*

Their `partial_if` arms are already implemented as whole-value membership against closed vague-phrase sets (`APPARAL_CARE_INSTRUCTIONS_VAGUE`, `APPARAL_INTENDED_USE_CONTEXT_VAGUE`). The reconnaissance step identified that merchant data may state multiple care methods or use contexts in a single value (e.g., `"Machine wash cold, tumble dry low"` or `"spring, hiking"`). Should the `satisfies` predicates use whole-value membership (matching the `partial_if` arms), delimiter-split structural recognition (like `enumerated_contents`), or a hybrid?

**Decision: Whole-value membership for both predicates. Composite structural phrases are authorized as closed vocabulary for these two predicates only. No delimiter splitting, no hybrid recognition, no prose recognition, no partial matching.**

### Governance Decision

#### 1. Taxonomy wording governs the value shape

`care_instructions` uses "guidance" (singular mass noun). `intended_use_context` uses "season, activity, or occasion" — a disjunctive list of alternatives, not a conjunctive list of combinable values. Neither says "enumerated" (contrast `in_the_box`: "enumerated contents" `taxonomy.md:151`) nor implies dimension-like syntax (contrast `physical_dimensions_weight`: "dimensions with units" `taxonomy.md:147`). The grammar of the taxonomy cells is the contract; we do not infer multi-value structure where the taxonomy does not state it.

#### 2. Consistency with `partial_if` arms is required

`care_without_method` and `generic_everyday_only` are implemented as whole-value `_member_of` predicates against closed vague-phrase frozensets. The `satisfies` and `partial_if` arms of a single check evaluate the SAME supplied value. They must share a structural model of what that value is. A value cannot be both a single whole (for ambiguity) and a splittable list (for satisfaction). The whole-value model is the established one for these checks.

#### 3. D-019 deferral principle forbids silent splitting of prose

`rec-03-vague-in-a-sentence` demonstrates that `"Easy care fabric that holds its shape"` and `"Cut for everyday wear and for layering"` must defer, not match. Whole-value membership achieves this: the full string is not in the lexicon. Delimiter-split on comma would incorrectly match `"Easy care"` inside the prose. D-019 requires "a value is supplied and the recognition predicate ran and could not decide it" → deferral. A split predicate cannot reliably distinguish enumeration from prose without language recognition, which D-019 reserves for the check phase over quoted spans, not the predicate phase.

#### 4. D-022 establishes the lexicon boundary; this decision authorizes composite structural phrases within it

D-022 (`product/decisions.md:421`) states: "Entries are the vocabulary of ambiguity, of units and of standards — never a fact about a product." This decision establishes that, **for `care_method_stated` and `use_context_stated` only**, whole-value composite structural phrases may be used as closed vocabulary where they represent care-method/use-context *structure* rather than product facts.

Examples of the newly authorized closed structural vocabulary (not pre-existing D-022 vocabulary):
- `care_method_stated`: `"machine wash cold, tumble dry low"`, `"hand wash, line dry, iron low"`
- `use_context_stated`: `"spring hiking"`, `"formal office wear"`

These are care-method combinations and use-context composites — structural vocabulary describing *types of care routines* and *types of use contexts* — not facts about a specific product. They contain no digits, no measurements, no brand terms. `APPARAL_SIZE_SYSTEM_STANDARDS` already contains composites like `"us 10"` (standard + value). The same structural principle applies: a named care routine or use context is a standard, not a product value.

#### 5. D-024 closed-list precedent applies

D-024 (`product/decisions.md:455`) held that "the parenthesis is a closed list, not an illustration" for `IDENT.TITLE_DISTINGUISHING`. Whole-value membership against a frozenset enforces closed-list semantics. Delimiter-split would effectively open the list: any combination of atomic terms would match, including combinations never reviewed. This decision authorizes the lexicon frozensets to contain composite entries, maintaining closed-list control.

#### 6. D-035 structural boundary precedent applies

D-035 (`product/decisions.md:820`) drew the predicate boundary at "magnitude parsed, unit token absent or unrecognized" — a purely structural test. It explicitly rejected "keyword matching for 'basis' terms" and "lexicon of capacity types" as language recognition. Comma-splitting requires judging whether a comma in merchant data is structural enumeration or prose punctuation — a language judgment, not a structural one. This decision stays on the structural side: whole-value exact match against a closed set.

#### 7. Explicit scope: these two predicates only

This decision applies ONLY to:
- `APPAREL.CARE_INSTRUCTIONS` → `care_method_stated`
- `APPAREL.INTENDED_USE_CONTEXT` → `use_context_stated`

It does NOT establish a general rule for all Tier-B attributes. `electronics.in_the_box` ("enumerated contents") and `electronics.physical_dimensions_weight` (dimension syntax) retain their delimiter-split semantics because their taxonomy wording explicitly describes enumeration and dimension structure. Future Tier-B attributes with "enumerated" or dimension-like wording would follow those precedents. Future "guidance" attributes would need their own decision record.

### Explicit Rejections

**Rejected: Delimiter splitting (Option B).** No taxonomy basis for "enumerated" or dimension syntax. Inconsistent with implemented `partial_if` arms. Violates D-019 prose safety. Invents delimiter grammar not in taxonomy. D-028's "enumeration is a structural property" reasoning applies only where taxonomy says "enumerated" (`product/decisions.md:544`).

**Rejected: Hybrid recognition (Option C).** No taxonomy basis for "when to split". D-035 rejects hybrid boundaries requiring judgment (`product/decisions.md:820`). Creates third predicate shape with no precedent. Inconsistent with `partial_if` arms. D-024 rejects expanding beyond explicit taxonomy wording.

**Rejected: Prose recognition / substring matching.** D-019 forbids language recognition in the predicate phase. `rec-03-vague-in-a-sentence` fixture intent: "Whole-value membership is the rule... A substring match here would be the predicate reading language."

**Rejected: Mixed recognized/unrecognized partial matching.** No predicate in the codebase partially matches a value and awards credit for the recognized portion. A value either satisfies, is ambiguous, or is undecided. Partial matching would introduce a new scoring semantics not present in `rubric.md`.

### Implementation Consequences (Not Part of the Decision)

The following are implementation consequences of the governance decision above. They are recorded here for traceability but are not the decision itself.

1. **Lexicon additions in `engine/lexicon.py`**:
   - `APPARAL_CARE_METHODS`: frozenset of composite care-routine phrases
   - `APPARAL_USE_CONTEXTS`: frozenset of composite use-context phrases
   - Both added to `VALUE_SHAPED` for corpus leak scanning
   - `LEXICON_VERSION` == `RUBRIC_VERSION` at import (D-022)

2. **Predicate implementations in `engine/recognize.py`**:
   - `care_method_stated(value)`: `X.normalize(value) in APPARAL_CARE_METHODS`
   - `use_context_stated(value)`: `X.normalize(value) in APPARAL_USE_CONTEXTS`
   - Registered in `VALUE_PREDICATES`

3. **Fixtures required** (minimum):
   - PASS: `care_instructions: "Machine wash cold, tumble dry low"` → expects `PASS` at 1.65
   - PASS: `intended_use_context: "spring hiking"` → expects `PASS` at 1.65
   - DEFERRED: `care_instructions: "Gentle cycle"` (not in lexicon) → expects deferral

4. **Version bumps** (same commit, D-023):
   - `RUBRIC_VERSION` 0.8 → 0.9
   - `LEXICON_VERSION` 0.8 → 0.9
   - `REGISTRY_VERSION` 0.8 → 0.9
   - Affected expectation files updated
   - `evals/monotonicity_baseline.json` updated

5. **Score movement**:
   - Products with exact lexicon phrases currently `UNKNOWN` (0/1.65) → `PASS` (1.65/1.65) → **+1.65 pts**
   - Products with multi-term values not in lexicon → `UNDECIDED` → deferred → no finding
   - Products with vague phrases → `PARTIAL` (unchanged, 0.825/1.65)
   - No products lose points

---

**Sources:**
- `product/taxonomy.md:120,123` (care_instructions, intended_use_context contracts)
- `product/decisions.md:536-548` (D-028: enumerated_contents scope)
- `product/decisions.md:449-475` (D-024: closed-list precedent)
- `product/decisions.md:795-844` (D-035: structural boundary)
- `product/decisions.md:409-427` (D-022: lexicon boundary)
- `engine/recognize.py:85-90` (_member_of whole-value implementation)
- `engine/recognize.py:173-187` (enumerated_contents delimiter-split implementation)
- `evals/fixtures/recognition/rec-02-vague-phrases.pip.json` (PARTIAL fixtures)
- `evals/fixtures/recognition/rec-03-vague-in-a-sentence.pip.json` (deferral fixture)
- `evals/expected/recognition/rec-02-vague-phrases.expected.json` (expectations)

---
## D-038 — `BEAUTY.key_actives_and_concentration`: the concentration is recognized structurally; the named active stays unverified

**Status:** Accepted. Governance-only step — no implementation.

**Question:** [`taxonomy.md`](./taxonomy.md) §5.2 fixes `key_actives_and_concentration` with `satisfies = actives_with_concentration` and `partial_if = actives_without_concentration`. Both ids are declared in `engine/taxonomy_data.py` and neither has an evaluator, so wherever a value is stated and no conflict is routed, `BEAUTY.KEY_ACTIVES_AND_CONCENTRATION` defers rather than deciding satisfaction. Should the engine implement them, what is the boundary, and does Q-13 govern — given that a satisfying arm would decide only one of the two components the taxonomy cell names?

**Decision: both arms are authorized as structural shape recognition over the supplied value, matched by unanchored search rather than whole-value membership — a stated proportion decides satisfaction, and the provable absence of any digit decides ambiguity. No vocabulary of any kind is added. The "named actives" component is not verified, and this record states why it does not need to be.**

1. **Exact scope — one check, two predicates, nothing else.**
   - Check: `BEAUTY.KEY_ACTIVES_AND_CONCENTRATION` (D2, Tier B, product scope, inheritable, `max_points` 1.32, `partial_credit` 0.5, so `PARTIAL` earns 0.66; `conflict_severity` `blocker`).
   - `actives_with_concentration` — the `satisfies` arm.
   - `actives_without_concentration` — the `partial_if` arm.

   This record reaches no other check, no other category, and no other predicate id.

2. **The structural boundary, stated exactly.**
   - `actives_with_concentration` fires when a proportion token — a number followed by `%` — occurs **anywhere in the supplied value**. This is an unanchored search over the value, not whole-value membership and not delimiter splitting.
   - `actives_without_concentration` fires when the value contains **no `%` and no digit at all**. The digit condition is what makes the arm provable rather than merely unmatched: a value with no digit cannot be carrying a concentration stated in some other notation.
   - A value that satisfies neither — one carrying a digit that is not a percentage — is `UNDECIDED`, and the check defers and emits nothing (D-019).

   The shape is the one `engine/recognize.py` already implements for `APPAREL.material_composition` (`_PROPORTION_RE`, `_DIGIT_RE`). Reusing it is the intended implementation form; introducing a different matching family for these two arms is not authorized here.

3. **What is deliberately NOT recognized.**
   - **That an active was named.** See 4.
   - **Concentrations stated outside percent notation** — `"10 mg/ml niacinamide"`, `"1000 ppm"` — remain `UNDECIDED`. Reaching them needs a unit vocabulary that this record does not add and does not authorize.
   - **Enumeration of several actives.** The value is read as a whole. No delimiter splitting, on the reasoning D-036 §6 gives for rejecting it: judging whether a comma is enumeration or prose punctuation is a language judgment, not a structural one.
   - **Prose.** The predicates are wired to `facts.Gathered.stated`, which `facts.gather` separates from `PROSE_PATHS` by path pattern. A value found only at `narrative.description_text` is never passed to either arm; the check defers (D-019). See 7 for the qualification this carries.

4. **Why the keyed-attribute assumption is sufficient for the "named active" component.**
   `engine/recognize.py` already states the assumption, and states that recognition inherits rather than introduces it: "A value found at an exactly-keyed attribute path is the merchant's assertion *about that attribute*. `material_with_proportions` does not verify that a fibre was named; it verifies that a proportion was stated at a field the merchant keyed as material composition. P3.1 already relies on this for every `VALUE_PRESENT` check -- recognition does not introduce the assumption, it inherits it."

   The same sentence holds here with `active` for `fibre`. A value at `attributes[key_actives_and_concentration]` is the merchant's assertion about actives; the predicate decides only whether a concentration accompanies it. **Nothing in either arm asserts what the active is**, and no finding either arm produces may say so — the finding quotes the merchant's own value at its own locator and interprets nothing (`engine/checks.ambiguous`, `engine/checks.present`).

   The alternative — verifying that an active was named — would require a lexicon of active-ingredient names. That is product-value vocabulary, forbidden by D-022 and refused for the same reason by D-034. It is not proposed and not authorized.

5. **`material_with_proportions` is the precedent, and it is an architectural one rather than a governance one.**
   `taxonomy.md` §5.1's `material_composition` cell — *"Fiber content with percentages"* / *"Material named without proportions"* — has the same two-conjunct shape as §5.2's `key_actives_and_concentration` cell: a named thing plus a measurable qualifier, where the qualifier is structurally decidable and the named thing is not. Its predicates have been in the engine since `engine/recognize.py` was created in `726f8e1`.

   **They carry no predicate-specific decision record.** That absence is stated here because it is the reason this record exists: the shape is established in the codebase but was never written down, and relying on an unwritten precedent is what AGENTS.md §7 asks us not to do. **This record governs the two Beauty predicates only. It does not retroactively govern `material_with_proportions`, does not ratify it, and makes no claim about whether it should have shipped without a record.**

6. **D-036 does not govern this change, and its scope limit is not engaged.**
   D-036 §7 confines itself to `APPAREL.CARE_INSTRUCTIONS → care_method_stated` and `APPAREL.INTENDED_USE_CONTEXT → use_context_stated`, and what it authorizes is *composite structural phrases as closed lexicon vocabulary*. **This record adds no lexicon entry, no lexicon set, and no vocabulary of any kind**, so there is nothing here for D-036's authorization or its scope limit to reach. No entry joins `VALUE_SHAPED`, so the corpus leak-scan surface does not grow. The only change to `engine/lexicon.py` the eventual implementation contemplates is the version literal moving with the rubric bump (item 12): the file is edited, but no vocabulary in it is.

   D-036 §2's requirement is met on its own terms: the `satisfies` and `partial_if` arms of one check must share a structural model of what the value is. Both arms here read the same whole value for the same property, from opposite sides.

7. **Q-13 does not apply by its own wording, and this record does not answer it.**
   Q-13 asks about *"a predicate **named as a disjunction**"*. It names `warranty_with_duration_or_scope` by id, and identifies the other predicate not by id but by its defining phrase — the ambiguity arm *"no unit **or** no basis"*, which is `number_without_unit_or_basis`. Neither Beauty predicate id contains a disjunction, and neither cell of the `key_actives_and_concentration` row is disjunctive — `"Named actives **with** concentration"` and `"Actives named without concentration"` are a conjunction and a single condition.

   **Q-13 remains open and is unchanged by this record.** Its resolution column asks for *"an explicit statement, **per predicate and per arm**, that a decidable half may decide alone"*; this record makes such a statement for these two arms and for nothing else. It does not generalize, it does not settle Q-13 for the predicates Q-13 names, and it is not authority for any other partially decidable predicate.

8. **The prose-origin dependency, named and left open.**
   The one corpus product these predicates would move — `sparse-beauty-02` / `handle:verda-barrier-cream` — carries its value at `attributes[key_actives_and_concentration]` with `origin: merchant_prose` and `src: narrative.description_text[16:47]`, extracted upstream by the fixture's producer. The engine's prose boundary is applied by **path pattern** (`facts.gather`), so that value is in `stated` and would reach the predicate, and the finding's evidence locator would be the description span the value came from.

   **This record does not decide whether that is right.** The question — *may a recognition predicate receive a `merchant_prose`-origin candidate, or is the prose boundary an origin boundary as well as a path boundary?* — is unresolved, is not specific to these predicates, and is not resolved here. It is named so the dependency is visible rather than silent: if that question is ever answered the other way, the finding on this fixture is one of several that would have to be revisited.

9. **Deferral is the permitted direction, and no arm asserts absence.**
   Neither arm can produce `UNKNOWN`, `FAIL` or a penalty. Absence and conflict are decided structurally before recognition runs, and `conflict_routing` on this check — which carries `blocker` conflict severity — is unchanged and continues to precede any predicate. No predicate here is owned by a penalty check, which `engine/registry._invariants` refuses to load.

10. **This record does NOT authorize:**
    - any lexicon of actives, ingredients, or concentrations;
    - any unit vocabulary for non-percent concentration notation;
    - delimiter splitting, substring matching against a vocabulary, or prose recognition;
    - `complete_ingredient_list` / `key_ingredients_only` (`BEAUTY.ingredients_full`), whose satisfying arm requires judging completeness;
    - any other `taxonomy.md` §5.2 predicate;
    - `materials_with_component_mapping` / `material_without_component_mapping`, or any other conjunctive cell in another category;
    - any change to `taxonomy.md` — both cells stand exactly as written;
    - any answer to Q-13, and any disposition of `rated_load_with_units`, which is a separate matter with its own history and is untouched here.

11. **No code, lexicon, fixture, expectation, version or baseline is changed by this governance-only step.**
    - `RUBRIC_VERSION` remains 0.11
    - `LEXICON_VERSION` remains 0.11
    - `REGISTRY_VERSION` remains 0.11
    - `NPR_VERSION` remains 0.2
    - No entry is added to `engine/lexicon.py`
    - No evaluator is added to `engine/recognize.py`
    - No predicate is registered in `engine/registry.py`
    - No fixture or expectation file is modified
    - `evals/expected/monotonicity_baseline.json` is not changed

12. **Expected governance consequence when implementation follows.** It is a separate score-moving change governed by D-023 and must carry, in one commit: `RUBRIC_VERSION`, `LEXICON_VERSION` and `REGISTRY_VERSION` moved together with `evals/measure/q6a.PINNED_RUBRIC_VERSION`; a migration of every affected expectation file; a fixture set exercising the satisfying arm, the ambiguity arm and — since the residue is real — the `UNDECIDED` case, on the practice every recognition slice has followed (`rec-16`–`rec-20`, `rec-21`–`rec-23`, `rec-25`); and the moved fixtures named in the commit message.

    Two facts about the corpus, measured against the engine while writing this record and to be re-verified by the implementing commit rather than taken from here: `evals/expected/sparse/sparse-beauty-02.expected.json` **already declares** `BEAUTY.KEY_ACTIVES_AND_CONCENTRATION` as `PARTIAL` with the reason *"Actives named without concentration."* at `narrative.description_text[16:47]` — an expectation written in P1 that the engine has never met; and the pinned sets of `monotonicity_baseline.json` do not move, because the only transition is a deferral becoming `PARTIAL`, which the recognition contract already permits.

**Rejected:** *Implement a lexicon of named actives so the satisfying arm can verify both components* — product-value vocabulary, forbidden by D-022 and refused on the same ground by D-034. *Implement the ambiguity arm alone* — a value stating a concentration would then earn nothing while a value stating none earned 0.66. **This record refuses that inversion for these two arms on its own reasoning, and not by appeal to a general rule.** D-021 and D-025 are the nearest analogous reasoning the repository holds, but both state their property about *variant coverage* — *"less information may never earn more than more complete variant coverage"* — and this check is product-scope and inheritable, so neither reaches this case as authority. Nothing here establishes a monotonicity rule about richer single values; item 7's limit applies to this paragraph too. What decides it is the contrast with D-034, which accepted a one-armed implementation for `APPAREL.COLOR_FINISH` **because** its satisfying arm is permanently blocked by D-022. That condition is what makes the asymmetry unavoidable there, and it does not hold here: the satisfying arm is implementable with the same shape as the ambiguity arm, so there is no reason to create the asymmetry. *Reach the value by delimiter splitting so each active is judged separately* — rejected on D-036 §6's reasoning. *Extend the boundary to non-percent concentration notation* — needs a unit vocabulary decided on its own merits. *Rely on `material_with_proportions` as precedent without a record* — the precedent is architectural and undocumented, which is what this record is for.

**Cost.** Three costs, each a case where honest data earns less than it might.

A merchant stating a concentration in any notation other than a percentage — `"10 mg/ml niacinamide"` — earns nothing for it; the check defers. A merchant naming actives with no concentration earns 0.66 of 1.32, which is the taxonomy's own `PARTIAL` and is correct rather than a cost. And a merchant whose active's *name* contains a digit — `"Vitamin B3"`, with no concentration stated — falls outside both arms and earns **nothing**, where the same statement of a digit-free name would have earned 0.66. That last case is the sharpest edge of the digit condition in 2, and it is recorded rather than smoothed over: the condition is what makes the ambiguity arm provable, and the price of provability is that it abstains where a digit appears for an unrelated reason. All three are D-019's permitted direction of failure — under-crediting supplied data rather than reading a value the tool cannot honestly read.

---

## Open questions
| Q-6a | **Diagnostic, no policy content.** Under the *existing* scoring function, are `uncategorized` products deflated or flattered in aggregate once D2's 22 points (`taxonomy.md` §2 rule 3) and `VARIANT.ATTRIBUTE_COVERAGE`'s 3.0 (D-029) are both removed and the total is renormalized by `rubric.md` §6.3? Direction is deliberately left open in the question: the removals are favourable exactly when the product's would-be earn-rate on the removed points is *below* its earn-rate on the rest, so the sign is product-dependent and neither direction may be presupposed. The norm it is measured against is `taxonomy.md` §6's closing line, *"Cross-category score comparison is valid at the score level (all are out of 100)"*, and `uncategorized` is a row in that table. | **Not a decision, and not blocked on one.** It is arithmetic over a scoring function that is already fully specified (`rubric.md` §1.2, §6.1), and it is unanswerable today only because no score exists to measure: `engine/runner.py` computes no total by design, and `evals/audits/arithmetic_audit.py` verifies a reported score that nothing yet produces. | P4 landing an actual aggregate score (`max_applicable`, renormalization factor, normalized total), **plus** an `uncategorized` fixture set adequate to measure over. `PRD.md` §12.1's corpus plan defines no such set, and the corpus currently holds two `uncategorized` fixtures — `checks-07` (single-variant, where `NA_SINGLE_VARIANT` fires regardless) and `rec-11` (the only multi-variant one). It must span the spread the mechanism predicts: well-attributed-but-uncategorized at one end, attribute-empty at the other. **No merchant data is required to answer this.** |
| Q-6b | **Remedy, and a real policy choice.** Should `uncategorized` products get an expanded Common Core, changing what is scored rather than measuring what is? Depends on Q-6a's answer and does not presuppose it. | Risks encouraging bad category hygiene, which is itself a real finding. It is also a scoring change, not an editorial one: `taxonomy.md` §3 puts the Common Core in D1/D5/D8 and *never* in D2, and §2 rule 3 with `rubric.md` §4/D2 remove D2 in full — so adopting it needs a taxonomy version bump (`taxonomy.md` §7), a `rubric_version` bump (D-023), and an expectation migration. Note the coupling to D-029: `taxonomy_data.variant_scope_keys` excludes the Common Core deliberately (its two non-inheritable variant-scope rows are already scored per variant, D-030). An expanded core that added a *new* non-inheritable variant-scope key routed into `uncategorized` would make `K` non-empty and stop D-029 case 2 firing. | Eval data on how often `uncategorized` occurs in real exports, and Q-6a answered first. |
| Q-7 | How should the tool treat merchant data that is stale rather than absent (a spec that no longer matches the shipped product)? | Undetectable without external state; possibly permanently out of scope. | Whether merchants report this as a felt problem. |
| Q-8 | Post-V0: do attribute keys map onto Shopify category metafields, and does that change tiering? | Requires taxonomy dependency V0 avoids (D-008). | Shopify taxonomy review at integration time. |
| Q-11 | `taxonomy.md` §2 rule 1 requires an `info` finding naming both signals when two same-tier signals disagree, but `rubric.md` §4 defines no `check_id` that could carry it. The engine records the disagreement as a `note` on the category block, serialized by `classify.Classification.as_dict`, rather than inventing a check id; the two disagreeing signals are quoted as that block's evidence, but the note is not additionally attached to those evidence items. | A check that is not in the rubric cannot have fixed points, severity or confidence, and adding one is a rubric change requiring a version bump. Nothing is lost meanwhile: the disagreement is reported, just not as a finding. | Either a `CATEGORY.*` check in `rubric.md` §4, or an explicit statement that the category block carries it. |
| Q-12 | Does a stated, non-placeholder structured value at a conditional attribute's own key establish that attribute's trigger? `taxonomy.md` §4.4 says a trigger is structural and never assumed; the engine currently defers every conditionally-triggered check, so three of them never run. | Deciding that absence of such a value establishes the trigger is *absent* would remove points from a denominator on an assumption. The presence half looks safe and the absence half is not, so the two need separating deliberately. | A decision record stating the presence half, with the absence half remaining deferred rather than `NOT_APPLICABLE`. |
| Q-13 | A predicate named as a disjunction has one decidable half and one that is language. Is firing on the decidable half alone faithful to the predicate as written? This covers **both arms**: the ambiguity arm ("no unit **or** no basis") and the **satisfying** arm — `warranty_with_duration_or_scope` is shipped and reaches `PASS` at the full 3.00 on a stated duration, with the scope disjunct never read. | A value with no unit satisfies the predicate whatever the basis half says, so the arm is provable — but the ambiguity keys carry `blocker` conflict severity, and the satisfying arm awards full credit, so both warrant sign-off rather than inference. The satisfying arm is the higher-stakes half and is already live, which is why it is named here rather than left implicit. | An explicit statement, per predicate and per arm, that a decidable half may decide alone — or a decision to defer `warranty_with_duration_or_scope` until the scope disjunct is readable. |
| Q-14 | Three D5 checks declare recognition predicates over attribute keys that `taxonomy.md` §3/§5 treats as presence. `TRUST.RETURNS_REFERENCE` in particular: §3 says *"a reference counts; the policy text need not be in the product record"*, which is presence, not recognition. | It reads as a specification inconsistency rather than a scoring judgment, but correcting it moves scores, so it cannot be done as an editorial fix. | A decision reclassifying the affected predicates as presence, with expectation files moving in the same commit under D-023. |
| Q-15 | `TRUST.SUPPORT_OR_CONTACT` and `TRUST.SHIPPING_OR_LEADTIME` declare prose-only `checked_paths`, so no structured value can ever reach a predicate for them. Should structured paths be added, or do they stay deferred until prose recognition exists? | Adding paths to a check's `checked_paths` changes what its absence evidence claims to have searched, which is an evidence-integrity change, not a convenience. | Either a registry change with expectation impact, or an explicit statement that they remain deferred. |
| Q-16 | `CONFLICT.UNIT_INCONSISTENCY` requires proving two values are the *same* quantity in different units, which needs a conversion table the engine deliberately does not hold. | A conversion table is the shortest path from "no world knowledge" to "some world knowledge" (D-006, non-negotiable 11), so the omission should be a recorded decision rather than a gap. | A decision to leave it unimplemented, or a bounded conversion table with its own record. |

---

## Sources

1. [Shopify Catalog and product discovery for agentic storefronts — Shopify Help Center](https://help.shopify.com/en/manual/online-sales-channels/agentic-storefronts/products)
2. [Shopify/product-taxonomy — GitHub](https://github.com/Shopify/product-taxonomy)
3. [Category metafields — Shopify Help Center](https://help.shopify.com/en/manual/custom-data/metafields/category-metafields)
