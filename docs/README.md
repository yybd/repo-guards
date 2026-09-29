*English · [עברית](README.he.md)*

# Grove decisions

**What this folder is.** For each architectural decision, a document saying **why** it
was made, what was measured to settle it, and what was **rejected and on what grounds**.

**Why it exists.** Several of the decisions here look wrong at first glance. Without the
record they get asked again every few weeks and answered from scratch, measurements
included. **What saves the time is not the decision — it is the alternative that was
ruled out.**

---

## [`cross-repo-session/`](cross-repo-session) — a session across directories and repos

| | |
|---|---|
| [1 — the need, the problems, the solution](cross-repo-session/1-need-problem-solution.md) | why one action requires several places, what breaks because of it, and what the answer is |
| [2 — what was rejected, and what is still open](cross-repo-session/2-rejected-and-open.md) | the alternatives that were measured and ruled out — and the open tasks |

## [`skills/`](skills) — where a skill loads, and what it costs

| | |
|---|---|
| [1 — where a skill lives](skills/1-skill-placement.md) | global against local, and the trap inside the criterion |
| [2 — the price of global](skills/2-global-cost.md) | what is always loaded, what it costs, and the axis nobody weighed |
| [3 — how a skill refers to a script](skills/3-script-references.md) | 39 references broken by one migration |

## [`maintenance/`](maintenance) — keeping it true over time

| | |
|---|---|
| [1 — what is checked, when, and what is only measured](maintenance/1-plan.md) | four cadences, the clean-room argument for CI, and the honest list of what no machine can check |

## Elsewhere

The shipping side of this work — the data layer the release skills read, the website the
stores check, the product plan — lives in **the app factory**, which is the companion
repo and a marketplace of its own. Grove governs where those skills load; it does not
carry them.

**And how a skill gets from the file to the session it runs in** — that is mechanics
rather than a decision, and it lives in [`HOW-IT-WORKS.md`](../HOW-IT-WORKS.md) at the
root.

---

## The rules for writing here

1. **Numbers are counted from disk, not copied.** Every number carries the date it was
   counted.
2. **Evidence before argument.** If it was measured, write what was measured and how. An
   argument with no measurement is marked as one.
3. **What turns out to be wrong is corrected in place, not deleted.** A dated
   correction; the history is in git.
4. **One document, one job.**
