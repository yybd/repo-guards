#!/usr/bin/env python3
"""PreToolUse guard: refuse a git command that reaches too far into a foreign repo.

Two shapes, one guard: a commit that SWEEPS work you cannot see, and a push that
PUBLISHES a branch you have not looked at.

The rule this enforces:

    A commit into a repo the session is not standing in may stage ONLY the paths
    it meant to write.

`git -C <elsewhere> commit -am` from here stages every TRACKED file modified there
(`git add .` also takes the untracked ones). What is dirty there is invisible to this
session — its `git status` is the cwd's — so the sweep is silent and lands in someone
else's commit. Measured 2026-09-08: app-hub's 17 files are all ` M`, tracked and
modified, which is exactly what `-a` takes. On 2026-09-08 app-hub carried
17 uncommitted files of the owner's own work while sessions elsewhere were writing
to it; that is the failure, not a hypothetical.

Sibling to honor_ownership.py, deliberately separate: that one matches
Write|Edit and never sees a commit, since commits travel through Bash. Kept apart
so a change here cannot break the file guard.

Scope differs from its sibling on purpose: this applies to EVERY registry root,
including `protected: never`. That flag means "you may write here from anywhere",
which says nothing about being free to sweep whatever is dirty here into a commit.

**And when it does not refuse, it shows.** A foreign git command that stages explicit
paths is allowed — but the session still cannot see what else is dirty there, which is
the same blindness one step short of the sweep. So an allowed foreign write carries the
target's `git status` back as context: not a warning, not a decision, just the picture
the session would have had if it were standing there. Costs one `git status` on a git
command that reaches into another registered repo, and nothing at all otherwise.

Reads the hook payload on stdin, answers on stdout. Fails OPEN: any error, any
command it cannot parse with confidence, allows — a guard that blocks by accident
stops work, and one that crashes stops everything.
"""
import json, os, subprocess, sys
# The guard ships inside grove and runs from the plugin cache, where
# nothing sits two directories above it. grove_repo finds the live repo — and reads the
# shell line, which its sibling guard must read the same way.
from grove_repo import registry_path, registry_roots as all_registry_roots, shell_commands

REGISTRY = registry_path()

# git subcommands that CHANGE the foreign repo. A read (log, status, diff, show) needs
# no picture — it is one. `clean` is here for a reason of its own: it deletes untracked
# files, which git cannot give back, in a repo whose dirt is invisible from here.
WRITES = {"add", "commit", "rm", "mv", "restore", "reset", "checkout", "apply",
          "stash", "cherry-pick", "revert", "merge", "rebase", "clean"}
SHOW_MAX = 8                                      # lines of foreign status; enough to judge


def real(p):
    return os.path.realpath(os.path.expanduser(p))


def picture(root):
    """What a session standing in `root` would see. None when git cannot answer."""
    try:
        p = subprocess.run(["git", "-C", root, "status", "--porcelain"],
                           capture_output=True, text=True, timeout=5)
        if p.returncode != 0:
            return None
        lines = [ln.rstrip() for ln in p.stdout.splitlines() if ln.strip()]
        
        b = subprocess.run(["git", "-C", root, "branch", "--show-current"],
                           capture_output=True, text=True, timeout=5)
        branch = b.stdout.strip() if b.returncode == 0 else ""

        a = subprocess.run(["git", "-C", root, "rev-list", "--count", "@{u}..HEAD"],
                           capture_output=True, text=True, timeout=5)
        ahead = a.stdout.strip() if a.returncode == 0 else ""
    except Exception:
        return None
        
    out = []
    if branch:
        out.append(f"  [current branch there: {branch}]")
        
    if not lines:
        out.append("  (clean — nothing uncommitted there)")
    else:
        out += ["  " + ln for ln in lines[:SHOW_MAX]]
        if len(lines) > SHOW_MAX:
            out.append(f"  … and {len(lines) - SHOW_MAX} more")
    if ahead.isdigit() and int(ahead):
        out.append(f"  ({ahead} commits there are unpushed — a push publishes all of them)")
    return out


