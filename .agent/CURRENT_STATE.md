# CURRENT STATE — Verified Checkpoint

**Status of this file: orchestration/context aid only. Not authoritative.**
It is a snapshot of the repository, taken at the checkpoint named below and
verified against the repository at that moment. It goes stale. Re-verify
before relying on any number here. Where it disagrees with an authoritative
source or with the code, the authoritative source or the code wins and the
disagreement is reported.

---

## 1. Checkpoint

| Field | Value |
| --- | --- |
| Repository | `dhyeymistri/shopify-product-intelligence` |
| Branch | `main` |
| HEAD | `4beda15` — *Implement Beauty actives concentration recognition* |
| Working tree at capture | clean |
| Date captured | 2026-08-27 |

## 2. Verified test and audit state

- `cd evals && python3 -m unittest discover -s tests` → **509 tests, OK** (green).
- `python3 evals/run_audits.py --self-test` → **0 unexpected outcomes across
  all audits**. The self-test exercises four audit families: fabrication,
  arithmetic, negation-language, and claim-scope.

## 3. Versions as established by the repository at this checkpoint

Read from the code and from `product/`, not asserted by this file.

| Identifier | Value | Source |
| --- | --- | --- |
| `RUBRIC_VERSION` | `0.12` | `engine/rubric_data.py` |
| Rubric document version | `0.12` | `product/rubric.md` header |
| `LEXICON_VERSION` | `0.12` | `engine/lexicon.py` (asserted equal to `RUBRIC_VERSION` at import, D-022) |
| `REGISTRY_VERSION` | `0.12` | `engine/registry.py` |
| `PINNED_RUBRIC_VERSION` | `0.12` | `evals/measure/q6a.py` |
| `NPR_VERSION` | `0.2` | `engine/model.py` |
| `TAXONOMY_VERSION` | `0.1` | `engine/taxonomy_data.py` |
| Taxonomy document version | `0.1` | `product/taxonomy.md` header |
| PRD spec version | `0.1.1` | `product/PRD.md` header |

Recognition predicate coverage at this checkpoint, measured from the registry:

- `RECOGNITION_PREDICATES` declared: **116**
- `IMPLEMENTED_PREDICATES` (value predicates): **31**
- `IMPLEMENTED_RELATIONS`: **2** (`title_names_product_type`,
  `title_carries_distinguishing_attribute`)

## 4. D-038 and the completed recognition slices

**D-038 is complete.** `product/decisions.md` D-038 governs
`BEAUTY.key_actives_and_concentration`; the implementation landed at HEAD
(`4beda15`) and carried `RUBRIC_VERSION`/`LEXICON_VERSION`/`REGISTRY_VERSION`
to `0.12` together with `q6a.PINNED_RUBRIC_VERSION`, per D-038 item 12.

Slices landed, as recorded in `product/rubric.md`'s version history (that
document is the authority; this is a restatement):

| Rubric version | Slice |
| --- | --- |
| `0.2` | First deterministic recognition predicates |
| `0.3` | P3.2 review decisions (D-024, D-025, D-026, D-027) |
| `0.4` | P3.2 slice D — D3 structural variant checks (D-029, D-030, D-031) |
| `0.5` | Format C option-locator conformance repair (D-032) |
| `0.6` | `variants[*].option_values` carries `{value, src}` pairs (D-033); `npr_version` → `0.2` |
| `0.7` | `unnamed_color_group` for `APPAREL.COLOR_FINISH` (D-034) |
| `0.8` | `number_without_unit_or_basis`, "no unit" sub-case only (D-035) |
| `0.9` | `care_method_stated`, `use_context_stated` (D-036) |
| `0.10` | `rated_load_with_units` (D-035) |
| `0.11` | `environment_stated`, closed `SPORTS_ENVIRONMENTS` vocabulary (D-037) |
| `0.12` | `actives_with_concentration`, `actives_without_concentration` (D-038) |

Not built at this checkpoint: the penalty families (D6 conflicts, D7 claim
substantiation), prose recognition, the aggregate score
(`engine/runner.py` computes no total by design), P4 reporting, and P5 skill
packaging (`skill/shopify-product-intelligence/SKILL.md` is an empty file).

