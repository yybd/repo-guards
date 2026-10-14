*English · [עברית](1-need-problem-solution.he.md)*

# A session across directories and repos — the need, the problems, the solution

## The need, in three layers

**Layer 1 — reach:**

> **That a session can act on another directory** — read from it, write to it, and close
> it — without giving up what it holds on this side.

**Layer 2 — orchestration:**

> **That there is a tool which knows which places, in what order, and under which rules —
> and drives the session accordingly.**

**Layer 3 — retention:**

> **That something decides where what was learned is stored — because knowledge saved in
> the wrong place loads in the wrong sessions, and never loads where it is needed.**

**Three words:** arrive · know what to do · retain what was learned.

#### Note: not every "place" is a directory

The eight places a price lives in divide like this: **six in repos, and two in external
services** — the product in a payment service, and the in-app purchase in App Store
Connect. The last two have no git: no status, no commit, no history, and no undo.

**And one of them is worse than that.** From `price-sync` itself:

> *"The payment provider's API is **read-only for products** — the price there is a
> dashboard edit, **always**."*

That is, **no session can write there at all.** It needs a person in front of a dashboard.

So layer 1 is wider than it sounds: not only *act on another directory*, but **reach
every place the output lands — and know how to hand a person what cannot be reached, and
then verify that it happened.**

#### Why 1 and 2 are two layers and not one

Because neither is worth anything without the other, and for the same reason from both
directions:

| You have | You lack | What you get |
| --- | --- | --- |
| **the reach** to write everywhere | **a tool** holding the list | **blind writing** — you update five places out of eight and report "done" |
| **a tool** that knows all eight places | **the reach** to get to them | **a map with no legs** — it knows exactly what must happen and cannot make it happen |

**And "knowing" is not a third layer** — it is part of what the tool does. The tool is
what reads all the places and compares them; the session alone would not even know where
to look.

#### Why retention is not part of orchestration

Because **not all knowledge belongs to the tool.** Knowledge created during such an action
has three kinds of ownership — and they are not in the same state:

| The knowledge concerns… | belongs to… | does it have a place? |
| --- | --- | --- |
| one project | that project | ✅ its memory directory |
| **a craft, not a project** | **the action itself** | ❌ **none** |
| the user and their preferences | the user | ✅ global |

*"This payment provider rounds to .99"* belongs to neither the hub, nor the site, nor any
app — it belongs to `price-sync`. **And that kind has no home today**, so it is written to
the memory of whichever directory the session happened to be standing in.

**And this cannot simply be shrugged off.** Misrouted memory is not merely useless — it is
**misleading**, because it loads confidently and unasked. One app's full dossier sat in
another app's memory, so it loaded in every session of the wrong app and never in the
right one.

> **Loaded, wrong memory is worse than no memory.**

And it has a property the other two layers do not: **it is irreversible.** The knowledge
is already written at the source, and the rule *"never write to another project's
memory"* prevents fixing it from outside as well.

#### Where layer 2's knowledge can live

The list of eight places is itself knowledge, and it has to be written somewhere. There
are three possibilities, and two of them do not work:

- **Not in a repo.** Each repo knows only what is inside it. The hub has no way to know
  that the price is also written on the site and in the app's `.storekit`.
- **Not in a directory's settings.** Those decide what **loads** when you stand there —
  not what **an action requires**.
- **In a skill.** A skill is the only thing written **per action** rather than per place.
  `price-sync` is the only thing in the system that says *"a price lives in these eight
  places"*.

**And from this follows why it is global.** A skill is not a program that runs by itself —
it is **text loaded into a session**, and what loads is decided by where the session
stands. If `price-sync` lived inside the hub, it would load only in a session standing in
the hub — that is, **not** in a session standing in an app repo, which is exactly where a
price change starts.

> **And that is the dependency between the two layers: layer 2's tool is itself subject to
> layer 1.** It can know everything about the action — and if it does not load, it does not
> exist.

# What creates such a need in the first place

Six shapes of connection between places — all of them properties of how the product is
built, not of the agent:

