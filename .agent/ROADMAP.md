# ROADMAP — Approved Development Direction

**Status of this file: orchestration/context aid only. Not authoritative, and
not an authorization.**

> **Nothing in this file authorizes any work.** A roadmap describes direction.
> Authority to act comes only from a human-placed `authorized` entry in
> `.agent/QUEUE.md`. An agent that reads a line here and starts building it
> has violated `.agent/RULES.md` §3.

Where this file disagrees with `AGENTS.md` §6's phase gates, the phase gates
win and the disagreement is reported.

---

## 1. How recognition work proceeds

**One coherent slice at a time.** A slice is a single check, or a tightly
related pair of arms on one check, taken from declaration through to a green
corpus in one working-tree change. The pattern the repository has followed
through rubric `0.7`–`0.12` is the pattern to keep:

1. A governance decision record exists first where one is required, and fixes
   the predicate's boundary exactly (D-034, D-035, D-036, D-037, D-038 are the
   worked examples).
2. The implementation lands the evaluator, its registration, and the version
   bump `RUBRIC_VERSION` / `LEXICON_VERSION` / `REGISTRY_VERSION` /
   `q6a.PINNED_RUBRIC_VERSION` moved together (D-023).
3. Fixtures exercise the satisfying arm, the ambiguity arm, and the
   `UNDECIDED` residue where one exists.
4. Every affected expectation file migrates in the same change.
5. The monotonicity baseline moves only where the recognition contract permits
   it, and a re-pin is named, never wildcarded.

**Governance precedes implementation where required.** A predicate whose
boundary is not already fixed by an accepted decision record is not
implementable; the governance step is its own separate slice, and it changes
no code, no version, no fixture and no baseline.

## 2. Remaining product direction inside V0

Stated as direction, in the order `AGENTS.md` §6 gates them. Not a schedule
and not a mandate.

- **P3.2 continued** — further recognition slices against the 116 declared
  predicates, each on the pattern above.
- **P3 remainder** — the penalty families (D6 factual consistency, D7 claim
  substantiation) and the arithmetic aggregate score. `engine/runner.py`
  computes no total today, which is what leaves Q-6a unanswerable.
- **P4 — reporting.** `report.json` first, `report.md` rendered from it.
- **P5 — skill packaging.** `skill/shopify-product-intelligence/SKILL.md`.
  This is the artifact that connects the repository to the larger skills goal.

Out of scope for V0, unchanged: anything in `app/future-shopify-app/` — OAuth,
API clients, billing, web UI, database, deployment config, Shopify write
operations (`AGENTS.md` §6).

## 3. The automation / control-plane layer

This `.agent/` directory is the first step of it. The direction, stated as
direction:

- Build the control-plane layer that makes agent work in this repository
  legible and bounded: an explicit project context, an explicit operating
  contract, a verified state snapshot, and a human-owned task queue.
- Eventually support an automated loop of roughly this shape:

  **GitHub Actions → OpenCode → a free or low-cost model → verification →
  human review.**

  The properties that matter more than the components: the model receives one
  explicitly authorized task and no discretion to pick another; verification
  is the repository's own suite and audits, run unmodified; and the loop
  terminates at a human review checkpoint with the change uncommitted.
- Every constraint in `.agent/RULES.md` holds inside that loop exactly as it
  holds in an interactive session. Automation is not an exception to "never
  commit, never push, never merge" — it is the reason those rules are written
  down.
- Note the standing constraint: `AGENTS.md` §5 non-negotiable 9 forbids
  network calls **in the product engine in V0**. CI infrastructure is not the
  V0 engine, but nothing in that loop may put a network call on the audit
  path.

## 4. The larger goal

**AI Client OS → generate skills → Shopify mini-app.** This is the owner's
stated surrounding direction. It is not recorded in the authoritative
repository documents, and it grants no scope here. `AGENTS.md` §1 states the
repository's own position: the mini-app *"is a destination, not a licence to
build toward it now."*

## 5. What this roadmap is not

- Not a queue. The queue is `.agent/QUEUE.md`.
- Not an authorization, individually or in aggregate. Reading an item here and
  beginning it is prohibited.
- Not a commitment to order. A human may authorize items in any order, or
  none.
- Not a place to record decisions. Decisions live in `product/decisions.md`.
