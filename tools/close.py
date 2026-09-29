#!/usr/bin/env python3
"""Bring every place this session touched to a closed state — and say what is still open.

The problem this answers, in one line: a session that writes in several places sees
ONE of them. `git status` is scoped to the directory the session stands in, so work
left anywhere else is invisible — not missing, invisible — and the session reports
"done" over a clean status while the rest sits open.

    python3 tools/close.py            report only; change nothing
    python3 tools/close.py --commit   also commit, in each place, its own paths

**Re-runnable by construction, and that is the whole design.** There is no commit
across repositories and no shared rollback, so three places are three operations and
any of them can be the one that does not happen — the turn ends, the user stops, a
hook refuses, the network drops. A command that says "do all three or none" cannot be
built. This one says "bring all three to a closed state" instead: every run recomputes
what is still open and continues from there, which turns an interruption from a
permanent silent half-change into an intermediate state that the next run closes.
a sibling project's deploy script already solves the same shape for eight publishes; this is that,
on commits.

**Three states, not two.** A place is dirty, then committed, then PUSHED — and for
some places there is a fourth, published, which no commit implies. So the report
carries all of them rather than stopping at "committed", because "committed" is where
the twelve-hour wrong price looked finished.

**It commits. It does not push and does not publish.** Those two are the irreversible
and the expensive one — a push publishes a whole branch, and a deployment costs money
and has run a quota to zero here before. What it does instead is the part that is
actually hard and that a person cannot do from memory: compute exactly what a push
would publish, separate what THIS session added from what was already there, and
print the commands. The decision stays with you; the blindness does not.

Reads the journal that record_touched_repos.py keeps — which is derived from what the
session actually touched, not declared in advance. Nothing to maintain, and no repo
can be forgotten because nobody put it on a list.
"""
import argparse, glob, json, os, subprocess, sys, textwrap, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PLUGINS = os.environ.get("GROVE_PLUGINS") or os.path.join(REPO, "plugins")
STATE_DIR = os.environ.get("GROVE_TOUCHED_STATE") or os.path.expanduser(
    "~/.claude/.grove/touched")


def git(root, *args, timeout=10, raw=False):
    """(ok, stdout). Never raises — a place that cannot answer is reported, not fatal.

    `raw` keeps the output byte-for-byte. It exists because `git status --porcelain`
    encodes state in COLUMN ONE — " M" is modified, "M " is staged — and stripping the
    output eats the leading space of the first line only. The first changed file in
    every place was therefore read one character short and counted as staged.
    """
    try:
        p = subprocess.run(["git", "-C", root] + list(args),
                           capture_output=True, text=True, timeout=timeout)
        return p.returncode == 0, (p.stdout if raw else p.stdout.strip())
    except Exception:
        return False, ""


INSTALLED = os.environ.get("GROVE_PLUGIN_CACHE") or os.path.expanduser(
    "~/.claude/plugins/cache")


def declaration_files():
    """Every `places.json` on this machine — installed copies first, this repo last.

    A declaring skill need not live here. Once the shipping tracks are their own
    marketplace, the operations that land in eight places are declared in a plugin
    grove never sees the source of — and reading only `plugins/` here would report
    "no operation declares its places" while a dozen do. So the installed caches are
    read too, and this repo is read last so that a skill you are editing wins over the
    copy that was installed from it.
    """
    found = []
    found += sorted(glob.glob(os.path.join(
        INSTALLED, "*", "*", "*", "skills", "*", "places.json")))
    found += sorted(glob.glob(os.path.join(PLUGINS, "*", "skills", "*", "places.json")))
    return found


def declarations():
    """{operation: parsed places.json} for every skill that declares where it lands.

    The journal answers "what did this session touch". A declaration answers a
    different question — "what does this OPERATION land in" — and the two differ in the
    case that matters: a place the operation should have written and did not appears in
    the second and never in the first. That is the eight-places failure, and no amount
    of watching a session can catch it.
    """
    out = {}
    for path in declaration_files():
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            name = d.get("operation") or os.path.basename(os.path.dirname(path))
            d["_lessons_path"] = os.path.join(os.path.dirname(path), "LESSONS.md")
            d["_source"] = path
            # Whether the declaration is one of OURS. A `state` command is a shell line,
            # and these are read from every installed plugin on the machine — see
            # show_declared, which will print somebody else's rather than run it.
            d["_trusted"] = path.startswith(os.path.join(PLUGINS, ""))
            out[name] = d
        except Exception:
            continue                                   # a broken declaration is not fatal
    return out