## 5. Separately open governance issues

These are open in the authoritative repository and are **not** part of any
current task. Each is listed with where it lives.

Open questions in `product/decisions.md`:

- **Q-1** multi-locale catalogs. **Q-2** market-specific price/availability.
  **Q-3** bundles and combined listings. **Q-4** raw score vs banded grade.
  **Q-5** batch ceiling and catalog-level reporting.
- **Q-6a** whether `uncategorized` products are deflated or flattered in
  aggregate — blocked on P4 landing a score and on an adequate
  `uncategorized` fixture set. **Q-6b** the remedy, a real policy choice.
- **Q-7** stale-rather-than-absent merchant data. **Q-8** post-V0 mapping of
  attribute keys onto Shopify category metafields.
- **Q-11** `taxonomy.md` §2 rule 1 requires an `info` finding for
  same-tier signal disagreement, but `rubric.md` §4 defines no `check_id`
  that could carry it; the engine records a `note` on the category block.
- **Q-12** whether a stated structured value at a conditional attribute's own
  key establishes that attribute's trigger.
- **Q-13** whether a predicate named as a disjunction may fire on its
  decidable half alone — covering both the ambiguity arm
  (`number_without_unit_or_basis`) and the already-shipped satisfying arm
  (`warranty_with_duration_or_scope`). D-038 §7 explicitly does **not**
  resolve it.
- **Q-14** three D5 checks declare recognition predicates over attribute keys
  the taxonomy treats as presence.
- **Q-15** `TRUST.SUPPORT_OR_CONTACT` and `TRUST.SHIPPING_OR_LEADTIME` declare
  prose-only `checked_paths`, so no structured value can reach a predicate.
- **Q-16** `CONFLICT.UNIT_INCONSISTENCY` needs a conversion table the engine
  deliberately does not hold.

Deferred by decision, not defects:

- **D-027** `unnamed_eco_claim` is withdrawn until its D7 route exists. An
  evaluator function of that name exists in `engine/recognize.py` and is not
  registered.
- **D-034** `named_color_per_variant` remains permanently deferred; a positive
  named-colour lexicon would enumerate product facts (D-022).
- **D-035** the "no basis" half of `number_without_unit_or_basis` is not
  implemented.

## 6. Known baseline / documentation inconsistencies

Observed at this checkpoint, **unverified as to intent**, and recorded so they
are visible rather than silent.

1. **`AGENTS.md` line 7 states `rubric_version` is `0.6`.** The rubric
   document and `engine/rubric_data.RUBRIC_VERSION` are both `0.12`. The
   `AGENTS.md` figure appears not to have moved with slices `0.7`–`0.12`.
2. **`AGENTS.md` §6 states "P3.2 has landed 27 of the 116 declared recognition
   predicates".** The registry at this checkpoint reports 31 implemented value
   predicates plus 2 relations against 116 declared. The `116` matches; the
   `27` does not.
3. **`README.md` states "Status: V0 specification. No implementation yet."**
   `engine/` and `evals/` are implemented and 509 tests pass.
4. **`evals/expected/monotonicity_baseline.json` carries
   `"baseline_version": "0.6"`** while its own `phase` and `repin` fields
   describe re-pinning through D-035/D-037/D-038. No test reads
   `baseline_version`. Whether the field is meant to track the rubric or to
   record the last membership re-pin is not stated anywhere I could find.
5. **`product/PRD.md` §6 and §7 example payloads show `"npr_version": "0.1"` and
   `"rubric_version": "0.3"`.** These read as illustrative examples rather
   than normative version declarations; whether they are meant to be kept
   current is not stated.

**These issues must not be silently repaired during unrelated work.** Each
one, if real, is a governance or documentation change with its own
authorization: a stale version figure in `AGENTS.md` is a governance edit, a
baseline field is an eval-contract edit, and both are exactly the class of
change `.agent/RULES.md` §2 rule 5 forbids as a side effect. Repairing any of
them is a separate task a human must authorize in `.agent/QUEUE.md`, and each
must be re-verified against the repository before it is treated as real —
this file is not evidence.
