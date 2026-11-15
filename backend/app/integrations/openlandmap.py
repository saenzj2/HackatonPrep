"""OpenLandMap soil properties (250 m, global) from Google Earth Engine, at 0, 10 and 30 cm depth.

Same 3-part pattern as nasa_power.py:
  1. `fetch_raw()`           one Earth Engine request (all bands of all 7 datasets at once).
  2. `parse_soil_profile()`  pure function: stored integers → physical units, masked pixels → None.
  3. `soil_profile()`        goes through JsonCache, one cache entry per 250 m pixel.

Dataset notes, bands and scale factors (checked against Earth Engine): docs/sources/openlandmap.md

Earth Engine is initialized once per process, never interactively: locally with the stored
`earthengine authenticate` credentials or Application Default Credentials, in deployment with a
service-account key file (GEE_SERVICE_ACCOUNT_KEY_FILE). The `ee` package is imported only when a
request is made (it takes ~0.6 s to import), so mock and cached modes never load it.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.cache import JsonCache
from app.domain.models import SoilLayer, SoilProfile
from app.domain.soil import silt_pct
from app.errors import ConfigError, SourceDataError, SourceUnavailableError

SOURCE = "openlandmap"
ATTRIBUTION = (
    "OpenLandMap soil property maps v02 (field capacity v01), Hengl et al. 2018-2019, "
    "CC-BY-SA 4.0 (doi:10.5281/zenodo.1475457), via Google Earth Engine"
)
RESOLUTION_M = 250  # nominal; the native grid is 1/480° (~232 m)
DEPTHS_CM = (0, 10, 30)  # bands b0, b10, b30. Every dataset also has b60, b100 and b200.

# Native grid shared by all 7 assets (EPSG:4326, checked with ee.Image.getInfo on 2026-11-14).
# Sampling on it returns exactly the pixel that contains the point, with no resampling.
GRID_DEG = 1 / 480
GRID_ORIGIN_LON = -180.0
GRID_ORIGIN_LAT = 87.37  # top edge of the maps
NATIVE_CRS = "EPSG:4326"
NATIVE_CRS_TRANSFORM = (GRID_DEG, 0.0, GRID_ORIGIN_LON, 0.0, -GRID_DEG, GRID_ORIGIN_LAT)
COORD_DECIMALS = 6  # pixel centres in the cache key; ~0.1 m, far below the pixel size
EE_TIMEOUT_MS = 60_000  # per Earth Engine request; a cold request takes ~4 s


@dataclass(frozen=True)
class SoilDataset:
    asset_id: str
    field: str  # SoilLayer attribute it fills
    scale: float  # physical value = stored integer x scale (stored as uint8 in every dataset)
    valid_range: tuple[float, float]  # in physical units; outside it the data is unusable


# Scale factors from the Earth Engine catalog and the dataset titles (docs/sources/openlandmap.md).
NUMERIC_DATASETS: dict[str, SoilDataset] = {
    # stored as pH x 10 (66 → pH 6.6)
    "ph": SoilDataset("OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02", "ph", 0.1, (0.0, 14.0)),
    # stored in steps of 5 g/kg (2 → 10 g/kg), so values are only precise to ±2.5 g/kg
    "organic_carbon": SoilDataset(
        "OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02",
        "organic_carbon_g_kg",
        5.0,
        (0.0, 1000.0),
    ),
    # stored directly as % by weight (kg/kg)
    "clay": SoilDataset(
        "OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02", "clay_pct", 1.0, (0.0, 100.0)
    ),
    "sand": SoilDataset(
        "OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02", "sand_pct", 1.0, (0.0, 100.0)
    ),
    # stored in steps of 10 kg/m³ (127 → 1270 kg/m³); 2650 = density of quartz, a hard ceiling
    "bulk_density": SoilDataset(
        "OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02",
        "bulk_density_kg_m3",
        10.0,
        (0.0, 2650.0),
    ),
    # stored as volumetric % at 33 kPa (34 → 0.34 m³/m³, the project's moisture unit)
    "field_capacity": SoilDataset(
        "OpenLandMap/SOL/SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01",
        "field_capacity_m3m3",
        0.01,
        (0.0, 1.0),
    ),
}
TEXTURE_ASSET_ID = "OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02"
# Class values 1..12 and their short names (Cl, SiCl, …) come with the asset's properties.
USDA_TEXTURE_CLASSES = {
    1: "clay",
    2: "silty clay",
    3: "sandy clay",
    4: "clay loam",
    5: "silty clay loam",
    6: "sandy clay loam",
    7: "loam",
    8: "silt loam",
    9: "sandy loam",
    10: "silt",
    11: "loamy sand",
    12: "sand",
}
# property → asset, in request order. Band names in the request are "<property>_b<depth>".
ASSET_IDS = {
    **{prop: dataset.asset_id for prop, dataset in NUMERIC_DATASETS.items()},
    "texture_class": TEXTURE_ASSET_ID,
}


def band_name(prop: str, depth_cm: int) -> str:
    """Name of a property's band in the combined request, e.g. ("clay", 30) → "clay_b30"."""
    return f"{prop}_b{depth_cm}"


