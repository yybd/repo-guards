*English · [עברית](3-script-references.he.md)*

# 3 — How a skill refers to a script

**Status:** decided and applied 2026-09-08. Corrected 2026-09-10.

> **Where the numbers come from.** RepoGuards ships two skills of its own. Everything measured
> below was measured on **the app factory** — the marketplace of app-shipping tracks that
> stands on RepoGuards — because that is where a library large enough to have a placement
> problem actually exists. The rule is enforced here; the evidence was taken there.

## What was found

After the skills became a plugin, **39 references to scripts were still pointing at
`~/.claude/skills/`** — a directory they had left. 33 in the app factory, 6 in a site repo.
Nobody caught it during the migration, and neither did the guide.

**And one of them was not documentation.** A reviews-responder script loaded
`publish_aab.py` **at import time**, to share the Play API authentication:

```python
SHIP = os.path.expanduser("~/.claude/skills/play-store-ship/scripts/publish_aab.py")
_spec = importlib.util.spec_from_file_location("ship", SHIP)
_spec.loader.exec_module(ship)     # ← raises. Before a single argument is parsed.
```

So that skill **could not load at all**. The rest would each fail at the step they
guard — and that is usually exactly the step meant to catch problems: measuring copy
before delivery, validating character limits after an edit, checking parity before a
release.

## The decision: two forms, because a plugin boundary is a real boundary

### Inside the same plugin → `${CLAUDE_PLUGIN_ROOT}`

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/copy-edit/scripts/measure_copy.py <path>
```

**Why not an absolute path into the repo.** A plugin does not run from the working tree.
It runs from:

```
~/.claude/plugins/cache/<marketplace>/<track>/<sha>/
                                             ^^^^^ pinned to a commit
```

An absolute path to `$REPO_GUARDS/plugins/...` would be right today, wrong after every
update, and would not survive installing the marketplace on another machine.
`${CLAUDE_PLUGIN_ROOT}` resolves to what is **actually loaded**.

### Between plugins → the skill's name, never a path

`${CLAUDE_PLUGIN_ROOT}` is the **caller's** root. It cannot address another plugin, and
no variable can. So a cross-plugin dependency is written as what it really is — an
**invocation**:

> Run the **`copy-edit`** skill in parity mode — `--parity-only --fail-on-parity` — over
> `<paths>`. It is in another plugin: pass it the flags and let it find its own script.

**And here is what justifies it rather than merely excusing it:** when the called skill
runs, **its** `CLAUDE_PLUGIN_ROOT` is its own plugin's root. It resolves its own script,
correctly, on every installation. This does not work around the boundary — it is what a
plugin boundary means.

**No precision is lost.** The flags are the contract, not the path.

*Evidence that this is the natural form:* one skill already said *"Run the `copy-edit`
skill"* and only then gave a path. The name was there from the start; the path was the
redundant half.

### Code → relative to `__file__`

```python
SHIP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", "play-store-ship", "scripts",
                                     "publish_aab.py"))
```

Both scripts ship in the same plugin, so they are always together. Code should not
depend on an environment variable somebody set.

### Outside the plugin system → the repo path

A project's local skill, or a maintenance document, does not run inside a plugin and has
no `${CLAUDE_PLUGIN_ROOT}`. There, `$REPO_GUARDS/plugins/<track>/skills/...` is the
answer — stable, and the marketplace source points there anyway.

*A caveat worth knowing:* a project's local skills could name the skill instead of the
path, which would be more portable. They are project-specific and will never be
installed elsewhere, so the path holds — but if they are ever packaged as a plugin, that
is the line that breaks.

## The numbers

| | |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}` (same plugin) | 29 |
| skill name (cross-plugin) | 4 |
| relative to `__file__` (code) | 1 |
| repo path (outside plugins) | 5 |
| **total** | **39** |

Verified: 30 `${CLAUDE_PLUGIN_ROOT}` paths resolve to an existing file, 0 broken; zero
references to `~/.claude/skills/` left in either repo.

## What this teaches about the migration

The migration moved files and verified loading — and did not verify **what the files say
about themselves**. 39 references is a lot, and they survived a census, a guide, and a
session that wrote decision records.

**The conclusion for any future move:** after relocating skills, sweep the old path
across every affected repo — not only `.md`. The single reference that took a skill down
was inside a `.py`, and the first measurement missed it precisely because it scanned
only Markdown.

## Correction, 2026-09-10: three survived

**"Zero references left" was not true.** Three survived, all in `.sh` — so the
migration's real total was **42**, not 39:

| File | The reference |
|---|---|
| `apple-track/.../app-store-deliver/scripts/sync_from_hub.sh` | `measure_copy.py` |
| `android-track/.../play-store-deliver/scripts/sync_from_hub.sh` | `measure_copy.py` |
| `apple-track/.../appstore-media/scripts/capture_selfrender.sh` | `convert_preview.sh` |

**And the first two are exactly the case this measurement exists to catch.** The copy
gate is described in both `SKILL.md` files as blocking and "exits non-zero" — and in
practice, since the migration, **every delivery skipped it** and said so in a line that
reads like a footnote: `⚠ copy check skipped — no measure_copy.py at …`. Observed live
on 2026-09-10, shipping one app to both stores.

**This is what turns "a warning" into a serious bug:** `--skip-copy-check` exists so
that skipping is a **deliberate act**. When the tool is missing, "skipped" and "passed"
read identically in the output, and the default became exactly what the flag was there
to mark. So a missing tool at a blocking gate now **fails**, rather than warning.

### What the three add to the two forms

The original decision stands. But it covered **documentation**
(`${CLAUDE_PLUGIN_ROOT}` in a `SKILL.md`) and **code a skill runs**, and not these two
cases:

1. **A cross-plugin dependency inside a script.** `sync_from_hub.sh` must run
   `shared-track`'s `measure_copy.py` with no human in the loop, so "invoke the skill by
   name" is not available to it. And `${CLAUDE_PLUGIN_ROOT}` is no answer either: it is
   unset when a script is run by hand, and in the cache **each track has its own sha** —
   so `shared-track`'s path cannot be reached by walking relative to ours. The form is a
   **search**: `$0` first (the working tree), then the cache by globbing the sha.

2. **A template that is copied out of the skill.** `capture_selfrender.sh` is copied to
   `<slug>/media/apple/capture.sh`, so `$(dirname "$0")` points at **the copy in the
   hub** rather than at the skill. The form: beside the copy first, then the root, the
   cache, and the working copy.

**The conclusion that added itself:** the 2026-09-08 sweep did not only miss `.md` — it
missed `.sh`. "Sweep the old path across every file type" has to include **verifying
that the sweep itself comes back empty**, not merely counting what was fixed.
