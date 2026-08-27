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

- **State:** blocked
- **Authorized by:** human owner
- **Scope:** Create the GitHub Actions workflow responsible for invoking the repository's automation/control-plane entrypoint. The workflow may create or modify only `.github/workflows/agent-task.yml`. It may reference the existing `.github/agent/git-shim/git`, `opencode.json`, `.opencode/agent/task-executor.md`, and `.agent/*` records as inputs/context, but must not modify those files.
- **Out of scope:** Do not modify `AGENTS.md`, `product/**`, `.agent/**`, `opencode.json`, `.opencode/agent/task-executor.md`, `.github/agent/git-shim/git`, or recognition implementation files. Do not create `.github/agent/verify_scope.sh` or `.opencode/plugin/deny-git-write.ts`. Do not implement changed-file/scope verification, notification/reporting automation, P4 reporting, P5 skill packaging, or anything under `app/future-shopify-app/`. Do not commit, amend, push, merge, or rebase.
- **Governing records:** `.agent/RULES.md` §3–§4; `.agent/ROADMAP.md` §3; `.agent/QUEUE.md` §1–§4; `opencode.json`; `.opencode/agent/task-executor.md`; `.github/agent/git-shim/git`.
- **Verification required:** T-010 cannot be considered complete until the OpenCode permission contradiction identified during implementation has been resolved and the workflow has been re-verified against the resulting configuration.
- **Ends at:** blocked pending human resolution of the OpenCode permission/configuration contradiction.

**Block reason:** T-010 discovered that the current `opencode.json` denies the task executor read access to governance/context files that its own contract requires it to read, while also denying the write capability required for the executor's `ready_for_review` working-tree end state. Resolving that contradiction is outside T-010's authorized scope and requires a separate human-authorized task.

### T-011 — Reconcile OpenCode permissions with the task-executor contract

- **State:** authorized
- **Authorized by:** human owner
- **Scope:** Inspect the existing OpenCode permission configuration and the existing `.opencode/agent/task-executor.md` contract, then make the minimum necessary changes to `opencode.json` so that the task-executor can actually perform its authorized operating contract. The configuration must permit the executor to read the repository governance/context records that its contract explicitly requires it to read, including `.agent/QUEUE.md`, `.agent/RULES.md`, `.agent/ROADMAP.md`, `.agent/CURRENT_STATE.md`, and `AGENTS.md`, while preserving the existing protection of secrets and preserving governance-file write protection. The configuration must also permit the executor to write only the repository files that an authorized task is permitted to modify, while continuing to deny writes to governance records and other protected paths. Preserve the existing default-deny security posture wherever possible. Do not weaken secret protection. Do not introduce network, subagent, task, or other capabilities not required by the existing task-executor contract. Do not redesign the OpenCode configuration.
- **Out of scope:** Modify only `opencode.json`. Do not modify `.opencode/agent/task-executor.md`, `.agent/**`, `AGENTS.md`, `product/**`, `.github/**`, recognition implementation files, or any other repository file. Do not modify `.agent/QUEUE.md`. Do not implement T-010 or any GitHub Actions changes. Do not create new plugins, scripts, workflows, or verification infrastructure. Do not commit, amend, push, merge, or rebase. Do not silently broaden permissions beyond what is required to reconcile the existing task-executor contract.
- **Governing records:** `.agent/RULES.md` §3–§4; `.agent/QUEUE.md` §1–§4; `.opencode/agent/task-executor.md`; existing `opencode.json`; `.agent/ROADMAP.md` §3.
- **Verification required:** Record the baseline with `git status --short`, `git rev-parse HEAD`, and `git diff --check`. Validate `opencode.json` with `opencode debug config`. Validate `opencode debug agent task-executor`. Confirm that governance files remain unreadable for writes, secret files remain protected, `web`, `task`, and `subagent` remain denied, and git-write protections remain intact. Confirm the resolved permissions now allow the task executor to read the governance/context files explicitly required by its contract and to write ordinary authorized task files while denying writes to `.agent/**`, `AGENTS.md`, and `product/**`. Run the relevant existing configuration/safety checks from the prior control-plane setup. Confirm only `opencode.json` changed and `git diff --check` is clean.
- **Ends at:** ready_for_review, uncommitted, with a report

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
