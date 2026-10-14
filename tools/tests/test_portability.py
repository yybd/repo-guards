"""Would this repo work on a second machine?

    python3 tools/tests/test_portability.py

The question is not rhetorical and it is not answerable by reading. It is answered by
building a second machine — a tree under a different base, with RepoGuards in it and
the other repos beside it — and asking the real code where things are.

What "portable" means here, precisely: **the registry says how the tree is SHAPED, and
the machine says where it sits.** `app-hub`, `web/<site>`, `<apps>/<app>` are the
shape; `/Users/someone/Developer` and `/tmp/other/dev` are two places to put it. Nothing
in the repo may name the second half.

An absolute root stays absolute on purpose — a repo genuinely outside the tree, and the
form every pipeline uses to point at a throwaway directory.
"""
import json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.path.join(REPO, "plugins", "repo-guards", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)
import guards_repo as fr                                    # noqa: E402


def main():
    base = os.path.realpath(tempfile.mkdtemp(prefix="repo-guards-machine2-"))
    fails = 0

    def check(ok, label, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"{'✓' if ok else '✗'} {label}" + (f"   [{detail}]" if detail and not ok else ""))

    try:
        # The shipped file is the EXAMPLE: registry.json is machine data and is not in
        # the repo, so a fresh clone has only the template — and the template is exactly
        # what has to be portable, since it is what every new tree starts from.
        src = os.path.join(REPO, "tools", "registry.example.json")
        if not os.path.exists(src):
            src = os.path.join(REPO, "tools", "registry.json")
        with open(src, encoding="utf-8") as f:
            reg = json.load(f)

        # --- the shape, as the registry writes it ---
        print("-- what the registry says --")
        # `_`-prefixed keys are prose and worked examples, skipped by the code that reads
        # the registry — so real entries are preferred here for the same reason. But the
        # SHIPPED registry is all examples, and they carry exactly the shape this test is
        # about: on a fresh clone they are the only roots there are, and a test that
        # passes only after someone registers a repo is a test that never runs on the
        # machine it matters most on.
        real = []
        for group, key in (("projects", "root"), ("apps", "repo")):
            for name, entry in (reg.get(group) or {}).items():
                if (not name.startswith("_") and isinstance(entry, dict)
                        and isinstance(entry.get(key), str)):
                    real.append((name, entry[key]))
        if not real:
            # The SHIPPED registry is all examples, and the code that reads it skips
            # `_`-prefixed names on purpose. Promoting them here is what lets the test run
            # on a fresh clone at all — and a test that passes only after someone registers
            # a repo is a test that never runs on the machine it matters most on.
            for group, key in (("projects", "root"), ("apps", "repo")):
                g = reg.get(group) or {}
                for name in [n for n in list(g) if n.startswith("_") and isinstance(g[n], dict)
                             and isinstance(g[n].get(key), str)]:
                    g[name.lstrip("_")] = g.pop(name)
                    real.append((name.lstrip("_"), g[name.lstrip("_")][key]))
        written = real
        check(bool(written), f"{len(written)} roots in the registry")
        absolute = [(n, v) for n, v in written if os.path.isabs(os.path.expanduser(v))]
        check(not absolute, "no root is an absolute path",
              ", ".join(f"{n}={v}" for n, v in absolute))

        # --- build the second machine: RepoGuards, and the other repos beside it ---
        print("\n-- a second machine --")
        m2 = os.path.join(base, "dev")
        f2 = os.path.join(m2, "repo-guards")
        os.makedirs(os.path.join(f2, ".claude-plugin"), exist_ok=True)
        os.makedirs(os.path.join(f2, "tools"), exist_ok=True)
        shutil.copy(os.path.join(REPO, ".claude-plugin", "marketplace.json"),
                    os.path.join(f2, ".claude-plugin", "marketplace.json"))
        # The registry as the code will read it — promoted examples included, which
        # `shutil.copy` of the shipped file would not carry.
        with open(os.path.join(f2, "tools", "registry.json"), "w", encoding="utf-8") as f:
            json.dump(reg, f, indent=2, ensure_ascii=False)
        for _name, rel in written:
            os.makedirs(os.path.join(m2, rel), exist_ok=True)

        env = dict(os.environ, REPO_GUARDS_ROOT=f2)
        # Both overrides have to go, not just one: a REPO_GUARDS_REGISTRY in the caller's
        # environment would make the second machine read THIS machine's registry, and the
        # test would report zero roots found while nothing was wrong. It only shows up for
        # someone whose registry is empty — which is exactly the mechanics-only user.
        env.pop("REPO_GUARDS_DEV_ROOT", None)
        env.pop("REPO_GUARDS_REGISTRY", None)
        code = (
            "import json,os,sys;sys.path.insert(0,%r);import guards_repo as fr;"
            "reg=json.load(open(fr.registry_path()));"
            "print(json.dumps({'base':fr.dev_base(),"
            "'roots':{n:r for n,r,_ in fr.registry_roots(reg)}}))" % SCRIPTS
        )
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           timeout=30, env=env, cwd=base)
        check(p.returncode == 0, "the code ran against the second machine", p.stderr.strip()[:120])
        if p.returncode != 0:
            return 1
        got = json.loads(p.stdout)

        check(got["base"] == m2, "the base is derived from where RepoGuards sits, with no configuration", got["base"])
        check(len(got["roots"]) == len(written), f"all {len(written)} roots were found",
              str(len(got["roots"])))
        strays = {n: r for n, r in got["roots"].items() if not r.startswith(m2 + os.sep)}
        check(not strays, "every root resolves into the second machine", str(strays)[:120])
        check(all(os.path.isdir(r) for r in got["roots"].values()),
              "and every one of them exists there")
        here = {n: r for n, r, _ in fr.registry_roots(reg)}
        check(all(not r.startswith(m2) for r in here.values()),
              "and meanwhile, here they still resolve here")

        # --- nothing a skill hands to a session may name THIS machine ---
        # The scripts are exempt on purpose: a last-resort default has to say something,
        # and `ENV["APP_HUB"] || $DEV_ROOT/app-hub` is a fallback, not an assumption.
        # What a skill TEACHES must be portable, because it is copied to the next
        # machine verbatim and read as instruction.
        print("\n-- what the skills say --")
        import glob
        offenders = []
        for f in glob.glob(os.path.join(REPO, "plugins", "**", "*"), recursive=True):
            if not f.endswith((".md", ".json")):
                continue
            try:
                txt = open(f, encoding="utf-8").read()
            except Exception:
                continue
            for needle in ("~/Developer", "/Users/"):
                if needle in txt:
                    offenders.append((os.path.relpath(f, REPO), needle))
        check(not offenders, "no skill names the path of any particular machine",
              "; ".join(f"{f}:{n}" for f, n in offenders[:3]))

        # --- $SITE is optional, and that has to be true in both directions ---
        print("\n-- a site, when there is one and when there is not --")
        check(fr.site_root({"projects": {}}) is None,
              "a registry with no site → $SITE unset")
        check("SITE" not in fr.anchors({"projects": {}}),
              "and the anchor is simply absent, not empty")
        marked = {"projects": {"w": {"root": "/tmp", "site": True}}}
        check(fr.site_root(marked) == os.path.realpath("/tmp"),
              "the `site: true` flag names it")
        check(fr.site_root({"projects": {"w": {"root": "/tmp", "role": "the website"}}}) is None,
              "a role string is NOT a guess — only the flag counts")

        # --- the escape hatches, which must keep working ---
        print("\n-- what stays absolute on purpose --")
        check(fr.resolve_root("/tmp") == os.path.realpath("/tmp"),
              "an absolute path is honoured as it is")
        check(fr.resolve_root("~") == os.path.realpath(os.path.expanduser("~")),
              "~ resolves to home, not to the base")
        p2 = subprocess.run(
            [sys.executable, "-c",
             "import sys;sys.path.insert(0,%r);import guards_repo as fr;print(fr.dev_base())" % SCRIPTS],
            capture_output=True, text=True, timeout=30,
            env=dict(os.environ, REPO_GUARDS_DEV_ROOT=m2))
        check(p2.stdout.strip() == m2, "REPO_GUARDS_DEV_ROOT overrides the derivation", p2.stdout.strip())

        # --- a base the registry NAMES, for a tree RepoGuards does not sit inside ---
        # The derivation assumes RepoGuards is one of the repos in the tree. That is true for
        # whoever built it here and false for anyone who adds it as a marketplace from
        # elsewhere — their roots would resolve beside RepoGuards instead of beside their work.
        print("\n-- a base that is declared rather than derived --")
        elsewhere = os.path.realpath(tempfile.mkdtemp(prefix="repo-guards-elsewhere-"))
        os.makedirs(os.path.join(elsewhere, "sub", "repo"), exist_ok=True)

        def ask(reg_body, expr="fr.dev_base()"):
            path = os.path.join(base, "declared-base.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(reg_body, f)
            env = {k: v for k, v in os.environ.items() if k != "REPO_GUARDS_DEV_ROOT"}
            env["REPO_GUARDS_REGISTRY"] = path
            r = subprocess.run(
                [sys.executable, "-c",
                 "import sys;sys.path.insert(0,%r);import guards_repo as fr;print(%s)"
                 % (SCRIPTS, expr)],
                capture_output=True, text=True, timeout=30, env=env)
            return r.stdout.strip()

        got = ask({"base": elsewhere, "projects": {"one": {"root": "sub/repo"}}})
        check(got == elsewhere, "a `base` in the registry is honoured", got)
        got = ask({"base": elsewhere}, 'fr.resolve_root("sub/repo")')
        check(got == os.path.join(elsewhere, "sub", "repo"),
              "and every relative root resolves against it", got)
        got = ask({"base": os.path.join(elsewhere, "no-such-dir")})
        check(got == "None", "a base naming a directory that is not there resolves to "
                             "nothing, rather than quietly to somewhere else", got)
        got = ask({"projects": {}})
        check(got and got != "None", "no base named — the derivation still answers", got)
        shutil.rmtree(elsewhere, ignore_errors=True)

        check(fr.resolve_root("") is None and fr.resolve_root(None) is None,
              "an empty value does not resolve to the base itself")
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print(f"\n{'all checks passed' if not fails else str(fails) + ' failed'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
