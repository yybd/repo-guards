"""Branch pipeline for warn_stale_plugin_cache.py.

The project rule (CLAUDE.md, "the guard") says a guard must fail safe and that every
change is run across all its branches before it takes effect. This is that pipeline.

    python3 tools/hooks/tests/test_warn_stale_plugin_cache.py

Builds a throwaway repo, a throwaway install registry and a throwaway cache, so it
never touches ~/.claude or the machine's real plugins — breaking the real install to
watch this fire is exactly what the hook exists to prevent. Exits non-zero on any
failure.
"""
import json, os, shutil, subprocess, sys, tempfile

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "warn_stale_plugin_cache.py")


def git(repo, *a):
    return subprocess.run(["git", "-C", repo] + list(a), capture_output=True, text=True)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(text)


def make_track(root, name, skills):
    write(os.path.join(root, ".claude-plugin", "plugin.json"),
          json.dumps({"name": name, "description": name}))
    for s, body in skills.items():
        write(os.path.join(root, "skills", s, "SKILL.md"), body)


def run(env, sid="s1", cwd=None, active=False):
    """(message, error). '' message means the hook stayed silent."""
    payload = {"session_id": sid, "stop_hook_active": active}
    if cwd:
        payload["cwd"] = cwd
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=30, env=env)
    if p.returncode != 0:
        return "CRASH", (p.stderr.strip() or "nonzero exit")[:160]
    out = p.stdout.strip()
    if not out:
        return "", ""
    try:
        return json.loads(out).get("systemMessage", ""), ""
    except Exception as e:
        return "BADJSON", str(e)[:120]


