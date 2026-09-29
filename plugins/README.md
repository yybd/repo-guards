*English · [עברית](README.he.md)*

# The plugins — how they reach every repo

**What this folder is.** The tracks grove distributes as plugins.

**What this document is.** Why it works the way it does, where exactly each thing is
stored, and why editing here does **not** reach a session until a command is run.

---

## In short — two facts

**1. Which repos load which track is decided by the registry,** through each repo's own
`.claude/settings.json`. `grove` is the exception: it is enabled at user scope and
therefore loads everywhere.

**2. What loads is not this folder — it is a snapshot of it.** Installation copied the
skills somewhere else, and every session reads from the copy. Editing here does not reach
it by itself. That second fact is the whole problem below.

---

## What is here

| Plugin | Skills | What |
|---|---|---|
| `grove` | 2 | `deploy` and `register-project` — the registry, and putting a repo on it |

*Counted from disk 2026-09-11.* One plugin, enabled at user scope, so its hooks run in
every repo. Everything below is about how a plugin reaches a session at all, which is the
same for the six app tracks that ship from **the app factory** and for any marketplace of
your own — the worked examples are drawn from there, because a one-plugin marketplace has
no update problem worth photographing.

---

## Where each thing is stored

### Two separate registrations

**The marketplace** — the catalogue. `~/.claude/plugins/known_marketplaces.json`. The
`grove` entry is of type `directory` and points at the repo itself. There is no
copy: `.claude-plugin/marketplace.json` is read live, in place.

**The plugin** — what is installed. `~/.claude/plugins/installed_plugins.json`. Here,
**even for a directory source, installation copies.** That is the confusing point: the
catalogue is live, the plugin is a snapshot.

### What the copy contains

