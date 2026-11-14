# Independent local MVP preview

This is a disposable evidence-exploration tool, not the team production frontend (#14/#43).
It uses only Python 3.11+ standard library and local browser assets. No install, API, account,
CDN, token or external quota is needed. The server exposes an explicit file allowlist, never
the repository root, and binds only `127.0.0.1`. Do not expose it as a public service.

## Start

From the repository root:

```powershell
python tools/local-mvp-preview/serve.py
```

Open **http://127.0.0.1:8765**. Stop with Ctrl+C. If Windows `python` opens the Store instead,
use the installed interpreter, for example on this machine:

```powershell
& "$env:LOCALAPPDATA/Programs/Python/Python312/python.exe" tools/local-mvp-preview/serve.py
```

Use `--port 8766` if needed. Drag to pan; use zoom/arrow buttons and Reset view.
Toggle Draw area and drag a rectangle, or use labeled keyboard-accessible sliders.
The yellow midpoint is approximate display geometry, not an API call or polygon average.
Explore dataset cards, optional hypothetical current crops and draft priorities. Those inputs
stay in memory, are not saved, and do not generate recommendations. Reload resets them.

The separate fixed Alajuela response shows existing API output: real cached NASA POWER
2001–2025 monthly normals, **mock soil**, approximate crop traits and heuristic ranking.
It is never relabeled as a San Carlos result and does not respond to the scenario controls.
Pineapple is an unsupported hypothetical report, not an identified crop or recommendation.
No API integration is enabled: its current data mode could trigger live calls.

## Update safely after team merges

The server reads the tracked images and JSON examples directly; no copied evidence to rebuild.
It uses `no-store` responses. Stop it first, inspect `git status --short` and keep a clean tree;
commit intended work or handle changes explicitly before merging. Do not reset or overwrite.
Once this preview is committed on its feature branch:

```powershell
git switch feat/local-mvp-preview
git fetch origin
git merge origin/main
```

Fetching/merging is an explicit user operation; the preview never performs it automatically.
If conflicts occur, resolve them deliberately (or `git merge --abort` to undo that merge).
Rerun the tests below, restart the server and refresh the browser. After fixture/contract
changes, also review labels, source periods and schema assumptions; unknown example shapes
must remain unavailable rather than receive invented fallback values. This preview does
not regenerate examples, change `mvp.yaml`, change the API contract or replace backend tests.

## Checks

```powershell
python tools/local-mvp-preview/test_preview.py
node tools/local-mvp-preview/test_model.mjs
node --check tools/local-mvp-preview/app.js
git diff --check
```

The HTTP test starts and stops a temporary loopback server, checking allowlisted files,
CSP and rejection of secret/traversal/directory paths; it never opens secret files.
Node is needed only for model tests, not to run the preview. Browser/visual accessibility
checks remain separate from these tests. Backend CI and `make check` are still required
before a PR. Rollback: remove `tools/local-mvp-preview/` and the root README preview link;
no backend or production frontend behavior changes.
