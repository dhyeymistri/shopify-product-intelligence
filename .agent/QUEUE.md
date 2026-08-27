# QUEUE — Task Authorization

**Status of this file: orchestration/context aid only. Not authoritative over
the product.** It is, however, the **only** source of an agent's authority to
act in this repository. No queue entry, no work.

---

## 1. The authorization rule

> **Only a human may authorize a task.**
>
> **An agent may not rewrite this queue to grant itself authorization.**

Concretely, an agent may **not**:

- add an entry in any state;
- promote an entry from `proposed` to `authorized`;
- reword an entry to widen what it covers;
- re-open a `completed` or `blocked` entry;
- treat a line in `.agent/ROADMAP.md`, a TODO in the code, an open question in
  `product/decisions.md`, a stale document, or a failing expectation as an
  authorization;
- treat "the obvious next slice" as authorized because the previous one is
  done.

An agent **may**, when explicitly asked to by a human, draft an entry in the
`proposed` state and say so plainly. Drafting a proposal is not authorization,
and the agent does not then act on it.

If an authorized task turns out to require work the entry does not cover, the
agent **stops** and reports (`.agent/RULES.md` §4). It does not extend the
entry.

## 2. States

| State | Meaning | Who may set it |
| --- | --- | --- |
| `proposed` | A candidate task. Described, not approved. Confers **no** authority. An agent may draft one only when asked, and never acts on it. | Human, or an agent drafting at a human's request |
| `authorized` | A human has approved exactly this task. This is the **only** state that permits an agent to change repository files. | **Human only** |
| `running` | An agent has begun the authorized task. Set when work starts, so a second agent does not pick up the same entry. | Agent, on an entry already `authorized` |
| `ready_for_review` | The agent finished, the change is in the working tree **uncommitted**, verification ran, and the report is delivered. This is where every agent task ends. | Agent |
| `completed` | The human has reviewed and accepted, and committed the change themselves. | **Human only** |
| `blocked` | Work stopped on a stop condition — governance ambiguity, scope ambiguity, or verification failure — and needs a human decision. The reason is recorded on the entry. | Agent or human |

Permitted transitions:

```text
proposed --(human)--> authorized --(agent)--> running --(agent)--> ready_for_review --(human)--> completed

                                       |                  |
                                       +--(agent)---------+--> blocked --(human)--> authorized | proposed
```

`proposed → running`, `proposed → completed`, and any agent-driven arrow into
`authorized` or `completed` are prohibited.

## 3. Current queue

### T-010 — Establish the GitHub Actions automation runner

- **State:** authorized
- **Authorized by:** human owner
- **Scope:** Create the GitHub Actions workflow responsible for invoking the repository's automation/control-plane entrypoint. The workflow may create or modify only `.github/workflows/agent-task.yml`. It may reference the existing `.github/agent/git-shim/git`, `opencode.json`, `.opencode/agent/task-executor.md`, and `.agent/*` records as inputs/context, but must not modify those files. The workflow must establish the runner-level environment needed to invoke the task executor while preserving the human-review boundary. It must not perform git commits, amend, push, merge, or rebase operations. It must not autonomously authorize work. It must respect the authorized-task model in `.agent/QUEUE.md`.
- **Out of scope:** Do not modify `AGENTS.md`, `product/**`, `.agent/**`, `opencode.json`, `.opencode/agent/task-executor.md`, `.github/agent/git-shim/git`, or any recognition implementation. Do not create `.github/agent/verify_scope.sh`. Do not create `.opencode/plugin/deny-git-write.ts`. Do not implement changed-file/scope verification, notification/reporting automation, P4 reporting, P5 skill packaging, or anything under `app/future-shopify-app/`. Do not commit, amend, push, merge, or rebase. Do not alter the queue or grant additional authorization.
- **Governing records:** `.agent/RULES.md` §3–§4; `.agent/ROADMAP.md` §3; existing `opencode.json`; existing `.opencode/agent/task-executor.md`; existing `.github/agent/git-shim/git`; the human-control/ready-for-review model established by `.agent/QUEUE.md` §1–§4.
- **Verification required:** `git status --short`; `git diff --check`; workflow YAML syntax/parse validation using an appropriate local validator available in the repository; inspection of the resulting workflow to confirm that it invokes the intended OpenCode/task-executor path, does not contain git commit/push/amend/merge/rebase operations, does not authorize tasks, and does not modify files outside the authorized scope. Verify that `.github/agent/git-shim/git` is available to the workflow as the existing runner-level git control. Report any GitHub Actions limitations that cannot be verified locally rather than claiming they were tested.
- **Ends at:** `ready_for_review`, uncommitted, with a report

## 4. Entry format

A human authorizing a task should write an entry carrying at least:

```text
### T-<n> — <one-line title>

- **State:** authorized
- **Authorized by:** Dhyey
- **Scope:** exactly which files and behaviors may change
- **Out of scope:** what the agent must not touch, stated where it is not obvious
- **Governing records:** the decision records / spec sections that fix the boundary
- **Verification required:** the commands that must pass
- **Ends at:** ready_for_review, uncommitted, with a report
```

Every task ends the same way regardless of its content: the change sits in the
working tree, **no commit, no amend, no push, no merge**, and the human
reviews it.
