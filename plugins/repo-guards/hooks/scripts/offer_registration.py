#!/usr/bin/env python3
"""UserPromptSubmit hook: say so when this repo is not on the registry.

The failure it closes, in one line:

    Every track is opt-in per project, so a repo nobody registered loads NOTHING —
    and nothing says so.

There is a second way to load nothing, and it took longer to find because the repo IS
registered. Claude Code reads project settings from the session's own directory, not
from the git root — measured 2026-09-09 with `claude plugin list`, which resolves them
the same way:

    <project>/              five tracks + RepoGuards
    <project>/apps/mobile/  RepoGuards only
    <app>/Capacitor/        RepoGuards only

So a session opened one directory in — `<app>/fastlane`, `ios/`, `apps/mobile`, which
is exactly where release work happens — has no store track, no release track, nothing.
And this hook was SILENT there, deliberately: containment in either direction counted
as "the registry already has an answer for this tree". It has an answer about the root;
it has nothing to say about a session standing below it. That silence is now a second
notice.

That is the price of making the tracks per-project, and it is paid in the currency
RepoGuards' README warns about: `A file never stops you; a missing skill does,
and quietly.` A session in an unregistered repo does not fail. It just does the work
the long way, without the skill that was written for exactly it, and without ever
mentioning that a track was missing. There is no error to notice, so the notice has to
be made.

WHY NOT SessionStart, WHICH IS WHERE THIS OBVIOUSLY BELONGS. It ran there for three
rounds, correctly, and the owner never saw a word of it. The Claude desktop app does
not display SessionStart hook output at all — confirmed by the owner not seeing the
watch plugin's line either, which is the same event and the same shape. The output
reached the model and the transcript; it never reached the screen. UserPromptSubmit
fires when a message is sent, so there is a turn in which the model can actually
speak, and a person waiting for a reply.

It only ever REPORTS. It cannot enable a track — plugin enablement is read at
session start, before this ever runs — so it points at the register-project skill,
which is in RepoGuards, the plugin that loads everywhere.
That is why that plugin exists.

Noise is what kills a hook like this — but a seven-day cooldown killed it the other
way first. It fired in one repo at 19:22, and the session the owner actually opened at
20:04 got silence, because the repo had already been "offered" that week. For a repo
you are actively trying to register, once a week is indistinguishable from never.

So it is not silenced by time. It is silenced per SESSION — SessionStart re-fires on
resume, clear and compact, and repeating inside one conversation is pointless — and it
DE-ESCALATES per repo instead of going quiet. The first three times a repo comes up, the
notice asks the model to put the choice to the user as a question, because a question is
the thing that cannot be scrolled past. After that it is one line: still said, every
session, never again as an interruption.

That distinction is the whole of it. A cooldown makes the notice absent exactly when you
are working in the repo; asking a fourth time makes it wallpaper. Neither of those is
"stop asking after an answer" — and an answer is still what ends it: register the repo,
or list it under `ignored`. `REPO_GUARDS_OFFER=off`, or `"offer_registration": false` in the
registry, is the other answer, for someone whose machine holds a hundred repos that are
nobody's business.

Fails silent: any error reports nothing. A hook that crashes at the start of every
session is worse than no hook.
"""
import hashlib, json, os, subprocess, sys, time
# The guard ships inside RepoGuards and runs from the plugin cache, where
# nothing sits two directories above it. guards_repo finds the live repo.
from guards_repo import registry_path, projects, apps, resolve_root

HERE = os.path.dirname(os.path.abspath(__file__))
# Overridable so the pipeline can run against a throwaway registry and state dir. Testing
# this against the real registry would mean the test's verdict depends on which repos the
# owner happens to have registered today.
REGISTRY = registry_path()
STATE_DIR = os.environ.get("REPO_GUARDS_OFFER_STATE") or os.path.expanduser("~/.claude/.repo-guards/offered")
# How many sessions a repo is ASKED about before the notice becomes a single line. Not a
# silence and not a cooldown — see the module note.
ASK_LIMIT = 3


