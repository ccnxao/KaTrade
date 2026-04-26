#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import csv
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static"
LOG_DIR = ROOT / "logs"
DEFAULT_CONFIG = ROOT / "config" / "default.cfg"
API_KEY_CONFIG = ROOT / "config" / "api_key.config"
LAST_PLATFORM_OUTPUT = LOG_DIR / "last_platform_run.txt"
RUN_DIR = LOG_DIR / "runs"
KIMI_CLI_EXTRACT_DIR = Path("/tmp/katrade-kimi-cli")
KIMI_CLI_WORK_DIR = Path("/tmp/katrade-kimi-agent-work")
AGENT_SESSION_DIR = LOG_DIR / "agent_sessions"
AGENT_MAX_HISTORY = 12
AGENT_LOCK = threading.Lock()
SESSION_ID_RE = re.compile(r"^[a-f0-9-]{32,36}$")
RUN_ID_RE = re.compile(r"^\d{8}-\d{6}(?:-[a-f0-9]{8})?$")

PROVIDERS = {
    "kimi": {
        "name": "Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "base_url_env": "KIMI_BASE_URL",
        "env": "MOONSHOT_API_KEY",
        "default_model": "kimi-k2.6",
        "model_env": "KIMI_MODEL",
    },
    "kimi_coding": {
        "name": "Kimi Coding Plan",
        "transport": "cli",
        "base_url": "local Kimi Code CLI",
        "base_url_env": "KIMI_CLI_PATH",
        "env": "KIMI_CLI_PATH",
        "default_model": "kimi-code/kimi-for-coding",
        "model_env": "KIMI_CODING_MODEL",
        "max_steps_env": "KIMI_CLI_MAX_STEPS",
        "default_max_steps": "1",
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "base_url_env": "DEEPSEEK_BASE_URL",
        "env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-v4-flash",
        "model_env": "DEEPSEEK_MODEL",
    },
}

CONFIG_KEYS = {
    "replay_path",
    "event_log_path",
    "report_json_path",
    "strategy.enabled",
    "history.mode",
    "history.server_url",
    "history.contracts",
    "history.cache_dir",
    "history.cache_ttl_seconds",
    "strategy.donchian.lookback",
    "strategy.ma_cross.fast_window",
    "strategy.ma_cross.slow_window",
    "strategy.macd.fast_alpha",
    "strategy.macd.slow_alpha",
    "strategy.macd.signal_alpha",
    "strategy.bollinger.window",
    "strategy.bollinger.band_width",
    "strategy.rsi.window",
    "strategy.rsi.oversold",
    "strategy.rsi.overbought",
    "print_cycles",
    "print_event_stream",
    "initial_cash",
    "optimizer.max_single_weight",
    "optimizer.max_gross",
    "risk.max_single_weight",
    "risk.max_gross",
    "execution.min_rebalance_delta",
    "execution.max_participation_rate",
}

