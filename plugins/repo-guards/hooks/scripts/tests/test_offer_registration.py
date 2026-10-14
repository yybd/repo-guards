"""Branch pipeline for offer_registration.py (UserPromptSubmit).

The project rule (CLAUDE.md, "The guard") says a guard is run across all its branches
before it takes effect, and install.py enforces that by refusing to register a hook
whose pipeline fails. This is that pipeline.

    python3 tools/hooks/tests/test_offer_registration.py

Everything is throwaway: its own git repos, its own registry, its own state dir. It
never reads the real registry — a test whose verdict depends on which repos the owner
happened to register today is not a test — and never writes under ~/.claude.

The two branches worth the most here are the silent ones. A hook that speaks when it
should not is the failure that gets hooks uninstalled.

The suppression branches earn their own group. This hook shipped with a seven-day
cooldown and it silenced the notice in the one repo the owner was actively trying to
register — offered at 19:22, silent for the session opened at 20:04. Suppression is
per SESSION now: repeat within one conversation is pointless, repeat across sessions
is the whole point, and what ends it for good is an answer in the registry.

Exits non-zero on any failure.
"""
import json, os, shutil, subprocess, sys, tempfile

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "offer_registration.py")


def git_repo(path):
    os.makedirs(path, exist_ok=True)
    subprocess.run(["git", "-C", path, "init", "-q"], capture_output=True)
    return os.path.realpath(path)


def run(env, cwd, payload=None, raw=None):
    """(text, error). '' text means the hook stayed silent — the common right answer.

    Plain stdout, deliberately, and the pipeline asserts it: the JSON form this hook
    shipped with twice was accepted by the host and then discarded, so nothing reached
    the screen, the transcript or the model. A structured-output assertion would have
    passed for both of those versions.
    """
    body = raw if raw is not None else json.dumps(payload or {"cwd": cwd,
                                                             "hook_event_name": "SessionStart"})
    p = subprocess.run([sys.executable, HOOK], input=body,
                       capture_output=True, text=True, timeout=30, env=env)
    if p.returncode != 0:
        return "CRASH", (p.stderr.strip() or "nonzero exit")[:160]
    out = p.stdout.strip()
    if out.startswith("{"):
        return "JSON", "structured output is silently dropped by the host — print plain text"
    return out, ""


