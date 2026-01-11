from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_hex(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    atomic_write_bytes(path, json.dumps(obj, indent=2, sort_keys=True).encode("utf-8"))


@dataclass(frozen=True)
class HttpRetry:
    max_attempts: int = 6
    timeout_seconds: float = 20.0
    base_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 60.0
    jitter_seconds: float = 0.25
    deadline_seconds: float = 180.0


def _sleep(seconds: float, jitter_seconds: float) -> None:
    if seconds <= 0:
        return
    jitter = random.uniform(0, jitter_seconds) if jitter_seconds > 0 else 0.0
    time.sleep(seconds + jitter)


def http_get_bytes(
    url: str,
    retry: HttpRetry,
    headers: dict[str, str] | None = None,
    *,
    allow_non_200: bool = False,
) -> tuple[int, dict[str, str], bytes]:
    """
    Returns (http_status, response_headers_lower, body_bytes).
    Retries on network errors and on 5xx/429/403 with backoff.
    """
    # Import lazily so callers that only use nba_api fallbacks don't require requests at import time.
    import requests  # type: ignore

    hdrs = {
        # Use a realistic browser UA; stats.nba.com is stricter than cdn.nba.com, but this is still a good default.
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
    }
    if headers:
        hdrs.update(headers)

    last_err: BaseException | None = None
    start = time.monotonic()
    for attempt in range(1, retry.max_attempts + 1):
        elapsed = time.monotonic() - start
        if elapsed > retry.deadline_seconds:
            raise RuntimeError(f"Deadline exceeded after {elapsed:.1f}s for {url}")
        try:
            resp = requests.get(url, headers=hdrs, timeout=retry.timeout_seconds)
            status = int(resp.status_code)
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            body = resp.content

            if status == 200:
                return status, resp_headers, body

            if allow_non_200:
                # Caller will decide how to handle the failure; we still apply retry policy below.
                # For non-retriable codes, we return immediately with the response body for logging/debugging.
                if status not in (403, 429) and not (500 <= status <= 599):
                    return status, resp_headers, body

            # Retry on common transient/anti-bot responses.
            if status in (403, 429) or 500 <= status <= 599:
                if attempt < retry.max_attempts:
                    backoff = min(retry.base_backoff_seconds * (2 ** (attempt - 1)), retry.max_backoff_seconds)
                    remaining = max(0.0, retry.deadline_seconds - (time.monotonic() - start))
                    _sleep(min(backoff, remaining), retry.jitter_seconds)
                    continue
            if allow_non_200:
                return status, resp_headers, body
            raise RuntimeError(f"HTTP {status} for {url}")
        except BaseException as e:  # noqa: BLE001
            last_err = e
            if attempt >= retry.max_attempts:
                break
            backoff = min(retry.base_backoff_seconds * (2 ** (attempt - 1)), retry.max_backoff_seconds)
            remaining = max(0.0, retry.deadline_seconds - (time.monotonic() - start))
            _sleep(min(backoff, remaining), retry.jitter_seconds)

    raise RuntimeError(f"GET failed after {retry.max_attempts} attempts: {url}") from last_err


def parse_json_bytes(body: bytes) -> dict[str, Any]:
    obj = json.loads(body.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Expected top-level JSON object")
    return obj


def write_with_manifest(
    out_json_path: Path,
    out_manifest_path: Path,
    *,
    url: str,
    http_status: int,
    response_headers: dict[str, str],
    body: bytes,
    source_type: str,
    source_key: str,
    fetched_at_utc: str,
) -> None:
    sha = sha256_hex(body)
    atomic_write_bytes(out_json_path, body)
    atomic_write_json(
        out_manifest_path,
        {
            "source_type": source_type,
            "source_key": source_key,
            "url": url,
            "fetched_at_utc": fetched_at_utc,
            "http_status": http_status,
            "etag": response_headers.get("etag"),
            "last_modified": response_headers.get("last-modified"),
            "content_type": response_headers.get("content-type"),
            "sha256_hex": sha,
            "byte_size": len(body),
            "path": str(out_json_path),
        },
    )


