*English · [עברית](README.he.md)*

# rules/ — standing instructions, versioned

`global-CLAUDE.md` is loaded in **every session in every project**, through a
symlink. It is the English copy; `global-CLAUDE.he.md` is the same rules in Hebrew,
kept beside it for the reader rather than for the agent:

```bash
ln -s $GROVE/rules/global-CLAUDE.md ~/.claude/CLAUDE.md
```

That one command is the whole install, and it is per machine.

## Why a symlink and not the plugin

A plugin cannot ship this. Plugins carry skills, agents, commands, MCP servers and
hooks — not memory. The settings key that *does* inject CLAUDE.md-style
instructions, `claudeMd`, is **only honored from managed/policy settings**, which is
an administrator surface, not something a user plugin can reach.

So the choice was between a symlink into this repo and a plugin-provided
`SessionStart` hook that injects the file's text as `additionalContext`. The
symlink wins because it uses the first-class mechanism: Claude Code loads
`~/.claude/CLAUDE.md` natively, always, with no code of ours in the path. The hook
would reimplement that with more moving parts and the same failure mode.

**Both fail silently.** A broken symlink and a broken hook each end with the rules
simply not there, and nothing announcing it. If the rules ever appear not to be in
force, check the link first:

```bash
readlink ~/.claude/CLAUDE.md && head -1 ~/.claude/CLAUDE.md
```

## This stacks with the project CLAUDE.md — it does not replace it

Memory files accumulate: the user-level file (this one, via the symlink) and a
project's own `CLAUDE.md` are **both** loaded. The settings schema names "User,
Project, and Local memory types" and offers `claudeMdExcludes` to leave one out —
an exclude list exists precisely because they all load together.

So this repo also carries `CLAUDE.md` at its root, for rules true only here. The two
are complementary by design, and must stay that way: unlike settings, which have a
documented precedence (user → project → local), **memory has no documented winner**.
Two files that contradict each other have no defined resolution, so never write a
rule in one that argues with the other.

The global file is named `rules/global-CLAUDE.md` rather than `CLAUDE.md` for a
different reason — not precedence but duplication. A `CLAUDE.md` at this repo's root
that the symlink also pointed at would reach a session running here twice, once as
user memory and once as project memory.

## Why not a skill

A skill loads on description match — only when something judges it relevant. A
standing rule must not depend on that judgement; it is least likely to trigger
exactly when discipline is slipping.