def registry_roots():
    """Every root in the registry, protected or not — projects AND apps.

    "EVERY registry root" is what the docstring above has always said and what this
    did not do: it read `projects` only, so the six app repos — the ones a release
    session is most likely to commit into from elsewhere — were exempt from the sweep
    check entirely. Fixed 2026-09-09.
    """
    roots = []
    try:
        reg = json.load(open(REGISTRY))
    except Exception:
        return roots
    return [(name, r) for name, r, _ in all_registry_roots(reg)]


def root_of(path, roots):
    """The registry root containing `path`, or None."""
    for name, r in roots:
        if path == r or path.startswith(r + os.sep):
            return name, r
    return None


def resolve(p, base):
    p = os.path.expanduser(p)
    return real(p if os.path.isabs(p) else os.path.join(base, p))


def git_target(tokens, here, env):
    """The working tree this git command acts on.

    `-C` was the only form read, so the two that say the same thing in other words —
    `--git-dir` / `--work-tree`, and `GIT_DIR` / `GIT_WORK_TREE` in front of the command
    — pointed a sweeping commit at a foreign repo while the guard looked at the cwd and
    saw nothing foreign at all. Measured 2026-09-11: `git --git-dir=../other/.git
    --work-tree=../other commit -am x` was allowed in silence.
    """
    base, opts, i = here, {}, 1
    while i < len(tokens):
        t = tokens[i]
        if t == "-C" and i + 1 < len(tokens):
            base = resolve(tokens[i + 1], base)
            i += 2
            continue
        if t in ("--git-dir", "--work-tree") and i + 1 < len(tokens):
            opts[t.lstrip("-")] = tokens[i + 1]
            i += 2
            continue
        if t.startswith(("--git-dir=", "--work-tree=")):
            k, _, v = t.partition("=")
            opts[k.lstrip("-")] = v
            i += 1
            continue
        if t.startswith("-"):
            i += 1
            continue
        break
    tree = opts.get("work-tree") or env.get("GIT_WORK_TREE")
    if tree:
        return resolve(tree, base)
    gitdir = opts.get("git-dir") or env.get("GIT_DIR")
    if gitdir:
        p = resolve(gitdir, base)
        return os.path.dirname(p) if os.path.basename(p) == ".git" else p
    return base


def split_sub(tokens):
    """(subcommand, its arguments) after dropping `git` and any pre-subcommand option."""
    i = 1
    while i < len(tokens):
        t = tokens[i]
        if t in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            i += 2
            continue
        if t.startswith("-"):
            i += 1
            continue
        break
    return (tokens[i], tokens[i + 1:]) if i < len(tokens) else None


def subcommand(tokens):
    found = split_sub(tokens)
    return found[0] if found else None


