"""Branch pipeline for honor_ownership.py.

CLAUDE.md: a guard is run across all its branches before it takes effect, and it must
fail open. Everything here is a throwaway tree with its own declaration, because the
property worth pinning is that UNDECLARED IS OPEN — and asserting that against the
live machine would make the verdict depend on which repo happens to declare today.

Three groups: what the declaration blocks, what it deliberately does not, and every
malformed input, each of which must ALLOW.

    python3 plugins/grove/hooks/scripts/tests/test_honor_ownership.py
"""
import json, os, shutil, subprocess, sys, tempfile

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "honor_ownership.py")


def write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    base = os.path.realpath(tempfile.mkdtemp(prefix="grove-owns-test-"))
    fails = 0

    def check(ok, got, exp, label, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"{'✓' if ok else '✗':2}{got:<10}{exp:<10}  {label}" + (f"   [{detail}]" if detail else ""))

    try:
        site = os.path.join(base, "site")
        outside = os.path.join(base, "outside")
        # a sibling whose name starts with the same string — containment is a path
        # question, not a prefix question
        lookalike = os.path.join(base, "site-evil")
        for d in (outside, lookalike):
            os.makedirs(d, exist_ok=True)

        write(os.path.join(site, ".claude", "owns.json"), json.dumps({"claims": [
            {"paths": ["src/pages/", "src/data/apps.ts"], "owner": "add-app-to-site",
             "action": "block", "why": "the page structure is written by this skill"},
            {"paths": ["i18n/"], "owner": "translate-site", "action": "block"},
            {"paths": ["content/en.json"], "action": "warn",
             "why": "run `npm run content` afterwards and commit both"},
            "a string where a claim should be — prose in a data file happens",
        ]}))
        for d in ("src/pages", "src/data", "i18n", "content", "public/data"):
            os.makedirs(os.path.join(site, d), exist_ok=True)

        def run(target, cwd, key="file_path", raw=None):   # target ignored when raw
            payload = raw if raw is not None else json.dumps(
                {"tool_name": "Write", "tool_input": {key: target}, "cwd": cwd})
            p = subprocess.run([sys.executable, HOOK], input=payload, capture_output=True,
                               text=True, timeout=15, cwd=base)
            if p.returncode != 0:
                return "CRASH", (p.stderr.strip() or "nonzero exit")[:120]
            out = p.stdout.strip()
            if not out:
                return "allow", ""
            try:
                d = json.loads(out)["hookSpecificOutput"]
            except Exception as e:
                return "BADJSON", str(e)[:80]
            if d.get("permissionDecision") == "deny":
                return "block", d.get("permissionDecisionReason", "")
            if d.get("additionalContext"):
                return "warn", d["additionalContext"]
            return "?", out[:80]

        print(f"{'':2}{'result':<10}{'expected':<10}  case")
        CASES = [
            ("block", "a declared path, from outside",            f"{site}/src/pages/x.astro", outside),
            ("block", "a file declared by name",               f"{site}/src/data/apps.ts", outside),
            ("block", "a second claim in the same declaration",       f"{site}/i18n/he.json", outside),
            ("warn",  "a rule, not ownership → informs, does not block", f"{site}/content/en.json", outside),

            ("allow", "standing in the place itself",             f"{site}/src/pages/x.astro", site),
            ("allow", "standing in a subdirectory of it",         f"{site}/src/pages/x.astro", f"{site}/src"),
            ("allow", "an undeclared path — open",         f"{site}/public/data/apps.json", outside),
            ("allow", "a sibling that declared nothing",             f"{outside}/x.txt", site),
            ("allow", "a directory whose name starts like the declared one",  f"{lookalike}/src/pages/x.astro", outside),
            ("allow", "a path that is only a prefix of a claim",  f"{site}/src/pag", outside),
        ]
        for exp, label, target, cwd in CASES:
            got, detail = run(target, cwd)
            check(got == exp, got, exp, label, detail if got != exp else "")

        for key in ("path", "notebook_path"):
            got, _ = run(f"{site}/i18n/he.json", outside, key=key)
            check(got == "block", got, "block", f"the {key} key")

        # --- shell lines: the surface the guard was blind to until 2026-09-10 ---
        print("\n-- writing through Bash --")

        def sh(cmd, cwd):
            return run(None, cwd, raw=json.dumps(
                {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": cwd}))

        SHELL = [
            ("block", "a redirection into a declared path",     f"echo x > {site}/src/pages/x.astro", outside),
            ("block", "an appending redirection (>>)",          f"echo x >> {site}/src/data/apps.ts", outside),
            ("block", "a stderr redirection (2>)",       f"cmd 2>{site}/src/data/apps.ts", outside),
            ("block", "sed -i on a declared file",       f"sed -i '' s/a/b/ {site}/src/data/apps.ts", outside),
            ("block", "tee",                        f"echo x | tee {site}/src/data/apps.ts", outside),
            ("block", "cp — the destination is the last argument",       f"cp /tmp/x {site}/i18n/he.json", outside),
            ("block", "mv — the source is written too",         f"mv {site}/i18n/he.json /tmp/x", outside),
            ("block", "rm -rf",                     f"rm -rf {site}/src/pages", outside),
            ("block", "mkdir inside a claim",           f"mkdir -p {site}/src/pages/new", outside),
            ("block", "cd, then a relative path",           f"cd {site} && echo x > src/pages/y.astro", outside),
            ("block", "one segment out of several",          f"echo a > /tmp/ok && echo b > {site}/i18n/he.json", outside),
            ("block", "a heredoc into a declared path",    f"cat > {site}/src/data/apps.ts <<'EOF'\nx\nEOF", outside),

            ("warn",  "a rule, not ownership — in a shell line too", f"echo x > {site}/content/en.json", outside),

            ("allow", "reading is not writing",           f"cat {site}/src/data/apps.ts", outside),
            ("allow", "grep over a declared directory",      f"grep -r foo {site}/src/pages", outside),
            ("allow", "an undeclared path",             f"echo x > {site}/public/data/apps.json", outside),
            ("allow", "outside every declaration",             f"echo x > {outside}/f.txt", outside),
            ("allow", "standing in the place itself",          "echo x > src/pages/x.astro", site),
            ("allow", "what a script writes is out of reach", f"python3 build.py --out {site}/i18n", outside),
            ("allow", "'>' inside a quoted string is not a redirection", f"echo 'a > b' {site}/src/pages", outside),
            ("allow", "a command that is not on the list",         f"chmod 644 {site}/src/data/apps.ts", outside),
        ]
        for exp, label, cmd, cwd in SHELL:
            got, detail = sh(cmd, cwd)
            check(got == exp, got, exp, label, detail[:90] if got != exp else "")

        # --- what walked past it until 2026-09-11 ---
        # Each of these was measured being allowed in silence while the same write,
        # spelled plainly, was refused. The last group is the other direction: a fix
        # that costs a legitimate command is not a fix.
        print("\n-- the shapes that used to walk past --")
        MORE = [
            ("block", "a subshell hides the cd",        "(cd %s && echo x > src/pages/p.astro)" % site, outside),
            ("block", "a brace group hides it too",     "{ cd %s && rm -rf src/pages; }" % site, outside),
            ("block", "bash -c with the write inside",  "bash -c 'echo x > %s/i18n/he.json'" % site, outside),
            ("block", "a quoted && no longer splits the line", "sh -c \"cd %s && rm -rf src/pages\"" % site, outside),
            ("block", "&> writes too",                  f"echo x &> {site}/src/data/apps.ts", outside),
            ("block", ">| is a deliberate overwrite",   f"echo x >| {site}/src/data/apps.ts", outside),
            ("block", "perl -pi, where only -i was read", f"perl -pi -e s/a/b/ {site}/src/data/apps.ts", outside),
            ("block", "rm -rf the parent of a claim",   f"rm -rf {site}/src", outside),
            ("block", "rm -rf the whole place",         f"rm -rf {site}", outside),
            ("block", "cp -r into the parent",          f"cp -r /tmp/pages {site}/src/", outside),
            ("block", "mv the parent away",             f"mv {site}/src /tmp/gone", outside),
            ("block", "sudo in front of it",            f"sudo tee {site}/src/data/apps.ts", outside),
            ("block", "env FOO=1 in front of it",       f"env FOO=1 cp /tmp/x {site}/i18n/he.json", outside),
            ("block", "a bare assignment in front of it", f"FOO=1 cp /tmp/x {site}/i18n/he.json", outside),

            ("allow", "a subshell somewhere else",      "(cd %s && echo x > f.txt)" % outside, outside),
            ("allow", "the cd ends with its group",     "(cd %s && ls); echo x > %s/f.txt" % (site, outside), outside),
            ("allow", "a command line that is a variable", 'sh -c "$CMD"', outside),
            ("allow", "xargs — the write belongs to a command this never sees",
             "xargs -I{} cp {} " + site + "/src/pages/", outside),
            ("allow", "find -exec, for the same reason",
             "find . -exec cp {} " + site + "/src/pages/ ;", outside),
            ("allow", "sed without -i writes nothing",  f"sed -n -e s/a/b/p {site}/src/data/apps.ts", outside),
            ("allow", "a flag bundle on a command that never writes in place",
             f"grep -ri foo {site}/src/pages", outside),
            ("allow", "the claim quoted inside an argument", f"echo 'rm -rf {site}/src' > /tmp/grove-note", outside),
        ]
        for exp, label, cmd, cwd in MORE:
            got, detail = sh(cmd, cwd)
            check(got == exp, got, exp, label, detail[:90] if got != exp else "")

        print("\n-- and the reason says which way it matched --")
        got, reason = sh(f"rm -rf {site}/src", outside)
        for needle, label in [("CONTAINS", "a target ABOVE a claim is named as containing it"),
                              ("src/pages", "and the claimed path it would take with it")]:
            check(needle in reason, "yes" if needle in reason else "no", "yes", label)

        print("\n-- the reason --")
        got, reason = run(f"{site}/src/pages/x.astro", outside)
        for needle, label in [("add-app-to-site", "names the owner from the declaration, not from a guess"),
                              ("page structure", "and passes on the why written there"),
                              ("change_directory", "and offers a way forward")]:
            check(needle in reason, "yes" if needle in reason else "no", "yes", label)
        got, ctx = run(f"{site}/content/en.json", outside)
        check("npm run content" in ctx, "yes" if "npm run content" in ctx else "no",
              "yes", "the warning carries the action to take")

        print("\n-- fails open --")
        bad = os.path.join(base, "bad")
        write(os.path.join(bad, ".claude", "owns.json"), "{not json")
        os.makedirs(os.path.join(bad, "src"), exist_ok=True)
        typed = os.path.join(base, "typed")
        write(os.path.join(typed, ".claude", "owns.json"),
              json.dumps({"claims": [{"paths": "src/", "action": "block"}]}))
        os.makedirs(os.path.join(typed, "src"), exist_ok=True)

        RAW = [
            ("empty stdin", ""),
            ("malformed JSON", "{{{"),
            ("no tool_input", json.dumps({"cwd": outside})),
            ("tool_input with no path", json.dumps({"tool_input": {"command": "ls"}, "cwd": outside})),
            ("file_path is null", json.dumps({"tool_input": {"file_path": None}, "cwd": outside})),
            ("file_path is a number", json.dumps({"tool_input": {"file_path": 7}, "cwd": outside})),
            ("tool_input is null", json.dumps({"tool_input": None, "cwd": outside})),
        ]
        for label, raw in RAW:
            got, detail = run(None, None, raw=raw)
            check(got == "allow", got, "allow", label, detail if got != "allow" else "")

        got, detail = run(f"{bad}/src/x.txt", outside)
        check(got == "allow", got, "allow", "a declaration that is not JSON → allows", detail if got != "allow" else "")
        got, _ = run(f"{typed}/src/x.txt", outside)
        check(got == "block", got, "block", "paths as a string, not a list → still enforced")

    finally:
        shutil.rmtree(base, ignore_errors=True)

    print(f"\n{'all checks passed' if not fails else str(fails) + ' failed'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
