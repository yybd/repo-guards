*English · [עברית](1-skill-placement.he.md)*

# 1 — Where a skill lives: global against local

**Status:** applied. The criterion stands; one debt is open (see *What is left*).

> **Where the numbers come from.** RepoGuards ships two skills of its own. Everything measured
> below was measured on **the app factory** — the marketplace of app-shipping tracks that
> stands on RepoGuards — because that is where a library large enough to have a placement
> problem actually exists. The rule is enforced here; the evidence was taken there.

## The question

When does a skill belong to a marketplace track (and load in every session it is
enabled for), and when does it belong to a project's repo (and load only from inside
it). The case that forced the
decision: three design skills that sat in a site repo and looked like the most
"site-specific" skills in the system.

## The criterion

> **The criterion is where the skill needs to load. "It does no harm there" is not a
> criterion.**

The rule is recorded in `CLAUDE.md` here. It was written after it turned out
that the design skills sat in the site not by decision but by convenience — they landed
there, and it did no harm.

## What was measured (2026-09-08)

**Repo-specific references, in the skills we considered moving:**

| Skill | References | What they are |
|---|---|---|
| `web-design-guidelines` | 0 | — |
| `frontend-design` | 1 | *"Example: one project's spec locks a system-font stack"* |
| `page-builder` | 1 | *"in this repo: `npm run ship`"* |

Both are **illustrations, not dependencies**. None of the three reads a file belonging to
the site, runs a command in it, or knows its directory layout. Two of them were not
written for it at all: `frontend-design` is a general frontend skill, and
`web-design-guidelines` is a published set of web interface guidelines.

*Correction 2026-09-08:* a commit message claimed "zero repo-specific references" for two
of them. Recounted with a wider pattern there is one in each, and both are examples. The
conclusion does not change; the number does.

**For comparison — the skills that stayed in the site repo, same count:**
`add-app-to-site` 39, `translate-site` 12, `reference-page` 8. Those simply cannot run
anywhere else.

## The price of global — measured, not estimated

This was the reasonable objection: a skill that applies only to the website, why carry it
in every session. The measurement settles it. **What sits in context is the description
alone; the skill's body is read only when it is invoked.**

| | Characters | ≈ tokens |
|---|---|---|
| 32 descriptions (always in context) | 28,186 | ~8,000 |
| 32 bodies (only when invoked) | 932,559 | ~266,000 |

**A 33:1 ratio.** And for the three design skills alone: descriptions 1,199 characters ≈
**343 tokens**, bodies 92,365 ≈ 26,390.

So the price of keeping them global is **343 tokens per session**. Had the bodies loaded,
26,390, there would have been something to discuss. They do not.

*Updated 2026-09-09:* the skills are **35**, and the descriptions **31,602** characters —
+12% in one day. The conclusion here does not change, but the growth itself is a figure
nobody had weighed, and it is measured in [`2`](2-global-cost.md). That document also
records a third axis this decision did not consider: **the file's location and the scope
of its activation are two questions**, and only the first was asked here.

## Why it was decided this way

Two concrete things, not theory:

1. **The evidence that arrived by itself.** RepoGuards' dashboard was built in a
   session here **with none of the three design skills loaded**, because they were locked
   inside the site repo. A generic skill parked inside one project is exactly the skill
   that is missing everywhere else it is relevant.
2. **Capacitor.** A Capacitor app's UI is HTML and CSS. The design work on it happens in
   the app's repo — which is neither the site nor the marketplace. A skill sitting in the
   site is absent precisely there.

`page-builder` is the only borderline one, and it travelled because the three are **one
pipeline** — structure (`page-builder`) → aesthetics (`frontend-design`) → review
(`web-design-guidelines`) — and its own description points at the other two. Splitting
the trio costs more than moving the borderline member.

## The real price — and it is not the tokens

A description in context is not only volume, it is **an invitation to invoke**. The move
created a genuine collision:

- `web-design-guidelines`: *Use when asked to **"review my UI"**, **"check accessibility"**, "audit design"*
- `apple-hig-design-review`: *whenever the user wants a **design review**… **improve accessibility**…*

In a macOS app session, "review my UI, check accessibility" fits both. Before the move it
could not have happened. **That is the debt the move created, and it is the right thing to
worry about — not the tokens.**

## The rule derived for future skills

The test is not "what does it apply to" but these two:

1. **Is the description precise enough that it will not fire outside its domain?** If so
   — global is nearly free.
2. **Does its absence elsewhere cost real work?** If so — global is necessary.

**Local** is right when the skill is **tied to a tree** and cannot run anywhere else at
all.

### Clarification 2026-09-09 — the trap in that rule

The rule above says: local if the skill is tied to a tree and cannot run elsewhere. **It
is easy to apply it wrongly, like this:**

> *"This skill cannot run without `app-hub` — the profile, the prices and `DATA.md` are
> there. So it is tied to the hub, therefore it is local, therefore it belongs in
> `app-hub`."*

**That sounds like the rule and is its opposite.** Measured: **31 of 35 skills depend on
the hub.** If that reasoning held, 31 skills would move into `app-hub` and the app factory
would be left with four.

**The root:** there is a difference between **reading data from the hub** and **living in
the hub**. The hub is the data layer for every app — reading from it is what everyone
does, and therefore signals nothing.

**The corrected test** is not *"which repo does it touch"* but **"how many trees does one
of its actions span"**:

| | How many trees | |
|---|---|---|
| `price-sync` | the hub · app repos · the site | **global** |
| `add-app-to-site` | the site only | **local to the site** |

**And why "one tree is not one app".** `app-hub` is **one tree** even though it serves
dozens of apps. So it too is a legitimate home for a local skill — but only for one that
works **entirely inside it**, such as one maintaining the hub's own schema. **There are
none today.**

The rule here was written against a site repo and carried a silent, unwritten assumption:
that a project's repo contains one project. The full account is in
the app factory's own `docs/skills/`, where the hub and the site are measured.

## What is left

- **The debt from the move:** sharpen `web-design-guidelines`'s description to say
  web/HTML explicitly, so it does not compete with `apple-hig-design-review`.
- **A stale line:** `page-builder/references/checklists/pre-delivery.md` says *"in this
  repo: `npm run ship`"*. The instruction itself is parametric and correct; the
  parenthetical was written when the skill lived in the site, and now "this repo" is
  whichever repo the session stands in.

## An open observation

On disk all 32 skills have a valid `description`. In the list loaded into a session on
2026-09-08, **11 of them appeared by name only**, with no description. The frontmatter
structure, the description lengths and the keys were all checked — **no pattern was
found**; skills with longer descriptions did appear. It is probably a display behaviour
of the list rather than a loading failure, **but it was not verified**. If it is a
failure, it bears directly on invocation and therefore on this whole document.
