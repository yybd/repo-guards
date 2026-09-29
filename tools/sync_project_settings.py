#!/usr/bin/env python3
"""Write each registered repo's .claude/settings.json from the registry's `tracks`.

The tracks are installed once, on the machine, and until now that meant they
loaded EVERYWHERE — in the website, in an unrelated repo, in grove itself. The
README decides where a skill belongs by asking "which directory is the session standing
in when I need it?", but nothing enforced the answer: `enabledPlugins` in the user's
settings is one global switch per track.

Claude Code resolves that key across scopes (user < project < local < flag < policy), so
a project's own .claude/settings.json can turn a track on that the user's settings never
mention. That is the lever this script pulls. The registry says which tracks each repo
gets; this turns those arrays into the files that make it true.

    python3 tools/sync_project_settings.py           write the settings files
    python3 tools/sync_project_settings.py --check   report drift, change nothing

It is deliberately narrow: it owns only the `grove@grove` keys inside
`enabledPlugins`, and leaves every other key in those files — and every plugin from
another marketplace — exactly as it found it. The repos are under git, which is the
backup; what this must not do is quietly drop a setting git would then record as ours.

The track names are checked against the plugins actually on disk. Grove rule is to
count rather than copy, and a registry that names a track nobody ships would produce a
settings file that silently enables nothing.
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
REGISTRY = os.environ.get("GROVE_REGISTRY") or os.path.join(HERE, "registry.json")
PLUGINS = os.environ.get("GROVE_PLUGINS") or os.path.join(REPO, "plugins")
MARKETPLACE = os.environ.get("GROVE_MARKETPLACE") or "grove"
# The registry says how the tree is SHAPED; where it sits is this machine's business,
# and only grove_repo knows how to join the two.
# grove_repo comes from THIS checkout, not from PLUGINS: when another marketplace runs
# this script against its own tree, PLUGINS is that tree's plugins and holds no grove.
sys.path.insert(0, os.path.join(REPO, "plugins", "grove", "hooks", "scripts"))
from grove_repo import resolve_root                       # noqa: E402


def real(p):
    return os.path.realpath(os.path.expanduser(p))


def pretty(p):
    home = os.path.expanduser("~")
    return "~" + p[len(home):] if p.startswith(home + os.sep) else p


def shipped_tracks():
    """Track names that exist as plugins on disk — counted, not trusted from a list."""
    try:
        return {n for n in os.listdir(PLUGINS)
                if os.path.isfile(os.path.join(PLUGINS, n, ".claude-plugin", "plugin.json"))}
    except Exception:
        return set()


def targets(reg):
    """(name, root, tracks) for every registry entry that has a repo on disk.

    Roots come back through grove_repo.resolve_root, which is the only place that
    knows a relative root is relative to the tree's base. Four files used to expand
    them four ways; one of them would have to be found and fixed on a second machine.
    """
    out = []
    for name, proj in (reg.get("projects") or {}).items():
        if name.startswith("_") or not proj.get("root"):
            continue
        out.append((name, resolve_root(proj["root"]), list(proj.get("tracks") or [])))
    for name, app in (reg.get("apps") or {}).items():
        if name.startswith("_") or not app.get("repo"):
            continue
        out.append((name, resolve_root(app["repo"]), list(app.get("tracks") or [])))
    return sorted(out)


def desired(tracks, shipped):
    """Only the tracks this marketplace actually ships.

    A registry entry may name tracks that come from somewhere else — grove is one
    marketplace among the ones a machine has installed, and a track it does not ship is
    not its business to enable. `plan` touches only `@grove` keys for the same reason,
    so the two marketplaces write the same file without either erasing the other.
    """
    return {f"{t}@{MARKETPLACE}": True for t in tracks if t in shipped}


def read_settings(path):
    if not os.path.exists(path):
        return {}, True
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), False
    except Exception as e:
        raise SystemExit(f"✗ {pretty(path)} is not readable JSON ({e}).\n"
                         f"  Fix or move it; this script will not overwrite a file it cannot parse.")


def plan(path, tracks, shipped):
    """(current_ours, wanted, merged_settings). current_ours is only OUR keys."""
    data, _ = read_settings(path)
    enabled = dict(data.get("enabledPlugins") or {})
    ours = {k: v for k, v in enabled.items() if k.endswith("@" + MARKETPLACE)}
    wanted = desired(tracks, shipped)
    for k in ours:
        enabled.pop(k)
    enabled.update(wanted)
    merged = dict(data)
    if enabled:
        merged["enabledPlugins"] = enabled
    else:
        merged.pop("enabledPlugins", None)
    return ours, wanted, merged


def write(path, merged):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
        f.write("\n")


USER_SETTINGS = os.environ.get("GROVE_SETTINGS") or os.path.expanduser(
    "~/.claude/settings.json")


def sync_anchors(reg, check):
    """Put the anchor variables where a shell can see them: the MACHINE-LOCAL settings.

    A skill writes `$SITE/content` because it cannot know this machine's paths. For
    that to be more than a nice idea, something has to define the variable here — and
    the right file is `~/.claude/settings.json`, which is per-machine by definition and
    is not in any repo. The registry says the shape, this writes where it landed.

    (path, before, after) so the caller can report; nothing else in the file is touched.
    """
    from grove_repo import anchors
    want = anchors(reg)
    data, _ = read_settings(USER_SETTINGS)
    env = dict(data.get("env") or {})
    before = {k: env.get(k) for k in want}
    if all(env.get(k) == v for k, v in want.items()):
        return None
    if not check:
        env.update(want)
        merged = dict(data)
        merged["env"] = env
        write(USER_SETTINGS, merged)
    return USER_SETTINGS, before, want


def main():
    ap = argparse.ArgumentParser(description="Sync project settings from the registry.")
    ap.add_argument("--check", action="store_true", help="report drift, change nothing")
    a = ap.parse_args()

    try:
        reg = json.load(open(REGISTRY, encoding="utf-8"))
    except Exception as e:
        sys.exit(f"✗ the registry could not be read ({e}).")

    shipped = shipped_tracks()
    if not shipped:
        sys.exit(f"✗ no plugins found in {pretty(PLUGINS)}. Nothing was written.")

    rows, drift, unknown = [], 0, []
    for name, root, tracks in targets(reg):
        bad = [t for t in tracks if t not in shipped]
        if bad:
            unknown.append((name, bad))
        if not os.path.isdir(root):
            rows.append(("?", name, f"{pretty(root)} — the directory does not exist"))
            continue
        path = os.path.join(root, ".claude", "settings.json")
        ours, wanted, merged = plan(path, tracks, shipped)
        if ours == wanted:
            rows.append(("=", name, f"{len(wanted)} tracks, already in sync"))
            continue
        drift += 1
        added = sorted(set(wanted) - set(ours))
        removed = sorted(set(ours) - set(wanted))
        note = ", ".join([f"+{k.split('@')[0]}" for k in added] +
                         [f"-{k.split('@')[0]}" for k in removed]) or "different values"
        if a.check:
            rows.append(("✗", name, note))
        else:
            write(path, merged)
            rows.append(("→", name, note))

    moved = sync_anchors(reg, a.check)
    if moved:
        _path, before, want = moved
        new = [k for k, v in want.items() if before.get(k) != v]
        rows.append(("✗" if a.check else "→", "anchors",
                     f"{len(new)} variables in {pretty(USER_SETTINGS)} ($" + ", $".join(sorted(new)[:4]) + "…)"))
        drift += 1

    print(f"registry: {pretty(REGISTRY)}")
    print(f"tracks on disk ({len(shipped)}): {', '.join(sorted(shipped))}\n")
    for mark, name, note in rows:
        print(f"  {mark} {name:<20} {note}")

    if unknown:
        # Reported, never failed on. A track this marketplace does not ship is either
        # another marketplace's — which is the normal case once a machine has more than
        # one — or a typo, and nothing here can tell those apart. Failing would break
        # every mixed installation to catch the rarer of the two.
        print()
        for name, bad in unknown:
            print(f"  · {name}: not shipped here — {', '.join(bad)}")
        print("    (another marketplace's track, or a typo. Nothing was written for them.)")

    print()
    if not drift:
        print("Everything is in sync. Nothing was changed.")
        return 0
    if a.check:
        print(f"{drift} repos differ from the registry. To sync:\n"
              f"  python3 {pretty(os.path.join(HERE, 'sync_project_settings.py'))}")
        return 1
    print(f"{drift} repos updated. The tracks load there from the next session.\n"
          "Each such change is a commit in its own repo — the file belongs to it, not to grove.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
