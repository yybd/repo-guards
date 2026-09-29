#!/usr/bin/env python3
"""Find grove repo from a guard that is running out of the plugin cache.

The guards used to sit in the repo and find the registry two directories up. They
ship with grove now, and a plugin is COPIED into
`~/.claude/plugins/cache/grove/grove/<sha>/` at install time — so
`../registry.json` from a guard's own location no longer points at anything.

The registry is not shippable either. It is live data: it changes every time a repo
is registered, and a copy pinned to whatever commit was last installed would answer
yesterday's question. The code moves into the plugin; the data stays in the repo,
and this is the bridge.

Three ways to find the repo, in order, each one right for a different caller:

1. `GROVE_ROOT` — the pipelines set it, so a test never depends on where this
   machine happens to keep grove.
2. Walking up from this file — true when a guard runs from the repo itself, which
   is how every pipeline and every hand-run invocation works.
3. `known_marketplaces.json` — where Claude Code recorded the marketplace's own
   install location. This is the one that answers from inside the cache, and it is
   machine-independent: the repo can live anywhere as long as it was added as a
   marketplace, which it must have been for the plugin to exist at all.

Returns None rather than raising. Every guard fails open, and "I could not find the
factory" has to mean silence, not a traceback at the start of every session.
"""
import json, os, re, shlex

MARKETPLACE = "grove"


def _looks_like_grove(path):
    # registry.json is MACHINE data and is not in the repo — a fresh clone has only the
    # example. Recognising grove must not depend on having been set up yet, or the
    # very first `deploy.py` would be unable to find the thing it is standing in.
    return (os.path.isfile(os.path.join(path, ".claude-plugin", "marketplace.json"))
            and (os.path.isfile(os.path.join(path, "tools", "registry.json"))
                 or os.path.isfile(os.path.join(path, "tools", "registry.example.json"))))


def grove_root():
    env = os.environ.get("GROVE_ROOT")
    if env:
        p = os.path.realpath(os.path.expanduser(env))
        return p if os.path.isdir(p) else None

    here = os.path.dirname(os.path.abspath(__file__))
    while True:
        if _looks_like_grove(here):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent

    try:
        known = os.path.expanduser("~/.claude/plugins/known_marketplaces.json")
        loc = json.load(open(known, encoding="utf-8"))[MARKETPLACE]["installLocation"]
        loc = os.path.realpath(os.path.expanduser(loc))
        return loc if _looks_like_grove(loc) else None
    except Exception:
        return None


def dev_base():
    """The directory this whole tree lives under, on THIS machine.

    Every root the registry names is relative to it — so the registry says how the tree
    is SHAPED and this says where it happens to sit. That split is what lets the same
    registry work on a second machine: the shape is the same everywhere, the base never
    is.

    Three answers, in this order, and the middle one is why this is not just a
    derivation any more:

    1. `GROVE_DEV_ROOT` — one session, one tree, decided from outside.
    2. `base` in the registry — **the answer for an installation that did not clone
       grove beside its repos.** The derivation below assumes grove is one of the repos
       in the tree, which is true for whoever built it here and false for anyone who
       adds this as a marketplace from elsewhere: their grove sits wherever they put
       it, and every relative root in their registry would resolve next to it rather
       than next to their work. A product cannot ask its users to arrange their disk
       around it.
    3. the directory above grove — still the default, and still right for the common
       case of cloning it beside everything else.
    """
    env = os.environ.get("GROVE_DEV_ROOT")
    if env:
        p = os.path.realpath(os.path.expanduser(env))
        return p if os.path.isdir(p) else None
    try:
        with open(registry_path(), encoding="utf-8") as f:
            named = json.load(f).get("base")
    except Exception:
        named = None
    if isinstance(named, str) and named.strip():
        p = os.path.realpath(os.path.expanduser(named))
        if os.path.isdir(p):
            return p
        # A base that names a directory which is not there is a configuration error, and
        # falling through to the derivation would answer a different question quietly —
        # every root resolved against the wrong tree, with nothing said. Better to have
        # no base: resolve_root returns None, and a root that cannot be resolved is
        # reported rather than guessed at.
        return None
    root = grove_root()
    return os.path.dirname(root) if root else None


