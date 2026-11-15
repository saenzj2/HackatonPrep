"""Regenerate the example API responses in docs/examples/ (the frontend's mock data).

Runs the real app in `cached` mode on top of the saved real responses for the demo point (NASA
POWER climate, OpenLandMap soil, NASA SMAP moisture), so the examples hold real data and never
touch the network.

    cd backend && .venv/bin/python -m scripts.make_examples
"""

from __future__ import annotations

import json
import logging
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.cache import JsonCache
from app.integrations import nasa_power, openlandmap, smap
from app.integrations.nasa_power import NasaPowerClimate
from app.integrations.openlandmap import EarthEngineSoil
from app.integrations.smap import SmapSoilMoisture
from app.main import create_app
from app.settings import BACKEND_DIR, DataMode, EnvSettings, load_mvp_config

log = logging.getLogger(__name__)

EXAMPLES_DIR = BACKEND_DIR / "docs" / "examples"
FIXTURES = BACKEND_DIR / "tests" / "fixtures"
# Demo point: Alajuela, Costa Rica (the location of the saved real responses below).
LAT, LON = 10.0, -84.2
# Pinned so regenerating the examples only changes the file when the app output changes.
GENERATED_AT = "2026-01-01T00:00:00Z"
RECOMMENDATION_REQUEST: dict[str, Any] = {
    "lat": LAT,
    "lon": LON,
    "priorities": {"water": 0.4, "soil": 0.3, "climate": 0.3},
    "current_rotation": ["maize", "maize"],
    "top_n": 3,
}


def seed_demo_cache(cache_dir: Path) -> None:
    """Put the saved real responses for (LAT, LON) where each adapter looks for them, through
    JsonCache's own live write: NASA POWER climate, OpenLandMap soil profile, NASA SMAP moisture.
    Also used by tests that need a `cached`-mode app with real data and no network."""
    cache = JsonCache(cache_dir, DataMode.LIVE)
    entries = [
        (
            nasa_power.SOURCE,
            NasaPowerClimate.request_params(LAT, LON),
            "nasa_power/climatology_alajuela.json",
        ),
        (
            openlandmap.SOURCE,
            EarthEngineSoil.point_params(LAT, LON),
            "openlandmap/soil_alajuela.json",
        ),
        (smap.SOURCE, SmapSoilMoisture.point_params(LAT, LON), "smap/monthly_alajuela.json"),
    ]
    for source, params, fixture in entries:
        cache.get_or_fetch(source, params, _reader(FIXTURES / fixture))


def _reader(path: Path) -> Callable[[], Any]:
    """A fetch function that returns the saved response instead of calling the source."""

    def read() -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    return read


def build_examples() -> dict[str, Any]:
    """Run the real app offline and return {file name: body}. `generated_at` is pinned."""
    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp)
        seed_demo_cache(cache_dir)
        config = load_mvp_config(BACKEND_DIR / "config" / "mvp.yaml").model_copy(
            update={"data_mode": DataMode.CACHED}
        )
        env = EnvSettings(
            _env_file=None, data_mode=None, cache_dir=cache_dir, cache_snapshot_dir=None
        )
        client = TestClient(create_app(config=config, env=env))

        conditions = client.get("/conditions", params={"lat": LAT, "lon": LON})
        conditions.raise_for_status()
        recommendation = client.post("/recommendations", json=RECOMMENDATION_REQUEST)
        recommendation.raise_for_status()
        crops = client.get("/crops")
        crops.raise_for_status()

    recommendation_body = recommendation.json()
    recommendation_body["generated_at"] = GENERATED_AT
    return {
        "conditions_alajuela.json": conditions.json(),
        "recommendation_request_alajuela.json": RECOMMENDATION_REQUEST,
        "recommendation_alajuela.json": recommendation_body,
        "crops.json": crops.json(),
    }


def render(body: Any) -> str:
    return json.dumps(body, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    EXAMPLES_DIR.mkdir(exist_ok=True)
    for name, body in build_examples().items():
        path = EXAMPLES_DIR / name
        path.write_text(render(body), encoding="utf-8")
        log.info("wrote %s", path.relative_to(BACKEND_DIR))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