def snap_to_pixel_center(lat: float, lon: float) -> tuple[float, float]:
    """Centre of the 250 m pixel that contains the point. Every click inside one pixel gets the
    same values and the same cache entry."""
    row = math.floor((GRID_ORIGIN_LAT - lat) / GRID_DEG)
    col = math.floor((lon - GRID_ORIGIN_LON) / GRID_DEG)
    return (
        round(GRID_ORIGIN_LAT - (row + 0.5) * GRID_DEG, COORD_DECIMALS),
        round(GRID_ORIGIN_LON + (col + 0.5) * GRID_DEG, COORD_DECIMALS),
    )


def _stored_value(raw: dict[str, Any], band: str) -> float | None:
    """The band's stored number, or None for a masked pixel (Earth Engine answers null)."""
    if band not in raw:
        raise SourceDataError(
            f"Earth Engine response has no {band} band", details={"source": SOURCE}
        )
    value = raw[band]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise SourceDataError(
            f"Unexpected value for {band}: {value!r}, expected a number",
            details={"source": SOURCE},
        )
    return float(value)


def _physical_value(raw: dict[str, Any], prop: str, depth_cm: int) -> float | None:
    dataset = NUMERIC_DATASETS[prop]
    stored = _stored_value(raw, band_name(prop, depth_cm))
    if stored is None:
        return None
    # round() only removes float noise from the scaling (66 x 0.1 = 6.6000000000000005)
    value = round(stored * dataset.scale, 6)
    low, high = dataset.valid_range
    if not low <= value <= high:
        raise SourceDataError(
            f"OpenLandMap {prop} at {depth_cm} cm is {value}, outside {low}..{high}",
            details={"source": SOURCE},
        )
    return value


def _texture_class(raw: dict[str, Any], depth_cm: int) -> str | None:
    stored = _stored_value(raw, band_name("texture_class", depth_cm))
    if stored is None:
        return None
    name = USDA_TEXTURE_CLASSES.get(int(stored)) if stored.is_integer() else None
    if name is None:
        raise SourceDataError(
            f"Unknown USDA texture class code {stored} at {depth_cm} cm",
            details={"source": SOURCE},
        )
    return name


