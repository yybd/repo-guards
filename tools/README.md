*English · [עברית](README.he.md)*

# tools/ — the control plane

Not skills. These are the parts of RepoGuards that a person runs: the registry of where every
project lives, the deployment that makes an edit real, and the commands that keep the
records honest.

*Counted from disk 2026-09-11: ten scripts here, seven guards in the plugin.*

## The scripts, and which question each answers

| | |
|---|---|
| `deploy.py` | **"make what this repo holds real on this machine."** Settings from the registry, then the installed copies, then verification. `--check` answers *is everything in place* without changing anything |
| `ci.py` | **"is this checkout sound?"** Everything that needs no installation — the gate a push is measured against, and the only thing that exercises a fresh clone |
| `close.py` | **"what did this session leave open, everywhere?"** One table per place, and `--commit` closes each one in its own terms |
| `sync_project_settings.py` | writes each registered repo's `.claude/settings.json` from the registry's `tracks`, and the anchors into the machine's own settings |
| `verify_guards.py` | the guard gate: every pipeline, plus a byte-for-byte comparison of each installed copy against this repo |
| `check_references.py` | every path these records point at — does it still exist |
| `check_ownership.py` | every local skill declared, every claim still pointing at something |
| `check_scripts.py` | the scripts a skill hands to a session: do they parse, do their imports resolve. **Static only — nothing is executed** |
| `check_bilingual.py` | the two language copies of a document, and whether they have drifted |
| `touched_report.py` | reads the journal: does a session really touch more than one repo, and does it reach beyond the registry |

