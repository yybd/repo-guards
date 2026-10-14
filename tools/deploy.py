#!/usr/bin/env python3
"""Put what this repo holds onto the machine, in the order that actually works.

Editing RepoGuards changes nothing by itself. A skill, a guard and a hooks.json all
live in a plugin, and a plugin is a COPY in ~/.claude/plugins/cache — so between "I
committed it" and "it is running" there are two steps that nothing performs for you,
and one of them is opening a new session. That gap has already produced the exact
failure it looks like it would: code committed, reported as fixed, and the machine
still running the old copy.

    python3 tools/deploy.py           sync, refresh the copies, verify
    python3 tools/deploy.py --check   report only, change nothing

Three steps, in this order, because each one's output is the next one's input:

1. **The registry into the settings files.** Which tracks a repo loads is declared in
   tools/registry.json and written into each repo's .claude/settings.json. Do this
   first: refreshing a copy before the settings that decide whether it loads at all
   just means doing it twice.

2. **The repo into the installed copies.** Per plugin, and NOT always the same command
   — `claude plugin update` is a no-op once the recorded version equals HEAD, so a
   copy holding content from no commit needs uninstall + install instead. That
   distinction is measured, not guessed, and it already lives in
   warn_stale_plugin_cache.py; this reuses its findings rather than re-deriving them.

3. **Verify.** The pipelines, and a byte-for-byte comparison of every installed copy
   against this repo.

**Commit first.** `update` copies the working tree but labels it with HEAD, so
deploying uncommitted work puts bytes in the cache under a commit that does not
contain them — and because `update` then sees a matching version, it can never repair
that copy again. The refusal below is not tidiness; it is avoiding a state whose only
exit is a reinstall.

**And it still needs a new session.** Nothing here changes what is already loaded.
"""
import argparse, glob, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCRIPTS = os.path.join(REPO, "plugins", "repo-guards", "hooks", "scripts")
MARKETPLACE = "repo-guards"
INSTALLED = os.path.expanduser("~/.claude/plugins/installed_plugins.json")
CACHE = os.path.expanduser("~/.claude/plugins/cache")
sys.path.insert(0, SCRIPTS)


def sh(cmd, timeout=300):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=REPO)
    return p.returncode, (p.stdout + p.stderr).strip()


def dirty_plugin_files():
    """Uncommitted changes under plugins/ — the ones that would deploy mislabelled."""
    rc, out = sh(["git", "-C", REPO, "status", "--porcelain", "--", "plugins"])
    if rc != 0:
        return []
    # Split on the status code rather than slicing three characters off the front:
    # sh() strips the combined output, which eats the leading space of ` M path` and
    # made the first filename come out a character short. A status code never
    # contains a space, so this holds whether or not the line was stripped.
    out_lines = []
    for ln in out.splitlines():
        parts = ln.split(maxsplit=1)
        if len(parts) == 2:
            out_lines.append(parts[1])
    return out_lines


def findings():
    """(lines, error) — what is stale in the installed copies, and the fix for each."""
    try:
        import warn_stale_plugin_cache as stale
        return stale.findings(), None
    except Exception as e:
        return None, str(e)[:200]


def fix_commands(items):
    """The commands the findings prescribe, parsed back out of their own advice.

    The advice text is the single source of which repair each case needs, so reading
    it back beats deciding again here and risking the two disagreeing.
    """
    cmds = []
    for _, line in items:
        for raw in line.splitlines():
            raw = raw.strip()
            if raw.startswith("claude plugin "):
                for part in raw.split("&&"):
                    part = part.strip()
                    if part.startswith("claude plugin "):
                        cmds.append(part.split())
    return cmds


