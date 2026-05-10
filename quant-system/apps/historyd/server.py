#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlparse


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPLAY_PATH = ROOT / "data" / "sample_bars.csv"
CSV_FIELDS = ["timestamp", "symbol", "exchange", "open", "high", "low", "close", "volume"]
OKX_BASE_URL = "https://www.okx.com"
OKX_DEFAULT_INSTRUMENTS = [
    "BTC-USDT",
    "ETH-USDT",
    "SOL-USDT",
    "XRP-USDT",
    "DOGE-USDT",
    "ADA-USDT",
    "BNB-USDT",
    "OKB-USDT",
    "LTC-USDT",
    "BCH-USDT",
    "LINK-USDT",
    "AVAX-USDT",
    "DOT-USDT",
    "TRX-USDT",
    "TON-USDT",
    "UNI-USDT",
    "AAVE-USDT",
    "PEPE-USDT",
    "SHIB-USDT",
    "XAUT-USDT",
    "SUI-USDT",
    "OP-USDT",
    "ARB-USDT",
    "NEAR-USDT",
    "FIL-USDT",
    "ETC-USDT",
    "ATOM-USDT",
    "APT-USDT",
    "INJ-USDT",
    "WLD-USDT",
    "POL-USDT",
    "CRV-USDT",
    "LDO-USDT",
    "RENDER-USDT",
    "ICP-USDT",
    "SEI-USDT",
    "ENS-USDT",
    "ORDI-USDT",
    "SATS-USDT",
    "JUP-USDT",
]
OKX_BAR_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1H": 3600,
    "2H": 7200,
    "4H": 14400,
    "1D": 86400,
}
DAY_MS = 24 * 60 * 60 * 1000
BACKFILL_LOCK = threading.Lock()
BACKFILL_JOBS: dict[str, dict[str, Any]] = {}
BACKFILL_THREADS: dict[str, threading.Thread] = {}


def configured_replay_path() -> Path:
    value = os.environ.get("KATRADE_HISTORY_REPLAY_PATH", "").strip()
    path = Path(value).expanduser() if value else DEFAULT_REPLAY_PATH
    return path if path.is_absolute() else ROOT / path


def history_cache_dir() -> Path:
    value = os.environ.get("KATRADE_HISTORY_CACHE_DIR", "").strip()
    path = Path(value).expanduser() if value else ROOT / "logs" / "cache" / "historyd"
    return path if path.is_absolute() else ROOT / path


def history_cache_ttl_seconds() -> int:
    raw = os.environ.get("KATRADE_HISTORY_CACHE_TTL_SECONDS", "1800").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 1800


def okx_base_url() -> str:
    return os.environ.get("OKX_BASE_URL", OKX_BASE_URL).strip().rstrip("/") or OKX_BASE_URL


def okx_instruments_config() -> list[str]:
    raw = os.environ.get("OKX_CRYPTO_INSTRUMENTS", ",".join(OKX_DEFAULT_INSTRUMENTS))
    values = [item.strip().upper() for item in raw.split(",") if item.strip()]
    return values or OKX_DEFAULT_INSTRUMENTS


def instrument_key(row: dict[str, str]) -> str:
    symbol = row.get("symbol", "").strip()
    exchange = row.get("exchange", "").strip()
    return f"{symbol}.{exchange}" if exchange else symbol


