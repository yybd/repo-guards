#!/usr/bin/env python3
"""Check the guards: their pipelines, the copy that is actually running, and leftovers.

The guards used to be registered by hand into ~/.claude/settings.json, and install.py
was the gate: it refused to register a hook whose pipeline failed, because RepoGuards
rule is that a guard is run across all its branches before it takes effect, and
installing WAS the moment it took effect.

They ship with RepoGuards now, so there is no install step left to gate — the
moment they take effect is `claude plugin install/update`, which this repo does not
own. The gate has to move to where the change is made instead of where it lands, and
this is it. Run it before committing a guard.

    python3 tools/verify_guards.py            pipelines, running copy, leftovers
    python3 tools/verify_guards.py --clean    also remove legacy settings.json entries

It answers three questions the old install.py could not:

**Do the pipelines pass?** Same as before, just from the plugin's tree.

**Which copy is running?** A plugin is COPIED into the cache at a pinned commit, so an
edit committed here is not the code guarding the machine until the plugin is updated.
That gap did not exist while the guards ran from the repo, and it is the real cost of
shipping them with the plugin. warn_stale_plugin_cache.py reports it at the end of a
turn; this reports it on demand, next to the pipelines, where you are already looking.

**Is anything registered twice?** A machine that ran the old install.py still has six
entries in settings.json pointing into tools/hooks/. Those files are gone, so each
one is now a hook that fails on every matching tool call. --clean removes exactly
those, and touches nothing else in the file.
"""
import argparse, glob, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_GUARDS = os.path.dirname(HERE)
GUARDS_SCRIPTS = os.path.join(REPO_GUARDS, "plugins", "repo-guards", "hooks", "scripts")
# The repo under test. RepoGuards by default; another marketplace's checkout when it is asked
# to verify its own copies — the byte-for-byte comparison below is the same question for
# everyone who ships plugins, and copying it per repo is how two answers drift apart.
REPO = (os.environ.get("REPO_GUARDS_REPO") or os.environ.get("GROVE_REPO")) or REPO_GUARDS
PLUGIN = os.environ.get("REPO_GUARDS_PLUGIN") or os.path.join(REPO, "plugins", "repo-guards")
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
TESTS = os.path.join(SCRIPTS, "tests")
SETTINGS = os.environ.get("REPO_GUARDS_SETTINGS") or os.path.expanduser("~/.claude/settings.json")
INSTALLED = os.environ.get("REPO_GUARDS_INSTALLED") or os.path.expanduser(
    "~/.claude/plugins/installed_plugins.json")
PLUGIN_ID = os.environ.get("REPO_GUARDS_PLUGIN_ID") or "repo-guards@repo-guards"
LEGACY_MARK = "tools/hooks/"


def pretty(p):
    home = os.path.expanduser("~")
    return "~" + p[len(home):] if p.startswith(home + os.sep) else p


def guards():
    return sorted(f for f in os.listdir(SCRIPTS)
                  if f.endswith(".py") and f not in ("guards_repo.py", "grove_repo.py"))   # the shim, until 0.3.0


def declared():
    """The guard files hooks.json actually registers — the list that matters."""
    try:
        d = json.load(open(os.path.join(PLUGIN, "hooks", "hooks.json"), encoding="utf-8"))
    except Exception as e:
        return None, str(e)
    out = []
    for entries in (d.get("hooks") or {}).values():
        for entry in entries:
            for h in entry.get("hooks", []):
                out.append(os.path.basename((h.get("command") or "").split()[-1]))
    return sorted(out), None


def run_pipeline(name, path=None):
    test = path or os.path.join(TESTS, f"test_{name}")
    if not os.path.exists(test):
        return True, "no pipeline"
    p = subprocess.run([sys.executable, test], capture_output=True, text=True,
                       timeout=300, cwd=TESTS)
    if p.returncode == 0:
        n = sum(1 for ln in p.stdout.splitlines() if ln.startswith("✓"))
        return True, f"{n} checks passed"
    tail = (p.stdout + p.stderr).strip().splitlines()[-3:]
    return False, "failed: " + " / ".join(t.strip() for t in tail)


def cache_findings():
    """What the Stop guard would report about the installed copies, on demand.

    Imported rather than re-implemented, and the sha check this replaced was wrong in
    both directions — warn_stale_plugin_cache.py measured it on 2026-09-09. `claude
    plugin update` copies the WORKING TREE and labels it with HEAD, so an uncommitted
    edit lands in the cache under a sha that does not contain it: the shas agree while
    the bytes differ. And `update` is a no-op once the sha matches, so a cache holding
    content from no commit cannot be repaired by `update` at all — it needs a
    reinstall, which only a content comparison can know to say.
    """
    sys.path.insert(0, GUARDS_SCRIPTS)
    try:
        import warn_stale_plugin_cache as stale
        found = stale.findings()
        # The rules symlink is optional — reported, never counted. See deploy.py, which
        # separates the same two kinds for the same reason.
        return ([line for k, line in found if not k.startswith("rules:")],
                [line for k, line in found if k.startswith("rules:")]), None
    except Exception as e:
        return None, str(e)[:160]


