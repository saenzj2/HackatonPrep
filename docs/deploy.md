# Deploy

One public URL serves everything: the API and the frontend run in **one Railway service** built
from the root `Dockerfile`.

| URL | What |
|---|---|
| `https://<service>.up.railway.app/` | Redirects to the app |
| `/app/` | Frontend (static files from `frontend/`) |
| `/docs` | Swagger UI for the API |
| `/health` | Health check (Railway uses it before switching traffic) |

Production runs in **`cached` mode**: real NASA POWER, OpenLandMap, SMAP and EcoCrop data from the
committed snapshot (`backend/app/cache/snapshots/`). It never calls external APIs and needs **no
secrets or API keys**. Demo points: San Carlos (11.0, −84.6) and Alajuela (10.0, −84.2). Any other
point answers `503 cache_miss`. To add a point, fetch it once locally in `live` mode, then run
`make cache-snapshot` and open a PR.

## How a team member deploys (all 6 of us)

You don't need a Railway account.

- **Automatic:** merge a PR to `main`. When CI passes on `main`, the **Deploy** workflow publishes
  that exact commit.
- **Manual (re-deploy or demo a branch):** GitHub → **Actions** → **Deploy** → **Run workflow** →
  choose the branch → **Run workflow**. This skips CI, so only use a branch whose PR is green.
- **Check it:** the workflow summary shows the deployed commit and who deployed it. Then open
  `/health` and `/app/` on the public URL.

**Roll back:** run **Deploy** manually on an earlier commit or branch (for example, a revert PR), or
use **Redeploy** on a previous deployment in the Railway dashboard (the owner can do this).

## Run the production image locally

Use this when you change `Dockerfile`, `frontend/` or startup code. You need Docker.

```bash
docker build -t harvest .
docker run --rm -p 8000:8000 harvest     # http://localhost:8000
```

Without Docker, `make dev` serves the same thing: the app at http://localhost:8000/app/ and the API
docs at `/docs`.

## One-time setup (done once by the Railway owner and the repo owner)

1. **Railway owner:** create a free account at railway.com, then **New Project → Empty Project**,
   then **+ Create → Empty Service**. Name the service (for example, `harvest`).
2. In the service: **Settings → Networking → Generate Domain**. That's the public URL.
3. In the project: **Settings → Tokens → Create project token** (environment `production`). Copy it.
4. **Repo owner** (only admins can add secrets): GitHub repo → **Settings → Secrets and variables →
   Actions**:
   - **Secrets → New repository secret:** `RAILWAY_TOKEN` = the project token.
   - **Variables → New repository variable:** `RAILWAY_SERVICE` = the service name.
5. Run **Actions → Deploy → Run workflow** on `main`. The first build takes about 3 minutes.

Until steps 3 and 4 are done, the Deploy workflow is skipped with a warning (it doesn't fail).

**Optional custom domain:** in Railway, **Settings → Networking → Custom Domain**, then add the
CNAME record it shows at your DNS provider (for example, the free GoDaddy domain from the Space Apps
offer). Railway issues the HTTPS certificate.

## Configuration

Set these in Railway → service → **Variables** only if you need to change the defaults baked into
the image:

| Variable | Default in the image | Notes |
|---|---|---|
| `DATA_MODE` | `cached` | Keep `cached` for the demo. `live` needs the Earth Engine credentials. |
| `FRONTEND_DIR` | `/srv/frontend` | Unset it to serve the API only. |
| `CORS_ORIGINS` | localhost dev ports | Only needed if a frontend is hosted on another domain. |
| `PORT` | set by Railway | Don't set it. |

Never put secrets in the `Dockerfile`, `railway.json` or the repo. `.dockerignore` keeps `.env`
files out of the image.

## Cost

Railway's trial credit covers the hackathon. To keep the URL up for judging, the owner needs the
Hobby plan (about USD 5 per month), or the team can move the same Docker image to Google Cloud Run
(Space Apps credits).