def resolve_root(value):
    """A root as the registry writes it → an absolute path here, or None.

    An absolute path (or `~/…`) is honoured unchanged. That is the escape hatch for a
    repo that genuinely lives outside the tree, and it is also what keeps every pipeline
    working: they point the registry at throwaway directories under /tmp.
    """
    if not isinstance(value, str) or not value:
        return None
    p = os.path.expanduser(value)
    if os.path.isabs(p):
        return os.path.realpath(p)
    base = dev_base()
    return os.path.realpath(os.path.join(base, p)) if base else None


def registry_path():
    """The live registry, or None. GROVE_REGISTRY still wins — the pipelines use it."""
    env = os.environ.get("GROVE_REGISTRY")
    if env:
        return env
    root = grove_root()
    return os.path.join(root, "tools", "registry.json") if root else None


def projects(reg):
    """(name, entry) for the real project entries in a loaded registry.

    Prose keys and non-dict values are skipped, and that is not tidiness. A single
    string under `projects` — a `_comment` or a `_note`, which is a normal thing to
    write in a hand-edited file — made `entry.get("root")` raise AttributeError. The
    exception escaped the loop, reached the guard's outer fail-open handler, and the
    boundary guard then ALLOWED EVERY WRITE on the machine, silently, with a zero exit
    code and no output. The guard whose entire purpose is to make a silent bypass loud
    could be switched off by a comment.

    Three guards read this map, all three had the flaw, and no pipeline could see it
    because the live registry happens to keep its prose at the top level. It is one
    function now so the invariant has one place to be true.
    """
    for name, entry in (reg.get("projects") or {}).items():
        if not name.startswith("_") and isinstance(entry, dict):
            yield name, entry


def apps(reg):
    """(name, entry) for the real app entries. Same reasoning as projects()."""
    for name, entry in (reg.get("apps") or {}).items():
        if not name.startswith("_") and isinstance(entry, dict):
            yield name, entry


def registry_roots(reg):
    """(name, root, entry) for every repo the registry names — projects AND apps.

    The registry keeps its repos in two lists, and they do not share a key: a project
    names its path in `root`, an app in `repo`. Three guards read only projects() and
    were therefore blind to all six app repos. Measured 2026-09-09: the Stop guard's
    roots were the four `projects` entries — so uncommitted work an
    outside session left in any APP repo was never reported, which is exactly the
    failure the commit rule exists to prevent, in the repos most likely to be written to
    from outside. scope_foreign_commits' own docstring claimed it covered "EVERY registry
    root" while covering none of them.

    One function, so the two lists cannot drift apart again — the same reasoning that
    made projects() one function after a prose key switched off three guards at once.
    """
    for name, entry in projects(reg):
        root = resolve_root(entry.get("root"))
        if root:
            yield name, root, entry
    for name, entry in apps(reg):
        repo = resolve_root(entry.get("repo"))
        if repo:
            yield name, repo, entry


def has_local_skills(root):
    """True when the repo carries a skill of its own — a SKILL.md, not just a directory.

    `protected: auto` means "protected exactly while local skills own these files", and
    it is meant to RELEASE when they are removed. Removing the duplicated skills from
    two web repos on 2026-09-09 left an empty `.claude/skills/`
    behind; os.path.isdir stayed true, and both repos went on refusing every write from
    outside while naming no owner at all — the denial text said "owns its files through
    skills" and then listed none. A guard that blocks by mistake stops work, which
    CLAUDE.md names as the worse of the two failures. An empty directory is not an owner.
    """
    d = os.path.join(root, ".claude", "skills")
    if not os.path.isdir(d):
        return False
    try:
        return any(os.path.isfile(os.path.join(d, n, "SKILL.md")) for n in os.listdir(d))
    except Exception:
        return False


