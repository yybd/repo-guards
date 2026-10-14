---
name: deploy
description: >-
  Put what the RepoGuards repo holds onto this machine, and answer "is everything in
  place?". Use when a skill, guard, hooks.json or the registry has changed and needs
  to take effect, when the user says "פרוס", "deploy RepoGuards", "עדכן את
  התוספים", "update the plugins", "בדוק שהכול במקום", "is everything deployed", when
  a skill or guard that was just edited does not seem to be running, or when the
  stale-plugin-cache warning appears at the end of a turn. It syncs the settings
  files from the registry, refreshes the installed plugin copies with the right
  command per plugin, and verifies — then says plainly that a new session is needed.
---

# Deploy RepoGuards

## The one fact this exists for

**Committing changes nothing.** Skills and guards live inside a plugin, and a plugin
is a *copy* under `~/.claude/plugins/cache/repo-guards/<track>/<sha>/`. Between "I
committed it" and "it is running" sit two steps nobody performs for you — refreshing
that copy, and opening a new session.

On 2026-09-09 this produced the failure twice in one hour: a guard was fixed,
committed, and reported as fixed, while the machine kept running the broken copy.
Both times it was caught by accident.

## Run it

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/repo_guards.py deploy
```

That form works before the first deploy has ever run; `python3 $REPO_GUARDS/tools/deploy.py`
is the same command, and `$REPO_GUARDS` is a variable **deploy itself writes**, so it is empty
on a machine that has not run it yet — which is exactly the machine that needs this.

`--check` reports without changing anything — that is the answer to "is everything in
place?". Read its output rather than summarising it from memory; it names what was
stale and what it ran.

Three steps, in this order, because each one's output feeds the next:

1. **registry → settings files.** `tools/registry.json` decides which tracks each
   repo loads; `sync_project_settings.py` writes them. First, because refreshing a
   copy before the setting that decides whether it loads means doing it twice.
2. **repo → installed copies.** Per plugin, and not always the same command — see
   below.
3. **verify.** Every guard pipeline, plus a byte-for-byte comparison of each
   installed copy against the repo.

## Two things to get right

**Commit before deploying.** `claude plugin update` copies the *working tree* but
labels it with HEAD. Deploying uncommitted work therefore puts bytes in the cache
under a commit that does not contain them — and because `update` then sees a matching
version, it will refuse to touch that copy ever again; only a reinstall can fix it.
`deploy.py` refuses rather than let that happen. `--dirty` overrides it, and is for
deliberately testing an uncommitted guard, not for saving a commit.

**`update` is not always the right command.** When the recorded version already equals
HEAD but the content differs, `update` is a no-op and the copy needs
`uninstall && install`. `deploy.py` reads which case each plugin is in from
`warn_stale_plugin_cache.py`'s findings rather than assuming.

## Then tell the user the truth

**Say that it takes effect in the next session.** Nothing deploy does changes what is
already loaded in the session you are in — skills and hooks are read at session start.
Reporting "deployed" without that sentence recreates the exact failure this skill
exists to end, five minutes later.

If `deploy.py` reported problems, say which ones and stop. Do not report success
because the command completed; report what its last line said.
