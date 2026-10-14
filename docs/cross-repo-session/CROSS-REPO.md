*English · [עברית](CROSS-REPO.he.md)*

# Cross-repo work — the problems and the answers

A project is split across several repositories — the app (the code), the hub (metadata,
copy, prices), the site (the web presence).

## 1. The need: why would a session work outside its own directory?

Because of that split, real tasks touch several repos at once. Asked to "prepare a new
release", an agent first builds the code in the **app** repo — and immediately afterwards
has to update the release notes, which live in the **hub**. A session opened in repo A
must, as an ordinary part of its work, write files in repo B.

## 2. What that creates

Four dangers, all following from one fact: the agent sees only the directory the session
opened in.

1. **Bypassing ownership.** If the hub has a local skill or local rules (`CLAUDE.md`)
   that explain *how* to write there correctly, a session standing in the app writes
   from a distance and loads none of them — making silent mistakes, such as skipping a
   mandatory sync script after a change.
2. **Orphaned changes.** The agent runs `git status` to see what changed, and that
   command shows only the current directory. Files it changed in the hub simply drop out
   of view and stay uncommitted.
3. **Blind commits and pushes.** The agent may run a sweeping commit (`git commit -a`)
   into the other repo and gather up another session's waiting files by accident. Worse,
   a `push` from a distance publishes an entire branch it never read.
4. **Split memory.** What the agent learns about the hub during a session running in the
   app is written to the app's memory. The knowledge is stored in the wrong place and is
   never loaded again when working in the hub directly.

## 3. How RepoGuards answers each one

It does not forbid cross-repo work — that work is necessary and cannot be removed. It
puts up guards instead.

### Problem 1 (bypassing ownership): `honor_ownership`, and a detector

* **At the moment of the write.** Each project declares, in its own `.claude/owns.json`,
  the paths it owns. If the agent tries — from the app — to write a claimed path in the
  hub, the hook refuses and says which owner is not loaded here. It reads shell lines as
  well as editor calls. **Undeclared is open.**
* **The net against forgetting.** Nobody can be relied on to update `owns.json` when a
  new local skill appears, so enforcement (which must be fast) is separated from
  detection (which can be thorough). `tools/check_ownership.py` runs during `deploy`,
  sweeps every registered place, and reports a local skill with no claim — or a claim
  pointing at something that no longer exists. `warn_ownership_drift.py` asks the same
  question at the end of every turn, about the place the session is standing in.

### Problems 2 and 3 (the git blind spot): `scope_foreign_commits`

* **Refusing the sweep.** `git commit -a`, `git add .` and `git push` aimed at a repo the
  session is not standing in are blocked outright: the first two gather files blindly,
  and the third publishes a whole branch that cannot be recalled.
* **Handing over the picture.** When the command is precise and legitimate —
  `git add path/to/file` into a foreign repo — the hook allows it and **injects that
  repo's `git status` as context**: what is dirty there, which branch it is on, and how
  many commits are waiting to be pushed. The blind spot closes at the moment it matters,
  without anyone having to ask.
* **The end-of-turn net (`warn_uncommitted_roots`).** If a foreign file was changed and
  left uncommitted anyway, a separate hook says so before the turn ends.

### Problem 4 (split memory): lessons that travel, in `LESSONS.md`

Instead of relying on session memory — which is saved against the wrong directory —
knowledge gained during cross-repo work is written into a `LESSONS.md` **inside the
skill's own folder in RepoGuards**. Because the skill travels everywhere it is loaded,
its lessons travel with it, and they are available in every place the task runs.

## 4. The parts

**Hooks** (`plugins/repo-guards/hooks/scripts/`):

* `honor_ownership.py` — enforces declared ownership on writes from elsewhere.
* `scope_foreign_commits.py` — blocks sweeping git commands and `push` into a foreign
  repo, and injects that repo's status when it allows a call.
* `warn_uncommitted_roots.py` — at the end of a turn, names work left uncommitted
  elsewhere.
* `warn_ownership_drift.py` — at the end of a turn, reports a gap between a place's
  local skills and its `owns.json`.
* `record_touched_repos.py` — the silent recorder of which repos the session touched, so
  the hooks above know where to look.

**Scripts and structural files:**

* `tools/close.py` — reports every place the session touched in one table, and commits
  each one safely. Named to the agent by the git warnings themselves.
* `tools/check_ownership.py` — the deploy-time detector that no skill is left
  unprotected.
* `.claude/owns.json` — the declaration file in each target repo, stating which paths it
  owns.
* `LESSONS.md` — memory that lives inside a global skill's folder, so cross-repo lessons
  travel with the skill.