|  | The connection | Example |
| --- | --- | --- |
| **Duplication** | the same fact written in several places | a price in eight places |
| **Derivation** | the source here, the derived thing there | profile in the hub → store copy → `fastlane/` in the app repo |
| **Reference** | one points at the other | a page on the site → the privacy policy URL |
| **Orchestration** | one process whose steps live in several places | a release: metadata · build · site page, **in that order** |
| **Reconciliation** | an action whose entire job is to compare and settle | `price-sync` compares a price across three sources and resolves them |
| **Tooling** | one serves them all | RepoGuards supplies the skills to everything else |

**And reconciliation is the sharpest of them:** such an action **cannot** exist inside one
place — not for convenience, but by definition.

### And each of the places can move on its own

So far we assumed somebody performs an action. But `price-sync`'s second trigger, in its
own words:

> *"**Reality moved** (the owner changed a price in the store or the payment provider)"*

Nothing in git changed. No session ran. **And the places no longer agree.**

All three layers assume an action is being performed — here there is no action, there is
**drift**. Which is why what is also needed is **a reconciliation that depends on no
change having been made: an audit, not a sync.**

---

## Examples

*Three of them: one that shows the three layers together, one that shows a further need
born from them, and one that shows they cannot be abolished.*

## Example 1 — the three layers in one action: changing a price

It sounds like a simple action. Here is where the price is actually written:

```
prices.json                    ← the hub
store metadata                 ← the hub
two profiles                   ← the hub
media scripts and captions     ← the hub
site copy                      ← the site repo
.storekit files                ← the app's repo
the product in the payment service   ← external
the IAP in App Store Connect         ← external
```

**Eight places. Three repos. Two external services.**

Update five and miss three and **the site advertises one price while the store charges
another.** Neither git nor the agent will warn you: they have no way to know the eight are
related. It will look fine until a customer complains. *(What can warn is a skill with the
list written inside it — see above.)*

And this is not a rare or exotic action. **It is a price change.**

**And all three layers are present here:**

|  | In the example |
| --- | --- |
| **Layer 1 — reach** | the output lands in **three repos**. A session that can write to only one of them does not perform the action — it performs a third of it |
| **Layer 2 — orchestration** | something has to hold **the list of eight**. Without the list, "able to write anywhere" only means you will update five and report "done" |
| **Layer 3 — retention** | *"this provider rounds to .99"* — a lesson learned along the way, belonging to the **action** and to none of the three repos. Today it is written to the memory of wherever the session happened to stand, and vanishes the next time the action runs from somewhere else |

---

## Example 2 — needing a tool that sees everyone's commit state at once

Two facts meet here, and a need is born from the meeting.

**First fact: there is no single commit across several repos.** A commit is atomic
**inside one repo** — it lands whole or not at all. There is no `git commit --all-repos`
and no shared rollback. Three repos are **three separate operations**, each with its own
success and failure.

**Second fact: the information in each repo depends on, or derives from, the others.**

| What landed in… | depends on it / derives from it |
| --- | --- |
| the profile in the hub | the site page that points at it |
| the store metadata | the binary that matches it |
| the changelog | the release that ships it |

**And from the meeting:** if one commits and the other does not, the result is not "half
the work was done" but **an inconsistent state** — a reference pointing at something that
does not exist.

> **And a half-finished cross-repo change is always discovered through the broken
> reference, never through the missing content** — that is, not when you look for it, but
> weeks later, when something else breaks.

To know that it even happened, you have to see the commit state of **all the repos
together**. `git status` shows one.

> **Hence the need for a tool that knows the current commit state of every repo at the
> same time.**

**And that is layer 2 again, wearing a different face.** Not a tool that knows *which
files* to update, but one that knows *what is already closed and what is still open* — in
every repo, at the same moment.

**Such a tool was built** — `tools/close.py`. It reads the state of every place the
session touched, and for a declaring operation, the places it is defined over. **What is
still missing is the seal:** nothing forces you to run it, other than a message at the end
of a turn.

### And "closed" is not "committed"

So far we assumed a commit is the last step. On a website it is not:

> *"**Pushing does not deploy** — `npm run ship` does. **Eight deployments sit on this
> repo**, one per domain… one of them **served a wrong price for twelve hours**."*

So the same repo has **eight publication states**, one per domain, and they do not follow
from the commit:

```
dirty  →  committed  →  published × 8
```

