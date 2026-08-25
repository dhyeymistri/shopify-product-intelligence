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

**One status is eliminated by authority before the question is reached.** `rubric.md` §3.1 defines `UNKNOWN` as *"Not found in any `checked_paths`."* With `K` empty, `variants[*].attributes` may be fully populated and nothing was "not found". `UNKNOWN` would misdescribe the record whichever way the rest is decided, so the live alternatives are `NOT_APPLICABLE` and deferral only.

**Decision: `NOT_APPLICABLE` in both cases, with a distinct reason string for each.** The check leaves the numerator and the denominator, and §6.3 renormalization follows.

**Case 1 — an assigned category whose `K` is empty.** Purely structural. `K` is empty as a fact about [`taxonomy.md`](./taxonomy.md) §5, fully determined from the taxonomy alone, with nothing missing from the merchant's record. PRD §10.3's prohibition — *"A check is never N/A because the information is missing"* — has no purchase on it: no information is missing. This is `taxonomy.md` §4.4's structural trigger in its plainest form.

*Currently unreachable, and stated anyway.* Every one of the five categories holds at least two non-inheritable variant-scope attributes (`apparel` 3, `beauty` 3, `electronics` 3, `home` 2, `sports` 2), so this branch moves no score today. It is written because the alternative is an unwritten branch that decides a score the first time a taxonomy edit reaches it.

**Case 2 — `uncategorized`.** `K` is empty because the record carries no category, and that *is* traceable to missing merchant data. This is the harder half and it is decided on an existing precedent rather than on a fresh judgment: `rubric.md` §4/D2 and `taxonomy.md` §2 rule 3 already settle the identical question one dimension over — for `uncategorized`, *"D2 is removed in full: its maximum is 0 and it leaves both the numerator and the denominator."* Twenty-two points of category-derived scoring are removed for exactly this reason. Retaining 3.0 points of D3 for the same missing field, in the same report, would be an inconsistency with no rule behind it.

**Engaging PRD §10.3 directly, because this case is what it warns about.** What is removed here is not a gap in the merchant's variant data — it is a requirement that was never posed. `rubric.md` §4/D3 conditions the requirement on the category (*"for the category"*), and with no category there is no set of attributes the variants could have failed to carry. Scoring 0 of 3.0 would charge the merchant for failing a test the rubric never wrote. The missing category itself is charged, once, where the rubric puts it: `IDENT.PRODUCT_TYPE_OR_CATEGORY` at 2.5 with `UNKNOWN` → `major`, plus `taxonomy.md` §2 rule 4's `minor` finding recommending the category be set. The merchant is told, and told once.

**Renormalization consequences, stated rather than left to be discovered.**

- The check's `max_points` leaves `max_applicable` (`checks.not_applicable` emits `max_points = 0`), so D3's applicable maximum falls from 15.0 to 12.0 for an affected multi-variant product, and the reported total is renormalized to 100 by `rubric.md` §6.3 with the factor printed.
- The effect is **not** a uniform gain. Renormalization redistributes weight across the checks that remain; whether an `uncategorized` product scores higher or lower than it would have depends on how it performs on those. For a product that would have earned 0 of 3.0 here, removal is favourable; for one that would have earned the full 3.0, it is not.
- On a **single-variant** product nothing changes: `NA_SINGLE_VARIANT` already removes this check, and the two triggers agree.
- The aggregate question — whether `uncategorized` products end up deflated or flattered once D2's 22 points and this 3.0 are both removed — is **Q-6**, and this record does not answer it. What this record fixes is that the two removals are decided the same way for the same reason.

**Rejected: deferral (the check emits nothing, keeps 3.0 in the denominator, earns 0).** Defensible, and it is the reading PRD §10.3 argues for if "missing" is followed one indirection back to the absent category. It was rejected because it makes the two removals inconsistent for the same missing field, and because a silent 0 of 3.0 tells the merchant nothing — the `NOT_APPLICABLE` finding states the reason where they can read it. Note that both options earn exactly 0.00; the disagreement is about the denominator and about what the report says, not about earned points.

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
