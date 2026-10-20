#!/usr/bin/env python3
"""Do the registered repos' GitHub workflows spend the account's Actions budget sparingly?

    python3 tools/check_actions.py [repo ...]

A private repository pays for Actions out of one allowance for the whole account — on
the free plan 2,000 minutes a month and 500 MB of artifact storage — and **a Windows
minute counts twice, a macOS minute ten times.** Run out, and every workflow in every
private repo stops: nothing builds, nothing is checked, until the month turns or someone
pays. Measured on 2026-10-20, the day it happened here: about 2,450 billed minutes in
twenty days, and 2 GB of artifacts. Half of the minutes came from two shapes — a test
matrix that ran macOS and Windows on every push (851), and a Windows build on every push
(612) — and most of the storage from installers kept for the default 90 days.

Nothing in a workflow file says what it costs, and a workflow is written once and then
runs for months. So the shapes that cost are checked here, statically, across every place
in the registry (or the repos named on the command line):

    FAIL    a Windows or macOS runner started by every push — anything but a tag push,
            unless the runner is chosen by the event (`github.event_name` on the same
            line, or an `if:` on the job naming it)
    FAIL    an `actions/upload-artifact` step with no `retention-days`, or one over 7 —
            the default keeps it 90 days, against the account's storage
    REPORT  no top-level `concurrency:` — a newer push does not cancel the run before it
    REPORT  a job with no `timeout-minutes` — a hung job runs for six hours
    REPORT  `docker/build-push-action` without `DOCKER_BUILD_RECORD_UPLOAD: false` — it
            uploads a build-record artifact on every run

**A public repository pays for none of this**, and a static check cannot see which repos
are public. So a deliberate exception is written in the workflow itself, where the next
reader sees the reason: a comment line `# repo-guards: actions-budget ok — <why>` mutes
the file.

What it cannot do: read YAML. It reads lines and indentation, which is enough for the
shapes above and stays inside the standard library, as every tool here must. A workflow
whose shape it does not understand passes rather than fails — a checker that cries wolf
is a checker nobody runs.
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "plugins", "repo-guards", "hooks", "scripts"))
import guards_repo as fr                                  # noqa: E402

MUTE = re.compile(r"#\s*repo-guards:\s*actions-budget ok", re.I)
COSTLY = re.compile(r"\b(windows|macos)-[\w.]+", re.I)
GATED = re.compile(r"github\.event_name|startsWith\(\s*github\.ref", re.I)
MAX_RETENTION = 7


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _block(lines, start):
    """The lines under lines[start], by indentation (comments and blanks kept)."""
    base = _indent(lines[start])
    out = []
    for ln in lines[start + 1:]:
        if ln.strip() and not ln.lstrip().startswith("#") and _indent(ln) <= base:
            break
        out.append(ln)
    return out


def _key(lines, name, indent=0):
    for i, ln in enumerate(lines):
        if _indent(ln) == indent and re.match(rf"\s*['\"]?{name}['\"]?\s*:", ln):
            return i
    return None


def push_untagged(lines):
    """Does a push other than a tag push start this workflow?"""
    i = _key(lines, "on")
    if i is None:
        return False
    head = lines[i].split(":", 1)[1].split("#")[0].strip()
    if head:                      # on: push  /  on: [push, pull_request]
        return bool(re.search(r"\bpush\b", head))
    block = _block(lines, i)
    for j, ln in enumerate(block):
        if re.match(r"\s*push\s*:", ln):
            rest = ln.split(":", 1)[1].split("#")[0].strip()
            if rest:              # push: {...} on one line
                return "tags" not in rest or "branches" in rest
            sub = [x for x in _block(block, j) if x.strip() and not x.lstrip().startswith("#")]
            keys = {re.match(r"\s*([\w-]+)\s*:", x).group(1)
                    for x in sub if re.match(r"\s*[\w-]+\s*:", x)}
            # Only tags (and their filters): a release, not every push.
            if keys and keys <= {"tags", "tags-ignore"}:
                return False
            # Branches named, and none of them the everyday one (release/**): also a release.
            if "branches" in keys:
                names = re.findall(r"[\w*./-]+", " ".join(
                    x.split(":", 1)[-1] if re.match(r"\s*branches\s*:", x) else x.strip(" -")
                    for x in sub if not re.match(r"\s*(paths|paths-ignore|tags|tags-ignore)\s*:", x)))
                names = [n for n in names if n != "branches"]
                if names and not any(n in ("main", "master", "*", "**") for n in names):
                    return False
            return True
        if re.match(r"\s*-\s*push\b", ln):
            return True
    return False


def jobs(lines):
    i = _key(lines, "jobs")
    if i is None:
        return []
    block = _block(lines, i)
    ind = min((_indent(x) for x in block if x.strip() and not x.lstrip().startswith("#")),
              default=None)
    out = []
    for j, ln in enumerate(block):
        m = re.match(r"\s*([\w-]+)\s*:", ln)
        if m and _indent(ln) == ind:
            out.append((m.group(1), ind, _block(block, j)))
    return out


def check_file(path):
    """(fails, reports) for one workflow file, each a list of strings."""
    text = open(path, encoding="utf-8", errors="replace").read()
    if MUTE.search(text):
        return [], []
    lines = text.splitlines()
    fails, reports = [], []
    on_push = push_untagged(lines)

    for name, ind, body in jobs(lines):
        code = [x for x in body if x.strip() and not x.lstrip().startswith("#")]
        job_if = next((x for x in code if _indent(x) == ind + 2 and x.strip().startswith("if:")), "")
        costly = [x for x in code if COSTLY.search(x) and not x.lstrip().startswith("- uses")
                  and "uses:" not in x]
        if on_push and costly and not GATED.search(job_if):
            if not all(GATED.search(x) for x in costly):
                kinds = sorted({k.lower() for x in costly for k in COSTLY.findall(x)})
                fails.append(f"job `{name}` runs {' and '.join(kinds)} on every push "
                             f"(x{10 if 'macos' in kinds else 2} minutes): start it by hand, "
                             f"on a tag, or choose the runner by `github.event_name`")
        if not any(_indent(x) == ind + 2 and x.strip().startswith("timeout-minutes:") for x in code):
            if not any(x.strip().startswith("uses:") and _indent(x) == ind + 2 for x in code):
                reports.append(f"job `{name}` has no `timeout-minutes` (a hung job runs six hours)")

    for k, ln in enumerate(lines):
        if re.search(r"uses:\s*actions/upload-artifact@", ln):
            # The step's keys sit beside `uses:` (`with:` among them), the ones under
            # `with:` deeper; the step ends at the next `- ` or anything shallower.
            key_ind = ln.index("uses:")
            mine = []
            for x in lines[k + 1:]:
                if not x.strip() or x.lstrip().startswith("#"):
                    continue
                if _indent(x) < key_ind or (_indent(x) == key_ind - 2 and x.lstrip().startswith("- ")):
                    break
                mine.append(x)
            ret = next((x for x in mine if re.match(r"\s*retention-days\s*:", x)), None)
            if ret is None:
                fails.append(f"line {k + 1}: upload-artifact with no `retention-days` "
                             f"(kept 90 days against the account's storage)")
            else:
                v = re.search(r":\s*['\"]?(\d+)", ret)
                if v and int(v.group(1)) > MAX_RETENTION:
                    fails.append(f"line {k + 1}: upload-artifact kept {v.group(1)} days "
                                 f"(at most {MAX_RETENTION})")

    if _key(lines, "concurrency") is None and jobs(lines):
        reports.append("no `concurrency:` — a newer push does not cancel the run before it")
    if re.search(r"uses:\s*docker/build-push-action@", text) and \
            not re.search(r"DOCKER_BUILD_RECORD_UPLOAD\s*:\s*['\"]?false", text, re.I):
        reports.append("docker/build-push-action uploads a build-record artifact on every run "
                       "(set `DOCKER_BUILD_RECORD_UPLOAD: false`)")
    return fails, reports


def workflows(root):
    d = os.path.join(root, ".github", "workflows")
    return sorted(glob.glob(os.path.join(d, "*.yml")) + glob.glob(os.path.join(d, "*.yaml")))


def _help_only():
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(__doc__.strip())
        raise SystemExit(0)


def main():
    _help_only()
    places = []
    if sys.argv[1:]:
        places = [(os.path.basename(os.path.abspath(p)), os.path.abspath(p)) for p in sys.argv[1:]]
    else:
        try:
            with open(fr.registry_path(), encoding="utf-8") as f:
                reg = json.load(f)
        except FileNotFoundError:
            print("No registry yet — a fresh checkout. Nothing declares a place to check.")
            return 0
        except Exception as e:
            print(f"no registry to read: {e}")
            return 1
        places = [(name, root) for name, root, _e in fr.registry_roots(reg) if os.path.isdir(root)]

    files = nfail = nrep = 0
    out = []
    for name, root in places:
        for wf in workflows(root):
            files += 1
            fails, reports = check_file(wf)
            if fails or reports:
                out.append((name, os.path.relpath(wf, root), fails, reports))
                nfail += len(fails)
                nrep += len(reports)

    print(f"Checked {files} workflows in {len(places)} places.\n")
    if not out:
        print("✓ nothing here spends the account's Actions minutes or storage carelessly.")
        return 0
    for name, rel, fails, reports in out:
        print(f"  {name} · {rel}")
        for f in fails:
            print(f"      ✗ {f}")
        for r in reports:
            print(f"      · {r}")
    print(f"\n{nfail} failures, {nrep} reports. A deliberate exception is a comment in the "
          f"workflow: `# repo-guards: actions-budget ok — <why>`.")
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
