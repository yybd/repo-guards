---
name: register-project
description: >-
  Put a repo on the registry so its tracks load — or record that it is
  deliberately left off. Use when a session opens in a repo RepoGuards does not
  know, when the user says "register this repo", "רשום את הפרויקט", "why aren't the
  skills loading here", "למה אין לי את הסקילים", when a store or release skill is
  missing in a repo that plainly needs it, or when a repo should be excluded so the
  offer stops coming back. It reads the repo to decide what it is, proposes the
  tracks that follow, writes the registry entry and the repo's own settings, and
  commits each in its own repo. Run it from the repo being registered.
---

# Register a project with RepoGuards

## Why this skill exists at all

Every other track is opt-in per project: it loads only where a
`.claude/settings.json` says so, which is generated from `tools/registry.json`.
That is what stops sixteen Apple skills from loading in a website repo.

It also creates one failure, and this skill is the whole answer to it. **A repo
nobody registered loads nothing** — silently. Nothing errors; the skill you
expected is simply not in the list, and the session does the work the long way
without ever saying a track was missing. RepoGuards' README names that exact
shape as the dangerous one: *the file never stops you; the missing skill does, and
quietly.*

So this skill is the only one that loads everywhere, and its job is to make the
silence loud exactly once, at the moment it can be fixed.

## Where you are

**Run from inside the repo being registered.** You need to read its files to know
what it is, and its `.claude/settings.json` is what you write. The registry lives
in RepoGuards (`$REPO_GUARDS/tools/registry.json`) and is reached by
path — RepoGuards declares no claim over it in its own `.claude/owns.json`, and undeclared
is open, which is precisely why writing it from here is allowed.

If the user asks you to register some *other* repo, move the session there
(`change_directory`) rather than guessing from outside. Reading a repo from
outside works; classifying one you cannot browse does not.

## 1. Is it already known?

Read `tools/registry.json` and look for this repo's real path under `projects`
(`root`), `apps` (`repo`), or `ignored` (`root`). Compare resolved absolute paths,
not names — a symlinked or renamed directory is the same repo.

**What gets registered is a directory, not a git repo.** Claude Code resolves a
project's `.claude/settings.json` against the session's cwd, so the registered root
is wherever a session actually stands — usually the git top-level, but not always:
one registry entry on the machine this was measured on points at a subdirectory,
`<repo>/web`, while the git repo itself is `<repo>` — because that subdirectory is
where sessions are opened.

The two directions of containment are **not** the same answer, and treating them as
one was a bug until 2026-09-09:

- **A registered root inside this directory** → already answered. Registering the
  tree above it would be asking about something the registry has settled.
- **This directory inside a registered root** → *not* answered. Settings resolve
  against the cwd, so a session standing here loads none of that repo's tracks —
  measured with `claude plugin list`: a registered project loads five tracks and
  its `apps/mobile` subtree loads none. Two answers are legitimate, and the
  user picks: **reopen the session at the root** (nothing to register — this is
  usually the right one), or **register this directory in its own right**, which
  gives it its own `.claude/settings.json` and loads the tracks here from the next
  session. Register a subdirectory only when the user actually works from it; every
  extra entry is another settings file to keep in sync.

- **Found under projects/apps at this exact path** → it is registered. If its tracks
  are not loading, the settings file is out of sync: run the check in step 5 and stop.
- **Found under ignored, at this path or above it** → the user already said no. Say
  so, name the reason recorded there, and do nothing unless they ask to reverse it.
- **Not found** → continue.

## 2. Decide what it is — against the files

RepoGuards' rule is that a placement decision is made against the contents, not
the title. `add-app-to-site` sounded like a thin bridge and turned out to be the
deepest worker in the site; `frontend-design` sounded like a site skill and was
entirely generic. A repo's name is the same kind of evidence: suggestive, not
deciding.

**Look below the root, not only at it.** This studio nests the buildable project one
level down: an app repo holds `CLAUDE.md`, `PLAN.md`, `app/`, `build/` and `Capacitor/`,
and every marker below lives inside that `Capacitor/` directory — the config, the
`android/` and `ios/` pair, the `package.json`. Judging the root alone finds nothing
and concludes `none`, and the one thing that looks conclusive from the root is a
directory *named* `Capacitor`, which is exactly the name-not-contents shortcut this
section forbids. All of the studio's Capacitor apps are shaped this way, so search
two levels deep before concluding anything:

```bash
find . -maxdepth 4 -type d \( -name node_modules -o -name 'build*' -o -name .git \
  -o -name Pods \) -prune -o \( -name 'capacitor.config.*' -o -name 'package.json' \
  -o -name '*.xcodeproj' -o -name 'build.gradle' -o -name 'Package.swift' \) -print
```

Two details in that command are load-bearing, both found by running it here rather
than reasoning about it. **maxdepth 4**, because the iOS marker sits at
`Capacitor/ios/App/App.xcodeproj` while the config is at depth 2 — stopping at 3
reports an Android-only app that in fact ships both. And **`-type d` on the prune**,
because without it `build*` matches the *file* `build.gradle` and silently drops
every Android signal. Pruning also matters on its own: `Capacitor/build-dd/` and
`build-sim/` hold vendored `.xcodeproj` files from Swift package checkouts, which
look exactly like evidence and are not.