def show_declared(d, run_state=False):
    """The places one operation lands in, and how each closes. Reports; closes nothing.

    Deliberately does not run the git side: an operation's places are not the same set
    as the repos this session happened to touch, and mixing them would report each as
    the other. What it DOES do is run the declared state command, because that is the
    only thing here that can answer "do the places still agree" — and that question has
    no session in it at all. It is the answer to reality moving while nobody ran.
    """
    print(f"operation: {d.get('operation', '?')}\n")
    for pl in d.get("places", []):
        mark = "   ← work from inside it" if pl.get("enter") else ""
        kind = pl.get("root") or f"({pl.get('type', '?')})"
        print(f"■ {pl.get('id', '?')}   {kind}{mark}")
        print(f"    closes with: {pl.get('close', '?')}")
        if pl.get("paths"):
            print(f"    paths: {' · '.join(pl['paths'])}")
        # The note is the point of the whole file — it is the knowledge that was
        # otherwise a sentence buried in prose, and printing the table without it
        # would be printing the index of a book instead of the book.
        note = pl.get("why_enter") or pl.get("note")
        if note:
            for line in textwrap.wrap(note, 92):
                print(f"      {line}")
        print()
    for key, label in (("order", "order"), ("push", "push")):
        if d.get(key):
            v = d[key]
            print(f"\n{label}: " + (" → ".join(v) if isinstance(v, list) else str(v)))

    # Lessons, if the skill keeps any. Printed BEFORE the state check, because that is
    # the order they are useful in: what this operation has taught, and only then what
    # it currently looks like. A lesson read afterwards arrives after the decision it
    # should have shaped — the same reason the boundary guard names an owner instead of
    # injecting it.
    lessons = d.get("_lessons_path")
    if lessons and os.path.isfile(lessons):
        heads = [ln[3:].strip() for ln in open(lessons, encoding="utf-8")
                 if ln.startswith("## ")]
        if heads:
            print("── what earlier runs learned ──")
            for h in heads:
                print(f"  · {h}")
            print(f"  {lessons}\n")

    st = d.get("state") or {}
    cmd = st.get("command")
    if not cmd:
        return
    print(f"\n── the state of these places ──\n$ {cmd}\n")
    # A `state` command is an arbitrary shell line, and declarations are read from EVERY
    # installed plugin on this machine — any marketplace you have ever added. Running one
    # because a file asked is the shape of a supply-chain attack, and it would run under
    # your shell, with your keys, at the moment you were looking at something else. Ours
    # run; anyone else's are printed for a person to read first.
    if not (d.get("_trusted") or run_state):
        print("(not run — this declaration ships with an installed plugin:\n"
              f"   {d.get('_source')}\n"
              " Read the line above and run it yourself, or pass --run-state to have this\n"
              " do it. Nothing else here executes anything a plugin wrote.)")
        return
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, timeout=180)
        print((r.stdout or r.stderr).rstrip() or "(no output)")
    except Exception as e:
        print(f"could not run the state check: {str(e)[:120]}")


