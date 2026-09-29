#!/usr/bin/env python3
"""Do the scripts the skills run still parse, and do their imports exist here?

The guards have pipelines. The scripts a skill hands to a session had nothing. A typo in
one of those does not surface at deploy; it surfaces at the single moment it is used —
and a skill's script is usually run at the point of no return, halfway through the
operation it exists to perform.

Two questions, and the split between them is the point:

    parse    the file compiles. Cheap, total, and catches the whole class of "someone
             edited it and did not run it".
    imports  every module imported at the top level can actually be found on this
             machine — stdlib or installed.

**Nothing here EXECUTES anything.** Not the script, not its imports, not `--help`. A
skill's scripts sign things, upload things and talk to other people's services; a
checker that runs them to see whether they work is a checker that ships something by
accident. Parsing is static, and imports are resolved with `find_spec`, which locates a
module without running it.

An import that resolves to something outside the standard library is COUNTED, not
failed. Pillow cannot be written in stdlib, and an image script rightly uses it. What
the count is for: this repo stands on the standard library alone, deliberately — it is
installed by cloning, so anything it imports is something the next machine has to have
— and that line moving is a decision worth seeing at deploy rather than discovering on
a machine where the package happens to be missing.
"""
import ast, importlib.util, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# Where a skill's scripts live, plus grove's own commands. The guards are left
# out on purpose: they each have a branch pipeline that already runs them.
ROOTS = [os.path.join(REPO, "plugins"), HERE]
SKIP = {"tests", "__pycache__", "node_modules", ".git", "dashboard"}
# Python 3.10 and later can name its own standard library. Below that it cannot, and the
# fallback used to be an empty set — which made every `import json` look like a
# third-party dependency and printed fifteen of them as "outside the standard library".
# macOS still ships 3.9 as /usr/bin/python3, so that was the first thing a new user saw.
# Unknown is not the same as absent: where the list is missing, the count is not offered.
STDLIB = set(getattr(sys, "stdlib_module_names", ()))
KNOWS_STDLIB = bool(STDLIB)
THIRD_PARTY = {}                                     # module → the scripts that import it


def files():
    for root in ROOTS:
        for base, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP]
            for n in sorted(names):
                if n.endswith((".py", ".sh")):
                    yield os.path.join(base, n)


def imported(tree):
    """Top-level module names this file imports. Nested imports are deliberate and skipped."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:          # `from .x import y` is local
                out.add(node.module.split(".")[0])
    return out


_LOCAL = None


def local_module(name):
    """A module this repo carries. Scripts reach them with sys.path.insert, and where
    exactly is not decidable statically — so the question asked is the one a person
    would ask: is there a file by that name in this repo at all?"""
    global _LOCAL
    if _LOCAL is None:
        _LOCAL = set()
        for base, dirs, names in os.walk(REPO):
            dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")]
            _LOCAL.update(n[:-3] for n in names if n.endswith(".py"))
    return name in _LOCAL


def check(path):
    """[(kind, detail)] for one file. Empty means it parses and resolves."""
    if path.endswith(".sh"):
        try:
            p = subprocess.run(["bash", "-n", path], capture_output=True, text=True,
                               timeout=20)
            return [] if p.returncode == 0 else [("syntax", p.stderr.strip()[:120])]
        except Exception as e:
            return [("cannot be checked", str(e)[:80])]

    try:
        with open(path, encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src, filename=path)
    except SyntaxError as e:
        return [("syntax", f"line {e.lineno}: {e.msg}")]
    except Exception as e:
        return [("cannot be read", str(e)[:80])]

    gaps = []
    for name in sorted(imported(tree)):
        if name in STDLIB or local_module(name):
            continue
        try:
            spec = importlib.util.find_spec(name)
        except Exception:
            spec = None
        if spec is None:
            gaps.append(("import not found here", name))
        elif KNOWS_STDLIB:
            # Installed and outside the standard library. Not a fault — Pillow cannot be
            # written in stdlib — but worth counting, because it is the difference
            # between a script that runs anywhere and one that runs on THIS machine.
            THIRD_PARTY.setdefault(name, []).append(path)
    return gaps


def _help_only():
    """`--help` must answer, not run. These take no options, so the docstring IS the
    usage — but a script that ignores `-h` and starts a full scan instead teaches you
    that its flags are not to be trusted."""
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(__doc__.strip())
        raise SystemExit(0)


def main():
    _help_only()
    checked = 0
    found = []
    for path in files():
        checked += 1
        for kind, detail in check(path):
            found.append((os.path.relpath(path, REPO), kind, detail))

    print(f"Checked {checked} scripts — static analysis only, nothing was executed.")
    if not KNOWS_STDLIB:
        print(f"This Python ({sys.version_info[0]}.{sys.version_info[1]}) cannot name its "
              f"own standard library, so nothing is counted as outside it.")
    if THIRD_PARTY:
        deps = ", ".join(f"{k} ({len(v)})" for k, v in sorted(THIRD_PARTY.items()))
        print(f"Outside the standard library, and installed: {deps}")
    print()
    if not found:
        print("✓ all of them parse, and every import resolves here.")
        return 0
    for rel, kind, detail in found:
        print(f"  ✗ {rel}\n      {kind}: {detail}")
    print(f"\n{len(found)} scripts that would break only at the moment they are used.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
