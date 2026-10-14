#!/usr/bin/env python3
"""Stop guard: say which registry repo this session dirtied and left uncommitted.

The rule this serves:

    Commit in the repo the change belongs to, before the turn ends.

The reason that rule is broken is stated in the rule itself: a change left in a repo
you are not standing in "is not visible in any `git status` you look at, and so it is
forgotten". Your own cwd you see; every other repo is a blind spot. This closes it.

It is also the IGNITION for $REPO_GUARDS/tools/close.py: nothing makes a session run that
command, and an engine without ignition is no different from no engine. This is the
one place a session cannot route around — it does not choose not to end a turn.

It DETECTS, it does not prevent — see docs/cross-repo-session/1-need-problem-solution.md. Prevention of the
adjacent failure (a commit that sweeps a foreign repo's work) is the sibling
scope_foreign_commits.py.

Noise is the thing that kills a hook like this. A repo can be dirty for reasons that
have nothing to do with this session — on 2026-09-08 app-hub carried 17 files of the
owner's own work in progress. Reporting those every single turn would train the reader
to skip the message, and then it fails at the one job it has. So it keeps a per-session
baseline and reports only what THIS session added, naming pre-existing work exactly
once, on the first turn, so it is known and then never repeated.

Fails silent: any error reports nothing. A hook that crashes at the end of every turn
is worse than no hook.
"""
import json, os, subprocess, sys, time
# The guard ships inside RepoGuards and runs from the plugin cache, where
# nothing sits two directories above it. guards_repo finds the live repo.
from guards_repo import registry_path, registry_roots

HERE = os.path.dirname(os.path.abspath(__file__))
# Both are overridable so the pipeline can exercise this against throwaway repos.
# Testing it against the real registry would mean dirtying a real project to see
# it fire, which is the one thing this hook exists to complain about.
REGISTRY = registry_path()
STATE_DIR = os.environ.get("REPO_GUARDS_STOP_STATE") or os.path.expanduser("~/.claude/.repo-guards/stop-state")


def real(p):
    return os.path.realpath(os.path.expanduser(p))


def roots():
    """Every registry root that exists on disk — projects AND apps.

    It read `projects` only, which left all six app repos unwatched: measured
    2026-09-09 this returned the four `projects` entries only, and
    nothing else. Work left uncommitted in any APP repo by a session standing
    elsewhere was therefore never reported — the blind spot this hook exists to close,
    in the repos most likely to have it.

    Whether a root is a git repo is no longer asked here. It used to test for a `.git`
    DIRECTORY, which is false for a worktree or a submodule (there `.git` is a file),
    and false for a root registered as a subdirectory of its repo — `<repo>/web`
    is registered while the repo top-level is `<repo>`, so it was skipped
    despite the registry saying the Stop guard is the reason it is listed. git answers
    that question correctly in dirty(), in a call this already makes.
    """
    try:
        reg = json.load(open(REGISTRY))
    except Exception:
        return []
    found = [(name, r) for name, r, _ in registry_roots(reg) if os.path.isdir(r)]

    # ONE LINE PER GIT REPOSITORY. Since 2026-09-09 the registry deliberately holds a
    # second entry for a directory INSIDE an already-registered repo — an app and
    # its Capacitor/ subtree, a project and its apps/mobile — because settings resolve
    # against the cwd and release work stands in the subdirectory. That is right for
    # loading tracks and wrong here: git has one answer for both, so a single changed
    # file was reported twice, the second time under a name the session was told it was
    # "not standing in". Noise is what kills this hook, and duplicate lines that
    # contradict each other are the worst kind.
    #
    # The representative is the registered root that IS the git top-level when there is
    # one, else the shortest — which keeps a root registered at a subdirectory
    # whose top-level is not registered at all, reporting its own subtree.
    groups = {}
    for name, r in found:
        top = git_top(r)
        if top is None:
            continue
        groups.setdefault(top, []).append((name, r))
    out = []
    for top, members in groups.items():
        exact = [m for m in members if m[1] == top]
        out.append(min(exact or members, key=lambda m: len(m[1])))
    return sorted(out)