STRATEGY_CATALOG = [
    {
        "id": "momentum",
        "display_name": "动量基线",
        "style": "trend",
        "horizon": "日频",
        "description": "日内收益为正时给多头信号，用作趋势策略基线。",
        "default_enabled": True,
    },
    {
        "id": "mean_reversion",
        "display_name": "均值回归基线",
        "style": "mean_reversion",
        "horizon": "日频",
        "description": "对异常大的日内涨跌做反向信号，用作震荡策略基线。",
        "default_enabled": True,
    },
    {
        "id": "defensive",
        "display_name": "防御资产",
        "style": "defensive",
        "horizon": "日频",
        "description": "危机状态下偏向黄金、债券等防御资产。",
        "default_enabled": True,
    },
    {
        "id": "donchian_breakout",
        "display_name": "唐奇安突破",
        "style": "trend",
        "horizon": "日频",
        "description": "突破上一段历史高低点后顺势跟随。",
        "default_enabled": True,
        "params": [
            {"key": "strategy.donchian.lookback", "label": "回看周期", "default": "3", "kind": "int"}
        ],
    },
    {
        "id": "ma_cross",
        "display_name": "均线交叉",
        "style": "trend",
        "horizon": "日频",
        "description": "快慢均线价差作为趋势方向和强度。",
        "default_enabled": True,
        "params": [
            {"key": "strategy.ma_cross.fast_window", "label": "快均线", "default": "2", "kind": "int"},
            {"key": "strategy.ma_cross.slow_window", "label": "慢均线", "default": "4", "kind": "int"},
        ],
    },
    {
        "id": "macd_trend",
        "display_name": "MACD 趋势",
        "style": "trend",
        "horizon": "日频",
        "description": "用快慢 EMA 差和信号线判断趋势动量。",
        "default_enabled": True,
        "params": [
            {"key": "strategy.macd.fast_alpha", "label": "快 EMA alpha", "default": "0.55", "kind": "float"},
            {"key": "strategy.macd.slow_alpha", "label": "慢 EMA alpha", "default": "0.30", "kind": "float"},
            {"key": "strategy.macd.signal_alpha", "label": "信号线 alpha", "default": "0.45", "kind": "float"},
        ],
    },
    {
        "id": "bollinger_reversion",
        "display_name": "布林带反转",
        "style": "mean_reversion",
        "horizon": "日频",
        "description": "价格偏离滚动均值超过阈值时做反向信号。",
        "default_enabled": True,
        "params": [
            {"key": "strategy.bollinger.window", "label": "窗口", "default": "4", "kind": "int"},
            {"key": "strategy.bollinger.band_width", "label": "带宽", "default": "1.2", "kind": "float"},
        ],
    },
    {
        "id": "rsi_reversion",
        "display_name": "RSI 反转",
        "style": "mean_reversion",
        "horizon": "日频",
        "description": "RSI 高位视作过热、低位视作超卖。",
        "default_enabled": True,
        "params": [
            {"key": "strategy.rsi.window", "label": "窗口", "default": "4", "kind": "int"},
            {"key": "strategy.rsi.oversold", "label": "超卖阈值", "default": "35", "kind": "float"},
            {"key": "strategy.rsi.overbought", "label": "超买阈值", "default": "65", "kind": "float"},
        ],
    },
    {
        "id": "range_fade",
        "display_name": "区间边缘反转",
        "style": "mean_reversion",
        "horizon": "日频",
        "description": "收盘靠近日内区间边缘时押注回到区间内部。",
        "default_enabled": True,
    },
]


def parse_config(path: Path = DEFAULT_CONFIG) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def parse_key_value_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_api_key(env_name: str) -> str:
    return get_local_setting(env_name, "")


def get_local_setting(name: str, default: str) -> str:
    env_value = os.environ.get(name, "").strip()
    if env_value:
        return env_value
    return parse_key_value_file(API_KEY_CONFIG).get(name, default).strip() or default


def provider_base_url(provider: dict[str, Any]) -> str:
    if provider.get("transport") == "cli":
        path, _ = resolve_kimi_cli()
        return str(path) if path else provider["base_url"]
    return get_local_setting(provider["base_url_env"], provider["base_url"]).rstrip("/")


def provider_default_model(provider: dict[str, Any]) -> str:
    return get_local_setting(provider["model_env"], provider["default_model"])


def normalize_kimi_cli_model(model: str) -> str:
    value = model.strip()
    if value in {"", "default", "kimi-cli-default"}:
        return ""
    if value == "kimi-for-coding":
        return "kimi-code/kimi-for-coding"
    return value


def kimi_cli_environment() -> dict[str, str]:
    env = os.environ.copy()
    settings = parse_key_value_file(API_KEY_CONFIG)
    mappings = {
        "KIMI_API_KEY": settings.get("KIMI_API_KEY", "") or settings.get("KIMI_CODING_API_KEY", ""),
        "KIMI_BASE_URL": settings.get("KIMI_CODING_BASE_URL", ""),
        "KIMI_MODEL_NAME": normalize_kimi_cli_model(settings.get("KIMI_CODING_MODEL", "")),
    }
    for key, value in mappings.items():
        if value and not env.get(key, "").strip():
            env[key] = value
    return env


def local_setting_source(name: str) -> str:
    if os.environ.get(name, "").strip():
        return "environment"
    if parse_key_value_file(API_KEY_CONFIG).get(name, "").strip():
        return "config/api_key.config"
    return ""


def provider_api_key_names(provider: dict[str, Any]) -> list[str]:
    return [provider["env"], *provider.get("env_aliases", [])]


def get_provider_api_key(provider: dict[str, Any]) -> str:
    for name in provider_api_key_names(provider):
        value = get_local_setting(name, "")
        if value:
            return value
    return ""


def provider_api_key_source(provider: dict[str, Any]) -> str:
    for name in provider_api_key_names(provider):
        source = local_setting_source(name)
        if source:
            return source
    return ""


def provider_api_key_label(provider: dict[str, Any]) -> str:
    return " 或 ".join(provider_api_key_names(provider))


def provider_user_agent(provider: dict[str, Any]) -> str:
    env_name = provider.get("user_agent_env")
    if not env_name:
        return "KaTradeLocalQuantAgent/0.1"
    return get_local_setting(env_name, provider.get("default_user_agent", "KaTradeLocalQuantAgent/0.1"))


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ensure_agent_session_dir() -> None:
    AGENT_SESSION_DIR.mkdir(parents=True, exist_ok=True)


