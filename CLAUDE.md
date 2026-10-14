*English · [עברית](CLAUDE.he.md)*

# RepoGuards rules

Loaded **in addition to** `~/.claude/CLAUDE.md` (which is a symlink to
`rules/global-CLAUDE.md` here), not instead of it. The global rules apply here too; what
follows adds to them and does not contradict them.

## Counts and numbers

**Count, do not copy.** Every number in these documents — how many guards, how many
checks in a pipeline, how many skills a track holds — is recounted from disk before it is
written. Measured in the app factory, where most of the numbers quoted here were taken: a
count copied from an earlier document was wrong twice, because it was duplicated without
being checked.

## Deciding where a skill belongs

**Decide against the files, not against the title.** Before deciding whether a skill is
global or local — read it and count how much of its content is tied to one particular
repo. Two skills measured in the app factory settled this: one that sounded like a thin
bridge turned out to be the deepest worker (455 lines, 28 references to one repo), and
one that sounded repo-specific turned out to be entirely generic (0). The reasoning is in
[docs/skills/](docs/skills/).

**"It does no harm there" is not a criterion.** The criterion is where the skill needs
to **load**.

## Migrations

**Verify before deleting.** In any skill migration — install and verify the destination
first, and only then delete the source. Temporary duplication is confusing; deleting
early leaves you with nothing.

## Deployment

**A commit is not a deployment.** Skills and hooks live inside a plugin, and a plugin is
a **copy** in `~/.claude/plugins/cache`. Between "I committed it" and "it is running"
there are two steps nobody takes for you, and one of them is opening a new session. On
2026-09-09 this happened twice in one hour: a guard was fixed, committed, reported as
fixed — and the machine went on running the broken code.

**After any change under `plugins/` or to `tools/registry.json`:**

```bash
python3 tools/deploy.py
```

It syncs the settings files from the registry, refreshes the installed copies, and
verifies. `--check` answers "is everything in place?" without changing anything. The
equivalent inside a session is `/repo-guards:deploy`.

**Commit before deploying.** `claude plugin update` copies the **working tree** and tags
it with HEAD, so deploying uncommitted work puts bytes in the cache that are in no
commit — and from that moment `update` cannot fix the copy, only a reinstall can.
`deploy.py` refuses to do it.

**And never report "fixed" on the strength of a commit.** The report comes after the
deployment, and with the sentence that it takes effect **in the next session**.

## Closing across places

**A session sees one `git status`.** What you left open anywhere else is not missing —
it is **invisible**, which is how "done" gets said over a clean status while the rest
sits open.

```bash
python3 tools/close.py
```

It reports **every** place the session touched: what you changed, what was already
there, what is staged, how many commits are unpushed — **and how many of those predate
the session**. `--commit -m "…"` closes them, each place separately and in its own
terms.

**It commits; it does not push and does not publish.** Those two are irreversible, and
what it gives instead is the thing you cannot do from memory: the exact push radius for
each place.

**And for an operation that declares where it lands** — `--op <name>` prints the list,
how each place closes, and runs that operation's state check. `--ops` lists who
declares. This is the only form that catches a place that **should** have been written
and was not; the journal only sees what was touched.

**It stages only paths the session actually wrote.** What changed in a place you did not
touch is reported and marked `⚠`, and never enters a commit — its first run found 101
such files.

## Staleness

**A record is written correctly, the world moves, and the record does not.** What
invalidated it sits somewhere else, so nobody looks. Measured: seven memories pointing
at paths that had vanished, and one migration that broke 39 references across two repos
— one of them inside an `import`, so the skill did not load at all.

**Most staleness cannot be detected mechanically** — *"the price is 9.99"* looks fine
even when it is wrong, and only asking the store settles it. **A path is the exception:**
either it is there or it is not.

```bash
python3 tools/check_references.py
```

It also runs inside `deploy.py`. It checks **only paths written as filenames** — not
prose, not numbers, not claims. The first version checked anything with a slash in it
and found 258 items, most of them `svh/dvh` and `next/font`. **A checker that reports
noise is a checker nobody runs.**

**The scripts the skills run are checked too** — `tools/check_scripts.py`, inside
`deploy.py`: that they parse, and that every import they name exists here. **Static
analysis only, nothing is executed** — these scripts sign artifacts and upload builds,
and a checker that runs them to see whether they work is a checker that ships something
by accident. Without it, a fault in one surfaces halfway through a release.

**And two language copies of one document drift apart** — `tools/check_bilingual.py`,
inside `deploy.py`. Nothing keeps `X.md` and `X.he.md` together; they are edited in
different sessions with no moment at which anyone compares. A missing counterpart is a
failure; a **number stated in one and not the other** is reported and never failed on,
because only a person can tell a real drift from a paragraph one side words differently.
Its first run, over the app factory, found two READMEs saying 40 skills and 35.

## The guards

**Seven guards, two of which block:** `honor_ownership` refuses a write to a path a
place **declared** in its own `.claude/owns.json` — and informs without blocking when
the path carries a rule rather than an owner; **undeclared is open**. It reads **shell
lines** too — redirections, `sed -i`, `cp`, `mv`, `tee`, `rm` — and not only the writing
tools; until 2026-09-10 a claim protected against `Edit` and was transparent to
`> file`. **What a script writes from the inside is out of reach**, and that is stated
rather than papered over. And `scope_foreign_commits` blocks two shapes in a foreign
repo — `commit -a`/`add .`, which sweep work you cannot see, **and `push`, which
publishes a whole branch and cannot be undone** (added 2026-09-10; before that it was
the most serious omission of the lot). The rest only report.

**And when it does not refuse, it shows.** A foreign write that names explicit paths is
allowed, and still blind: what is dirty there is invisible from here. So it hands back
the target's `git status` as context — not a decision, not a warning, but the picture
the session would have had standing there.

**What the guard cannot say is said twice elsewhere.** "Not declared" and "forgot to
declare" look identical to it — it must fail open, so it cannot tell them apart. The two
shapes asked are: a local skill nothing claims, and a claim that outlived what it
described — a skill name that is not here, or a path that vanished.

`warn_ownership_drift` asks them **at the end of every turn, about the place you are
standing in** — where the hole was made and where the reason is still remembered.
`tools/check_ownership.py` asks them **about every place, inside `deploy.py`**. Both
read `guards_repo.ownership_gaps`, because a detector that answers differently
depending on who asked is worse than none. And the Stop guard speaks only when something
**changed** — a gap already named stays quiet.

`plugins/repo-guards/hooks/scripts/honor_ownership.py` **must fail open.** Every
change to it is run across all its branches before it takes effect —
`tools/verify_guards.py` — because a guard that blocks by mistake stops work, and a
guard that crashes stops everything.