Then look for what is actually there, and say what you found — including *where* you
found it, since a marker two levels down is the normal case here rather than a
surprise:

| Kind | What actually says so |
|---|---|
| `app` | `capacitor.config.*`, an `android/` **and** `ios/` pair, `*.xcodeproj`/`*.xcworkspace`, a `Package.swift` with an app target, `build.gradle` with `com.android.application` |
| `web` | a site framework in `package.json` (astro, next, vite, eleventy…), `public/` + `src/pages`, an `i18n/` tree, a deploy config (`netlify.toml`, `vercel.json`) |
| `hub` | no code — profiles, store copy, media, prices. Data a build reads, not a thing that builds |
| `none` | everything else: a library, a scratch repo, someone else's clone, a tool |

Two traps worth naming, because both have happened here:

- **A web repo that holds copies of tracked skills is still a web repo.** Two were
  found in that state on 2026-09-09. The duplicates are a separate problem — the
  registration is still `web`.
- **An app with no store presence yet is still an app.** Registration is about
  which tracks load, not about whether anything has shipped.
- **One store is still an app.** A Capacitor project with `android/` but no `ios/`
  is an `app`; whether to keep apple-track is a question for step 3, not a reason to
  classify it as something else.

If the evidence is thin or mixed, say what you found and ask. Do not register on a
guess — a wrong entry is worse than no entry, because it stops the offer from
coming back.

## 3. Propose the tracks

`track_defaults` in the registry is the proposal table for each kind. Read it —
do not quote the list from memory; it changes when a track is added or split, and
the project rule is to count from disk rather than copy from a document.

Show the user the kind you concluded, the evidence, and the tracks that follow,
and let them cut or add. Three answers are all legitimate:

- **register with tracks** — the normal case.
- **register with `tracks: []`** — the repo is known to RepoGuards (the Stop
  guard reports uncommitted work in registry repos) but loads no tracks. This is
  what RepoGuards itself carries.
- **ignore** — add it to `ignored` with a one-line reason. That is the answer for
  a clone, a scratch repo, or anything not yours. Say plainly that this is what
  stops the offer returning; an offer that keeps coming back after being declined
  is how a prompt stops being read.

## 4. Write the registry entry

In `tools/registry.json`:

- **anything** goes under `projects` with `root`, `role` and `tracks`. That is the
  whole of what RepoGuards reads, and it is the right answer unless the line below applies;
- an **app** goes under `apps` instead — but only in a tree that already has that
  section, because it belongs to the marketplace that ships apps rather than to RepoGuards.
  There it carries `repo`, `tracks`, and whatever identifiers that marketplace reads
  (`hub_slug`, `platforms`). Follow the entries already there; do not invent the shape;
- an **ignored** repo goes under `ignored` with `root` and why.

**Read `_extensions` at the top of the registry before writing an entry.** RepoGuards reads
`projects`, `ignored` and `keys_root`; every other section is somebody else's, and a
registration that invents keys nobody reads looks exactly like one that works.

**There is no protection flag to set.** `protected` and `open_paths` were deleted on
2026-09-10: a place declares what it owns in its own `.claude/owns.json`, and the
registry has no opinion about it. If the repo you are registering carries local skills,
say so and offer to write that declaration — `tools/check_ownership.py` will report it
as a gap at the next deploy either way.

Write `tracks` as an explicit array even when it equals the default. The default
is a proposal table; the entry is the decision, and a reader must not have to
re-derive one from the other.

## 5. Generate the settings and verify

From RepoGuards:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/repo_guards.py sync_project_settings --check
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/repo_guards.py sync_project_settings
```

(`python3 $REPO_GUARDS/tools/sync_project_settings.py` is the same command, once `$REPO_GUARDS`
exists — it is written by the first deploy, and the form above needs no variable.)

The script owns only the `repo-guards@repo-guards` keys inside `enabledPlugins` and
leaves everything else in those files alone. Run `--check` first and read it: it
is also how you diagnose a registered repo whose tracks are not loading.

## 6. Commit — two repos, two commits

This change lands in two repos, so it is two commits, never one:

1. **RepoGuards** — the registry entry. Message in RepoGuards' terms: a project
   was registered and which tracks it draws.
2. **the repo itself** — its `.claude/settings.json`. Message in that repo's terms:
   it declares which tracks it loads.

Content before the thing that points at it: commit the registry first. A
half-applied pair is always found through the broken reference, not the missing
content.

Do not push. Pushing is asked for, never assumed.

## 7. Tell the user the truth about when it takes effect

**The tracks load from the next session, not this one.** Enabling a plugin is read
at session start; nothing you write now changes what is already loaded. Say this
explicitly rather than letting them discover it by asking for a skill that still
is not there — that is the same silent failure this skill exists to end, arriving
five minutes later.
