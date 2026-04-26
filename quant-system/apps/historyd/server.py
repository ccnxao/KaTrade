#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPLAY_PATH = ROOT / "data" / "sample_bars.csv"
CSV_FIELDS = ["timestamp", "symbol", "exchange", "open", "high", "low", "close", "volume"]


def configured_replay_path() -> Path:
    value = os.environ.get("KATRADE_HISTORY_REPLAY_PATH", "").strip()
    path = Path(value).expanduser() if value else DEFAULT_REPLAY_PATH
    return path if path.is_absolute() else ROOT / path


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

    def do_GET(self) -> None:
        try:
            route = urlparse(self.path)
            params = parse_qs(route.query)
            rows = read_rows()

            if route.path == "/api/health":
                self.send_json(
                    {
                        "ok": True,
                        "service": "historyd",
                        "path": str(configured_replay_path()),
                        "row_count": len(rows),
                        "contract_count": len(contracts_summary(rows)),
                    }
                )
                return

            if route.path == "/api/contracts":
                self.send_json({"contracts": contracts_summary(rows)})
                return

            if route.path == "/api/bars.csv":
                contract = params.get("contract", [""])[0]
                selected = filter_contracts(rows, [contract])
                self.send_csv(csv_payload(selected))
                return

            if route.path == "/api/replay.csv":
                contracts = ",".join(params.get("contracts", [])).split(",")
                selected = filter_contracts(rows, contracts)
                self.send_csv(csv_payload(selected))
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
