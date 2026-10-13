*English · [עברית](global-CLAUDE.he.md)*

# Working rules — every project

## Language

**Answer the user in Hebrew — always.** Every reply, summary, question and
report is written in Hebrew, whatever language the request, the tool output or
the earlier turns were in. Code, identifiers, commit messages, file and command
names stay as they are (commit messages in English, per the rules below).
Documents follow the language of the project they land in.

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
a **whole branch**, not your last commit: on 2026-09-07 this sent 20 commits in an app
repo, 18 of them older than the session, and 5 in the hub, most of them the owner's own
work.

**`push` is not `deploy`.** Never report "the site is updated" on the strength of a
push. In at least one project this is explicit — that repo's own memory says
`push deploys nothing`.

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
`$GROVE/README.md`.

## Anchors — why it says `$SITE` and not a path

**No skill names the path of any particular machine.** `$SITE/content`, `$GROVE`,
`$KEYS_ROOT`, and every registry entry by its own name — these are **real environment
variables**, written into
`~/.claude/settings.json` from the registry by every
`python3 $GROVE/tools/deploy.py`. On a command line they expand by themselves; to
see them all: `env | grep -E "DEV_ROOT|GROVE|KEYS_|SITE"`.

**The registry says how the tree is shaped, the machine says where it sits.** A root is
written relative (`<data-repo>`, `web/<site>`), and the base is derived from where grove
itself sits. The same registry therefore works on a second machine without
changing a word — which is why writing a machine path such as `~/Developer/…` into a
skill is a regression, and `tools/tests/test_portability.py` fails on it.
