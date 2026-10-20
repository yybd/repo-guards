"""Branch pipeline for check_actions.py.

    python3 tools/tests/test_check_actions.py

Each case is a workflow written to a throwaway file, and asserts the exact number of
failures and reports — not merely that something was said. The cases are the shapes
found on 2026-10-20, when the account's Actions minutes ran out, and the fixed shape of
each: a checker has to stay quiet on the fix as surely as it speaks on the fault.
"""
import os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import check_actions as ca                                # noqa: E402

CASES = [
    ("every push on three systems", """
on:
  push:
  pull_request:
jobs:
  test:
    strategy:
      matrix:
        os: [macos-latest, windows-latest, ubuntu-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
""", 1, 2),
    ("the runner chosen by the event", """
on:
  push:
    paths-ignore: ['**.md']
  workflow_dispatch:
concurrency:
  group: t-${{ github.ref }}
  cancel-in-progress: true
jobs:
  test:
    timeout-minutes: 15
    strategy:
      matrix:
        os: ${{ fromJSON(github.event_name == 'push' && '["ubuntu-latest"]' || '["macos-latest", "windows-latest"]') }}
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
""", 0, 0),
    ("windows on a tag or by hand, artifact kept 90 days", """
on:
  workflow_dispatch:
  push:
    tags: ['v*']
concurrency:
  group: w
  cancel-in-progress: true
jobs:
  build:
    runs-on: windows-latest
    timeout-minutes: 60
    steps:
      - uses: actions/upload-artifact@v4
        with:
          name: x
          path: a.exe
""", 1, 0),
    ("retention before the name, and over the limit", """
on: [workflow_dispatch]
concurrency: {group: w}
jobs:
  build:
    runs-on: windows-latest
    timeout-minutes: 60
    steps:
      - name: up
        uses: actions/upload-artifact@v4
        with:
          retention-days: 3
          name: x
      - uses: actions/upload-artifact@v4
        with:
          name: y
          retention-days: 30
""", 1, 0),
    ("windows on pushes to release branches only", """
on:
  workflow_dispatch:
  push:
    branches:
      - 'release/**'
concurrency: {group: w}
jobs:
  build:
    runs-on: windows-latest
    timeout-minutes: 90
    steps:
      - uses: actions/checkout@v4
""", 0, 0),
    ("windows on every push to main", """
on:
  push:
    branches: [main]
concurrency: {group: w}
jobs:
  build:
    runs-on: windows-latest
    timeout-minutes: 90
    steps:
      - uses: actions/checkout@v4
""", 1, 0),
    ("docker without the build record switch", """
on: [workflow_dispatch]
concurrency: {group: d}
jobs:
  image:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: docker/build-push-action@v6
""", 0, 1),
    ("a deliberate exception", """
# repo-guards: actions-budget ok — public repository
on: push
jobs:
  check:
    runs-on: macos-latest
""", 0, 0),
]


def main():
    fails = 0
    with tempfile.TemporaryDirectory(prefix="actions-check-") as d:
        for label, text, want_f, want_r in CASES:
            p = os.path.join(d, "wf.yml")
            open(p, "w", encoding="utf-8").write(text.lstrip("\n"))
            f, r = ca.check_file(p)
            ok = (len(f), len(r)) == (want_f, want_r)
            print(f"{'✓' if ok else '✗'} {label}: {len(f)} failures, {len(r)} reports"
                  + ("" if ok else f" (want {want_f}, {want_r})\n      {f}\n      {r}"))
            fails += not ok
    print(f"\n{len(CASES) - fails}/{len(CASES)} cases")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
