import pytest
import yaml

from app.errors import ConfigError
from app.main import create_app
from app.settings import BACKEND_DIR, get_env, load_mvp_config

REAL = BACKEND_DIR / "config" / "mvp.yaml"


def write(tmp_path, **overrides):
    raw = yaml.safe_load(REAL.read_text(encoding="utf-8"))
    raw.update(overrides)
    path = tmp_path / "mvp.yaml"
    path.write_text(yaml.safe_dump(raw))
    return path


def test_real_config_is_valid():
    load_mvp_config(REAL)


def test_weights_must_sum_to_one(tmp_path):
    path = write(tmp_path, priority_weights={"water": 0.5, "soil": 0.5, "climate": 0.5})
    with pytest.raises(ConfigError, match=r"sum to 1\.0"):
        load_mvp_config(path)


def test_seasons_cannot_overlap(tmp_path):
    path = write(
        tmp_path, seasons=[{"name": "a", "months": [1, 2]}, {"name": "b", "months": [2, 3]}]
    )
    with pytest.raises(ConfigError, match="share months"):
        load_mvp_config(path)


def test_season_names_must_be_unique(tmp_path):
    seasons = [{"name": "wet", "months": [5, 6]}, {"name": "wet", "months": [9, 10]}]
    with pytest.raises(ConfigError, match="season names must be unique"):
        load_mvp_config(write(tmp_path, seasons=seasons))


def test_invalid_env_is_config_error(monkeypatch):
    monkeypatch.setenv("DATA_MODE", "bogus")
    get_env.cache_clear()
    try:
        with pytest.raises(ConfigError, match="environment"):
            get_env()
    finally:
        get_env.cache_clear()


def test_unknown_variable(tmp_path):
    with pytest.raises(ConfigError, match="variables"):
        load_mvp_config(write(tmp_path, variables=["humidity"]))


def test_unknown_crop_fails_at_startup(tmp_path, env):
    cfg = load_mvp_config(write(tmp_path, crops=["rice", "kale"]))
    with pytest.raises(ConfigError, match="kale"):
        create_app(config=cfg, env=env)