And the deploy script there decides per project **against the commit that site actually
last submitted** — because that is the only question with an answer. The same shape
applies to RepoGuards itself: a commit is not a deployment to
`~/.claude/plugins/cache`, and the rule *"a commit is not a deployment"* was born from
exactly that gap.

**So the tool this example describes is wider than it sounds:** *"what is closed and what
is open"* is not a question about commits alone — there are places where a commit is the
middle of the road, not its end.

*(And here the two halves of the need separate: the **commit half** would vanish if all
the repos were one — there, a single commit closes everything. The **publication half**
would not: the eight deployment targets already sit on one repo.)*

## Example 3 — why the need cannot be abolished: merge the repos

This is the first objection anyone raises — *if the split creates this, abolish the
split* — and it has a measured answer: **they are separate for reasons that cannot be
abolished.**

| The repo | Why it is separate |
| --- | --- |
| **the app's repo** | the code ships to a store. A version **freezes** at release — a website's does not |
| `app-hub` | data, not code. Profiles, prices and media that several consumers read |
| the site | **eight deployments sit on it, one per domain** — imposed by the platform |
| `RepoGuards` | the tooling. It serves all the others and belongs to none of them |

Different life rhythms, different publication targets, different ownership. Merging would
not simplify — it would create a repo that releases to a store and to a website
simultaneously, which is exactly what must not happen.

> **The split is right. The problem is not the split — it is that the tools assume it does
> not exist.**

---

# The problem

*Up to here — **the need**: why one action requires several repos. From here — **the
problem**: why the agent cannot deliver it.*

## The three problems

All three are the same shape of problem — **what the session holds is decided by where it
stands**, and is therefore missing when it stands somewhere else.

**And note the unit, because it is not the same unit in all three:**

| \# | The mechanism | The unit | What breaks | Evidence |
| --- | --- | --- | --- | --- |
| **1** | **git** — the state and the commit | **another repo** | four separate failures — see below | **20 commits pushed in an app repo, 18 of them older than the session** · **three files entered a commit, two of them not the session's** |
| **2** | **what the other directory holds** — `.claude/skills/` and `CLAUDE.md` | **another directory** | the write succeeds without the tools that live in the other directory, and without its rules | **a wrong price served for twelve hours** — the rule that would have prevented it sat in the site's `CLAUDE.md` |
| **3** | `memory/` — the knowledge | **another directory** | saved against the cwd, not in the other directory the session wrote to | **one app's full dossier sat in another app's memory** |

*(Four mechanisms —* `git status`*,* `.claude/skills/`*,* `CLAUDE.md` *and* `memory/` *—
reduce to three problems, because the skills and the rules are one principle; see the note
on problem 2.)*

**Only in problem 1 is the unit the repo**, and that is not accidental: it is git's unit.
If it is the same repo, `git status` shows the change and there is no blindness.

**In problems 2 and 3 the unit is the directory — and it need not be another repo at
all.** Claude Code resolves settings, skills and memory against the cwd, not against the
git root. Measured 2026-09-09 with `claude plugin list`:

```
<project>/              android · apple · capacitor · design · shared · RepoGuards
<project>/apps/mobile/  RepoGuards only
<app>/                  five tracks + RepoGuards
<app>/Capacitor/        RepoGuards only
```

**Same repo. Same git. One directory in — and everything is gone.**

## Four notes that change how they are handled

### Problem 1 is four failures, not one

