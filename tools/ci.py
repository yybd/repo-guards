#!/usr/bin/env python3
"""Everything that can be checked without installing anything.

    python3 tools/ci.py             run every check; exit non-zero if one fails
    python3 tools/ci.py --metrics   the same, and print the numbers as JSON
    python3 tools/ci.py --record    …and append them to tools/metrics.jsonl

**Why this exists next to `deploy.py`.** Deploy answers "is this machine set up", and
most of what it does is install: it copies plugins into the cache, writes settings, and
fails when a copy is stale. None of that is true of a clean checkout on a build runner,
which has no plugins installed and never will. Running deploy there would report
problems that are not problems — the noise that gets a checker ignored.

What is left when you remove the machine is exactly what a **push** should be gated on:
the guard pipelines, and the checks that read files. That set is this file.

**And it is the only thing that exercises a fresh clone.** Every other check runs on a
machine that was already set up, which is how two bugs survived until 2026-09-11: a
portability test that could only pass once a registry existed, and a deploy that failed
on an optional step. Both were found by cloning into a temporary directory by hand. This
runs that path on every push instead.

**It installs nothing and touches no settings**, so it is safe to run anywhere.
"""
import argparse, glob, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HISTORY = os.path.join(HERE, "metrics.jsonl")

# (label, argv) — each must be runnable on a bare checkout with git and python3.
CHECKS = [
    ("references", [sys.executable, os.path.join(HERE, "check_references.py")]),
    ("scripts",    [sys.executable, os.path.join(HERE, "check_scripts.py")]),
    ("bilingual",  [sys.executable, os.path.join(HERE, "check_bilingual.py")]),
    ("ownership",  [sys.executable, os.path.join(HERE, "check_ownership.py")]),
]


def pipelines():
    """The guard pipelines and the tool tests, by path — counted, never listed by hand."""
    out = []
    for p in sorted(glob.glob(os.path.join(HERE, "tests", "test_*.py"))):
        out.append((os.path.basename(p)[:-3], [sys.executable, p]))
    for p in sorted(glob.glob(os.path.join(
            REPO, "plugins", "*", "hooks", "scripts", "tests", "test_*.py"))):
        out.append((os.path.basename(p)[:-3], [sys.executable, p]))
    return out


def manifests():
    """Do the two manifests still agree with each other and with the disk?

    A plugin is described twice: in `.claude-plugin/marketplace.json`, which is what a
    catalogue shows, and in its own `plugin.json`, which is **what loads into every
    session that enables it**. Nothing kept them together, and they had already drifted —
    one track's marketplace line had lost a sentence its plugin.json still carried. The
    same class as a stale cache: the text people read and the text that runs, diverging
    quietly.
    """
    import json
    out = []
    mp = os.path.join(REPO, ".claude-plugin", "marketplace.json")
    try:
        m = json.load(open(mp, encoding="utf-8"))
    except Exception as e:
        return [f"marketplace.json could not be read: {e}"]
    listed = set()
    for pl in m.get("plugins", []):
        name = pl.get("name", "?")
        listed.add(name)
        src = os.path.normpath(os.path.join(REPO, pl.get("source", "")))
        pj = os.path.join(src, ".claude-plugin", "plugin.json")
        if not os.path.isfile(pj):
            out.append(f"{name}: listed in the marketplace, no plugin.json at {pl.get('source')}")
            continue
        try:
            d = json.load(open(pj, encoding="utf-8"))
        except Exception as e:
            out.append(f"{name}: plugin.json could not be read: {e}")
            continue
        if d.get("name") != name:
            out.append(f"{name}: its plugin.json calls it '{d.get('name')}'")
        if d.get("description") != pl.get("description"):
            out.append(f"{name}: the marketplace description and plugin.json's have drifted")
    on_disk = {os.path.basename(os.path.dirname(os.path.dirname(p)))
               for p in glob.glob(os.path.join(REPO, "plugins", "*", ".claude-plugin", "plugin.json"))}
    for extra in sorted(on_disk - listed):
        out.append(f"{extra}: a plugin on disk that the marketplace does not list")
    return out