def sweeping(tokens, target=None, root=None):
    """(subcommand, flag) if these git tokens stage beyond explicit paths, else None.

    Deliberately narrow: only patterns whose sweep is unambiguous. Anything else
    — an unknown subcommand, a flag we do not model — returns None and is allowed.

    `target` and `root` are what let a PATHSPEC be recognised as a sweep. `add .` was
    caught by a list of literals, so the same instruction spelled as a path —
    `git -C ../other add ../other/`, or the repo\'s absolute path — walked through: it
    stages everything in the repo and looked like an explicit path.
    """
    found = split_sub(tokens)
    if not found:
        return None
    sub, args = found

    if sub == "commit":
        skip = False
        for a in args:
            if skip:
                skip = False
                continue
            if a in ("-m", "--message", "-F", "--file", "--author", "--date"):
                skip = True
                continue
            if a in ("--all",):
                return ("commit", a)
            # short bundle containing 'a' (-a, -am, -va) — but not a long option
            if a.startswith("-") and not a.startswith("--") and "a" in a[1:]:
                return ("commit", a)
        return None

    if sub == "push":
        # A push publishes a WHOLE BRANCH, not the commit you just made, and it cannot
        # be undone. Measured 2026-09-07: 20 commits went out in one app repo, 18 of them
        # older than the session that pushed. Documented afterwards as the single most
        # serious omission in the guards — the one failure with no recovery.
        #
        # Everything else here is about staging too much; this is about publishing what
        # you never looked at. Same shape, so it lives in the same guard.
        return ("push", " ".join(args) or "push")

    if sub == "add":
        pathspecs = []
        skip = False
        for a in args:
            if skip:
                skip = False
                continue
            if a in ("--chmod", "--pathspec-from-file"):
                skip = True
                continue
            if a in ("-A", "--all", "--no-ignore-removal", "-u", "--update"):
                return ("add", a)
            if a.startswith("-"):
                continue
            pathspecs.append(a)
        for p in pathspecs:
            if p in (".", "*", ":/", "./", "-A"):
                return ("add", p)
            if target and root:
                q = resolve(p, target)
                if q == root or root.startswith(q + os.sep):
                    return ("add", p)
        return None

    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return                                    # not our business; allow

    cmd = (payload.get("tool_input") or {}).get("command")
    if not cmd or "git" not in cmd:
        return
    # No cwd in the payload means we do not know where the session stands, and
    # "foreign" is defined against it. Falling back to os.getcwd() would decide on a
    # guess, and a guard that denies on a guess is the failure the project rule names
    # first. Deliberately stricter than the sibling guard, which does fall back.
    raw_cwd = payload.get("cwd")
    if not raw_cwd:
        return
    cwd = real(raw_cwd)
    roots = registry_roots()
    if not roots:
        return

    here = root_of(cwd, roots)                    # the root we are standing in, if any

    seen = []                                     # foreign writes that were ALLOWED
    # Where each command runs — including inside a subshell, and including a `cd` whose
    # effect ENDS with its group. Reading `(cd ../other && git status); git commit -am x`
    # as though the cd leaked would refuse a commit in the repo we are standing in.
    for tokens, here_dir, env in shell_commands(cmd, cwd):
        if os.path.basename(tokens[0]) != "git":
            continue

        target = git_target(tokens, here_dir, env)
        there = root_of(target, roots)
        if not there:
            continue                              # not a registry repo; not ours
        if here and here[1] == there[1]:
            continue                              # we ARE standing in it; allowed

        hit = sweeping(tokens, target, there[1])
        if not hit:
            sub = subcommand(tokens)
            if sub in WRITES:
                seen.append((there, sub))
            continue
        sub, flag = hit
        name, root = there

        if sub == "push":
            reason = (
                f"`git push` targets the '{name}' repo ({root}), which this session is "
                f"not standing in — this session is in {cwd}.\n"
                f"A push publishes a WHOLE BRANCH, not the commit you just made, and it "
                f"cannot be undone. On 2026-09-07 this sent 20 commits in one app repo, 18 of "
                f"them written before that session existed.\n"
                f"Look first, from here:\n"
                f"  git -C {root} log @{{u}}..HEAD --oneline    # everything this would publish\n"
                f"  python3 $GROVE/tools/close.py                    # every place, and its push radius\n"
                f"Then either move the session to {root} and push there, or ask the owner "
                f"to push. Do not push a branch you have no picture of."
            )
        else:
            reason = (
                f"`git {sub} {flag}` targets the '{name}' repo ({root}), which this "
                f"session is not standing in — this session is in {cwd}.\n"
                f"Whatever is already dirty there is invisible from here, so this "
                f"stages work you never saw into your commit. On 2026-09-08 app-hub "
                f"held 17 uncommitted files of the owner's own.\n"
                f"Stage exactly what you wrote instead:\n"
                f"  git -C {root} add <the paths you wrote>\n"
                f"  git -C {root} status --short      # nothing else staged?\n"
                f"  git -C {root} commit -m \"…\"       # in that repo's terms\n"
                f"Or let `python3 $GROVE/tools/close.py --commit -m \"…\"` do it for every "
                f"place at once — it stages only the paths this session actually wrote."
            )
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }))
        return                                    # one decision per call

    # Nothing to refuse — but a foreign write still happens blind. Hand over the
    # picture the session would have had standing there. It informs; it decides nothing.
    if not seen:
        return
    (name, root), sub = seen[0]
    shown = picture(root)
    if not shown:
        return                                    # git could not answer; say nothing
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": (
            f"[foreign] `git {sub}` reaches into '{name}' ({root}), and this session stands in {cwd}. "
            f"What is dirty there is invisible from here — this is it:\n"
            + "\n".join(shown)
            + "\nStage only what you wrote. `python3 $GROVE/tools/close.py` shows every place at once."
        )}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass                                      # fail open, always