def parse_soil_profile(raw: dict[str, Any], *, lat: float, lon: float) -> SoilProfile:
    """Earth Engine reduceRegion result → SoilProfile in physical units.

    Example input: {"ph_b0": 66, "clay_b0": 38, "sand_b0": 34, "texture_class_b0": 4, ...}
    Masked pixels (water, ice, no prediction) come back as null and become None, never a guess.
    """
    layers = []
    for depth in DEPTHS_CM:
        values = {
            dataset.field: _physical_value(raw, prop, depth)
            for prop, dataset in NUMERIC_DATASETS.items()
        }
        layers.append(
            SoilLayer(
                depth_cm=depth,
                ph=values["ph"],
                organic_carbon_g_kg=values["organic_carbon_g_kg"],
                clay_pct=values["clay_pct"],
                sand_pct=values["sand_pct"],
                silt_pct=silt_pct(values["clay_pct"], values["sand_pct"]),
                bulk_density_kg_m3=values["bulk_density_kg_m3"],
                field_capacity_m3m3=values["field_capacity_m3m3"],
                texture_class=_texture_class(raw, depth),
            )
        )
    return SoilProfile(lat=lat, lon=lon, layers=tuple(layers))


# Projects Earth Engine was initialized with in this process. ee keeps its own global state, so
# one initialization serves every request; the lock stops two first requests racing each other.
_initialized_projects: set[str] = set()
_init_lock = threading.Lock()


def initialize_earth_engine(project_id: str, service_account_key_file: Path | None = None) -> None:
    """Initialize Earth Engine once per process. Never opens a browser or asks for input.

    No key file: the credentials stored by `earthengine authenticate`, else Application Default
    Credentials (`gcloud auth application-default login`). Key file: that service account.
    """
    import ee  # noqa: PLC0415  (~0.6 s import, only paid when Earth Engine is actually used)
    from google.auth.exceptions import GoogleAuthError  # noqa: PLC0415  (installed with ee)

    with _init_lock:
        if project_id in _initialized_projects:
            return
        credentials: Any = "persistent"
        if service_account_key_file is not None:
            credentials = _service_account_credentials(service_account_key_file)
        try:
            ee.Initialize(credentials=credentials, project=project_id)
        except (ee.EEException, GoogleAuthError) as e:
            # Missing or expired credentials, or a project without Earth Engine enabled.
            raise ConfigError(
                f"Earth Engine could not start for project {project_id} ({e}). Locally, run "
                "`earthengine authenticate`; in deployment, set GEE_SERVICE_ACCOUNT_KEY_FILE",
                details={"source": SOURCE},
            ) from e
        except OSError as e:
            raise SourceUnavailableError(
                f"Earth Engine is unreachable ({type(e).__name__})", details={"source": SOURCE}
            ) from e
        ee.data.setDeadline(EE_TIMEOUT_MS)
        _initialized_projects.add(project_id)


def _service_account_credentials(key_file: Path) -> Any:
    import ee  # noqa: PLC0415  (see initialize_earth_engine)
    from google.oauth2 import service_account  # noqa: PLC0415  (installed with ee)

    try:
        return service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]  # google-auth leaves this untyped
            str(key_file), scopes=ee.oauth.SCOPES
        )
    except (OSError, ValueError, KeyError) as e:
        # Never echo the file's contents: it holds a private key.
        raise ConfigError(
            f"GEE_SERVICE_ACCOUNT_KEY_FILE could not be read as a service-account key "
            f"({type(e).__name__})",
            details={"source": SOURCE},
        ) from e


def sample_point(lat: float, lon: float) -> Any:
    """ONE Earth Engine request: every band of every dataset at the pixel containing (lat, lon).

    Returns {"<prop>_b<depth>": stored integer or None}. Earth Engine must be initialized first.
    """
    import ee  # noqa: PLC0415  (see initialize_earth_engine)

    bands = [f"b{d}" for d in DEPTHS_CM]
    image = ee.Image.cat(
        [
            ee.Image(asset_id).select(bands, [band_name(prop, d) for d in DEPTHS_CM])
            for prop, asset_id in ASSET_IDS.items()
        ]
    )
    return image.reduceRegion(
        reducer=ee.Reducer.first(),
        geometry=ee.Geometry.Point([lon, lat]),  # Earth Engine wants [lon, lat]
        crs=NATIVE_CRS,
        crsTransform=list(NATIVE_CRS_TRANSFORM),
    ).getInfo()


