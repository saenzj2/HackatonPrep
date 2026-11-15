# One image = API + static frontend. Used by Railway (railway.json) and runs anywhere with Docker:
#   docker build -t harvest . && docker run -p 8000:8000 harvest   ->  http://localhost:8000
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
COPY frontend/ /srv/frontend/

EXPOSE 8000
# Shell form so $PORT (set by Railway) expands.
CMD uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips="*"
