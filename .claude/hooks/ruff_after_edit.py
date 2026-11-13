#!/usr/bin/env python3
"""PostToolUse hook: ruff format + fix the backend .py file Claude just edited.

Exit 0 = fine (silent). Exit 2 = leftover lint errors, sent back to Claude to fix.
Stdlib only and Python 3.8+ compatible: it may run under the system python3, not the venv.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".").resolve()
    backend = project / "backend"
    path = Path(file_path).resolve() if file_path else None
    if path is None or path.suffix != ".py" or backend not in path.parents or not path.exists():
        return 0

    ruff = backend / ".venv" / "bin" / "ruff"
    if not ruff.exists():
        return 0  # not set up yet (make setup); pre-commit/CI will still catch it

    subprocess.run([str(ruff), "format", "--quiet", str(path)], cwd=backend, check=False)
    result = subprocess.run(
        [str(ruff), "check", "--fix", "--quiet", "--output-format", "concise", str(path)],
        cwd=backend,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write("ruff found issues it could not auto-fix:\n" + result.stdout + result.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