def legacy_entries(data):
    """settings.json hooks left over from the hand-registration era."""
    found = []
    for event, entries in (data.get("hooks") or {}).items():
        for entry in entries:
            for h in entry.get("hooks", []):
                if LEGACY_MARK in (h.get("command") or ""):
                    found.append((event, os.path.basename(h["command"])))
    return found


def strip_legacy(data):
    hooks = data.get("hooks") or {}
    for event in list(hooks):
        keep = []
        for entry in hooks[event]:
            inner = [h for h in entry.get("hooks", [])
                     if LEGACY_MARK not in (h.get("command") or "")]
            if inner:
                keep.append({**entry, "hooks": inner})
        if keep:
            hooks[event] = keep
        else:
            del hooks[event]
    return data


def copies_only():
    """The byte-for-byte check alone, for a repo that ships plugins and no guards."""
    got, err = cache_findings()
    print("\nThe copies that actually run:")
    if err:
        print(f"  ✗ cannot compare against the cache: {err}")
        print("\n1 problems.")
        return 1
    lines, notes = got
    if not lines:
        print("  ✓ every installed plugin is byte-for-byte what the repo holds")
    for line in lines:
        print("  ✗ " + line.replace("\n", "\n  "))
    for line in notes:
        print("  · optional: " + line.lstrip("· ").replace("\n", "\n  "))
    print("\n" + ("All good." if not lines else f"{len(lines)} problems."))
    return 1 if lines else 0


def main():
    ap = argparse.ArgumentParser(description="Verify RepoGuards' guards.")
    ap.add_argument("--clean", action="store_true",
                    help="remove legacy tools/hooks/ entries from settings.json")
    a = ap.parse_args()
    bad = 0

    print(f"repo: {pretty(REPO)}")

    if not os.path.isdir(SCRIPTS):
        # A repo that ships plugins but no guards — another marketplace asking the one
        # question that is not repo-guards-specific: do the installed copies still match?
        return copies_only()

    names, err = declared()
    if err:
        print(f"  ✗ hooks.json could not be read: {err}")
        return 2
    on_disk = set(guards())
    missing = [n for n in names if n not in on_disk]
    unwired = sorted(on_disk - set(names))
    print(f"\nGuards in hooks.json: {len(names)}")
    for n in missing:
        print(f"  ✗ {n} — registered in hooks.json and not on disk")
        bad += 1
    for n in unwired:
        print(f"  ✗ {n} — on disk and not registered in hooks.json")
        bad += 1
    if not missing and not unwired:
        print("  ✓ everything registered exists, and everything that exists is registered")

    print("\nPipelines:")
    ran = set()
    for n in sorted(set(names)):
        ok, note = run_pipeline(n)
        ran.add(os.path.splitext(f"test_{n}")[0])   # names carry .py; test files do not
        print(f"  {'✓' if ok else '✗'} {n} — {note}")
        bad += 0 if ok else 1
    # And every other pipeline sitting beside them. Not all of them are named after a
    # guard: what the two guards stand on — reading a shell line — is one function in
    # guards_repo, and a test named after it would have been run by nothing here. That is
    # the lesson deploy.py already learned about its own tests directory, arriving in the
    # second one: a suite that is only partly run is a suite that rots.
    for path in sorted(glob.glob(os.path.join(TESTS, "test_*.py"))):
        name = os.path.basename(path)[:-3]
        if name in ran:
            continue
        ok, note = run_pipeline(None, path)
        print(f"  {'✓' if ok else '✗'} {name[5:]} — {note}")
        bad += 0 if ok else 1

    print("\nThe copies that actually run:")
    got, err = cache_findings()
    if err:
        print(f"  ✗ cannot compare against the cache: {err}")
        bad += 1
    else:
        lines, notes = got
        if not lines:
            print("  ✓ every installed plugin is byte-for-byte what the repo holds")
        for line in lines:
            print("  ✗ " + line.replace("\n", "\n  "))
        for line in notes:
            print("  · optional: " + line.lstrip("· ").replace("\n", "\n  "))
        bad += len(lines)

    try:
        data = json.load(open(SETTINGS, encoding="utf-8")) if os.path.exists(SETTINGS) else {}
    except Exception as e:
        print(f"\n  ✗ {pretty(SETTINGS)} is not readable JSON ({e}).")
        return 2
    old = legacy_entries(data)
    print("\nStale registrations in settings.json:")
    if not old:
        print("  ✓ none")
    elif a.clean:
        backup = f"{SETTINGS}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(SETTINGS, backup)
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(strip_legacy(data), f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  backup: {pretty(backup)}")
        for event, name in old:
            print(f"  – removed {name} ({event})")
        print("  Other tools' hooks were left alone.")
    else:
        for event, name in old:
            print(f"  ✗ {name} ({event}) — points at tools/hooks/, which no longer exists")
        print("  To remove:  python3 tools/verify_guards.py --clean")
        bad += len(old)

    print("\n" + ("All good." if not bad else f"{bad} problems."))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
