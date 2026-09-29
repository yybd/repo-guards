*English · [עברית](README.he.md)*

# Grove (Cross-Repo Guards)
**The safety and orchestration layer for AI agents in multi-repo environments.**

An AI agent (like Claude Code) is a brilliant tool when operating within a single project folder (Repository). However, in the real world, tasks cross boundaries: shipping a feature requires a code change (App), a data schema update (Hub), and editing a marketing page (Web).
The moment the agent "reaches out" to a foreign directory, it loses touch with reality. Because the `git status` command is limited to its current working directory, the agent might blindly overwrite another developer's open files, push code to the wrong branch, or perform a destructive blind commit.

**Grove was built to solve exactly this.** It is a set of guardrails that run inside the session, at the moment of the tool call: they detect the anomaly, refuse the two actions that cannot be undone, and hand the agent back the picture it was missing so it can correct itself.

---

## The Components: What does Grove do?

The system provides 3 critical solutions:

### 1. Active Guardrails (The Guard Hooks)
* **Blocking Blind Commits (`scope_foreign_commits`):** If the AI stands in directory A and attempts to run `git commit -a` in directory B, the system blocks it. Instead of a generic failure, it injects the true state of the foreign directory (including the branch name and open files), instructing the AI to commit only specific files.
* **Honoring Boundaries (`honor_ownership`):** If a file is claimed by another project (via `.claude/owns.json`), the hook refuses to let the AI edit it, redirecting the agent to the proper location.

### 2. Smart Contextual Committing (`close.py`)
An agent updating 3 projects simultaneously leaves a trail of changes. Standard Git commands break down here.
The script `$GROVE/tools/close.py --commit` reads which files **this specific session** wrote across every directory, and stages only those — never a sweep. What it claims is deliberately narrow: a path counts only if a writing tool of this session named it and it is still dirty, so a parallel session's work can never be swept into your commit. The cost of that choice is stated plainly under *Known limits*.

### 3. The Central Registry (`registry.json`)
The brain that tracks which projects exist on your machine, and which "Skill Tracks" each project is allowed to load. This prevents an agent in an iOS app from loading Android deployment commands. (The system syncs perfectly with other skill libraries, such as the [App Factory](https://github.com/yybd/app-factory)).

---

## Installation

Because Grove manages your environment, it is usually **the first product you install**, sitting alongside your other projects (typically under a `<base>` directory like `~/Developer`).

```bash
git clone https://github.com/yybd/cross-repo-guards.git <base>/cross-repo-guards
claude plugin marketplace add <base>/cross-repo-guards
python3 <base>/cross-repo-guards/tools/deploy.py
```

`deploy.py` is the whole installation: it creates your `tools/registry.json` from the shipped template, installs the plugin, and verifies. It prints what it did — read that rather than assuming. **Then open a new session**, because hooks and skills are read at session start.

**Optional, and reported by every deploy until you do it or decide not to** — the working rules, loaded in every session in every repo:

```bash
ln -s "<base>/cross-repo-guards/rules/global-CLAUDE.md" ~/.claude/CLAUDE.md
```

If you already have a `~/.claude/CLAUDE.md`, that link would replace it. Move yours aside first, or skip this step: nothing else depends on it.

### Connecting a New Project
For the guardrails and skills to activate in a specific project (e.g., your frontend repo), enter the project and run:
```bash
/grove:register-project
```
This command reads the project, writes its entry in Grove's `registry.json`, and generates a local `.claude/settings.json` in the project itself.

**What registration does and does not change.** The guards are always on — they ship with the plugin, which is enabled for your user, so they run in every repo whether or not it is registered. Registration decides two other things: **which skill tracks load there**, and whether the end-of-turn guard **reports work you left uncommitted** in it. So an unregistered repo is not protected-by-being-ignored; it is a repo that quietly loads no tracks.

That is why an unregistered repo says so, once per session. **It asks three times and then stops interrupting** — after that it is a single line, still said every session, because the thing it reports does not go away on its own. Two answers end it: register the repo, or list it under `ignored`. On a machine full of repos that are nobody's business, `GROVE_OFFER=off` in the environment, or `"offer_registration": false` in the registry, ends it everywhere.

---

## Ground Rules for AI Agents (Cross-Repo)

While working on a project in parallel with others, these are the rules Grove enforces:
1. **Read the Injected Intelligence:** The moment you touch a foreign directory, the system injects a `[foreign]` message containing the remote status (including the Branch name). The agent must read this before continuing its edits.
2. **Never `push` remotely:** Commands like `git -C ../other-repo push` are completely blocked. Push publishes an entire branch, which is too aggressive when executed "through the wall."
3. **Do not collect garbage:** Never run `add .` on a foreign directory. Work surgically with exact paths, or let `close.py` do the heavy lifting for you.
4. **Turn Completion Report:** At the end of any prompt where the agent left foreign files open without committing them, Grove's Stop Guard will surface a warning to the screen: "You left a mess elsewhere."

---

## Known limits

A guard that pretends to full coverage is worse than one whose edge is known. These are the edges, and they are tested:

* **What a script writes from the inside is out of reach.** `python3 build.py` can write anywhere, and nothing in the command line says so. The guards read tool calls and shell lines; they are not a file-system watcher.
* **A command whose target is computed cannot be judged.** `git -C $DIR push` or a path built by `$(…)` resolves at run time, inside the shell — so the guard sees a variable and, by design, allows it. Everything it cannot parse with confidence, it allows.
* **It fails open, always.** A malformed payload, an unreadable registry, a missing file — every one of them allows the operation. A guard that blocks by mistake stops work; a guard that crashes stops everything.
* **`close.py` under-claims rather than over-claims.** A file written through a shell line is reported as changed but is never staged for you, and the report says so.

---

## How does it work inside?

Want to know how the Hooks intercept commands or how the Plugin Cache works?
Read the full documentation:
* **[How It Works (HOW-IT-WORKS.md)](HOW-IT-WORKS.md)** — Under the hood: Cache, Hooks, and Registry loading mechanics.
* **[CLAUDE.md](CLAUDE.md)** — The constitution and guidelines the agent reads when operating inside this specific Repo (for developing Grove itself).
* **[Docs & Reasoning (docs/)](docs/)** — Every architectural decision (what was measured, why alternative solutions were rejected) is logged there.

---

**License:** MIT
