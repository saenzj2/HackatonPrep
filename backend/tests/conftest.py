from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import BACKEND_DIR, DataMode, EnvSettings, MvpConfig, load_mvp_config

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(rel: str) -> dict:
    return json.loads((FIXTURES / rel).read_text(encoding="utf-8"))


def isolated_config() -> MvpConfig:
    """The real config/mvp.yaml, forced to mock mode so tests never hit the network."""
    cfg = load_mvp_config(BACKEND_DIR / "config" / "mvp.yaml")
    return cfg.model_copy(update={"data_mode": DataMode.MOCK})


def isolated_app() -> FastAPI:
    """An app that ignores the developer's .env and never touches the network or the real cache."""
    env = EnvSettings(_env_file=None, data_mode=None, cache_dir=Path(tempfile.mkdtemp()))
    return create_app(config=isolated_config(), env=env)


@pytest.fixture
def env(tmp_path: Path) -> EnvSettings:
    """Isolated env: never reads the developer's .env, cache goes to a temp dir."""
    return EnvSettings(_env_file=None, data_mode=None, cache_dir=tmp_path / "cache")


@pytest.fixture
def config() -> MvpConfig:
    return isolated_config()


@pytest.fixture
def client(config: MvpConfig, env: EnvSettings) -> TestClient:
    return TestClient(create_app(config=config, env=env))


@pytest.fixture
def make_client(env: EnvSettings, config: MvpConfig):
    """Build a client with config overrides, e.g. make_client(data_mode=DataMode.CACHED)."""

    def _make(**overrides) -> TestClient:
        return TestClient(create_app(config=config.model_copy(update=overrides), env=env))

    return _make
