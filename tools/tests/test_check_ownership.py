"""Branch pipeline for check_ownership.py.

    python3 tools/tests/test_check_ownership.py

The checker's whole value is that it stays quiet on a machine where nothing drifted —
so the cases below are built as throwaway repos and every one of them asserts the exact
set of problems, not merely that something was reported. A checker that cries wolf is a
checker that gets removed.
"""
import json, os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
# The judgement lives in grove_repo, shared with the Stop hook — this file used to
# call check_ownership.check(), which stopped existing when the two were unified, and
# nothing noticed because nothing ran it. Both halves of that are fixed: the import
# follows the logic, and deploy.py now runs every test in this directory.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)),
                                "plugins", "grove", "hooks", "scripts"))
import grove_repo as co                                  # noqa: E402


def main():
    base = tempfile.mkdtemp(prefix="own-check-test-")
    fails = 0

    def mk(name, skills=(), claims=None, make=()):
        r = os.path.join(base, name)
        os.makedirs(os.path.join(r, ".claude"), exist_ok=True)
        for s in skills:
            os.makedirs(os.path.join(r, ".claude", "skills", s), exist_ok=True)
            open(os.path.join(r, ".claude", "skills", s, "SKILL.md"), "w").write("x")
        for m in make:
            os.makedirs(os.path.join(r, m), exist_ok=True)
        if claims is not None:
            json.dump({"claims": claims},
                      open(os.path.join(r, ".claude", "owns.json"), "w"))
        return r

    def t(label, got, want):
        nonlocal fails
        ok = got == want
        fails += 0 if ok else 1
        print(f"{'✓' if ok else '✗'} {label}" + ("" if ok else f"   [{got} != {want}]"))

    kinds = lambda root: sorted(k for k, _, _ in co.ownership_gaps(root))

    try:
        t("a place with no skills and no declaration — silent",
          kinds(mk("plain")), [])
        t("local skills and no declaration at all",
          kinds(mk("bare", skills=["a", "b"])), ["no declaration at all"])
        t("a skill nothing claims",
          kinds(mk("half", skills=["a", "b"], make=["x"],
                   claims=[{"paths": ["x"], "owner": "a", "action": "block"}])),
          ["a local skill nothing claims"])
        t("a claim naming a skill that is not here",
          kinds(mk("stale", skills=["a"], make=["x"],
                   claims=[{"paths": ["x"], "owner": "a · gone", "action": "block"}])),
          ["a claim naming a skill that is not here"])
        t("a claim on a path that vanished",
          kinds(mk("nopath", skills=["a"],
                   claims=[{"paths": ["vanished/"], "owner": "a", "action": "block"}])),
          ["claim on a path that does not exist"])
        t("a warn claim with no owner is not a missing skill",
          kinds(mk("warnonly", make=["f"], claims=[{"paths": ["f"], "action": "warn"}])), [])
        r = mk("badjson")
        open(os.path.join(r, ".claude", "owns.json"), "w").write("{{{")
        t("broken JSON — reports exactly what the guard sees", kinds(r), ["the declaration cannot be read"])
        t("several owners on one claim are all counted",
          kinds(mk("multi", skills=["a", "b"], make=["x"],
                   claims=[{"paths": ["x"], "owner": "a · b", "action": "block"}])), [])
        ghost = mk("empty-dir")
        os.makedirs(os.path.join(ghost, ".claude", "skills", "ghost"), exist_ok=True)
        t("a skill directory without SKILL.md is not a skill", kinds(ghost), [])
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print(f"\n{'all checks passed' if not fails else str(fails) + ' failed'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
