# Deploy

**Live:** https://terracosmos.space (the app is at `/app/` and the API docs at `/docs`).

One Railway service runs the API and the frontend. It's built from the root `Dockerfile`.

| URL | What |
|---|---|
| `https://terracosmos.space/` | Redirects to the app |
| `/app/` | Frontend: `frontend/` by default, or the React build from `frontend-app/` (see `FRONTEND_DIR`) |
| `/docs` | Swagger UI for the API |
| `/health` | Health check (Railway uses it before switching traffic) |
| `https://harvest-production-3c6bc064.up.railway.app` | Same service on Railway's own domain (fallback) |
| `https://www.terracosmos.space/*` | 301 redirect to `https://terracosmos.space/*` |

Production runs in **`cached` mode**: real NASA POWER, OpenLandMap, SMAP and EcoCrop data from the
committed snapshot (`backend/app/cache/snapshots/`). It never calls external APIs and needs **no
data-source keys**. Demo points: San Carlos (11.0, −84.6) and Alajuela (10.0, −84.2). Any other point
answers `503 cache_miss`. To add a point, fetch it once locally in `live` mode, run
`make cache-snapshot` and open a PR.

## How a team member deploys (all 6 of us)

You don't need a Railway or Cloudflare account.

- **Automatic:** merge a PR to `main`. When CI passes on `main`, the **Deploy** workflow publishes
  that exact commit.
- **Manual (re-deploy or demo a branch):** GitHub → **Actions** → **Deploy** → **Run workflow** →
  choose the branch → **Run workflow**. This skips CI, so only use a branch whose PR is green.
  From a terminal: `gh workflow run Deploy --ref <branch>`.
- **Check it:** the workflow summary shows the deployed commit and who deployed it. Then open
  https://terracosmos.space/health and https://terracosmos.space/app/.

**Roll back:** run **Deploy** manually on an earlier commit or branch (for example, a revert PR), or
use **Redeploy** on a previous deployment in the Railway dashboard (the Railway owner can do this).

## Run the production image locally

Use this when you change `Dockerfile`, `frontend/`, `frontend-app/` or startup code. You need Docker Desktop.
CI's `image` job runs the same build and a smoke test on every PR.

**Demo without internet:** the API and the React app work offline on cached data, but the map
(OpenStreetMap tiles) stays blank and the background videos (YouTube) don't play. Use the demo
field buttons instead of the map. Edits to `backend/data/*.json` reach the app only after a rebuild.

```bash
docker build -t harvest .
docker run --rm -p 8000:8000 harvest     # http://localhost:8000
docker run --rm -p 8000:8000 -e FRONTEND_DIR=/srv/frontend-app harvest   # with the React app
```

Without Docker, `make dev` serves the same thing: the app at http://localhost:8000/app/ and the API
docs at `/docs`. For the React app, run `make web-install` once, then `make dev` and `make web-dev`
in two terminals and open http://localhost:5173/app/ (Vite sends API calls to :8000).

## What is set up, and where

Owner of both accounts: Andres (GitHub `AndresACV`). Ask him for dashboard changes.

**GitHub** (repo → Settings → Secrets and variables → Actions)
- Secret `RAILWAY_TOKEN`: a Railway **project token** named `github-actions`, scoped to the
  `production` environment of this project only.
- Variable `RAILWAY_SERVICE` = `harvest`.

**Railway**: project `guardians-of-the-harvest`, environment `production`
- Service `harvest`. **No repo connected on purpose:** code arrives only through `railway up` from
  the Deploy workflow. Connecting the repo would deploy every push twice.
- Build and deploy settings live in the Railway dashboard (service `harvest` → **Settings**), not
  in the repo. Railway deprecated `railway.json` ("Config as Code"), which stops being read on
  2026-12-01, so we removed it. The settings are:
  - **Build:** Dockerfile. Railway always uses the root `Dockerfile` when it finds one.
  - **Healthcheck Path:** `/health`, with a **Healthcheck Timeout** of `120` s. Railway switches
    traffic only after it passes.
  - **Restart Policy:** `On Failure`, with **Max Retries** `3`.
  If the service is recreated, set these again by hand. Railway **stages** settings changes: they
  only take effect when you click **Deploy** on the "Apply N changes" bar, and that redeploys the
  service.
- Service variable **`PORT=8000`**. Both domains route to port 8000, and Railway would otherwise
  inject its own `PORT`. Don't remove it.
- Domains: the generated `harvest-production-3c6bc064.up.railway.app` and the custom
  `terracosmos.space` (verified). The Trial plan allows one custom domain, so `www` isn't in
  Railway.

**Cloudflare**: zone `terracosmos.space` (free plan, domain registered at Cloudflare)

| Type | Name | Value | Proxy |
|---|---|---|---|
| CNAME | `@` | the target Railway shows for the custom domain | DNS only (grey) |
| TXT | `_railway-verify` | Railway's verification value | — |
| A | `www` | `192.0.2.1` (placeholder, never receives traffic) | Proxied (orange) |

- Redirect rule "Redirect from WWW to root": `https://www.terracosmos.space/*` →
  `https://terracosmos.space/${1}`, 301, keeps the query string.
