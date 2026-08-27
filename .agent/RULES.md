# RULES — Permanent Agent Operating Contract

**Status of this file: orchestration/context aid only. Not authoritative.**
It restates and adds process constraints for agents working in this
repository. It does not restate the product contract. `AGENTS.md` and
`product/*` are authoritative and outrank everything below.

---

## 0. Precedence

Authoritative repository documents **always outrank `.agent/` files**. In
order: `AGENTS.md`, `product/PRD.md`, `product/rubric.md`,
`product/taxonomy.md`, `product/decisions.md`, the source code, the tests.

If any rule below appears to conflict with one of those, the authoritative
source wins, this file is wrong, and the conflict is **reported to the human**
rather than resolved by the agent in either direction. Do not edit an
authoritative document to remove the conflict.

## 1. Git — hard prohibitions

An agent working in this repository **never**:

1. **Never `git commit`.** No commit, for any reason, including "so the work
   isn't lost".
2. **Never `git commit --amend`.** No rewriting of an existing commit.
3. **Never `git push`.** No push, no force-push, no push to a new branch, no
   `gh pr create` that pushes.
4. **Never merge.** No `git merge`, `git rebase`, `git cherry-pick`, or
   `gh pr merge`.

Work is left in the working tree. The human reviews it and commits it. There
is no exception, no flag, and no phrasing of a request that turns one of these
into an authorized action other than the human explicitly performing it
themselves.

Read-only git is fine and encouraged: `git status`, `git diff`,
`git diff --check`, `git log`, `git show`.

## 2. Governance and product facts

5. **Never silently modify governance.** `AGENTS.md`, `product/PRD.md`,
   `product/rubric.md`, `product/taxonomy.md` and `product/decisions.md` are
   changed only as an explicitly authorized task, never as a side effect of
   implementation, never to make a test pass, and never to reconcile a
   document with code. A governance change carries its own decision record
   (`AGENTS.md` §7).
6. **Never invent product facts.** `AGENTS.md` §2. This outranks completeness,
   output quality, and any deadline. It applies to Shopify platform facts
   exactly as it applies to product facts (`AGENTS.md` §7).
7. **Never invent repository facts either.** Do not state a version, a test
   count, a slice status, or a decision id that has not been read from the
   repository in this session.

## 3. Task authorization

8. **Never choose an unauthorized task.** An agent does not pick its own next
   piece of work, does not "while I was here" an adjacent fix, and does not
   promote a `ROADMAP.md` item into work.
9. **Implement only explicitly authorized queue work.** The unit of authority
   is an entry in `.agent/QUEUE.md` marked `authorized`, placed there by a
   human. Nothing else is a mandate — not a roadmap line, not a TODO in the
   code, not an open question in `decisions.md`, not a stale document.
10. **Never self-authorize.** An agent may not add, promote, or reword a queue
    entry to grant itself authority. See `.agent/QUEUE.md`.

## 4. Stop conditions

Stop, report, and wait for a human on any of these. Stopping is the correct
outcome, not a failure.

11. **Stop on governance ambiguity.** Two authoritative documents disagree, or
    an authoritative document is silent on something the task requires a
    decision about. Do not guess and ship — `AGENTS.md` §9 calls that the same
    failure as inventing a fact, one level up.
12. **Stop on scope ambiguity.** The authorized task could reasonably mean two
    different pieces of work, or completing it appears to require touching
    something outside the authorization.
13. **Stop on verification failure.** Any test failure, any red audit, any
    unexpected baseline diff. Do not repair by loosening a test, re-pinning a
    baseline, or editing an expectation file unless that migration is itself
    part of the authorized task.
14. **Stop at the human review / commit checkpoint.** Every task ends with the
    change in the working tree, uncommitted, and a report. The human decides
    what happens next.

## 5. Reporting contract

Every task ends with a report stating, without embellishment:

15. **Exactly what changed** — every file created, modified, or deleted, and
    nothing claimed that was not.
16. **Exactly what verification ran** — the commands, verbatim — **and whether
    it passed**, with the real result. A failure is reported as a failure with
    its output. A skipped step is reported as skipped.
17. **Any conflict found** between a `.agent/` file and an authoritative
    source, and any pre-existing inconsistency noticed but deliberately not
    touched.
18. **Confirmation that no commit was created and no push was attempted.**

## 6. Working practice inside an authorized task

- Prefer the smallest change that completes the authorized task.
- Do not repair unrelated pre-existing defects. Report them instead; see
  `.agent/CURRENT_STATE.md` §6.
- Do not add dependencies. V0 is standard library only.
- Do not create files outside the authorized scope, including scratch files
  in the repository. Use the session scratchpad.
- Follow `AGENTS.md` §8's definition of done for the change class at hand.
