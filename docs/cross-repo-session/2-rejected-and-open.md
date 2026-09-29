*English · [עברית](2-rejected-and-open.he.md)*

# 2 — What was rejected, and what is still open

**Type:** a record. There is no problem statement and no solution here — both are in
[`1-need-problem-solution.md`](1-need-problem-solution.md).

**Why this file exists.** Several of the decisions in this folder look wrong at first
glance, and without the record they get asked again every few weeks and answered from
scratch — measurements included. **What saves the time is not the decision but the
alternative that was ruled out, and the reason that was measured.**

*Measurements taken 2026-09-08/09 on one machine, and gathered here 2026-09-10 from eight
documents that were replaced.*

---

## Rejected — about the boundary and the space

**"Always move the session."** Tempting, and it erases a great deal of pain: the
preliminary check, the commit/push distinction, maintaining exceptions, and the judgement
about memory.

**What broke it:** `price-sync` touches the hub, the site and several app repos, and its
job is **to reconcile values that have drifted apart**. Under that rule one price change
becomes four moves or more, and at no moment does the session hold the picture it came to
settle.

> **"Always move" does not give you both sides. It only chooses which single side will be
> loaded — and it chooses the destination, which is usually the less important one.**

**"A separate session per repo."** A stronger enforcement, and it solves exactly the same
failures. **And it pays dearly: the transcript does not travel.** Measured: 3 of 10
commits in the site repo on one day rested on knowledge created in grove — including
a dashboard built **with none** of the three design skills loaded. A session born in the
site can **read** grove; it cannot know **what was weighed and rejected there**.

**"Just read the target's `CLAUDE.md`."** Possible — it was proven readable from outside.
Rejected **as the only solution**: it is a decision you have to **remember to make**, and
that is precisely the missing capability. For skills it does not help at all, because a
skill can be read and cannot be run.

**Block `commit -a` always, even in the repo you are standing in.** Rejected: there
`git status` shows the state before the commit, and `-a` is the normal flow. **The danger
is specific to the repo you cannot see.**

**Change an existing guard instead of adding a sibling.** Rejected: a change to a guard
requires running every one of its branches before it takes effect, and a guard that
crashes stops everything.

---

## Rejected — about detection

**A file watcher as the foundation.** Kernel-level; it catches writes a script made, with
no command parsing. **Tested and it works.** Rejected **as the foundation** for one
reason: there is no file watcher by default on macOS, it was installed here by hand, and
nothing depends on it — one `brew uninstall` and the layer dies silently. It remains an
optional improvement; what it buys is one case — a write made by a script whose path
appeared in no tool call.

**Command parsing.** The guard that blocks `commit -a` and `add .` rests on it. **It was
proven to be bypassable in one command:** `git add $(git diff --name-only)` — the same
effect exactly, and it passes.

**Scanning every repo every turn.** 235 repos, **4.5 seconds**. Too expensive.

**Extending the registry to every repo on the machine.** An enumeration stays an
enumeration, and it needs maintaining forever. **Derivation from behaviour** — every path
passing through a tool call resolves to its repo — answers the right question and requires
nothing.

---

## An alternative that stayed on the table, and not as a replacement

**Delegate the commit to a session standing in the target.** The strongest idea raised:
rather than teaching the stranger to commit correctly, launch a task with the target's
`cwd` — it loads the rules, the memory and the skills there, and sees a real `git status`.

**It solves** the rules that do not load and the decisions made without them. **It does
not solve** visibility, staging or atomicity — because it fires **only when the stranger
decides to delegate**, and that is the missing capability.

And this is the distinction worth remembering: there are two questions here — **whether**
there is a place that needs closing, and **how** to close it. An execution mechanism
answers "how" excellently and "whether" not at all.

> **An excellent engine with no ignition is no different from no engine.**

---

## Rejected — about staleness

**"Just maintain the memory."** Rejected — **there is no moment at which that happens.**
Maintenance requires somebody to initiate reading a record they have no reason to read.

**A periodic scan of everything.** 129 memories, and most staleness cannot be detected
mechanically — *"the price is 9.99"* looks fine even when it is wrong. **A scan catches
the cheap kind and misses the expensive kind.**

---

## Two pieces of evidence that were disqualified — recorded so they are not cited again

**"This session wrote zero memory in the site repo."** Checking showed that everything
done there is documented in `CLAUDE.md`, in a skills README and in the git history — and
the memory rule forbids storing what the repo already records. **Zero was correct.**

**"0 of 69 sessions wrote memory for more than one project."** The number measures how
many sessions **moved**, not how many **failed**. A session that did not move holds one
project, and writing to one is correct.

---

## Open tasks

| | What | Requires |
|---|---|---|
| **1** | **An audit script for stuck memory** — a cheap heuristic: a memory whose name or description names a project other than the one it is filed under. It catches the leak class that has already occurred twice | a session in grove |
| **2** | **The seal** — refusing to end a turn while a place is open. Deliberately unbuilt: blocking on a report requires the report to be right, and the measurement that would justify it failed once already | a session in grove |
