"""Branch pipeline for warn_uncommitted_roots.py.

The project rule (CLAUDE.md, "the guard") says a guard must fail safe and that every
change is run across all branches before it takes effect. This is that pipeline.

    python3 tools/hooks/tests/test_warn_uncommitted_roots.py

Builds throwaway git repos and a throwaway registry, so it never touches app-hub,
a real project or grove itself — dirtying a real repo to watch the hook fire is
precisely what the hook exists to complain about. Exits non-zero on any failure.
"""
import json, os, shutil, subprocess, sys, tempfile

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "warn_uncommitted_roots.py")


def git(repo, *a):
    subprocess.run(["git", "-C", repo] + list(a), capture_output=True, text=True)


def make_repo(base, name):
    r = os.path.join(base, name)
    os.makedirs(r)
    git(r, "init", "-q")
    git(r, "config", "user.email", "t@t"); git(r, "config", "user.name", "t")
    open(os.path.join(r, "seed.txt"), "w").write("seed\n")
    git(r, "add", "."); git(r, "commit", "-qm", "seed")
    return r


def run(env, sid="s1", cwd=None, active=False):
    payload = {"session_id": sid, "stop_hook_active": active}
    if cwd:
        payload["cwd"] = cwd
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=15, env=env)
    if p.returncode != 0:
        return "CRASH", p.stderr.strip()[:120]
    out = p.stdout.strip()
    if not out:
        return "", ""
    try:
        return json.loads(out).get("systemMessage", ""), ""
    except Exception as e:
        return "BADJSON", str(e)[:80]