- Keep the apex CNAME **DNS only**: Railway issues and renews the HTTPS certificate itself.
- **SSL/TLS → Edge Certificates → Always Use HTTPS: on.** It upgrades `http://www` at the edge
  before the redirect rule runs.

**Cloudflare MCP for AI assistants (optional, per person).** Claude Code can read the zone through
Cloudflare's MCP server (`https://mcp.cloudflare.com/mcp`). Register it only in **local** scope
(`claude mcp add --scope local …`). Local scope keeps it in your user config, outside the repo.
**Never** add it to `.mcp.json`, `.claude/settings.json` or any file in the repo, and never paste
a token in a chat, issue or PR.
- To connect, you approve an OAuth consent screen in the browser ("Cloudflare MCP Server wants to
  access your account"). That screen requests broad access to the whole account, **including
  "Account API Tokens Write"**. A token with only `user:read` and `account:read` added was not
  enough to connect on its own.
- Use it only to read (DNS records, zone settings). DNS changes are still made by the account owner
  in the dashboard.
- When you're done, revoke it in **My Profile → Access Management → Connected Applications**.

## Pending

- [x] **Always Use HTTPS** is on (Cloudflare **SSL/TLS → Edge Certificates**). Checked with curl
      on 2026-11-15: `http://www.terracosmos.space/` gets a 301 to https from Cloudflare (no more
      522), then the www rule sends it to `https://terracosmos.space/`. `http://terracosmos.space`
      is redirected to https by Railway.
- [ ] **Railway plan: the Trial ends around 2026-12-15.** Railway doesn't show the date. It only
      says "30 days or $5.00 left" (on 2026-11-15: USD 5.00 left, USD 0.0006 used). The date
      assumes 30 days from 2026-11-15, and the trial ends sooner if the credit runs out. Then the
      account drops to the Free plan (USD 1/month credit).
      **Risk:** Railway's pricing page lists custom domains on Free as "1 trial, then 0". On Free,
      `terracosmos.space` stops working. Only `harvest-production-3c6bc064.up.railway.app` would be
      left, and only if the USD 1 credit covers the service. The link we submitted to Space Apps
      would break during judging. To prevent it, upgrade to Hobby (USD 5/month, includes USD 5 of
      usage, 2 custom domains per service) before the trial ends.
      **Team decision (2026-11-15):** we decide on **2026-12-03**, when Space Apps announces the
      Global Nominees. Local judging (around 16–22 Nov) ends well inside the trial.
      - **If we are nominated:** Andres upgrades to Hobby that day, by **2026-12-10** at the latest.
        Finalists (December) and winners (January) are judged after the trial ends, and the
        submitted link can't be changed.
      - **If we are not nominated:** we let the account drop to Free. The domain stays ours; it
        just stops serving the app.
- [ ] **After the submission:** revoke the Cloudflare MCP OAuth access (My Profile → Access
      Management → Connected Applications). It has write access to the whole account. On
      2026-11-15 it read the zone and confirmed the table above: Always Use HTTPS `on`, SSL `full`.
- [ ] Optional on Hobby: add `www.terracosmos.space` as a second custom domain in Railway, then
      drop the placeholder record and the redirect rule.
- [ ] A teammate follows the README on their own laptop (issue #12).

## Configuration

Set these in Railway → service `harvest` → **Variables** only if you need to change the defaults
baked into the image:

| Variable | Value | Notes |
|---|---|---|
| `PORT` | `8000` (set in Railway) | Must match the domains' target port. |
| `DATA_MODE` | `cached` (image default) | Keep `cached` for the demo. `live` needs Earth Engine credentials. |
| `FRONTEND_DIR` | `/srv/frontend` (image default) | `/srv/frontend-app` serves the React app. Unset it to serve the API only. |
| `CORS_ORIGINS` | localhost dev ports | Only needed if a frontend is hosted on another domain. |

Never put secrets in the `Dockerfile`, the workflows or the repo. `.dockerignore` keeps `.env`
files out of the image (checked: the image has no `.env`).

## Setting it up again from zero

Use this only if the project or the token is lost.

1. **Railway:** **New Project → Empty Project**, then **+ Create → Empty Service** named `harvest`.
   Don't connect a repo. Set the service variable `PORT=8000`. In **Settings → Networking**, choose
   **Generate Domain** (port 8000) and **Custom Domain** `terracosmos.space` (port 8000). In
   **Settings → Deploy**, set Healthcheck Path `/health`, timeout `120`, and Restart Policy
   `On Failure` with 3 retries.
2. **Railway:** **Project Settings → Tokens → Create Token**, environment `production`.
3. **GitHub** (needs repo write access):
   `gh secret set RAILWAY_TOKEN` (paste the token) and `gh variable set RAILWAY_SERVICE --body harvest`.
4. **Cloudflare:** create the records from the table above, using Railway's exact CNAME target and
   TXT value.
5. Run `gh workflow run Deploy --ref main`. The first build takes about 3 minutes.

Until `RAILWAY_TOKEN` and `RAILWAY_SERVICE` exist, the Deploy workflow is skipped with a warning
(it doesn't fail).
