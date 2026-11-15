@AGENTS.md

# Claude Code specifics

Everything above applies. This section only adds what is specific to Claude Code.
Folder rules load automatically when you work in a folder: each `CLAUDE.md` there imports its
`AGENTS.md` (`backend/`, `backend/app/domain/`, `backend/app/integrations/`, `backend/app/api/`, `backend/tests/`).

## Skills (`.claude/skills/`)
| Command | Use when |
|---|---|
| `/explore-dataset <name or URL>` | Evaluating a dataset or API. Writes `backend/docs/sources/<name>.md` and saves a fixture. |
| `/new-source <name>` | Turning an explored dataset into an adapter + tests (NASA POWER pattern). |
| `/new-endpoint <description>` | Adding or changing an endpoint: contract → schemas → route → tests. |
| `/demo-check` | Before any demo or presentation: full checks + offline (`cached`) run. |

## Subagents (`.claude/agents/`)
- `nasa-data`: questions about NASA datasets, variables, units, resolution, coverage. Read-only plus web.
- `agro-logic`: review agronomic soundness of `backend/app/domain/` or of `mvp.yaml` choices.
- `reviewer`: review the branch diff against AGENTS.md / Definition of Done before opening a PR.

## Hooks and permissions (`.claude/settings.json`)
- After every Edit/Write of a `backend/**/*.py` file, ruff formats and fixes it automatically.
- When you finish a turn that changed `backend/`, fast tests run. If they fail you'll be asked to fix them.
- `.env` files are unreadable by design; `rm -rf`, force-push and `reset --hard` remain denied.
  `git add` and `git commit` are subject to the active runtime permission rules; authorization in
  conversation does not bypass a permission prompt or denial.
- Personal overrides go in `.claude/settings.local.json` (gitignored).

## Working style
- Before writing any `raise`, `except` or error response, follow `backend/docs/errors.md`.
- Run `make check` before saying a task is done. Report failures honestly.
- Parallel sessions: use a git worktree per task (`git worktree add ../hp-<task> -b feat/<task>`).
- Ask before changing `mvp.yaml`, the API contract or scoring constants. Those are team decisions.
- Commit, push or open a PR only when the user explicitly authorizes that operation, and follow
  the repository branch, review and CI rules. Never bypass runtime permission checks. Merge remains
  a separate user decision; do not add AI attribution to commits.