def prune_cache(check):
    """Delete cached plugin versions nothing points at any more.

    Every deploy writes a new <sha> directory beside the old ones and nothing ever
    removes them: seven tracks had accumulated 41 copies, 34 of them dead, before
    anyone noticed. Only the version named in installed_plugins.json is live, and
    only RepoGuards' tree is touched — another marketplace's cache is not ours.
    """
    if not os.path.exists(INSTALLED):
        # A machine that has never installed a plugin has no registry and no cache, and
        # there is nothing to prune. Saying "cleaning old versions failed: No such file"
        # there is a warning about the absence of a problem — measured on a clone in a
        # temporary directory with an empty HOME, which is the state of every new user.
        return (0, 0), None
    try:
        data = json.load(open(INSTALLED, encoding="utf-8"))["plugins"]
    except Exception as e:
        return None, str(e)[:120]
    live = {k.split("@")[0]: os.path.basename(v[0]["installPath"])
            for k, v in data.items() if k.endswith("@" + MARKETPLACE) and v}
    base = os.path.join(CACHE, MARKETPLACE)
    freed = n = 0
    for track in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        tp = os.path.join(base, track)
        if not os.path.isdir(tp):
            continue
        for ver in sorted(os.listdir(tp)):
            vp = os.path.join(tp, ver)
            if not os.path.isdir(vp) or ver == live.get(track):
                continue
            size = sum(os.path.getsize(os.path.join(dp, f))
                       for dp, _, fs in os.walk(vp) for f in fs
                       if os.path.exists(os.path.join(dp, f)))
            n += 1
            freed += size
            if not check:
                shutil.rmtree(vp, ignore_errors=True)
    return (n, freed), None


