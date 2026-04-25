#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static"
LOG_DIR = ROOT / "logs"
DEFAULT_CONFIG = ROOT / "config" / "default.cfg"
API_KEY_CONFIG = ROOT / "config" / "api_key.config"
LAST_PLATFORM_OUTPUT = LOG_DIR / "last_platform_run.txt"

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
        "base_url": "https://api.kimi.com/coding/v1",
        "base_url_env": "KIMI_CODING_BASE_URL",
        "env": "KIMI_CODING_API_KEY",
        "env_aliases": ["MOONSHOT_API_KEY"],
        "default_model": "kimi-for-coding",
        "model_env": "KIMI_CODING_MODEL",
        "max_tokens_env": "KIMI_CODING_MAX_TOKENS",
        "default_max_tokens": "32768",
        "user_agent_env": "KIMI_CODING_USER_AGENT",
        "default_user_agent": "KaTradeLocalQuantAgent/0.1",
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
    return get_local_setting(provider["base_url_env"], provider["base_url"]).rstrip("/")


def provider_default_model(provider: dict[str, Any]) -> str:
    return get_local_setting(provider["model_env"], provider["default_model"])


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


def write_config(values: dict[str, Any], path: Path = DEFAULT_CONFIG) -> None:
    current = parse_config(path)
    for key, value in values.items():
        if key not in CONFIG_KEYS:
            raise ValueError(f"unsupported config key: {key}")
        current[key] = str(value)

    ordered = [
        "replay_path",
        "event_log_path",
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
    return {
        "ok": run["returncode"] == 0,
        "stage": "run",
        "output": run["output"],
        "summary": parse_summary(),
        "equity_curve": parse_equity_curve(run["output"]),
        "events": read_events(120),
    }


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
    return json.dumps(
        {
            "config": config,
            "summary": summary,
            "recent_events": events,
        },
        ensure_ascii=False,
    )


def call_agent(provider_key: str, model: str, prompt: str) -> dict[str, Any]:
    provider = PROVIDERS.get(provider_key)
    if provider is None:
        raise ValueError(f"不支持的服务商：{provider_key}")

    api_key = get_provider_api_key(provider)
    if not api_key:
        key_label = provider_api_key_label(provider)
        return {
            "ok": False,
            "error": f"缺少 {key_label}，请设置环境变量或写入 config/api_key.config",
        }

    selected_model = model.strip() or provider_default_model(provider)
    endpoint = provider_base_url(provider) + "/chat/completions"
    payload = {
        "model": selected_model,
        "messages": [
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
                "content": f"运行上下文 JSON:\n{agent_context()}\n\n问题:\n{prompt}",
            },
        ],
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
        if self.path in {"/", "/index.html"}:
            self.send_static(STATIC_DIR / "index.html")
            return
        if self.path == "/styles.css":
            self.send_static(STATIC_DIR / "styles.css")
            return
        if self.path == "/app.js":
            self.send_static(STATIC_DIR / "app.js")
            return
        if self.path == "/api/status":
            self.send_json(
                {
                    "config": parse_config(),
                    "summary": parse_summary(),
                    "equity_curve": parse_equity_curve(),
                    "events": read_events(80),
                    "providers": {
                        key: {
                            "name": value["name"],
                            "default_model": provider_default_model(value),
                            "base_url": provider_base_url(value),
                            "env": provider_api_key_label(value),
                            "configured": bool(get_provider_api_key(value)),
                            "source": provider_api_key_source(value),
                        }
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
        if self.path == "/api/config":
            self.send_json({"config": parse_config()})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        try:
            if self.path == "/api/config":
                body = self.read_json()
                write_config(body.get("config", {}))
                self.send_json({"ok": True, "config": parse_config()})
                return
            if self.path == "/api/backtest":
                self.send_json(run_backtest())
                return
            if self.path == "/api/check":
                self.send_json(run_checks())
                return
            if self.path == "/api/pricing":
                self.send_json(run_pricing_demo())
                return
            if self.path == "/api/agent":
                body = self.read_json()
                self.send_json(
                    call_agent(
                        str(body.get("provider", "kimi")),
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
