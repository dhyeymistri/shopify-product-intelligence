# AGENTS.md — Shopify Product Intelligence

Operating contract for anyone working in this repository, human or agent. Read this before touching anything.

**Current phase: P3 — checks and scoring. P0 (specification), P1 (fixtures + fabrication audit) and P2 (the normalizer) are complete.** See §6.

---

## 1. What this product is

A tool that audits ecommerce product data and reports, **with evidence**, whether that data is complete, consistent, structured, and useful enough for a human or an automated agent to understand, compare, and decide on the product.

V0 is a **local AI skill** that reads a local catalog file and writes local report files. It is not a Shopify app. It makes no network calls.

The eventual product is a Shopify mini-app. That is a destination, not a licence to build toward it now.

---

## 2. The one rule

> **NEVER INVENT PRODUCT FACTS.**

If the supplied data does not state a fact, report **UNKNOWN**. Not "no". Not "false". Not a plausible guess.

Three corollaries that decide most day-to-day questions:

1. **Absence is not negation.** No stated warranty means `warranty: UNKNOWN`, never "no warranty".
2. **The tool asks; it does not answer.** Remediation is a question to the merchant, never generated copy that supplies the missing fact.
3. **Every finding carries evidence** — including findings about absence, which must enumerate every path searched.

This rule outranks every other consideration in this repo, including completeness, output quality, elegance, and deadline. A report that is honest and incomplete is a success. A report that is complete and contains one invented fact is a product failure.

**If a change would make the tool more useful by loosening this rule, the change is rejected.** Do not propose it; do not implement it behind a flag.

---

## 3. Document map — read in this order

| File | What it governs | Authority |
| --- | --- | --- |
| [`product/PRD.md`](product/PRD.md) | Customer, problem, use case, input formats, NPR, output/finding schema, severity, confidence, evidence rules, handling rules, acceptance criteria, evaluation, non-goals | Authoritative for product scope and behavior |
| [`product/rubric.md`](product/rubric.md) | Dimensions, checks, points, severity/confidence assignment, score computation, worked example | Authoritative for scoring |
| [`product/taxonomy.md`](product/taxonomy.md) | The five categories, their attributes, tiers, scopes, inheritance, category mapping | Authoritative for category logic |
| [`product/decisions.md`](product/decisions.md) | Decision records with rationale, rejected alternatives, and open questions | Authoritative for *why* |

Conflicts resolve in that order, except that `rubric.md` wins over `PRD.md` on scoring specifics and `taxonomy.md` wins on attribute definitions.

**Before proposing a change, check `decisions.md`.** Several attractive ideas — Shopify integration, generated copy, model-assigned scores, penalizing absence, auto-resolving conflicts — were considered and rejected with reasons. Reopening one requires engaging with the recorded reasoning, not restating the idea.

---

## 4. Repository layout

```
product/          Specification. Authoritative. Change deliberately.
engine/           The product engine. P2: the normalizer — input → NPR, with
                  locators that resolve back to the input. Stdlib only.
skill/            The V0 skill (SKILL.md + supporting instructions). NOT YET WRITTEN.
evals/fixtures/   Input fixtures, by set (complete, sparse, conflict, claims,
                  variants, ambiguous, duplicates, adversarial), plus csv/ for
                  Format A inputs.
evals/expected/   Expected check outcomes per fixture.
evals/audits/     The fabrication audit. Verifies reports; NOT the product engine.
evals/testdata/   Hand-written report doubles: honest ones must pass, seeded ones must fail.
evals/tests/      Test suite. Run: cd evals && python3 -m unittest discover -s tests
reports/          Run output: reports/<run-id>/report.json + report.md. Gitignored output.
app/future-shopify-app/   Placeholder. Deliberately empty. Do not populate in V0.
```

---

## 5. Non-negotiables

Violating any of these is a defect regardless of how well the code works.

1. **No invented product facts.** §2.
2. **No finding without evidence.** A finding with an empty `evidence` array is dropped at report assembly and logged as a `run_error`. This is a structural gate, not a guideline.
3. **Absence evidence must enumerate `checked_paths`.** A claim that something is missing must show where it looked. A false gap is a `blocker`-severity bug.
4. **Quotes are byte-exact.** No paraphrase, no cleanup, no ellipsis-editing. If it cannot be reproduced from the input at its locator, the finding is invalid.
5. **Missing information never subtracts points.** `UNKNOWN` = 0 earned, 0 penalty. Only conflicts (D6) and unsupported claims (D7) penalize.
6. **`FAIL` requires something present to be wrong.** Absence is `UNKNOWN`. A check that emits `FAIL` on absence is a spec violation.
7. **The score is arithmetic.** No model-generated number enters the score path. The model determines status and evidence; points are fixed per check.
8. **No AI-ranking or visibility claims** in code, copy, docs, commit messages, or reports. We evaluate data sufficiency, not channel outcomes.
9. **No network calls in V0.** Not for verification, not for enrichment, not for taxonomy fetching. A referenced external source is *mentioned*, never fetched, never verified.
10. **The tool never picks a winner in a conflict.** Both values cited, no resolution asserted.
11. **World knowledge never contradicts a merchant-stated fact.** We audit internal integrity and sufficiency, not veracity about the world.
12. **`low` confidence never carries a penalty and never exceeds `minor` severity.**

---

## 6. Phase gates