def keys_root(reg=None):
    """Where credentials live — NEVER inside a repo. An anchor, nothing more.

    Grove itself has no secrets and no opinion about them. This exists because a skill
    that needs one — in this marketplace or in any other layered on top — must be able
    to write `$KEYS_ROOT/<whatever>` without knowing what this machine called its
    secrets folder, or whether it has one at all. Named in the registry (`keys_root`,
    relative to the tree's base like any root); `KEYS_ROOT` in the environment wins,
    for a folder outside the tree entirely — an external disk, a mounted vault.

    Returns a path whether or not it exists: "it should be here and is not" is an
    answer the caller can act on, and creating a folder for someone's secrets behind
    their back is not this code's decision.
    """
    env = os.environ.get("KEYS_ROOT")
    if env:
        return os.path.realpath(os.path.expanduser(env))
    if reg is None:
        try:
            with open(registry_path(), encoding="utf-8") as f:
                reg = json.load(f)
        except Exception:
            reg = {}
    named = reg.get("keys_root") if isinstance(reg, dict) else None
    return resolve_root(named or "keys")


def site_root(reg=None):
    """The tree's website repo, when there is one — `$SITE`. Often there is not.

    One more anchor, and optional by construction: a tree with no website is an
    ordinary case, so this returns None rather than a default, and whoever names `$SITE`
    is responsible for saying what to do when it is absent.

    Found by the registry entry a project marks with `"site": true`, or failing that by
    an entry literally named `site`. Not by guessing from a role string — a guess here
    would point work at the wrong repo.
    """
    if reg is None:
        try:
            with open(registry_path(), encoding="utf-8") as f:
                reg = json.load(f)
        except Exception:
            return None
    projects = (reg.get("projects") or {}) if isinstance(reg, dict) else {}
    for name, entry in sorted(projects.items()):
        if name.startswith("_") or not isinstance(entry, dict):
            continue
        if entry.get("site") is True or name == "site":
            return resolve_root(entry.get("root"))
    return None


def anchors(reg=None):
    """The variables a skill may stand on → where they point on THIS machine.

    A skill cannot name `/Users/someone/Developer/<repo>`, because on the next machine
    that is somewhere else. It names `$<REPO>`, and this is the one table that says
    what that means. Derived from the registry rather than listed, so a repo registered
    tomorrow is nameable tomorrow — and so the table cannot drift from the registry,
    which is the failure this repo has already had twice.

    `deploy.py` writes these into the machine-local settings so the shell has them too;
    `check_references.py` expands them to check the paths still exist. Same table.
    """
    if reg is None:
        try:
            with open(registry_path(), encoding="utf-8") as f:
                reg = json.load(f)
        except Exception:
            reg = {}
    out = {"DEV_ROOT": dev_base(), "GROVE": grove_root(),
           "KEYS_ROOT": keys_root(reg)}
    site = site_root(reg)
    if site:
        out["SITE"] = site
    for name, root, _entry in registry_roots(reg):
        out[re.sub(r"[^A-Z0-9]", "_", name.upper())] = root
    return {k: v for k, v in out.items() if v}


CLAIMS = os.path.join(".claude", "owns.json")


def local_skills(root):
    """Skill names this repo carries of its own — a directory counts only with a SKILL.md."""
    d = os.path.join(root, ".claude", "skills")
    if not os.path.isdir(d):
        return []
    try:
        return sorted(n for n in os.listdir(d)
                      if os.path.isfile(os.path.join(d, n, "SKILL.md")))
    except Exception:
        return []


def _owners(claim):
    """The skills one claim names. `owner` may name several, separated by · or comma."""
    raw = claim.get("owner")
    if not isinstance(raw, str) or not raw.strip():
        return []                                  # a rule, not an owner
    return [q.strip() for q in re.split(r"[·,]", raw) if q.strip()]


