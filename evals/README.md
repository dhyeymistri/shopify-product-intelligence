# Evaluation corpus and audits (P1)

Phase P1 of [`AGENTS.md`](../AGENTS.md): the fixture corpus and the fabrication audit.

**Nothing here is the product's audit engine.** The engine lives in `engine/`;
the normalizer (P2) is built, the check and scoring engine (P3) is not. What
lives here is the *verifier* — the thing that tells us whether the engine is
honest. It resolves locators with its own implementation of the PRD §8.2.1
grammar rather than the engine's, deliberately: an audit that shared the
engine's resolver could not catch a bug in it, because the error would cancel
out on both sides.

## Why this was built first

The fabrication audit is the operational definition of the core principle
(`AGENTS.md` §2). Building checks before it would mean having no way to know
whether their output is honest — you would be testing that reports *look* right.

It has already earned its place: it caught five bad character offsets in the very
fixtures written for it, one stale offset in an expectation file, and one
false-positive class in its own bait matching. See "What it caught" below.

## Layout

```
fixtures/sparse/         10 products, realistic data gaps, one file per product
fixtures/adversarial/     4 products designed to bait invention
fixtures/checks/          8 products exercising the deterministic check layer:
                          presence, absence, conflict, coverage, scope, and the
                          one shape where a value is present and wrong
fixtures/recognition/     8 products exercising the deterministic recognition
                          predicates: each satisfying arm, each ambiguity arm,
                          and the two shapes that must stay silent
fixtures/csv/             Format A (Shopify product CSV) inputs for the normalizer
expected/<set>/           one expectation per fixture (same id, .expected.json)
audits/                   the audit implementation
testdata/reports/honest/      hand-written reports that MUST audit clean
testdata/reports/violations/  one seeded defect each; each MUST be caught
tests/                    unittest suite (stdlib only, no dependencies), covering
                          both the audits and engine/ (P2)
harness.py                projects engine output into the report.json shape so
                          the audits can run against it before P4 writes reports
run_audits.py             CLI / CI gate
```

## The audits run against real engine output

`tests/test_engine_audits.py` puts every fixture through the engine and through
the fabrication, negation-language and claim-scope audits. That is `AGENTS.md`
§6's rule — *a red audit blocks the change* — as a test rather than as a habit,
and it is the only gate that checks what the engine actually emits rather than a
double someone wrote by hand.

The arithmetic audit's whole-score stages are not run there yet, because this
phase computes no score. Its per-finding stage is: points-per-status is settled
by `rubric.md` §3.1 and is exactly what the check layer decides.

## Running

```bash
python3 evals/run_audits.py --self-test                   # audit the bundled doubles
cd evals && python3 -m unittest discover -s tests -v      # full suite
python3 evals/run_audits.py --report R.json --fixture F.pip.json \
                            --expected E.expected.json --markdown R.md --json
```

Exit status is 0 only when every audited artifact is clean, so `run_audits.py`
works directly as a CI gate. Python 3.9+, standard library only — consistent with
the no-network, no-dependency posture of V0 (`decisions.md` D-001, D-006).

## Fixture format

Fixtures are PIP JSON (PRD §5.3) — records already shaped like the Normalized
Product Record (PRD §6.1) — inside a thin envelope carrying the provenance note
that PRD §12.1 requires:

```jsonc
{
  "pip_version": "0.1",
  "fixture": { "id": "...", "set": "...", "intent": "...", "provenance": "...", "notes": "..." },
  "products": [ /* NPR-shaped records: the PIP payload proper */ ]
}
```

**The envelope is not input**, and PRD §5.3.1 makes that normative: the envelope
is not product evidence, the provenance index excludes it, bait descriptions are
never product facts, and the envelope cannot satisfy an evidence requirement.

The reason it matters: `intent` and `notes` describe the baits in plain language.
If they leaked into the provenance index, a report asserting a baited value would
audit clean — our own description of the trap would excuse falling into it.
`ProvenanceIndex` therefore takes a product, never a fixture document, so the
mistake is hard to make rather than merely discouraged. Two tests hold the line:
one asserts the isolation, one proves a fact appearing only in the envelope
cannot satisfy a finding.

## PIP locator grammar

**Defined normatively in PRD §8.2.1.** That section is the single authoritative
definition of locator syntax for every input format; this document does not
restate it. `audits/pip_locator.py` implements it.

## Expectation files

Per PRD §12.2, plus two fields that make expectations executable today:

- `must_not_fabricate` — values that must never appear in a report about this
  product. Drives `FAB014`. Every bait is verified absent from its own fixture,
  because a bait that is actually present would make the audit fire on honest
  reports.
