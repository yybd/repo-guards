#!/usr/bin/env python3
"""Stop guard: say when grove's global surface is not what this repo holds.

Two things here load in every session on the machine, by two different mechanisms:

    plugins/<track>/  → COPIED into ~/.claude/plugins/cache at install time
    rules/global-CLAUDE.md → SYMLINKED from ~/.claude/CLAUDE.md, read live

The symlink cannot go stale; it can only be broken. The copy is the problem. Nothing
in editing, committing, pulling or opening a session refreshes it, and nothing
compares it to this repo — so a skill can be written, committed, and load nowhere.
That is not hypothetical: on 2026-09-09 three shared-track skills had been committed
two days earlier and were reaching no session at all.

WHY CONTENT AND NOT THE SHA. The install records a gitCommitSha, so comparing it to
HEAD looks like the obvious check. It is wrong in both directions, measured
2026-09-09:

  · `claude plugin update` copies the WORKING TREE but labels it with HEAD. An
    uncommitted edit therefore lands in the cache under a SHA that does not contain
    it — the SHAs agree while the content differs.
  · `update` is a no-op when the SHA already matches, even if the content does not.
    A cache holding content that exists in no commit cannot be repaired by `update`
    at all; it needs uninstall + install. The advice has to know which case it is in.

So this compares the bytes. 139 files, 1.2 MB — cheap, and it is the actual question.

NOISE. A dirty `git status` clears itself when you commit; a stale copy does not, so
this would otherwise fire every turn until the day someone runs the command. It
latches on the finding set per session and speaks only when that set CHANGES.

Registered at user scope like every hook, so it runs at the end of every turn in
every repo — and its first act is to check cwd and leave. Elsewhere it costs one
python process that reads a payload and exits.

It DETECTS, it does not repair: a hook that silently mutated install state would be
doing a deploy nobody asked for, and would still need a restart to take effect.

Fails silent: any error reports nothing.
"""
import hashlib, json, os, subprocess, sys, time
# The guard ships inside grove and runs from the plugin cache, where
# nothing sits two directories above it. grove_repo finds the live repo.
from grove_repo import grove_root

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = grove_root()

# All overridable so the pipeline can drive throwaway trees. Pointing the tests at the
# real ~/.claude would mean breaking the machine's own plugins to watch this fire.
REPO_DIR = os.environ.get("GROVE_REPO") or REPO
INSTALLED = os.environ.get("GROVE_INSTALLED_PLUGINS") or os.path.expanduser(
    "~/.claude/plugins/installed_plugins.json")
USER_CLAUDE_MD = os.environ.get("GROVE_USER_CLAUDE_MD") or os.path.expanduser(
    "~/.claude/CLAUDE.md")
MARKETPLACE = os.environ.get("GROVE_MARKETPLACE") or "grove"
STATE_DIR = os.environ.get("GROVE_STALE_STATE") or os.path.expanduser(
    "~/.claude/.grove/stale-plugins")

# Written by the plugin runtime into the installed copy, or by macOS/python into
# either side. Neither is content, and comparing them would make every run differ.
SKIP_DIRS = {".in_use", "__pycache__", ".git", "node_modules"}
SKIP_FILES = {".DS_Store"}


def real(p):
    return os.path.realpath(os.path.expanduser(p))


def imports(path, want):
    """A user CLAUDE.md of one's own that pulls the rules in with an `@path` line.

    That is the other way to load them, and the right one for anyone with personal
    rules of their own: the rules stay shared, the additions stay private. Claude Code
    resolves a relative import against the importing file's directory.
    """
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except Exception:
        return False
    base = os.path.dirname(os.path.realpath(path))
    for ln in lines:
        ln = ln.strip()
        if ln.startswith("@") and len(ln) > 1:
            target = os.path.expanduser(ln[1:].split()[0])
            if real(os.path.join(base, target)) == want:
                return True
    return False


def tree(root):
    """{relpath: sha256} for a plugin directory, or None if it is not readable.

    None and {} must stay distinct: a missing install is a finding, an empty one is
    a different finding, and treating them alike would report the wrong fix.
    """
    if not os.path.isdir(root):
        return None
    out = {}
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn in SKIP_FILES:
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root)
                try:
                    with open(full, "rb") as fh:
                        out[rel] = hashlib.sha256(fh.read()).hexdigest()
                except Exception:
                    # Unreadable file: record it as its own state rather than
                    # skipping, so a permission change does not read as "identical".
                    out[rel] = "unreadable"
    except Exception:
        return None
    return out


def sources():
    """{plugin name: absolute source dir} from this repo's marketplace manifest.

    Read rather than assumed: the manifest is what decides which subtree becomes the
    plugin, so a rename or a moved source is followed instead of guessed.
    """
    mf = os.path.join(REPO_DIR, ".claude-plugin", "marketplace.json")
    try:
        data = json.load(open(mf))
    except Exception:
        return {}
    out = {}
    for p in data.get("plugins") or []:
        name, src = p.get("name"), p.get("source")
        if name and isinstance(src, str):
            out[name] = real(os.path.join(REPO_DIR, src))
    return out