**How a skill reaches them.** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/repo_guards.py <tool> …`
— the plugin knows where it is installed, and that shim knows how to get from there to
this repo. The equivalent `python3 $REPO_GUARDS/tools/<tool>.py` is the same command *once
`$REPO_GUARDS` exists*, and `$REPO_GUARDS` is written by the first deploy — so the skill whose job is
to run that first deploy could not name it. The tools stay here rather than being copied
into the plugin, for the reason the registry already forced: a plugin is a copy pinned to
a commit, and a tool shipped inside it would be yesterday's tool operating on today's
repo.

**And one of them can execute something you did not write.** `close.py --op <name>` reads
a skill's `places.json`, which may declare a command that reports the state of its
places — and declarations are collected from every installed plugin on the machine, any
marketplace you have ever added. Ours run; anyone else's is printed for a person to read,
and `--run-state` is the deliberate act. Running a shell line because a file asked is the
shape of a supply-chain attack, and it would run under your shell, with your keys.

## The invariant

> **A place's files may be written from outside only if nothing there declares that it
> owns them.**

A repo carrying its own `.claude/skills` has *local* owners — skills that load only when
the session's working directory is that repo. Writing there from an outside session always
appears to work: the file lands, git commits, nothing errors. It simply bypasses the skill
whose job that file was. The failure is silent, which is why it needs a guard rather than
a convention.

### And ownership is declared, never guessed

Each place writes what it owns in its own `.claude/owns.json`, and the guard reads only
that:

```json
{
  "claims": [
    {"paths": ["src/pages/", "src/data/apps.ts"], "owner": "add-app-to-site",
     "action": "block", "why": "the page structure is written by this skill"},
    {"paths": ["content/en.json"], "action": "warn",
     "why": "edit the JSON, run `npm run content`, commit both together"}
  ]
}
```

**Two actions, and they are not a dial.** `block` is for a path a local skill *authors* —
reading a skill from outside is no substitute for running it, so writing there genuinely
skips something. `warn` is for a path that carries a **rule** rather than an owner: the
write may be perfectly legitimate, it just has to know something first.

**Undeclared is open.** The predecessor blocked a whole repo to protect three subtrees and
needed two exception lists in the registry to stay usable; both were deleted on
2026-09-10. This has nothing to maintain and no exceptions to keep in sync. The cost is
that a place which declares nothing is protected by nothing — which is the honest default,
and why the drift checks below exist.

## registry.json

**Three things here are RepoGuards', and the rest is somebody else's.** It reads `projects`
(where each repo is, and which tracks it loads), `ignored` (repos deliberately left off,
so the offer stops returning) and `keys_root` — an anchor, because a skill that needs
credentials must be able to name a folder this machine has without knowing what it is
called. Anything else in the file belongs to whichever marketplace put it there: a repo
has one identity, and splitting it across two registries is how two answers drift apart.
The `apps` section in the shipped template is exactly that, and a tree that ships nothing
should delete it.

Where each project is, which tracks it loads, and — through the names of its entries —
what every anchor variable means on this machine. It is machine data: the repo ships
`registry.example.json`, and `deploy.py` copies it on a fresh clone.

**The guards read both lists.** `projects` and `apps` are two lists of repos differing
only in which key names the path (`root` / `repo`), and three guards once read `projects`
alone — so the app repos, the ones a release session is likeliest to write into from
elsewhere, sat outside every boundary. They all go through
`guards_repo.registry_roots()` now, so the two lists cannot drift apart again.

## The guards — seven, and they arrive with the plugin

They ship inside `RepoGuards`. `plugins/repo-guards/hooks/hooks.json` registers them, so installing
that plugin is what puts them on a machine: there is no install step of ours and no entry
in `~/.claude/settings.json`. RepoGuards is the always-on plugin, which is exactly the scope
these need — a guard protecting one repo from another repo's session has to load in that
other session.

| file | event · matcher | denies / reports |
|---|---|---|
| `honor_ownership.py` | `PreToolUse` · `Write\|Edit\|MultiEdit\|NotebookEdit\|Bash` | a write to a path another place declared it owns |
| `scope_foreign_commits.py` | `PreToolUse` · `Bash` | `commit -a` / `add .` / `push` aimed at a repo the session is not standing in — and hands back that repo's status when it allows one |
| `record_touched_repos.py` | `PreToolUse` · most tools | records only: which repos this session touched, and what it wrote |
| `warn_uncommitted_roots.py` | `Stop` | work this session left uncommitted in a registry repo |
| `warn_stale_plugin_cache.py` | `Stop` | the repo and the installed plugin copies have diverged |
| `warn_ownership_drift.py` | `Stop` | a local skill nothing declares, or a claim that outlived what it described |
| `offer_registration.py` | `UserPromptSubmit` | this repo is on no registry list, so no track loads here |

**They fail safe, in two different ways.** The `PreToolUse` guards fail *open* — any error,
malformed payload or missing registry allows the operation, because a broken guard must
never stop the work. The `Stop` and `UserPromptSubmit` hooks fail *silent*: they have
nothing to permit, and one that raises every turn is worse than none.

`offer_registration` sits on `UserPromptSubmit` rather than the `SessionStart` it obviously
belongs on, because **the desktop app does not display SessionStart hook output at all** —
it ran there correctly for three rounds and reached the model and the transcript but never
the screen.

**The registry does not travel with them.** It is live data, rewritten every time a repo is
registered, so a copy pinned to the last installed commit would answer yesterday's
question. `guards_repo.py` bridges the two: `REPO_GUARDS_ROOT`, then walking up from the file,
then the marketplace's own `installLocation`, which is what answers from inside the cache.

### What the guards cannot see

Stated here rather than papered over, because a guard that pretends to full coverage is
worse than one whose edge is known:

* **what a script writes from the inside** — `python3 build.py` can write anywhere, and
  nothing in the command line says so;
* **a target that is computed** — `git -C $DIR push`, a path built by `$(…)`: it resolves
  in the shell, at run time, and the guard sees a variable;
* **a command string it cannot parse with confidence** — which it therefore allows.

## The gate: run it before committing a guard

`install.py` used to be the gate, because installing was the moment a guard took effect.
That moment is now `claude plugin install/update`, which this repo does not own — so the
gate moved to where the change is made:

```bash
python3 tools/verify_guards.py
```

It runs every pipeline, says which copy is actually running and whether it matches HEAD,
and reports registrations left over from the hand-registration era (`--clean` removes
exactly those). Any pipeline can also be run on its own:

```bash
python3 plugins/repo-guards/hooks/scripts/tests/test_scope_foreign_commits.py
```

Or exercise a guard by hand — output means denied, and the JSON carries the reason; no
output means allowed:

```bash
echo '{"cwd":"/some/other/place","tool_input":{"file_path":"<a path some place declared it owns>"}}' \
  | python3 plugins/repo-guards/hooks/scripts/honor_ownership.py
```

Why each guard exists, and what was rejected on the way — [`docs/cross-repo-session/`](../docs/cross-repo-session).