def safe_session_id(session_id: str) -> str:
    value = session_id.strip()
    if not SESSION_ID_RE.fullmatch(value):
        raise ValueError("无效的会话 ID")
    return value


def agent_session_path(session_id: str) -> Path:
    return AGENT_SESSION_DIR / f"{safe_session_id(session_id)}.json"


def default_agent_session(provider: str = "kimi_coding", model: str = "") -> dict[str, Any]:
    timestamp = now_iso()
    return {
        "id": str(uuid4()),
        "title": "新的研究会话",
        "provider": provider,
        "model": model,
        "created_at": timestamp,
        "updated_at": timestamp,
        "messages": [],
    }


def summarize_session_title(messages: list[dict[str, Any]]) -> str:
    for message in messages:
        if message.get("role") == "user":
            content = str(message.get("content", "")).strip().replace("\n", " ")
            return content[:28] + ("..." if len(content) > 28 else "") if content else "新的研究会话"
    return "新的研究会话"


def save_agent_session(session: dict[str, Any]) -> None:
    ensure_agent_session_dir()
    session["updated_at"] = now_iso()
    session["title"] = summarize_session_title(session.get("messages", []))
    path = agent_session_path(str(session["id"]))
    path.write_text(json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_agent_session(session_id: str) -> dict[str, Any]:
    path = agent_session_path(session_id)
    if not path.exists():
        raise ValueError("找不到 Agent 会话")
    return json.loads(path.read_text(encoding="utf-8"))


def list_agent_sessions() -> list[dict[str, Any]]:
    ensure_agent_session_dir()
    sessions: list[dict[str, Any]] = []
    for path in sorted(AGENT_SESSION_DIR.glob("*.json"), reverse=True):
        try:
            session = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        sessions.append(
            {
                "id": session.get("id", path.stem),
                "title": session.get("title") or summarize_session_title(session.get("messages", [])),
                "provider": session.get("provider", "kimi_coding"),
                "model": session.get("model", ""),
                "updated_at": session.get("updated_at", ""),
                "message_count": len(session.get("messages", [])),
            }
        )
    sessions.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return sessions


def history_for_agent(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for message in messages[-AGENT_MAX_HISTORY:]:
        role = str(message.get("role", ""))
        content = str(message.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            history.append({"role": role, "content": content})
    return history


def history_as_text(messages: list[dict[str, str]]) -> str:
    if not messages:
        return "无"
    lines: list[str] = []
    role_names = {"user": "用户", "assistant": "助手"}
    for message in messages:
        role = role_names.get(message["role"], message["role"])
        lines.append(f"{role}: {message['content']}")
    return "\n".join(lines)


def kimi_cli_candidates() -> list[Path]:
    paths: list[Path] = []
    configured = get_local_setting("KIMI_CLI_PATH", "")
    if configured:
        paths.append(Path(configured).expanduser())
    paths.append(KIMI_CLI_EXTRACT_DIR / "kimi" / "kimi")
    extension_root = Path.home() / ".vscode" / "extensions"
    paths.extend(
        sorted(
            extension_root.glob("moonshot-ai.kimi-code-*-darwin-arm64/bin/uv-wrapper/kimi"),
            reverse=True,
        )
    )
    return paths


def latest_kimi_cli_archive() -> Optional[Path]:
    extension_root = Path.home() / ".vscode" / "extensions"
    archives = sorted(
        extension_root.glob("moonshot-ai.kimi-code-*-darwin-arm64/bin/kimi/archive.tar.gz"),
        reverse=True,
    )
    return archives[0] if archives else None


def is_executable_file(path: Path) -> bool:
    return path.exists() and path.is_file() and os.access(path, os.X_OK)


def extract_kimi_cli_from_archive() -> Optional[Path]:
    target = KIMI_CLI_EXTRACT_DIR / "kimi" / "kimi"
    if is_executable_file(target):
        return target
    archive = latest_kimi_cli_archive()
    if archive is None:
        return None
    KIMI_CLI_EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        base = KIMI_CLI_EXTRACT_DIR.resolve()
        for member in tar.getmembers():
            destination = (KIMI_CLI_EXTRACT_DIR / member.name).resolve()
            if not str(destination).startswith(str(base)):
                raise ValueError(f"unsafe archive member: {member.name}")
        tar.extractall(KIMI_CLI_EXTRACT_DIR)
    return target if is_executable_file(target) else None


def resolve_kimi_cli() -> tuple[Optional[Path], str]:
    configured = get_local_setting("KIMI_CLI_PATH", "")
    if configured and is_executable_file(Path(configured).expanduser()):
        return Path(configured).expanduser(), local_setting_source("KIMI_CLI_PATH") or "config"
    for path in kimi_cli_candidates():
        if is_executable_file(path):
            return path, "local Kimi Code CLI"
    extracted = extract_kimi_cli_from_archive()
    if extracted is not None:
        return extracted, "VS Code Kimi Code extension"
    return None, ""


def write_config(values: dict[str, Any], path: Path = DEFAULT_CONFIG) -> None:
    current = parse_config(path)
    for key, value in values.items():
        if key not in CONFIG_KEYS:
            raise ValueError(f"unsupported config key: {key}")
        current[key] = str(value)

    ordered = [
        "replay_path",
        "event_log_path",
        "report_json_path",
        "strategy.enabled",
        "history.mode",
        "history.server_url",
        "history.contracts",
        "history.cache_dir",
        "history.cache_ttl_seconds",
        "strategy.donchian.lookback",
        "strategy.ma_cross.fast_window",
        "strategy.ma_cross.slow_window",
        "strategy.macd.fast_alpha",
        "strategy.macd.slow_alpha",
        "strategy.macd.signal_alpha",
        "strategy.bollinger.window",
        "strategy.bollinger.band_width",
        "strategy.rsi.window",
        "strategy.rsi.oversold",
        "strategy.rsi.overbought",
        "print_cycles",
        "print_event_stream",
        "initial_cash",
        "optimizer.max_single_weight",
        "optimizer.max_gross",
        "risk.max_single_weight",
        "risk.max_gross",
        "execution.min_rebalance_delta",
        "execution.max_participation_rate",
    ]
    lines = ["# generated by KaTrade local platform"]
    lines.extend(f"{key}={current[key]}" for key in ordered if key in current)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_summary(path: Path = LOG_DIR / "last_run_summary.txt") -> dict[str, Any]:
    summary: dict[str, Any] = {}
    if not path.exists():
        return summary
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        try:
            if key in {"cycles", "event_count", "total_fills"}:
                summary[key] = int(value)
            else:
                summary[key] = float(value)
        except ValueError:
            summary[key] = value
    return summary


def parse_equity_curve(output: Optional[str] = None) -> list[dict[str, Any]]:
    if output is None:
        output = LAST_PLATFORM_OUTPUT.read_text(encoding="utf-8") if LAST_PLATFORM_OUTPUT.exists() else ""
    pattern = re.compile(
        r"- (?P<label>\d{4}-\d{2}-\d{2}) equity=(?P<equity>[-0-9.]+) "
        r"cash=(?P<cash>[-0-9.]+) gross=(?P<gross>[-0-9.]+)"
    )
    points: list[dict[str, Any]] = []
    for match in pattern.finditer(output):
        points.append(
            {
                "label": match.group("label"),
                "equity": float(match.group("equity")),
                "cash": float(match.group("cash")),
                "gross": float(match.group("gross")),
            }
        )
    return points


def read_events(limit: int = 200) -> list[dict[str, Any]]:
    config = parse_config()
    event_log_path = ROOT / config.get("event_log_path", "logs/events.jsonl")
    if not event_log_path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in event_log_path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def resolve_runtime_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def history_cache_root(config: Optional[dict[str, str]] = None) -> Path:
    config = config or parse_config()
    cache_dir = resolve_runtime_path(config.get("history.cache_dir", "logs/cache/history"))
    server = config.get("history.server_url", "http://127.0.0.1:8790").rstrip("/")
    server_slug = re.sub(r"[^A-Za-z0-9_-]", "_", server) or "default"
    return cache_dir / server_slug


def history_cache_profile(config: Optional[dict[str, str]] = None) -> dict[str, Any]:
    config = config or parse_config()
    root = history_cache_root(config)
    files = sorted(root.glob("*.csv")) if root.exists() else []
    return {
        "path": str(root),
        "file_count": len(files),
        "files": [path.name for path in files[-20:]],
        "ttl_seconds": int(config.get("history.cache_ttl_seconds", "1800") or "1800"),
    }


def history_server_status(config: Optional[dict[str, str]] = None) -> dict[str, Any]:
    config = config or parse_config()
    url = config.get("history.server_url", "http://127.0.0.1:8790").rstrip("/")
    if not url:
        return {"ok": False, "url": "", "error": "未配置 history.server_url"}
    try:
        with urllib.request.urlopen(url + "/api/health", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        payload["url"] = url
        return payload
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def read_report_json() -> dict[str, Any]:
    config = parse_config()
    path = resolve_runtime_path(config.get("report_json_path", "logs/last_report.json"))
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def data_profile() -> dict[str, Any]:
    config = parse_config()
    history_mode = config.get("history.mode", "local")
    path = resolve_runtime_path(config.get("replay_path", "data/sample_bars.csv"))
    profile: dict[str, Any] = {
        "history_mode": history_mode,
        "history_server": history_server_status(config) if history_mode == "remote" else {},
        "history_contracts": [item.strip() for item in config.get("history.contracts", "").split(",") if item.strip()],
        "history_cache": history_cache_profile(config),
        "path": str(path),
        "exists": path.exists(),
        "row_count": 0,
        "symbols": [],
        "start": "",
        "end": "",
        "bars_per_symbol": {},
        "bad_rows": 0,
        "warnings": [],
        "preview": [],
    }
    if history_mode == "remote":
        status = profile["history_server"]
        profile["path"] = (
            f"{config.get('history.server_url', 'http://127.0.0.1:8790').rstrip('/')}"
            f" / {config.get('history.contracts', '')}"
        )
        profile["exists"] = bool(status.get("ok"))
        profile["warnings"].append("远端模式：回测运行时按合约从历史数据服务器拉取数据。")
        profile["warnings"].append(
            f"本地缓存目录 {profile['history_cache']['path']}，TTL "
            f"{profile['history_cache']['ttl_seconds']} 秒。"
        )
        if not status.get("ok"):
            profile["warnings"].append("历史数据服务器不可用：" + str(status.get("error", "")))
        return profile

    if not path.exists():
        profile["warnings"].append("数据文件不存在")
        return profile

    required = {"timestamp", "symbol", "exchange", "open", "high", "low", "close", "volume"}
    symbols: set[str] = set()
    timestamps: list[str] = []
    bars_per_symbol: dict[str, int] = {}
    closes: list[float] = []
    total_volume = 0.0
    preview: list[dict[str, str]] = []

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = sorted(required - fieldnames)
        if missing:
            profile["warnings"].append("缺少字段: " + ", ".join(missing))

        for row in reader:
            profile["row_count"] += 1
            preview.append(row)
            preview = preview[-8:]
            try:
                timestamp = row.get("timestamp", "").strip()
                symbol = row.get("symbol", "").strip()
                exchange = row.get("exchange", "").strip()
                key = f"{symbol}.{exchange}" if exchange else symbol
                close = float(row.get("close", "nan"))
                volume = float(row.get("volume", "0"))
                if not timestamp or not symbol or close <= 0.0:
                    raise ValueError
                timestamps.append(timestamp)
                symbols.add(key)
                bars_per_symbol[key] = bars_per_symbol.get(key, 0) + 1
                closes.append(close)
                total_volume += volume
            except (TypeError, ValueError):
                profile["bad_rows"] += 1

    if profile["row_count"] == 0:
        profile["warnings"].append("数据文件没有可读取的行情行")
    if profile["bad_rows"] > 0:
        profile["warnings"].append(f"{profile['bad_rows']} 行数据无法通过基础校验")
    if timestamps:
        profile["start"] = min(timestamps)
        profile["end"] = max(timestamps)
    profile["symbols"] = sorted(symbols)
    profile["bars_per_symbol"] = dict(sorted(bars_per_symbol.items()))
    profile["min_close"] = min(closes) if closes else None
    profile["max_close"] = max(closes) if closes else None
    profile["total_volume"] = total_volume
    profile["preview"] = preview
    return profile


def archive_backtest_run(run: dict[str, Any]) -> dict[str, Any]:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    run_id = f"{time.strftime('%Y%m%d-%H%M%S', time.localtime())}-{uuid4().hex[:8]}"
    destination = RUN_DIR / run_id
    destination.mkdir(parents=True, exist_ok=True)

    config = parse_config()
    report = read_report_json()
    metadata = {
        "id": run_id,
        "created_at": now_iso(),
        "ok": bool(run.get("ok")),
        "stage": run.get("stage", ""),
        "config": config,
        "summary": report.get("summary", parse_summary()),
        "data_profile": data_profile(),
    }
    (destination / "run.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (destination / "output.txt").write_text(run.get("output", ""), encoding="utf-8")

    for source, name in [
        (resolve_runtime_path(config.get("report_json_path", "logs/last_report.json")), "report.json"),
        (resolve_runtime_path(config.get("event_log_path", "logs/events.jsonl")), "events.jsonl"),
        (LOG_DIR / "last_run_summary.txt", "summary.txt"),
        (DEFAULT_CONFIG, "config.cfg"),
    ]:
        if source.exists():
            shutil.copyfile(source, destination / name)
    return metadata


def list_runs() -> list[dict[str, Any]]:
    if not RUN_DIR.exists():
        return []
    runs: list[dict[str, Any]] = []
    for path in sorted(RUN_DIR.iterdir(), reverse=True):
        metadata_path = path / "run.json"
        if not metadata_path.exists():
            continue
        try:
            runs.append(json.loads(metadata_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return runs


def safe_run_id(run_id: str) -> str:
    value = run_id.strip()
    if not RUN_ID_RE.fullmatch(value):
        raise ValueError("无效的运行 ID")
    return value


def load_run_archive(run_id: str) -> dict[str, Any]:
    directory = RUN_DIR / safe_run_id(run_id)
    if not directory.exists():
        raise ValueError("找不到运行档案")

    def read_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    events: list[dict[str, Any]] = []
    events_path = directory / "events.jsonl"
    if events_path.exists():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    output = ""
    output_path = directory / "output.txt"
    if output_path.exists():
        output = output_path.read_text(encoding="utf-8")

    return {
        "metadata": read_json(directory / "run.json"),
        "report": read_json(directory / "report.json"),
        "events": events,
        "output": output,
    }


def run_command(args: list[str], timeout: int = 120) -> dict[str, Any]:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    return {
        "returncode": completed.returncode,
        "output": completed.stdout,
    }


def run_backtest() -> dict[str, Any]:
    LOG_DIR.mkdir(exist_ok=True)
    build = run_command(["make", "traderd"], timeout=120)
    if build["returncode"] != 0:
        return {
            "ok": False,
            "stage": "build",
            "output": build["output"],
        }
    run = run_command(["./traderd", "config/default.cfg"], timeout=120)
    LAST_PLATFORM_OUTPUT.write_text(run["output"], encoding="utf-8")
    payload = {
        "ok": run["returncode"] == 0,
        "stage": "run",
        "output": run["output"],
        "summary": parse_summary(),
        "equity_curve": parse_equity_curve(run["output"]),
        "events": read_events(120),
        "report": read_report_json(),
    }
    payload["run"] = archive_backtest_run(payload)
    return payload


def run_pricing_demo() -> dict[str, Any]:
    build = run_command(["make", "option_demo"], timeout=120)
    if build["returncode"] != 0:
        return {"ok": False, "output": build["output"]}
    run = run_command(["./option_demo"], timeout=60)
    return {"ok": run["returncode"] == 0, "output": run["output"]}


def run_checks() -> dict[str, Any]:
    run = run_command(["make", "check"], timeout=180)
    return {"ok": run["returncode"] == 0, "output": run["output"]}


def agent_context() -> str:
    summary = parse_summary()
    events = read_events(40)
    config = parse_config()
    report = read_report_json()
    return json.dumps(
        {
            "config": config,
            "summary": summary,
            "structured_report": report,
            "data_profile": data_profile(),
            "recent_events": events,
        },
        ensure_ascii=False,
    )


def call_agent(
    provider_key: str,
    model: str,
    prompt: str,
    history: Optional[list[dict[str, str]]] = None,
) -> dict[str, Any]:
    provider = PROVIDERS.get(provider_key)
    if provider is None:
        raise ValueError(f"不支持的服务商：{provider_key}")
    if provider.get("transport") == "cli":
        return call_kimi_cli_agent(provider, model, prompt, history or [])

    api_key = get_provider_api_key(provider)
    if not api_key:
        key_label = provider_api_key_label(provider)
        return {
            "ok": False,
            "error": f"缺少 {key_label}，请设置环境变量或写入 config/api_key.config",
        }

    selected_model = model.strip() or provider_default_model(provider)
    endpoint = provider_base_url(provider) + "/chat/completions"
    messages = [
        {
            "role": "system",
            "content": (
                "你是本地 KaTrade 量化研究助手。"
                "请基于提供的运行上下文解释风险、诊断问题、提出下一步工程改进。"
                "回答要简洁，不要编造数据。"
            ),
        },
        {
            "role": "user",
            "content": f"当前运行上下文 JSON:\n{agent_context()}",
        },
        *history_for_agent(history or []),
        {
            "role": "user",
            "content": prompt,
        },
    ]
    payload = {
        "model": selected_model,
        "messages": messages,
        "temperature": 0.2,
    }
    if "max_tokens_env" in provider:
        max_tokens = get_local_setting(provider["max_tokens_env"], provider["default_max_tokens"])
        if max_tokens:
            payload["max_tokens"] = int(max_tokens)
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": provider_user_agent(provider),
    }
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        hint = ""
        if exc.code == 401:
            hint = (
                f"；当前 endpoint={provider_base_url(provider)}。"
                "请检查 API key 是否属于这个平台，必要时在 config/api_key.config 中设置对应 BASE_URL"
            )
        if exc.code == 403 and provider_key == "kimi_coding":
            hint = (
                f"；当前 endpoint={provider_base_url(provider)}。"
                "Kimi Coding Plan 可能限制只能由官方支持的 Coding Agent 调用。"
                "本平台会按真实 User-Agent 标识自己，不会伪装成其他客户端。"
            )
        return {"ok": False, "error": f"服务商 HTTP {exc.code}: {detail}{hint}"}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": f"服务商连接失败：{exc}"}

    content = ""
    choices = body.get("choices") or []
    if choices:
        content = choices[0].get("message", {}).get("content", "")
    return {
        "ok": True,
        "provider": provider["name"],
        "model": selected_model,
        "content": content,
        "raw": body,
    }


def call_kimi_cli_agent(
    provider: dict[str, Any],
    model: str,
    prompt: str,
    history: list[dict[str, str]],
) -> dict[str, Any]:
    cli_path, source = resolve_kimi_cli()
    if cli_path is None:
        return {
            "ok": False,
            "error": "未找到可执行的 Kimi Code CLI。请安装 Kimi Code CLI，或设置 KIMI_CLI_PATH。",
        }

    selected_model = normalize_kimi_cli_model(model)
    max_steps = get_local_setting(provider["max_steps_env"], provider["default_max_steps"])
    KIMI_CLI_WORK_DIR.mkdir(parents=True, exist_ok=True)
    full_prompt = (
        "你是本地 KaTrade 量化研究助手。"
        "请只基于下面提供的运行上下文和对话历史回答。"
        "不要修改文件，不要调用工具，不要编造数据。\n\n"
        f"运行上下文 JSON:\n{agent_context()}\n\n"
        f"对话历史:\n{history_as_text(history_for_agent(history))}\n\n"
        f"本轮问题:\n{prompt}"
    )
    args = [
        str(cli_path),
        "--work-dir",
        str(KIMI_CLI_WORK_DIR),
        "--quiet",
        "--max-steps-per-turn",
        max_steps,
        "-p",
        full_prompt,
    ]
    if selected_model:
        args[4:4] = ["--model", selected_model]
    completed = subprocess.run(
        args,
        cwd=KIMI_CLI_WORK_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=kimi_cli_environment(),
        timeout=180,
        check=False,
    )
    output = completed.stdout.strip()
    content = re.sub(r"\n+To resume this session:.*$", "", output, flags=re.DOTALL).strip()
    return {
        "ok": completed.returncode == 0,
        "provider": provider["name"],
        "model": selected_model or "kimi-cli-default",
        "content": content,
        "source": source,
        "raw": output,
        "error": "" if completed.returncode == 0 else content,
    }


def create_agent_session(provider: str, model: str) -> dict[str, Any]:
    session = default_agent_session(provider or "kimi_coding", model or "")
    with AGENT_LOCK:
        save_agent_session(session)
    return session


def send_agent_message(
    session_id: str,
    provider_key: str,
    model: str,
    prompt: str,
) -> dict[str, Any]:
    content = prompt.strip()
    if not content:
        return {"ok": False, "error": "请输入问题"}

    with AGENT_LOCK:
        if session_id:
            session = load_agent_session(session_id)
        else:
            session = default_agent_session(provider_key or "kimi_coding", model or "")
            save_agent_session(session)

        history = history_for_agent(session.get("messages", []))
        session["provider"] = provider_key or session.get("provider", "kimi_coding")
        session["model"] = model
        session["messages"].append(
            {
                "role": "user",
                "content": content,
                "created_at": now_iso(),
            }
        )
        save_agent_session(session)

    result = call_agent(provider_key, model, content, history)
    assistant_content = result.get("content", "") if result.get("ok") else result.get("error", "Agent 调用失败")

    with AGENT_LOCK:
        session = load_agent_session(str(session["id"]))
        session["messages"].append(
            {
                "role": "assistant",
                "content": assistant_content,
                "created_at": now_iso(),
                "ok": bool(result.get("ok")),
                "provider": result.get("provider", provider_key),
                "model": result.get("model", model),
            }
        )
        save_agent_session(session)

    return {
        "ok": bool(result.get("ok")),
        "session": session,
        "reply": assistant_content,
        "provider": result.get("provider", provider_key),
        "model": result.get("model", model),
        "error": "" if result.get("ok") else assistant_content,
    }


def provider_status(provider: dict[str, Any]) -> dict[str, Any]:
    if provider.get("transport") == "cli":
        cli_path, source = resolve_kimi_cli()
        return {
            "name": provider["name"],
            "default_model": provider_default_model(provider),
            "base_url": str(cli_path) if cli_path else provider["base_url"],
            "env": "KIMI_CLI_PATH",
            "configured": cli_path is not None,
            "source": source,
        }
    return {
        "name": provider["name"],
        "default_model": provider_default_model(provider),
        "base_url": provider_base_url(provider),
        "env": provider_api_key_label(provider),
        "configured": bool(get_provider_api_key(provider)),
        "source": provider_api_key_source(provider),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "KaTradePlatform/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_static(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return
        content_type = "text/plain"
        if path.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        route = urlparse(self.path)
        path = route.path
        if path in {
            "/",
            "/index.html",
            "/dashboard",
            "/runs",
            "/report",
            "/strategies",
            "/data",
            "/events",
            "/config",
            "/agent",
        }:
            self.send_static(STATIC_DIR / "index.html")
            return
        if path == "/styles.css":
            self.send_static(STATIC_DIR / "styles.css")
            return
        if path == "/app.js":
            self.send_static(STATIC_DIR / "app.js")
            return
        if path == "/api/status":
            config = parse_config()
            self.send_json(
                {
                    "config": config,
                    "summary": parse_summary(),
                    "equity_curve": parse_equity_curve(),
                    "events": read_events(80),
                    "report": read_report_json(),
                    "data_profile": data_profile(),
                    "history_server": history_server_status(config)
                    if config.get("history.mode", "local") == "remote"
                    else {},
                    "strategies": STRATEGY_CATALOG,
                    "runs": list_runs(),
                    "providers": {
                        key: provider_status(value)
                        for key, value in PROVIDERS.items()
                    },
                    "binaries": {
                        "traderd": (ROOT / "traderd").exists(),
                        "replay_check": (ROOT / "replay_check").exists(),
                        "option_demo": (ROOT / "option_demo").exists(),
                        "pricing_check": (ROOT / "pricing_check").exists(),
                    },
                }
            )
            return
        if path == "/api/config":
            self.send_json({"config": parse_config()})
            return
        if path == "/api/report":
            self.send_json({"report": read_report_json()})
            return
        if path == "/api/data/profile":
            self.send_json({"profile": data_profile()})
            return
        if path == "/api/strategies":
            self.send_json({"strategies": STRATEGY_CATALOG})
            return
        if path == "/api/runs":
            self.send_json({"runs": list_runs()})
            return
        if path == "/api/run":
            params = parse_qs(route.query)
            run_id = params.get("id", [""])[0]
            self.send_json({"run": load_run_archive(run_id)})
            return
        if path == "/api/agent/sessions":
            with AGENT_LOCK:
                self.send_json({"sessions": list_agent_sessions()})
            return
        if path == "/api/agent/session":
            params = parse_qs(route.query)
            session_id = params.get("id", [""])[0]
            with AGENT_LOCK:
                self.send_json({"session": load_agent_session(session_id)})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        try:
            path = urlparse(self.path).path
            if path == "/api/config":
                body = self.read_json()
                write_config(body.get("config", {}))
                self.send_json({"ok": True, "config": parse_config()})
                return
            if path == "/api/backtest":
                self.send_json(run_backtest())
                return
            if path == "/api/check":
                self.send_json(run_checks())
                return
            if path == "/api/pricing":
                self.send_json(run_pricing_demo())
                return
            if path == "/api/agent":
                body = self.read_json()
                self.send_json(
                    call_agent(
                        str(body.get("provider", "kimi")),
                        str(body.get("model", "")),
                        str(body.get("prompt", "")),
                    )
                )
                return
            if path == "/api/agent/session":
                body = self.read_json()
                self.send_json(
                    {
                        "ok": True,
                        "session": create_agent_session(
                            str(body.get("provider", "kimi_coding")),
                            str(body.get("model", "")),
                        ),
                    }
                )
                return
            if path == "/api/agent/message":
                body = self.read_json()
                self.send_json(
                    send_agent_message(
                        str(body.get("session_id", "")),
                        str(body.get("provider", "kimi_coding")),
                        str(body.get("model", "")),
                        str(body.get("prompt", "")),
                    )
                )
                return
            self.send_error(404)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)


def main() -> int:
    host = os.environ.get("KATRADE_HOST", "127.0.0.1")
    port = int(os.environ.get("KATRADE_PORT", "8787"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"KaTrade platform listening on http://{host}:{port}")
    print(f"Project root: {ROOT}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
