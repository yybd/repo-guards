"""Branch pipeline for warn_ownership_drift.py.

    python3 plugins/grove/hooks/scripts/tests/test_warn_ownership_drift.py

Everything runs against a throwaway registry and throwaway places, because the property
worth pinning is that it stays SILENT — silent outside a registered place, silent where
the declaration and the disk agree, and silent about a gap it has already named. A Stop
hook that speaks every turn is a Stop hook that gets read past.
"""
import json, os, shutil, subprocess, sys, tempfile

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "warn_ownership_drift.py")
SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    base = os.path.realpath(tempfile.mkdtemp(prefix="grove-drift-test-"))
    fails = 0

    def check(ok, label, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"{'✓' if ok else '✗'} {label}" + (f"   [{detail}]" if detail and not ok else ""))

    def place(name, skills=(), claims=None, make=()):
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

    def fire(cwd, sid="s1", raw=None):
        payload = raw if raw is not None else json.dumps({"session_id": sid, "cwd": cwd})
        p = subprocess.run([sys.executable, HOOK], input=payload, capture_output=True,
                           text=True, timeout=15, cwd=base,
                           env=dict(os.environ,
                                    GROVE_REGISTRY=os.path.join(base, "registry.json"),
                                    GROVE_OWNS_STATE=os.path.join(base, "state"),
                                    PYTHONPATH=SCRIPTS))
        if p.returncode != 0:
            return "CRASH", (p.stderr.strip() or "nonzero exit")[:120]
        if not p.stdout.strip():
            return "silent", ""
        try:
            return "speaks", json.loads(p.stdout)["systemMessage"]
        except Exception as e:
            return "BADJSON", str(e)[:80]

    try:
        clean = place("clean")                                  # no skills, no claims
        bare = place("bare", skills=["alpha"])                   # skills, no declaration
        good = place("good", skills=["alpha"], make=["src"],
                     claims=[{"paths": ["src"], "owner": "alpha", "action": "block"}])
        stale = place("stale", skills=["alpha"], make=["src"],
                      claims=[{"paths": ["src"], "owner": "alpha · gone", "action": "block"}])
        nested = place(os.path.join("good", "inner"), skills=["beta"])
        json.dump({"projects": {
            "clean": {"root": clean}, "bare": {"root": bare}, "good": {"root": good},
            "stale": {"root": stale}, "nested": {"root": nested},
        }}, open(os.path.join(base, "registry.json"), "w"))

        print("-- when it stays silent --")
        got, _ = fire(os.path.join(base, "nowhere"))
        check(got == "silent", "outside every registered place", got)
        got, _ = fire(clean)
        check(got == "silent", "a place with no skills and no declaration", got)
        got, _ = fire(good)
        check(got == "silent", "a declaration that agrees with the disk", got)
        got, _ = fire(os.path.join(good, "src"))
        check(got == "silent", "from a subdirectory of a sound place too", got)

        print("\n-- when it speaks --")
        got, msg = fire(bare, sid="a")
        check(got == "speaks", "skills with no declaration at all", got)
        check("alpha" in msg, "names the skill")
        check("owns.json" in msg, "and points at the file to edit")
        got, msg = fire(stale, sid="b")
        check(got == "speaks" and "gone" in msg, "a claim naming a skill that is not here", got)

        print("\n-- once, not every turn --")
        got, _ = fire(bare, sid="a")
        check(got == "silent", "the same gap in this session — silent", got)
        os.makedirs(os.path.join(bare, ".claude", "skills", "gamma"), exist_ok=True)
        open(os.path.join(bare, ".claude", "skills", "gamma", "SKILL.md"), "w").write("x")
        got, msg = fire(bare, sid="a")
        check(got == "speaks" and "gamma" in msg, "a new gap — speaks again", got)
        got, _ = fire(bare, sid="c")
        check(got == "speaks", "another session hears it for itself", got)

        print("\n-- the right place --")
        got, msg = fire(nested, sid="d")
        check(got == "speaks" and "beta" in msg and "alpha" not in msg,
              "a nested repo — the deepest one wins", msg[:60])

        print("\n-- never crashes, never stops anything --")
        for label, raw in [("empty stdin", ""),
                           ("malformed JSON", "{{{"),
                           ("no cwd", json.dumps({"session_id": "x"})),
                           ("cwd is null", json.dumps({"cwd": None})),
                           ("a cwd that does not exist", json.dumps({"cwd": "/no/such/place"})),
                           ("no session_id", json.dumps({"cwd": bare}))]:
            got, detail = fire(None, raw=raw)
            check(got in ("silent", "speaks"), label, f"{got} {detail}")

        broken = place("broken", skills=["alpha"])
        open(os.path.join(broken, ".claude", "owns.json"), "w").write("{{{")
        json.dump({"projects": {"broken": {"root": broken}}},
                  open(os.path.join(base, "registry.json"), "w"))
        got, msg = fire(broken, sid="e")
        check(got == "speaks" and "cannot be read" in msg,
              "a broken declaration — reports exactly what the guard sees", got)
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print(f"\n{'all checks passed' if not fails else str(fails) + ' failed'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
