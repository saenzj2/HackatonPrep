"""On-disk JSON cache for external API responses, so the demo works without internet.

Layout: <cache_dir>/<namespace>/<sha256(params)[:16]>.json
Each file stores {"params", "fetched_at", "data"} so it is easy to inspect by hand.

An optional read-only *snapshot* directory (same layout, committed to the repo) is checked when
the runtime cache has no entry, so a fresh clone serves the demo points in `cached` mode with
real data. The cache never writes to the snapshot. Refresh it with `make cache-snapshot`.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.errors import CacheMissError, SourceError
from app.settings import DataMode

log = logging.getLogger(__name__)


class JsonCache:
    def __init__(self, root: Path, mode: DataMode, snapshot: Path | None = None) -> None:
        self.root = root
        self.mode = mode
        self.snapshot = snapshot  # read-only fallback, same layout (see module docstring)

    def path_for(self, namespace: str, params: dict[str, Any]) -> Path:
        digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:16]
        return self.root / namespace / f"{digest}.json"

    def peek(self, namespace: str, params: dict[str, Any]) -> Any | None:
        """The cached data for these params, or None. Never fetches, in any mode.

        For sources whose data never changes (e.g. SRTM elevation): the adapter can reuse a cached
        copy even in live mode instead of spending an API call.
        """
        return self._lookup(namespace, params)

    def peek_fresh(self, namespace: str, params: dict[str, Any], max_age: timedelta) -> Any | None:
        """The cached data if it was fetched less than `max_age` ago, else None. Never fetches.

        For sources that change slowly (e.g. NOAA's monthly ENSO files): the adapter can skip the
        network in live mode while the copy is recent enough, and still refetch once it isn't.
        """
        entry = self._lookup_entry(namespace, params)
        if entry is None:
            return None
        try:
            fetched_at = datetime.fromisoformat(entry["fetched_at"])
        except (KeyError, TypeError, ValueError):
            return None  # no usable timestamp: treat as stale
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        return entry["data"] if datetime.now(UTC) - fetched_at < max_age else None

    def _lookup(self, namespace: str, params: dict[str, Any]) -> Any | None:
        """Runtime cache first, then the committed snapshot. None if neither has it."""
        entry = self._lookup_entry(namespace, params)
        return None if entry is None else entry["data"]

    def _lookup_entry(self, namespace: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """The whole {"params", "fetched_at", "data"} entry: runtime cache, then the snapshot."""
        entry = self._read_entry(self.path_for(namespace, params))
        if entry is None and self.snapshot is not None:
            digest = self.path_for(namespace, params).name
            entry = self._read_entry(self.snapshot / namespace / digest)
        return entry

    def _read_entry(self, path: Path) -> dict[str, Any] | None:
        """The cache file's payload, or None if missing or unreadable (treated as a miss)."""
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            log.warning("Ignoring unreadable cache file %s", path)
            return None
        if not isinstance(entry, dict) or "data" not in entry:
            log.warning("Ignoring unreadable cache file %s", path)
            return None
        return entry

    def _write(self, path: Path, payload: dict[str, Any]) -> None:
        """Atomic: write a temp file, then rename, so a crash never leaves half a file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        # Final newline: committed snapshots must pass the end-of-file-fixer pre-commit hook.
        tmp.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
        tmp.replace(path)

    def get_or_fetch(self, namespace: str, params: dict[str, Any], fetch: Callable[[], Any]) -> Any:
        """cached → read or raise CacheMissError. live → fetch and store (falls back to the
        cached copy if the fetch fails, so a flaky network doesn't break a demo)."""
        path = self.path_for(namespace, params)
        if self.mode == DataMode.CACHED:
            cached = self._lookup(namespace, params)
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
            cached = self._lookup(namespace, params)
            if cached is None:
                raise
            log.warning("%s fetch failed, serving cached copy %s", namespace, path)
            return cached
        self._write(
            path, {"params": params, "fetched_at": datetime.now(UTC).isoformat(), "data": data}
        )
        return data
