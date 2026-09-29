#!/usr/bin/env python3
"""Read the touched-repos log and answer the one question that decides docs/cross-repo-session/1-need-problem-solution.

    python3 tools/touched_report.py

The question: does a session typically touch more than one repo, and does it touch
repos the registry does not list? If the answer is "one repo, always the one it stands
in", then the design is a solution to a rare problem and should not be built.

Reads only. Written the same day as the recorder, because in a week nobody will
remember what to query — which is the failure this whole line of work is about.
"""
import json, os, sys, collections

STATE_DIR = os.environ.get("GROVE_TOUCHED_STATE") or os.path.expanduser(
    "~/.claude/.grove/touched")
REGISTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registry.json")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "plugins", "grove", "hooks", "scripts"))
from grove_repo import registry_roots as all_registry_roots  # noqa: E402


def registry_roots():
    """Every root the registry names — projects AND apps.

    It read `projects` alone, so the six app repos counted as unregistered and the
    report's headline said 100% of sessions touched a repo off the registry when the
    real figure is lower. Same omission as the three guards, measured the same day; the
    shared helper is the fix in all four places.
    """
    try:
        reg = json.load(open(REGISTRY))
        return {r for _, r, _ in all_registry_roots(reg)}
    except Exception:
        return set()


def _help_only():
    """`--help` must answer, not run. These take no options, so the docstring IS the
    usage — but a script that ignores `-h` and starts a full scan instead teaches you
    that its flags are not to be trusted."""
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(__doc__.strip())
        raise SystemExit(0)


def main():
    _help_only()
    if not os.path.isdir(STATE_DIR):
        print(f"No data yet — {STATE_DIR} does not exist.")
        return 1
    files = [f for f in os.listdir(STATE_DIR) if f.endswith(".json")]
    sessions = []
    for f in files:
        try:
            d = json.load(open(os.path.join(STATE_DIR, f)))
        except Exception:
            continue
        if d.get("repos"):
            sessions.append(d)
    if not sessions:
        print("No sessions recorded yet.")
        return 1

    known = registry_roots()
    counts = collections.Counter()
    repo_freq = collections.Counter()
    off_registry = 0
    multi = 0

    for d in sessions:
        repos = list(d["repos"])
        counts[len(repos)] += 1
        if len(repos) > 1:
            multi += 1
        for r in repos:
            repo_freq[r] += 1
        if any(r not in known for r in repos):
            off_registry += 1

    n = len(sessions)
    print(f"Sessions recorded: {n}   (since {min(d.get('started','?') for d in sessions)})")
    print()
    print("Repos per session:")
    for k in sorted(counts):
        bar = "█" * min(counts[k], 40)
        print(f"  {k:>2} repos │ {bar} {counts[k]}")
    print()
    med = sorted(len(d["repos"]) for d in sessions)[n // 2]
    print(f"  median: {med}   mean: {sum(len(d['repos']) for d in sessions)/n:.1f}"
              f"   max: {max(len(d['repos']) for d in sessions)}")
    print()
    print(f"Sessions that touched more than one repo:  {multi:>3}/{n}  ({multi/n*100:.0f}%)")
    print(f"Sessions that touched an unregistered repo: {off_registry:>3}/{n}  ({off_registry/n*100:.0f}%)")
    print()
    print("Most frequent repos:")
    for r, c in repo_freq.most_common(10):
        mark = "  " if r in known else " ← not in the registry"
        print(f"  {c:>3}× {r}{mark}")

    print()
    print("─" * 60)
    if n < 10:
        # A confident conclusion from a handful of sessions is the exact mistake this
        # measurement exists to avoid. Say so instead of implying one.
        print(f"Verdict: not enough data. Only {n} sessions — at least 10 are needed,")
        print("         and preferably a week of ordinary work. Run it again later.")
        print("─" * 60)
        return 0
    if multi / n < 0.2:
        print("Verdict: a typical session touches one repo. The solution answers a rare problem —")
        print("         do not build layers 2–4.")
    elif off_registry == 0:
        print("Verdict: there is cross-repo work, but all of it inside the registered repos.")
        print("         The existing mechanism covers it. Consider only layers 2–3.")
    else:
        print("Verdict: cross-repo work is common, and it reaches beyond the registry —")
        print("         which means the existing mechanism misses it. The solution is justified.")
    print("─" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
