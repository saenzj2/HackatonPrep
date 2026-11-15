"""FastAPI entry point. Run with `make dev`; docs at http://localhost:8000/docs.

There is no module-level `app`: importing this module has no side effects (no .env or YAML reads).
uvicorn builds the app with `app.main:create_app --factory`.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.errors import REQUEST_ID_HEADER, install_error_handling
from app.api.routes import router
from app.errors import ConfigError
from app.integrations import build_sources
from app.services import AppContext
from app.settings import EnvSettings, MvpConfig, get_config, get_env

FRONTEND_PATH = "/app"

log = logging.getLogger(__name__)


def _check_startup(ctx: AppContext) -> None:
    """Fail fast with ConfigError instead of failing on the first request."""
    catalog = ctx.sources.crops.all()
    unknown = sorted(set(ctx.config.crops) - set(catalog))
    if unknown:
        raise ConfigError(
            f"config/mvp.yaml lists crops not in the crop catalog: {unknown}",
            details={"unknown": unknown, "available": sorted(catalog)},
        )
    perennials = ctx.sources.perennials.all()
    unknown = sorted(set(ctx.config.permanent_crops) - set(perennials))
    if unknown:
        raise ConfigError(
            f"config/mvp.yaml lists permanent crops not in the permanent crop catalog: {unknown}",
            details={"unknown": unknown, "available": sorted(perennials)},
        )


def _mount_frontend(app: FastAPI, env: EnvSettings) -> None:
    """Serve the static frontend at /app (same origin as the API, so no CORS) and redirect /."""
    if env.frontend_dir is None:
        return
    if not (env.frontend_dir / "index.html").is_file():
        raise ConfigError(
            f"FRONTEND_DIR has no index.html: {env.frontend_dir}",
            details={"frontend_dir": str(env.frontend_dir)},
        )
    app.mount(FRONTEND_PATH, StaticFiles(directory=env.frontend_dir, html=True), name="frontend")

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(f"{FRONTEND_PATH}/")


def create_app(config: MvpConfig | None = None, env: EnvSettings | None = None) -> FastAPI:
    """App factory. Tests pass their own config/env; production reads .env + config/mvp.yaml."""
    env = env or get_env()
    config = config or get_config()
    ctx = AppContext(config=config, sources=build_sources(config, env))
    _check_startup(ctx)

    app = FastAPI(
        title="Guardians of the Harvest API",
        version=__version__,
        description="Crop rotation decision support from NASA Earth observation data.",
        separate_input_output_schemas=False,
    )
    app.state.ctx = ctx
    app.include_router(router)
    _mount_frontend(app, env)
    install_error_handling(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=env.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )

    log.info("Started in data_mode=%s with sources %s", config.data_mode, ctx.sources.names())
    return app