def main():
    ap = argparse.ArgumentParser(description="Deploy RepoGuards onto this machine.")
    ap.add_argument("--check", action="store_true", help="report only, change nothing")
    ap.add_argument("--dirty", action="store_true",
                    help="deploy uncommitted plugin changes anyway (see the module docstring)")
    a = ap.parse_args()
    problems = 0

    # A fresh clone has the example and no registry of its own. Copying it is the whole
    # of "set up RepoGuards", and doing it here means nobody has to be told to.
    reg_path = os.path.join(HERE, "registry.json")
    if not os.path.exists(reg_path):
        example = os.path.join(HERE, "registry.example.json")
        if not os.path.exists(example):
            pass                                   # no registry and no template: let it fail below
        elif a.check:
            # --check changes nothing, so it must not create the file — but "the registry
            # cannot be read" is the wrong sentence for a clone that was never set up.
            print("   No tools/registry.json yet — a fresh clone.")
            print("   Run  python3 tools/deploy.py  and it will be created from the template.\n")
            return 1
        else:
            shutil.copy(example, reg_path)
            print("   Created tools/registry.json from the template — register projects with "
                  "/repo-guards:register-project\n")

    print("── 1. the registry → the settings files ──")
    rc, out = sh([sys.executable, os.path.join(HERE, "sync_project_settings.py")]
                 + (["--check"] if a.check else []))
    # Everything except the rows that say "already synced". Printing only the last three
    # lines meant that with 11 registered repos you saw two arbitrary "=" rows, and a
    # `✗ the registry asks for a track that does not exist` line printed above them went
    # unread — which is how the swallowed exit code below stayed invisible.
    rows = [ln for ln in out.splitlines() if ln.strip()]
    shown = [ln for ln in rows if not ln.lstrip().startswith("=")] or rows[-1:]
    print("\n".join("   " + ln for ln in shown))
    # Any non-zero is a problem, in BOTH modes. The old condition added zero whenever
    # --check was on, so `deploy.py --check` printed sync's ✗ and then answered
    # "✓ everything is in place" with exit 0 — reproduced 2026-09-09 with a registry
    # naming a track that does not exist. In check mode drift IS the finding; in write
    # mode sync has already repaired drift, so a non-zero there means it could not.
    if rc != 0:
        problems += 1

    print("\n── 2. the repo → the installed copies ──")
    dirty = dirty_plugin_files()
    if dirty and not a.check and not a.dirty:
        print(f"   ✗ {len(dirty)} uncommitted changes under plugins/:")
        for f in dirty[:5]:
            print(f"       {f}")
        print("   `update` copies the WORKING TREE but tags it with HEAD, so deploying now")
        print("   puts bytes in the cache that are in no commit — and from then on `update`")
        print("   cannot fix the copy, only a reinstall can. Commit first, or --dirty if deliberate.")
        return 1
    if dirty and a.dirty:
        print(f"   ⚠ deploying with {len(dirty)} uncommitted changes — the cache will be tagged"
              f" with HEAD without them in it.")

    items, err = findings()
    # The rules symlink is the one finding that is not a fault. `rules/global-CLAUDE.md`
    # is optional — the guards, the registry and close.py work without it — so a fresh
    # clone that never linked it would otherwise be told "1 thing is not in place" about
    # a step its own README calls optional. Said once, counted never.
    notes = [it for it in (items or []) if it[0].startswith("rules:")]
    items = [it for it in (items or []) if not it[0].startswith("rules:")]
    if err:
        print(f"   ✗ cannot compare against the cache: {err}")
        problems += 1
    elif not items:
        print("   ✓ every installed copy already matches the repo. Nothing to deploy.")
    else:
        for _, line in items:
            print("   · " + line.splitlines()[0].lstrip("· "))
        cmds = fix_commands(items)
        if a.check:
            print(f"   {len(cmds)} commands needed. To run them:  python3 tools/deploy.py")
            problems += len(items)
        else:
            for cmd in cmds:
                print(f"   → {' '.join(cmd)}")
                rc, out = sh(cmd)
                if rc != 0:
                    print(f"     ✗ {out.splitlines()[-1][:120] if out else 'failed'}")
                    problems += 1

    for _, line in notes:
        for i, ln in enumerate(line.splitlines()):
            print("   " + ("· optional: " + ln.lstrip("· ") if i == 0 else ln))

    got, err = prune_cache(a.check)
    if err:
        print(f"   ⚠ cleaning old versions failed: {err}")
    elif got and got[0]:
        n, freed = got
        verb = "would remove" if a.check else "removed"
        print(f"   {verb} {n} old versions from the cache ({freed / 1024 / 1024:.1f} MB)")

    print("\n── 3. verification ──")
    # Paths this repo's own records point at. Printed whole when it fails: the list is
    # short by design — a checker that reported everything with a slash in it was tried
    # first and found 258 things, most of which were prose.
    rc_ref, out_ref = sh([sys.executable, os.path.join(HERE, "check_references.py")])
    if rc_ref != 0:
        for ln in out_ref.splitlines():
            if ln.strip() and not ln.startswith("Checked "):
                print("   " + ln.rstrip())
        problems += 1
    # And the other direction of the same rot: a local skill that nobody declared, or a
    # declaration that outlived the skill it named. The guard cannot report this — it
    # must fail open and cannot tell "open on purpose" from "forgotten".
    rc_own, out_own = sh([sys.executable, os.path.join(HERE, "check_ownership.py")])
    if rc_own != 0:
        for ln in out_own.splitlines():
            if ln.strip() and not ln.startswith("Checked "):
                print("   " + ln.rstrip())
        problems += 1
    # The scripts a skill hands to a session had no check of any kind: a typo in one
    # surfaces at the single moment it is used, not here. Static only — nothing is
    # executed, because executing these is how something ships by accident. It runs
    # below, with the other file checks.
    # Every test beside this file, not a named one. test_check_ownership had been broken
    # since the logic it calls moved — and nothing noticed, because only one test in this
    # directory was ever run. A suite that is only partly run is a suite that rots.
    for test in sorted(glob.glob(os.path.join(HERE, "tests", "test_*.py"))):
        rc_t, out_t = sh([sys.executable, test])
        if rc_t != 0:
            print(f"   ✗ {os.path.basename(test)}")
            for ln in out_t.splitlines():
                if ln.startswith(("✗", "Traceback", "  File")) or "Error" in ln:
                    print("      " + ln.rstrip()[:110])
            problems += 1
    # Two copies of the same document, edited in different sessions, with nothing that
    # compares them. The pair failures are mechanical and block; the number differences
    # are printed and never do, because only a person can read one.
    rc_bi, out_bi = sh([sys.executable, os.path.join(HERE, "check_bilingual.py")])
    if rc_bi != 0:
        for ln in out_bi.splitlines():
            if ln.strip() and not ln.startswith("Checked "):
                print("   " + ln.rstrip())
        problems += 1
    rc_scr, out_scr = sh([sys.executable, os.path.join(HERE, "check_scripts.py")])
    if rc_scr != 0:
        for ln in out_scr.splitlines():
            if ln.strip() and not ln.startswith(("Checked ", "Outside the standard library")):
                print("   " + ln.rstrip())
        problems += 1
    rc, out = sh([sys.executable, os.path.join(HERE, "verify_guards.py")])
    for ln in out.splitlines():
        if ln.startswith(("  ✗", "✗")) or "failed" in ln:
            print("   " + ln.strip())
    print("   " + (out.splitlines()[-1] if out.splitlines() else ""))
    if rc != 0:
        problems += 1

    print()
    if problems:
        print(f"✗ {problems} things are not in place. See above.")
        return 1
    if a.check:
        print("✓ everything is in place.")
        return 0
    print("✓ deployed.  **Open a new session** — skills and hooks load at session start,\n"
          "  and nothing here changed what is already loaded in this one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
