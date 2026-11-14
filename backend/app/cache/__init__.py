"""On-disk JSON cache for external API responses, so the demo works without internet.

Layout: <cache_dir>/<namespace>/<sha256(params)[:16]>.json
Each file stores {"params", "fetched_at", "data"} so it is easy to inspect by hand.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.errors import CacheMissError, SourceError
from app.settings import DataMode

log = logging.getLogger(__name__)


class JsonCache:
    def __init__(self, root: Path, mode: DataMode) -> None:
        self.root = root
        self.mode = mode

    def path_for(self, namespace: str, params: dict[str, Any]) -> Path:
        digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:16]
        return self.root / namespace / f"{digest}.json"

    def peek(self, namespace: str, params: dict[str, Any]) -> Any | None:
        """The cached data for these params, or None. Never fetches, in any mode.

        For sources whose data never changes (e.g. SRTM elevation): the adapter can reuse a cached
        copy even in live mode instead of spending an API call.
        """
        return self._read(self.path_for(namespace, params))

    def _read(self, path: Path) -> Any | None:
        """The cached data, or None if the file is missing or unreadable (treated as a miss)."""
        try:
            return json.loads(path.read_text(encoding="utf-8"))["data"]
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError):
            log.warning("Ignoring unreadable cache file %s", path)
            return None

    def _write(self, path: Path, payload: dict[str, Any]) -> None:
        """Atomic: write a temp file, then rename, so a crash never leaves half a file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        tmp.replace(path)

    def get_or_fetch(self, namespace: str, params: dict[str, Any], fetch: Callable[[], Any]) -> Any:
        """cached → read or raise CacheMissError. live → fetch and store (falls back to the
        cached copy if the fetch fails, so a flaky network doesn't break a demo)."""
        path = self.path_for(namespace, params)
        if self.mode == DataMode.CACHED:
            cached = self._read(path)
            if cached is not None:
                return cached
            raise CacheMissError(
                f"No cached {namespace} data for this request. "
                "Run once with data_mode=live to fill the cache.",
                details={"source": namespace},
            )
        try:
            data = fetch()
        except SourceError:
            cached = self._read(path)
            if cached is None:
                raise
            log.warning("%s fetch failed, serving cached copy %s", namespace, path)
            return cached
        self._write(
            path, {"params": params, "fetched_at": datetime.now(UTC).isoformat(), "data": data}
        )
        return data