def main():
    base = tempfile.mkdtemp(prefix="repo-guards-offer-test-")
    fails = 0

    def check(ok, label, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"{'✓' if ok else '✗'} {label}" + (f"   [{detail}]" if detail and not ok else ""))

    try:
        known_proj = git_repo(os.path.join(base, "known-project"))
        known_app = git_repo(os.path.join(base, "known-app"))
        excluded = git_repo(os.path.join(base, "excluded"))
        stranger = git_repo(os.path.join(base, "stranger"))
        plain = os.path.join(base, "not-a-repo")
        os.makedirs(plain, exist_ok=True)
        nested = os.path.join(known_proj, "src", "deep")
        os.makedirs(nested, exist_ok=True)
        app_nested = os.path.join(known_app, "fastlane")
        os.makedirs(app_nested, exist_ok=True)
        # a registered root that loads nothing anyway — RepoGuards' own case
        trackless = git_repo(os.path.join(base, "trackless"))
        trackless_sub = os.path.join(trackless, "plugins")
        os.makedirs(trackless_sub, exist_ok=True)
        excluded_sub = os.path.join(excluded, "deep")
        os.makedirs(excluded_sub, exist_ok=True)

        # one git repo, one registered subdirectory inside it, one unregistered sibling
        monorepo = git_repo(os.path.join(base, "monorepo"))
        sub_registered = os.path.join(monorepo, "web")
        sibling = os.path.join(monorepo, "other")
        os.makedirs(sub_registered, exist_ok=True)
        os.makedirs(sibling, exist_ok=True)

        registry = os.path.join(base, "registry.json")
        json.dump({
            "projects": {"known-project": {"root": known_proj, "tracks": ["web-track"]},
                         "sub-registered": {"root": sub_registered, "tracks": ["web-track"]},
                         "trackless": {"root": trackless, "tracks": []},
                         "_comment": "entries starting with _ are prose, not projects"},
            "apps": {"known-app": {"repo": known_app, "tracks": ["apple-track"]},
                     "no-repo-yet": {"repo": None}},
            "ignored": {"excluded": {"root": excluded, "why": "someone else's clone"}},
        }, open(registry, "w"))

        def env(state="state", reg=None):
            e = dict(os.environ)
            e["REPO_GUARDS_REGISTRY"] = reg or registry
            e["REPO_GUARDS_OFFER_STATE"] = os.path.join(base, state)
            return e

        # --- the silent branches: speaking here is the failure that gets it uninstalled
        msg, err = run(env("s-proj"), known_proj)
        check(msg == "", "registered project — silent", err or msg[:70])

        # This asserted silence until 2026-09-09, and the silence was the bug: project
        # settings resolve against the cwd, so a session one directory in loads none of
        # the repo's tracks. Verified against `claude plugin list`, which resolves them
        # the same way: a nested app directory had RepoGuards and nothing else.
        msg, err = run(env("s-nested"), nested)
        check(msg != "" and "SUBDIRECTORY" in msg and known_proj in msg,
              "subdirectory of a registered project — says the tracks are not loaded",
              err or msg[:70])
        check("web-track" in msg, "…and names what is missing", err or msg[:70])
        check("Register this directory" in msg and "Reopen at the repo root" in msg,
              "…and offers both ways out", err or msg[:70])

        msg, err = run(env("s-appnested"), app_nested)
        check(msg != "" and "apple-track" in msg,
              "subdirectory of a registered APP — same notice", err or msg[:70])

        msg, err = run(env("s-trackless"), trackless_sub)
        check(msg == "", "subdirectory of a root with no tracks — silent, nothing is lost",
              err or msg[:70])

        msg, err = run(env("s-ignsub"), excluded_sub)
        check(msg == "", "subdirectory of an ignored repo — silent", err or msg[:70])

        msg, err = run(env("s-app"), known_app)
        check(msg == "", "registered app — silent", err or msg[:70])

        msg, err = run(env("s-ign"), excluded)
        check(msg == "", "deliberately ignored repo — silent", err or msg[:70])

        msg, err = run(env("s-plain"), plain)
        check(msg == "", "not a git repo — silent", err or msg[:70])

        # A registered root that is a SUBDIRECTORY of its git repo — how one measured root is
        # actually registered, because projectSettings resolve against cwd, not the git
        # root. Both directions of containment must silence the offer.
        msg, err = run(env("s-sub"), sub_registered)
        check(msg == "", "registered dir inside a bigger repo — silent", err or msg[:70])

        msg, err = run(env("s-parent"), monorepo)
        check(msg == "", "repo root containing a registered dir — silent", err or msg[:70])

        msg, err = run(env("s-sibling"), sibling)
        check(msg != "" and sibling in msg,
              "sibling of a registered dir, same repo — speaks about the cwd", err or msg[:70])

        # --- the one branch that speaks
        msg, err = run(env("s-new"), stranger)
        check(stranger in msg and "register-project" in msg,
              "unregistered repo — names the repo and the skill", err or msg[:70])
        check("AskUserQuestion" in msg,
              "the notice asks rather than announces", msg[:70])
        for opt in ("Register it", "Never ask again", "Not now"):
            check(opt in msg, f'…and offers "{opt}"', msg[:70])
        check("register or exclude\nnothing" in msg or "register or exclude" in msg,
              "…while still forbidding it to act unasked", msg[:70])
        # It rides on the user's message now, so it must not swallow the turn.
        check("Then answer their message" in msg,
              "…and hands the turn back to what the user actually asked", msg[:70])
        check(not msg.startswith("{"),
              "plain text, not JSON — this host drops structured hook output", msg[:70])

        # --- suppression is per session, not per week
        msg, err = run(env("s-sess"), stranger, payload={"cwd": stranger, "session_id": "A"})
        check(msg != "", "first time in a session speaks", err)
        msg2, err = run(env("s-sess"), stranger, payload={"cwd": stranger, "session_id": "A"})
        check(msg2 == "", "same session again (resume/compact) — silent", err or msg2[:70])
        msg3, err = run(env("s-sess"), stranger, payload={"cwd": stranger, "session_id": "B"})
        check(msg3 != "", "a NEW session speaks again — the week-long cooldown is gone",
              err)
        msg4, err = run(env("s-sess"), stranger, payload={"cwd": known_proj, "session_id": "B"})
        check(msg4 == "", "same session, a registered repo — still silent", err or msg4[:70])

        # --- fail-open: it must never be the reason a session cannot start
        msg, err = run(env("s-noreg", reg=os.path.join(base, "missing.json")), stranger)
        check(msg == "", "missing registry — silent, not a crash", err or msg[:70])

        bad = os.path.join(base, "bad.json")
        open(bad, "w").write("{not json")
        msg, err = run(env("s-badreg", reg=bad), stranger)
        check(msg == "", "unparseable registry — silent, not a crash", err or msg[:70])

        junk = os.path.join(base, "junk.json")
        json.dump({"projects": "not-a-dict", "apps": None, "ignored": [1, 2]}, open(junk, "w"))
        msg, err = run(env("s-junk", reg=junk), stranger)
        check(msg != "CRASH", "registry with wrong-typed sections — no crash", err)

        msg, err = run(env("s-raw"), stranger, raw="not json at all")
        check(msg == "", "malformed stdin — silent, exit 0", err or msg[:70])

        msg, err = run(env("s-empty"), stranger, raw="{}")
        check(msg != "CRASH", "payload with no cwd — no crash", err)

        # --- asked three times, then it stops interrupting ------------------------------
        # A cooldown made it absent exactly when the repo was being worked on. Going quiet is
        # the failure; asking for a dialog forever is the other one. So: three sessions with
        # a question, then one line, every session, for good.
        print("\n-- it de-escalates rather than going quiet --")
        fresh = git_repo(os.path.join(base, "asked-often"))
        e = env("s-escalate")
        seen = []
        for n in range(1, 6):
            msg, err = run(e, fresh, payload={"cwd": fresh, "session_id": "sess-%d" % n})
            seen.append(msg if not err else "ERR " + err)
        for n in (1, 2, 3):
            check("AskUserQuestion" in seen[n - 1], "session %d asks the question" % n,
                  seen[n - 1][:70])
        for n in (4, 5):
            check(seen[n - 1] != "" and "AskUserQuestion" not in seen[n - 1],
                  "session %d still speaks, and no longer interrupts" % n, seen[n - 1][:70])
        check("REPO_GUARDS_OFFER=off" in seen[4], "and it names the way to end it", seen[4][:70])

        # the two answers that end it for good
        msg, _ = run(dict(env("s-off"), REPO_GUARDS_OFFER="off"), fresh,
                     payload={"cwd": fresh, "session_id": "sess-off"})
        check(msg == "", "REPO_GUARDS_OFFER=off silences it entirely", msg[:70])

        reg_off = os.path.join(base, "registry-off.json")
        json.dump({"projects": {}, "offer_registration": False}, open(reg_off, "w"))
        msg, _ = run(env("s-regoff", reg=reg_off), fresh,
                     payload={"cwd": fresh, "session_id": "sess-regoff"})
        check(msg == "", "and so does `offer_registration: false` in the registry", msg[:70])

    finally:
        shutil.rmtree(base, ignore_errors=True)

    print(f"\n{'FAIL' if fails else 'OK'}: {fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
