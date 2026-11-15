"""The API can serve the static frontend (one service for the deploy, docs/deploy.md)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.errors import ConfigError
from app.main import create_app
from app.settings import BACKEND_DIR, EnvSettings, MvpConfig

REPO_FRONTEND = BACKEND_DIR.parent / "frontend"


def _client(env: EnvSettings, config: MvpConfig, frontend_dir: Path | None) -> TestClient:
    env = env.model_copy(update={"frontend_dir": frontend_dir})
    return TestClient(create_app(config=config, env=env))


def test_serves_frontend_and_redirects_root(env: EnvSettings, config: MvpConfig) -> None:
    client = _client(env, config, REPO_FRONTEND)

    page = client.get("/app/")
    assert page.status_code == 200
    assert "Guardians of the Harvest" in page.text

    root = client.get("/", follow_redirects=False)
    assert root.status_code == 307
    assert root.headers["location"] == "/app/"

    assert client.get("/health").status_code == 200  # API routes still win


def test_frontend_is_not_part_of_the_api_schema(env: EnvSettings, config: MvpConfig) -> None:
    paths = _client(env, config, REPO_FRONTEND).get("/openapi.json").json()["paths"]
    assert "/" not in paths
    assert not any(p.startswith("/app") for p in paths)


def test_without_frontend_dir_root_is_not_served(env: EnvSettings, config: MvpConfig) -> None:
    client = _client(env, config, None)
    assert client.get("/").status_code == 404
    assert client.get("/app/").status_code == 404


def test_frontend_dir_without_index_fails_at_startup(
    env: EnvSettings, config: MvpConfig, tmp_path: Path
) -> None:
    with pytest.raises(ConfigError, match=r"index.html"):
        _client(env, config, tmp_path)