def run(argv):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=600, cwd=REPO)
        return p.returncode, (p.stdout + p.stderr)
    except Exception as e:
        return 1, f"could not run: {e}"


def counted(text):
    """The number of ✓/✗ lines a pipeline printed — its own count of what it checked."""
    return sum(1 for ln in text.splitlines() if ln.startswith(("✓", "✗")))


def measure():
    """What this repo IS, counted from disk. Numbers only — no judgement."""
    md = [p for p in glob.glob(os.path.join(REPO, "**", "*.md"), recursive=True)
          if ".git" not in p]
    return {
        "plugins": len(glob.glob(os.path.join(REPO, "plugins", "*", ".claude-plugin", "plugin.json"))),
        "skills": len(glob.glob(os.path.join(REPO, "plugins", "*", "skills", "*", "SKILL.md"))),
        "guards": len([p for p in glob.glob(os.path.join(
            REPO, "plugins", "*", "hooks", "scripts", "*.py"))
            if not os.path.basename(p).endswith("_repo.py")]),
        "docs": len(md),
        "doc_pairs": len([p for p in md if p.endswith(".he.md")]),
        "python": len([p for p in glob.glob(os.path.join(REPO, "**", "*.py"), recursive=True)
                       if ".git" not in p]),
    }


def head():
    ok, out = True, ""
    try:
        p = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        out = p.stdout.strip()
    except Exception:
        ok = False
    return out if ok else "?"


def main():
    ap = argparse.ArgumentParser(description="Every check that needs no installation.")
    ap.add_argument("--metrics", action="store_true", help="print the numbers as JSON")
    ap.add_argument("--record", action="store_true",
                    help="append the numbers to tools/metrics.jsonl")
    a = ap.parse_args()

    failed, checks_run = [], 0
    print("── checks that read files ──")
    for label, argv in CHECKS:
        rc, out = run(argv)
        last = [ln for ln in out.splitlines() if ln.strip()]
        print(f"  {'✓' if rc == 0 else '✗'} {label:<12} {last[-1][:80] if last else ''}")
        if rc != 0:
            failed.append((label, out))

    bad_manifests = manifests()
    print(f"  {'✓' if not bad_manifests else '✗'} {'manifests':<12} "
          + ("the marketplace and every plugin.json agree" if not bad_manifests
             else f"{len(bad_manifests)} disagreements"))
    if bad_manifests:
        failed.append(("manifests", "\n".join("✗ " + b for b in bad_manifests)))

    print("\n── pipelines ──")
    for label, argv in pipelines():
        rc, out = run(argv)
        n = counted(out)
        checks_run += n
        print(f"  {'✓' if rc == 0 else '✗'} {label:<28} {n} checks")
        if rc != 0:
            failed.append((label, out))

    m = measure()
    m["pipeline_checks"] = checks_run
    m["date"] = time.strftime("%Y-%m-%d")
    m["head"] = head()
    m["failed"] = [label for label, _ in failed]

    print(f"\n{m['plugins']} plugin(s) · {m['skills']} skills · {m['guards']} guards · "
          f"{checks_run} checks in {len(pipelines())} pipelines · "
          f"{m['doc_pairs']} bilingual pairs of {m['docs']} documents")

    if failed:
        # The whole output of whatever failed, not a filtered slice of it: a gate that
        # says "3 failed" without saying which is a gate nobody can act on.
        for label, out in failed:
            print(f"\n── {label} ──")
            for ln in out.splitlines():
                print("  " + ln.rstrip())
        print(f"\n{len(failed)} failed: {', '.join(label for label, _ in failed)}")
    else:
        print("\n✓ everything that can be checked without installing is in place.")

    if a.metrics or a.record:
        print("\n" + json.dumps(m, ensure_ascii=False, sort_keys=True))
    if a.record:
        with open(HISTORY, "a", encoding="utf-8") as f:
            f.write(json.dumps(m, ensure_ascii=False, sort_keys=True) + "\n")
        print(f"appended to {os.path.relpath(HISTORY, REPO)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
