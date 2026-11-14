"""Runtime settings: environment variables (.env) + MVP scope (config/mvp.yaml)."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.errors import ConfigError

BACKEND_DIR = Path(__file__).resolve().parent.parent

Variable = Literal["temperature", "rainfall", "soil_ph", "soil_moisture", "heat", "frost"]


class DataMode(StrEnum):
    MOCK = "mock"
    CACHED = "cached"
    LIVE = "live"


class EnvSettings(BaseSettings):
    """Values that differ per machine. Read from env vars or backend/.env."""

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    data_mode: DataMode | None = None  # overrides mvp.yaml when set
    mvp_config: Path = BACKEND_DIR / "config" / "mvp.yaml"
    cache_dir: Path = BACKEND_DIR / ".cache"
    crop_catalog: Path = BACKEND_DIR / "data" / "ecocrop_subset.csv"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


class Region(BaseModel):
    name: str
    bbox: tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat

    @model_validator(mode="after")
    def _check_bbox(self) -> Region:
        min_lon, min_lat, max_lon, max_lat = self.bbox
        if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
            raise ValueError("region.bbox must be [min_lon, min_lat, max_lon, max_lat]")
        return self

    def contains(self, lat: float, lon: float) -> bool:
        min_lon, min_lat, max_lon, max_lat = self.bbox
        return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


class PriorityWeights(BaseModel):
    water: float = Field(ge=0)
    soil: float = Field(ge=0)
    climate: float = Field(ge=0)


class SeasonConfig(BaseModel):
    name: str
    months: list[int] = Field(min_length=1)

    @field_validator("months")
    @classmethod
    def _valid_months(cls, v: list[int]) -> list[int]:
        if any(m < 1 or m > 12 for m in v):
            raise ValueError("months must be between 1 and 12")
        return v


class MvpConfig(BaseModel):
    """Shape of config/mvp.yaml. Validation errors here stop the app at startup."""

    region: Region
    crops: list[str] = Field(min_length=2, max_length=8)
    variables: list[Variable] = Field(min_length=1)
    priority_weights: PriorityWeights
    seasons: list[SeasonConfig] = Field(min_length=2, max_length=4)
    top_n: int = Field(default=5, ge=1, le=50)
    data_mode: DataMode = DataMode.MOCK

    @model_validator(mode="after")
    def _check(self) -> MvpConfig:
        w = self.priority_weights
        total = w.water + w.soil + w.climate
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"priority_weights must sum to 1.0 (got {total:.2f})")
        names = [s.name for s in self.seasons]
        if len(names) != len(set(names)):
            raise ValueError("season names must be unique")
        months = [m for s in self.seasons for m in s.months]
        if len(months) != len(set(months)):
            raise ValueError("seasons must not share months")
        return self


def load_mvp_config(path: Path) -> MvpConfig:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ConfigError(f"MVP config not found: {path}", details={"path": str(path)}) from e
    except yaml.YAMLError as e:
        raise ConfigError(f"{path.name} is not valid YAML: {e}", details={"path": str(path)}) from e
    try:
        return MvpConfig.model_validate(raw)
    except ValueError as e:
        raise ConfigError(f"Invalid {path.name}:\n{e}", details={"path": str(path)}) from e


@lru_cache
def get_env() -> EnvSettings:
    try:
        return EnvSettings()
    except ValueError as e:  # pydantic ValidationError, e.g. DATA_MODE=typo in .env
        raise ConfigError(f"Invalid environment / .env: {e}") from e


@lru_cache
def get_config() -> MvpConfig:
    env = get_env()
    cfg = load_mvp_config(env.mvp_config)
    if env.data_mode is not None:
        cfg = cfg.model_copy(update={"data_mode": env.data_mode})
    return cfg