def read_rows() -> list[dict[str, str]]:
    path = configured_replay_path()
    if not path.exists():
        raise FileNotFoundError(f"history replay file does not exist: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(CSV_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError("history replay file missing fields: " + ", ".join(sorted(missing)))
        return [{field: row.get(field, "") for field in CSV_FIELDS} for row in reader]


def try_read_rows() -> tuple[list[dict[str, str]], str]:
    try:
        return read_rows(), ""
    except Exception as exc:
        return [], str(exc)


def csv_payload(rows: list[dict[str, str]]) -> bytes:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def contracts_summary(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = instrument_key(row)
        if not key:
            continue
        item = summary.setdefault(
            key,
            {
                "contract": key,
                "symbol": row.get("symbol", ""),
                "exchange": row.get("exchange", ""),
                "rows": 0,
                "start": row.get("timestamp", ""),
                "end": row.get("timestamp", ""),
            },
        )
        timestamp = row.get("timestamp", "")
        item["rows"] += 1
        item["start"] = min(item["start"], timestamp) if item["start"] else timestamp
        item["end"] = max(item["end"], timestamp) if item["end"] else timestamp
    return sorted(summary.values(), key=lambda item: item["contract"])


def text_from_epoch_ms(epoch_ms: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch_ms / 1000.0))


def epoch_ms_from_text(value: str) -> int:
    text = value.strip()
    if not text:
        raise ValueError("empty timestamp")
    if text.isdigit():
        raw = int(text)
        return raw if raw > 10_000_000_000 else raw * 1000
    from datetime import datetime, timezone

    normalized = text.replace("Z", "+00:00")
    if "T" not in normalized and " " in normalized:
        normalized = normalized.replace(" ", "T", 1)
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def safe_cache_component(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value) or "default"


def cleanup_cache() -> int:
    root = history_cache_dir()
    ttl = history_cache_ttl_seconds()
    if not root.exists():
        return 0
    deleted = 0
    now = time.time()
    for path in root.rglob("*.json"):
        if ttl <= 0 or now - path.stat().st_mtime > ttl:
            path.unlink(missing_ok=True)
            deleted += 1
    return deleted


def cache_path(name: str) -> Path:
    return history_cache_dir() / "okx" / f"{safe_cache_component(name)}.json"


def read_cached_json(name: str) -> Any:
    path = cache_path(name)
    ttl = history_cache_ttl_seconds()
    if not path.exists() or ttl <= 0 or time.time() - path.stat().st_mtime > ttl:
        return None
    os.utime(path, None)
    return json.loads(path.read_text(encoding="utf-8"))


def write_cached_json(name: str, value: Any) -> None:
    path = cache_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def truthy_param(params: dict[str, list[str]], key: str) -> bool:
    value = str(params.get(key, [""])[0]).strip().lower()
    return value in {"1", "true", "yes", "on", "live", "refresh"}


def okx_series_dir(inst_id: str, bar: str) -> Path:
    return history_cache_dir() / "okx_series" / safe_cache_component(inst_id) / safe_cache_component(bar)


def day_start_ms(epoch_ms: int) -> int:
    return epoch_ms - (epoch_ms % DAY_MS)


def day_key(epoch_ms: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(epoch_ms / 1000.0))


def okx_series_path(inst_id: str, bar: str, day_ms: int) -> Path:
    return okx_series_dir(inst_id, bar) / f"{day_key(day_ms)}.json"


def read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    ttl = history_cache_ttl_seconds()
    if ttl <= 0 or time.time() - path.stat().st_mtime > ttl:
        path.unlink(missing_ok=True)
        return default
    os.utime(path, None)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def merge_okx_series(inst_id: str, bar: str, bars: list[dict[str, Any]]) -> int:
    if not bars:
        return 0
    grouped: dict[int, dict[int, dict[str, Any]]] = {}
    for item in bars:
        ts = int(item["t"])
        grouped.setdefault(day_start_ms(ts), {})[ts] = item
    written = 0
    for day_ms, items in grouped.items():
        path = okx_series_path(inst_id, bar, day_ms)
        existing = read_json_file(path, [])
        merged = {int(item["t"]): item for item in existing if isinstance(item, dict) and item.get("t") is not None}
        merged.update(items)
        ordered = [merged[key] for key in sorted(merged)]
        write_json_file(path, ordered)
        written += len(items)
    return written


def load_okx_series(inst_id: str, bar: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
    bars: dict[int, dict[str, Any]] = {}
    current = day_start_ms(start_ms)
    end_day = day_start_ms(end_ms)
    while current <= end_day:
        path = okx_series_path(inst_id, bar, current)
        for item in read_json_file(path, []):
            if not isinstance(item, dict) or item.get("t") is None:
                continue
            ts = int(item["t"])
            if start_ms <= ts <= end_ms:
                bars[ts] = item
        current += DAY_MS
    return [bars[key] for key in sorted(bars)]


def expected_bar_count(start_ms: int, end_ms: int, bar: str) -> int:
    return max(1, int((end_ms - start_ms) / (OKX_BAR_SECONDS.get(bar, 60) * 1000)) + 1)


def okx_series_summary() -> list[dict[str, Any]]:
    root = history_cache_dir() / "okx_series"
    summaries: list[dict[str, Any]] = []
    if not root.exists():
        return summaries
    for inst_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        for bar_dir in sorted(path for path in inst_dir.iterdir() if path.is_dir()):
            row_count = 0
            start_ts: int | None = None
            end_ts: int | None = None
            shards = 0
            for path in sorted(bar_dir.glob("*.json")):
                items = read_json_file(path, [])
                if not items:
                    continue
                shards += 1
                row_count += len(items)
                first = int(items[0]["t"])
                last = int(items[-1]["t"])
                start_ts = first if start_ts is None else min(start_ts, first)
                end_ts = last if end_ts is None else max(end_ts, last)
            if row_count:
                summaries.append(
                    {
                        "inst_id": inst_dir.name,
                        "bar": bar_dir.name,
                        "rows": row_count,
                        "shards": shards,
                        "start": start_ts,
                        "end": end_ts,
                        "start_text": text_from_epoch_ms(start_ts or 0),
                        "end_text": text_from_epoch_ms(end_ts or 0),
                    }
                )
    return summaries


def okx_public_get(path: str) -> dict[str, Any]:
    request = urllib.request.Request(
        okx_base_url() + path,
        headers={"Accept": "application/json", "User-Agent": "KaTradeHistoryD/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if str(payload.get("code", "0")) != "0":
                raise RuntimeError(payload.get("msg") or "OKX API error")
            return payload
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"OKX HTTP {exc.code}: {body[:300]}") from exc


def okx_row_to_bar(row: list[Any]) -> dict[str, Any]:
    return {
        "t": int(row[0]),
        "o": float(row[1]),
        "h": float(row[2]),
        "l": float(row[3]),
        "c": float(row[4]),
        "v": float(row[5]),
        "confirm": row[8] if len(row) > 8 else "",
    }


def okx_fetch_window(inst_id: str, bar: str, start_ms: int, end_ms: int, max_pages: int) -> dict[str, Any]:
    series_bars = load_okx_series(inst_id, bar, start_ms, end_ms)
    expected = expected_bar_count(start_ms, end_ms, bar)
    # A backfilled window should be reused directly. The threshold allows for
    # exchange maintenance gaps and incomplete current candles.
    if len(series_bars) >= max(1, int(expected * 0.92)):
        return {
            "ok": True,
            "inst_id": inst_id,
            "bar": bar,
            "start": start_ms,
            "end": end_ms,
            "bars": series_bars,
            "rows": len(series_bars),
            "cache": "series",
            "truncated": False,
            "warning": "",
        }

    cache_name = f"window_{inst_id}_{bar}_{start_ms}_{end_ms}_{max_pages}"
    cached = read_cached_json(cache_name)
    if cached is not None:
        cached["cache"] = "hit"
        return cached

    rows: dict[int, dict[str, Any]] = {}
    cursor = end_ms + OKX_BAR_SECONDS.get(bar, 60) * 1000
    truncated = False
    endpoint = "/api/v5/market/history-candles"
    for page in range(max_pages):
        query = urlencode({"instId": inst_id, "bar": bar, "after": str(cursor), "limit": "100"})
        payload = okx_public_get(f"{endpoint}?{query}")
        data = payload.get("data", [])
        if not data:
            break
        page_bars = [okx_row_to_bar(row) for row in data if isinstance(row, list) and len(row) >= 6]
        for item in page_bars:
            if start_ms <= int(item["t"]) <= end_ms:
                rows[int(item["t"])] = item
        min_ts = min(int(item["t"]) for item in page_bars)
        if min_ts <= start_ms:
            break
        cursor = min_ts
        if page == max_pages - 1:
            truncated = True

    bars = [rows[key] for key in sorted(rows)]
    merge_okx_series(inst_id, bar, bars)
    result = {
        "ok": True,
        "inst_id": inst_id,
        "bar": bar,
        "start": start_ms,
        "end": end_ms,
        "bars": bars,
        "rows": len(bars),
        "cache": "miss",
        "truncated": truncated,
        "warning": "历史窗口超过本次分页上限，已返回可用部分。" if truncated else "",
    }
    write_cached_json(cache_name, result)
    return result


def aggregate_bars(bars: list[dict[str, Any]], width: int) -> tuple[list[dict[str, Any]], int]:
    if not bars:
        return [], 1
    target = max(200, min(width, 2400))
    bucket_size = max(1, math.ceil(len(bars) / target))
    result = []
    for index in range(0, len(bars), bucket_size):
        bucket = bars[index : index + bucket_size]
        first = bucket[0]
        last = bucket[-1]
        result.append(
            {
                "t": first["t"],
                "o": first["o"],
                "h": max(item["h"] for item in bucket),
                "l": min(item["l"] for item in bucket),
                "c": last["c"],
                "v": sum(float(item["v"]) for item in bucket),
                "n": len(bucket),
                "confirm": last.get("confirm", ""),
            }
        )
    return result, bucket_size


def okx_candles_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    cleanup_cache()
    inst_id = params.get("instId", [okx_instruments_config()[0]])[0].upper()
    bar = params.get("bar", ["1m"])[0]
    if bar not in OKX_BAR_SECONDS:
        bar = "1m"
    now_ms = int(time.time() * 1000)
    limit = max(20, min(int(params.get("limit", ["500"])[0]), 5000))
    default_end = now_ms
    default_start = default_end - limit * OKX_BAR_SECONDS[bar] * 1000
    start_ms = int(params.get("start", [str(default_start)])[0])
    end_ms = int(params.get("end", [str(default_end)])[0])
    if end_ms < start_ms:
        start_ms, end_ms = end_ms, start_ms
    width = max(200, min(int(params.get("width", ["1400"])[0]), 2400))
    max_pages = max(1, min(int(params.get("max_pages", [os.environ.get("KATRADE_OKX_MAX_PAGES", "8")])[0]), 200))
    if truthy_param(params, "live") or truthy_param(params, "refresh"):
        query = urlencode({"instId": inst_id, "bar": bar, "limit": str(min(limit, 500))})
        payload = okx_public_get(f"/api/v5/market/candles?{query}")
        rows = [
            okx_row_to_bar(row)
            for row in payload.get("data", [])
            if isinstance(row, list) and len(row) >= 6
        ]
        rows = [item for item in rows if start_ms <= int(item["t"]) <= end_ms]
        rows.sort(key=lambda item: int(item["t"]))
        merge_okx_series(inst_id, bar, rows)
        bars, bucket_size = aggregate_bars(rows, width)
        return {
            "ok": True,
            "inst_id": inst_id,
            "bar": bar,
            "start": start_ms,
            "end": end_ms,
            "bars": bars,
            "raw_rows": len(rows),
            "rows": len(bars),
            "bucket_size": bucket_size,
            "cache": "live",
            "truncated": False,
            "warning": "",
            "start_text": text_from_epoch_ms(start_ms),
            "end_text": text_from_epoch_ms(end_ms),
        }
    raw = okx_fetch_window(inst_id, bar, start_ms, end_ms, max_pages)
    bars, bucket_size = aggregate_bars(raw["bars"], width)
    return {
        **raw,
        "bars": bars,
        "raw_rows": raw["rows"],
        "rows": len(bars),
        "bucket_size": bucket_size,
        "start_text": text_from_epoch_ms(start_ms),
        "end_text": text_from_epoch_ms(end_ms),
    }


def okx_tickers_payload() -> dict[str, Any]:
    cached = read_cached_json("tickers_spot")
    if cached is not None:
        cached["cache"] = "hit"
        return cached
    payload = okx_public_get("/api/v5/market/tickers?instType=SPOT")
    wanted = set(okx_instruments_config())
    tickers = []
    for item in payload.get("data", []):
        if item.get("instId") not in wanted:
            continue
        tickers.append(
            {
                "inst_id": item.get("instId", ""),
                "last": item.get("last", ""),
                "bid": item.get("bidPx", ""),
                "ask": item.get("askPx", ""),
                "high_24h": item.get("high24h", ""),
                "low_24h": item.get("low24h", ""),
                "volume_24h": item.get("vol24h", ""),
                "timestamp": item.get("ts", ""),
            }
        )
    result = {"ok": True, "tickers": tickers, "cache": "miss"}
    write_cached_json("tickers_spot", result)
    return result


def backfill_job_id(inst_ids: list[str], bar: str, start_ms: int, end_ms: int) -> str:
    raw = f"{','.join(inst_ids)}_{bar}_{start_ms}_{end_ms}"
    return safe_cache_component(raw)[-180:]


def update_backfill_job(job_id: str, **values: Any) -> None:
    with BACKFILL_LOCK:
        job = BACKFILL_JOBS.setdefault(job_id, {})
        job.update(values)
        job["updated_at"] = text_from_epoch_ms(int(time.time() * 1000))


def backfill_worker(job_id: str) -> None:
    with BACKFILL_LOCK:
        job = dict(BACKFILL_JOBS[job_id])
    inst_ids = list(job.get("inst_ids", []))
    bar = str(job.get("bar", "1m"))
    start_ms = int(job.get("start", 0))
    end_ms = int(job.get("end", int(time.time() * 1000)))
    throttle_ms = int(job.get("throttle_ms", 180))
    total_written = 0
    total_pages = 0
    try:
        update_backfill_job(job_id, status="running", error="")
        for inst_id in inst_ids:
            cursor = end_ms + OKX_BAR_SECONDS.get(bar, 60) * 1000
            inst_written = 0
            while cursor > start_ms:
                if BACKFILL_JOBS.get(job_id, {}).get("cancel_requested"):
                    update_backfill_job(job_id, status="cancelled")
                    return
                query = urlencode({"instId": inst_id, "bar": bar, "after": str(cursor), "limit": "100"})
                payload = okx_public_get(f"/api/v5/market/history-candles?{query}")
                data = payload.get("data", [])
                if not data:
                    break
                page_bars = [okx_row_to_bar(row) for row in data if isinstance(row, list) and len(row) >= 6]
                if not page_bars:
                    break
                selected = [item for item in page_bars if int(item["t"]) >= start_ms and int(item["t"]) <= end_ms]
                written = merge_okx_series(inst_id, bar, selected)
                inst_written += written
                total_written += written
                total_pages += 1
                min_ts = min(int(item["t"]) for item in page_bars)
                update_backfill_job(
                    job_id,
                    current_inst_id=inst_id,
                    current_cursor=min_ts,
                    current_cursor_text=text_from_epoch_ms(min_ts),
                    pages=total_pages,
                    rows_written=total_written,
                    progress=max(0.0, min(1.0, (end_ms - min_ts) / max(end_ms - start_ms, 1))),
                )
                if min_ts <= start_ms:
                    break
                cursor = min_ts
                time.sleep(max(throttle_ms, 0) / 1000.0)
            update_backfill_job(job_id, last_completed_inst_id=inst_id, last_completed_rows=inst_written)
        update_backfill_job(job_id, status="completed", progress=1.0, completed_at=text_from_epoch_ms(int(time.time() * 1000)))
    except Exception as exc:
        update_backfill_job(job_id, status="failed", error=str(exc))


def parse_backfill_body(body: dict[str, Any]) -> dict[str, Any]:
    inst_ids_raw = body.get("instIds") or body.get("inst_ids") or okx_instruments_config()
    if isinstance(inst_ids_raw, str):
        inst_ids = [item.strip().upper() for item in inst_ids_raw.split(",") if item.strip()]
    else:
        inst_ids = [str(item).strip().upper() for item in inst_ids_raw if str(item).strip()]
    inst_ids = inst_ids or okx_instruments_config()
    bar = str(body.get("bar", "1m"))
    if bar not in OKX_BAR_SECONDS:
        bar = "1m"
    now_ms = int(time.time() * 1000)
    if body.get("start") is not None:
        start_ms = int(body["start"])
    else:
        days = max(1, min(int(body.get("days", 7)), 730))
        start_ms = now_ms - days * DAY_MS
    end_ms = int(body.get("end", now_ms))
    if end_ms < start_ms:
        start_ms, end_ms = end_ms, start_ms
    throttle_ms = max(0, min(int(body.get("throttle_ms", 180)), 3000))
    return {"inst_ids": inst_ids, "bar": bar, "start": start_ms, "end": end_ms, "throttle_ms": throttle_ms}


def start_backfill(body: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_backfill_body(body)
    job_id = backfill_job_id(parsed["inst_ids"], parsed["bar"], parsed["start"], parsed["end"])
    with BACKFILL_LOCK:
        existing = BACKFILL_JOBS.get(job_id)
        if existing and existing.get("status") in {"queued", "running"}:
            return {"ok": True, "job": dict(existing), "reused": True}
        BACKFILL_JOBS[job_id] = {
            "id": job_id,
            "status": "queued",
            "progress": 0.0,
            "pages": 0,
            "rows_written": 0,
            "created_at": text_from_epoch_ms(int(time.time() * 1000)),
            "start_text": text_from_epoch_ms(parsed["start"]),
            "end_text": text_from_epoch_ms(parsed["end"]),
            **parsed,
        }
        thread = threading.Thread(target=backfill_worker, args=(job_id,), daemon=True)
        BACKFILL_THREADS[job_id] = thread
        thread.start()
        return {"ok": True, "job": dict(BACKFILL_JOBS[job_id]), "reused": False}


def list_backfill_jobs() -> list[dict[str, Any]]:
    with BACKFILL_LOCK:
        return sorted((dict(job) for job in BACKFILL_JOBS.values()), key=lambda item: item.get("created_at", ""), reverse=True)


def cancel_backfill(body: dict[str, Any]) -> dict[str, Any]:
    job_id = str(body.get("id", "")).strip()
    if not job_id:
        raise ValueError("missing backfill job id")
    with BACKFILL_LOCK:
        job = BACKFILL_JOBS.get(job_id)
        if not job:
            return {"ok": False, "error": "backfill job not found"}
        if job.get("status") in {"completed", "failed", "cancelled"}:
            return {"ok": True, "job": dict(job), "already_done": True}
        job["cancel_requested"] = True
        job["updated_at"] = text_from_epoch_ms(int(time.time() * 1000))
        return {"ok": True, "job": dict(job)}


def okx_contract_from_key(contract: str) -> str:
    value = contract.strip().upper()
    if value.endswith(".OKX"):
        value = value[:-4]
    return value or okx_instruments_config()[0]


def okx_csv_payload(params: dict[str, list[str]]) -> bytes:
    contract = params.get("contract", [okx_instruments_config()[0]])[0]
    inst_id = okx_contract_from_key(contract)
    request_params = dict(params)
    request_params["instId"] = [inst_id]
    request_params["width"] = ["5000"]
    request_params.setdefault("max_pages", ["20"])
    payload = okx_candles_payload(request_params)
    rows = []
    symbol, exchange = inst_id, "OKX"
    for bar in payload["bars"]:
        rows.append(
            {
                "timestamp": text_from_epoch_ms(int(bar["t"])),
                "symbol": symbol,
                "exchange": exchange,
                "open": str(bar["o"]),
                "high": str(bar["h"]),
                "low": str(bar["l"]),
                "close": str(bar["c"]),
                "volume": str(bar["v"]),
            }
        )
    return csv_payload(rows)


def filter_contracts(rows: list[dict[str, str]], contracts: list[str]) -> list[dict[str, str]]:
    wanted = {contract.strip() for contract in contracts if contract.strip()}
    if not wanted:
        return rows
    return [row for row in rows if instrument_key(row) in wanted]


class Handler(BaseHTTPRequestHandler):
    server_version = "KaTradeHistoryD/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_csv(self, data: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        try:
            route = urlparse(self.path)
            params = parse_qs(route.query)

            if route.path == "/api/health":
                rows, replay_error = try_read_rows()
                self.send_json(
                    {
                        "ok": True,
                        "service": "historyd",
                        "path": str(configured_replay_path()),
                        "cache_dir": str(history_cache_dir()),
                        "cache_ttl_seconds": history_cache_ttl_seconds(),
                        "okx_base_url": okx_base_url(),
                        "okx_instruments": okx_instruments_config(),
                        "okx_series": okx_series_summary(),
                        "backfill_jobs": list_backfill_jobs()[:10],
                        "replay_error": replay_error,
                        "row_count": len(rows),
                        "contract_count": len(contracts_summary(rows)),
                    }
                )
                return

            if route.path == "/api/contracts":
                rows, replay_error = try_read_rows()
                okx_contracts = [
                    {
                        "contract": f"{inst_id}.OKX",
                        "symbol": inst_id,
                        "exchange": "OKX",
                        "rows": 0,
                        "start": "",
                        "end": "",
                    }
                    for inst_id in okx_instruments_config()
                ]
                self.send_json({"contracts": contracts_summary(rows) + okx_contracts, "replay_error": replay_error})
                return

            if route.path == "/api/bars.csv":
                contract = params.get("contract", [""])[0]
                if contract.upper().endswith(".OKX"):
                    self.send_csv(okx_csv_payload(params))
                    return
                rows = read_rows()
                selected = filter_contracts(rows, [contract])
                self.send_csv(csv_payload(selected))
                return

            if route.path == "/api/replay.csv":
                rows = read_rows()
                contracts = ",".join(params.get("contracts", [])).split(",")
                selected = filter_contracts(rows, contracts)
                self.send_csv(csv_payload(selected))
                return

            if route.path == "/api/okx/tickers":
                self.send_json(okx_tickers_payload())
                return

            if route.path == "/api/okx/candles":
                self.send_json(okx_candles_payload(params))
                return

            if route.path == "/api/okx/bars.csv":
                self.send_csv(okx_csv_payload(params))
                return

            if route.path == "/api/okx/series":
                self.send_json({"ok": True, "series": okx_series_summary()})
                return

            if route.path == "/api/okx/backfill":
                self.send_json({"ok": True, "jobs": list_backfill_jobs()})
                return

            self.send_error(404)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def do_POST(self) -> None:
        try:
            route = urlparse(self.path)
            if route.path == "/api/okx/backfill":
                self.send_json(start_backfill(self.read_json()))
                return
            if route.path == "/api/okx/backfill/cancel":
                self.send_json(cancel_backfill(self.read_json()))
                return
            self.send_error(404)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)


def main() -> int:
    host = os.environ.get("KATRADE_HISTORY_HOST", "127.0.0.1")
    port = int(os.environ.get("KATRADE_HISTORY_PORT", "8790"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"KaTrade historyd listening on http://{host}:{port}")
    print(f"Replay file: {configured_replay_path()}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
