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

```
proposed --(human)--> authorized --(agent)--> running --(agent)--> ready_for_review --(human)--> completed
                                       |                  |
                                       +--(agent)---------+--> blocked --(human)--> authorized | proposed
```

`proposed → running`, `proposed → completed`, and any agent-driven arrow into
`authorized` or `completed` are prohibited.

## 3. Current queue

**No recognition slice is authorized by this file.**

At this checkpoint the next work is establishing the automation /
control-plane layer described in `.agent/ROADMAP.md` §3, of which this
directory is the first step. That establishment work is not itself an open
authorization: each piece needs its own `authorized` entry placed by a human.

| # | Task | State | Notes |
| --- | --- | --- | --- |
| — | *(none)* | — | No task is authorized at this checkpoint. |

**Explicitly not authorized right now**, listed because their absence is
deliberate rather than an oversight:

- Any new recognition predicate or recognition slice. The pattern is described
  in `.agent/ROADMAP.md` §1; description is not authorization.
- Any change to `AGENTS.md` or `product/*`, including repairing the stale
  version figures recorded in `.agent/CURRENT_STATE.md` §6.
- Any change to `evals/expected/monotonicity_baseline.json`, including its
  `baseline_version` field.
- Any P4 reporting work, any P5 skill packaging work, and anything under
  `app/future-shopify-app/`.

## 4. Entry format

A human authorizing a task should write an entry carrying at least:

```
### T-<n> — <one-line title>
- **State:** authorized
- **Authorized by:** <human>
- **Scope:** exactly which files and behaviors may change
- **Out of scope:** what the agent must not touch, stated where it is not obvious
- **Governing records:** the decision records / spec sections that fix the boundary
- **Verification required:** the commands that must pass
- **Ends at:** ready_for_review, uncommitted, with a report
```

Every task ends the same way regardless of its content: the change sits in the
working tree, **no commit, no amend, no push, no merge**, and the human
reviews it.
