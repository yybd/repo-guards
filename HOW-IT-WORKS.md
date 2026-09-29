*English · [עברית](HOW-IT-WORKS.he.md)*

# How it works (under the hood)

This document is the mechanics: how a hook or a skill gets from the file you edited into
the session that runs it, and why a change you just saved has not taken effect yet.

> **Navigation.** This document is the *how*. **[`README.md`](README.md)** is the *what*,
> and **[`CLAUDE.md`](CLAUDE.md)** carries the working rules for developing Grove itself.

---

## The three layers

Every change travels the same road, and there are three stations on it:

```text
1. the source        ← $GROVE, the repo you edit
2. the copy          ← ~/.claude/plugins/cache/, where Claude Code runs the code from
3. the session       ← what is loaded in memory, read once at session start
```

**The iron rule: the move between layers is not automatic.** Saving a file does not
update the copy, and an updated copy does not reach a session that is already running.

---

## Skills

**What it is.** One text file, `SKILL.md`, under `plugins/<plugin>/skills/<name>/`.

**How it reaches the copy.** `claude plugin install grove@grove` **copies** the subtree
the marketplace manifest points at into `~/.claude/plugins/cache/grove/grove/<sha>/`. The
directory name is grove's commit at the moment of installation, and since `plugin.json`
declares no version, that commit *is* the version.

**How it reaches a session.** At session start, and only then. What enters the context is
each skill's `name` and `description` — **not its body**, which is read when the skill is
invoked. So a library of skills costs descriptions per session, not documents.

---

## Hooks

**What it is.** A skill is text for the model; a hook is a program the harness runs.
[`plugins/grove/hooks/hooks.json`](plugins/grove/hooks/hooks.json) registers each guard
against an **event** and, where the event has one, a **tool matcher**. Claude Code starts
it as its own process and hands it the event payload as JSON on stdin.

| Event | When it fires | What the guard may answer |
|---|---|---|
| `PreToolUse` | before a matching tool call runs | allow · deny, with a reason the model reads · add context |
| `Stop` | at the end of a turn | a message on the screen |
| `UserPromptSubmit` | when a message is sent | text added to that turn's context |

The matchers name the tools themselves — `Write`, `Edit`, `Bash` — so a guard sees the
exact call it is about to judge, before it happens.

**The catch is the same as a skill's:** the hook that runs is the copy in the cache, not
the file you just saved in your editor.

---

## Deployment: three steps, and not one of them happens by itself

1. **Commit** — for the reason below, which is not tidiness.
2. **Refresh the copy** — `python3 tools/deploy.py`. It syncs the settings files from the
   registry, runs the right command per plugin, and verifies.
3. **Open a new session** — skills and hooks are read at session start.

### Why the commit comes first, precisely

`claude plugin update` **copies the working tree** and labels the copy with HEAD. Two
consequences follow, both measured here:

* an uncommitted edit lands in the cache under a commit that does not contain it — **the
  SHAs agree while the bytes differ**;
* `update` is a no-op once the recorded version equals HEAD, so from that moment the copy
  **cannot be repaired by `update` at all**. Only `uninstall` then `install` can.

That is the state `deploy.py` refuses to create: it stops while anything under `plugins/`
is uncommitted. `--dirty` overrides it, and is for deliberately testing an uncommitted
guard.

### How you find out the copy has gone stale

[`warn_stale_plugin_cache.py`](plugins/grove/hooks/scripts/warn_stale_plugin_cache.py), a
`Stop` hook. It **hashes every file on both sides and compares the bytes** — not the SHAs,
for the reason above — and names both what differs and the exact command that repairs
*that* case. It reports and never installs: a hook that silently changed installation
state would be a deployment nobody asked for.

It speaks only when the set of findings **changes**, so an unfixed gap does not shout
every turn, and it speaks in grove's own directory, because that is where the gap is made.

A session that is already running is locked to the copy it started with, and nothing can
change that from inside it.

---

## The registry

[`tools/registry.json`](tools/registry.example.json) says which repos exist in this tree
and which tracks each one loads. It is **machine data**: the repo ships
`tools/registry.example.json` and `deploy.py` copies it on a fresh clone.

**And it does not travel inside the plugin.** It changes every time a repo is registered,
so a copy pinned to the last installed commit would answer yesterday's question. The code
moves into the plugin and the data stays in the repo;
[`grove_repo.py`](plugins/grove/hooks/scripts/grove_repo.py) is the bridge that finds the
live file from a guard running out of the cache.

What it holds:

1. **where each project is** — written relative to the tree's base, so the same registry
   works on another machine;
2. **which tracks each one loads** — including tracks from other marketplaces, which grove
   reports and deliberately does not write;
3. **the anchors** — every entry's name becomes an environment variable (`$GROVE`, and one
   per repo), written into `~/.claude/settings.json` by every deploy. That is why a skill
   names `$SITE/content` and never a path belonging to one machine.

`/grove:register-project` is what writes an entry, from inside the repo being registered.

---

**In one line:** there is a layer you edit and a layer that runs, and crossing between
them is an explicit act. That separation is what keeps a session stable while you edit the
code that guards it — and it is why *"I committed it"* is never the same sentence as
*"it is running"*.