def sessions():
    """Journal records, newest first."""
    out = []
    if not os.path.isdir(STATE_DIR):
        return out
    for name in sorted(os.listdir(STATE_DIR)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(STATE_DIR, name)
        try:
            with open(path, encoding="utf-8") as f:
                out.append((os.path.getmtime(path), json.load(f)))
        except Exception:
            continue
    return [rec for _, rec in sorted(out, reverse=True)]


def places(session_id=None):
    """{root: info dict} for the session in question, straight from the journal.

    Two fields decide everything downstream, and they are not interchangeable.
    `baseline` is what was already dirty when the session first saw the place — it
    separates "changed while I was here" from "the owner had it in progress". `written`
    is what a writing tool of THIS session actually named — it is the only field that
    may be read as authorship. `paths` (everything mentioned) is deliberately not used
    for that; see mine().
    """
    recs = sessions()
    if session_id:
        recs = [r for r in recs if r.get("session") == session_id] or recs[:1]
    if not recs:
        return {}, None
    rec = recs[0]
    out = {}
    for root, info in (rec.get("repos") or {}).items():
        if os.path.isdir(root):
            out[root] = {
                "baseline": set(info.get("baseline") or []),
                "written": [q for q in (info.get("written") or []) if isinstance(q, str)],
                "head": info.get("head") or "",
            }
    return out, rec.get("session")


def mine(written, now):
    """Of what this session wrote, what is still uncommitted here.

    This used to be inferred: everything dirty that was not in the baseline and that the
    session had *mentioned*. It was wrong twice, in the same direction — 101 media files
    in the hub, then five localisation files in an app repo that a parallel session was
    writing while this one merely grepped for them. Mentioning is not writing, and a
    baseline is a snapshot in time, not a record of who did what; neither can be filtered
    into authorship. So the claim now rests on the write itself and nothing else.

    A write that was refused, failed, or has since been committed drops out here, because
    a path only counts while it is actually dirty.
    """
    keep = []
    for w in written:
        for n in now:
            # exact file, a file inside a directory git reports whole (`he.lproj/`),
            # or a directory we wrote into
            if w == n or w.startswith(n.rstrip("/") + "/") or n.startswith(w.rstrip("/") + "/"):
                keep.append(w)
                break
    return sorted(set(keep))


def state(root, info):
    """Everything the report needs about one place. `None` fields mean 'could not ask'."""
    baseline = info["baseline"]
    ok, top = git(root, "rev-parse", "--show-toplevel")
    if not ok:
        return {"repo": False}

    ok, porcelain = git(root, "status", "--porcelain", "--", ".", raw=True)
    now = {ln[3:].strip() for ln in porcelain.splitlines() if len(ln) > 3} if ok else set()
    staged = {ln[3:].strip() for ln in porcelain.splitlines()
              if len(ln) > 3 and ln[0] not in " ?"} if ok else set()

    ok, branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    branch = branch if ok else "?"
    ok, email = git(root, "config", "user.email")
    signer = email if ok and email else "(unset — the global one will sign)"

    ahead = since = None
    ok, cnt = git(root, "rev-list", "--count", "@{u}..HEAD")
    if ok and cnt.isdigit():
        ahead = int(cnt)
        # Of what a push would publish, how much was even created after we got here.
        # Asked against the commit this place stood on at first sight, not against the
        # clock: "committed in the last 24 hours" called nine of the owner's own commits
        # this session's on 2026-09-10. A sha cannot drift like that. It is still only a
        # time boundary — a parallel session's commits land after it too — so the wording
        # downstream says "since the session arrived", never "mine".
        if info["head"]:
            ok2, c2 = git(root, "rev-list", "--count", "@{u}..HEAD", "^" + info["head"])
            if ok2 and c2.isdigit():
                since = min(int(c2), ahead)
    mine_here = mine(info["written"], now)
    return {"repo": True, "top": top, "dirty": now, "staged": staged,
            "mine": mine_here, "unclaimed": sorted(now - baseline - set(mine_here)),
            "theirs": sorted(now & baseline),
            "branch": branch, "signer": signer, "ahead": ahead, "since": since}


def short(root):
    home = os.path.expanduser("~")
    return "~" + root[len(home):] if root.startswith(home + os.sep) else root


def report(rows):
    """One line per place, and the three states on it."""
    print(f"{'place':<34} {'mine':>5} {'theirs':>5}  state")
    print("─" * 78)
    for root, st in rows:
        if not st["repo"]:
            print(f"{short(root):<34} {'—':>5} {'—':>5}  not a git repo — nothing to commit, nothing to undo")
            continue
        bits = []
        if st["staged"]:
            bits.append(f"{len(st['staged'])} staged, waiting for a commit")
        if not st["mine"] and not st["staged"]:
            # "clean" means the place is clean, not merely that nothing here is ours —
            # after a commit those two diverge, and the second read as the first is how
            # a place with someone else's open work gets reported as finished.
            bits.append("clean" if not st["dirty"] else "no open writing of this session")
        if st["ahead"] is None:
            bits.append("no upstream")
        elif st["ahead"]:
            extra = ""
            if st["since"] is not None and st["since"] < st["ahead"]:
                extra = f" — {st['ahead'] - st['since']} of them predate this session"
            bits.append(f"{st['ahead']} unpushed{extra}")
        print(f"{short(root):<34} {len(st['mine']):>5} {len(st['theirs']):>5}  " + " · ".join(bits))
        for q in st["mine"][:4]:
            print(f"{'':<34} {'':>5} {'':>5}    {q}")
        if len(st["mine"]) > 4:
            print(f"{'':<34} {'':>5} {'':>5}    +{len(st['mine']) - 4} more")
        if st["unclaimed"]:
            print(f"{'':<34} {'':>5} {'':>5}    ⚠ {len(st['unclaimed'])} changed here and are not this session's writing — never committed")


def main():
    ap = argparse.ArgumentParser(description="Bring every touched place to a closed state.")
    ap.add_argument("--commit", action="store_true", help="also commit, per place, its own paths")
    ap.add_argument("-m", "--message", help="commit message (per place, in its own terms)")
    ap.add_argument("--session", help="a specific session id from the journal")
    ap.add_argument("--op", metavar="NAME",
                    help="report an OPERATION's declared places instead of this session's")
    ap.add_argument("--ops", action="store_true", help="list the operations that declare their places")
    ap.add_argument("--run-state", action="store_true",
                    help="with --op: also run a state command that came from an installed "
                         "plugin (ours run either way)")
    a = ap.parse_args()

    decls = declarations()
    if a.ops:
        if not decls:
            print("no skill declares where it lands.")
            return 0
        for name, d in sorted(decls.items()):
            mark = "" if d.get("_trusted") else "   ← from an installed plugin"
            print(f"  {name:<20} {len(d.get('places', []))} places{mark}")
        return 0
    if a.op:
        d = decls.get(a.op)
        if not d:
            print(f"no declaration for '{a.op}'. There is: " + (", ".join(sorted(decls)) or "none"))
            return 2
        show_declared(d, run_state=a.run_state)
        return 0

    found, sid = places(a.session)
    if not found:
        print("the journal is empty — no places were touched.")
        return 0

    rows = [(root, state(root, info)) for root, info in sorted(found.items())]
    print(f"session {sid}\n")
    report(rows)

    open_git = [(r, s) for r, s in rows if s["repo"] and (s["mine"] or s["staged"])]
    unpushed = [(r, s) for r, s in rows if s["repo"] and s["ahead"]]

    if a.commit and open_git:
        if not a.message:
            print("\n✗ --commit needs -m. The message is written in the terms of the repo it lands in.")
            return 2
        print()
        for root, st in open_git:
            paths = st["mine"] or sorted(st["staged"])   # only writes, never a sweep
            ok, _ = git(root, "add", "--", *paths)
            if not ok:
                print(f"   ✗ {short(root)}: add failed")
                continue
            ok, out = git(root, "commit", "-m", a.message, "--", *paths, timeout=60)
            print(f"   {'✓' if ok else '✗'} {short(root)}: "
                  f"{len(paths)} paths" + ("" if ok else f" — {out.splitlines()[-1][:70] if out else 'failed'}"))
        print()
        rows = [(root, state(root, info)) for root, info in sorted(found.items())]
        report(rows)
        unpushed = [(r, s) for r, s in rows if s["repo"] and s["ahead"]]
        open_git = [(r, s) for r, s in rows if s["repo"] and (s["mine"] or s["staged"])]

    print()
    if open_git and not a.commit:
        print("to close:  python3 tools/close.py --commit -m \"...\"")
    if unpushed:
        print("\nto push — and what each one would publish:")
        for root, st in unpushed:
            note = ""
            if st["since"] is not None and st["since"] < st["ahead"]:
                note = (f"   ← {st['ahead']} commits, {st['ahead'] - st['since']} of them predate this"
                        f" session — and the rest are not necessarily its own")
            print(f"   git -C {short(root)} push        ({st['branch']}, signed as {st['signer']}){note}")
        print("\n   The push is not done here: it publishes a whole branch and cannot be undone.")
    if not open_git and not unpushed:
        print("✓ every place you touched is closed and pushed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