def ownership_gaps(root):
    """[(kind, what, why)] where a place and its declaration stopped agreeing.

    Lives here, next to the guard, because the guard is the thing it is about: what
    honor_ownership CANNOT report. "Not declared" and "someone forgot to declare" look
    identical to it — it must fail open, so it cannot tell them apart, and a rule added
    there would cost on every tool call. This is the same question asked where it is
    cheap: once at the end of a turn, and once more across every place at deploy.

    Both directions, because a declaration rots in two ways — a skill that nobody
    claimed, and a claim that outlived what it described.
    """
    skills = local_skills(root)
    decl = os.path.join(root, CLAIMS)
    gaps = []

    if not os.path.isfile(decl):
        if skills:
            gaps.append(("no declaration at all", ", ".join(skills),
                         "the skills here author paths nobody declared — and that looks "
                         "exactly like a place that chose to be open"))
        return gaps                                # no skills and no claims: nothing to say

    try:
        with open(decl, encoding="utf-8") as f:
            claims = json.load(f).get("claims") or []
    except Exception as e:
        return [("the declaration cannot be read", CLAIMS,
                 f"{e} — and the guard reads that as 'no claims'")]

    claimed = set()
    for c in claims:
        if not isinstance(c, dict):
            continue                               # prose in a data file happens
        claimed.update(_owners(c))
        paths = c.get("paths")
        paths = [paths] if isinstance(paths, str) else (paths or [])
        for q in paths:
            if isinstance(q, str) and not os.path.exists(os.path.join(root, q.rstrip("/"))):
                gaps.append(("claim on a path that does not exist", q, "the guard will never fire on it"))

    for s in skills:
        if s not in claimed:
            gaps.append(("a local skill nothing claims", s,
                         "its paths can be written from anywhere, silently"))
    for o in sorted(claimed - set(skills)):
        gaps.append(("a claim naming a skill that is not here", o,
                     "either the skill moved to grove and the claim is stale, "
                     "or it was deleted and nothing authors that path any more"))
    return gaps


# ─────────────────────────────────────────────────────────────────────────────
# Reading a shell line — shared, because two guards judge the same line
#
# `honor_ownership` asks "what does this write" and `scope_foreign_commits` asks "which
# repo does this act on", and both first have to answer the same smaller question:
# WHICH COMMANDS ARE IN THIS LINE, AND WHAT DIRECTORY DOES EACH ONE RUN IN. Each had its
# own splitter, and each was defeated by the same one-character trick — a leading `(`.
# Measured 2026-09-11 against a throwaway pair of repos: `(cd ../other && git commit -am
# x)` was allowed in silence by one, and `(cd $SITE && echo x > src/pages/p.astro)` by
# the other, while both refused the identical line without the parentheses.
#
# One splitter, for the same reason projects() is one function: a question answered
# differently depending on who asked is worse than not asking it.

_OPEN, _CLOSE = "({", ")}"
_SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
# Commands that run ANOTHER command and are transparent about it. `sudo tee f` writes f.
_WRAPPERS = {"sudo", "doas", "env", "command", "builtin", "exec", "nohup", "nice", "time",
             "stdbuf", "setsid", "ionice"}
_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*=")
MAX_COMMANDS = 64                                  # a pathological line costs nothing


def _split(text):
    """A shell line → its sequentially executed pieces, respecting quotes.

    Both guards used to split on a regex, which reads a separator INSIDE a quoted string
    as a separator: `bash -c \'cd there && rm x\'` came apart in the middle of its own
    argument, and both halves were then unparseable and therefore allowed. Splitting has
    to know what is quoted before it can know what is a boundary.

    `$( … )` is kept whole for the same reason, one level down: what is inside it is
    another command line, and this one is not it.
    """
    out, buf = [], []
    quote, subst, i, n = None, 0, 0, len(text)
    while i < n:
        c = text[i]
        if quote:
            buf.append(c)
            if c == "\\" and quote == '"' and i + 1 < n:
                buf.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "'\"":
            quote = c
            buf.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            buf += [c, text[i + 1]]
            i += 2
            continue
        if text[i:i + 2] == "$(":
            subst += 1
            buf.append(text[i:i + 2])
            i += 2
            continue
        if subst:
            if c == ")":
                subst -= 1
            buf.append(c)
            i += 1
            continue
        if text[i:i + 2] in ("&&", "||"):
            out.append("".join(buf))
            buf = []
            i += 2
            continue
        if c in ";\n|":
            # `>|` is one token — a deliberate overwrite — not a redirect followed by a
            # pipe. Splitting there left the path in a piece of its own, where nothing
            # reads it as a write, so the one form a shell user reaches for when they
            # mean "clobber it" was the one form that was never judged.
            if c == "|" and "".join(buf).rstrip().endswith(">"):
                buf.append(c)
                i += 1
                continue
            out.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    out.append("".join(buf))
    return out


