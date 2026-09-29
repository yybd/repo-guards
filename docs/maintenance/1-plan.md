*English · [עברית](1-plan.he.md)*

# 1 — Keeping this repo true: what is checked, when, and what is only measured

**Type:** an operating plan. **Status:** in effect 2026-09-11.

---

## The problem this answers

Every check here already existed. What did not exist was **a moment at which any of them
is guaranteed to run.** `deploy.py` is thorough and runs only when a person types it;
the Stop guards run constantly and can only see the turn they are in. Between those two
sits a push — the act that publishes — with nothing in front of it.

And the checks were only ever run on **this machine, already set up**. Two bugs survived
exactly there until they were found by cloning into a temporary directory by hand: a
portability test that could not pass before a registry existed, and a deploy that failed
on a step its own README calls optional. Both are the same class: *correct on a
configured machine, broken on a new one.*

---

## Four cadences, and what runs at each

| when | what | who triggers it | cost |
|---|---|---|---|
| **every turn** | the Stop guards — work left open elsewhere, a cache diverged from its repo, an undeclared local skill | automatic | milliseconds |
| **every change to `plugins/` or the registry** | `python3 tools/deploy.py` — settings, installed copies, then every check below | a person | seconds |
| **every push** | `python3 tools/ci.py` — everything that needs no installation, on six machines | GitHub Actions | ~20s per job |
| **monthly, by hand** | the list in *What no machine can check* | a person | minutes |

**`ci.py` is the new one, and its value is not the checks — it is the clean room.** It
runs on a checkout with no plugins installed, no registry, and no settings, which is the
state of every new user and of no developer. That is why it catches what deploy cannot.

**And on more than one machine, since 2026-09-11.** macOS and Linux, across three
Pythons, six jobs. The floor is 3.9 because macOS still ships it as `/usr/bin/python3` —
the interpreter a user gets by typing `python3` without thinking about it — and the
standard library is the only dependency here, so there is nothing to install and no
excuse for not checking. The first run of that matrix found `check_scripts.py` printing
fifteen standard-library modules as third-party dependencies on 3.9.

```bash
python3 tools/ci.py             # the gate
python3 tools/ci.py --metrics   # …and the numbers as JSON
python3 tools/ci.py --record    # …appended to tools/metrics.jsonl
```

**What CI deliberately does not run:** `deploy.py`, `verify_guards.py` and anything that
compares against the plugin cache. A runner has no cache, so those would report an
absence as a fault — the noise that gets a checker ignored.

---

## What is measured, and why the history is kept by hand

`--record` appends one line per run to `tools/metrics.jsonl`: plugins, skills, guards,
total pipeline checks, documents, bilingual pairs, python files, the date and the commit.

**The gate runs in CI; the history is written locally.** A runner would have to commit
back into the repo to keep a series, and a repo that commits to itself on every push is
a repo whose history stops meaning anything. Recording is a deliberate act, taken when
something changed enough to be worth a datapoint.

**What the numbers are for.** Not targets — a drop in `pipeline_checks` after a refactor
is the question worth asking, and the file is there so the question can be asked at all.
The one number that is a rule: **`failed` must be empty in every recorded line.**

---

## The obligation to the other repo

The app factory runs **these scripts** against its own checkout —
`sync_project_settings.py` and `verify_guards.py`, with `GROVE_REPO` and
`GROVE_MARKETPLACE` in the environment — and imports `grove_repo` through its own
`factory/grove.py`. So four things here are a **public interface**, and changing one is a
change in two repos:

1. `grove_repo`'s function names and return shapes (`resolve_root`, `anchors`,
   `registry_roots`, `ownership_gaps`).
2. The `GROVE_*` environment variables that redirect a tool at another tree.
3. `warn_stale_plugin_cache.findings()` — imported in-process by both deploys.
4. The registry's shape, since both read the same file. It gained an optional `base`
   key on 2026-09-11 — where the tree sits, for an installation that did not clone grove
   beside its repos. Additive: a registry without it behaves exactly as before, and the
   other repo needs no change to keep working. It does need to know the key exists
   before it writes a registry of its own.

**And three checkers are copies, deliberately.** `check_references.py`,
`check_scripts.py` and `check_bilingual.py` exist in both repos. That is what lets the
app factory's CI run on a runner that has only that repo — the alternative, importing
them from here, would make its gate depend on a private checkout and a token. The cost is
real and was paid twice on the first day: **a fix in one is a fix in both.** Two of them
were found by CI itself — a `~/` path is the machine's and not the repo's, and a
third-party import that is absent on a runner is not a broken script.

**Nothing checks any of this automatically.** CI in each repo sees only its own. The rule is the
one the global rules already state: content before what points at it, and the broken
reference is how a half-finished cross-repo change is always discovered.

---

## What no machine can check

The honest limit, listed so it is done rather than assumed:

- **Whether a measurement is still true.** Every document here carries the date it was
  measured. A number from 2026-09-08 is not wrong because it is old — but it is a claim
  nobody has re-tested. `check_bilingual` reports numbers that appear in one language and
  not the other; it cannot tell you that both are now stale.
- **Whether a guard's judgement is right.** The pipelines prove it behaves as written.
  They cannot say the rule is the right rule.
- **What a script writes from the inside.** Stated in the guard's own docs rather than
  papered over; it is the known hole.
- **Whether the documentation still teaches the system that exists.** The split on
  2026-09-11 left two documents that were near-verbatim copies of each other, and no
  checker noticed — only reading did.

**Monthly, and after any structural change:** read one document end to end, re-run one
measurement it states, and follow the install instructions on a clone in a temporary
directory **with an empty `HOME`**. That last one is fifteen minutes and has now caught
four bugs — two of them on 2026-09-11, and both in the same fifteen minutes:

- `deploy.py` warned that cleaning old plugin versions had failed, on a machine that has
  no plugin cache because it has never installed one. A warning about the absence of a
  problem, on every new machine.
- and worse, it then said **"every installed copy already matches the repo, nothing to
  deploy"** — on a machine where grove was not installed at all. A missing
  `installed_plugins.json` was read as *nothing is known* rather than *nothing is
  installed*, so the one command a new user runs did nothing and reported success.

The empty `HOME` is the part that matters and the part that is easy to leave out: a
clone in a temporary directory still reads your `~/.claude`, and both of those bugs are
invisible while it does.
