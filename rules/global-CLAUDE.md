*English · [עברית](global-CLAUDE.he.md)*

# Working rules — every project

## Commits

**Commit in the repo the change belongs to, before the turn ends.** A change left
uncommitted in a repo you are not standing in appears in no `git status` you will look
at, and is therefore forgotten.

**One logical change = one commit per repo.** Work that touches two repos is two
commits, not one. There is no cross-repo commit. Each message is written in the terms of
the repo it lands in.

**Order between repos:** the content before whatever points at it — a changelog before
the release that ships it. A half-finished cross-repo change is always discovered
through the broken reference, never through the missing content.

## Pushing

**Push only when asked.**

**Before every `push` — read `git log @{u}..HEAD`.** If it contains commits that were
not created in this session, say so and get approval before pushing. A `push` publishes
a **whole branch**, not your last commit — every commit waiting on it goes out, including
ones another session or another person made, and none of it can be taken back.

**`push` is not `deploy`.** Never report "the site is updated" on the strength of a
push. Whether a push deploys anything is a fact about that project — check it there,
and say "pushed", not "live", until you have.

## Working across projects

**File access crosses directories; loading does not.** An absolute path reaches any
repo, but a project's skills, memory and transcripts load **only** when the session
stands in it (`~/.claude/projects/<cwd>/`). So real work in another project is done
**from inside it** — `change_directory`, or a task launched with its `cwd` — and not
through an absolute path from outside.

A fact learned about project A while sitting in project B is written to B's memory and
will never be recalled while working on A. This cannot be repaired afterwards, which
makes it a consideration in choosing where the session stands rather than a footnote.

The full account — what is protected, who owns what, and when to move a session — is in
`$REPO_GUARDS/README.md`.

## Anchors — why it says `$SITE` and not a path

**No skill names the path of any particular machine.** `$SITE/content`, `$REPO_GUARDS`,
`$KEYS_ROOT`, and every registry entry by its own name — these are **real environment
variables**, written into
`~/.claude/settings.json` from the registry by every
`python3 $REPO_GUARDS/tools/deploy.py`. On a command line they expand by themselves; to
see them all: `env | grep -E "DEV_ROOT|REPO_GUARDS|KEYS_|SITE"`.

**The registry says how the tree is shaped, the machine says where it sits.** A root is
written relative (`<data-repo>`, `web/<site>`), and the base is derived from where RepoGuards
itself sits. The same registry therefore works on a second machine without
changing a word — which is why writing a machine path such as `~/Developer/…` into a
skill is a regression, and `tools/tests/test_portability.py` fails on it.