- `critical_invariant` / `placeholder_invariant` / `injection_invariant` — named
  rules with the spec clause they enforce.

`status_coverage` is `"partial"`: expectations assert the checks each fixture was
built to exercise plus corpus-wide invariants. The exhaustive per-check status map
is completed in P3 when the check registry exists. **Fields asserted today are
final and must not be relaxed to make an implementation pass** (PRD §12.5).

## Violation codes

| Code | Detects | Stage |
| --- | --- | --- |
| `FAB000_UNKNOWN_PRODUCT` | report describes a product the fixture does not contain | 1 |
| `FAB001_EMPTY_EVIDENCE` | finding with no evidence (PRD §8.3 rule 1) | 1 |
| `FAB002_INVALID_LOCATOR` | locator does not resolve against the input | 1 |
| `FAB003_NON_REPRODUCIBLE_QUOTE` | excerpt is not byte-exact at its locator (§8.3 rule 4) | 1 |
| `FAB004_FABRICATED_MODEL_NUMBER` | model-shaped string absent from input | 2 |
| `FAB005_FABRICATED_SPECIFICATION` | quantity, duration or percentage absent from input | 2 |
| `FAB006_INVENTED_MATERIAL` | material or ingredient absent from input | 2 |
| `FAB007_INVENTED_COMPATIBILITY` | device, OS or interface absent from input | 2 |
| `FAB008_INVENTED_DIMENSION` | dimensions absent from input | 2 |
| `FAB009_INVENTED_SAFETY_CLAIM` | safety claim or standard absent from input | 2 |
| `FAB010_INVENTED_USE_CASE` | use case asserted that the input does not state | 2 |
| `FAB011_MISSING_CHECKED_PATHS` | absence evidence that does not say where it looked | 1 |
| `FAB012_FALSE_GAP` | claims a value is missing that the input supplies (§8.3 rule 5) | 1 |
| `FAB013_SUGGESTED_VALUE_IN_QUESTION` | merchant question introduces a value absent from input (PRD §7.6) | 3 |
| `FAB014_KNOWN_BAIT_EMITTED` | a value the fixture declares must never be fabricated | 4 |

Stage 1 runs first because a fact cannot be checked for traceability if its
evidence does not resolve at all.

## How the fact scan avoids being noise

An honest report is full of prose. Demanding that every word trace to input would
flag "Not stated in the supplied data" and make the audit useless. So only
**fact-bearing** tokens are checked, on two rules:

1. **Specific, never generic.** `cotton` is a material assertion; `fabric` is not.
   `EN 1078` is a standard; `certification` is not. A report must be able to name
   what it is *asking for* without being accused of asserting it.
2. **The allowlist holds structural vocabulary only** — check IDs, attribute keys,
   statuses, fixed spec phrases. Never a product value. A value clears the audit
   only by being traceable, never by being listed.
   `factlex.assert_allowlist_has_no_values()` enforces this and is called by the
   suite: it is the one way this module could fail open.

Unclassified report fields are scanned rather than skipped — the audit fails
closed, so a field nobody thought about does not become a blind spot.

## What it caught while being built

Recorded because each is evidence the gate works, and each would otherwise have
shipped silently:

1. **Five wrong character offsets** in the fixtures written for this corpus. Every
   `src` span had been written by hand; the resolver rejected them on first run.
2. **A stale offset in an expectation file** — written before the fixture offsets
   were corrected. Caught by the test asserting that expectation spans match the
   fixture's own declared sources, not merely that they resolve.
3. **Unaudited category evidence.** The audit initially checked evidence only
   inside `findings`, leaving classification evidence unverified. Now held to the
   same standard.
4. **A false-positive class in bait matching.** Substring matching let the bait
   `CE` match inside "certificate" and `certified` match an honest question
   asking which standard a helmet is certified to. Fixed by word-boundary
   matching, and by the rule that a bait must name a *value*, not a verb. A
   regression test runs every bait in the corpus against the honest reports.

5. **Two enforcement gaps in PRD §7.6**, found when the amendment added its
   regression tests. `such as machine wash cold` contains no token in any
   lexicon, and so passed a purely pattern-based scan. Fixed by adding a
   *structural* rule: an example frame inside a question is by construction
   introducing an illustration, so if the illustrated phrase is not in the
   supplied data it is an invented value — whatever vocabulary it uses. This is
   lexicon-independent, and it is a concrete instance of the recall limit
   recorded in `decisions.md` D-017.

## Adding a fixture

Fixtures are append-only (PRD §12.5). A new one needs: a synthetic provenance
note, an `intent`, an expectation file with the same id, at least one declared
bait, and `src` locators that resolve. `tests/test_fixtures.py` enforces all of
it — run the suite before committing.
