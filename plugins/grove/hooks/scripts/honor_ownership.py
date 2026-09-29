#!/usr/bin/env python3
"""PreToolUse guard: honour what a place declares it owns.

Replaces protect_project_roots.py, and the difference is the whole point.

**The old criterion was a proxy.** It asked "does this repo have a .claude/skills
directory?" and, if so, blocked EVERY write into the repo from a session standing
elsewhere — with two exception lists in the registry (`protected`, `open_paths`) to
claw back the over-reach. It then GUESSED which skill owned the path by grepping
SKILL.md text for path fragments; the comment in that code said "well enough to point
at", which is an honest thing to say about a guess and a bad thing to enforce on.

**The new criterion is a declaration.** A place says, in its own `.claude/owns.json`,
which paths it owns and what a foreign write to them should do. Nothing else is
blocked. The boundary belongs to the owner: a new local skill adds a line where it
lives, and no visiting operation has to learn about it.

Two levels, and they are not a dial — they are two different things:

    block   a local skill AUTHORS this path. Reading a skill from outside is not a
            substitute for running it, so this is the one case where writing from
            elsewhere genuinely bypasses something.
    warn    the path carries a RULE rather than an owner. The write may be perfectly
            legitimate; it just has to know something first. a site repo's content/en.json
            is the case: no skill owns it, editing it requires `npm run content`, and
            skipping that served a wrong price for twelve hours while every guard on
            the machine stayed silent — because no skill owned the path.

    {
      "claims": [
        {"paths": ["src/pages/", "src/data/apps.ts"], "owner": "add-app-to-site",
         "action": "block", "why": "the page structure is written by this skill"},
        {"paths": ["content/en.json"], "action": "warn",
         "why": "edit the JSON, run `npm run content`, commit both together"}
      ]
    }

Undeclared is open. That is deliberate: the old default blocked a whole repo to protect
three subtrees, and needed an exception list to stay usable. This one has nothing to
maintain and no exceptions to keep in sync — the cost is that a place which declares
nothing is protected by nothing, which is already true of every repo but one.

**It reads shell lines too, and that is not an extra — it was the hole.** The guard
used to look only at `file_path`, so a claim held against `Edit` and was invisible to
`sed -i`, `> file`, `cp` and `tee` — the forms a session reaches for most, and the only
forms available at all when it works through Bash. What is parsed here is deliberately
narrow: redirections, and a fixed list of commands whose write target is unambiguous.

**Four shapes walked straight past it until 2026-09-11**, each measured against a
throwaway declaration, and each refused now:

    (cd <root> && echo x > src/pages/p)   a subshell — the splitter never saw the `cd`
    echo x &> src/pages/p                 `&>` and `>|`, which the redirection pattern
                                          required a digit or nothing in front of
    perl -pi -e s/a/b/ src/pages/p        the flag bundle, where only a lone `-i` counted
    rm -rf <root>/src                     a target ABOVE the claim: the declared path is
                                          not in the command at all

The last one is the one worth naming twice. It does the most damage with the least
typing, and the guard was silent precisely because nothing in the line resembled the
thing it protects.

**What is still out of reach**, stated rather than papered over, because a guard that
pretends to full coverage is worse than one whose edge is known:

    python3 build.py          what a script writes from the inside
    cp a "$DEST"              a target that only exists after the shell expands it
    xargs · find -exec        the write target belongs to a command this never sees
    sh -c "$CMD"              a command line that is a variable

Fails OPEN: any error allows the write. A broken guard must not stop work.
"""
import json, os, re, sys
# The two guards judge the same shell line and must read it the same way — see
# shell_commands there. Splitting it twice is how two answers drift apart.
from grove_repo import shell_commands

CLAIMS = os.path.join(".claude", "owns.json")


def real(p):
    return os.path.realpath(os.path.expanduser(p))