def main():
    base = tempfile.mkdtemp(prefix="grove-stale-test-")
    fails = 0

    def check(ok, label, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"{'✓' if ok else '✗'} {label}" + (f"   [{detail}]" if detail and not ok else ""))

    try:
        # ---- throwaway world -------------------------------------------------
        repo = os.path.join(base, "repo")
        os.makedirs(repo)
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "t@t"); git(repo, "config", "user.name", "t")
        write(os.path.join(repo, ".claude-plugin", "marketplace.json"), json.dumps({
            "name": "grove", "plugins": [
                {"name": "alpha", "source": "./plugins/alpha"},
                {"name": "beta", "source": "./plugins/beta"}]}))
        make_track(os.path.join(repo, "plugins", "alpha"), "alpha", {"a1": "one\n"})
        make_track(os.path.join(repo, "plugins", "beta"), "beta", {"b1": "one\n"})
        write(os.path.join(repo, "rules", "global-CLAUDE.md"), "rules\n")
        git(repo, "add", "."); git(repo, "commit", "-qm", "seed")
        HEAD = git(repo, "rev-parse", "HEAD").stdout.strip()

        cache = os.path.join(base, "cache")
        installed = os.path.join(base, "installed_plugins.json")
        state = os.path.join(base, "state")
        link = os.path.join(base, "CLAUDE.md")
        os.symlink(os.path.join(repo, "rules", "global-CLAUDE.md"), link)

        def install(name, version=HEAD[:12]):
            """Copy the track into the throwaway cache, as a real install would."""
            dst = os.path.join(cache, name, version)
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(os.path.join(repo, "plugins", name), dst)
            os.makedirs(os.path.join(dst, ".in_use"), exist_ok=True)
            open(os.path.join(dst, ".in_use", "999"), "w").write("{}")
            return dst

        def registry(entries):
            json.dump({"version": 2, "plugins": {
                f"{n}@grove": [{"scope": "user", "installPath": p, "version": v}]
                for n, (p, v) in entries.items()}}, open(installed, "w"))

        env = dict(os.environ, GROVE_REPO=repo, GROVE_INSTALLED_PLUGINS=installed,
                   GROVE_USER_CLAUDE_MD=link, GROVE_STALE_STATE=state,
                   GROVE_MARKETPLACE="grove")

        a = install("alpha"); b = install("beta")
        registry({"alpha": (a, HEAD[:12]), "beta": (b, HEAD[:12])})

        # ---- in sync ---------------------------------------------------------
        msg, err = run(env, cwd=repo)
        check(msg == "", "everything in sync → silent", err or msg[:80])
        check(".in_use" not in msg, ".in_use in the copy is not a difference", msg[:80])

        # noise that must not count as a difference
        os.makedirs(os.path.join(a, "__pycache__"), exist_ok=True)
        open(os.path.join(a, "__pycache__", "x.pyc"), "w").write("junk")
        open(os.path.join(a, ".DS_Store"), "w").write("junk")
        msg, err = run(env, sid="noise", cwd=repo)
        check(msg == "", "__pycache__ and .DS_Store are not differences", err or msg[:80])

        # ---- a skill added in the repo and never installed --------------------
        write(os.path.join(repo, "plugins", "alpha", "skills", "a2", "SKILL.md"), "two\n")
        msg, err = run(env, sid="s2", cwd=repo)
        check("alpha" in msg and "missing from the copy" in msg,
              "a new skill in the repo → reports alpha", err or msg[:120])
        check("beta" not in msg, "the clean beta is not mentioned", msg[:120])

        # SHA still equals HEAD, so `update` would be a no-op — advise reinstall
        check("no-op" in msg and "uninstall" in msg,
              "SHA==HEAD → recommends reinstall, not update", msg[:160])

        # ---- latch -----------------------------------------------------------
        msg2, _ = run(env, sid="s2", cwd=repo)
        check(msg2 == "", "the same finding again in the same session → silent", msg2[:80])
        msg3, _ = run(env, sid="other", cwd=repo)
        check("alpha" in msg3, "another session does hear the finding", msg3[:80])

        # a NEW finding in the same session must break the latch
        write(os.path.join(repo, "plugins", "beta", "skills", "b2", "SKILL.md"), "two\n")
        msg4, _ = run(env, sid="s2", cwd=repo)
        check("beta" in msg4 and "alpha" in msg4,
              "another finding in the same session → speaks again", msg4[:120])

        # ---- committed drift advises update, not reinstall --------------------
        git(repo, "add", "."); git(repo, "commit", "-qm", "add skills")
        msg, err = run(env, sid="s3", cwd=repo)
        check("claude plugin update" in msg and "no-op" not in msg,
              "the SHA trails HEAD → recommends update", err or msg[:160])

        # ---- back in sync ----------------------------------------------------
        NEW = git(repo, "rev-parse", "HEAD").stdout.strip()
        a = install("alpha", NEW[:12]); b = install("beta", NEW[:12])
        registry({"alpha": (a, NEW[:12]), "beta": (b, NEW[:12])})
        msg, err = run(env, sid="s4", cwd=repo)
        check(msg == "", "after a reinstall → silent", err or msg[:120])

        # ---- a track that was never installed --------------------------------
        registry({"alpha": (a, NEW[:12])})
        msg, _ = run(env, sid="s5", cwd=repo)
        check("beta" in msg and "not installed" in msg,
              "a track never installed → reports install", msg[:140])

        # ---- installed copy deleted from disk --------------------------------
        registry({"alpha": (a, NEW[:12]), "beta": (os.path.join(cache, "beta", "ghost"), NEW[:12])})
        msg, _ = run(env, sid="s6", cwd=repo)
        check("missing from disk" in msg, "a copy deleted from disk → reported", msg[:140])

        registry({"alpha": (a, NEW[:12]), "beta": (b, NEW[:12])})

        # ---- the rules symlink -----------------------------------------------
        msg, _ = run(env, sid="s7", cwd=repo)
        check(msg == "", "a correct symlink → silent about the rules", msg[:120])

        os.unlink(link)
        msg, _ = run(env, sid="s8", cwd=repo)
        check("reaches no session" in msg, "a missing symlink → reported", msg[:140])

        os.symlink(os.path.join(repo, "rules"), link)          # points at the wrong thing
        msg, _ = run(env, sid="s9", cwd=repo)
        check("does not resolve" in msg, "a symlink pointing elsewhere → reported", msg[:140])
        os.unlink(link)

        # a file of one's own that imports the rules is the other correct shape
        write(link, "@" + os.path.join(repo, "rules", "global-CLAUDE.md") + "\n\nmine\n")
        msg, _ = run(env, sid="s9a", cwd=repo)
        check(msg == "", "an own CLAUDE.md importing the rules → silent", msg[:120])
        write(link, "mine, and no import\n")
        msg, _ = run(env, sid="s9b", cwd=repo)
        check("does not resolve" in msg, "an own CLAUDE.md without the import → reported", msg[:140])
        os.unlink(link)
        os.symlink(os.path.join(repo, "rules", "global-CLAUDE.md"), link)

        # a broken link must not be reported as a plugin problem
        msg, _ = run(env, sid="s10", cwd=repo)
        check(msg == "", "after the link is fixed → silent", msg[:120])

        # ---- scope: it runs everywhere, it speaks only here --------------------
        outside = os.path.join(base, "elsewhere")
        os.makedirs(outside)
        write(os.path.join(repo, "plugins", "alpha", "skills", "a3", "SKILL.md"), "three\n")
        msg, _ = run(env, sid="s11", cwd=outside)
        check(msg == "", "cwd outside grove → silent despite a real gap", msg[:120])
        msg, _ = run(env, sid="s11", cwd=os.path.join(repo, "plugins", "alpha"))
        check("alpha" in msg, "cwd in a subdirectory of grove → speaks", msg[:120])

        msg, _ = run(env, sid="s12")
        check(msg == "", "no cwd → silent", msg[:120])
        msg, _ = run(env, sid="s13", cwd=repo, active=True)
        check(msg == "", "stop_hook_active → silent", msg[:120])

        # ---- fail-safe on every malformed input -------------------------------
        open(installed, "w").write("{ not json")
        msg, err = run(env, sid="s14", cwd=repo)
        check(msg == "", "malformed installed_plugins.json → silent, not a crash", err or msg[:120])

        registry({"alpha": (a, NEW[:12]), "beta": (b, NEW[:12])})
        write(os.path.join(repo, ".claude-plugin", "marketplace.json"), "{ not json")
        msg, err = run(env, sid="s15", cwd=repo)
        check(msg == "", "malformed marketplace.json → silent, not a crash", err or msg[:120])

        write(os.path.join(repo, ".claude-plugin", "marketplace.json"), json.dumps({
            "name": "grove", "plugins": [
                {"name": "alpha", "source": "./plugins/alpha"},
                {"name": "beta", "source": "./plugins/beta"}]}))
        os.remove(installed)
        msg, err = run(env, sid="s16", cwd=repo)
        # Not silence. A file that is not there is not the same as a file that cannot be
        # read: the first means nothing is installed, which is the state of a machine
        # that has just cloned this, and the answer it needs is `install`. Silence there
        # let deploy.py report "nothing to deploy" on a machine with nothing installed.
        check("not installed" in msg and "plugin install" in msg,
              "no installed_plugins.json at all → nothing is installed, and it says so",
              err or msg[:120])

        # and the same, proven against a manifest that IS readable
        json.dump({"version": 2, "plugins": "not-a-dict"}, open(installed, "w"))
        msg, err = run(env, sid="s16b", cwd=repo)
        check(msg == "", "an unexpected registration shape → silent", err or msg[:120])

        env_noenv = dict(os.environ, GROVE_REPO=os.path.join(base, "nope"),
                         GROVE_INSTALLED_PLUGINS=installed, GROVE_USER_CLAUDE_MD=link,
                         GROVE_STALE_STATE=state)
        msg, err = run(env_noenv, sid="s17", cwd=repo)
        check(msg == "", "a REPO that does not exist → silent", err or msg[:120])

        p = subprocess.run([sys.executable, HOOK], input="not json at all",
                           capture_output=True, text=True, timeout=15, env=env)
        check(p.returncode == 0 and p.stdout.strip() == "",
              "stdin that is not JSON → exit 0 and no output", f"rc={p.returncode}")

    finally:
        shutil.rmtree(base, ignore_errors=True)

    print(f"\n{'PASS' if fails == 0 else str(fails) + ' FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
