#!/usr/bin/env python3
"""
Fetch NBA PBP JSON from the validated CDN endpoint and write an archive file + manifest.

Endpoint pattern:
  https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{gameId}.json

Validation:
  - JSON parses
  - has keys: meta.code == 200, game.gameId, game.actions (list)

Historical note:
  The CDN "liveData" endpoint may return 403 for older games (e.g. 2015-16).
  In that case (or if --source nba_api is selected), we fall back to the NBA Stats API via nba_api
  and *convert* the response into the same game.actions shape the loader expects.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from scripts.lib._fetch_lib import HttpRetry, http_get_bytes, parse_json_bytes, utc_now_iso_compact, write_with_manifest


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch NBA play-by-play JSON from cdn.nba.com.")
    p.add_argument("--game-id", required=True, help="NBA gameId string, e.g. 0022400196")
    p.add_argument("--out", required=True, help="Output JSON path, e.g. data/raw/pbp/0022400196.json")
    p.add_argument(
        "--source",
        choices=["auto", "cdn", "nba_api"],
        default="auto",
        help="Fetch source. auto=try CDN, fall back to nba_api on failure; cdn=only CDN; nba_api=only nba_api.",
    )
    p.add_argument("--timeout-seconds", type=float, default=20.0)
    p.add_argument("--deadline-seconds", type=float, default=180.0, help="Max total time allowed for the fetch (caps retries).")
    p.add_argument("--max-attempts", type=int, default=6)
    p.add_argument("--base-backoff-seconds", type=float, default=1.0)
    p.add_argument("--max-backoff-seconds", type=float, default=60.0)
    p.add_argument("--jitter-seconds", type=float, default=0.25)
    p.add_argument(
        "--nba-api-throttle-seconds",
        type=float,
        default=0.75,
        help="Sleep (plus jitter) before nba_api requests to stats.nba.com (used for CDN fallbacks).",
    )
    p.add_argument(
        "--debug-stats-dump",
        default="",
        help="If set, write raw stats.nba.com response diagnostics to this file when the stats PBP fetch fails.",
    )
    p.add_argument("--verbose", action="store_true", help="Print progress (useful when retries/timeouts make it look hung).")
    return p.parse_args()


def _safe_int(x: Any) -> int | None:
    if x is None:
        return None
    if isinstance(x, bool):
        return int(x)
    try:
        s = str(x).strip()
        if s == "":
            return None
        return int(float(s))
    except Exception:
        return None


def _ensure_order_numbers(obj: dict[str, Any]) -> bool:
    """
    Ensure every action in obj["game"]["actions"] has a stable integer orderNumber.

    Why:
    - Our DB loader (`scripts/load_pbp.py`) requires `orderNumber` and uses it as a stable uniqueness key.
    - Stats playbyplayv3 payloads often omit `orderNumber` but include `actionNumber`.
    - CDN liveData uses (observationally) orderNumber ~= actionNumber * 10000.

    Returns True if we modified the object.
    """
    game = obj.get("game")
    if not isinstance(game, dict):
        return False
    actions = game.get("actions")
    if not isinstance(actions, list):
        return False

    changed = False
    seen: set[int] = set()
    for i, a in enumerate(actions):
        if not isinstance(a, dict):
            continue
        existing = _safe_int(a.get("orderNumber"))
        if existing is None:
            an = _safe_int(a.get("actionNumber"))
            if an is None:
                # fallback: stable monotonic ordering, preserve large gaps like liveData
                candidate = (i + 1) * 10000
            else:
                candidate = an * 10000
            # guarantee uniqueness within a game
            while candidate in seen:
                candidate += 1
            a["orderNumber"] = candidate
            existing = candidate
            changed = True
        # track uniqueness for later conflict-avoidance even if the field was already present
        if existing is not None:
            seen.add(existing)

    return changed


def _clock_from_pctimestring(s: str | None) -> str:
    """
    Convert stats.nba.com PCTIMESTRING like "12:00" into liveData clock format "PT12M00.00S".
    """
    if not s:
        return "PT00M00.00S"
    s2 = str(s).strip()
    if ":" not in s2:
        return "PT00M00.00S"
    parts = s2.split(":")
    if len(parts) != 2:
        return "PT00M00.00S"
    try:
        mm = int(parts[0])
        ss = int(parts[1])
    except Exception:
        return "PT00M00.00S"
    mm = max(0, mm)
    ss = max(0, min(59, ss))
    return f"PT{mm:02d}M{ss:02d}.00S"


def _period_type(period: int) -> str:
    # Minimal mapping for our schema (derived view doesn't depend on this).
    return "OVERTIME" if period > 4 else "REGULAR"


def _description_from_row(r: dict[str, Any]) -> str:
    # Prefer visitor/home/neutral descriptions in a stable order.
    parts: list[str] = []
    for k in ("VISITORDESCRIPTION", "HOMEDESCRIPTION", "NEUTRALDESCRIPTION"):
        v = r.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            parts.append(s)
    return " | ".join(parts)


def _infer_score_order_and_carry_forward(rows: list[dict[str, Any]]) -> list[tuple[int, int]]:
    """
    PlayByPlayV2 includes SCORE strings on some events (format like "10 - 8"), but it can be NULL
    for many rows. We carry-forward the last known score and infer which side of the SCORE string
    corresponds to HOME vs AWAY by observing the first scoring event with a clear home/visitor description.

    Returns a list aligned with rows: [(score_home, score_away), ...]
    """
    # mapping: True means SCORE is "away - home", False means "home - away", None unknown yet
    away_first: bool | None = None

    # track last parsed raw score parts
    last_a = 0
    last_b = 0
    last_home = 0
    last_away = 0
    out: list[tuple[int, int]] = []

    def parse_score(s: str) -> tuple[int, int] | None:
        s2 = s.strip()
        if " - " in s2:
            parts = s2.split(" - ")
        elif "-" in s2:
            parts = [p.strip() for p in s2.split("-")]
        else:
            return None
        if len(parts) != 2:
            return None
        try:
            return int(parts[0]), int(parts[1])
        except Exception:
            return None

    for r in rows:
        score_str = r.get("SCORE")
        parsed = parse_score(str(score_str)) if score_str not in (None, "") else None
        if parsed is not None:
            a, b = parsed
            # try to infer away_first on the first unambiguous scoring event
            if away_first is None and (a != last_a or b != last_b):
                home_desc = str(r.get("HOMEDESCRIPTION") or "").strip()
                vis_desc = str(r.get("VISITORDESCRIPTION") or "").strip()
                scored_side = "home" if home_desc else ("away" if vis_desc else "unknown")
                # only infer if exactly one side is indicated by description
                if scored_side in ("home", "away"):
                    da = a - last_a
                    db = b - last_b
                    if da > 0 and db == 0:
                        # side 'a' increased
                        away_first = True if scored_side == "away" else False
                    elif db > 0 and da == 0:
                        # side 'b' increased
                        away_first = False if scored_side == "away" else True

            # update last raw parts
            last_a, last_b = a, b

            if away_first is True:
                last_away, last_home = a, b
            elif away_first is False:
                last_home, last_away = a, b
            else:
                # mapping unknown: keep carry-forward as-is until inferred
                pass

        out.append((last_home, last_away))

    return out


def _fetch_via_nba_api(
    game_id: str,
    *,
    throttle_seconds: float,
    max_attempts: int,
    base_backoff_seconds: float,
    max_backoff_seconds: float,
    jitter_seconds: float,
    deadline_seconds: float,
    verbose: bool,
) -> tuple[str, bytes]:
    """
    Fetch PBP via stats.nba.com (NBA Stats API).

    Due diligence / correctness notes:
    - nba_api ships 3 PBP endpoints: playbyplay, playbyplayv2 (legacy tabular), playbyplayv3 (modern JSON)
    - playbyplayv3 already returns the same `game.actions` schema as the cdn.nba.com liveData feed
      (fields like actionNumber, clock, scoreHome/scoreAway, actionType/subType, etc.)
    - When possible, we prefer playbyplayv3 to avoid lossy v2 conversion.

    Returns (source_url_label, json_bytes).
    """
    # We try (A) stats playbyplayv3 (preferred), then (B) stats playbyplayv2 + conversion, then (C) nba_api wrapper.

    start = time.monotonic()
    last_err: BaseException | None = None
    rows: list[dict[str, Any]] = []
    last_stats_diag: dict[str, Any] | None = None
    last_v3_body: bytes | None = None
    for attempt in range(1, max_attempts + 1):
        if time.monotonic() - start > deadline_seconds:
            raise RuntimeError(f"nba_api deadline exceeded after {deadline_seconds:.1f}s for game_id={game_id}")
        try:
            # conservative throttle before request (plus jitter)
            if throttle_seconds > 0:
                if verbose:
                    print(f"[fetch_pbp] stats attempt {attempt}/{max_attempts} sleeping throttle={throttle_seconds}s", flush=True)
                time.sleep(throttle_seconds + (random.uniform(0, jitter_seconds) if jitter_seconds > 0 else 0.0))
            # Use nba_api's known-good headers (they include Host, Accept-Encoding, etc.).
            from nba_api.stats.library.http import STATS_HEADERS  # type: ignore
            import requests  # type: ignore

            # (A) Prefer playbyplayv3 (already loader-compatible)
            stats_base_v3 = "https://stats.nba.com/stats/playbyplayv3"
            stats_url_v3 = stats_base_v3 + "?" + urlencode({"GameID": game_id, "StartPeriod": 0, "EndPeriod": 14})
            if verbose:
                print(f"[fetch_pbp] GET {stats_base_v3} (game_id={game_id})", flush=True)
            resp_v3 = requests.get(stats_url_v3, headers=dict(STATS_HEADERS), timeout=max(5.0, float(30.0)))
            last_v3_body = resp_v3.content
            last_stats_diag = {
                "url": stats_url_v3,
                "status": int(resp_v3.status_code),
                "content_type": resp_v3.headers.get("content-type"),
                "body_prefix": (last_v3_body or b"")[:500].decode("utf-8", errors="replace"),
            }
            if verbose:
                print(f"[fetch_pbp] v3 status={resp_v3.status_code} content_type={resp_v3.headers.get('content-type')}", flush=True)
            if int(resp_v3.status_code) == 200:
                obj_v3 = parse_json_bytes(last_v3_body)
                game = obj_v3.get("game", {})
                actions = game.get("actions") if isinstance(game, dict) else None
                if isinstance(actions, list) and str(game.get("gameId")) == str(game_id):
                    # Success: return raw v3 bytes; it's already in the `game.actions` schema.
                    return stats_base_v3, last_v3_body

            # (B) Fall back to playbyplayv2 tabular, then convert.
            stats_base_v2 = "https://stats.nba.com/stats/playbyplayv2"
            stats_url_v2 = stats_base_v2 + "?" + urlencode({"GameID": game_id, "StartPeriod": 0, "EndPeriod": 14})
            if verbose:
                print(f"[fetch_pbp] GET {stats_base_v2} (game_id={game_id})", flush=True)
            resp = requests.get(stats_url_v2, headers=dict(STATS_HEADERS), timeout=max(5.0, float(30.0)))
            body = resp.content
            last_stats_diag = {
                "url": stats_url_v2,
                "status": int(resp.status_code),
                "content_type": resp.headers.get("content-type"),
                "body_prefix": body[:500].decode("utf-8", errors="replace"),
            }
            if verbose:
                print(f"[fetch_pbp] v2 status={resp.status_code} content_type={resp.headers.get('content-type')}", flush=True)
            if int(resp.status_code) != 200:
                raise RuntimeError(f"stats playbyplayv2: HTTP {resp.status_code}")

            obj = parse_json_bytes(body)
            # Stats returns either resultSets (list) or resultSet (dict), depending on endpoint.
            rs = obj.get("resultSets")
            if isinstance(rs, list) and rs:
                rs0 = rs[0]
                headers0 = rs0.get("headers")
                rowset0 = rs0.get("rowSet")
                if not isinstance(headers0, list) or not isinstance(rowset0, list):
                    raise RuntimeError("stats playbyplayv2: unexpected headers/rowSet structure")
                rows = [dict(zip(headers0, r, strict=False)) for r in rowset0 if isinstance(r, list)]
            else:
                rs1 = obj.get("resultSet")
                if isinstance(rs1, dict):
                    headers1 = rs1.get("headers")
                    rowset1 = rs1.get("rowSet")
                    if not isinstance(headers1, list) or not isinstance(rowset1, list):
                        raise RuntimeError("stats playbyplayv2: unexpected resultSet structure")
                    rows = [dict(zip(headers1, r, strict=False)) for r in rowset1 if isinstance(r, list)]
                else:
                    keys = sorted(obj.keys())
                    raise RuntimeError(f"stats playbyplayv2: missing resultSets/resultSet (top-level keys={keys})")

            break
        except BaseException as e:  # noqa: BLE001
            last_err = e
            if attempt >= max_attempts:
                break
            backoff = min(base_backoff_seconds * (2 ** (attempt - 1)), max_backoff_seconds)
            remaining = max(0.0, deadline_seconds - (time.monotonic() - start))
            if verbose:
                print(f"[fetch_pbp] stats attempt {attempt} failed ({type(e).__name__}): {e}. backoff={backoff:.2f}s", flush=True)
            time.sleep(min(backoff, remaining) + (random.uniform(0, jitter_seconds) if jitter_seconds > 0 else 0.0))
    if not rows:
        # (C) Fallback: nba_api wrapper (sometimes works even when direct parsing fails).
        try:
            from nba_api.stats.endpoints import playbyplayv3, playbyplayv2  # type: ignore

            if verbose:
                print("[fetch_pbp] falling back to nba_api PlayByPlayV3()", flush=True)
            pbp3 = playbyplayv3.PlayByPlayV3(game_id=game_id, timeout=30)
            raw3 = pbp3.nba_response.get_dict()
            raw3_bytes = json.dumps(raw3, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
            game3 = raw3.get("game", {})
            if isinstance(game3, dict) and isinstance(game3.get("actions"), list) and str(game3.get("gameId")) == str(game_id):
                return "nba_api.PlayByPlayV3", raw3_bytes

            if verbose:
                print("[fetch_pbp] falling back to nba_api PlayByPlayV2()", flush=True)
            pbp2 = playbyplayv2.PlayByPlayV2(game_id=game_id, timeout=30)
            df = pbp2.get_data_frames()[0]
            rows = df.to_dict(orient="records")
        except BaseException as e:  # noqa: BLE001
            diag = ""
            if last_stats_diag is not None:
                diag = f" stats_diag={last_stats_diag}"
            raise RuntimeError(f"Stats PBP fetch failed after {max_attempts} attempts for game_id={game_id}.{diag}") from (last_err or e)

    # Sort by event number for deterministic ordering
    def eventnum(r: dict[str, Any]) -> int:
        try:
            return int(r.get("EVENTNUM") or 0)
        except Exception:
            return 0

    rows.sort(key=eventnum)
    scores = _infer_score_order_and_carry_forward(rows)

    actions: list[dict[str, Any]] = []
    for r, (score_home, score_away) in zip(rows, scores, strict=True):
        ev = eventnum(r)
        period = int(r.get("PERIOD") or 0) if str(r.get("PERIOD") or "").strip() else 0
        pct = str(r.get("PCTIMESTRING") or "")
        msg_type = r.get("EVENTMSGTYPE")
        msg_action = r.get("EVENTMSGACTIONTYPE")

        # Team/player ids (often NULL for administrative events)
        team_id = r.get("PLAYER1_TEAM_ID")
        person_id = r.get("PLAYER1_ID")
        team_tricode = r.get("PLAYER1_TEAM_ABBREVIATION")
        player_name = r.get("PLAYER1_NAME")

        # Minimal, loader-compatible action dict
        a: dict[str, Any] = {
            "actionNumber": ev,
            # Match CDN/liveData convention: orderNumber ~= actionNumber * 10000
            "orderNumber": ev * 10000,
            "period": period,
            "periodType": _period_type(period),
            "clock": _clock_from_pctimestring(pct),
            "actionType": str(msg_type) if msg_type is not None else "",
            "subType": str(msg_action) if msg_action is not None else "",
            "description": _description_from_row(r),
            # scoreboard (carry-forward so loader doesn't crash)
            "scoreHome": score_home,
            "scoreAway": score_away,
            # optional dims
            "teamId": int(team_id) if team_id not in (None, "", 0) else None,
            "teamTricode": str(team_tricode) if team_tricode not in (None, "") else None,
            "personId": int(person_id) if person_id not in (None, "", 0) else None,
            "playerName": str(player_name) if player_name not in (None, "") else None,
            # fields the loader expects to exist (or safely defaults)
            "isFieldGoal": 1 if str(msg_type) in ("1", "2") else 0,
            "isTargetScoreLastPeriod": False,
            "qualifiers": None,
            "personIdsFilter": None,
            "possession": None,
            # Keep original row for debugging/traceability
            "rawStatsRow": r,
        }
        actions.append(a)

    obj = {"meta": {"code": 200, "source": "nba_api.playbyplayv2"}, "game": {"gameId": str(game_id), "actions": actions}}
    body = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "nba_api.stats.endpoints.PlayByPlayV2", body


def main() -> int:
    args = parse_args()
    game_id = args.game_id
    url = f"https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json"

    retry = HttpRetry(
        max_attempts=args.max_attempts,
        timeout_seconds=args.timeout_seconds,
        base_backoff_seconds=args.base_backoff_seconds,
        max_backoff_seconds=args.max_backoff_seconds,
        jitter_seconds=args.jitter_seconds,
        deadline_seconds=args.deadline_seconds,
    )

    fetched_url = url
    status = 200
    resp_headers: dict[str, str] = {}
    body: bytes

    if args.source in ("auto", "cdn"):
        try:
            if args.verbose:
                print(f"[fetch_pbp] source=cdn url={url}", flush=True)
            status, resp_headers, body = http_get_bytes(url, retry=retry)
            obj = parse_json_bytes(body)

            meta = obj.get("meta", {})
            if not isinstance(meta, dict) or meta.get("code") != 200:
                raise RuntimeError(f"Unexpected PBP meta.code: {meta.get('code')}")

            game = obj.get("game", {})
            if not isinstance(game, dict) or str(game.get("gameId")) != str(game_id):
                raise RuntimeError("Unexpected PBP game.gameId")

            actions = game.get("actions")
            if not isinstance(actions, list):
                raise RuntimeError("Unexpected PBP game.actions (expected list)")
        except Exception:
            if args.source == "cdn":
                raise
            if args.verbose:
                print("[fetch_pbp] CDN failed; falling back to stats/nba_api", flush=True)
            fetched_url, body = _fetch_via_nba_api(
                game_id,
                throttle_seconds=args.nba_api_throttle_seconds,
                max_attempts=args.max_attempts,
                base_backoff_seconds=args.base_backoff_seconds,
                max_backoff_seconds=args.max_backoff_seconds,
                jitter_seconds=args.jitter_seconds,
                deadline_seconds=args.deadline_seconds,
                verbose=bool(args.verbose),
            )
            status = 200
            resp_headers = {}
            obj = parse_json_bytes(body)
    else:
        if args.verbose:
            print("[fetch_pbp] source=nba_api(stats) (forced)", flush=True)
        fetched_url, body = _fetch_via_nba_api(
            game_id,
            throttle_seconds=args.nba_api_throttle_seconds,
            max_attempts=args.max_attempts,
            base_backoff_seconds=args.base_backoff_seconds,
            max_backoff_seconds=args.max_backoff_seconds,
            jitter_seconds=args.jitter_seconds,
            deadline_seconds=args.deadline_seconds,
            verbose=bool(args.verbose),
        )
        status = 200
        resp_headers = {}
        obj = parse_json_bytes(body)

    # Final validation (regardless of source)
    #
    # CDN liveData responses include meta.code==200.
    # Stats playbyplayv3 responses do NOT include meta.code, so we only enforce meta.code when present.
    meta = obj.get("meta", None)
    if meta is not None:
        if not isinstance(meta, dict):
            raise RuntimeError("Unexpected PBP meta (expected object)")
        if "code" in meta and meta.get("code") != 200:
            raise RuntimeError(f"Unexpected PBP meta.code: {meta.get('code')}")
    game = obj.get("game", {})
    if not isinstance(game, dict) or str(game.get("gameId")) != str(game_id):
        raise RuntimeError("Unexpected PBP game.gameId")
    actions = game.get("actions")
    if not isinstance(actions, list):
        raise RuntimeError("Unexpected PBP game.actions (expected list)")

    # Normalize stats-derived payloads to satisfy loader invariants (esp. missing orderNumber in playbyplayv3).
    # We do this after validation so we can safely write an archive that the loader can ingest.
    if _ensure_order_numbers(obj):
        body = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")

    out_path = Path(args.out)
    manifest_path = out_path.with_suffix(out_path.suffix + ".manifest.json")
    fetched_at = utc_now_iso_compact()

    write_with_manifest(
        out_path,
        manifest_path,
        url=fetched_url,
        http_status=status,
        response_headers=resp_headers,
        body=body,
        source_type="pbp",
        source_key=game_id,
        fetched_at_utc=fetched_at,
    )

    print(f"Wrote {out_path} (+ manifest). actions={len(actions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