def real(p):
    return os.path.realpath(os.path.expanduser(p))


def repo_root(cwd):
    """The git top-level containing cwd, or None. A repo is the unit being registered."""
    try:
        p = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=5)
        return real(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else None
    except Exception:
        return None


def known_roots(reg):
    """(name, root, tracks) for every path the registry has an answer for.

    The tracks come along because the second notice needs to name what is missing, and
    because a root with none — RepoGuards itself — has nothing to warn about.

    `ignored` entries come back with tracks None: "never ask" is an answer about the
    whole tree, and it has to silence the subdirectory notice as well as the offer.
    isinstance rather than `or {}` because a wrong-typed section would raise, reach the
    fail-silent handler, and switch the notice off machine-wide — the same shape as the
    prose key that once switched off three guards.
    """
    out = []
    for name, proj in projects(reg):
        if proj.get("root"):
            out.append((name, resolve_root(proj["root"]), list(proj.get("tracks") or [])))
    for name, app in apps(reg):
        if app.get("repo"):
            out.append((name, resolve_root(app["repo"]), list(app.get("tracks") or [])))
    ignored = reg.get("ignored")
    if isinstance(ignored, dict):
        for name, ign in ignored.items():
            if not name.startswith("_") and isinstance(ign, dict) and ign.get("root"):
                out.append((name, resolve_root(ign["root"]), None))
    return out


def already_offered(root, session):
    """(seen, statefile) — has this repo already been offered IN THIS SESSION.

    Keyed on session + path, not on time. The previous version kept a seven-day
    cooldown and that is what silenced the notice in the one repo the owner was
    trying to register: it had been offered 42 minutes earlier, in a session that
    was already closed. A repo you are working in is exactly the repo you reopen.

    sha1 of the pair rather than hash(): Python randomises hash() per process, so a
    filename built from it would be new every run and would never suppress anything.
    """
    try:
        key = hashlib.sha1(f"{session}\n{root}".encode("utf-8")).hexdigest()[:16]
        f = os.path.join(STATE_DIR, key + ".json")
        if not os.path.exists(f):
            return False, f
        rec = json.load(open(f))
        return rec.get("root") == root and rec.get("session") == session, f
    except Exception:
        return False, None


def stamp(path, root, session):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        json.dump({"root": root, "session": session, "at": time.time()}, open(path, "w"))
        # one file per session per repo would otherwise accumulate forever
        cutoff = time.time() - 7 * 86400
        for f in os.listdir(STATE_DIR):
            fp = os.path.join(STATE_DIR, f)
            if f.endswith(".json") and os.path.getmtime(fp) < cutoff:
                os.remove(fp)
    except Exception:
        pass


def seen_count(path, bump):
    """How many sessions this place has already been offered in, and add one.

    Kept in a subdirectory of its own because the state beside it is swept after seven
    days: a per-session stamp is worthless once its session is over, and this is the
    opposite — one small file per place, the only memory that outlives the session. A
    counter that the cleanup ate would restart the questions every week.
    """
    d = os.path.join(STATE_DIR, "counts")
    try:
        key = hashlib.sha1(path.encode("utf-8")).hexdigest()[:16]
        f = os.path.join(d, key + ".json")
        try:
            n = int(json.load(open(f)).get("sessions") or 0)
        except Exception:
            n = 0
        if bump:
            os.makedirs(d, exist_ok=True)
            json.dump({"root": path, "sessions": n + 1, "at": time.time()}, open(f, "w"))
        return n
    except Exception:
        return 0                                      # unknown → ask; asking is the default


def switched_off(reg):
    if ((os.environ.get("REPO_GUARDS_OFFER") or os.environ.get("GROVE_OFFER")) or "").strip().lower() in ("off", "0", "false", "no"):
        return True
    return isinstance(reg, dict) and reg.get("offer_registration") is False


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    cwd = real(payload.get("cwd") or os.getcwd())
    root = repo_root(cwd)
    if not root:
        return                                        # not a git repo; nothing to register

    try:
        reg = json.load(open(REGISTRY, encoding="utf-8"))
    except Exception:
        return                                        # no registry, no opinion

    if switched_off(reg):
        return                                        # an answer, given once, for good

    # Against the cwd, not the git root: the cwd is where a settings file would take
    # effect, and it is what the registry records.
    knowns = known_roots(reg)

    # Registered AT this path, or the registered root is BELOW us. A measured case of
    # the second: a root registered at `<repo>/web` while the git top-level is `<repo>`
    # — and offering to register the tree above it would be asking about something the
    # registry has already answered.
    for _, kroot, _ in knowns:
        if cwd == kroot or kroot.startswith(cwd + os.sep):
            return

    session = str(payload.get("session_id") or "unknown")

    # Inside a registered root but not AT it. Deepest match wins, so a registered
    # subdirectory of a registered repo is described by its own entry.
    for name, kroot, tracks in sorted(knowns, key=lambda t: -len(t[1])):
        if not cwd.startswith(kroot + os.sep):
            continue
        if not tracks:
            return                                    # ignored, or a root with no tracks
        seen, statef = already_offered(cwd, session)
        if seen:
            return
        if statef:
            stamp(statef, cwd, session)
        asked = seen_count(cwd, bump=True)
        if asked >= ASK_LIMIT:
            print(
                f"[repo-guards] Still a subdirectory of '{name}' — none of that repo's tracks "
                f"({', '.join(tracks)}) load here, because settings are read from the "
                f"session's own directory. Reopen at {kroot}, or register this directory "
                f"with the register-project skill. Said once per session; no answer needed."
            )
            return
        print(
            f"[repo-guards] This session is in a SUBDIRECTORY of '{name}' ({kroot}). Claude Code "
            f"reads project settings from the session's own directory, so NONE of that repo's "
            f"tracks are loaded here — missing: {', '.join(tracks)}. Only the always-on "
            f"RepoGuards is loaded.\n"
            f"BEFORE answering the user's message, ask them with AskUserQuestion: header "
            f"\"Directory\", options \"Reopen at the repo root\" (the tracks load there; this "
            f"session cannot load them, plugins are read at startup), \"Register this "
            f"directory\" (run the register-project skill on this cwd so the tracks load here "
            f"from the next session), \"Not now\". Then answer their message. Ask once per "
            f"session; change nothing before they choose."
        )
        return

    seen, statef = already_offered(cwd, session)
    if seen:
        return
    if statef:
        stamp(statef, cwd, session)

    where = root if root == cwd else f"{cwd} (git repo: {root})"

    # Asked three times, never answered: keep saying it, stop interrupting for it. The
    # line stays because the failure it names is permanent and silent — no track loads
    # here — and a notice that disappears is indistinguishable from a problem that did.
    if seen_count(cwd, bump=True) >= ASK_LIMIT:
        print(
            f"[repo-guards] Not on the registry: {where} — no track is enabled here. "
            f"The register-project skill puts it on; `ignored` in the registry stops this "
            f"line for good, and `REPO_GUARDS_OFFER=off` stops it everywhere. No answer needed."
        )
        return

    # Plain stdout: on UserPromptSubmit it is added to the turn's context. The
    # documented hookSpecificOutput JSON was tried on SessionStart and silently
    # discarded by this host, so nothing here relies on it.
    #
    # SHORT AND IMPERATIVE, deliberately. The first version was three sentences of
    # explanation and the model reasonably got on with the user's actual request
    # instead. What has to survive is one instruction.
    print(
        f"[repo-guards] This repo is not on the registry: {where} — so no track is "
        f"enabled here, and nothing said so.\n"
        f"BEFORE answering the user's message, ask them about it with AskUserQuestion: "
        f"header \"Registry\", options \"Register it\" (run the register-project "
        f"skill), \"Never ask again\" (add it to `ignored` in the registry), \"Not "
        f"now\". Then answer their message. Ask once per session; register or exclude "
        f"nothing before they choose."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass                                          # fail silent, always