class EarthEngineSoil:
    name = SOURCE
    attribution = ATTRIBUTION
    resolution_m = RESOLUTION_M

    def __init__(
        self,
        cache: JsonCache,
        *,
        project_id: str | None,
        service_account_key_file: Path | None = None,
        sampler: Callable[[float, float], Any] | None = None,
    ) -> None:
        """`sampler` replaces the real Earth Engine call (tests pass a fake that never touches
        the network). Without it, Earth Engine is initialized on the first uncached request."""
        self.cache = cache
        self.project_id = project_id
        self.service_account_key_file = service_account_key_file
        self.sampler = sampler

    @staticmethod
    def point_params(lat: float, lon: float) -> dict[str, Any]:
        # Also the cache key: the pixel centre plus the exact asset versions and depths, so a new
        # dataset version or depth list never reuses old entries.
        center_lat, center_lon = snap_to_pixel_center(lat, lon)
        return {
            "assets": sorted(ASSET_IDS.values()),
            "depths_cm": list(DEPTHS_CM),
            "latitude": center_lat,
            "longitude": center_lon,
        }

    def _default_sampler(self) -> Callable[[float, float], Any]:
        if self.project_id is None:
            # Only reached when the cache can't answer, so cached mode works without a project.
            raise ConfigError(
                "No Earth Engine project configured (GEE_PROJECT_ID); it is needed to fetch "
                "new soil "
                "data from Earth Engine (data_mode=live)",
                details={"source": SOURCE},
            )
        initialize_earth_engine(self.project_id, self.service_account_key_file)
        return sample_point

    def fetch_raw(self, params: dict[str, Any]) -> dict[str, Any]:
        import ee  # noqa: PLC0415  (see initialize_earth_engine)
        import httplib2  # noqa: PLC0415  (ee's HTTP transport, installed with it)
        from google.auth.exceptions import RefreshError, TransportError  # noqa: PLC0415

        sampler = self.sampler or self._default_sampler()
        try:
            data = sampler(params["latitude"], params["longitude"])
        except ee.EEException as e:
            # Earth Engine answered with an error (quota, asset missing, timeout). Only the class
            # name in the message; the original stays chained for the server log.
            raise SourceUnavailableError(
                f"Earth Engine request failed ({type(e).__name__})", details={"source": SOURCE}
            ) from e
        except RefreshError as e:
            raise ConfigError(
                "Earth Engine credentials expired or were revoked; run `earthengine authenticate`",
                details={"source": SOURCE},
            ) from e
        except (OSError, httplib2.HttpLib2Error, TransportError) as e:
            raise SourceUnavailableError(
                f"Earth Engine is unreachable ({type(e).__name__})", details={"source": SOURCE}
            ) from e
        if not isinstance(data, dict):
            raise SourceDataError(
                f"Earth Engine returned {type(data).__name__}, expected an object",
                details={"source": SOURCE},
            )
        return data

    def _fetch_valid(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate before the cache stores it, so a malformed answer is never cached."""
        raw = self.fetch_raw(params)
        parse_soil_profile(raw, lat=params["latitude"], lon=params["longitude"])
        return raw

    def soil_profile(self, lat: float, lon: float) -> SoilProfile:
        """Soil at 0, 10 and 30 cm for the 250 m pixel containing the point. One Earth Engine
        request if the pixel isn't cached, none once it is."""
        params = self.point_params(lat, lon)
        # The maps are static (one release, no time dimension), so a cached pixel is reused in
        # every mode; get_or_fetch alone would call Earth Engine again on every live request.
        raw = self.cache.peek(SOURCE, params)
        if raw is None:
            raw = self.cache.get_or_fetch(SOURCE, params, lambda: self._fetch_valid(params))
        return parse_soil_profile(raw, lat=params["latitude"], lon=params["longitude"])
