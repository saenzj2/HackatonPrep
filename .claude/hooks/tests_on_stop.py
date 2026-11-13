#!/usr/bin/env python3
"""Stop hook: when Claude finishes a turn with uncommitted changes in backend/, run the fast tests.

Exit 0 = let Claude stop. Exit 2 = tests failed, output is sent back to Claude to fix.
Never blocks twice in a row (stop_hook_active) to avoid loops.
Stdlib only and Python 3.8+ compatible.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

MAX_OUTPUT = 4000


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = {}
    if payload.get("stop_hook_active"):
        return 0

    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".").resolve()
    backend = project / "backend"
    pytest = backend / ".venv" / "bin" / "pytest"
    if not pytest.exists():
        return 0

    changed = subprocess.run(
        ["git", "status", "--porcelain", "--", "backend/"],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if not changed:
        return 0

    result = subprocess.run(
        [str(pytest), "-q", "-x", "-m", "not slow and not network", "--no-header"],
        cwd=backend,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if result.returncode not in (0, 5):  # 5 = no tests collected
        out = (result.stdout + result.stderr)[-MAX_OUTPUT:]
        sys.stderr.write("Fast tests failed after your changes in backend/. Fix them:\n" + out)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
