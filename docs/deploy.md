# Deploy

**Live:** https://terracosmos.space (the app is at `/app/` and the API docs at `/docs`).

One Railway service runs the API and the frontend. It's built from the root `Dockerfile`.

| URL | What |
|---|---|
| `https://terracosmos.space/` | Redirects to the app |
| `/app/` | Frontend (static files from `frontend/`) |
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

Use this when you change `Dockerfile`, `frontend/` or startup code. You need Docker Desktop.

```bash
docker build -t harvest .
docker run --rm -p 8000:8000 harvest     # http://localhost:8000
```

Without Docker, `make dev` serves the same thing: the app at http://localhost:8000/app/ and the API
docs at `/docs`.

## What is set up, and where

Owner of both accounts: Andres (GitHub `AndresACV`). Ask him for dashboard changes.

**GitHub** (repo → Settings → Secrets and variables → Actions)
- Secret `RAILWAY_TOKEN`: a Railway **project token** named `github-actions`, scoped to the
  `production` environment of this project only.
- Variable `RAILWAY_SERVICE` = `harvest`.

**Railway**: project `guardians-of-the-harvest`, environment `production`
- Service `harvest`. **No repo connected on purpose:** code arrives only through `railway up` from
  the Deploy workflow. Connecting the repo would deploy every push twice.
- Build and health check come from `railway.json` (Dockerfile build, `/health`).
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

## Pending

- [ ] **`http://www.terracosmos.space` answers 522.** Turn on Cloudflare **SSL/TLS → Edge
      Certificates → Always Use HTTPS** so the edge upgrades to https before the www redirect.
      `http://terracosmos.space` already redirects to https (Railway does it).
- [ ] **Railway plan.** The account is on Trial (30 days or USD 5 of credit, from 2026-11-15).
      Afterwards it drops to the Free plan (USD 1/month credit, 0.5 GB RAM), which may stop the
      service. To keep the URL up through judging, upgrade to Hobby (USD 5/month, includes USD 5 of
      usage) before the trial ends. That's a team decision.
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
| `FRONTEND_DIR` | `/srv/frontend` (image default) | Unset it to serve the API only. |
| `CORS_ORIGINS` | localhost dev ports | Only needed if a frontend is hosted on another domain. |

Never put secrets in the `Dockerfile`, `railway.json` or the repo. `.dockerignore` keeps `.env`
files out of the image (checked: the image has no `.env`).

## Setting it up again from zero

Use this only if the project or the token is lost.

1. **Railway:** **New Project → Empty Project**, then **+ Create → Empty Service** named `harvest`.
   Don't connect a repo. Set the service variable `PORT=8000`. In **Settings → Networking**, choose
   **Generate Domain** (port 8000) and **Custom Domain** `terracosmos.space` (port 8000).
2. **Railway:** **Project Settings → Tokens → Create Token**, environment `production`.
3. **GitHub** (needs repo write access):
   `gh secret set RAILWAY_TOKEN` (paste the token) and `gh variable set RAILWAY_SERVICE --body harvest`.
4. **Cloudflare:** create the records from the table above, using Railway's exact CNAME target and
   TXT value.
5. Run `gh workflow run Deploy --ref main`. The first build takes about 3 minutes.

Until `RAILWAY_TOKEN` and `RAILWAY_SERVICE` exist, the Deploy workflow is skipped with a warning
(it doesn't fail).