def _unwrap(tokens):
    """(real command, the environment assignments in front of it).

    `sudo tee x`, `env FOO=1 cp a b`, `GIT_DIR=../x git commit` — all of them hide the
    command behind a word that is not the command. A wrapper's own FLAGS are deliberately
    not modelled: the strip stops at the first `-`, so `sudo -u someone tee f` reads as
    an unknown command and is allowed. Under-reading is the safe direction in a guard.
    """
    env, out = {}, list(tokens)
    while out:
        first = out[0]
        if _ASSIGN.match(first):
            k, _, v = first.partition("=")
            env[k] = v
            out = out[1:]
            continue
        if os.path.basename(first) in _WRAPPERS and len(out) > 1 and not out[1].startswith("-"):
            out = out[1:]
            continue
        break
    return out, env


def _shell_c(tokens):
    """The command string a shell was handed with -c, or None.

    `bash -lc "$CMD"` is a variable and stays unreadable on purpose — the guard sees a
    command it cannot resolve and allows it, which is the documented edge.
    """
    if os.path.basename(tokens[0]) not in _SHELLS:
        return None
    for i, t in enumerate(tokens[1:], 1):
        if t.startswith("-") and not t.startswith("--") and "c" in t[1:]:
            arg = tokens[i + 1] if i + 1 < len(tokens) else None
            if arg and "$" not in arg and "`" not in arg:
                return arg
            return None
    return None


def shell_commands(cmd, cwd):
    """[(tokens, cwd, env)] — every command in a shell line, and where each one runs.

    `cd` is tracked across segments, and **undone when its group closes**. That is not
    tidiness: reading `(cd ../other && git status); git commit -am x` as though the `cd`
    leaked would make the second command look foreign and get it refused — and a guard
    that blocks by mistake stops work, which is the worse of the two failures.

    A subshell's contents are read (`(…)`, `{…}`, `sh -c '…'`); `cd` segments are
    consumed rather than returned, since neither caller has anything to say about one.
    """
    out = []

    def absolute(p, here):
        p = os.path.expanduser(p)
        return os.path.realpath(p if os.path.isabs(p) else os.path.join(here, p))

    def walk(text, here, budget):
        if budget <= 0:
            return
        stack = []
        for raw in _split(text):
            piece = raw.strip()
            # `piece and` is not defensive noise: "" is a substring of every string, so
            # `piece[:1] in _OPEN` is True for an empty piece — and a lone `}` from
            # `{ cd there && rm x; }` spun this loop forever on its own emptiness.
            while piece and piece[0] in _OPEN:
                piece = piece[1:].lstrip()
                stack.append(here)
            closes = 0
            # A trailing `)` belongs to a command substitution when the piece opened one;
            # stripping it there would take the end off a command rather than a group.
            while piece and piece[-1] in _CLOSE and "$(" not in piece:
                piece = piece[:-1].rstrip()
                closes += 1
            if piece:
                try:
                    tokens = shlex.split(piece)
                except Exception:
                    tokens = []                    # unparseable segment: allow it
                tokens, env = _unwrap(tokens)
                if tokens:
                    if tokens[0] == "cd" and len(tokens) > 1 and not tokens[1].startswith("-"):
                        here = absolute(tokens[1], here)
                    else:
                        inner = _shell_c(tokens)
                        if inner is not None:
                            walk(inner, here, budget - 1)
                        else:
                            out.append((tokens, here, env))
            for _ in range(closes):
                if stack:
                    here = stack.pop()
            if len(out) >= MAX_COMMANDS:
                return

    walk(cmd, os.path.realpath(os.path.expanduser(cwd)), 3)
    return out