def head():
    try:
        p = subprocess.run(["git", "-C", REPO_DIR, "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=5)
        return p.stdout.strip() if p.returncode == 0 else None
    except Exception:
        return None


def installs():
    """{plugin name: (installPath, version)}, or None when the registry is unreadable.

    None and {} must stay distinct. An unreadable registry means nothing is KNOWN, and
    reading that as "nothing is installed" would announce that every track is missing
    when they are fine — a guard that cries wolf on its own unreadable input is the
    fail-closed behaviour the project rule forbids.

    **A registry that is not there is a third thing, and it used to be read as the
    second.** A machine that has never installed a plugin has no such file, and the
    honest answer there is "nothing is installed" — not "nothing is known". Measured on
    a clone in a temporary directory with an empty HOME, which is the state of every new
    user: `deploy.py` said *every installed copy already matches the repo, nothing to
    deploy* and installed nothing, on a machine where grove was not installed at all.
    The one command a new user runs did nothing and reported success.
    """
    if not os.path.exists(INSTALLED):
        return {}
    try:
        data = json.load(open(INSTALLED))
    except Exception:
        return None
    if not isinstance(data.get("plugins"), dict):
        return None
    out = {}
    suffix = "@" + MARKETPLACE
    for key, entries in (data.get("plugins") or {}).items():
        if not key.endswith(suffix):
            continue
        name = key[: -len(suffix)]
        for e in entries or []:
            if e.get("scope", "user") == "user" and e.get("installPath"):
                out[name] = (real(e["installPath"]), e.get("version") or "")
                break
    return out


def diff_note(want, have):
    """Human count of how two trees differ. Called only when they do."""
    missing = len([k for k in want if k not in have])
    extra = len([k for k in have if k not in want])
    changed = len([k for k in want if k in have and want[k] != have[k]])
    bits = []
    if missing:
        bits.append(f"{missing} file(s) missing from the copy")
    if changed:
        bits.append(f"{changed} changed")
    if extra:
        bits.append(f"{extra} stale file(s) the repo no longer has")
    return ", ".join(bits) or "contents differ"


def findings():
    """Sorted (key, human line) pairs. Key identifies the finding for the latch."""
    out = []
    srcs = sources()
    inst = installs()
    h = head()

    # Unknown beats wrong: with no readable registry there is nothing true to say about
    # the copies, so that half stays quiet. The symlink check below is independent.
    for name in sorted(srcs if inst is not None else {}):
        src = tree(srcs[name])
        if src is None:
            continue                                   # source gone: not this hook's business
        if name not in inst:
            out.append((f"missing:{name}",
                        f"· {name}: declared in the marketplace but not installed — "
                        f"none of its skills load anywhere.\n"
                        f"    claude plugin install {name}@{MARKETPLACE}"))
            continue
        path, ver = inst[name]
        have = tree(path)
        if have is None:
            out.append((f"gone:{name}",
                        f"· {name}: installed copy is missing from disk ({path}).\n"
                        f"    claude plugin uninstall {name}@{MARKETPLACE} && "
                        f"claude plugin install {name}@{MARKETPLACE}"))
            continue
        if have == src:
            continue
        note = diff_note(src, have)
        # `update` refuses to act when the recorded version already equals HEAD, so at
        # that point it cannot repair the copy and saying "run update" would send the
        # reader in a circle. Measured 2026-09-09.
        if h and ver and h.startswith(ver):
            fix = (f"    `update` is a no-op at this version — reinstall:\n"
                   f"    claude plugin uninstall {name}@{MARKETPLACE} && "
                   f"claude plugin install {name}@{MARKETPLACE}")
        else:
            fix = f"    claude plugin update {name}@{MARKETPLACE}"
        out.append((f"stale:{name}:{note}", f"· {name}: {note}.\n{fix}"))

    # The rules travel by symlink and cannot go stale — but they can go missing, and
    # then the standing rules are simply absent with nothing announcing it.
    want = real(os.path.join(REPO_DIR, "rules", "global-CLAUDE.md"))
    if os.path.isfile(want):
        if not os.path.exists(USER_CLAUDE_MD):
            out.append(("rules:absent",
                        f"· rules/global-CLAUDE.md reaches no session — {USER_CLAUDE_MD} "
                        f"does not exist.\n    ln -s {want} {USER_CLAUDE_MD}"))
        elif real(USER_CLAUDE_MD) != want and not imports(USER_CLAUDE_MD, want):
            out.append(("rules:elsewhere",
                        f"· {USER_CLAUDE_MD} does not resolve to this repo's "
                        f"rules/global-CLAUDE.md.\n    readlink {USER_CLAUDE_MD}"))
    return sorted(out)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if payload.get("stop_hook_active"):
        return                                         # already handled; do not re-fire

    cwd = payload.get("cwd")
    if not cwd:
        return                                         # cannot tell where we stand
    cwd = real(cwd)
    repo = real(REPO_DIR)
    if not (cwd == repo or cwd.startswith(repo + os.sep)):
        return                                         # the drift is made here; speak here

    found = findings()
    sid = payload.get("session_id") or "unknown"
    os.makedirs(STATE_DIR, exist_ok=True)
    statef = os.path.join(STATE_DIR, f"{sid}.json")
    sig = [k for k, _ in found]
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

    if not found or sig == prev:
        return                                         # nothing new to say

    head_txt = ("What this repo publishes globally is not what is loading. Skills reach "
                "other repos through a COPY made at install time; editing, committing and "
                "opening a session all leave that copy untouched.\n")
    tail = "\nRestart the session afterwards — a running session is locked to the copy it started with."
    print(json.dumps({"systemMessage": head_txt + "\n".join(l for _, l in found) + tail}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass                                           # fail silent, always
