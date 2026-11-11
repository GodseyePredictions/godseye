"""Cached, rate-limited, retrying HTTP GET shared by every data pull.

Every raw response is written to disk (gzip) with the time it was fetched, so a pull that
stops half way resumes from where it stopped: anything already on disk is not asked for again
unless `max_age` says it is stale. Nothing here pretends to be a browser.
"""
import gzip
import hashlib
import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT = "godseye-nba/0.1 (data pipeline)"
_locks: dict[str, threading.Lock] = {}
_last: dict[str, float] = {}
_guard = threading.Lock()


class FetchError(Exception):
    pass


def _throttle(host: str, min_interval: float) -> None:
    with _guard:
        lock = _locks.setdefault(host, threading.Lock())
    with lock:
        wait = _last.get(host, 0.0) + min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.monotonic()


def cache_path(root: Path, url: str, tag: str = "") -> Path:
    host = url.split("/")[2]
    key = hashlib.sha1((url + tag).encode()).hexdigest()
    return Path(root) / host / key[:2] / f"{key}.gz"


def get(url: str, root: Path, *, min_interval: float = 0.25, retries: int = 4, timeout: float = 40,
        max_age: float | None = None, tag: str = "", opener=None, redact: str | None = None) -> tuple[bytes, str]:
    """Return (body, fetched_at ISO time). `tag` keeps several timed snapshots of one URL apart.
    `redact` is a secret (an API key) that must not be written to the cache index."""
    path = cache_path(root, url if not redact else url.replace(redact, "KEY"), tag)
    meta = path.with_suffix(".json")
    if path.exists() and meta.exists():
        m = json.loads(meta.read_text())
        age = time.time() - datetime.fromisoformat(m["fetched_at"]).timestamp()
        if max_age is None or age <= max_age:
            return gzip.decompress(path.read_bytes()), m["fetched_at"]
    host = url.split("/")[2]
    err = None
    for attempt in range(retries + 1):
        _throttle(host, min_interval)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with (opener or urllib.request.urlopen)(req, timeout=timeout) as r:
                body = r.read()
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp%d" % threading.get_ident())
            tmp.write_bytes(gzip.compress(body, 5))
            tmp.replace(path)
            meta.write_text(json.dumps({"url": url if not redact else url.replace(redact, "KEY"),
                                        "fetched_at": now, "bytes": len(body)}))
            return body, now
        except urllib.error.HTTPError as e:
            err = e
            if e.code in (400, 401, 403, 404, 422):   # asking again will not help
                raise FetchError(f"{e.code} for {host}") from e
        except Exception as e:  # timeouts, resets
            err = e
        time.sleep(min(30, 2 ** attempt))
    raise FetchError(f"gave up on {host} after {retries + 1} tries: {err}")