def git_top(root):
    """The git top-level containing `root`, or None when it is not in a repository."""
    try:
        p = subprocess.run(["git", "-C", root, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=5)
        return real(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else None
    except Exception:
        return None


def dirty(root):
    """Paths git reports as not committed under `root`, or None when it is not in a repo.

    Scoped with `-- .` so a root that is a subdirectory of its repo reports its own
    subtree and not the whole repo. None rather than an empty set, so "clean" and "not
    a repo at all" stay distinguishable — one registered directory was not a repository, and a
    root that cannot be read must be dropped rather than recorded as clean.
    """
    try:
        p = subprocess.run(["git", "-C", root, "status", "--porcelain", "--", "."],
                           capture_output=True, text=True, timeout=5)
        if p.returncode != 0:
            return None
        return {ln[3:].strip() for ln in p.stdout.splitlines() if len(ln) > 3}
    except Exception:
        return None


def unpushed(root):
    """Count of commits ahead of upstream, or None when there is no upstream."""
    try:
        p = subprocess.run(["git", "-C", root, "rev-list", "--count", "@{u}..HEAD"],
                           capture_output=True, text=True, timeout=5)
        return int(p.stdout.strip()) if p.returncode == 0 else None
    except Exception:
        return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if payload.get("stop_hook_active"):
        return                                        # already handled; do not re-fire

    sid = payload.get("session_id") or "unknown"
    cwd = real(payload.get("cwd") or "") if payload.get("cwd") else None

    rs = roots()
    if not rs:
        return

    now = {}
    for name, root in rs:
        d = dirty(root)
        if d is not None:
            now[name] = d
    rs = [(n, r) for n, r in rs if n in now]
    if not rs:
        return

    os.makedirs(STATE_DIR, exist_ok=True)
    statef = os.path.join(STATE_DIR, f"{sid}.json")
    first = not os.path.exists(statef)
    try:
        base = json.load(open(statef)) if not first else {}
    except Exception:
        base, first = {}, True

    # Registered at user scope, so this runs in every project on the machine — 69 of
    # them against a registry of 11. That is right for NEW changes: a session anywhere
    # may dirty a registry repo, and catching that is the whole point. It is wrong for
    # the pre-existing report, which is context about RepoGuards' own repos and is
    # pure noise in a project that has nothing to do with them. So that half speaks
    # only when the session actually stands inside the registry's world.
    inside = bool(cwd) and any(cwd == r or cwd.startswith(r + os.sep) for _, r in rs)

    lines = []
    for name, root in rs:
        seen = set(base.get(name, []))
        added = sorted(now[name] - seen)
        where = "  (this session's own cwd)" if cwd and (cwd == root or cwd.startswith(root + os.sep)) else ""
        if first:
            if now[name] and inside:
                lines.append(f"· {name}: {len(now[name])} file(s) were ALREADY uncommitted "
                             f"before this session — not yours, not reported again.{where}")
        elif added:
            ahead = unpushed(root)
            tail = f"; {ahead} unpushed" if ahead else ""
            # Two names, not the whole list: enough to recognise what this is about,
            # while the full picture belongs to close.py rather than to a reminder.
            shown = ", ".join(added[:2]) + (f" +{len(added) - 2}" if len(added) > 2 else "")
            lines.append(f"· {name} ({root}): {len(added)} change(s) from THIS session "
                         f"— {shown}{tail}.{where}")
    try:
        json.dump({n: sorted(v) for n, v in now.items()}, open(statef, "w"))
        # one state file per session would otherwise accumulate forever
        cutoff = time.time() - 7 * 86400
        for f in os.listdir(STATE_DIR):
            fp = os.path.join(STATE_DIR, f)
            if f.endswith(".json") and os.path.getmtime(fp) < cutoff:
                os.remove(fp)
    except Exception:
        pass

    if not lines:
        return

    head = ("Work left open outside this session's own `git status`:\n")
    tail = ("\n\n  python3 $REPO_GUARDS/tools/close.py      ← what changed where, and what is still open\n\n"
            "That is the report; this is only the reminder. It stages just the paths this "
            "session wrote, commits per place, and prints the push radius rather than pushing.")
    print(json.dumps({"systemMessage": head + "\n".join(lines) + tail}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass                                          # fail silent, always
