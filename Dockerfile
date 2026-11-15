# One image = API + frontend. Used by Railway (railway.json) and runs anywhere with Docker:
#   docker build -t harvest . && docker run -p 8000:8000 harvest   ->  http://localhost:8000

# Stage 1: build the React app (frontend-app/) into static files.
FROM node:22-slim AS web
WORKDIR /web
# Dependencies first so source-only changes reuse this layer.
COPY frontend-app/package.json frontend-app/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend-app/ ./
RUN npm run build

# Stage 2: the API, which serves the frontend at /app (FRONTEND_DIR).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_MODE=cached \
    FRONTEND_DIR=/srv/frontend \
    PORT=8000

WORKDIR /srv/backend
# Dependencies first so code-only changes reuse this layer.
COPY backend/pyproject.toml ./
COPY backend/app/__init__.py app/__init__.py
RUN pip install -e .

COPY backend/ ./
# Both frontends ship in the image. FRONTEND_DIR picks one: /srv/frontend (static skeleton, default
# until the React app is ready) or /srv/frontend-app (React build). Switching needs no rebuild.
COPY frontend/ /srv/frontend/
COPY --from=web /web/dist/ /srv/frontend-app/

EXPOSE 8000
# Shell form so $PORT (set by Railway) expands.
CMD uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips="*"
