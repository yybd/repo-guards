"""The module's name before the rename to RepoGuards (0.2.0) — kept for one release.

The app factory 0.4.0 imports `grove_repo` by name; this keeps it working until it
imports `guards_repo`. New code imports `guards_repo`.
"""
from guards_repo import *                                   # noqa: F401,F403
from guards_repo import guards_root as grove_root            # noqa: F401
