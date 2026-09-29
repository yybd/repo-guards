#!/usr/bin/env python3
"""Pipeline for the one thing close.py can be made to EXECUTE.

    python3 tools/tests/test_close_declarations.py

`close.py --op <name>` reads a skill's `places.json` and, if it names a `state` command,
runs it. The declarations are collected from every installed plugin in the cache — any
marketplace the machine has ever added — so that a cross-place operation declared by
another marketplace can still be reported. That is right, and it makes the file the one
place here where somebody else's text becomes a shell line running under your account.

So: ours run, anyone else's is printed for a person to read, and `--run-state` is the
deliberate act. This asserts exactly that, in a throwaway tree, with a command whose only
effect is a file it creates — the test then asks whether that file exists, which is the
only honest way to check whether something ran.
"""
import json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CLOSE = os.path.join(REPO, "tools", "close.py")


def declare(root, plugin, skill, marker, sha=None):
    """A declaration where close.py looks for one. The cache keeps a <sha> level; this
    repo's own plugins/ does not, and the difference is the whole point of the test."""
    parts = [root, plugin] + ([sha] if sha else []) + ["skills", skill]
    d = os.path.join(*parts)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "places.json"), "w", encoding="utf-8") as f:
        json.dump({"operation": skill,
                   "places": [{"id": "somewhere", "root": "/tmp", "close": "commit"}],
                   "state": {"command": "touch %s" % marker}}, f)


def main():
    base = os.path.realpath(tempfile.mkdtemp(prefix="grove-close-test-"))
    fails = 0

    def check(ok, label, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"{'✓' if ok else '✗'} {label}" + (f"   [{detail}]" if detail and not ok else ""))

    try:
        ours = os.path.join(base, "ours")          # stands in for this repo's plugins/
        cache = os.path.join(base, "cache", "some-marketplace")
        mine = os.path.join(base, "ran-ours")
        theirs = os.path.join(base, "ran-theirs")
        declare(ours, "grove", "ours-op", mine)
        declare(cache, "their-plugin", "theirs-op", theirs, sha="abc123")

        def run(*args):
            env = dict(os.environ, GROVE_PLUGINS=ours,
                       GROVE_PLUGIN_CACHE=os.path.dirname(cache))
            p = subprocess.run([sys.executable, CLOSE] + list(args),
                               capture_output=True, text=True, timeout=120, env=env)
            return p.stdout + p.stderr

        out = run("--ops")
        check("ours-op" in out and "theirs-op" in out,
              "both declarations are found — the cache is read on purpose", out[:120])
        check("installed plugin" in out.split("theirs-op")[1].splitlines()[0],
              "and the one from the cache is marked as somebody else's")

        out = run("--op", "ours-op")
        check(os.path.exists(mine), "our own state command runs", out[-200:])

        out = run("--op", "theirs-op")
        check(not os.path.exists(theirs), "a plugin's state command does NOT run", out[-200:])
        check("touch " + theirs in out, "it is printed instead, in full")
        check("--run-state" in out, "and the way to run it deliberately is named")

        out = run("--op", "theirs-op", "--run-state")
        check(os.path.exists(theirs), "--run-state is the deliberate act", out[-200:])

        # A declaration that is not readable must not take the report down with it.
        os.makedirs(os.path.join(cache, "broken", "sha", "skills", "x"), exist_ok=True)
        with open(os.path.join(cache, "broken", "sha", "skills", "x", "places.json"), "w") as f:
            f.write("{not json")
        out = run("--ops")
        check("ours-op" in out, "a broken declaration beside them is skipped, not fatal")
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print(f"\n{'all checks passed' if not fails else str(fails) + ' failed'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