Only the subtree the manifest's `source` points at. **No `.git`, no `docs/`, no
`tools/`, no `CLAUDE.md`.** Grove's rules do not travel with the plugin — see
[two routes to global](#two-routes-to-global).

### The directory name is the SHA

It is grove's commit **at the moment of installation**. Since `plugin.json` declares
no `version`, the SHA serves as one. That is why copies of different commits sit side by
side.

### `.in_use/` — why old versions stay

One file per live process reading that version. It is a refcount: it prevents deleting a
version an open session is still using. `claude plugin prune` clears what nobody holds.

### What enters a session's context

Not the skills' contents — only a `name` + `description` line for each. The body of a
`SKILL.md` is read only when the skill is invoked. The fixed per-session cost is 40
descriptions, not 40 documents. `claude plugin details <name>` shows the estimated cost.

---

## Two routes to global

Grove has **two** things that load in every session in every repo, by two entirely
different mechanisms:

| | The skills | The rules |
|---|---|---|
| What | `plugins/*/skills/` | [`rules/global-CLAUDE.md`](../rules/global-CLAUDE.md) |
| Mechanism | a plugin — **a copy** into the cache | a **symlink** from `~/.claude/CLAUDE.md` |
| What loads | the copy | the file itself, live |
| When an edit takes effect | only after `plugin update` + a restart | in the next session |
| When it breaks | a skill is silently missing | the rules are simply not there, silently |

**That is why `CLAUDE.md` is not in the plugin's copy.** A plugin carries skills, agents,
commands, MCP servers and hooks — **not memory.** There is no way to ship rules through
one.

The full reasoning — why a symlink and not a hook — is in
[`rules/README.md`](../rules/README.md).

**The practical difference:** the rules route does not have the staleness problem below.
Editing `global-CLAUDE.md` takes effect immediately, because there is no copy in the
middle.

---

## The problem: the copy does not update

### What updates it and what does not

| Action | Affects the copy? |
|---|---|
| `claude plugin update grove@grove` | **yes, if the SHA moved.** If it is identical — a no-op |
| `uninstall` then `install` | yes, always — the only way that works when the SHA has not moved |
| `claude plugin install` / `/plugin` | yes — a first installation |
| `claude plugin marketplace update grove` | **no** — it refreshes the catalogue only |
| editing a skill here | no |
| a commit · `git pull` | no |
| opening a new session | no |

The copy is read **at process start** — `update` says so explicitly, "restart required to
apply", and `.in_use` records a `procStart`. A running session is locked to the copy that
existed when it opened.

**There is no check at startup that compares SHAs.** Nothing warns.

### And `update` copies the working tree, not the commit

Measured, and both conclusions change the design:

**It copies from disk and tags it with HEAD.** An uncommitted edit enters the copy under a
SHA that does not contain it — that is, **the SHAs agree while the contents differ.**

**And it is a no-op when the SHA already matches**, even when the contents differ. A copy
holding content that is in no commit **cannot be repaired by `update`**; it requires
`uninstall` then `install`.

**Hence comparing SHAs is the wrong check in both directions**, which is why the hook below
compares content.

### And it has already happened

A gap was found: the installation was five commits behind HEAD, and one track was further
behind still.

**Three skills of one track had loaded in no session at all.** They were written,
committed, and existed nowhere that anything loads from.

The sharper piece of evidence was the plugin-level description: the text living in every
session on the machine was the old one. The description had gone stale too, not only the
list.

### It is a special case of [staleness](../docs/cross-repo-session/1-need-problem-solution.md)

The four properties described there apply here one by one:

**No owner** — nobody is responsible for asking whether the copy is current. **Silent and
self-assured** — a session loads 32 skills and declares them, with no sign that three are
missing. **The event does not check the record** — whoever writes a skill is busy writing;
the copy is somewhere else entirely.

The one difference in its favour: here the staleness **is mechanically detectable**. Two
SHAs, one comparison.

---

## Two approaches, and only one of them solves it

*Not decided.*

They must be kept apart, because they do not answer the same question.

### A. Detect — [`warn_stale_plugin_cache.py`](grove/hooks/scripts/warn_stale_plugin_cache.py)

***This is a detector, not a solution*** — the copy still goes stale, and you still run the
command and reopen a session by hand. What changes is that you know. The previous gap lived
two days in silence.

A `Stop` hook. **It compares content, not SHAs** — every file, hashed on both sides — for
the reason above. It reads `.claude-plugin/marketplace.json` to learn which subtree is each
track's source, rather than assuming the structure.

**Five findings,** each with its own correct fix:

| | And what it says |
|---|---|
| content differs, the SHA is behind | `claude plugin update` |
| content differs, the SHA already matches | `update` is a no-op here — `uninstall` then `install` |
| a track in the marketplace never installed | `install` |
| a copy that was registered and deleted from disk | reinstall |
| `~/.claude/CLAUDE.md` missing or pointing elsewhere | `ln -s` / `readlink` |

**The rules too, because they fail differently.** `rules/global-CLAUDE.md` loads through a
symlink and therefore **cannot go stale** — but it can break, and then the rules are simply
not there and nobody says so.

**Noise.** `git status` clears itself when you commit; a gap in the copy does not clear
itself, so without a latch the hook would shout every turn forever. It latches on the **set
of findings** per session and speaks only when that set **changes**.

**Scope.** Registered like any hook, so it runs at the end of every turn in every repo; its
first lines read `cwd` from the payload and exit if this is not grove. The gap is
created here, so the message is said here.

**It does not repair.** A hook that silently changes installation state performs a deploy
nobody asked for, and would still require a restart to have any value.

**Fails open.** A malformed registration, a malformed manifest, a missing file, stdin that
is not JSON — all silent, exit 0. The first version **failed this**: a malformed
`installed_plugins.json` made it report that every track was uninstalled. The pipeline
caught it, and the fix is that the reader returns `None` on unreadable input — *unknown* is
distinguished from *absent*.

**The pipeline:** [`tests/test_warn_stale_plugin_cache.py`](grove/hooks/scripts/tests/test_warn_stale_plugin_cache.py)
— 27 checks, run against throwaway trees only.

### B. Abolish the copy — `skills-dir`

*This is what actually solves it. Not adopted, because of the cost below.*

`~/.claude/skills/<name>/` loads **live** — no marketplace, no installation, no copy. A
directory containing `.claude-plugin/plugin.json` and `skills/` registers as
`<name>@skills-dir`.

**And it works through a symlink.** Tested with a probe track:

| What was tested | Result |
|---|---|
| a symlink from `~/.claude/skills/probe-track` to a directory outside `~/.claude` | registers and loads |
| a copy in `plugins/cache/` | **none** |
| an entry in `installed_plugins.json` or `settings.json` | **none** |
| adding a skill **after** the link exists, with no command at all | visible immediately |
| `claude plugin details` | works, token cost included |

That fourth row is the whole point: **there is nothing to update, because there is no
copy.**

**The cost.** In one line: **the copy is not merely a delay — it is a holding cell.** While
it exists there is a separation between what is written in the repo and what runs on the
machine, and crossing it is an explicit act. A symlink abolishes the separation, and **the
working tree becomes production.** Everything follows from that:

| | | Measured |
|---|---|---|
| **1. A track cannot be switched off** | `plugin disable` → *"not found"* | yes |
| **2. Uneven blast radius** | a malformed `SKILL.md` → the track survives, but the description is not read | yes |
| **3. `git` becomes `deploy`** | `checkout`, `rebase`, `stash`, returning to an old commit — all change what is loaded | yes |
| **4. No rollback** | the SHA was also a ceiling. The only way back is `git revert` | yes |
| **5. Breaks silently** | `plugin list` shows the error **if you look**; a session that opens simply lacks it | yes |
| **6. Migration** | `uninstall` is required **before** creating the link, or it loads twice | yes |

**1 and 3 are the significant ones.** 2, 4 and 5 are risks you can live with; 1 gives up an
existing capability, and 3 changes what you are allowed to do in this repo.

**3 carries particular weight here,** because it contradicts a rule that already exists:
*"`push` is not `deploy`"*. That rule exists because the separation between "I committed"
and "it is live" is worth something. On this route **`checkout` becomes deploy** — the same
fault in the opposite direction.

**And 1 reverses an earlier decision.** Being able to switch a track off is one of the
reasons the skills were moved to a marketplace in the first place.

### What was weighed and rejected in both

| | Why not |
|---|---|
| automatic update in a hook | it requires a restart anyway, and a hook that silently changes installation state is worse |
| relying on memory | the staleness document rules it out explicitly: there is no moment at which that happens |

**What neither covers.** Sessions that are already running are locked to what loaded when
they opened.

---

## Commands

```bash
claude plugin update grove@grove                # one
claude plugin list                              # what is installed, and at which version
claude plugin details grove                     # inventory and token cost
claude plugin prune                             # clear versions nobody holds
```

In every case — **restart the session** for the update to take hold. Or simply:

```bash
python3 tools/deploy.py
```

which does all of the above in the right order, and verifies.