|  | The failure | Why it is silent |
| --- | --- | --- |
| **1** | `git status` **shows a quarter of the state** — the session is in A, and B and C are dirty too | worse than "missing information": the information **looks complete**. A clean report is received as "the state is clean" |
| **2** | `-a` **and** `.` **sweep the target's dirt** — they are defined relative to the target repo, "everything dirty there" | git has no notion of "what this session did". And `git commit -am` is the habitual command, entirely correct when you are standing in the repo |
| **3** | **staging survives** — the index is a file on disk. A session that ran `add` and never committed leaves a loaded index | in the repo you stand in this shouts from every `git status`. **In a foreign one it is silent forever** — until somebody commits and creates a commit nobody intended |
| **4** | **three decisions are made without the session running the commit** — who signs (the target's `user.email`), which branch (the active one there), and what a `push` publishes (**every** commit on the branch) | the session neither chooses nor sees any of the three. Measured: a commit signed with the target's identity; the target was moved to another branch and the next commit landed there with no warning |

**And `push` is the worst of them in hindsight:** a push publishes **a whole branch** and
cannot be undone. That is what happened in one app repo — 20 commits, 18 of them from
before the session.

**And there is a case where none of the four exists — and that is worse.** One registered
app is not a git repo at all. No status there, no commit, no history — **and no undo.**
Problem 1 does not apply to it, and neither does any recovery.

### The problems are not all of one kind — and that is what separates them

**Failures 1–3 come from a lack of sight, and are cured by supplying it.** Let the session
see what is dirty in the other directory — including a loaded index, which appears in
`git status` like any change — and they close.

**Failure 4 is half of that.** `git status` shows the branch and the number of commits
above upstream, but **not who will sign** — that is `git config user.email`. And even full
sight would not close it, because it is not a problem of sight but of **inheritance**: the
target's configuration decides, and the session is not a party to the decision. It did not
"fail to see" — it **was not asked**.

### Problem 2 is one principle over two kinds of content

Skills and rules are **the same problem**: content that lives in the other directory,
loads only per cwd, and is silently absent. But **the two kinds are not identical**, and
not by accident:

|  | What it is | And what actually happens |
| --- | --- | --- |
| `.claude/skills/` | the skill **owns** the file — writing from outside bypasses ownership | a write to such a root is **refused** |
| `CLAUDE.md` | the rule is **knowledge**, not ownership — the write may be perfectly legitimate, it just happens without anyone having read it | **nothing happens at all** |

And two differences that explain why:

1. **How they load.** `CLAUDE.md` loads **in full, always**. A skill loads only a name and
   a description; the body is read only on invocation. So a missing `CLAUDE.md` is a
   certain loss; a missing skill is a loss only if it would have been invoked at all.
2. **How far they can be reconstructed from outside.** `cat <target>/CLAUDE.md` is a
   **complete substitute** — the rules are text, and you have read them. A skill is not:
   you would have to know in advance **which** one is relevant, and a local skill of a repo
   you are not standing in can only be **read as a file, not run**.

**And why this is not merely theory** — measured 2026-09-10: the repo with the largest
rules file in the system, 46 KB of them, carried no local skills and therefore no
protection at all: a session standing elsewhere writes into it and nothing says a word.

**And why it is that way and not otherwise:** if "has a `CLAUDE.md`" triggered a block,
nearly every app repo would be blocked — and cross-repo writing, which exists
**deliberately** and which three mechanisms were built to allow, would become impossible.
**So the two kinds of content remain in different states: one has a block, the other has
nothing.**

**And two more of the same kind, secondary but real:**

- **Permissions.** `settings.local.json` is per directory. A session standing in A and
  acting on B runs under **A's** permissions, not the target's.
- **`launch.json`** — it is what says **how to run the app**. A session from outside
  cannot run the target, which means it cannot **verify** that its change works.

### Problem 3 is bidirectional, and that is easy to miss

Not only does the session fail to **read** the target's memory — it also **saves** what it
learned about the target in the wrong place. And the second direction is worse, because it
is **irreversible**: the knowledge is already written at the source, will load there
forever, and will never load where it is needed.

**And two more things fall into the same problem:**

- **The transcript does not travel, and it is the only one that is not a file.** Another
  directory's `CLAUDE.md` and memory are **readable** from outside; what was weighed and
  rejected in the current session is not. Measured: 3 of 10 commits in the site repo on one
  day rested on knowledge created in RepoGuards.
- **Writing to another directory's memory is entirely permitted and unenforced.** The
  worst of both worlds: it cannot be written **well** from outside — without reading and
  merging — and nothing prevents writing it **badly**.

---

# A different axis: staleness — not "where", but "still true?"

The three problems above all ask **where**: where the knowledge is, where the tools are,
where the state is. There is another axis belonging to none of them, and it asks an
entirely different question — **whether what was recorded is still true.** The record is
in exactly the right place. It simply is no longer real.

**And it has happened, and it is documented in the records themselves:**

| | |
| --- | --- |
| **16 of 129 memories (12%)** carry an explicit correction | `"was WRONG"` · `"corrected"` — history, not a scenario |
| **7 memories** point at paths that no longer exist | and none of them is marked as stale |
| **One event** — the skills migration — invalidated **seven kinds of record** | one of them was not caught for days |

**And 12% is a floor, not a ceiling.** Catching a stale record requires four things at
once — that a session loads in the right project, that it works on exactly what the record
describes, that it notices the contradiction, and that it bothers to fix it. **Three of the
four are chance.**

## And here is the connection to multiple directories — narrow and precise

> **Multiple repos do not cause staleness. They break the repair.**

The only repair mechanism that exists is a session loading, working on the subject, and
catching the contradiction — and it works only if the record is filed with its subject.
Multiple directories break it in two ways:

**1. The record is not with its subject.** One app's dossier sat in another app's memory —
that is, **in the one place where it cannot be repaired.** A session of the right app will
never load it, and even if that app changes completely, nobody will catch it.

**2. The event and the record are in two different places** — and this is the serious one,
because it applies even to records filed **correctly**. Whoever moved the skills was
standing in RepoGuards; what they invalidated sat in the site's `CLAUDE.md`, in the hub's
memory, and in a third project's memory. **Whoever caused the damage does not see it.**

*And measured:* five broken references in one repo's `CLAUDE.md` were caught **only**
because the guard forced a session move there before the deletion. Without the guard they
would not have been caught.

# An imperfect solution: jump to the other directory's repo

The obvious idea: instead of writing into another directory from outside, **move the
session there** and write from inside — `change_directory`, or a task launched with its
`cwd`.

## What it solves, and what it does not

|  | The problem | Does jumping solve it? |
| --- | --- | --- |
| **2** | the skills and the rules | ✅ **solved.** This is the only problem the jump was built for — you stand there, and they load |
| **1.1** | the blind spot | ❌ **moved, not closed.** While you are in B, the repo you left is invisible again |
| **1.2** | the sweep | ✅ **solved.** `git status` shows what is dirty there, and `-a` becomes a command whose result you can see |
| **1.3** | staging | ❌ **worse.** Every jump produces another repo you left with an open index |
| **1.4** | identity · branch · push | ❌ **untouched** — these are decided at the target, and standing there neither changes nor displays them |
| **3** | memory | ❌ **not solved — inverted.** From the jump onwards, what is learned about **the source** is written to the target |

**Two out of six** — and the failure it does not touch, 1.4, is the one that caused the 20
pushed commits.

## And two caveats that damage the one problem it does solve

**"At the moment of writing" is already too late.** The target's skill is worth something
**before** it was decided what to write, not while writing it. Jumping at the moment of the
write arrives after all the decisions it was supposed to shape — the same reason it is
better to **name the skill** than to inject its contents.

**And the jump does not take effect in the same turn.** Project settings move to the
target **at the end of the turn**. So "jump and write" in one turn gives you the write
**without** the target's skills and rules — that is, exactly nothing. For it to work you
need jump → end of turn → write in the next turn, **for each repo separately**.

## What it makes worse — and what it creates from scratch

**Worse — failure 1.3.** Every jump is a departure, and every departure is another repo
left with an open index nobody sees. The more you jump, the more you leave.

**Worse — problem 3 splinters.** Before the jump, all of one action's lessons landed in one
place — the wrong one, but **one**. After three jumps they are scattered across three
memory directories, each with a fragment and none with the picture. And scattering is worse
than concentrating in the wrong place, because the rule *"never write to another project's
memory"* also prevents gathering them back.

**Created — multiplied interruption points.** The jump takes effect at the end of a turn,
so an action over three repos requires at least three additional turn boundaries — and
every turn boundary is an opportunity to be interrupted. **The jump increases the risk of a
half-finished change in exactly the action that most needs to complete.**

**Created — context that accumulates and is never released.** Every jump loads the target's
`CLAUDE.md` and memory into the transcript, and they stay. Measured: three targets at
~6,041, ~4,923 and ~3,537 tokens. Three jumps ≈ **14,500 tokens** that will not be freed.

## And beyond that — it works against the need from example 3

The need there was **a tool that sees everyone's commit state at once**. The jump is the
exact opposite: it guarantees that at any moment you see **one**. It does not merely fail
to supply the picture — it makes it harder for the picture ever to exist.

## In one line

> **The jump solves the loading problem — the only problem it was built for. It does not
> touch identity, branch or push; it moves the blind spot instead of closing it; it inverts
> and splinters the memory problem instead of solving it; and it adds interruption points
> of its own.**

---

# The goal

> **Solve every problem optimally — without damaging the need.**

The two halves of that sentence are two separate tests, and every proposed solution has to
pass both.

## The first half: what "without damaging the need" means

The three layers must remain possible. A solution that achieves one at another's expense
has not solved — it has traded.

| The layer | What a solution must not break |
| --- | --- |
| **1 — reach** | it must not split an action defined across several places. An action whose whole job is to reconcile cannot be performed side by side |
| **2 — orchestration** | the tool that knows the list has to be **loaded** when it is needed, and able to run what it knows |
| **3 — retention** | what is learned must have a correct destination — even when it belongs to no repo |

## The second half: what "solve every problem" means

|  | The problem | What a solution must supply |
| --- | --- | --- |
| **1.1** | the blind spot | seeing the state of **every** place that was touched — not one at a time |
| **1.2** | the sweep | that a commit takes only what the action wrote, and not what was already there |
| **1.3** | staging | that no open index is left in a place nobody looks at any more |
| **1.4** | identity · branch · push | that the session is **party to the decision** — sees who signs, which branch, and exactly what would be published |
| **2** | skills and rules | that each place's tools and rules influence the decision **before** it is made |
| **3** | memory | that every lesson is routed to the destination where it will load the next time it is needed |

## And the test applied to what has already been examined

Jumping to the other directory's repo fails both tests at once: two of six in the first
column — **and it damages the need at the same time**, because it splits the very action
whose job is to unify.

**It is not the answer. But it is the bar:** every solution from here on is measured
against those same two columns.

---

# The solution

> **Every cross-place action gets a list of its places — and one command that reads the
> state of all of them, reports, and closes only what is yours.**

And why that shape: **atomicity that does not exist cannot be manufactured**, but something
can be built that **does not need it** — one that recomputes on every run what is still
open and continues from there.

## Four parts

### 1 · The list of places — "the declaration"

Beside each such action, **where it lands and how each place closes** is written down:

```
app-hub     prices.json · <slug>/store/**    commit
app-repos   **/*.storekit                    commit
the site    the pages in site_paths          commit → npm run content → npm run ship   ← work from inside
App Store   API                              person
payments    dashboard                        person
```

That list already exists today — inside a paragraph of English prose inside the skill.
**Here it becomes something a machine can read.**

**And the last two rows are not a mistake.** App Store Connect's API **can** write a price
— and the action still does not touch it, because *changing what a customer pays is the
owner's decision, not file management*. The payment provider has no write path at all. **A
place closes according to who is entitled to close it, not according to what is technically
possible.**

> **Built** — a skill's `places.json`, and
> `close.py --op price-sync` reads it and runs the state check it names.

### 2 · The command — "what is open, and close what is mine"

Five steps, always in the same order:

1. gather the places — from the declaration, or **from the journal** when there is none
2. ask each place **what its state is now**
3. report **one table**, separating what you changed from what was already there
4. close **only the declared paths** — a commit in each place separately, never `-a`
5. re-read, and say what is still open

**And the property that holds it all together: it can be run again and again.**
Interrupted halfway — run it again and it continues. **And when it is run without changing
anything, it is the audit:** do the places still agree.

> **Built** — `tools/close.py`. And its first run found a flaw in it: it presented 101
> files in the hub as "mine", another session's media. **The report is generous, the commit
> is not** — a path enters only if the session actually wrote it.

### 3 · The ownership declaration — each place says what is its own

In each repo, a small file saying what is protected and what has to be known:

```
apps/             block.  add-app-to-site writes the catalogue and the app pages
privacy-policy/   block.  written from a scan of the app's own source
sites/            block.  product-site clusters — scaffolded, translated, synced
content/en.json   warn:   after editing, run npm run content and commit both together
style.css         warn:   after changing, run npm run design, or eight sites serve the old one
```

**Two levels, and they are exactly the two conclusions from problem 2:**

- **block** — when a local skill **owns** the path. That is the one thing reading from
  outside is no substitute for.
- **warn** — when it is **knowledge** rather than ownership. The write is permitted, it
  just needs to know something first.

**And anything not declared is open.** Note what the fourth line covers: `content/en.json`
**has no owner**, no skill writes it — **and that is precisely the incident of the wrong
price served for twelve hours.** Until the declaration was written, no mechanism saw it.

> **Built** — the site's `.claude/owns.json`, five claims. **And written from a session
> standing there**, which changed it: from outside I had claimed an `i18n/` at the root, and
> it does not exist — it sits inside each cluster. The rule about `style.css` came from that
> repo's `CLAUDE.md`, which loads only when you stand there.

### 4 · `LESSONS.md` beside the skill

*"This provider rounds to .99"* belongs to neither the hub, the site nor the app — **it
belongs to the action**. Today it has no home, so it is written to whichever directory was
underfoot and disappears. Here it travels with the skill.

> **Built** — a skill's `LESSONS.md`. What goes in is not the
> method but **what the runs taught**, and `close.py --op` prints it **before** the state
> check: a lesson read after the decision arrives too late.

## What it looks like in practice — changing a price

**Today:** you change a price, update five places out of eight, commit in one repo,
`git status` is clean, and you report "done". Two months later the site shows one price and
the store charges another.

| The step | What happens |
| --- | --- |
| run the command | you see the eight places and the price in each — **and immediately see that two disagree** |
| edit | a write to a path with an owner is **refused, and the owner is named**. Editing the copy gets **a warning that a sync must be run** |
| run it again | it commits in three repos separately, each in its own terms |
| read the report | *"three committed · the site is not published yet — `npm run ship` · the payment provider is waiting in a dashboard"* |
| tomorrow, changing nothing | run it again — and that is the audit |

## What was deleted

**One guard was replaced, and three were not deleted** — the first description here counted
only what it had touched:

| | |
|---|---|
| `protect_project_roots` | **deleted.** Replaced by `honor_ownership`, which reads a declaration instead of guessing with grep |
| `protected` · `open_paths` in the registry | **deleted** — nine keys. No exception list to maintain any more |
| `scope_foreign_commits` | stayed, **and widened** — it now blocks a foreign `push` as well |
| `warn_uncommitted_roots` | stayed, **and shrank** — it points at `close.py` instead of duplicating it |
| `record_touched_repos` | stayed — it is the journal that feeds the command |
| `warn_stale_plugin_cache` · `offer_registration` | stayed — deployment and registration, never in scope |

**What changed is not the number but that one of them stopped guessing.**

---

# What is still unsolved

**1 · Identity and branch.** The command **shows** who signs and which branch it lands on —
it will not choose for you, and it cannot stop the target from being on a different branch
than you thought.

**2 · Permissions and `launch.json`.** These load per directory too. A session from outside
still runs under the permissions of the place it stands in, and still cannot **run** the
target to verify that its change works.

**3 · The transcript does not travel.** Rules, memory and files are all **readable from
outside**. What was weighed and rejected in this session is not a file, and so is
accessible to nobody. **There is no solution to this.**

**4 · "Is it still true" — half closed, and it is worth knowing which half.**

**Where there is a live source to ask, it is solved.** An operation declaration has a
`state` — a command that reads the state of every place — and for a price that is a script
asking the store and the payment provider **live**. So *"9.99 is no longer true"* is
exactly the question that does get answered. **That is the answer to drift that happened
with no session running at all.**

**And where there is no live source — it is not.** *"The user writes in Hebrew"*, *"the
skills load in every session"* — records with nobody to ask, and they look fine even when
they are wrong. The path check — *what was mentioned, does it still exist?* — **was built**
(`tools/check_references.py`, run inside `deploy.py`) and closes the mechanical part: it
found three real breakages, one of them created that same day when a document was deleted.
**The rest requires judgement, and has no mechanics.**

## And atomicity — not solved, but converted

There is not and will not be a commit across several places. If you are interrupted
halfway, there will be a moment when part has landed and part has not. **What the command
buys is not the removal of that window but its closing:** instead of a silent half-change
that stays forever and is discovered two months later through the broken reference — **a
temporary inconsistency that the next run heals.**

## And two risks

**Everything depends on the command being run.** Nothing compels it except a message at the
end of a turn that can be skipped. If that message wears out, the next step is **refusing
to end a turn** while something is left open — the one point that cannot be routed around.
But not before the command has proven it does not err.

**And the declarations are themselves records, and records go stale.** An ownership
declaration left behind after a restructure is exactly the failure the second axis
describes — and this time **the mechanism itself** is the victim. A cheap check closes most
of it: every declared path must exist, and every local skill must be declared.

---

# What is not finished, and what to measure before finishing it

*As of 2026-09-10, after the parts above were built and deployed.*

## What was built, and what was not

| | |
|---|---|
| the command · the operation declaration · the ownership declaration · `LESSONS.md` | ✅ |
| the path check (the mechanical half of staleness) | ✅ |
| the guards: `honor_ownership` · refusing a foreign `push` · the Stop hook as ignition | ✅ |
| **the seal** | ❌ **deliberately** — see below |
| declarations for two further cross-place operations | ❌ |

**And why the seal was not built:** blocking the end of a turn on what a tool says requires
the tool not to be wrong. **`close.py` has run three times**, and all three tools built
here found a bug in themselves on their first run. Blocking now would trade "forgetting to
close" for "stuck on a wrong report" — and the second is worse, because it teaches people
to route around the mechanism.

## The measurement that decides — taken, and failed

**The expensive question was: does "mine" contain anything the session did not write.** The
third run returned **five files** — an `Info.plist`, a project file, and three localisation
directories. The session wrote none of them; it had searched in them. A parallel session
wrote them, and committed them seven minutes later. `--commit` would have swept them in.

**And in the same run the push attribution failed too:** nine of the owner's own commits
were reported as the session's, because "committed in the last 24 hours" was read as "what
this session did".

**All three failures shared one root: inferring ownership from what was observed.** The
journal records **every** path mentioned, deliberately — that is peripheral vision, not a
record of writing. The dirty baseline is **a snapshot in time**, not a record of who did
what, so it cannot separate the session from whoever wrote in parallel after we arrived.
Both were read as evidence of ownership, and no filter turns them into that. **It is the
same mistake that had already happened with 101 files** — the filter added then narrowed it
instead of removing its source, so it came back.

**What changed:** ownership now rests on the write itself and nothing else.

- The recorder separates **`paths`** (sweeping, as before) from **`written`** — only a path
  a writing tool named. What `Bash` writes **is not recorded at all**: a shell line can
  write anything, and under-reporting is the safe direction.
- The recorder stores the **HEAD the place stood on at arrival**. "How many commits predate
  the session" is asked against that sha; a sha does not drift like a clock. Even then the
  wording is "predate the session", not "mine" — because a parallel session's commit lands
  after that boundary too.
- `--commit` stages **only** paths that were written, intersected with what is actually
  dirty — so a write that was refused or already committed drops out by itself.
- **An older bug found on the way:** the git helper stripped the whole output, and the
  leading space of the first line of `status --porcelain` was eaten. The first file in every
  place was read one character short and counted as staged.

**What remains to be measured:** the other direction — **does it miss something the session
did write.** Annoying and not dangerous (the path is reported as `⚠ will not be committed`),
but now more common: every write through `Bash` falls there. **A real run has to show how
much of the work stays unattributed** — if most writes in practice are shell lines,
`--commit` will be empty most of the time and will not be worth its existence.

**The seal waits on that.** Not out of distrust of the command as a whole, but because
there is no point blocking the end of a turn on a report whose coverage is not yet known.

**And two more things to check.** Whether the guards actually fire in a live session — they
were verified by direct invocation and against the binary, **not end to end in a reloaded
session**. And whether the end-of-turn message wears out: if it is read and the command is
run, the seal is unnecessary; if it is skipped, the seal is required. **That is data which
collects itself, and only needs looking at.**

**And a hole that is already known.** `check_references.py` checks **paths written as
filenames**. It does **not** check the claims inside the declarations: `<slug>/store/**`
and `**/*.storekit` are patterns, not files, and if the structure beneath them changes
nothing will say so. **The mechanism built against staleness is not yet covered against
it.**
