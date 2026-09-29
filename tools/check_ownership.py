#!/usr/bin/env python3
"""Does every local skill have a declaration, and does every declaration still hold?

The guard reads `.claude/owns.json` and blocks nothing that is not written there. That
is deliberate — undeclared is open — but it has one failure mode that is silent by
construction: **a new local skill adds no line, so the paths it authors stay open, and
nothing anywhere says so.** The hole looks exactly like a place that decided to be open.

This is the detector, and it is a detector on purpose rather than a rule in the guard.
The guard must fail OPEN and runs on every write; anything added there costs on every
call and can stop work when it is wrong. A drift between a skill and a declaration is
not urgent — it is wrong for as long as nobody looks — so it is asked in the two places
where it is cheap: here, across every registered place, inside `deploy.py`; and at the
end of a turn about the place the session is standing in, by `warn_ownership_drift.py`.
The two are the same four questions from `grove_repo.ownership_gaps`, because a
detector that answers differently depending on who asked is worse than none.

Four questions, and the last two are the reverse direction — a declaration outliving
what it described:

    1. a repo with local skills and no owns.json at all
    2. a local skill that no claim names as its owner
    3. a claim naming an owner that is no longer a skill here
    4. a claim on a path that no longer exists

What it does NOT do: decide whether the claimed paths are the RIGHT paths. A skill's
text names dozens of paths, most of them in another tree or written as patterns, and the
first version of check_references.py already proved where that road ends — 258 findings,
most of them prose. A checker that reports noise is a checker nobody runs. The question
here is only whether the two sides know about each other.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "plugins", "grove", "hooks", "scripts"))
import grove_repo as fr                                  # noqa: E402

# The four questions live in grove_repo, next to the guard they are about, so
# the end-of-turn hook and this deploy-time sweep can never answer them
# differently. This file is the sweep and the wording; the judgement is there.

def _help_only():
    """`--help` must answer, not run. These take no options, so the docstring IS the
    usage — but a script that ignores `-h` and starts a full scan instead teaches you
    that its flags are not to be trusted."""
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(__doc__.strip())
        raise SystemExit(0)


def main():
    _help_only()
    try:
        # fr.registry_path(), not HERE/registry.json: it honours GROVE_REGISTRY and
        # finds the repo from anywhere. Reading the neighbour file worked only because
        # this script happens to sit beside it — which is the assumption portability
        # is supposed to have removed.
        with open(fr.registry_path(), encoding="utf-8") as f:
            reg = json.load(f)
    except FileNotFoundError:
        # A checkout that was never deployed has only registry.example.json — the state
        # of every build runner and of every clone before its first deploy. There are no
        # declared places yet, so there is nothing to be wrong about. Said, not failed.
        print("No registry yet — a fresh checkout. Nothing declares a place to check.")
        print("`python3 tools/deploy.py` creates one from the template.")
        return 0
    except Exception as e:
        print(f"no registry to read: {e}")
        return 1

    places = with_skills = 0
    found = []
    for name, root, _entry in fr.registry_roots(reg):
        if not os.path.isdir(root):
            continue
        places += 1
        if fr.has_local_skills(root):
            with_skills += 1
        for kind, what, why in fr.ownership_gaps(root):
            found.append((name, kind, what, why))

    print(f"Checked {places} places, {with_skills} of them carrying local skills.\n")
    if not found:
        print("✓ every local skill is declared, and every claim still points at something.")
        return 0
    last = None
    for name, kind, what, why in found:
        if name != last:
            print(f"  {name}")
            last = name
        print(f"      ✗ {kind}: {what}")
        print(f"        {why}")
    print(f"\n{len(found)} gaps between what is declared and what is there.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
