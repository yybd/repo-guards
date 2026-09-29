#!/usr/bin/env python3
"""Run one of grove's tools from inside the plugin, wherever the repo happens to sit.

    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/grove.py deploy --check
    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/grove.py close --commit -m "…"

The skills said `python3 $GROVE/tools/deploy.py`, and `$GROVE` is written into the
machine's settings by — deploy. So the one command a fresh installation needs was the
one command it could not name: before the first deploy the variable does not exist, and
the skill whose whole job is to run that first deploy pointed at nothing. Worse, it
pointed at nothing *silently*, because an unset variable in a shell is the empty string.

The plugin always knows where it is (`CLAUDE_PLUGIN_ROOT`, and this file's own path).
`grove_repo.grove_root()` knows how to get from there to the repo — through the
marketplace's recorded install location, which exists because the plugin could not have
been installed otherwise. This is the join between the two.

The tools stay in the repo rather than being copied into the plugin, and that is the
same decision the registry already forced: a plugin is a COPY pinned to a commit, so a
tool shipped inside it would be yesterday's tool operating on today's repo — and
`deploy.py`'s entire job is to notice that gap.
"""
import os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "hooks", "scripts")))
from grove_repo import grove_root                            # noqa: E402

SAFE = re.compile(r"^[a-z][a-z0-9_]*(\.py)?$")               # a tool's name, nothing else


def tools(root):
    d = os.path.join(root, "tools")
    try:
        return sorted(f[:-3] for f in os.listdir(d)
                      if f.endswith(".py") and not f.startswith("_"))
    except Exception:
        return []


def main():
    args = sys.argv[1:]
    root = grove_root()
    if not root:
        sys.stderr.write(
            "✗ grove's repo was not found from here.\n"
            "  The plugin is installed; the repo it was installed FROM is what carries\n"
            "  the tools and the registry, and nothing on this machine records it any\n"
            "  more. Either re-add the marketplace, or set GROVE_ROOT to the clone.\n")
        return 2
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip())
        print("\ntools here: " + ", ".join(tools(root)))
        return 0
    name = args[0]
    if not SAFE.match(name):
        sys.stderr.write(f"✗ not a tool name: {name}\n")
        return 2
    if not name.endswith(".py"):
        name += ".py"
    path = os.path.join(root, "tools", name)
    if not os.path.isfile(path):
        sys.stderr.write(f"✗ no such tool: {name[:-3]}\n"
                         f"  there is: {', '.join(tools(root))}\n")
        return 2
    return subprocess.run([sys.executable, path] + args[1:]).returncode


if __name__ == "__main__":
    sys.exit(main())
