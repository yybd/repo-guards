#!/usr/bin/env python3
"""PreToolUse recorder: which repos has this session touched, and where.

Layer 1 of docs/cross-repo-session/1-need-problem-solution. It answers the question the registry cannot: not "which repos
were declared important" but "which repos has THIS session actually touched". The
registry lists 11; this machine has hundreds.

Records only. It never blocks, never prints, never has an opinion. Everything that
acts on this data is a separate hook, so this one can run on every single tool call
without being able to break anything.

Every tool call carries paths. Each path resolves to the repo containing it — the
whole mechanism is `git rev-parse --show-toplevel`, measured at 8ms and cached per
directory, so in practice almost every call is a dictionary lookup. On first sight of
a repo it also records that repo's dirty set as a BASELINE, which is what later lets
"what this session changed" be separated from "what the owner already had".

Over-inclusive on purpose — in `paths`. A path merely mentioned counts the same as a
path written, because that is what peripheral vision does for a person: they see the
other window whether or not they typed in it. A repo in the set costs one `git status`
later; a repo missing from it is the failure this exists to prevent.

`written` is the opposite, and the separation is the point. It holds only paths that a
WRITING tool named — Write, Edit, MultiEdit, NotebookEdit — and it is the only field in
this file that may be read as authorship. Measured 2026-09-10: a session that merely
grepped for `Info.plist` had five of another session's files reported back to it as
"mine", because `paths` was being read as evidence of writing. It is not, and no amount
of filtering makes it so. What a `Bash` line writes is not recorded here at all: a shell
line can write anything, so under-claiming there is the only safe direction.

Fails silent: any error records nothing and allows the call. A recorder that breaks a
tool call is worse than no recorder.
"""
import json, os, re, shlex, subprocess, sys, time

STATE_DIR = os.environ.get("GROVE_TOUCHED_STATE") or os.path.expanduser(
    "~/.claude/.grove/touched")

PATH_KEYS = ("file_path", "path", "notebook_path")
WRITE_KEYS = ("file_path", "notebook_path")     # `path` is a read/glob key, not a write
WRITERS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
MAX_PATHS = 24                      # a Bash line can mention many; cap the work


def candidate_paths(tool, ti):
    """Paths this tool call refers to. Over-inclusive by design."""
    out = []
    for k in PATH_KEYS:
        v = ti.get(k)
        if isinstance(v, str) and v:
            out.append(v)
    # MultiEdit and friends can carry a list of edits, each with its own path
    for v in ti.values():
        if isinstance(v, list):
            for item in v[:MAX_PATHS]:
                if isinstance(item, dict):
                    for k in PATH_KEYS:
                        if isinstance(item.get(k), str):
                            out.append(item[k])
    if tool == "Bash":
        cmd = ti.get("command")
        if isinstance(cmd, str):
            try:
                tokens = shlex.split(cmd)
            except Exception:
                tokens = re.split(r"\s+", cmd)
            for t in tokens:
                t = t.strip("'\"`,;|&()")
                # anything shaped like a path; existence is checked by the caller
                if t.startswith(("/", "~", "./", "../")) or ("/" in t and not t.startswith("-")):
                    out.append(t)
    return out[:MAX_PATHS]


def written_paths(tool, ti):
    """Paths this call is about to WRITE. Deliberately narrow — see the module note.

    An intended write that never lands cannot survive here: the consumer intersects
    this with what is actually dirty, so a refused or failed call drops out on its own.
    """
    if tool not in WRITERS:
        return []
    out = []
    for k in WRITE_KEYS:
        v = ti.get(k)
        if isinstance(v, str) and v:
            out.append(v)
    for v in ti.values():                       # MultiEdit-shaped: a list of edits
        if isinstance(v, list):
            for item in v[:MAX_PATHS]:
                if isinstance(item, dict):
                    for k in WRITE_KEYS:
                        if isinstance(item.get(k), str):
                            out.append(item[k])
    return out[:MAX_PATHS]


def head_of(root):
    """The commit this place stood on when we arrived. Lets 'what is ahead of the
    upstream' be split into what predates the session and what does not — without
    guessing from timestamps."""
    try:
        r = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=3)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def repo_of(path, cache):
    """The git repo containing `path`, or None. Cached per directory."""
    p = os.path.realpath(os.path.expanduser(path))
    d = p if os.path.isdir(p) else os.path.dirname(p)
    if not d or not os.path.isdir(d):
        return None
    if d in cache:
        return cache[d] or None
    try:
        r = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=3)
        top = os.path.realpath(r.stdout.strip()) if r.returncode == 0 else ""
    except Exception:
        top = ""
    cache[d] = top
    return top or None


def dirty(root):
    try:
        r = subprocess.run(["git", "-C", root, "status", "--porcelain"],
                           capture_output=True, text=True, timeout=5)
        return sorted({ln[3:].strip() for ln in r.stdout.splitlines() if len(ln) > 3}) \
            if r.returncode == 0 else []
    except Exception:
        return []


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    sid = payload.get("session_id")
    if not sid or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", str(sid)):
        return                                      # no session, nowhere to record
    ti = payload.get("tool_input") or {}
    if not isinstance(ti, dict):
        return
    tool = payload.get("tool_name") or ""
    paths = candidate_paths(tool, ti)
    wrote = set()
    for w in written_paths(tool, ti):
        wrote.add(os.path.realpath(os.path.expanduser(w)))
    cwd = payload.get("cwd")
    if cwd:
        paths.append(cwd)                           # where the session stands counts too
    if not paths:
        return

    os.makedirs(STATE_DIR, exist_ok=True)
    f = os.path.join(STATE_DIR, f"{sid}.json")
    try:
        state = json.load(open(f)) if os.path.exists(f) else {}
    except Exception:
        state = {}
    state.setdefault("session", sid)
    state.setdefault("started", time.strftime("%Y-%m-%dT%H:%M:%S"))
    repos = state.setdefault("repos", {})
    cache = state.setdefault("dir_cache", {})

    changed = False
    for p in paths:
        root = repo_of(p, cache)
        if not root:
            continue
        entry = repos.get(root)
        if entry is None:
            entry = repos[root] = {"first_seen": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                   "head": head_of(root),
                                   "baseline": dirty(root), "paths": [], "written": []}
            changed = True
        entry.setdefault("written", [])         # journals written before this field
        rp = os.path.realpath(os.path.expanduser(p))
        rel = os.path.relpath(rp, root) if rp.startswith(root + os.sep) else "."
        if rel not in entry["paths"]:
            entry["paths"].append(rel)
            entry["paths"] = entry["paths"][:200]
            changed = True
        if rp in wrote and rel != "." and rel not in entry["written"]:
            entry["written"].append(rel)
            entry["written"] = entry["written"][:200]
            changed = True

    if not changed:
        return
    try:                                            # atomic-ish; a lost update is fine
        tmp = f + ".tmp"
        json.dump(state, open(tmp, "w"))
        os.replace(tmp, f)
        # 30 days, not 7: this is a measurement log read weeks later, and a 7-day
        # window would start deleting the earliest sessions exactly when someone
        # first looks at it. The Stop hook's own state is different — it is only
        # useful during the session that wrote it.
        cutoff = time.time() - 30 * 86400
        for name in os.listdir(STATE_DIR):
            fp = os.path.join(STATE_DIR, name)
            if name.endswith(".json") and os.path.getmtime(fp) < cutoff:
                os.remove(fp)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass                                        # fail silent, always
