#!/usr/bin/env python3
"""Stop guard: this place has a local skill that its declaration does not mention.

The gap this closes is one of timing, not of logic. `honor_ownership` reads
`.claude/owns.json` and blocks nothing that is not written there — deliberate, and it
has one silent failure: **a new local skill adds no line, so the paths it authors stay
open, and the hole looks exactly like a place that chose to be open.** The guard itself
cannot report it. It must fail open, so "not declared" and "forgot to declare" are the
same thing to it, and any rule added there would cost on every tool call.

`tools/check_ownership.py` already asks this across every registered place — but only
inside `deploy.py`, which is a REPO_GUARDS action. The hole is created somewhere else: you
add a skill to a project, and nothing in that project ever runs RepoGuards' deploy. The
detector could lag for weeks.

So this asks the same question at the other end: **about the place the session is
standing in, at the end of the turn that created the hole.** That is where the person
is, where the fix belongs, and the one moment they still remember why.

Deliberately scoped to the current place, not all thirteen. A gap in a repo you have not
visited is not yours to be interrupted about — `deploy.py` sweeps those.

Noise is what kills a hook like this, so it speaks only when the set of gaps CHANGES.
An unfixed gap stays quiet after it has been said once; a new one speaks. Same pattern
as warn_stale_plugin_cache, for the same reason.

Fails silent: any error reports nothing. A hook that crashes at the end of every turn is
worse than no hook.
"""
import json, os, sys, time
from guards_repo import registry_path, registry_roots, ownership_gaps

STATE_DIR = os.environ.get("REPO_GUARDS_OWNS_STATE") or os.path.expanduser(
    "~/.claude/.repo-guards/owns-state")


def real(p):
    return os.path.realpath(os.path.expanduser(p))


def standing_in(cwd):
    """The registered place containing `cwd` — the deepest one, so a nested repo wins."""
    try:
        with open(registry_path(), encoding="utf-8") as f:
            reg = json.load(f)
    except Exception:
        return None, None
    best = (None, None)
    for name, root, _entry in registry_roots(reg):
        if cwd == root or cwd.startswith(root + os.sep):
            if best[1] is None or len(root) > len(best[1]):
                best = (name, root)
    return best


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    cwd = payload.get("cwd")
    if not cwd:
        return                                         # cannot tell where we stand
    name, root = standing_in(real(cwd))
    if not root:
        return                                         # not a registered place

    gaps = ownership_gaps(root)
    sid = payload.get("session_id") or "unknown"
    sig = sorted(f"{k}:{w}" for k, w, _ in gaps)

    os.makedirs(STATE_DIR, exist_ok=True)
    statef = os.path.join(STATE_DIR, f"{sid}.json")
    try:
        prev = json.load(open(statef))
    except Exception:
        prev = None
    try:
        json.dump(sig, open(statef, "w"))
        cutoff = time.time() - 7 * 86400               # one file per session, else forever
        for f in os.listdir(STATE_DIR):
            fp = os.path.join(STATE_DIR, f)
            if f.endswith(".json") and os.path.getmtime(fp) < cutoff:
                os.remove(fp)
    except Exception:
        pass

    if not gaps or sig == prev:
        return                                         # nothing new to say

    lines = [f"  · {kind}: {what}\n    {why}" for kind, what, why in gaps]
    print(json.dumps({"systemMessage":
                      f"What {name} declares and what it holds do not agree:\n"
                      + "\n".join(lines)
                      + f"\n\nThe declaration is {root}/.claude/owns.json, and the guard reads "
                      "only that — what is not written there can be written from anywhere, "
                      "silently."}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass                                           # fail silent, always