| Phase | Status | Allowed |
| --- | --- | --- |
| P0 — Specification | Complete | Editing `product/*`, `AGENTS.md`, `README.md`. Writing fixtures. |
| P1 — Fixtures & audits | Complete | `evals/` corpus (10 sparse + 4 adversarial), the fabrication audit, its test suite. See [`evals/README.md`](evals/README.md). |
| P2 — Normalizer | Complete | Input → NPR, with locators. `engine/`. Formats A (Shopify CSV) and C (PIP JSON); Format B deferred. |
| **P3 — Checks & scoring** | **Current** | Check set, ledger, arithmetic scoring. |
| P4 — Reporting | Not started | `report.json` then `report.md` rendered from it. |
| P5 — Skill packaging | Not started | `skill/shopify-product-intelligence/SKILL.md`. |

**Do not skip ahead.** In particular, do not write checks before the fabrication audit exists — the audit is the definition of correctness, and building checks first means having no way to know they are honest. The audit now exists; every report the engine produces must be run through `evals/run_audits.py`, and a red audit blocks the change.

Nothing in `app/future-shopify-app/` is in scope. Do not add OAuth, API clients, billing, a web UI, a database, deployment config, or Shopify write operations. If a task seems to require one of these, it is out of V0 scope; say so instead of building it.

---

## 7. Working practices

### Shopify facts
- Use **primary sources only**: `shopify.dev`, `help.shopify.com`, `changelog.shopify.com`, and the official `Shopify/*` GitHub repos.
- **Never invent a Shopify API, field, limit, or capability.** The no-invention rule applies to Shopify facts exactly as it applies to product facts.
- Cite the URL in the document where the fact is used. Existing citations are in each document's Sources section.
- Shopify's platform changes. If a stated platform fact matters to a decision, re-verify it rather than trusting this repo's copy.

### Specification changes
- A scoring change bumps `rubric_version` and updates every affected expectation file **in the same commit**.
- A semantic change to scoring requires a new record in `decisions.md`.
- Attribute keys and `check_id`s are permanent identifiers. Renaming is a breaking change requiring expectation migration. Retired IDs stay reserved.
- Point totals must sum to 100. A change that breaks this is rejected at review.

### Adding a check
A new check needs all of: a stable namespaced `check_id`; explicit `checked_paths`; a fixed severity and confidence; a merchant-answerable question; and a fixture exercising **both** its pass and its fail path.

Two hard limits: a check that cannot produce evidence is not a check, and no check may score prose style, keyword density, or character counts. We measure information, not writing.

### Adding a category or attribute
Five categories is a hard cap for V0 (`decisions.md` D-008). A new attribute must be stated in real merchant data often enough to be checkable, must change a buying decision, must not reword an existing key, and must be answerable by a merchant without research.

### Fixtures
Synthetic or public-derived only. Never a real merchant's private data. Each fixture carries a provenance note. Fixtures are append-only; expectation files change with the rubric that moved them.

---

## 8. Definition of done

For a specification change: the four `product/` documents remain internally consistent, all cross-references resolve, every Shopify fact carries a primary-source citation, and any decision made is recorded in `decisions.md` with its rejected alternatives.

For an implementation change (P1+): the eval suite passes, including the fabrication audit, evidence-integrity audit, negation-language audit, claim-scope audit, determinism audit, and arithmetic audit; expectation files are updated in the same commit as any behavior change; and no non-negotiable in §5 is weakened.

---

## 9. If you are unsure

1. **Would this state a product fact the input does not contain?** → Stop. It is prohibited.
2. **Is this within the current phase gate?** → If not, say so rather than building it.
3. **Was this decided already?** → Check `decisions.md` before proposing.
4. **Is the answer genuinely underdetermined?** → Add it to the Open Questions table in `decisions.md` and proceed with the parts that do not depend on it, stating your assumption.

Do not resolve product ambiguity by guessing and shipping. That is the same failure as inventing a product fact, one level up.

---

## 10. Repository policy

**This repository is public. No open-source license has been granted.** Public visibility is not a licence grant: all rights are reserved unless the project owner states otherwise in writing.

### Licensing

- **Do not create a `LICENSE` file.**
- **Do not add MIT, Apache-2.0, GPL, BSD, or any other open-source or source-available licence**, in a file, a header, a package manifest, or a README badge, unless the project owner explicitly instructs it. "It is public so it should have a licence" is not that instruction.
- **Do not change repository visibility** in either direction.
- **Do not introduce third-party code or content with incompatible licensing.** Copied code, vendored files, fixture text lifted from another project, and generated content carrying an upstream licence all count. V0 is standard library only ([`decisions.md`](./decisions.md) D-001, D-006), which keeps this simple: the answer to "which dependency should we add?" is almost always none.

If a task appears to require a licence decision, say so and stop. It is the owner's call, and it is not reversible by a later commit — anything published under a permissive licence stays available under it.

### What may be public

- Specification, code, documentation, and the eval corpus. Fixtures are **synthetic or public-derived only** and each carries a provenance note (§7) — that rule is what makes the corpus safe to publish, so it is a licensing constraint as well as a data-quality one.
- Tests, expectation files, and report doubles, on the same basis.

### What must never be committed

Secrets, API keys, tokens, credentials, connection strings, private customer data, a real merchant's catalog or export, personal data of any kind, or internal material belonging to someone else. This holds regardless of file type, and regardless of whether the file is gitignored at the time — a gitignore entry is a convenience, not a control.

A secret that reaches a public repository is compromised the moment it lands. Deleting it in a later commit does not undo that: it remains in history, in forks, and in anything that mirrored the repository in between. If one is committed, say so immediately and treat the credential as burned — rotate it first, clean history second.
