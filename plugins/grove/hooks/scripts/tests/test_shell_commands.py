#!/usr/bin/env python3
"""Pipeline for the one thing both guards stand on: reading a shell line.

    python3 plugins/grove/hooks/scripts/tests/test_shell_commands.py

`honor_ownership` asks what a line writes and `scope_foreign_commits` asks which repo it
acts on, and both first need the same answer: WHICH COMMANDS ARE IN THIS LINE, AND WHERE
DOES EACH ONE RUN. They each had their own splitter until 2026-09-11, and each was
defeated by the same leading `(`.

Two properties are worth more than the rest, and both are asserted here:

    a `cd` inside a group does NOT leak past it   — or a legitimate commit in the repo
                                                    you are standing in gets refused
    an empty piece terminates                     — `"" in "({"` is True, so a lone `}`
                                                    span the strip loop forever

Everything runs in memory. No files, no repos, no machine.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from grove_repo import shell_commands                       # noqa: E402

HERE = "/base/home"
THERE = "/base/other"


def words(cmd, cwd=HERE):
    return [(t, h) for t, h, _e in shell_commands(cmd, cwd)]


def main():
    fails = 0

    def check(ok, label, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"{'✓' if ok else '✗'} {label}" + (f"   [{detail}]" if detail and not ok else ""))

    print("-- where each command runs --")
    got = words(f"cd {THERE} && rm x")
    check(got == [(["rm", "x"], THERE)], "a cd moves what follows it", got)

    got = words(f"(cd {THERE} && rm x); rm y")
    check(got == [(["rm", "x"], THERE), (["rm", "y"], HERE)],
          "and a cd inside a group is undone when the group closes", got)

    got = words("{ cd %s && rm x; }; rm y" % THERE)
    check(got == [(["rm", "x"], THERE), (["rm", "y"], HERE)],
          "the same for a brace group", got)

    got = words(f"cd {THERE}/sub && cd .. && rm x")
    check(got == [(["rm", "x"], THERE)], "relative cds compose", got)

    print("\n-- what is one command and what is two --")
    check(len(words("echo 'a && b' > f")) == 1,
          "a separator inside quotes is not a separator")
    check([t for t, _ in words("echo hi | tee f")] == [["echo", "hi"], ["tee", "f"]],
          "a pipe is two commands")
    check([t for t, _ in words("echo hi >| f")] == [["echo", "hi", ">|", "f"]],
          "`>|` is one redirection, not a redirect and a pipe")
    check(len(words("git add $(git diff --name-only)")) == 1,
          "a command substitution is kept whole")

    print("\n-- the wrappers, and what is left of them --")
    for cmd, want in [("sudo tee f", ["tee", "f"]),
                      ("env FOO=1 cp a b", ["cp", "a", "b"]),
                      ("FOO=1 cp a b", ["cp", "a", "b"]),
                      ("time nice git push", ["git", "push"]),
                      ("sudo -u someone tee f", ["sudo", "-u", "someone", "tee", "f"])]:
        got = [t for t, _ in words(cmd)]
        check(got == [want], f"{cmd!r} → {want}", got)

    got = shell_commands("GIT_DIR=/x/.git git commit", HERE)
    check(got and got[0][2].get("GIT_DIR") == "/x/.git",
          "an assignment is handed back rather than dropped", got)

    print("\n-- a shell inside the shell --")
    got = words("bash -c 'cd %s && rm x'" % THERE)
    check(got == [(["rm", "x"], THERE)], "sh -c is read as the command line it is", got)
    got = words("(cd %s && bash -c 'rm x'); rm y" % THERE)
    check(got == [(["rm", "x"], THERE), (["rm", "y"], HERE)],
          "and its cd cannot leak either", got)
    got = [t for t, _ in words('sh -c "$CMD"')]
    check(got == [["sh", "-c", "$CMD"]],
          "a command line that is a variable stays unread — and is therefore allowed", got)

    print("\n-- it always terminates --")
    # `"" in "({"` is True, and that emptiness is what spun the strip loops.
    for cmd in ["}", "{", "(", ")", "()", "{}", "; ; ;", "|||", "$(", "'", '"',
                "( ( ( rm x ) ) )", "a" * 4000, "; ".join(["rm x"] * 200)]:
        try:
            shell_commands(cmd, HERE)
            check(True, f"{cmd[:18]!r}")
        except Exception as e:                     # noqa: BLE001 — the point is that it cannot
            check(False, f"{cmd[:18]!r}", str(e)[:60])
    check(len(shell_commands("; ".join(["rm x"] * 200), HERE)) <= 64,
          "and a pathological line is capped")

    print(f"\n{'all checks passed' if not fails else str(fails) + ' failed'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