def declaring_root(target):
    """The nearest directory at or above `target` that declares what it owns."""
    d = target if os.path.isdir(target) else os.path.dirname(target)
    while True:
        if os.path.isfile(os.path.join(d, CLAIMS)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def claims_of(root):
    try:
        with open(os.path.join(root, CLAIMS), encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []                                  # unreadable declaration → no claims
    out = []
    for c in (data.get("claims") or []):
        if not isinstance(c, dict):
            continue                               # prose in a data file; skip it
        paths = c.get("paths")
        paths = [paths] if isinstance(paths, str) else paths
        if not isinstance(paths, list):
            continue
        out.append({"paths": [str(p) for p in paths if isinstance(p, str)],
                    "owner": c.get("owner"),
                    "action": (c.get("action") or "block").lower(),
                    "why": c.get("why") or ""})
    return out


def matching(claims, rel):
    """Claims covering `rel`, block before warn, longest path first.

    Two ways a target meets a claim, and only the first was asked:

        inside    the target IS the claimed path or sits under it
        contains  the target sits ABOVE it — `rm -rf src` when `src/pages/` is claimed,
                  or `mv site elsewhere`, or `cp -r pages site/src/`

    The second is not a corner case. It is the shape that does the most damage with the
    least typing: the declared path never appears in the command at all, so the guard
    saw nothing to match and allowed a line that removes the whole thing. Measured
    2026-09-11 against a throwaway declaration — `rm -rf <root>` was allowed in silence
    while `rm -rf <root>/src/pages` was refused.
    """
    hits = []
    for c in claims:
        for p in c["paths"]:
            q, r = p.rstrip("/"), rel.rstrip("/")
            if r == q or r.startswith(q + "/"):
                how = "inside"
            elif r in (".", "") or q.startswith(r + "/"):
                how = "contains"
            else:
                continue
            hits.append((0 if c["action"] == "block" else 1, -len(q),
                         dict(c, how=how, hit=q)))
            break
    hits.sort(key=lambda t: (t[0], t[1]))
    return [c for _, _, c in hits]


# `>f`, `>>f`, `2>f`, `&>f`, `&>>f`, `>|f`, and each of them bare with the path after.
# `&>` and `>|` were invisible here: the pattern demanded a digit or nothing before the
# `>`, so the two forms a shell user reaches for when overwriting deliberately were the
# two the guard could not see.
REDIR = re.compile(r"^(?:\d+|&)?>>?\|?(.*)$")

# Commands whose write target can be read off the line with certainty. Anything not
# here is allowed: an unknown command is not evidence of a write.
ALL_ARGS = {"tee", "rm", "unlink", "touch", "truncate", "mkdir", "rmdir"}
LAST_ARG = {"cp", "install", "rsync", "ln"}        # destination is the final argument
BOTH_ENDS = {"mv"}                                 # destination AND source: mv empties it
IN_PLACE = {"sed", "perl", "ruby", "gawk"}         # only with -i, and only on real files


def args_of(tokens):
    """Non-flag arguments after the command word, and whether -i was among the flags."""
    args, in_place, skip = [], False, False
    for t in tokens[1:]:
        if skip:
            skip = False
            continue
        if t.startswith("-") and len(t) > 1:
            # `-pi` is the form the perl one-liner is actually written in, and a rule
            # that only knew `-i` read it as an ordinary flag and let the edit through.
            if (t == "--in-place" or t.startswith("-i")
                    or (not t.startswith("--") and "i" in t[1:])):
                in_place = True
            if t in ("-t", "--target-directory", "-S", "--suffix", "-e", "--expression"):
                skip = True                        # its value is not a target
            continue
        args.append(t)
    return args, in_place


def bash_targets(cmd, cwd):
    """Absolute paths this shell line writes. Narrow by construction — see the note.

    Where each command runs comes from shell_commands, which tracks `cd`, reads a
    subshell and a shell\'s `-c` argument, and strips `sudo`/`env`. This used to do its
    own splitting on a regex, and a single leading `(` was enough to make every claim in
    the system invisible.
    """
    out = []
    for tokens, here, _env in shell_commands(cmd, cwd):

        def absolute(p, here=here):
            p = os.path.expanduser(p)
            return real(p if os.path.isabs(p) else os.path.join(here, p))

        # redirections, wherever they sit in the command
        rest, i = [], 0
        while i < len(tokens):
            t = tokens[i]
            m = REDIR.match(t)
            if m and ">" in t:
                tail = m.group(1)
                if not tail and i + 1 < len(tokens):
                    tail, i = tokens[i + 1], i + 1
                if tail and not tail.startswith("&"):
                    out.append(absolute(tail))
            else:
                rest.append(t)
            i += 1
        if not rest:
            continue

        name = os.path.basename(rest[0])
        args, in_place = args_of(rest)
        if (name.startswith("python") or name == "node"
                or (name in ("ruby", "perl") and not in_place)):
            continue                               # what a script writes is unknowable
        if name in ALL_ARGS:
            out += [absolute(a) for a in args]
        elif name in BOTH_ENDS and len(args) >= 2:
            out += [absolute(a) for a in args]
        elif name in LAST_ARG and len(args) >= 2:
            out.append(absolute(args[-1]))
        elif name in IN_PLACE and in_place:
            # `sed -i \'\' s/a/b/ file` hands us three arguments and only one is a path.
            # The separator: a real target\'s PARENT exists. `s/a/b/` resolves under a
            # directory that does not, and the empty suffix argument resolves to the
            # cwd itself — which would otherwise be claimed as a write.
            for a in args:
                if not a:
                    continue
                p = absolute(a)
                if os.path.isdir(os.path.dirname(p) or "/"):
                    out.append(p)
        elif name == "dd":
            for a in rest[1:]:
                if a.startswith("of="):
                    out.append(absolute(a[3:]))
    return out


def judge(target, cwd):
    """(root, rel, hits) for one write target, or None when nothing here claims it."""
    root = declaring_root(target)
    if not root:
        return None                                # nothing here declares anything
    if cwd == root or cwd.startswith(root + os.sep):
        return None                                # we ARE there; its own rules apply
    rel = os.path.relpath(target, root)
    hits = matching(claims_of(root), rel)
    return (root, rel, hits) if hits else None     # undeclared is open


def deny(root, rel, top, cwd):
    who = f"'{top['owner']}'" if top.get("owner") else "this place"
    why = f"\n{top['why']}" if top["why"] else ""
    what = (f"{rel} is declared as owned by {who}"
            if top.get("how") != "contains" else
            f"{rel} CONTAINS {top.get('hit')}, which is declared as owned by {who}")
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            f"{what} in {root}/{CLAIMS} — and this "
            f"session is in {cwd}, so that owner is not loaded here.{why}\n"
            f"A local skill can be READ from outside but not RUN, which is exactly "
            f"what writing here would skip. Do one of these:\n"
            f"  • change_directory to {root} and let its owner do the work, or\n"
            f"  • spawn a task with cwd={root}, or\n"
            f"  • if this path should be writable from anywhere, remove the claim."
        )}}))


