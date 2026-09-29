"""Branch pipeline for record_touched_repos.py.

    python3 tools/hooks/tests/test_record_touched_repos.py

The recorder runs on EVERY tool call, so the properties that matter most are that it
never blocks, never prints, and never raises — those are checked against malformed
input as well as good. State goes to a throwaway dir via GROVE_TOUCHED_STATE.
"""
import json, os, shutil, subprocess, sys, tempfile

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "record_touched_repos.py")


def mk(base, name):
    r = os.path.join(base, name); os.makedirs(r)
    for a in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", r] + a, capture_output=True)
    open(os.path.join(r, "seed.txt"), "w").write("s\n")
    subprocess.run(["git", "-C", r, "add", "."], capture_output=True)
    subprocess.run(["git", "-C", r, "commit", "-qm", "s"], capture_output=True)
    return r


def fire(state, payload, raw=None):
    p = subprocess.run([sys.executable, HOOK],
                       input=raw if raw is not None else json.dumps(payload),
                       capture_output=True, text=True, timeout=30,
                       env=dict(os.environ, GROVE_TOUCHED_STATE=state))
    return p.returncode, p.stdout, p.stderr


def load(state, sid="s1"):
    f = os.path.join(state, f"{sid}.json")
    return json.load(open(f)) if os.path.exists(f) else None


def main():
    base = tempfile.mkdtemp(prefix="grove-rec-test-")
    fails = 0

    def check(ok, label, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"{'✓' if ok else '✗'} {label}" + (f"   [{detail}]" if detail and not ok else ""))

    try:
        A, B = mk(base, "A"), mk(base, "B")
        open(os.path.join(A, "owner.txt"), "w").write("pre-existing\n")   # baseline dirt
        st = os.path.join(base, "state")

        # Write tool -> repo recorded, with the path
        rc, out, err = fire(st, {"session_id": "s1", "tool_name": "Write",
                                 "tool_input": {"file_path": os.path.join(A, "mine.txt")},
                                 "cwd": A})
        d = load(st)
        check(rc == 0 and out == "" and d and os.path.realpath(A) in d["repos"],
              "the Write tool → the repo is recorded", err[:80] or out[:60])
        check("mine.txt" in d["repos"][os.path.realpath(A)]["paths"], "the path itself is recorded")
        check(d["repos"][os.path.realpath(A)]["baseline"] == ["owner.txt"],
              "dirt that predates the session is kept as the baseline")
        check(d["repos"][os.path.realpath(A)]["written"] == ["mine.txt"],
              "a writing tool → the path is recorded as written too")
        head = d["repos"][os.path.realpath(A)].get("head")
        check(isinstance(head, str) and len(head) == 40, "the HEAD the place stood on is recorded")

        # --- the separation that authorship rests on ---
        # A path that was only READ must never appear in `written`. This is the defect
        # that reported five of a parallel session's files as "mine" on 2026-09-10.
        print("\n-- what was only read is not writing --")
        fire(st, {"session_id": "s1", "tool_name": "Read",
                  "tool_input": {"file_path": os.path.join(A, "seed.txt")}, "cwd": A})
        fire(st, {"session_id": "s1", "tool_name": "Grep",
                  "tool_input": {"path": os.path.join(A, "owner.txt")}, "cwd": A})
        fire(st, {"session_id": "s1", "tool_name": "Bash",
                  "tool_input": {"command": f"sed -i '' s/x/y/ {A}/shellwrite.txt"}, "cwd": A})
        w = d_after = load(st)["repos"][os.path.realpath(A)]
        check("seed.txt" in w["paths"] and "seed.txt" not in w["written"],
              "a read is recorded in paths and not in written")
        check("owner.txt" not in w["written"], "a path scanned by Grep is not a write")
        check("shellwrite.txt" not in w["written"],
              "what Bash writes is not claimed as ours — under-reporting is the safe direction")

        # a writing tool that names several paths records all of them
        fire(st, {"session_id": "s1", "tool_name": "MultiEdit",
                  "tool_input": {"edits": [{"file_path": os.path.join(A, "e1.txt")},
                                           {"file_path": os.path.join(A, "e2.txt")}]}, "cwd": A})
        w = load(st)["repos"][os.path.realpath(A)]["written"]
        check("e1.txt" in w and "e2.txt" in w, "MultiEdit → every written path is recorded")

        # the cwd counts as a place, and must never count as a write
        check("." not in load(st)["repos"][os.path.realpath(A)]["written"],
              "the cwd is never a write")

        # a foreign repo mentioned only inside a Bash command
        fire(st, {"session_id": "s1", "tool_name": "Bash",
                  "tool_input": {"command": f"cat {B}/seed.txt | head -1"}, "cwd": A})
        d = load(st)
        check(os.path.realpath(B) in d["repos"], "a repo mentioned only inside a Bash command")

        # a path outside any repo is ignored
        fire(st, {"session_id": "s1", "tool_name": "Read",
                  "tool_input": {"file_path": "/etc/hosts"}, "cwd": A})
        d = load(st)
        check(all("/etc" not in r for r in d["repos"]), "a path in no repo → skipped")

        # sessions do not bleed into each other
        fire(st, {"session_id": "s2", "tool_name": "Write",
                  "tool_input": {"file_path": os.path.join(B, "x.txt")}, "cwd": B})
        d2 = load(st, "s2")
        check(d2 and os.path.realpath(A) not in d2["repos"], "a second session is kept separate")

        # the directory cache fills, so repeats are lookups rather than git calls
        check(len(load(st).get("dir_cache", {})) > 0, "the directory cache fills")

        # --- properties that matter on every single tool call ---
        print("\n-- never blocks, never prints, never crashes --")
        for label, payload, raw in [
            ("empty stdin", None, ""),
            ("malformed JSON", None, "{{{"),
            ("no session_id", {"tool_name": "Write", "tool_input": {"file_path": A}}, None),
            ("a malicious session_id", {"session_id": "../../etc/x", "tool_name": "Read",
                                  "tool_input": {"file_path": A}}, None),
            ("tool_input is a string", {"session_id": "s1", "tool_input": "nope"}, None),
            ("no paths at all", {"session_id": "s1", "tool_name": "Bash",
                                "tool_input": {"command": "echo hi"}}, None),
            ("a path that does not exist", {"session_id": "s1", "tool_name": "Write",
                                 "tool_input": {"file_path": "/no/such/place/x"}}, None),
            ("a command with 200 paths", {"session_id": "s1", "tool_name": "Bash",
                                     "tool_input": {"command": " ".join(f"{A}/f{i}" for i in range(200))}}, None),
        ]:
            rc, out, err = fire(st, payload, raw)
            check(rc == 0 and out == "" and err.strip() == "", label, f"rc={rc} out={out[:40]} err={err[:60]}")

        # nothing escaped the state dir
        check(not os.path.exists("/etc/x.json"), "a malicious session_id created no file outside the directory")
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print(f"\n{'all checks passed' if not fails else str(fails) + ' failed'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
