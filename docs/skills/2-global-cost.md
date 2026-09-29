*English · [עברית](2-global-cost.he.md)*

# 2 — The price of global, and the axis nobody weighed

**Type:** a problem document, with a recorded option that was **not decided**.
**Written:** 2026-09-09 · every measurement taken that day on this machine.

---

> **Where the numbers come from.** Grove ships two skills of its own. Everything measured
> below was measured on **the app factory** — the marketplace of app-shipping tracks that
> stands on grove — because that is where a library large enough to have a placement
> problem actually exists. The rule is enforced here; the evidence was taken there.

## In short

[`1-skill-placement`](1-skill-placement.md) priced global loading, found ~8,000 tokens,
and decided they were acceptable. **That decision stands** — this document does not
contradict it.

What it does say is two things:

**A. The question was asked as a binary.** Global (in a track) against local (in the
project's repo). There is a **third axis** that was never weighed: the skill stays in
the track, and only its **activation** moves to the repo. It exists, it was tested
here, and it works.

**B. The price has a growth term nobody measures.** 8,000 is not a fixed number — it is
a floor.

---

## What was measured

### The fixed cost, per track

From `claude plugin details`:

| Track | Always on | Share |
|---|---|---|
| `apple-track` | 3,704 tok | **46%** |
| `shared-track` | 1,925 | 24% |
| `android-track` | 1,677 | 21% |
| `capacitor-track` | 366 | 5% |
| `design-track` | 322 | 4% |
| **total** | **7,994** | |

**`apple-track` alone is nearly half.** That is the number that makes any allocation
discussion practical: there are not five equal problems here, there is one big one and
four small ones.

### The denominator — how many sessions it is multiplied across

| | |
|---|---|
| repos with sessions on this machine | **70** |
| repos in `tools/registry.json` | **3** |

The 70 were not classified and it is not known how many are apps. But the 7,994 tokens
load in **all of them**, including every repo with no connection to apps at all.

### The growth — the term nobody had measured

| | 2026-09-08 ([`skills/1`](1-skill-placement.md)) | 2026-09-09 | change |
|---|---|---|---|
| skills | 32 | **35** | +3 |
| description characters | 28,186 | **31,602** | **+12%** |

**+12% in one day, from three skills.** There is no leak and no bug — that is simply the
shape of the cost: **monotonically increasing, and nobody looks.** No threshold, no
alert, and no moment at which anyone compares.

*A note on method:* [`skills/1`](1-skill-placement.md) also measured the skills'
**directories** (`references/`, `scripts/`) and arrived at a 33:1 ratio. The count here
is of `SKILL.md` only — 310,374 body characters, a 10:1 ratio. Two different measures,
both supporting the same conclusion: **the description is cheap against the body.** As a
check on the method, the three design skills come to 1,199 characters here, exactly as
in [`skills/1`](1-skill-placement.md).

---

## The problem, stated

**The missing axis.** [`skills/1`](1-skill-placement.md) asked *"where does the skill
live?"* and offered two answers. But the file's location and the scope of its activation
are **two questions**, and only the first was asked. A skill can live in a track —
with the versions, the history and the guards — and still load only where it is needed.

**And [`skills/1`](1-skill-placement.md)'s justification depends on that.** Its argument
was *"a generic skill parked inside one project is exactly the skill that is missing
everywhere else"* — a correct argument against **local**, because local ties the file to
one tree. It is **not** an argument against selective activation, which ties nothing.
The third axis escapes that reasoning entirely.

**And the price grows.** A decision that is right at 8,000 is not necessarily right at
15,000, and there is no mechanism to say when the line was crossed.

---

## The option — `--scope project`

**Not decided.** Recorded because it was tested and works, not because it was
recommended.

`claude plugin install <track>@<marketplace> --scope project` writes:

```json
// <repo>/.claude/settings.json
{ "enabledPlugins": { "design-track@app-factory": true } }
```

**Tested 2026-09-09 against a scratch directory:**

| | |
|---|---|
| from the repo it was enabled in | `Scope: project` · `Status: ✔ enabled` |
| from another repo | `Scope: project` · `Status: ✘ disabled` |
| while the track is also enabled at user scope | the project entry **changes nothing** |

That third row is the condition: saving anything requires **removing** the global
enablement, not merely adding a project one.

**The saving, derived from the table above** — not measured in a live session, derived:

| Repo kind | Tracks | Cost | Saved |
|---|---|---|---|
| iOS/macOS app | apple + shared | 5,629 | 2,365 · 30% |
| Android app | android + shared | 3,602 | 4,392 · 55% |
| Capacitor, both stores | everything but design | 7,672 | 322 · 4% |
| website | design | 322 | 7,672 · 96% |
| **everything else** | — | **0** | **7,994 · 100%** |

### What the option costs

**A silent failure, of the familiar kind.** A new app repo starts with no skills at all
and nobody says so. And that is worse than an ordinary absence: *"the skill did not
load"* looks exactly like *"the skill decided it was not relevant"*. This is
[staleness](../cross-repo-session/1-need-problem-solution.md) again — an allocation that
was right when it was set, and a new repo invalidates it with nobody watching.

**Writing into a foreign repo.** `.claude/settings.json` is written inside the app's
repo, which requires moving the session there. The guard would refuse it from here, and
**rightly**. On the other hand, the file documents which tracks the app needs, and that
is an advantage.

**It enlarges the configuration surface.** Today enablement is in one place. Afterwards,
in every repo.

### The cheap variant: `apple-track` only

`apple-track` is 46% of the cost. Moving that one alone saves 3,704 in every repo that
is not an Apple app — that is, in the overwhelming majority of the 70 — and pays the
setup cost in only a handful. The remaining four together are 4,290, spread across four
setups.

**And the "silence" risk is limited there:** someone standing in an Xcode project and
asking about the App Store will notice quickly that something is missing. In a generic
track it would be far less obvious.

---

## What was tried and ruled out

| | Why not |
|---|---|
| **`skills-dir` through a symlink** | solves the staleness of the copy, but **removes the ability to switch a track off** — measured. That gives up precisely the only tool against this cost. Detail in [`plugins/README.md`](../../plugins/README.md) |
| **Shortening descriptions** | the description is the invitation to invoke; shortening it damages invocation accuracy, which is the debt [`skills/1`](1-skill-placement.md) already warns about |
| **Moving skills back into repos** | that is exactly [`skills/1`](1-skill-placement.md)'s decision, and it is right. The axis here is different — the file stays |
| **Doing nothing** | a legitimate option today. 7,994 does not hurt. But without measurement we will not know when it does |

---

## Why this was not decided here

**Because there is no evidence yet that the cost does harm.**
[`skills/1`](1-skill-placement.md) decided 8,000 was acceptable, and no measurement shows
it hurting in practice. Changing the architecture on the strength of a number not shown
to be harmful is trading a known problem for a new one — the silent failure.

**What is missing, and is cheap:** a periodic measurement of the total. The problem is
not 7,994; it is that there is no moment at which anyone compares. Grove dashboard
already shows state, and this is a number that belongs there.