def inform(root, rel, top, cwd):
    why = f"\n{top['why']}" if top["why"] else ""
    what = (f"{rel} carries a rule" if top.get("how") != "contains"
            else f"{rel} contains {top.get('hit')}, which carries a rule")
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": (
            f"[owns] {what} in {root}/{CLAIMS}, and this session is not "
            f"standing in {root} so that rule is not loaded here.{why}\n"
            f"The write is allowed — read the rule first, and do what it says afterwards."
        )}}))


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    ti = payload.get("tool_input") or {}
    if not isinstance(ti, dict):
        return
    cwd = real(payload.get("cwd") or os.getcwd())

    targets = []
    one = ti.get("file_path") or ti.get("path") or ti.get("notebook_path")
    if isinstance(one, str) and one:
        targets.append(real(one))
    cmd = ti.get("command")
    if isinstance(cmd, str) and cmd:
        targets += bash_targets(cmd, cwd)

    verdicts = [v for v in (judge(t, cwd) for t in targets) if v]
    if not verdicts:
        return

    # One decision per call, and a block anywhere in the line decides it: the segments
    # of a shell line are not independent, so allowing the call because only one of its
    # writes is claimed would let that write through.
    for root, rel, hits in verdicts:
        if hits[0]["action"] == "block":
            deny(root, rel, hits[0], cwd)
            return
    root, rel, hits = verdicts[0]
    inform(root, rel, hits[0], cwd)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass                                       # fail open, always
