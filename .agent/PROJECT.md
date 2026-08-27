# PROJECT — Repository Control Plane

**Status of this file: orchestration/context aid only. Not authoritative.**
It summarizes the repository for agent orientation. It does not govern the
product, the scoring function, or the operating contract. Where it disagrees
with an authoritative source, the authoritative source wins and the
disagreement is reported, never silently reconciled.

---

## 1. Repository identity

- **Repository:** `dhyeymistri/shopify-product-intelligence`
- **Default branch:** `main`
- **Visibility:** public, **no open-source licence granted** (`AGENTS.md` §10).
  All rights reserved. Do not add a `LICENSE`, a licence header, or a badge.
- **Dependencies:** Python standard library only (`decisions.md` D-001, D-006).
- **Test entry point:** `cd evals && python3 -m unittest discover -s tests`
- **Audit entry point:** `python3 evals/run_audits.py --self-test`, and
  `--report/--fixture` for a real report.

## 2. Current product purpose

A tool that audits ecommerce product data and reports, **with evidence**,
whether that data is complete, consistent, structured, and useful enough for a
human or an automated agent to understand, compare, and decide on the product.

The governing rule is `AGENTS.md` §2: **never invent product facts.** Absence
is `UNKNOWN`, never "no". Every finding carries evidence. The tool asks
questions; it does not supply the missing fact.

V0 is a **local AI skill** reading a local catalog file and writing local
report files. It is not a Shopify app and makes no network calls
(`decisions.md` D-001).

## 3. Current development phase

Phase **P3 — checks and scoring** (`AGENTS.md` §6).

- P0 specification, P1 fixtures + fabrication audit, P2 normalizer: complete.
- P3.1 (check registry, finding contract, deterministic check runner): done.
- P3.2 (recognition predicates): in progress, landing one coherent slice at a
  time. Penalty families, prose recognition and the aggregate score are not
  built.
- P4 reporting: not started. `report.json` / `report.md` do not exist.
- P5 skill packaging: not started.
  `skill/shopify-product-intelligence/SKILL.md` is an empty file.
- `app/future-shopify-app/` is deliberately empty and out of V0 scope.

Precise version and slice state lives in `.agent/CURRENT_STATE.md`, and is
itself a restatement of the repository, not a source of truth.

## 4. Authority hierarchy

Authoritative, in this order:

1. `AGENTS.md` — operating contract, non-negotiables, phase gates, repository
   policy.
2. `product/PRD.md` — product scope, input formats, NPR, output/finding
   schema, severity, confidence, evidence rules, acceptance criteria.
3. `product/rubric.md` — scoring. Wins over `PRD.md` on scoring specifics.
4. `product/taxonomy.md` — category logic. Wins over `PRD.md` and `rubric.md`
   on attribute definitions.
5. `product/decisions.md` — authoritative for *why*, and for what was already
   rejected.
6. **The actual source code** under `engine/`, and **the actual tests** and
   expectation files under `evals/`.

Below all of that, non-authoritative:

7. `.agent/*` — this control plane. Orchestration and context only.

Rules that follow from the ordering:

- A `.agent/` file may **never** override, reinterpret, soften, extend, or
  "clarify" an authoritative source.
- If a `.agent/` statement conflicts with an authoritative source, the
  authoritative source wins, the `.agent/` statement is wrong, and the
  conflict is **reported to the human** rather than silently resolved in
  either direction.
- Editing an authoritative document to agree with a `.agent/` file is
  prohibited. Governance changes are their own authorized task
  (`AGENTS.md` §7, `decisions.md`).

`P3.2-PLAN.md` and `product/P3-plan.md` are planning documents, not authority.
They record intent that the four `product/` documents and `AGENTS.md` may have
since superseded.

## 5. Larger project context

Stated by the project owner as the surrounding direction. **None of it is
recorded in the authoritative repository documents, and none of it authorizes
work here.**

- This repository is one component of a larger **AI Client OS** goal: a system
  that generates and operates **skills**, of which the eventual **Shopify
  mini-app** is a downstream destination.
- The V0 deliverable that connects this repository to that goal is the skill
  package in `skill/` (P5) — a local, evidence-bound audit skill. That is the
  seam.
- `AGENTS.md` §1 already states the repository's own position on the
  destination: *"The eventual product is a Shopify mini-app. That is a
  destination, not a licence to build toward it now."* §6 forbids anything in
  `app/future-shopify-app/`: no OAuth, API clients, billing, web UI, database,
  deployment config, or Shopify write operations.
- Therefore the larger goal changes **nothing** about what may be built in
  this repository today. It explains why the repository exists; it grants no
  scope.
