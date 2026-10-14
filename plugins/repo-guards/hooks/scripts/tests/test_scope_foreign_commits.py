"""Branch pipeline for scope_foreign_commits.py.

The project rule (CLAUDE.md, "The guard") says a guard must fail open and that every
change is run across all branches before it takes effect. This is that pipeline —
versioned so the rule is checkable rather than remembered.

    python3 plugins/repo-guards/hooks/scripts/tests/test_scope_foreign_commits.py

Exits non-zero on any failure. Every deny case must deny, every allow case must
allow, and the malformed-input cases must allow rather than crash.
"""

import atexit, json, os, shutil, subprocess, sys, tempfile

# Derived, never written down. These four were absolute paths into tools/hooks/, and
# when the guards moved into the plugin this pipeline went on testing the OLD file and
# reporting 36 passes for code nobody was running any more. It only spoke up once the
# old copy was deleted — which is to say it would have stayed silent through the entire
# migration if the sources had been kept "just in case".
SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS)
from guards_repo import guards_root, resolve_root  # noqa: E402

HOOK = os.path.join(SCRIPTS, "scope_foreign_commits.py")
FACTORY = guards_root()
if not FACTORY:
    sys.exit("✗ RepoGuards repo was not found. This pipeline checks against the live registry.")

# From the live registry rather than hardcoded: this pipeline is the one that asserts
# against real roots, so it must read the same file the guard reads.
#
# And it has to work on a machine that is not this one. Naming three specific repos made
# this test unpassable for anybody who installed RepoGuards — their registry holds their
# repos, not these. So: use whatever the registry actually has, and when it has too
# little (a fresh clone has the template), build a registry of throwaway repos and test
# against that instead. The guard cannot tell the difference; the assertions are the same.
def _load():
    """The registry the GUARD will read — registry_path(), not the repo's file.

    They are the same thing until someone sets REPO_GUARDS_REGISTRY, and then they are not:
    the test picked real repos out of this machine's registry while the guard, reading an
    empty override, saw none and allowed everything. 28 checks failed and the guard was
    correct in every one of them.
    """
    try:
        from guards_repo import registry_path
        with open(registry_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _live_roots(reg):
    """(hub, site, app) from the registry — the first real entries, whatever they are."""
    projects = [resolve_root(e["root"]) for n, e in sorted((reg.get("projects") or {}).items())
                if not n.startswith("_") and isinstance(e, dict) and e.get("root")]
    apps = [resolve_root(e["repo"]) for n, e in sorted((reg.get("apps") or {}).items())
            if not n.startswith("_") and isinstance(e, dict) and e.get("repo")]
    projects = [p for p in projects if p and os.path.isdir(p)]
    apps = [a for a in apps if a and os.path.isdir(a)]
    # RepoGuards itself is one of them, and the test needs roots that are NOT it
    others = [p for p in projects if p != FACTORY]
    if len(others) >= 2 and apps:
        return others[0], others[1], apps[0]
    return None


def _fixture():
    """Three throwaway repos and a registry naming them, for a machine with no tree yet."""
    base = os.path.realpath(tempfile.mkdtemp(prefix="repo-guards-scope-fixture-"))
    atexit.register(shutil.rmtree, base, True)
    made = []
    for name in ("hub", "site", "app"):
        r = os.path.join(base, name)
        os.makedirs(r)
        subprocess.run(["git", "-C", r, "init", "-q"], capture_output=True)
        made.append(r)
    reg = {"projects": {"hub": {"root": made[0]}, "site": {"root": made[1]},
                        "factory": {"root": FACTORY}},
           "apps": {"app": {"repo": made[2]}}}
    path = os.path.join(base, "registry.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reg, f)
    os.environ["REPO_GUARDS_REGISTRY"] = path          # the guard reads this one from now on
    return tuple(made)


_live = _live_roots(_load())
HUB, SITE, APP = _live if _live else _fixture()

def run(cmd, cwd=FACTORY, raw=None):
    payload = raw if raw is not None else json.dumps(
        {"tool_input": {"command": cmd}, "cwd": cwd})
    p = subprocess.run([sys.executable, HOOK], input=payload,
                       capture_output=True, text=True, timeout=10)
    if p.returncode != 0:
        return "CRASH", p.stderr.strip()[:120]
    out = p.stdout.strip()
    if not out:
        return "allow", ""
    try:
        d = json.loads(out)["hookSpecificOutput"]
    except Exception as e:
        return "BADJSON", str(e)[:80]
    if "permissionDecision" in d:
        return d["permissionDecision"], ""
    # a third verdict: allowed, and handed the foreign repo's status as context
    if d.get("additionalContext"):
        return "context", d["additionalContext"]
    return "?", out[:80]

CASES = [
    # (expected, label, cmd, cwd)
    ("deny",  "commit -am on foreign hub",        f'git -C {HUB} commit -am "x"',        FACTORY),
    ("deny",  "commit -a -m on foreign hub",      f'git -C {HUB} commit -a -m "x"',      FACTORY),
    ("deny",  "commit --all on foreign hub",      f'git -C {HUB} commit --all -m "x"',   FACTORY),
    ("deny",  "commit -va bundle",                f'git -C {HUB} commit -va -m "x"',     FACTORY),
    ("deny",  "add . on foreign site",            f'git -C {SITE} add .',                FACTORY),
    ("deny",  "add -A on foreign site",           f'git -C {SITE} add -A',               FACTORY),
    ("deny",  "add --all on foreign site",        f'git -C {SITE} add --all',            FACTORY),
    ("deny",  "add -u on foreign site",           f'git -C {SITE} add -u',               FACTORY),
    ("deny",  "cd then commit -am",               f'cd {HUB} && git commit -am "x"',     FACTORY),
    ("deny",  "cd then add .",                    f'cd {HUB} && git add .',              FACTORY),
    ("deny",  "compound, git last",               f'echo hi && git -C {HUB} commit -am "x"', FACTORY),
    ("deny",  "foreign from inside another root", f'git -C {HUB} commit -am "x"',        SITE),
    ("deny",  "factory is a root too",            f'git -C {FACTORY} commit -am "x"',    HUB),

    ("deny",  "commit -am on a foreign APP repo",  f'git -C {APP} commit -am "x"',  FACTORY),
    ("deny",  "add . on a foreign APP repo",         f'git -C {APP} add .',           FACTORY),
    ("deny",  "app repo swept from another app",     f'git -C {APP} commit -am "x"',  HUB),

    ("allow", "standing in the app: commit -am",     f'git -C {APP} commit -am "x"',  APP),
    ("context", "explicit paths in the app repo",    f'git -C {APP} add ios/App.plist', FACTORY),
    ("context", "explicit paths on foreign hub",  f'git -C {HUB} add anapp/prices.json', FACTORY),
    ("context", "commit without -a (staged)",     f'git -C {HUB} commit -m "x"',         FACTORY),
    ("allow", "standing in it: commit -am",       f'git commit -am "x"',                 FACTORY),
    ("allow", "standing in it via -C",            f'git -C {FACTORY} commit -am "x"',    FACTORY),
    ("allow", "standing in hub: add .",           f'git add .',                          HUB),
    ("allow", "subdir of the root counts as in",  f'git -C {HUB} commit -am "x"', HUB + "/anapp"),
    ("context", "message containing -a",          f'git -C {HUB} commit -m "fix -a bug"', FACTORY),
    ("context", "message via -F file",            f'git -C {HUB} commit -F /tmp/msg',    FACTORY),
    ("allow", "repo not in registry",             'git -C /tmp/whatever commit -am "x"', FACTORY),
    ("allow", "read-only git",                    f'git -C {HUB} status --short',        FACTORY),
    ("allow", "git log",                          f'git -C {HUB} log --oneline',         FACTORY),
    ("allow", "not git at all",                   'ls -a && rm -rf /tmp/x',              FACTORY),
    ("context", "add with --chmod",               f'git -C {HUB} add --chmod=+x run.sh', FACTORY),
    ("allow", "empty command",                    '',                                    FACTORY),
    ("allow", "unparseable quoting",              f'git -C {HUB} commit -am "unclosed',  FACTORY),
    ("allow", "diff/show",                        f'git -C {HUB} diff HEAD~1',           FACTORY),
    # push was out of scope until 2026-09-10, and the docs called that the most serious
    # omission of the lot: it publishes a whole branch and cannot be undone.
    ("deny",  "push to a foreign repo",           f'git -C {HUB} push',                  FACTORY),
    ("deny",  "push --force to a foreign repo",   f'git -C {HUB} push --force',          FACTORY),
    ("deny",  "cd then push",                     f'cd {HUB} && git push',               FACTORY),
    ("allow", "push while standing in it",        f'git push',                           HUB),
    ("allow", "push while standing in it via -C", f'git -C {HUB} push',                  HUB),
    ("allow", "push to a repo not in the registry", 'git -C /tmp/whatever push',         FACTORY),
]

# Every one of these was measured walking straight past the guard on 2026-09-11, against
# a throwaway pair of repos. They are grouped rather than mixed into the list above so
# that the record stays readable: this is what a splitter that read only `cd` at the head
# of a segment, and a target that could only be spelled `-C`, could not see.
CASES += [
    ("deny",  "a subshell hides the cd",          "(cd %s && git commit -am x)" % HUB,   FACTORY),
    ("deny",  "a brace group hides it too",       "{ cd %s && git commit -am x; }" % HUB, FACTORY),
    ("deny",  "bash -c with the whole line in it", "bash -c 'cd %s && git commit -am x'" % HUB, FACTORY),
    ("deny",  "sh -c around a foreign push",      "sh -c 'git -C %s push'" % HUB,        FACTORY),
    ("deny",  "--git-dir with --work-tree",       f"git --git-dir={HUB}/.git --work-tree={HUB} commit -am x", FACTORY),
    ("deny",  "the same two, spelled with spaces", f"git --git-dir {HUB}/.git --work-tree {HUB} commit -am x", FACTORY),
    ("deny",  "--git-dir alone names the tree above it", f"git --git-dir={HUB}/.git commit -am x", FACTORY),
    ("deny",  "GIT_DIR and GIT_WORK_TREE in front", f"GIT_DIR={HUB}/.git GIT_WORK_TREE={HUB} git commit -am x", FACTORY),
    ("deny",  "GIT_DIR alone",                    f"GIT_DIR={HUB}/.git git commit -am x", FACTORY),
    ("deny",  "a pathspec that IS the repo root", f"git -C {HUB} add {HUB}",             FACTORY),
    ("deny",  "the same with a trailing slash",   f"git -C {HUB} add {HUB}/",            FACTORY),
    ("deny",  "sudo in front of it",              f"sudo git -C {HUB} push",             FACTORY),
    ("deny",  "git by absolute path",             f"/usr/bin/git -C {HUB} commit -am x", FACTORY),

    # …and the other direction, which matters more: none of the above may cost a
    # legitimate command. A `cd` inside a group ENDS with the group, and reading it as
    # though it leaked would refuse a commit in the repo the session is standing in.
    ("allow", "the cd ends with its group",       "(cd %s && git status); git commit -am x" % HUB, FACTORY),
    ("allow", "and with its brace group",         "{ cd %s && git log; }; git commit -am x" % HUB, FACTORY),
    ("context", "an explicit path under the root is not a sweep", f"git -C {HUB} add {HUB}/one/file.json", FACTORY),
    ("context", "clean -fd is reported, not refused", f"git -C {HUB} clean -fd",         FACTORY),
    ("allow", "a command line that is a variable", 'sh -c "$CMD"',                       FACTORY),
    ("allow", "a loop variable cannot be resolved", "for d in %s; do git -C $d commit -am x; done" % HUB, FACTORY),
    ("allow", "the command quoted inside an argument", "echo 'git -C %s commit -am x' > /tmp/repo-guards-note" % HUB, FACTORY),
]

fails = 0
print(f"{'':2}{'result':<8}{'expected':<8}  case")
for exp, label, cmd, cwd in CASES:
    got, err = run(cmd, cwd)
    ok = got == exp
    fails += 0 if ok else 1
    print(f"{'✓' if ok else '✗':2}{got:<8}{exp:<8}  {label}" + (f"   [{err}]" if err else ""))

# --- the third verdict: allowed, and handed the picture it could not see ---
# A foreign write that stages explicit paths is legitimate, and still blind: what else
# is dirty there is invisible from here. So it is allowed and the status comes with it.
print("\n-- the picture you cannot see from here --")
EYES = [
    ("context", "an explicit foreign write → gets the status", f'git -C {HUB} add x.json',   FACTORY),
    ("allow",   "a foreign read needs no picture",          f'git -C {HUB} log --oneline', FACTORY),
    ("allow",   "standing there — the status is already in front of you",         f'git add x.json',             HUB),
    ("allow",   "a repo that is not in the registry",                   'git -C /tmp/whatever add x',  FACTORY),
]
for exp, label, cmd, cwd in EYES:
    got, ctx = run(cmd, cwd)
    ok = got == exp
    fails += 0 if ok else 1
    print(f"{'✓' if ok else '✗':2}{got:<8}{exp:<8}  {label}")
got, ctx = run(f'git -C {HUB} add x.json', FACTORY)
for needle, label in [(HUB, "the picture names the target repo"),
                      ("close.py", "and points at the command that sees them all")]:
    ok = needle in ctx
    fails += 0 if ok else 1
    print(f"{'✓' if ok else '✗':2}{'yes' if ok else 'no':<8}{'yes':<8}  {label}")

# --- a repo nobody registered is still foreign ---
# Until 0.3.0 only registry roots counted, so a stranger's two fresh repos were exempt —
# while the README said the guards run in every repo, registered or not. Git decides now.
print("\n-- unregistered repos --")
_u = os.path.realpath(tempfile.mkdtemp(prefix="repo-guards-unreg-"))
atexit.register(shutil.rmtree, _u, True)
for _n in ("mine", "theirs"):
    subprocess.run(["git", "init", "-q", os.path.join(_u, _n)], capture_output=True)
os.makedirs(os.path.join(_u, "mine", "src"))
os.makedirs(os.path.join(_u, "plain"))
MINE, THEIRS = os.path.join(_u, "mine"), os.path.join(_u, "theirs")
UNREG = [
    ("deny",    "push into an unregistered sibling",           "git -C ../theirs push",        MINE),
    ("deny",    "commit -am into an unregistered sibling",     "git -C ../theirs commit -am x", MINE),
    ("deny",    "add . after cd into it",                      "cd ../theirs && git add .",     MINE),
    ("context", "an explicit add there gets the picture",      "git -C ../theirs add a.txt",   MINE),
    ("allow",   "push from a subdirectory of our own repo",    "git push",                     os.path.join(MINE, "src")),
    ("allow",   "commit -am in our own repo",                  "git commit -am x",             MINE),
    ("allow",   "a target that is not a git repo at all",      "git -C ../plain add .",        MINE),
    ("deny",    "standing outside any repo, pushing into one", f"git -C {THEIRS} push",        _u),
]
for exp, label, cmd, cwd in UNREG:
    got, _ = run(cmd, cwd)
    ok = got == exp
    fails += 0 if ok else 1
    print(f"{'✓' if ok else '✗':2}{got:<8}{exp:<8}  {label}")

# --- the push refusal names what it would have published ---
# It used to say "look at git log @{u}..HEAD" and leave it there; the demo's caption said
# it showed the commits. Now it does, and says so honestly when git cannot tell.
print("\n-- push refusal lists the commits --")
_up = os.path.join(_u, "up.git")
subprocess.run(["git", "init", "-q", "--bare", _up], capture_output=True)
_g = ["git", "-C", THEIRS, "-c", "user.name=t", "-c", "user.email=t@t"]


def _reason(cwd, target):
    p = subprocess.run([sys.executable, HOOK], capture_output=True, text=True, timeout=10,
                       input=json.dumps({"tool_input": {"command": f"git -C {target} push"},
                                         "cwd": cwd}))
    try:
        return json.loads(p.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    except Exception:
        return ""


subprocess.run(_g + ["commit", "-q", "--allow-empty", "-m", "base"], capture_output=True)
no_upstream = _reason(MINE, THEIRS)
subprocess.run(_g + ["remote", "add", "origin", _up], capture_output=True)
subprocess.run(_g + ["push", "-q", "-u", "origin", "HEAD"], capture_output=True)
level = _reason(MINE, THEIRS)
for i in (1, 2, 3):
    subprocess.run(_g + ["commit", "-q", "--allow-empty", "-m", f"ahead {i}"], capture_output=True)
ahead = _reason(MINE, THEIRS)
for ok, label in [("could not say what is ahead" in no_upstream, "no upstream: says git cannot tell"),
                  ("Nothing is ahead" in level, "level with upstream: says nothing is ahead"),
                  ("It would publish 3 commit(s)" in ahead, "three ahead: counts them"),
                  (all(f"ahead {i}" in ahead for i in (1, 2, 3)), "and lists each one")]:
    fails += 0 if ok else 1
    print(f"{'✓' if ok else '✗':2}{'yes' if ok else 'no':<8}{'yes':<8}  {label}")

# fail-open cases: malformed input must never crash and never deny
print("\n-- fails open --")
for label, raw in [("empty stdin", ""), ("malformed JSON", "{{{"),
                   ("no tool_input", '{"cwd":"/tmp"}'),
                   ("command is null", '{"tool_input":{"command":null},"cwd":"/tmp"}'),
                   ("command is a number", '{"tool_input":{"command":123},"cwd":"/tmp"}'),
                   ("no cwd", '{"tool_input":{"command":"git -C %s commit -am x"}}' % HUB)]:
    got, err = run(None, raw=raw)
    ok = got == "allow"
    fails += 0 if ok else 1
    print(f"{'✓' if ok else '✗':2}{got:<8}{'allow':<8}  {label}" + (f"   [{err}]" if err else ""))

print(f"\n{'all checks passed' if not fails else str(fails) + ' failed'}")
sys.exit(1 if fails else 0)