def main():
    base = tempfile.mkdtemp(prefix="grove-stop-test-")
    fails = 0

    def check(ok, label, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"{'✓' if ok else '✗'} {label}" + (f"   [{detail}]" if detail and not ok else ""))

    try:
        alpha = make_repo(base, "alpha")
        beta = make_repo(base, "beta")
        # An APP entry: under `apps`, path keyed `repo`. The guard read `projects` only,
        # so all six app repos were unwatched — the blind spot it exists to close.
        gamma = make_repo(base, "gamma")
        # A root registered as a SUBDIRECTORY of its repo, which is how one measured root is
        # registered. There is no .git at that path, and testing for one skipped it.
        subdir = os.path.join(alpha, "web")
        os.makedirs(subdir, exist_ok=True)
        reg = os.path.join(base, "registry.json")
        json.dump({"projects": {"alpha": {"root": alpha}, "beta": {"root": beta}},
                   "apps": {"gamma": {"repo": gamma}}}, open(reg, "w"))
        state = os.path.join(base, "state")
        env = dict(os.environ, GROVE_REGISTRY=reg, GROVE_STOP_STATE=state)

        # everything clean, first run -> silent
        msg, err = run(env)
        check(msg == "", "entirely clean, first run → silent", err or msg[:60])

        # pre-existing dirt, NEW session -> named once as pre-existing
        open(os.path.join(alpha, "preexisting.txt"), "w").write("x\n")
        msg, err = run(env, sid="s2", cwd=alpha)
        check("ALREADY uncommitted" in msg and "alpha" in msg,
              "existing dirt, a new session inside the registry → reported once", err or msg[:60])

        # the same first run from a project outside the registry must stay silent:
        # pre-existing dirt in grove's repos is noise there
        msg, err = run(env, sid="s-outside", cwd=os.path.join(base, "unrelated"))
        check(msg == "", "the same dirt, a session in a foreign project → silent", err or msg[:80])

        # same session, nothing new -> silent (the anti-noise property)
        msg, err = run(env, sid="s2", cwd=alpha)
        check(msg == "", "the same session, nothing new → silent", err or msg[:80])

        # same session, a NEW file -> reported as this session's
        open(os.path.join(alpha, "mine.txt"), "w").write("y\n")
        msg, err = run(env, sid="s2", cwd=alpha)
        check("THIS" in msg and "mine.txt" in msg and "preexisting.txt" not in msg,
              "a new file → reported as the session's, without the pre-existing", err or msg[:80])

        # a second repo dirtied too -> both named
        open(os.path.join(beta, "other.txt"), "w").write("z\n")
        msg, err = run(env, sid="s2", cwd=alpha)
        check("beta" in msg, "a second dirtied repo → reported as well", err or msg[:80])

        # an APP repo dirtied -> named exactly like a project
        open(os.path.join(gamma, "app.txt"), "w").write("g\n")
        msg, err = run(env, sid="s2", cwd=alpha)
        check("gamma" in msg and "app.txt" in msg,
              "a dirtied app repo → reported like any root", err or msg[:80])

        # committing it clears the report
        git(alpha, "add", "."); git(alpha, "commit", "-qm", "done")
        git(beta, "add", "."); git(beta, "commit", "-qm", "done")
        git(gamma, "add", "."); git(gamma, "commit", "-qm", "done")
        msg, err = run(env, sid="s2", cwd=alpha)
        check(msg == "", "after a commit → silent", err or msg[:80])

        # cwd marking
        open(os.path.join(alpha, "again.txt"), "w").write("q\n")
        msg, err = run(env, sid="s2", cwd=alpha)
        check("own cwd" in msg, "marks the repo the session stands in", err or msg[:80])

        # stop_hook_active -> never re-fires
        msg, err = run(env, sid="s2", cwd=alpha, active=True)
        check(msg == "", "stop_hook_active → does not fire again", err or msg[:80])

        # a root that is a SUBDIRECTORY of its repo -> watched, and scoped to itself
        # Tracked first: git collapses an untracked directory to `?? web/`, which would
        # make this pass on the directory name alone and say nothing about scoping.
        open(os.path.join(subdir, "inside.txt"), "w").write("w\n")
        git(alpha, "add", "."); git(alpha, "commit", "-qm", "web seed")
        json.dump({"projects": {"web": {"root": subdir}}}, open(reg, "w"))
        run(env, sid="s4", cwd=subdir)                     # baseline turn
        open(os.path.join(subdir, "inside.txt"), "w").write("changed\n")
        open(os.path.join(alpha, "outside.txt"), "w").write("o\n")
        msg, err = run(env, sid="s4", cwd=subdir)
        check("web/inside.txt" in msg, "a root that is a subdirectory of a repo → watched", err or msg[:90])
        check("outside.txt" not in msg,
              "and reports only the registered subtree, not the whole repo", err or msg[:90])

        # A registered directory INSIDE an already-registered repo — an app's Capacitor/
        # subtree and a project's apps/mobile, registered 2026-09-09 so their tracks load
        # where release work stands. git has one answer for both roots, so this must
        # report the repo ONCE, not once per registry name.
        nestdir = os.path.join(beta, "Capacitor")
        os.makedirs(nestdir, exist_ok=True)
        open(os.path.join(nestdir, "n.txt"), "w").write("n\n")
        git(beta, "add", "."); git(beta, "commit", "-qm", "nested seed")
        json.dump({"projects": {"beta": {"root": beta},
                                "beta-capacitor": {"root": nestdir}}}, open(reg, "w"))
        run(env, sid="s5", cwd=beta)                       # baseline turn
        open(os.path.join(nestdir, "n.txt"), "w").write("changed\n")
        msg, err = run(env, sid="s5", cwd=beta)
        check(msg.count("Capacitor/n.txt") == 1,
              "a nested root — the file is reported once, not twice", err or msg[:110])
        check("beta-capacitor" not in msg,
              "…and by the repo's name, not the inner entry's", err or msg[:110])

        # a registry root that is not a git repo at all -> skipped, no crash. And a
        # directory that EXISTS but is not a repository: one registered entry was exactly that,
        # and it must be dropped rather than recorded as clean.
        notrepo = os.path.join(base, "notrepo")
        os.makedirs(notrepo, exist_ok=True)
        json.dump({"projects": {"alpha": {"root": alpha},
                                "ghost": {"root": os.path.join(base, "nope")},
                                "notrepo": {"root": notrepo}}}, open(reg, "w"))
        msg, err = run(env, sid="s3", cwd=alpha)
        check(err == "" and "ghost" not in msg, "a root that is not a repo → skipped without a crash", err)
        check("notrepo" not in msg, "an existing directory that is not a repo → skipped", err or msg[:80])

        # --- fail-silent on malformed input ---
        print("\n-- fails silent --")
        for label, raw, e in [
            ("empty stdin", "", env),
            ("malformed JSON", "{{{", env),
            ("no session_id", '{"cwd":"/tmp"}', env),
            ("a missing registry", "{}", dict(env, GROVE_REGISTRY="/nonexistent/r.json")),
            ("a malformed registry", "{}", dict(env, GROVE_REGISTRY=__file__)),
            ("an unwritable state dir", "{}", dict(env, GROVE_STOP_STATE="/proc/nope/x")),
        ]:
            p = subprocess.run([sys.executable, HOOK], input=raw, capture_output=True,
                               text=True, timeout=15, env=e)
            ok = p.returncode == 0
            check(ok, label, p.stderr.strip()[:100])
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print(f"\n{'all checks passed' if not fails else str(fails) + ' failed'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
