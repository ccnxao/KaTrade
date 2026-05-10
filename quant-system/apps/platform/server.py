#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import base64
import copy
import csv
import hashlib
import hmac
import math
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request
from bisect import bisect_left, bisect_right
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, quote, urlencode, urlparse
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static"
LOG_DIR = ROOT / "logs"
DEFAULT_CONFIG = ROOT / "config" / "default.cfg"
API_KEY_CONFIG = ROOT / "config" / "api_key.config"
RISK_STATE_PATH = LOG_DIR / "risk_state.json"
OPS_STATE_PATH = LOG_DIR / "ops_state.json"
OPS_ALERT_ACK_PATH = LOG_DIR / "ops_alert_ack.json"
OPS_INCIDENT_DIR = LOG_DIR / "ops_incidents"
OPS_INCIDENT_PATH = OPS_INCIDENT_DIR / "incidents.jsonl"
OPS_INCIDENT_LOCK = threading.RLock()
LAST_PLATFORM_OUTPUT = LOG_DIR / "last_platform_run.txt"
BACKENDD_BIN = ROOT / "backendd"
BACKENDD_CMAKE_BIN = ROOT / "build" / "backendd"
BACKENDD_HTTP_BASE = os.environ.get("KATRADE_BACKENDD_URL", "http://127.0.0.1:8791").rstrip("/")
OKX_POLICY_BIN = ROOT / "okx_policy"
OKX_POLICY_CMAKE_BIN = ROOT / "build" / "okx_policy"
OPS_CHECK_BIN = ROOT / "ops_check"
OPS_CHECK_CMAKE_BIN = ROOT / "build" / "ops_check"
TRADING_UNIT_POLICY_BIN = ROOT / "trading_unit_policy"
TRADING_UNIT_POLICY_CMAKE_BIN = ROOT / "build" / "trading_unit_policy"
REALTIME_ENGINE_BIN = ROOT / "realtime_engine"
REALTIME_ENGINE_CMAKE_BIN = ROOT / "build" / "realtime_engine"
RUN_DIR = LOG_DIR / "runs"
EXPERIMENT_DIR = LOG_DIR / "experiments"
SWEEP_DIR = LOG_DIR / "sweeps"
WALK_FORWARD_DIR = LOG_DIR / "walk_forward"
STRATEGY_WASH_DIR = LOG_DIR / "strategy_wash"
REALTIME_ENGINE_DIR = LOG_DIR / "realtime_engine"
REALTIME_ENGINE_STATUS_PATH = REALTIME_ENGINE_DIR / "status.json"
REALTIME_ENGINE_EVENTS_PATH = REALTIME_ENGINE_DIR / "events.jsonl"
REALTIME_ENGINE_WATCH_LOG_PATH = REALTIME_ENGINE_DIR / "watch.log"
MARKET_QUALITY_DIR = LOG_DIR / "market_quality"
MARKET_QUALITY_LATEST_PATH = MARKET_QUALITY_DIR / "latest.json"
PAPER_DIR = LOG_DIR / "paper_trading"
PAPER_RUN_DIR = PAPER_DIR / "runs"
PAPER_STATE_PATH = PAPER_DIR / "state.json"
PAPER_MARKERS_PATH = PAPER_DIR / "markers.json"
PAPER_LATEST_REPORT_PATH = PAPER_DIR / "latest_report.json"
PAPER_LATEST_OUTPUT_PATH = PAPER_DIR / "latest_output.txt"
PAPER_OKX_BASELINE_PATH = PAPER_DIR / "okx_baseline.json"
TRADING_UNIT_ALLOCATION_STATE_PATH = PAPER_DIR / "trading_unit_state.json"
CONFIG_BACKUP_DIR = LOG_DIR / "config_backups"
BROKER_LOG_DIR = LOG_DIR / "broker"
OKX_AUDIT_PATH = BROKER_LOG_DIR / "okx_audit.jsonl"
KIMI_CLI_EXTRACT_DIR = Path("/tmp/katrade-kimi-cli")
KIMI_CLI_WORK_DIR = Path("/tmp/katrade-kimi-agent-work")
AGENT_SESSION_DIR = LOG_DIR / "agent_sessions"
TRADING_UNIT_AGENT_STATE_PATH = AGENT_SESSION_DIR / "trading_unit_leverage.json"
TRADING_UNIT_AGENT_BRIEF_PATH = AGENT_SESSION_DIR / "trading_unit_brief.json"
GOLD_1M_DEFAULT_PATH = ROOT / "data" / "gold_1m.csv"
AGENT_MAX_HISTORY = 12
AGENT_LOCK = threading.Lock()
PAPER_LOCK = threading.RLock()
PAPER_STOP_EVENT = threading.Event()
PAPER_THREAD: Optional[threading.Thread] = None
REALTIME_ENGINE_PROCESS_LOCK = threading.RLock()
REALTIME_ENGINE_PROCESS: Optional[subprocess.Popen[Any]] = None
REALTIME_ENGINE_PROCESS_META: dict[str, Any] = {}
BACKEND_CORE_CACHE_LOCK = threading.RLock()
BACKEND_CORE_CACHE: dict[str, Any] = {"ts": 0.0, "payload": {}}
SESSION_ID_RE = re.compile(r"^[a-f0-9-]{32,36}$")
RUN_ID_RE = re.compile(r"^\d{8}-\d{6}(?:-[a-f0-9]{8})?$")
EXPERIMENT_ID_RE = re.compile(r"^exp-\d{8}-\d{6}(?:-[a-f0-9]{8})?$")
WALK_FORWARD_ID_RE = re.compile(r"^wf-\d{8}-\d{6}(?:-[a-f0-9]{8})?$")
OKX_BASE_URL = "https://www.okx.com"
OKX_BLOCKED_BASE_URLS = {"https://aws.okx.com"}
OKX_PUBLIC_WS_URL = "wss://ws.okx.com:8443/ws/v5/public"
OKX_PUBLIC_WS_SIMULATED_URL = "wss://wspap.okx.com:8443/ws/v5/public"
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
PRIMARY_BROKER_NAME = "okx"
OKX_EXECUTION_INST_TYPE = "SPOT"
OKX_EXECUTION_TD_MODE = "cash"
OKX_DERIVATIVE_INST_TYPES = {"SWAP", "FUTURES"}
OKX_DERIVATIVE_TD_MODES = {"isolated", "cross"}
OKX_ALLOWED_ORDER_TYPES = {"limit", "post_only"}
OKX_TERMINAL_ORDER_STATES = {"filled", "canceled", "cancelled", "rejected", "mmp_canceled", "expired"}
OKX_MAX_BACKTEST_INSTRUMENTS = 8
OKX_MAX_RUNTIME_INSTRUMENTS = 50
PAPER_OKX_AUTO_CONFIRM = "AUTO_OKX_SIMULATED_ONLY"
PAPER_LOCAL_DEBUG_CONFIRM = "LOCAL_PAPER_DEBUG_ONLY"
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
MARKET_STREAM_DIR = LOG_DIR / "market_stream"
MARKET_STREAM_JOURNAL_PATH = MARKET_STREAM_DIR / "okx_public.jsonl"
MARKET_STREAM_LOCK = threading.RLock()
MARKET_STREAM_STOP_EVENT = threading.Event()
MARKET_STREAM_THREAD: Optional[threading.Thread] = None
MARKET_STREAM_ALLOWED_CHANNELS = {"trades", "tickers", "books5"}
OKX_SUBMIT_GATE_LOCK = threading.RLock()
OKX_SUBMIT_GATE_CACHE: dict[str, Any] = {"key": "", "checked_at": 0.0, "payload": {}}
OKX_ACCOUNT_CONFIG_CACHE_LOCK = threading.RLock()
OKX_ACCOUNT_CONFIG_CACHE: dict[str, Any] = {"checked_at": 0.0, "payload": {}}
OKX_REFERENCE_DIR = LOG_DIR / "okx_reference"
OKX_INSTRUMENT_CACHE_LOCK = threading.RLock()
OKX_TICKER_CACHE_LOCK = threading.RLock()
OKX_TICKER_CACHE: dict[str, dict[str, Any]] = {}
EVENT_JOURNAL_DIR = LOG_DIR / "event_journal"
EVENT_JOURNAL_PATH = EVENT_JOURNAL_DIR / "events.jsonl"
EVENT_JOURNAL_LOCK = threading.RLock()
EVENT_JOURNAL_LAST_EMIT: dict[str, float] = {}
ORDER_JOURNAL_DIR = LOG_DIR / "order_journal"
ORDER_JOURNAL_PATH = ORDER_JOURNAL_DIR / "orders.jsonl"
ORDER_JOURNAL_LOCK = threading.RLock()
EXECUTION_TRACE_DIR = LOG_DIR / "execution_trace"
EXECUTION_TRACE_PATH = EXECUTION_TRACE_DIR / "decisions.jsonl"
EXECUTION_TRACE_LOCK = threading.RLock()
EXECUTION_LEDGER_DIR = LOG_DIR / "execution_ledger"
EXECUTION_LEDGER_PATH = EXECUTION_LEDGER_DIR / "events.jsonl"
EXECUTION_LEDGER_LOCK = threading.RLock()
RECONCILIATION_DIR = LOG_DIR / "reconciliation"
RECONCILIATION_PATH = RECONCILIATION_DIR / "okx_reconcile.jsonl"
RECONCILIATION_LOCK = threading.RLock()
MARKET_STREAM_STATE: dict[str, Any] = {
    "status": "stopped",
    "running": False,
    "url": "",
    "environment": "",
    "started_at": "",
    "stopped_at": "",
    "last_message_at": "",
    "last_trade_at": "",
    "last_ticker_at": "",
    "last_books_at": "",
    "last_error": "",
    "reconnects": 0,
    "messages": 0,
    "events": 0,
    "subscriptions": [],
    "channels": [],
    "instruments": [],
    "recent_trades": {},
    "tickers": {},
    "books5": {},
}
DAY_MS = 24 * 60 * 60 * 1000
TRUTHY_VALUES = {"1", "true", "yes", "enabled", "on"}
FALSY_VALUES = {"0", "false", "no", "disabled", "off"}
BROKER_FILL_EPS = 1e-12

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
DEFAULT_AGENT_PROVIDER = "kimi"
DEFAULT_AGENT_MODEL = ""

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
    "history.bar",
    "history.start",
    "history.end",
    "history.max_pages",
    "strategy.donchian.lookback",
    "strategy.ma_cross.fast_window",
    "strategy.ma_cross.slow_window",
    "strategy.macd.fast_alpha",
    "strategy.macd.slow_alpha",
    "strategy.macd.signal_alpha",
    "strategy.ema_slope.alpha",
    "strategy.ema_slope.min_slope",
    "strategy.keltner.alpha",
    "strategy.keltner.multiplier",
    "strategy.volume_spike.alpha",
    "strategy.volume_spike.multiplier",
    "strategy.micro_scalper.min_return",
    "strategy.micro_scalper.min_body_ratio",
    "strategy.spread_capture.alpha",
    "strategy.spread_capture.threshold",
    "strategy.order_flow.volume_alpha",
    "strategy.order_flow.imbalance_threshold",
    "strategy.inventory_skew.neutral_band",
    "strategy.bollinger.window",
    "strategy.bollinger.band_width",
    "strategy.rsi.window",
    "strategy.rsi.oversold",
    "strategy.rsi.overbought",
    "strategy.zscore.window",
    "strategy.zscore.threshold",
    "print_cycles",
    "print_event_stream",
    "metrics.drawdown_stride",
    "regime.detector",
    "regime.hmm_states",
    "regime.oem_dim",
    "regime.rule.crisis_vol",
    "regime.rule.crisis_corr",
    "regime.rule.trending_adx",
    "regime.rule.trending_ret",
    "regime.rule.trending_vol_cap",
    "regime.rule.mean_revert_adx",
    "regime.rule.mean_revert_vol_cap",
    "initial_cash",
    "optimizer.max_single_weight",
    "optimizer.max_gross",
    "risk.max_single_weight",
    "risk.max_gross",
    "risk.max_order_notional",
    "risk.kill_switch",
    "risk.drawdown_limit",
    "risk.vol_threshold",
    "risk.vol_reduction",
    "risk.stress_tolerance",
    "risk.budget_scale",
    "risk.turnover_limit",
    "okx.base_url",
    "okx.simulated",
    "execution.min_rebalance_delta",
    "execution.max_participation_rate",
    "execution.maker_offset_bps",
    "execution.maker_fee_bps",
    "execution.max_expected_cost_bps",
    "execution.pending_order_ttl_bars",
    "execution.derivatives.enabled",
    "execution.derivatives.inst_type",
    "execution.derivatives.margin_mode",
    "execution.derivatives.position_mode",
    "execution.derivatives.max_exchange_leverage",
    "execution.derivatives.max_effective_leverage",
    "execution.derivatives.max_unit_effective_leverage",
    "execution.trade_unit.base_notional_usdt",
    "execution.trade_unit.agent_leverage_enabled",
    "execution.trade_unit.agent_max_step",
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
        "id": "ema_slope_trend",
        "display_name": "EMA 斜率趋势",
        "style": "trend",
        "horizon": "日频/分钟",
        "description": "用递推 EMA 斜率识别短周期趋势方向。",
        "default_enabled": True,
        "params": [
            {"key": "strategy.ema_slope.alpha", "label": "EMA alpha", "default": "0.35", "kind": "float"},
            {"key": "strategy.ema_slope.min_slope", "label": "最小斜率", "default": "0.001", "kind": "float"},
        ],
    },
    {
        "id": "keltner_breakout",
        "display_name": "Keltner 通道突破",
        "style": "trend",
        "horizon": "日频/分钟",
        "description": "用上一周期 EMA 与 ATR 通道判断突破。",
        "default_enabled": True,
        "params": [
            {"key": "strategy.keltner.alpha", "label": "平滑 alpha", "default": "0.25", "kind": "float"},
            {"key": "strategy.keltner.multiplier", "label": "ATR 倍数", "default": "1.5", "kind": "float"},
        ],
    },
    {
        "id": "volume_spike_momentum",
        "display_name": "量能放大动量",
        "style": "trend",
        "horizon": "分钟",
        "description": "成交量显著高于递推均量时跟随同向价格变动。",
        "default_enabled": True,
        "params": [
            {"key": "strategy.volume_spike.alpha", "label": "均量 alpha", "default": "0.20", "kind": "float"},
            {"key": "strategy.volume_spike.multiplier", "label": "放量倍数", "default": "1.8", "kind": "float"},
        ],
    },
    {
        "id": "micro_scalper",
        "display_name": "微结构剥头皮",
        "style": "hybrid",
        "horizon": "分钟/高频",
        "description": "用分钟 bar 的实体、区间和相邻收盘收益代理短周期冲击方向。",
        "default_enabled": False,
        "params": [
            {"key": "strategy.micro_scalper.min_return", "label": "最小收益", "default": "0.0004", "kind": "float"},
            {"key": "strategy.micro_scalper.min_body_ratio", "label": "最小实体占比", "default": "0.35", "kind": "float"},
        ],
    },
    {
        "id": "spread_capture_maker",
        "display_name": "价差捕获做市",
        "style": "hybrid",
        "horizon": "分钟/做市",
        "description": "用 fair price EMA 和 bar 区间代理中轴与价差，价格偏离时做反向信号。",
        "default_enabled": False,
        "params": [
            {"key": "strategy.spread_capture.alpha", "label": "中轴 alpha", "default": "0.25", "kind": "float"},
            {"key": "strategy.spread_capture.threshold", "label": "偏离阈值", "default": "0.55", "kind": "float"},
        ],
    },
    {
        "id": "order_flow_imbalance",
        "display_name": "订单流失衡",
        "style": "hybrid",
        "horizon": "分钟/高频",
        "description": "用收盘位置和成交量放大代理主动买卖压力。",
        "default_enabled": False,
        "params": [
            {"key": "strategy.order_flow.volume_alpha", "label": "均量 alpha", "default": "0.20", "kind": "float"},
            {"key": "strategy.order_flow.imbalance_threshold", "label": "失衡阈值", "default": "0.45", "kind": "float"},
        ],
    },
    {
        "id": "inventory_skew_maker",
        "display_name": "库存倾斜做市",
        "style": "hybrid",
        "horizon": "分钟/做市",
        "description": "根据当前持仓权重输出反向信号，模拟做市商控制库存回到中性。",
        "default_enabled": False,
        "params": [
            {"key": "strategy.inventory_skew.neutral_band", "label": "中性库存带", "default": "0.04", "kind": "float"},
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
        "id": "zscore_reversion",
        "display_name": "Z-score 反转",
        "style": "mean_reversion",
        "horizon": "日频/分钟",
        "description": "价格偏离滚动均值超过阈值时做轻量反向信号。",
        "default_enabled": True,
        "params": [
            {"key": "strategy.zscore.window", "label": "窗口", "default": "8", "kind": "int"},
            {"key": "strategy.zscore.threshold", "label": "阈值", "default": "1.25", "kind": "float"},
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

TRADING_UNIT_DEFINITIONS = [
    {
        "id": "unit_trend",
        "display_name": "趋势交易单元",
        "role": "directional",
        "strategy_ids": [
            "momentum",
            "donchian_breakout",
            "ma_cross",
            "macd_trend",
            "ema_slope_trend",
            "keltner_breakout",
            "volume_spike_momentum",
        ],
    },
    {
        "id": "unit_reversion",
        "display_name": "均值回归交易单元",
        "role": "directional",
        "strategy_ids": [
            "mean_reversion",
            "bollinger_reversion",
            "rsi_reversion",
            "zscore_reversion",
            "range_fade",
        ],
    },
    {
        "id": "unit_maker",
        "display_name": "做市/高频交易单元",
        "role": "maker",
        "strategy_ids": [
            "micro_scalper",
            "spread_capture_maker",
            "order_flow_imbalance",
            "inventory_skew_maker",
        ],
    },
]


def strategy_catalog_index() -> dict[str, dict[str, Any]]:
    return {str(item.get("id", "")): item for item in STRATEGY_CATALOG}


def trading_unit_for_strategy(strategy_id: Any) -> dict[str, Any]:
    """Return the trading unit that owns a strategy id, if configured."""
    strategy = str(strategy_id or "").strip()
    if not strategy:
        return {}
    for unit in TRADING_UNIT_DEFINITIONS:
        if strategy in {str(item) for item in unit.get("strategy_ids", []) or []}:
            return unit
    return {}


def primary_strategy_from_attribution(attribution: Any) -> str:
    """Pick the largest contributing strategy from a strategy_attribution list."""
    if not isinstance(attribution, list):
        return ""
    best_id = ""
    best_weight = -1.0
    for row in attribution:
        if not isinstance(row, dict):
            continue
        strategy_id = str(row.get("strategy_id", "")).strip()
        if not strategy_id:
            continue
        weight = max(
            float_from_any(row.get("share")),
            abs(float_from_any(row.get("weighted_score"))),
            abs(float_from_any(row.get("net_score"))),
        )
        if weight > best_weight:
            best_id = strategy_id
            best_weight = weight
    return best_id


def source_order_strategy_id(source: dict[str, Any], fallback: Optional[dict[str, Any]] = None) -> str:
    """Resolve the strategy responsible for an order/fill without using generic order labels."""
    source = source if isinstance(source, dict) else {}
    fallback = fallback if isinstance(fallback, dict) else {}
    catalog = strategy_catalog_index()
    for value in (
        source.get("strategy_id"),
        source.get("_strategy_id"),
        fallback.get("strategy_id"),
        fallback.get("_strategy_id"),
    ):
        strategy = str(value or "").strip()
        if strategy and (strategy in catalog or strategy not in {"realtime-maker-rebalance", "paper-tick-rebalance"}):
            return strategy
    strategy_ids = source.get("strategy_ids") if isinstance(source.get("strategy_ids"), list) else fallback.get("strategy_ids")
    if isinstance(strategy_ids, list):
        for item in strategy_ids:
            strategy = str(item or "").strip()
            if strategy:
                return strategy
    strategy = primary_strategy_from_attribution(source.get("strategy_attribution"))
    if strategy:
        return strategy
    return primary_strategy_from_attribution(fallback.get("strategy_attribution"))


def source_order_attribution_context(source: dict[str, Any], fallback: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Normalize strategy/agent/trading-unit identity for order and fill records."""
    source = source if isinstance(source, dict) else {}
    fallback = fallback if isinstance(fallback, dict) else {}
    strategy_id = source_order_strategy_id(source, fallback)
    unit = trading_unit_for_strategy(strategy_id)
    trading_unit_id = str(
        source.get("trading_unit_id")
        or source.get("_trading_unit_id")
        or fallback.get("trading_unit_id")
        or fallback.get("_trading_unit_id")
        or unit.get("id", "")
    ).strip()
    agent_id = str(source.get("agent_id") or fallback.get("agent_id") or strategy_id or trading_unit_id or "").strip()
    return {
        "strategy_id": strategy_id,
        "agent_id": agent_id,
        "trading_unit_id": trading_unit_id,
        "trading_unit_name": str(unit.get("display_name", "")),
    }


def strategy_parameter_options() -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for strategy in STRATEGY_CATALOG:
        for param in strategy.get("params", []):
            options.append(
                {
                    "key": str(param.get("key", "")),
                    "label": f"{strategy.get('display_name', strategy.get('id', '策略'))} / {param.get('label', param.get('key', '参数'))}",
                    "kind": str(param.get("kind", "text")),
                    "default": str(param.get("default", "")),
                    "strategy_id": str(strategy.get("id", "")),
                }
            )
    return options


def strategy_parameter_keys() -> set[str]:
    return {item["key"] for item in strategy_parameter_options() if item.get("key")}


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


def write_key_value_file_updates(path: Path, updates: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output.append(line)
            continue
        key, _ = stripped.split("=", 1)
        key = key.strip()
        if key in updates:
            output.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            output.append(line)
    missing = [key for key in updates if key not in seen]
    if missing and output and output[-1].strip():
        output.append("")
    for key in missing:
        output.append(f"{key}={updates[key]}")
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def get_api_key(env_name: str) -> str:
    return get_local_setting(env_name, "")


def get_local_setting(name: str, default: str) -> str:
    env_value = os.environ.get(name, "").strip()
    if env_value:
        return env_value
    return parse_key_value_file(API_KEY_CONFIG).get(name, default).strip() or default


def get_first_local_setting(names: list[str], default: str = "") -> str:
    for name in names:
        value = get_local_setting(name, "")
        if value:
            return value
    return default


def parse_bool_setting(value: str, default: bool = False) -> bool:
    normalized = value.strip().lower()
    if normalized in TRUTHY_VALUES:
        return True
    if normalized in FALSY_VALUES:
        return False
    return default


def bool_setting_from_any(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return parse_bool_setting(str(value), default)


def mask_value(value: str, visible: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= visible:
        return "*" * len(value)
    return f"{'*' * (len(value) - visible)}{value[-visible:]}"


def scrub_secret_fields(value: Any) -> Any:
    if isinstance(value, dict):
        scrubbed: dict[str, Any] = {}
        for key, item in value.items():
            lower = str(key).lower()
            if any(token in lower for token in ["secret", "passphrase", "api_key", "apikey", "access-key"]):
                scrubbed[key] = mask_value(str(item))
            else:
                scrubbed[key] = scrub_secret_fields(item)
        return scrubbed
    if isinstance(value, list):
        return [scrub_secret_fields(item) for item in value]
    return value


def compact_event_value(value: Any, depth: int = 0) -> Any:
    """Keep the unified event journal small and safe to render in the UI."""
    value = scrub_secret_fields(value)
    if depth >= 4:
        if isinstance(value, (dict, list)):
            return "...truncated..."
        return value
    if isinstance(value, dict):
        compacted: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in {"ticks", "trades", "orders", "reports", "signals"} and isinstance(item, list):
                compacted[key] = [compact_event_value(row, depth + 1) for row in item[:8]]
                if len(item) > 8:
                    compacted[f"{key}_truncated"] = len(item) - 8
            else:
                compacted[key] = compact_event_value(item, depth + 1)
        return compacted
    if isinstance(value, list):
        rows = [compact_event_value(item, depth + 1) for item in value[:12]]
        if len(value) > 12:
            rows.append({"truncated": len(value) - 12})
        return rows
    if isinstance(value, str) and len(value) > 1000:
        return value[:1000] + "...truncated..."
    return value


def append_platform_event(
    event_type: str,
    source: str,
    payload: dict[str, Any],
    *,
    severity: str = "info",
    message: str = "",
) -> dict[str, Any]:
    """Append a compact event to the local platform journal.

    This is the bridge between realtime components.  It intentionally stores
    searchable summaries instead of full payloads; raw market messages and OKX
    audits keep their own dedicated journals.
    """
    EVENT_JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    now_ms = int(time.time() * 1000)
    compact_payload = compact_event_value(payload)
    event = {
        "id": f"evt-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}-{uuid4().hex[:8]}",
        "ts": now_iso(),
        "ts_ms": now_ms,
        "type": event_type,
        "source": source,
        "severity": severity,
        "message": message,
        **compact_payload,
    }
    with EVENT_JOURNAL_LOCK:
        with EVENT_JOURNAL_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    return event


def append_platform_event_throttled(
    event_type: str,
    source: str,
    payload: dict[str, Any],
    *,
    throttle_key: str,
    min_interval_seconds: float,
    severity: str = "info",
    message: str = "",
) -> Optional[dict[str, Any]]:
    now = time.monotonic()
    with EVENT_JOURNAL_LOCK:
        last = EVENT_JOURNAL_LAST_EMIT.get(throttle_key, 0.0)
        if now - last < min_interval_seconds:
            return None
        EVENT_JOURNAL_LAST_EMIT[throttle_key] = now
    return append_platform_event(event_type, source, payload, severity=severity, message=message)


def read_platform_events(limit: int = 200, event_type: str = "", source: str = "") -> list[dict[str, Any]]:
    if not EVENT_JOURNAL_PATH.exists():
        return []
    limit = max(0, min(int(limit), 5000))
    if limit <= 0:
        return []
    with EVENT_JOURNAL_LOCK:
        with EVENT_JOURNAL_PATH.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 2_000_000))
            text = handle.read().decode("utf-8", "ignore")
    rows: list[dict[str, Any]] = []
    for line in text.splitlines()[-limit * 5:]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event_type and str(row.get("type", "")) != event_type:
            continue
        if source and str(row.get("source", "")) != source:
            continue
        rows.append(row)
    return rows[-limit:][::-1]


def platform_events_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    limit = bounded_int(params.get("limit", ["200"])[0], 200, 1, 1000)
    event_type = params.get("type", [""])[0].strip()
    source = params.get("source", [""])[0].strip()
    events = read_platform_events(limit, event_type=event_type, source=source)
    counts: dict[str, int] = {}
    sources: dict[str, int] = {}
    for event in events:
        counts[str(event.get("type", "unknown"))] = counts.get(str(event.get("type", "unknown")), 0) + 1
        sources[str(event.get("source", "unknown"))] = sources.get(str(event.get("source", "unknown")), 0) + 1
    return {
        "ok": True,
        "generated_at": now_iso(),
        "journal_path": str(EVENT_JOURNAL_PATH),
        "events": events,
        "summary": {
            "count": len(events),
            "types": counts,
            "sources": sources,
            "latest_ts": events[0].get("ts", "") if events else "",
        },
    }


def normalize_order_state(value: str) -> str:
    text = str(value or "").strip().lower()
    names = {
        "pending": "pending",
        "submitted": "pending",
        "pending_tick_maker": "pending",
        "pending_maker": "pending",
        "partiallyfilled": "partially_filled",
        "partially_filled": "partially_filled",
        "filled": "filled",
        "expired": "expired",
        "expired_tick_maker": "expired",
        "expired_maker": "expired",
        "rejected": "rejected",
        "cancelled": "cancelled",
        "canceled": "cancelled",
    }
    return names.get(text, text or "unknown")


def order_event_key(session_id: str, order_id: str) -> str:
    return f"{session_id or 'unknown'}:{order_id or 'unknown'}"


def append_order_journal_event(event_type: str, row: dict[str, Any]) -> dict[str, Any]:
    ORDER_JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    order_id = str(row.get("order_id", "")).strip()
    session_id = str(row.get("paper_session_id") or row.get("session_id") or row.get("settings_hash") or "unknown").strip()
    event = {
        "id": f"ordevt-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}-{uuid4().hex[:8]}",
        "ts": now_iso(),
        "ts_ms": int(time.time() * 1000),
        "type": event_type,
        "source": row.get("source", "paper_broker"),
        "paper_session_id": session_id,
        "order_key": order_event_key(session_id, order_id),
        **compact_event_value(row),
    }
    with ORDER_JOURNAL_LOCK:
        with ORDER_JOURNAL_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    return event


def split_paper_source_order_id(source_order_id: Any) -> tuple[str, str]:
    text = str(source_order_id or "").strip()
    if ":" not in text:
        return "", ""
    session_id, order_id = text.split(":", 1)
    return session_id.strip(), order_id.strip()


def broker_order_state_to_paper_state(state: Any) -> str:
    text = str(state or "").lower().strip()
    if text in {"live", "pending", "submitted"}:
        return "pending"
    if text in {"partially_filled", "partiallyfilled"}:
        return "partially_filled"
    if text in {"canceled", "cancelled", "mmp_canceled"}:
        return "cancelled"
    if text in {"filled", "rejected", "expired"}:
        return text
    return normalize_order_state(text)


def append_broker_order_journal_sync(
    source_order_id: Any,
    identity: dict[str, Any],
    detail: dict[str, Any],
    *,
    order: Optional[dict[str, Any]] = None,
    audit_id: str = "",
    sync_status: str = "synced",
    reason: str = "",
) -> dict[str, Any]:
    """Write OKX simulated order lifecycle into the paper order state machine.

    OKX 模拟盘订单是交易所侧的真实状态源，但 UI 的资金曲线、订单表和平仓盈亏
    都依赖本地 paper order journal。这个同步函数把 OKX 的 ordId/clOrdId/state
    重新写成本地 order.broker_sync 事件，使本地虚拟盘状态机不会停留在 submitted。
    source_order_id 使用 paper_session_id:order_id，保证能回写到同一笔策略委托。
    """
    session_id, order_id = split_paper_source_order_id(source_order_id)
    if not session_id or not order_id:
        return {}
    order = order if isinstance(order, dict) else {}
    detail = detail if isinstance(detail, dict) else {}
    identity = identity if isinstance(identity, dict) else {}
    inst_id = str(detail.get("inst_id") or identity.get("instId") or order.get("instId") or "").upper().strip()
    state = str(detail.get("state") or sync_status or "").lower().strip()
    paper_state = broker_order_state_to_paper_state(state)
    broker_filled_qty = float_from_any(detail.get("acc_fill_sz"))
    broker_contract_value = okx_contract_value_from_sources(inst_id, order, detail)
    broker_filled_base_qty, broker_fill_domain = okx_normalized_broker_fill_qty(
        inst_id,
        broker_filled_qty,
        broker_contract_value,
    )
    broker_order_qty = float_from_any(detail.get("sz"))
    broker_order_base_qty = okx_normalized_broker_order_qty(
        inst_id,
        broker_order_qty,
        broker_contract_value,
    )
    attribution_context = source_order_attribution_context(order)
    sync_payload = {
        "source": "okx_simulated",
        "source_order_id": str(source_order_id or ""),
        "paper_session_id": session_id,
        "order_id": order_id,
        "inst_id": inst_id,
        **attribution_context,
        "broker_inst_id": inst_id,
        "side": detail.get("side") or order.get("side", ""),
        "order_type": detail.get("ord_type") or order.get("ordType", ""),
        "limit_price": float_from_any(detail.get("px"), float_from_any(order.get("px"))),
        "state": paper_state,
        "broker_status": f"OKX:{state or sync_status}",
        "broker_state": state,
        "broker_order_id": detail.get("ord_id") or identity.get("ordId", ""),
        "broker_cl_ord_id": detail.get("cl_ord_id") or identity.get("clOrdId", ""),
        "broker_px": detail.get("px", ""),
        "broker_sz": detail.get("sz", ""),
        "broker_order_qty": broker_order_qty,
        "broker_order_base_qty": broker_order_base_qty,
        "broker_filled_qty": broker_filled_qty,
        "broker_filled_base_qty": broker_filled_base_qty,
        "broker_contract_value": broker_contract_value,
        "broker_fill_quantity_domain": broker_fill_domain,
        "broker_avg_price": float_from_any(detail.get("avg_px")),
        "broker_updated_at": detail.get("u_time", ""),
        "sync_status": sync_status,
        "audit_id": audit_id,
        "reason": reason,
    }
    # OKX order detail is the first reliable source that tells us a maker order
    # was actually filled.  Before writing the broker_sync snapshot, append only
    # the incremental fill missing from the local state machine; the following
    # broker_sync event then preserves OKX's terminal/live state.
    append_broker_fill_backfill_event_if_needed(
        sync_payload["source_order_id"],
        identity,
        detail,
        order=order,
        sync_payload=sync_payload,
        audit_id=audit_id,
        source="okx_order_sync",
    )
    return append_order_journal_event(
        "order.broker_sync",
        sync_payload,
    )


def append_order_journal_events_from_cycle(run_id: str, cycle: dict[str, Any]) -> None:
    cycle_index = int(cycle.get("cycle_index", 0) or 0)
    label = str(cycle.get("label", ""))
    order_meta_by_id: dict[str, dict[str, Any]] = {}
    for order in cycle.get("orders", []) or []:
        if not isinstance(order, dict):
            continue
        instrument = instrument_from_report_item(order)
        attribution_fields = order_signal_attribution_fields(order)
        order_id = str(order.get("order_id", ""))
        if order_id:
            order_meta_by_id[order_id] = attribution_fields
        append_order_journal_event(
            "order.created",
            {
                "run_id": run_id,
                "cycle_index": cycle_index,
                "label": label,
                "order_id": order_id,
                "paper_session_id": order.get("paper_session_id", ""),
                "inst_id": instrument.get("inst_id", ""),
                **attribution_fields,
                "side": order.get("side", ""),
                "order_type": order.get("type", ""),
                "quantity": float_from_any(order.get("quantity")),
                "remaining_qty": float_from_any(order.get("quantity")),
                "limit_price": order_report_price(order),
                "state": "pending",
                "broker_status": order.get("broker_status", "PENDING"),
                "time_in_force": order.get("time_in_force", ""),
                "parent_decision_id": order.get("parent_decision_id", ""),
            },
        )
    for fill in cycle.get("reports", []) or []:
        if not isinstance(fill, dict) or float_from_any(fill.get("last_fill_qty")) <= 0.0:
            continue
        instrument = instrument_from_report_item(fill)
        order_meta = order_meta_by_id.get(str(fill.get("order_id", "")), {})
        attribution_fields = order_signal_attribution_fields(fill, order_meta)
        append_order_journal_event(
            "order.fill",
            {
                "run_id": run_id,
                "cycle_index": cycle_index,
                "label": label,
                "order_id": fill.get("order_id", ""),
                "paper_session_id": fill.get("paper_session_id", ""),
                "inst_id": instrument.get("inst_id", ""),
                **attribution_fields,
                "side": fill.get("side", ""),
                "filled_qty": float_from_any(fill.get("last_fill_qty")),
                "remaining_qty": float_from_any(fill.get("remaining_qty")),
                "fill_price": float_from_any(fill.get("last_fill_price"), float_from_any(fill.get("avg_price"))),
                "avg_price": float_from_any(fill.get("avg_price")),
                "commission": float_from_any(fill.get("commission")),
                "position_effect": fill.get("position_effect", ""),
                "closed_qty": float_from_any(fill.get("closed_qty")),
                "opened_qty": float_from_any(fill.get("opened_qty")),
                "close_gross_pnl": float_from_any(fill.get("close_gross_pnl")),
                "close_fee": float_from_any(fill.get("close_fee")),
                "close_net_pnl": float_from_any(fill.get("close_net_pnl")),
                "realized_pnl_after": float_from_any(fill.get("realized_pnl_after")),
                "state": normalize_order_state(str(fill.get("status", ""))),
                "broker_status": fill.get("broker_status", ""),
            },
        )
    for expired in cycle.get("expired_order_records", []) or []:
        if not isinstance(expired, dict):
            continue
        instrument = instrument_from_report_item(expired)
        order_meta = order_meta_by_id.get(str(expired.get("order_id", "")), {})
        attribution_fields = order_signal_attribution_fields(expired, order_meta)
        append_order_journal_event(
            "order.expired",
            {
                "run_id": run_id,
                "cycle_index": cycle_index,
                "label": expired.get("expired_label", label),
                "order_id": expired.get("order_id", ""),
                "paper_session_id": expired.get("paper_session_id", ""),
                "inst_id": instrument.get("inst_id", ""),
                **attribution_fields,
                "side": expired.get("side", ""),
                "remaining_qty": float_from_any(expired.get("quantity")),
                "limit_price": order_report_price(expired),
                "state": "expired",
                "broker_status": expired.get("broker_status", "EXPIRED"),
                "reason": expired.get("reason", ""),
            },
        )


def read_order_journal(limit: int = 5000) -> list[dict[str, Any]]:
    if not ORDER_JOURNAL_PATH.exists():
        return []
    limit = max(0, min(int(limit), 20000))
    if limit <= 0:
        return []
    with ORDER_JOURNAL_LOCK:
        with ORDER_JOURNAL_PATH.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 4_000_000))
            text = handle.read().decode("utf-8", "ignore")
    rows: list[dict[str, Any]] = []
    for line in text.splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def reduce_order_states(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for event in events:
        order_key = str(event.get("order_key") or order_event_key(str(event.get("paper_session_id", "")), str(event.get("order_id", ""))))
        row = states.setdefault(
            order_key,
            {
                "order_key": order_key,
                "paper_session_id": event.get("paper_session_id", ""),
                "order_id": event.get("order_id", ""),
                "inst_id": event.get("inst_id", ""),
                "strategy_id": event.get("strategy_id", ""),
                "agent_id": event.get("agent_id", ""),
                "trading_unit_id": event.get("trading_unit_id", ""),
                "trading_unit_name": event.get("trading_unit_name", ""),
                "strategy_attribution": event.get("strategy_attribution", []),
                "strategy_ids": event.get("strategy_ids", []),
                "side": event.get("side", ""),
                "order_type": event.get("order_type", ""),
                "quantity": 0.0,
                "filled_qty": 0.0,
                "remaining_qty": 0.0,
                "limit_price": 0.0,
                "avg_price": 0.0,
                "commission": 0.0,
                "closed_qty": 0.0,
                "opened_qty": 0.0,
                "close_gross_pnl": 0.0,
                "close_fee": 0.0,
                "close_net_pnl": 0.0,
                "realized_pnl_after": 0.0,
                "position_effect": "",
                "state": "unknown",
                "broker_status": "",
                "broker_inst_id": "",
                "broker_order_id": "",
                "broker_cl_ord_id": "",
                "broker_state": "",
                "broker_order_qty": 0.0,
                "broker_order_base_qty": 0.0,
                "broker_filled_qty": 0.0,
                "broker_filled_base_qty": 0.0,
                "broker_contract_value": 0.0,
                "broker_fill_quantity_domain": "",
                "broker_avg_price": 0.0,
                "broker_updated_at": "",
                "sync_status": "",
                "sync_audit_id": "",
                "created_at": "",
                "updated_at": "",
                "last_event_type": "",
                "run_id": "",
                "cycle_index": 0,
                "reason": "",
            },
        )
        event_type = str(event.get("type", ""))
        row["updated_at"] = event.get("ts", row.get("updated_at", ""))
        row["last_event_type"] = event_type
        row["run_id"] = event.get("run_id", row.get("run_id", ""))
        row["cycle_index"] = max(int(row.get("cycle_index", 0) or 0), int(event.get("cycle_index", 0) or 0))
        for key in ["paper_session_id", "order_id", "inst_id", "side", "broker_status", "strategy_id", "agent_id", "trading_unit_id", "trading_unit_name"]:
            if event.get(key):
                row[key] = event.get(key)
        if isinstance(event.get("strategy_attribution"), list):
            row["strategy_attribution"] = event.get("strategy_attribution")
        if isinstance(event.get("strategy_ids"), list):
            row["strategy_ids"] = event.get("strategy_ids")
        if event.get("order_type"):
            row["order_type"] = event.get("order_type")
        if event.get("limit_price") is not None:
            row["limit_price"] = float_from_any(event.get("limit_price"))
        if event_type == "order.created":
            row["created_at"] = event.get("ts", row.get("created_at", ""))
            row["quantity"] = float_from_any(event.get("quantity"))
            row["remaining_qty"] = float_from_any(event.get("remaining_qty"), row["quantity"])
            row["state"] = normalize_order_state(str(event.get("state", "pending")))
            row["time_in_force"] = event.get("time_in_force", "")
            row["parent_decision_id"] = event.get("parent_decision_id", "")
        elif event_type == "order.fill":
            fill_qty = float_from_any(event.get("filled_qty"))
            row["filled_qty"] = float_from_any(row.get("filled_qty")) + fill_qty
            row["remaining_qty"] = float_from_any(event.get("remaining_qty"), max(float_from_any(row.get("quantity")) - row["filled_qty"], 0.0))
            row["avg_price"] = float_from_any(event.get("avg_price"), float_from_any(event.get("fill_price"), row.get("avg_price", 0.0)))
            row["commission"] = float_from_any(row.get("commission")) + float_from_any(event.get("commission"))
            row["closed_qty"] = float_from_any(row.get("closed_qty")) + float_from_any(event.get("closed_qty"))
            row["opened_qty"] = float_from_any(row.get("opened_qty")) + float_from_any(event.get("opened_qty"))
            row["close_gross_pnl"] = float_from_any(row.get("close_gross_pnl")) + float_from_any(event.get("close_gross_pnl"))
            row["close_fee"] = float_from_any(row.get("close_fee")) + float_from_any(event.get("close_fee"))
            row["close_net_pnl"] = float_from_any(row.get("close_net_pnl")) + float_from_any(event.get("close_net_pnl"))
            if event.get("realized_pnl_after") is not None:
                row["realized_pnl_after"] = float_from_any(event.get("realized_pnl_after"))
            if event.get("position_effect"):
                row["position_effect"] = event.get("position_effect")
            state = normalize_order_state(str(event.get("state", "")))
            row["state"] = state if state not in {"unknown", ""} else ("filled" if row["remaining_qty"] <= 1e-12 else "partially_filled")
        elif event_type == "order.expired":
            row["remaining_qty"] = float_from_any(event.get("remaining_qty"), row.get("remaining_qty", 0.0))
            row["state"] = "expired"
            row["reason"] = event.get("reason", "")
        elif event_type == "order.broker_sync":
            row["broker_inst_id"] = event.get("broker_inst_id", row.get("broker_inst_id", ""))
            row["broker_order_id"] = event.get("broker_order_id", row.get("broker_order_id", ""))
            row["broker_cl_ord_id"] = event.get("broker_cl_ord_id", row.get("broker_cl_ord_id", ""))
            row["broker_state"] = event.get("broker_state", row.get("broker_state", ""))
            row["broker_order_qty"] = float_from_any(event.get("broker_order_qty"), row.get("broker_order_qty", 0.0))
            row["broker_order_base_qty"] = float_from_any(event.get("broker_order_base_qty"), row.get("broker_order_base_qty", 0.0))
            if row["broker_order_base_qty"] > BROKER_FILL_EPS:
                row["quantity"] = row["broker_order_base_qty"]
                row["remaining_qty"] = max(row["quantity"] - float_from_any(row.get("filled_qty")), 0.0)
            row["broker_filled_qty"] = float_from_any(event.get("broker_filled_qty"), row.get("broker_filled_qty", 0.0))
            row["broker_filled_base_qty"] = float_from_any(event.get("broker_filled_base_qty"), row.get("broker_filled_base_qty", 0.0))
            row["broker_contract_value"] = float_from_any(event.get("broker_contract_value"), row.get("broker_contract_value", 0.0))
            if event.get("broker_fill_quantity_domain"):
                row["broker_fill_quantity_domain"] = event.get("broker_fill_quantity_domain")
            row["broker_avg_price"] = float_from_any(event.get("broker_avg_price"), row.get("broker_avg_price", 0.0))
            authoritative_filled = row["broker_filled_base_qty"] if row["broker_filled_base_qty"] > BROKER_FILL_EPS else row["broker_filled_qty"]
            if event.get("broker_filled_qty") is not None or event.get("broker_filled_base_qty") is not None:
                row["filled_qty"] = authoritative_filled
                if row["broker_avg_price"] > 0.0:
                    row["avg_price"] = row["broker_avg_price"]
                if row["quantity"] < row["filled_qty"]:
                    row["quantity"] = row["filled_qty"]
                row["remaining_qty"] = max(float_from_any(row.get("quantity")) - row["filled_qty"], 0.0)
            row["broker_updated_at"] = event.get("broker_updated_at", row.get("broker_updated_at", ""))
            row["sync_status"] = event.get("sync_status", row.get("sync_status", ""))
            row["sync_audit_id"] = event.get("audit_id", row.get("sync_audit_id", ""))
            state = broker_order_state_to_paper_state(event.get("broker_state") or event.get("state"))
            if state and state != "unknown":
                row["state"] = state
            if event.get("broker_status"):
                row["broker_status"] = event.get("broker_status")
            if event.get("reason"):
                row["reason"] = event.get("reason")
        row["terminal"] = row["state"] in {"filled", "expired", "cancelled", "rejected"}
    return sorted(states.values(), key=lambda row: (str(row.get("updated_at", "")), str(row.get("order_key", ""))), reverse=True)


def order_state_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    limit = bounded_int(params.get("limit", ["500"])[0], 500, 1, 5000)
    events = read_order_journal(max(limit * 10, 1000))
    states = reduce_order_states(events)
    counts: dict[str, int] = {}
    for row in states:
        key = str(row.get("state", "unknown"))
        counts[key] = counts.get(key, 0) + 1
    return {
        "ok": True,
        "generated_at": now_iso(),
        "journal_path": str(ORDER_JOURNAL_PATH),
        "summary": {
            "orders": len(states),
            "events": len(events),
            "state_counts": dict(sorted(counts.items())),
        },
        "orders": states[:limit],
        "events": events[-limit:][::-1],
    }


def order_state_index(limit: int = 5000) -> dict[str, dict[str, Any]]:
    """Return the latest local state per paper order key.

    This helper is intentionally read-only.  It is used by OKX reconciliation
    code to decide whether an exchange-side fill has already been represented
    in the local order journal before appending a delta event.
    """
    events = read_order_journal(max(limit * 10, 1000))
    return {
        str(row.get("order_key", "")): row
        for row in reduce_order_states(events)
        if str(row.get("order_key", ""))
    }


def okx_inst_type_from_inst_id(inst_id: Any) -> str:
    text = str(inst_id or "").upper().strip()
    parts = text.split("-")
    if len(parts) >= 3:
        suffix = parts[-1]
        if suffix in OKX_DERIVATIVE_INST_TYPES:
            return suffix
        return "FUTURES"
    return "SPOT"


def okx_contract_value_from_sources(inst_id: Any, order: dict[str, Any], detail: dict[str, Any]) -> float:
    """Find the contract value needed to convert OKX SWAP/FUTURES sz to base qty."""
    for value in (
        order.get("_ctVal"),
        order.get("ctVal"),
        order.get("ct_val"),
        detail.get("ctVal"),
        detail.get("ct_val"),
    ):
        parsed = float_from_any(value)
        if parsed > 0.0:
            return parsed

    inst = str(inst_id or detail.get("inst_id") or order.get("instId") or "").upper().strip()
    inst_type = okx_inst_type_from_inst_id(inst)
    if inst_type not in OKX_DERIVATIVE_INST_TYPES:
        return 0.0
    rows, _ = okx_cached_live_derivative_rows(inst_type)
    parsed = float_from_any(rows.get(inst, {}).get("ct_val") if isinstance(rows.get(inst), dict) else 0.0)
    return parsed if parsed > 0.0 else 0.0


def okx_normalized_broker_fill_qty(inst_id: Any, raw_filled_qty: Any, contract_value: Any) -> tuple[float, str]:
    """Normalize OKX filled quantity into the paper engine's base-coin unit."""
    raw = float_from_any(raw_filled_qty)
    inst_type = okx_inst_type_from_inst_id(inst_id)
    ct_val = float_from_any(contract_value)
    if inst_type in OKX_DERIVATIVE_INST_TYPES and ct_val > 0.0:
        return raw * ct_val, "base_from_contracts"
    if inst_type in OKX_DERIVATIVE_INST_TYPES:
        return raw, "contracts_missing_ctval"
    return raw, "base"


def okx_normalized_broker_order_qty(inst_id: Any, raw_order_qty: Any, contract_value: Any) -> float:
    """Normalize OKX order size into base quantity for local child-order state."""
    raw = float_from_any(raw_order_qty)
    if raw <= 0.0:
        return 0.0
    inst_type = okx_inst_type_from_inst_id(inst_id)
    ct_val = float_from_any(contract_value)
    if inst_type in OKX_DERIVATIVE_INST_TYPES and ct_val > 0.0:
        return raw * ct_val
    if inst_type in OKX_DERIVATIVE_INST_TYPES:
        return 0.0
    return raw


def latest_okx_submission_orders_by_source(limit: int = 1000) -> dict[str, dict[str, Any]]:
    """Index recent submit audits by source_order_id for ctVal and order metadata."""
    result: dict[str, dict[str, Any]] = {}
    for row in reversed(read_okx_audit(limit)):
        if str(row.get("action", "")) != "order_submitted":
            continue
        source_order_id = str(row.get("source_order_id", "")).strip()
        order = row.get("order", {}) if isinstance(row.get("order"), dict) else {}
        if source_order_id and order:
            result[source_order_id] = order
    return result


def broker_fill_backfill_action_from_state(
    row: dict[str, Any],
    *,
    source_order_id: str = "",
    identity: Optional[dict[str, Any]] = None,
    detail: Optional[dict[str, Any]] = None,
    order: Optional[dict[str, Any]] = None,
    audit_id: str = "",
) -> dict[str, Any]:
    """Build one local fill-delta action from an OKX broker snapshot.

    OKX derivatives report accFillSz in contracts.  The local paper order book
    tracks base-coin quantity, so the action always compares normalized
    exchange quantity, not raw contracts, against local filled_qty.
    """
    row = row if isinstance(row, dict) else {}
    detail = detail if isinstance(detail, dict) else {}
    order = order if isinstance(order, dict) else {}
    identity = identity if isinstance(identity, dict) else {}
    order_key = str(source_order_id or row.get("order_key") or "").strip()
    session_id, order_id = split_paper_source_order_id(order_key)
    has_local_state = bool(
        row.get("paper_session_id")
        or row.get("order_id")
        or row.get("created_at")
        or row.get("updated_at")
    )
    inst_id = str(
        detail.get("inst_id")
        or identity.get("instId")
        or order.get("instId")
        or row.get("broker_inst_id")
        or row.get("inst_id")
        or ""
    ).upper().strip()
    raw_broker_filled = float_from_any(
        detail.get("acc_fill_sz"),
        float_from_any(row.get("broker_filled_qty")),
    )
    contract_value = okx_contract_value_from_sources(inst_id, order, detail)
    raw_broker_order_qty = float_from_any(
        detail.get("sz"),
        float_from_any(row.get("broker_order_qty")),
    )
    broker_order_base_qty = okx_normalized_broker_order_qty(
        inst_id,
        raw_broker_order_qty,
        contract_value,
    )
    normalized_broker_filled, quantity_domain = okx_normalized_broker_fill_qty(
        inst_id,
        raw_broker_filled,
        contract_value,
    )
    local_filled = float_from_any(row.get("filled_qty"))
    delta = normalized_broker_filled - local_filled
    quantity = broker_order_base_qty or float_from_any(row.get("quantity"))
    remaining = max(quantity - normalized_broker_filled, 0.0) if quantity > 0.0 else 0.0
    broker_state = str(detail.get("state") or row.get("broker_state") or row.get("state") or "").lower().strip()
    state = broker_order_state_to_paper_state(broker_state)
    if state in {"unknown", "pending"}:
        state = "filled" if remaining <= BROKER_FILL_EPS and normalized_broker_filled > 0.0 else "partially_filled"
    fill_price = float_from_any(
        detail.get("avg_px"),
        float_from_any(detail.get("px"), float_from_any(row.get("broker_avg_price"), float_from_any(row.get("avg_price"), float_from_any(row.get("limit_price"))))),
    )
    eligible = (
        bool(order_key)
        and has_local_state
        and bool(inst_id)
        and raw_broker_filled > BROKER_FILL_EPS
        and normalized_broker_filled > local_filled + BROKER_FILL_EPS
        and quantity_domain != "contracts_missing_ctval"
    )
    reason = "OKX broker_sync 显示新增成交，按合约 ctVal 折算为本地 base 数量后回补 order.fill。"
    if not eligible:
        if not has_local_state:
            reason = "当前 order journal 窗口找不到本地订单状态，不能安全回补。"
        elif quantity_domain == "contracts_missing_ctval":
            reason = "缺少 ctVal，不能安全把 OKX 合约张数折算为本地 base 数量。"
        elif raw_broker_filled <= BROKER_FILL_EPS:
            reason = "OKX 尚无成交数量。"
        elif normalized_broker_filled <= local_filled + BROKER_FILL_EPS:
            reason = "本地 filled_qty 已覆盖 OKX 归一化成交数量。"
        else:
            reason = "缺少 source_order_id 或 instId，不能安全回补。"
    attribution_context = source_order_attribution_context(row, order)
    return {
        "eligible": bool(eligible),
        "order_key": order_key,
        "paper_session_id": row.get("paper_session_id", session_id),
        "order_id": row.get("order_id", order_id),
        "inst_id": inst_id,
        **attribution_context,
        "side": detail.get("side") or row.get("side") or order.get("side", ""),
        "order_type": detail.get("ord_type") or row.get("order_type") or order.get("ordType", ""),
        "quantity": quantity,
        "local_filled_qty": local_filled,
        "broker_order_qty": raw_broker_order_qty,
        "broker_order_base_qty": broker_order_base_qty,
        "broker_filled_qty": raw_broker_filled,
        "broker_filled_base_qty": normalized_broker_filled,
        "broker_fill_delta_qty": max(delta, 0.0),
        "broker_contract_value": contract_value,
        "broker_fill_quantity_domain": quantity_domain,
        "remaining_qty": remaining,
        "fill_price": fill_price,
        "state": state,
        "broker_state": broker_state,
        "broker_order_id": detail.get("ord_id") or identity.get("ordId") or row.get("broker_order_id", ""),
        "broker_cl_ord_id": detail.get("cl_ord_id") or identity.get("clOrdId") or row.get("broker_cl_ord_id", ""),
        "audit_id": audit_id or row.get("sync_audit_id", ""),
        "reason": reason,
    }


def broker_sync_normalization_needed(row: dict[str, Any], action: dict[str, Any]) -> bool:
    """Whether a historical broker_sync needs base-quantity fields refreshed."""
    if not row or not action.get("order_key"):
        return False
    if not (
        row.get("paper_session_id")
        or row.get("order_id")
        or row.get("created_at")
        or row.get("updated_at")
    ):
        return False
    if float_from_any(action.get("broker_filled_qty")) <= BROKER_FILL_EPS:
        return False
    if action.get("broker_fill_quantity_domain") == "contracts_missing_ctval":
        return False
    return (
        float_from_any(row.get("broker_filled_base_qty")) <= BROKER_FILL_EPS
        or float_from_any(row.get("broker_order_base_qty")) <= BROKER_FILL_EPS
    )


def append_broker_fill_backfill_event(action: dict[str, Any], *, source: str) -> dict[str, Any]:
    """Append an idempotent local fill delta derived from OKX order detail."""
    if not action.get("eligible"):
        return {}
    delta = float_from_any(action.get("broker_fill_delta_qty"))
    if delta <= BROKER_FILL_EPS:
        return {}
    return append_order_journal_event(
        "order.fill",
        {
            "source": "okx_broker_fill_backfill",
            "repair_source": source,
            "paper_session_id": action.get("paper_session_id", ""),
            "order_id": action.get("order_id", ""),
            "source_order_id": action.get("order_key", ""),
            "inst_id": action.get("inst_id", ""),
            "strategy_id": action.get("strategy_id", ""),
            "agent_id": action.get("agent_id", ""),
            "trading_unit_id": action.get("trading_unit_id", ""),
            "trading_unit_name": action.get("trading_unit_name", ""),
            "side": action.get("side", ""),
            "order_type": action.get("order_type", ""),
            "filled_qty": delta,
            "remaining_qty": float_from_any(action.get("remaining_qty")),
            "fill_price": float_from_any(action.get("fill_price")),
            "avg_price": float_from_any(action.get("fill_price")),
            "commission": 0.0,
            "position_effect": "broker_sync_unclassified",
            "closed_qty": 0.0,
            "opened_qty": 0.0,
            "close_gross_pnl": 0.0,
            "close_fee": 0.0,
            "close_net_pnl": 0.0,
            "state": action.get("state", "filled"),
            "broker_status": f"OKX:{action.get('broker_state', '') or 'filled'}",
            "broker_order_id": action.get("broker_order_id", ""),
            "broker_cl_ord_id": action.get("broker_cl_ord_id", ""),
            "broker_order_qty": float_from_any(action.get("broker_order_qty")),
            "broker_order_base_qty": float_from_any(action.get("broker_order_base_qty")),
            "broker_filled_qty": float_from_any(action.get("broker_filled_qty")),
            "broker_filled_base_qty": float_from_any(action.get("broker_filled_base_qty")),
            "broker_contract_value": float_from_any(action.get("broker_contract_value")),
            "broker_fill_quantity_domain": action.get("broker_fill_quantity_domain", ""),
            "broker_sync_audit_id": action.get("audit_id", ""),
            "pnl_status": "pending_trade_reconciliation",
            "reason": action.get("reason", ""),
        },
    )


def append_broker_fill_backfill_event_if_needed(
    source_order_id: Any,
    identity: dict[str, Any],
    detail: dict[str, Any],
    *,
    order: Optional[dict[str, Any]] = None,
    sync_payload: Optional[dict[str, Any]] = None,
    audit_id: str = "",
    source: str,
) -> dict[str, Any]:
    source_key = str(source_order_id or "").strip()
    if not source_key:
        return {}
    state_row = order_state_index(5000).get(source_key, {})
    merged = dict(state_row)
    if isinstance(sync_payload, dict):
        merged.update(sync_payload)
    action = broker_fill_backfill_action_from_state(
        merged,
        source_order_id=source_key,
        identity=identity,
        detail=detail,
        order=order,
        audit_id=audit_id,
    )
    return append_broker_fill_backfill_event(action, source=source)


def trace_failed_checks(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect the failed pre-trade facts that explain an execution decision."""
    failed: list[dict[str, Any]] = []
    risk = candidate.get("risk", {}) if isinstance(candidate.get("risk"), dict) else {}
    for group in ("cxx_policy_checks", "order_rule_checks"):
        checks = risk.get(group, []) if isinstance(risk.get(group), list) else []
        for item in checks:
            if isinstance(item, dict) and not item.get("ok"):
                failed.append(
                    {
                        "group": group,
                        "name": item.get("name", ""),
                        "severity": item.get("severity", ""),
                        "message": item.get("message", ""),
                    }
                )
    tradeability = candidate.get("tradeability", {}) if isinstance(candidate.get("tradeability"), dict) else {}
    checks = tradeability.get("checks", []) if isinstance(tradeability.get("checks"), list) else []
    for item in checks:
        if isinstance(item, dict) and not item.get("ok"):
            failed.append(
                {
                    "group": "tradeability",
                    "name": item.get("name", ""),
                    "severity": item.get("severity", ""),
                    "message": item.get("message", ""),
                }
            )
    return failed[:20]


def execution_trace_source_order(source_order: dict[str, Any]) -> dict[str, Any]:
    instrument = instrument_from_report_item(source_order)
    return {
        "paper_session_id": source_order.get("paper_session_id", ""),
        "order_id": source_order.get("order_id", ""),
        "inst_id": instrument.get("inst_id", ""),
        "side": source_order.get("side", ""),
        "type": source_order.get("type", ""),
        "quantity": float_from_any(source_order.get("quantity")),
        "reference_price": float_from_any(source_order.get("reference_price")),
        "status": source_order.get("status", ""),
        "broker_status": source_order.get("broker_status", ""),
        "parent_decision_id": source_order.get("parent_decision_id", ""),
    }


def execution_trace_market_snapshot(candidate: dict[str, Any]) -> dict[str, Any]:
    tradeability = candidate.get("tradeability", {}) if isinstance(candidate.get("tradeability"), dict) else {}
    return {
        "bid": tradeability.get("bid", ""),
        "ask": tradeability.get("ask", ""),
        "last": tradeability.get("last", ""),
        "spread_bps": tradeability.get("spread_bps"),
        "expected_cost_bps": tradeability.get("expected_cost_bps"),
        "volume_24h_usdt": tradeability.get("volume_24h_usdt"),
        "depth": tradeability.get("depth", {}),
    }


def runtime_risk_budget_snapshot() -> dict[str, Any]:
    """Read the latest C++ risk budget decision for trace and UI drill-downs."""
    market_quality = read_json_file(MARKET_QUALITY_LATEST_PATH)
    budget = market_quality.get("risk_budget", {}) if isinstance(market_quality.get("risk_budget"), dict) else {}
    checks = budget.get("checks", []) if isinstance(budget.get("checks"), list) else []
    normalized_checks: list[dict[str, Any]] = []
    failed_checks: list[dict[str, Any]] = []
    for item in checks:
        if not isinstance(item, dict):
            continue
        check = {
            "name": str(item.get("name", "")),
            "ok": bool(item.get("ok", False)),
            "severity": str(item.get("severity", "")),
            "message": str(item.get("message", "")),
        }
        normalized_checks.append(check)
        if not check["ok"]:
            failed_checks.append(check)
    action = str(budget.get("action", ""))
    reason = str(budget.get("reason", ""))
    if action in {"Halt", "Reject"} and not failed_checks:
        failed_checks.append(
            {
                "name": "runtime_budget_action",
                "ok": False,
                "severity": "halt",
                "message": reason or action,
            }
        )
    return {
        "action": action,
        "reason": reason,
        "scale": float_from_any(budget.get("scale"), 1.0),
        "source": str(market_quality.get("source", "")),
        "generated_at": str(market_quality.get("generated_at", "")),
        "generated_at_ms": market_quality.get("generated_at_ms", 0),
        "checks": normalized_checks[:40],
        "failed_checks": failed_checks[:20],
    }


def append_execution_trace_event(
    event_type: str,
    source_order_id: str,
    candidate: dict[str, Any],
    cycle: dict[str, Any],
    *,
    status: str,
    message: str = "",
    result: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Append a local signal-to-execution decision record."""
    EXECUTION_TRACE_DIR.mkdir(parents=True, exist_ok=True)
    source_order = candidate.get("source_order", {}) if isinstance(candidate.get("source_order"), dict) else {}
    trace_key = hashlib.sha256(
        f"{source_order_id}|{cycle.get('cycle_index', '')}|{cycle.get('label', '')}|{event_type}".encode("utf-8")
    ).hexdigest()[:20]
    order = candidate.get("order", {}) if isinstance(candidate.get("order"), dict) else {}
    tradeability = candidate.get("tradeability", {}) if isinstance(candidate.get("tradeability"), dict) else {}
    forecast = candidate.get("execution_forecast", {}) if isinstance(candidate.get("execution_forecast"), dict) else {}
    result = result if isinstance(result, dict) else {}
    runtime_budget = (
        candidate.get("runtime_risk_budget")
        if isinstance(candidate.get("runtime_risk_budget"), dict)
        else runtime_risk_budget_snapshot()
    )
    failed_checks = trace_failed_checks(candidate)
    for item in runtime_budget.get("failed_checks", []) if isinstance(runtime_budget.get("failed_checks"), list) else []:
        if not isinstance(item, dict):
            continue
        failed_checks.append(
            {
                "group": "runtime_risk_budget",
                "name": item.get("name", ""),
                "severity": item.get("severity", ""),
                "message": item.get("message", ""),
            }
        )
    event = {
        "id": f"exec-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}-{uuid4().hex[:8]}",
        "trace_key": trace_key,
        "ts": now_iso(),
        "ts_ms": int(time.time() * 1000),
        "type": event_type,
        "status": status,
        "source": "paper_okx_bridge",
        "cycle_index": cycle.get("cycle_index", 0),
        "cycle_label": cycle.get("label", ""),
        "source_order_id": source_order_id,
        "source_order": execution_trace_source_order(source_order),
        "inst_id": candidate.get("inst_id", order.get("instId", "")),
        "side": order.get("side", source_order.get("side", "")),
        "approved": bool(candidate.get("approved")),
        "message": message or candidate.get("message") or candidate.get("reason", ""),
        "order": order,
        "planned_notional": candidate.get("planned_notional", 0.0),
        "source_notional": candidate.get("source_notional", 0.0),
        "scale": candidate.get("scale", 0.0),
        "tradeability_status": candidate.get("tradeability_status", tradeability.get("status", "")),
        "execution_forecast": forecast,
        "market": execution_trace_market_snapshot(candidate),
        "runtime_risk_budget": runtime_budget,
        "failed_checks": failed_checks[:20],
        "result": {
            key: result.get(key)
            for key in [
                "ok",
                "error",
                "audit_id",
                "request_id",
                "status_code",
                "base_url",
                "okx_code",
                "okx_msg",
                "data_errors",
                "error_summary",
                "raw_okx",
                "fallback_errors",
                "result",
                "order_detail",
            ]
            if key in result
        },
    }
    event = scrub_secret_fields(event)
    with EXECUTION_TRACE_LOCK:
        with EXECUTION_TRACE_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    return event


def read_execution_trace(limit: int = 300, source_order_id: str = "", event_type: str = "") -> list[dict[str, Any]]:
    if not EXECUTION_TRACE_PATH.exists():
        return []
    limit = max(0, min(int(limit), 5000))
    if limit <= 0:
        return []
    with EXECUTION_TRACE_LOCK:
        rows = read_jsonl_tail(EXECUTION_TRACE_PATH, max(limit * 5, limit))
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if source_order_id and str(row.get("source_order_id", "")) != source_order_id:
            continue
        if event_type and str(row.get("type", "")) != event_type:
            continue
        filtered.append(row)
    return filtered[-limit:][::-1]


def execution_trace_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    limit = bounded_int(params.get("limit", ["300"])[0], 300, 1, 5000)
    source_order_id = params.get("sourceOrderId", params.get("source_order_id", [""]))[0].strip()
    event_type = params.get("type", [""])[0].strip()
    rows = read_execution_trace(limit, source_order_id=source_order_id, event_type=event_type)
    runtime_budget = runtime_risk_budget_snapshot()
    display_rows: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    tradeability_counts: dict[str, int] = {}
    total_notional = 0.0
    total_cost = 0.0
    for row in rows:
        display_row = dict(row)
        if not isinstance(display_row.get("runtime_risk_budget"), dict):
            display_row["runtime_risk_budget"] = runtime_budget
        display_rows.append(display_row)
        status = str(row.get("status") or "unknown")
        event_name = str(row.get("type") or "unknown")
        tradeability_status = str(row.get("tradeability_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        type_counts[event_name] = type_counts.get(event_name, 0) + 1
        tradeability_counts[tradeability_status] = tradeability_counts.get(tradeability_status, 0) + 1
        forecast = row.get("execution_forecast", {}) if isinstance(row.get("execution_forecast"), dict) else {}
        total_notional += float_from_any(forecast.get("planned_notional_usdt"), float_from_any(row.get("planned_notional")))
        total_cost += float_from_any(forecast.get("expected_cost_usdt"))
    return {
        "ok": True,
        "generated_at": now_iso(),
        "journal_path": str(EXECUTION_TRACE_PATH),
        "summary": {
            "events": len(rows),
            "status_counts": dict(sorted(status_counts.items())),
            "type_counts": dict(sorted(type_counts.items())),
            "tradeability_counts": dict(sorted(tradeability_counts.items())),
            "total_planned_notional_usdt": total_notional,
            "total_expected_cost_usdt": total_cost,
            "weighted_expected_cost_bps": safe_ratio(total_cost, total_notional) * 10000.0,
            "runtime_risk_budget": runtime_budget,
        },
        "events": display_rows,
    }


def execution_trace_health_payload(
    settings: dict[str, Any],
    report: dict[str, Any],
    auto: dict[str, Any],
    *,
    limit: int = 500,
) -> dict[str, Any]:
    """Summarize whether signal-to-execution tracing is healthy.

    Production systems need more than orders and fills; they need evidence that
    every strategy-generated order either submitted, failed, or was explicitly
    blocked with a reason.  This health summary lets ops/readiness catch trace
    gaps before execution data becomes unusable for replay and calibration.
    """
    trace = execution_trace_payload({"limit": [str(limit)]})
    events = trace.get("events", []) if isinstance(trace.get("events"), list) else []
    summary = trace.get("summary", {}) if isinstance(trace.get("summary"), dict) else {}
    latest_event = events[0] if events else {}
    latest_age = age_seconds_from_text(latest_event.get("ts")) if latest_event else None
    status_counts = summary.get("status_counts", {}) if isinstance(summary.get("status_counts"), dict) else {}
    submitted_count = int(status_counts.get("submitted", 0) or 0)
    failed_count = int(status_counts.get("failed", 0) or 0)
    blocked_count = sum(
        int(status_counts.get(key, 0) or 0)
        for key in ("blocked", "blocked_tradeability", "guarded")
    )
    decision_count = submitted_count + failed_count + blocked_count
    failure_ratio = safe_ratio(float(failed_count), float(decision_count))
    blocked_ratio = safe_ratio(float(blocked_count), float(decision_count))
    trace_sample_max_age_seconds = max(1800.0, float(paper_worker_poll_seconds(settings) * 30))
    trace_sample_fresh = latest_age is None or latest_age <= trace_sample_max_age_seconds
    decision_sample_actionable = decision_count > 0 and trace_sample_fresh

    cycles = report.get("cycles", []) if isinstance(report.get("cycles"), list) else []
    latest_cycle = cycles[-1] if cycles and isinstance(cycles[-1], dict) else {}
    latest_cycle_orders = latest_cycle.get("orders", []) if isinstance(latest_cycle.get("orders"), list) else []
    latest_cycle_index = latest_cycle.get("cycle_index", None)
    latest_cycle_label = str(latest_cycle.get("label", ""))
    latest_trace_coverage = [
        row for row in events
        if row.get("cycle_index") == latest_cycle_index and str(row.get("cycle_label", "")) == latest_cycle_label
    ]

    auto_recent = [item for item in (auto.get("recent", []) or []) if isinstance(item, dict)]
    auto_enabled = bool(settings.get("okx_auto_submit") or auto.get("enabled"))
    max_expected_cost_bps = float_from_any(parse_config().get("execution.max_expected_cost_bps", "50"), 50.0)
    weighted_cost_bps = float_from_any(summary.get("weighted_expected_cost_bps"))
    trace_file = file_state(EXECUTION_TRACE_PATH)
    expected_for_latest_cycle = auto_enabled and bool(latest_cycle_orders)
    has_auto_activity = bool(auto_recent)
    trace_present_for_activity = (not has_auto_activity) or bool(events)
    latest_cycle_covered = (not expected_for_latest_cycle) or bool(latest_trace_coverage) or not has_auto_activity
    cost_ok = (not decision_sample_actionable) or weighted_cost_bps <= max_expected_cost_bps

    checks = [
        paper_health_check(
            "执行轨迹文件",
            trace_file.get("exists") or not auto_enabled,
            "warn",
            f"轨迹文件 {trace_file.get('path')} 已存在。"
            if trace_file.get("exists")
            else "自动提交尚未产生执行轨迹文件。",
            file=trace_file,
        ),
        paper_health_check(
            "执行轨迹覆盖",
            trace_present_for_activity and latest_cycle_covered,
            "warn",
            "最近自动提交流水已有对应执行轨迹。"
            if trace_present_for_activity and latest_cycle_covered
            else "自动提交流水或最新策略订单缺少执行轨迹，需要确认 trace 写入链路。",
            auto_recent_count=len(auto_recent),
            latest_cycle_order_count=len(latest_cycle_orders),
            latest_cycle_trace_count=len(latest_trace_coverage),
        ),
        paper_health_check(
            "执行失败比例",
            (not decision_sample_actionable) or failure_ratio <= 0.20,
            "warn",
            f"执行样本已过期 {int(latest_age)} 秒，失败比例仅作为历史诊断。"
            if decision_count and not trace_sample_fresh and latest_age is not None
            else
            f"失败 {failed_count}/{decision_count}，比例 {failure_ratio:.1%}。"
            if decision_count
            else "暂无执行决策样本。",
            failed_count=failed_count,
            decision_count=decision_count,
            failure_ratio=failure_ratio,
            sample_fresh=trace_sample_fresh,
            sample_age_seconds=latest_age,
            sample_max_age_seconds=trace_sample_max_age_seconds,
        ),
        paper_health_check(
            "执行阻断比例",
            (not decision_sample_actionable) or blocked_ratio <= 0.80,
            "warn",
            f"执行样本已过期 {int(latest_age)} 秒，阻断比例仅作为历史诊断。"
            if decision_count and not trace_sample_fresh and latest_age is not None
            else
            f"阻断 {blocked_count}/{decision_count}，比例 {blocked_ratio:.1%}。"
            if decision_count
            else "暂无执行决策样本。",
            blocked_count=blocked_count,
            decision_count=decision_count,
            blocked_ratio=blocked_ratio,
            sample_fresh=trace_sample_fresh,
            sample_age_seconds=latest_age,
            sample_max_age_seconds=trace_sample_max_age_seconds,
        ),
        paper_health_check(
            "执行成本轨迹",
            cost_ok,
            "warn",
            f"执行成本样本已过期 {int(latest_age)} 秒，仅作为历史诊断。"
            if decision_count and not trace_sample_fresh and latest_age is not None
            else f"加权预计成本 {weighted_cost_bps:.2f} bps，阈值 {max_expected_cost_bps:.2f} bps。",
            weighted_expected_cost_bps=weighted_cost_bps,
            max_expected_cost_bps=max_expected_cost_bps,
            sample_fresh=trace_sample_fresh,
            sample_age_seconds=latest_age,
            sample_max_age_seconds=trace_sample_max_age_seconds,
        ),
    ]
    return {
        "ok": paper_health_overall(checks) != "halt",
        "status": paper_health_overall(checks),
        "journal_path": str(EXECUTION_TRACE_PATH),
        "summary": {
            **summary,
            "latest_event_at": latest_event.get("ts", ""),
            "latest_event_age_seconds": latest_age,
            "latest_cycle_index": latest_cycle_index,
            "latest_cycle_label": latest_cycle_label,
            "latest_cycle_order_count": len(latest_cycle_orders),
            "latest_cycle_trace_count": len(latest_trace_coverage),
            "auto_recent_count": len(auto_recent),
            "failure_ratio": failure_ratio,
            "blocked_ratio": blocked_ratio,
            "max_expected_cost_bps": max_expected_cost_bps,
            "sample_fresh": trace_sample_fresh,
            "sample_max_age_seconds": trace_sample_max_age_seconds,
        },
        "checks": checks,
        "latest": latest_event,
        "file": trace_file,
    }


def execution_failure_example(row: dict[str, Any]) -> dict[str, Any]:
    result = row.get("result", {}) if isinstance(row.get("result"), dict) else {}
    return {
        "ts": row.get("ts", ""),
        "type": row.get("type", ""),
        "status": row.get("status", ""),
        "inst_id": row.get("inst_id", ""),
        "side": row.get("side", ""),
        "source_order_id": row.get("source_order_id", ""),
        "message": row.get("message") or result.get("error") or "",
        "error_summary": result.get("error_summary", {}) if isinstance(result.get("error_summary"), dict) else {},
        "failed_checks": [
            {
                "group": item.get("group", ""),
                "name": item.get("name", ""),
                "message": item.get("message", ""),
            }
            for item in (row.get("failed_checks", []) or [])[:3]
            if isinstance(item, dict)
        ],
    }


def execution_failure_text(row: dict[str, Any]) -> str:
    """Flatten one execution trace row into text for deterministic clustering."""
    chunks: list[str] = [
        str(row.get("type", "")),
        str(row.get("status", "")),
        str(row.get("message", "")),
        str(row.get("tradeability_status", "")),
    ]
    result = row.get("result", {}) if isinstance(row.get("result"), dict) else {}
    for key in ("error", "result", "request_id", "okx_code", "okx_msg"):
        if key in result:
            chunks.append(str(result.get(key, "")))
    error_summary = result.get("error_summary", {}) if isinstance(result.get("error_summary"), dict) else {}
    if error_summary:
        chunks.append(json.dumps(error_summary, ensure_ascii=False, default=str))
    for item in row.get("failed_checks", []) or []:
        if not isinstance(item, dict):
            continue
        chunks.extend(
            [
                str(item.get("group", "")),
                str(item.get("name", "")),
                str(item.get("severity", "")),
                str(item.get("message", "")),
            ]
        )
    return " ".join(chunk for chunk in chunks if chunk)


def execution_failure_okx_error_key(row: dict[str, Any]) -> str:
    """Build a stable display key for the raw OKX failure recorded on a trace."""
    result = row.get("result", {}) if isinstance(row.get("result"), dict) else {}
    error_summary = result.get("error_summary", {}) if isinstance(result.get("error_summary"), dict) else {}
    data_errors = error_summary.get("data_errors", [])
    first_data_error = data_errors[0] if data_errors and isinstance(data_errors[0], dict) else {}
    s_code = str(error_summary.get("s_code") or first_data_error.get("sCode") or "").strip()
    s_msg = str(error_summary.get("s_msg") or first_data_error.get("sMsg") or "").strip()
    if s_code or s_msg:
        return f"sCode={s_code or '-'} {s_msg or '-'}".strip()
    okx_code = str(error_summary.get("okx_code") or result.get("okx_code") or "").strip()
    okx_msg = str(error_summary.get("okx_msg") or result.get("okx_msg") or "").strip()
    if okx_code or okx_msg:
        return f"code={okx_code or '-'} {okx_msg or '-'}".strip()
    error = str(error_summary.get("error") or result.get("error") or "").strip()
    if text_has_any(error, ("all operations failed",)):
        return "bridge=All operations failed"
    return ""


def execution_failure_is_okx_account_mode(row: dict[str, Any]) -> bool:
    """Detect OKX account-mode rejects such as sCode 51010.

    IMPORTANT: 排除 status="guarded" 的条目——这些是门禁自己的阻断记录，
    其中包含原错误消息中的 "51010" 关键字，会形成自激循环。
    只匹配真正从 OKX API 返回的 51010 错误。
    """
    if str(row.get("status", "")).lower().strip() == "guarded":
        return False
    text = f"{execution_failure_okx_error_key(row)} {execution_failure_text(row)}"
    return text_has_any(
        text,
        (
            "51010",
            "current account mode",
            "account mode",
            "账户模式",
        ),
    )


def add_limited_example(target: list[dict[str, Any]], row: dict[str, Any], limit: int = 5) -> None:
    if len(target) < limit:
        target.append(execution_failure_example(row))


def text_has_any(text: str, needles: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(needle.lower() in lower for needle in needles)


def classify_execution_failure(row: dict[str, Any]) -> set[str]:
    """Classify failed/blocked execution trace rows into actionable buckets."""
    status = str(row.get("status", "")).lower()
    event_type = str(row.get("type", "")).lower()
    tradeability_status = str(row.get("tradeability_status", "")).lower()
    failure_like = (
        status in {"failed", "blocked", "blocked_tradeability", "guarded", "rejected"}
        or "failed" in event_type
        or "blocked" in event_type
        or "guarded" in event_type
    )
    if not failure_like:
        return set()

    text = execution_failure_text(row)
    categories: set[str] = set()

    if text_has_any(
        text,
        (
            "timeout",
            "timed out",
            "read operation",
            "handshake",
            "_ssl",
            "ssl",
            "connection",
            "network",
            "proxy",
            "temporarily unavailable",
            "连接",
            "超时",
        ),
    ):
        categories.add("network_timeout")

    if status == "blocked_tradeability" or tradeability_status.startswith("block") or text_has_any(
        text,
        (
            "可交易性",
            "tradeability",
            "不可交易",
        ),
    ):
        categories.add("tradeability_liquidity")

    if text_has_any(
        text,
        (
            "24h",
            "volume",
            "成交量",
            "liquidity",
            "流动性",
            "depth",
            "深度",
            "spread",
            "价差",
            "盘口",
        ),
    ):
        categories.add("tradeability_liquidity")

    if text_has_any(
        text,
        (
            "最近 tick 耗时",
            "tick 耗时",
            "runtime",
            "latency",
            "耗时",
            "自动提交门禁",
            "门禁",
            "guard",
        ),
    ):
        categories.add("runtime_guard")

    if text_has_any(
        text,
        (
            "minsz",
            "min size",
            "小于 minsz",
            "最小",
            "数量 0",
            "下单数量",
        ),
    ):
        categories.add("order_sizing_rules")

    if text_has_any(
        text,
        (
            "ctval",
            "lotsz",
            "ticksz",
            "合约规则",
            "合约元数据",
            "contract rule",
            "instrument rule",
        ),
    ):
        categories.add("order_sizing_rules")

    if text_has_any(
        text,
        (
            "51010",
            "current account mode",
            "account mode",
            "账户模式",
        ),
    ):
        categories.add("okx_account_mode")

    if text_has_any(
        text,
        (
            "all operations failed",
            "submit failed",
            "order failed",
            "rejected",
            "smsg",
            "scode",
            "okx error",
            "api error",
        ),
    ):
        categories.add("exchange_reject")

    if not categories:
        categories.add("unknown_failure")
    return categories


def execution_failure_analysis_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    """Cluster execution trace failures with the C++ ops checker.

    This is read-only: it consumes the local execution trace journal and returns
    an ops view that tells the operator which class of problem is currently
    blocking automated OKX simulated execution.
    """
    limit = bounded_int(params.get("limit", ["500"])[0], 500, 1, 5000)
    trace = execution_trace_payload({"limit": [str(limit)]})
    rows = trace.get("events", []) if isinstance(trace.get("events"), list) else []
    summary = trace.get("summary", {}) if isinstance(trace.get("summary"), dict) else {}
    status_counts = summary.get("status_counts", {}) if isinstance(summary.get("status_counts"), dict) else {}
    submitted_count = int(status_counts.get("submitted", 0) or 0)
    failed_count = int(status_counts.get("failed", 0) or 0)
    blocked_count = int(status_counts.get("blocked", 0) or 0) + int(status_counts.get("blocked_tradeability", 0) or 0)
    guarded_count = int(status_counts.get("guarded", 0) or 0)
    decision_count = submitted_count + failed_count + blocked_count + guarded_count
    denominator = max(decision_count, 1)

    category_counts = {
        "network_timeout": 0,
        "exchange_reject": 0,
        "okx_account_mode": 0,
        "tradeability_liquidity": 0,
        "runtime_guard": 0,
        "order_sizing_rules": 0,
        "unknown_failure": 0,
    }
    examples: dict[str, list[dict[str, Any]]] = {key: [] for key in category_counts}
    okx_error_counts: dict[str, int] = {}
    okx_error_examples: dict[str, list[dict[str, Any]]] = {}
    min_size_rule_count = 0
    contract_rule_count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        okx_error_key = execution_failure_okx_error_key(row)
        if okx_error_key:
            okx_error_counts[okx_error_key] = okx_error_counts.get(okx_error_key, 0) + 1
            add_limited_example(okx_error_examples.setdefault(okx_error_key, []), row)
        categories = classify_execution_failure(row)
        for category in sorted(categories):
            if category not in category_counts:
                continue
            category_counts[category] += 1
            if category == "order_sizing_rules":
                text = execution_failure_text(row)
                if text_has_any(text, ("ctval", "lotsz", "ticksz", "合约规则", "合约元数据", "contract rule", "instrument rule")):
                    contract_rule_count += 1
                else:
                    min_size_rule_count += 1
            add_limited_example(examples[category], row)
    okx_error_rows = [
        {"key": key, "count": count, "examples": okx_error_examples.get(key, [])}
        for key, count in sorted(okx_error_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    binary = ops_check_bin_path()
    if binary is None:
        return {
            "ok": False,
            "generated_at": now_iso(),
            "error": "ops_check executable is not built; run make ops_check",
            "summary": {
                "decision": "block",
                "source": "missing_binary",
                "total_events": len(rows),
                "decision_count": decision_count,
                "failed_count": failed_count,
                "blocked_count": blocked_count,
                "guarded_count": guarded_count,
            },
            "clusters": [],
            "actions": ["先构建 C++ ops_check，再查看执行失败聚类。"],
            "trace": {"journal_path": trace.get("journal_path", ""), "summary": summary},
        }

    args = [
        str(binary),
        "--execution-failures",
        "true",
        "--total-events",
        str(len(rows)),
        "--decision-count",
        str(decision_count),
        "--submitted-count",
        str(submitted_count),
        "--failed-count",
        str(failed_count),
        "--blocked-count",
        str(blocked_count),
        "--guarded-count",
        str(guarded_count),
        "--network-error-count",
        str(category_counts["network_timeout"]),
        "--exchange-error-count",
        str(category_counts["exchange_reject"]),
        "--account-mode-error-count",
        str(category_counts["okx_account_mode"]),
        "--tradeability-block-count",
        str(category_counts["tradeability_liquidity"]),
        "--guard-runtime-count",
        str(category_counts["runtime_guard"]),
        "--min-size-count",
        str(min_size_rule_count),
        "--contract-rule-count",
        str(contract_rule_count),
        "--liquidity-warning-count",
        "0",
        "--unknown-error-count",
        str(category_counts["unknown_failure"]),
        "--failure-ratio",
        str(safe_ratio(float(failed_count), float(denominator))),
        "--blocked-ratio",
        str(safe_ratio(float(blocked_count + guarded_count), float(denominator))),
    ]
    try:
        result = subprocess.run(
            args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:
        return {
            "ok": False,
            "generated_at": now_iso(),
            "error": str(exc),
            "summary": {"decision": "block", "source": "cpp_exception"},
            "clusters": [],
            "actions": ["修复 ops_check 调用异常后再查看执行失败聚类。"],
            "trace": {"journal_path": trace.get("journal_path", ""), "summary": summary},
        }
    if result.returncode != 0:
        return {
            "ok": False,
            "generated_at": now_iso(),
            "error": result.stderr.strip() or result.stdout.strip() or f"ops_check exited {result.returncode}",
            "summary": {"decision": "block", "source": "cpp_error"},
            "clusters": [],
            "actions": ["修复 C++ ops_check 执行失败诊断错误。"],
            "trace": {"journal_path": trace.get("journal_path", ""), "summary": summary},
        }
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "generated_at": now_iso(),
            "error": f"ops_check returned invalid JSON: {exc}",
            "summary": {"decision": "block", "source": "invalid_json"},
            "clusters": [],
            "actions": ["修复 C++ ops_check JSON 输出。"],
            "trace": {"journal_path": trace.get("journal_path", ""), "summary": summary},
        }

    report_clusters = report.get("clusters", []) if isinstance(report.get("clusters"), list) else []
    clusters = []
    for cluster in report_clusters:
        if not isinstance(cluster, dict):
            continue
        cluster_id = str(cluster.get("id", ""))
        clusters.append({**cluster, "examples": examples.get(cluster_id, [])})

    return {
        "ok": True,
        "generated_at": now_iso(),
        "source": "cpp_ops_check",
        "binary": str(binary),
        "summary": {
            "decision": report.get("decision", ""),
            "source": "cpp_ops_check",
            "total_events": len(rows),
            "decision_count": decision_count,
            "submitted_count": submitted_count,
            "failed_count": failed_count,
            "blocked_count": blocked_count,
            "guarded_count": guarded_count,
            "failure_ratio": safe_ratio(float(failed_count), float(denominator)),
            "blocked_ratio": safe_ratio(float(blocked_count + guarded_count), float(denominator)),
            "category_counts": category_counts,
            "min_size_rule_count": min_size_rule_count,
            "contract_rule_count": contract_rule_count,
            "okx_error_counts": okx_error_rows[:10],
        },
        "clusters": clusters,
        "actions": report.get("actions", []) if isinstance(report.get("actions"), list) else [],
        "trace": {"journal_path": trace.get("journal_path", ""), "summary": summary},
    }


def execution_ledger_event_type_from_audit(row: dict[str, Any]) -> str:
    """Map Python OKX audit actions onto the C++ ExecutionLedger vocabulary."""
    action = str(row.get("action", ""))
    if action == "order_submitted":
        return "exchange_ack"
    if action in {"order_cancelled"}:
        return "cancel"
    if action in {"order_synced", "paper_auto_order_synced"}:
        detail = row.get("order_detail", {}) if isinstance(row.get("order_detail"), dict) else {}
        state = str(detail.get("state", "")).lower()
        fill_qty = float_from_any(detail.get("acc_fill_sz"), float_from_any(row.get("acc_fill_sz")))
        if fill_qty > 0.0 and state in {"filled", "partially_filled", "partiallyfilled"}:
            return "fill"
        if state in {"canceled", "cancelled", "mmp_canceled", "expired"}:
            return "cancel"
        if state == "rejected":
            return "error"
        return "sync"
    if action in {
        "order_blocked",
        "order_submit_failed",
        "order_cancel_failed",
        "order_sync_failed",
        "paper_auto_order_sync_failed",
        "derivative_leverage_set_failed",
        "paper_auto_submit_blocked",
    }:
        return "error"
    return ""


def execution_ledger_error_category(row: dict[str, Any]) -> str:
    """Classify failures for later C++ risk/ops aggregation."""
    action = str(row.get("action", ""))
    if action in {"order_blocked", "paper_auto_submit_blocked"}:
        return "local_guard"
    if action == "derivative_leverage_set_failed":
        return "leverage"
    summary = row.get("error_summary", {}) if isinstance(row.get("error_summary"), dict) else {}
    result = row.get("result", {}) if isinstance(row.get("result"), dict) else {}
    raw = row.get("raw_okx", {}) if isinstance(row.get("raw_okx"), dict) else {}
    data_errors = summary.get("data_errors", []) if isinstance(summary.get("data_errors"), list) else []
    text = json.dumps(
        {
            "error": row.get("error", ""),
            "summary": summary,
            "result_error": result.get("error", "") if isinstance(result, dict) else "",
            "raw": raw,
            "data_errors": data_errors,
        },
        ensure_ascii=False,
        default=str,
    ).lower()
    if any(token in text for token in ["timeout", "timed out", "dns", "ssl", "connection", "network", "urlopen", "unreachable"]):
        return "network"
    if any(token in text for token in ["minsz", "min sz", "minimum", "lot", "ctval", "contract", "size", "数量", "张数"]):
        return "quantity_rule"
    if summary.get("okx_code") or summary.get("s_code") or data_errors:
        return "exchange_reject"
    return "unknown"


def execution_ledger_trace_id(row: dict[str, Any], order: dict[str, Any], detail: dict[str, Any], identity: dict[str, Any]) -> str:
    source_order_id = str(row.get("source_order_id") or row.get("_source_order_id") or "").strip()
    cl_ord_id = str(detail.get("cl_ord_id") or order.get("clOrdId") or identity.get("clOrdId") or "").strip()
    ord_id = str(detail.get("ord_id") or row.get("ord_id") or identity.get("ordId") or "").strip()
    return source_order_id or cl_ord_id or ord_id or str(row.get("id", uuid4().hex))


def execution_ledger_float(value: Any) -> float:
    return float_from_any(value, 0.0)


def execution_ledger_fill_ratio(fill_qty: float, order_qty: float) -> float:
    if order_qty <= 0.0 or fill_qty <= 0.0:
        return 0.0
    return max(0.0, min(fill_qty / order_qty, 1.0))


def execution_ledger_slippage_bps(side: str, expected_price: float, fill_price: float) -> float:
    if expected_price <= 0.0 or fill_price <= 0.0:
        return 0.0
    side = side.lower()
    if side == "sell":
        return (expected_price - fill_price) / expected_price * 10000.0
    return (fill_price - expected_price) / expected_price * 10000.0


def append_execution_ledger_event(event: dict[str, Any]) -> dict[str, Any]:
    """Append one ExecutionLedger JSONL event using the C++ schema field names."""
    EXECUTION_LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    row = scrub_secret_fields(event)
    with EXECUTION_LEDGER_LOCK:
        with EXECUTION_LEDGER_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), default=str) + "\n")
    return row


def append_execution_ledger_from_okx_audit(audit_event: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Bridge OKX audit facts into the append-only ExecutionLedger.

    The Python server is still responsible for OKX HTTP calls today.  Mirroring
    those facts into this C++-shaped ledger gives the next C++ OMS/risk process
    a single lifecycle stream to consume without scraping UI-specific audit logs.
    """
    event_type = execution_ledger_event_type_from_audit(audit_event)
    if not event_type:
        return None
    order = audit_event.get("order", {}) if isinstance(audit_event.get("order"), dict) else {}
    payload = audit_event.get("payload", {}) if isinstance(audit_event.get("payload"), dict) else {}
    detail = audit_event.get("order_detail", {}) if isinstance(audit_event.get("order_detail"), dict) else {}
    identity = audit_event.get("identity", {}) if isinstance(audit_event.get("identity"), dict) else {}
    result = audit_event.get("result", {}) if isinstance(audit_event.get("result"), dict) else {}
    error_summary = audit_event.get("error_summary", {}) if isinstance(audit_event.get("error_summary"), dict) else {}

    inst_id = str(detail.get("inst_id") or order.get("instId") or payload.get("instId") or identity.get("instId") or "").upper().strip()
    side = str(detail.get("side") or order.get("side") or payload.get("side") or "").lower().strip()
    pos_side = str(order.get("posSide") or order.get("_posSide") or payload.get("posSide") or "").lower().strip()
    ord_type = str(detail.get("ord_type") or order.get("ordType") or payload.get("ordType") or "").lower().strip()
    expected_price = execution_ledger_float(
        audit_event.get("expected_price")
        or order.get("_expected_price")
        or order.get("px")
        or detail.get("px")
        or payload.get("px")
    )
    order_price = execution_ledger_float(detail.get("px") or order.get("px") or payload.get("px"))
    order_qty = execution_ledger_float(detail.get("sz") or order.get("sz") or payload.get("sz"))
    fill_qty = execution_ledger_float(detail.get("acc_fill_sz") or audit_event.get("acc_fill_sz"))
    fill_price = execution_ledger_float(detail.get("avg_px") or audit_event.get("avg_px"))
    if event_type == "fill" and fill_qty <= 0.0 and order_qty > 0.0 and str(detail.get("state", "")).lower() == "filled":
        fill_qty = order_qty
    trace_id = execution_ledger_trace_id(audit_event, order, detail, identity)
    ts = str(audit_event.get("ts") or now_iso())
    raw_status = str(detail.get("state") or audit_event.get("status") or audit_event.get("action") or "")

    ledger_event = {
        "trace_id": trace_id,
        "event_type": event_type,
        "event_ts": ts,
        "strategy_id": str(audit_event.get("strategy_id") or order.get("_strategy_id") or ""),
        "agent_id": str(audit_event.get("agent_id") or order.get("_agent_id") or audit_event.get("strategy_id") or order.get("_strategy_id") or ""),
        "trading_unit_id": str(audit_event.get("trading_unit_id") or order.get("_trading_unit_id") or ""),
        "source_order_id": str(audit_event.get("source_order_id") or order.get("_source_order_id") or ""),
        "inst_id": inst_id,
        "side": side,
        "pos_side": pos_side,
        "ord_type": ord_type,
        "expected_price": expected_price,
        "order_price": order_price,
        "order_qty": order_qty,
        "submit_ts": ts if event_type in {"exchange_ack", "error"} else "",
        "ack_ts": ts if event_type == "exchange_ack" else "",
        "fill_ts": ts if event_type == "fill" else "",
        "cancel_ts": ts if event_type == "cancel" else "",
        "latency_ms": execution_ledger_float(audit_event.get("latency_ms")),
        "fill_price": fill_price,
        "fill_qty": fill_qty,
        "fee": execution_ledger_float(detail.get("fee") or audit_event.get("fee")),
        "slippage_bps": execution_ledger_slippage_bps(side, expected_price or order_price, fill_price),
        "fill_ratio": execution_ledger_fill_ratio(fill_qty, order_qty),
        "close_pnl": execution_ledger_float(detail.get("pnl") or audit_event.get("close_pnl")),
        "okx_ord_id": str(detail.get("ord_id") or identity.get("ordId") or result.get("ordId") or payload.get("ordId") or ""),
        "okx_cl_ord_id": str(detail.get("cl_ord_id") or order.get("clOrdId") or identity.get("clOrdId") or result.get("clOrdId") or payload.get("clOrdId") or ""),
        "raw_status": raw_status,
        "error_category": execution_ledger_error_category(audit_event) if event_type == "error" else "",
        "raw_error": "",
        "audit_id": str(audit_event.get("id", "")),
        "audit_action": str(audit_event.get("action", "")),
        "request_id": str(audit_event.get("request_id") or result.get("request_id") or error_summary.get("request_id") or ""),
    }
    if event_type == "error":
        ledger_event["raw_error"] = scrub_secret_fields(
            {
                "error": audit_event.get("error", ""),
                "error_summary": error_summary,
                "raw_okx": audit_event.get("raw_okx", {}),
                "result": {key: result.get(key) for key in ["ok", "error", "status_code", "okx_code", "okx_msg", "data_errors"] if key in result},
            }
        )
    if str(audit_event.get("action", "")) in {"order_submitted", "order_submit_failed", "order_blocked"}:
        intent_event = dict(ledger_event)
        intent_event.update(
            {
                "event_type": "order_intent",
                "ack_ts": "",
                "fill_ts": "",
                "cancel_ts": "",
                "fill_price": 0.0,
                "fill_qty": 0.0,
                "fee": 0.0,
                "slippage_bps": 0.0,
                "fill_ratio": 0.0,
                "close_pnl": 0.0,
                "raw_status": "intent",
                "error_category": "",
                "raw_error": "",
            }
        )
        append_execution_ledger_event(intent_event)
    return append_execution_ledger_event(ledger_event)


def read_execution_ledger(limit: int = 300, event_type: str = "", trace_id: str = "") -> list[dict[str, Any]]:
    limit = max(0, min(int(limit), 5000))
    if limit <= 0:
        return []
    with EXECUTION_LEDGER_LOCK:
        rows = read_jsonl_tail(EXECUTION_LEDGER_PATH, max(limit * 5, limit))
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if event_type and str(row.get("event_type", "")) != event_type:
            continue
        if trace_id and str(row.get("trace_id", "")) != trace_id:
            continue
        filtered.append(row)
    return filtered[-limit:][::-1]


def execution_ledger_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    limit = bounded_int(params.get("limit", ["300"])[0], 300, 1, 5000)
    event_type = params.get("type", [""])[0].strip()
    trace_id = params.get("traceId", params.get("trace_id", [""]))[0].strip()
    rows = read_execution_ledger(limit, event_type=event_type, trace_id=trace_id)
    type_counts: dict[str, int] = {}
    error_counts: dict[str, int] = {}
    for row in rows:
        event_key = str(row.get("event_type") or "unknown")
        type_counts[event_key] = type_counts.get(event_key, 0) + 1
        if row.get("error_category"):
            error_key = str(row.get("error_category") or "unknown")
            error_counts[error_key] = error_counts.get(error_key, 0) + 1
    return {
        "ok": True,
        "generated_at": now_iso(),
        "journal_path": str(EXECUTION_LEDGER_PATH),
        "summary": {
            "events": len(rows),
            "type_counts": dict(sorted(type_counts.items())),
            "error_counts": dict(sorted(error_counts.items())),
            "latest_event_at": rows[0].get("event_ts", "") if rows else "",
        },
        "events": rows,
    }


def execution_ledger_source_order_meta(limit: int = 5000) -> dict[str, dict[str, Any]]:
    """Index strategy context by paper source_order_id from the execution ledger."""
    meta: dict[str, dict[str, Any]] = {}
    for row in reversed(read_execution_ledger(limit)):
        if not isinstance(row, dict):
            continue
        source_order_id = str(row.get("source_order_id", "")).strip()
        if not source_order_id:
            continue
        current = meta.setdefault(source_order_id, {})
        for key in ["strategy_id", "agent_id", "trading_unit_id", "inst_id", "side"]:
            value = str(row.get(key, "")).strip()
            if value and not current.get(key):
                current[key] = value
    return meta


def resolved_fill_attribution_context(
    event: dict[str, Any],
    state_by_key: dict[str, dict[str, Any]],
    ledger_meta_by_source: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    order_key = str(
        event.get("order_key")
        or order_event_key(str(event.get("paper_session_id", "")), str(event.get("order_id", "")))
    )
    source_order_id = str(event.get("source_order_id") or order_key).strip()
    state = state_by_key.get(order_key, {})
    ledger_meta = ledger_meta_by_source.get(source_order_id) or ledger_meta_by_source.get(order_key) or {}
    fallback = {**ledger_meta, **state}
    context = source_order_attribution_context(event, fallback)
    if not context.get("strategy_id") and state.get("strategy_attribution"):
        context = source_order_attribution_context(state, ledger_meta)
    strategy_id = context.get("strategy_id") or "unknown"
    unit = trading_unit_for_strategy(strategy_id)
    if not context.get("trading_unit_id") and unit:
        context["trading_unit_id"] = str(unit.get("id", ""))
        context["trading_unit_name"] = str(unit.get("display_name", ""))
    context["strategy_id"] = strategy_id
    context["agent_id"] = context.get("agent_id") or strategy_id
    context["source_order_id"] = source_order_id
    context["order_key"] = order_key
    context["attribution_source"] = (
        "order_journal"
        if event.get("strategy_id") or event.get("strategy_attribution")
        else "execution_ledger_join"
        if ledger_meta.get("strategy_id")
        else "order_state_join"
        if state.get("strategy_id") or state.get("strategy_attribution")
        else "unknown"
    )
    return context


def attribution_row_template(strategy_id: str, context: dict[str, Any], capital_snapshot: dict[str, Any]) -> dict[str, Any]:
    catalog = strategy_catalog_index()
    strategy = catalog.get(strategy_id, {})
    unit = trading_unit_for_strategy(strategy_id)
    agent_id = str(context.get("agent_id") or strategy_id)
    capital = capital_snapshot.get(agent_id, {}) if isinstance(capital_snapshot, dict) else {}
    return {
        "strategy_id": strategy_id,
        "agent_id": agent_id,
        "display_name": strategy.get("display_name", strategy_id),
        "style": strategy.get("style", "unknown"),
        "trading_unit_id": context.get("trading_unit_id") or unit.get("id", ""),
        "trading_unit_name": context.get("trading_unit_name") or unit.get("display_name", ""),
        "fill_count": 0,
        "close_fill_count": 0,
        "open_fill_count": 0,
        "win_count": 0,
        "loss_count": 0,
        "filled_qty": 0.0,
        "closed_qty": 0.0,
        "opened_qty": 0.0,
        "notional": 0.0,
        "commission": 0.0,
        "close_gross_pnl": 0.0,
        "close_fee": 0.0,
        "close_net_pnl": 0.0,
        "capital_snapshot_pnl": float_from_any(capital.get("cumulative_pnl")),
        "allocated_capital": float_from_any(capital.get("allocated_capital")),
        "cycles_active": int(float_from_any(capital.get("cycles_active"))),
        "under_review": bool(capital.get("under_review", False)),
        "last_fill_at": "",
        "attribution_sources": {},
    }


def finalize_attribution_rows(rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows.values():
        close_count = float_from_any(row.get("close_fill_count"))
        wins = float_from_any(row.get("win_count"))
        row["win_rate"] = wins / close_count if close_count > 0 else 0.0
        row["pnl_bps"] = (
            float_from_any(row.get("close_net_pnl")) / float_from_any(row.get("notional")) * 10000.0
            if float_from_any(row.get("notional")) > 1e-12
            else 0.0
        )
        row["attribution_sources"] = dict(sorted(row.get("attribution_sources", {}).items()))
        result.append(row)
    result.sort(key=lambda item: (abs(float_from_any(item.get("close_net_pnl"))), float_from_any(item.get("notional"))), reverse=True)
    return result


def fill_strategy_shares(event: dict[str, Any], context: dict[str, Any], state_by_key: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Return fractional strategy shares for one fill.

    New paper fills carry `strategy_attribution`; older fills may only have a
    single strategy from ExecutionLedger/order_state.  The return shape is
    always normalized and safe to multiply by PnL/notional.
    """
    order_key = str(context.get("order_key", ""))
    state = state_by_key.get(order_key, {})
    attribution = event.get("strategy_attribution") if isinstance(event.get("strategy_attribution"), list) else None
    if attribution is None and isinstance(state.get("strategy_attribution"), list):
        attribution = state.get("strategy_attribution")
    if attribution:
        return fill_strategy_allocations({"strategy_attribution": attribution}, {})
    return [{"strategy_id": context.get("strategy_id") or "unknown", "share": 1.0, "direction": "unknown"}]


def add_attribution_amounts(
    row: dict[str, Any],
    *,
    share: float,
    fill_qty: float,
    closed_qty: float,
    opened_qty: float,
    notional: float,
    commission: float,
    close_gross: float,
    close_fee: float,
    close_net: float,
    close_event: bool,
    source: str,
    event_ts: str,
) -> None:
    row["fill_count"] += share
    row["filled_qty"] += fill_qty * share
    row["closed_qty"] += closed_qty * share
    row["opened_qty"] += opened_qty * share
    row["notional"] += notional * share
    row["commission"] += commission * share
    row["close_gross_pnl"] += close_gross * share
    row["close_fee"] += close_fee * share
    row["close_net_pnl"] += close_net * share
    if close_event:
        row["close_fill_count"] += share
        if close_net > 0:
            row["win_count"] += share
        elif close_net < 0:
            row["loss_count"] += share
    else:
        row["open_fill_count"] += share
    row["attribution_sources"][source] = row["attribution_sources"].get(source, 0) + share
    row["last_fill_at"] = max(str(row.get("last_fill_at", "")), event_ts)


def agent_trade_attribution_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    """Rebuild strategy/agent PnL attribution from order -> fill -> close PnL.

    This is read-only and deliberately uses local journals.  It does not query
    OKX or mutate paper state.  The authoritative realized contribution is the
    `order.fill.close_net_pnl` written by the paper position book; missing
    strategy ids are backfilled from ExecutionLedger using source_order_id.
    """
    limit = bounded_int(params.get("limit", ["20000"])[0], 20000, 100, 50000)
    recent_limit = bounded_int(params.get("recent", ["200"])[0], 200, 0, 1000)
    events = read_order_journal(limit)
    state_by_key = {
        str(row.get("order_key", "")): row
        for row in reduce_order_states(events)
        if str(row.get("order_key", ""))
    }
    ledger_meta = execution_ledger_source_order_meta(max(5000, min(limit, 20000)))
    agent_state_path = LOG_DIR / "agent" / "state.json"
    agent_state = read_json_file(agent_state_path) if agent_state_path.exists() else {}
    capital_snapshot = {
        str(row.get("id", "")): row
        for row in agent_state.get("agents", [])
        if isinstance(row, dict) and row.get("id")
    } if isinstance(agent_state.get("agents"), list) else {}

    rows_by_strategy: dict[str, dict[str, Any]] = {}
    rows_by_agent: dict[str, dict[str, Any]] = {}
    recent_fills: list[dict[str, Any]] = []
    total_close_net_pnl = 0.0
    attributed_close_net_pnl = 0.0
    unknown_close_net_pnl = 0.0
    fill_count = 0
    close_fill_count = 0
    unknown_fill_count = 0

    for event in events:
        if not isinstance(event, dict) or str(event.get("type", "")) != "order.fill":
            continue
        fill_qty = float_from_any(event.get("filled_qty"))
        if fill_qty <= 1e-12:
            continue
        fill_count += 1
        context = resolved_fill_attribution_context(event, state_by_key, ledger_meta)
        close_net = float_from_any(event.get("close_net_pnl"))
        close_gross = float_from_any(event.get("close_gross_pnl"))
        close_fee = float_from_any(event.get("close_fee"))
        closed_qty = float_from_any(event.get("closed_qty"))
        opened_qty = float_from_any(event.get("opened_qty"))
        fill_price = float_from_any(event.get("fill_price"), float_from_any(event.get("avg_price")))
        notional = fill_qty * fill_price
        commission = float_from_any(event.get("commission"))
        close_event = closed_qty > 1e-12 or abs(close_net) > 1e-12
        allocations = fill_strategy_shares(event, context, state_by_key)
        has_known_allocation = any(str(item.get("strategy_id") or "unknown") != "unknown" for item in allocations)
        if close_event:
            close_fill_count += 1
            total_close_net_pnl += close_net
            if has_known_allocation:
                attributed_close_net_pnl += close_net
            else:
                unknown_close_net_pnl += close_net
        if not has_known_allocation:
            unknown_fill_count += 1
        source = str(context.get("attribution_source", "unknown"))

        for allocation in allocations:
            share = max(0.0, float_from_any(allocation.get("share")))
            if share <= 1e-12:
                continue
            strategy_id = str(allocation.get("strategy_id") or context.get("strategy_id") or "unknown")
            alloc_context = source_order_attribution_context({"strategy_id": strategy_id}, context)
            agent_id = str(alloc_context.get("agent_id") or strategy_id)

            row = rows_by_strategy.setdefault(
                strategy_id,
                attribution_row_template(strategy_id, alloc_context, capital_snapshot),
            )
            row["agent_id"] = agent_id
            add_attribution_amounts(
                row,
                share=share,
                fill_qty=fill_qty,
                closed_qty=closed_qty,
                opened_qty=opened_qty,
                notional=notional,
                commission=commission,
                close_gross=close_gross,
                close_fee=close_fee,
                close_net=close_net,
                close_event=close_event,
                source=source,
                event_ts=str(event.get("ts", "")),
            )

            agent_row = rows_by_agent.setdefault(
                agent_id,
                {
                    **attribution_row_template(agent_id, {**alloc_context, "agent_id": agent_id}, capital_snapshot),
                    "strategy_ids": set(),
                },
            )
            agent_row["strategy_ids"].add(strategy_id)
            add_attribution_amounts(
                agent_row,
                share=share,
                fill_qty=fill_qty,
                closed_qty=closed_qty,
                opened_qty=opened_qty,
                notional=notional,
                commission=commission,
                close_gross=close_gross,
                close_fee=close_fee,
                close_net=close_net,
                close_event=close_event,
                source=source,
                event_ts=str(event.get("ts", "")),
            )

        if recent_limit > 0:
            primary_strategy = str(context.get("strategy_id") or allocations[0].get("strategy_id") if allocations else "unknown")
            recent_fills.append(
                {
                    "ts": event.get("ts", ""),
                    "source_order_id": context.get("source_order_id", ""),
                    "order_id": event.get("order_id", ""),
                    "inst_id": event.get("inst_id", ""),
                    "side": event.get("side", ""),
                    "strategy_id": primary_strategy or "unknown",
                    "agent_id": context.get("agent_id") or primary_strategy or "unknown",
                    "trading_unit_id": context.get("trading_unit_id", ""),
                    "filled_qty": fill_qty,
                    "fill_price": fill_price,
                    "closed_qty": closed_qty,
                    "opened_qty": opened_qty,
                    "close_net_pnl": close_net,
                    "position_effect": event.get("position_effect", ""),
                    "attribution_source": source,
                }
            )

    for agent_row in rows_by_agent.values():
        strategies = agent_row.pop("strategy_ids", set())
        agent_row["strategy_ids"] = sorted(str(item) for item in strategies)

    by_strategy = finalize_attribution_rows(rows_by_strategy)
    by_agent = finalize_attribution_rows(rows_by_agent)
    recent_fills.sort(key=lambda item: str(item.get("ts", "")), reverse=True)

    return {
        "ok": True,
        "generated_at": now_iso(),
        "source": {
            "order_journal_path": str(ORDER_JOURNAL_PATH),
            "execution_ledger_path": str(EXECUTION_LEDGER_PATH),
            "agent_state_path": str(agent_state_path),
            "limit": limit,
        },
        "summary": {
            "order_events_scanned": len(events),
            "fill_count": fill_count,
            "close_fill_count": close_fill_count,
            "unknown_fill_count": unknown_fill_count,
            "total_close_net_pnl": total_close_net_pnl,
            "attributed_close_net_pnl": attributed_close_net_pnl,
            "unknown_close_net_pnl": unknown_close_net_pnl,
            "strategy_count": len(by_strategy),
            "agent_count": len(by_agent),
            "method": "order_journal.order.fill.close_net_pnl joined with ExecutionLedger by source_order_id",
        },
        "by_strategy": by_strategy,
        "by_agent": by_agent,
        "recent_fills": recent_fills[:recent_limit],
    }


def append_okx_audit(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    BROKER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    event = {
        "id": f"okx-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}-{uuid4().hex[:8]}",
        "ts": now_iso(),
        "action": action,
        **scrub_secret_fields(payload),
    }
    with OKX_AUDIT_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    try:
        append_execution_ledger_from_okx_audit(event)
    except Exception as exc:
        try:
            append_execution_ledger_event(
                {
                    "trace_id": event.get("id", uuid4().hex),
                    "event_type": "error",
                    "event_ts": now_iso(),
                    "strategy_id": "",
                    "trading_unit_id": "",
                    "source_order_id": str(event.get("source_order_id", "")),
                    "inst_id": "",
                    "side": "",
                    "pos_side": "",
                    "ord_type": "",
                    "expected_price": 0.0,
                    "order_price": 0.0,
                    "order_qty": 0.0,
                    "submit_ts": "",
                    "ack_ts": "",
                    "fill_ts": "",
                    "cancel_ts": "",
                    "latency_ms": 0.0,
                    "fill_price": 0.0,
                    "fill_qty": 0.0,
                    "fee": 0.0,
                    "slippage_bps": 0.0,
                    "fill_ratio": 0.0,
                    "close_pnl": 0.0,
                    "okx_ord_id": "",
                    "okx_cl_ord_id": "",
                    "raw_status": "ledger_bridge_failed",
                    "error_category": "ledger_bridge",
                    "raw_error": {"error": str(exc), "audit_id": event.get("id", ""), "audit_action": action},
                }
            )
        except Exception:
            pass
    return event


def read_okx_audit(limit: int = 100) -> list[dict[str, Any]]:
    if not OKX_AUDIT_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    with OKX_AUDIT_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-max(0, limit):][::-1]


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


def now_iso_millis() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def ensure_agent_session_dir() -> None:
    AGENT_SESSION_DIR.mkdir(parents=True, exist_ok=True)


def safe_session_id(session_id: str) -> str:
    value = session_id.strip()
    if not SESSION_ID_RE.fullmatch(value):
        raise ValueError("无效的会话 ID")
    return value


def agent_session_path(session_id: str) -> Path:
    return AGENT_SESSION_DIR / f"{safe_session_id(session_id)}.json"


def default_agent_session(provider: str = DEFAULT_AGENT_PROVIDER, model: str = DEFAULT_AGENT_MODEL) -> dict[str, Any]:
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
                "provider": session.get("provider", DEFAULT_AGENT_PROVIDER),
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
            # 跳过未注册的配置键（如新增的 optimizer.type / capital.* / regime.*），
            # 避免因 CONFIG_KEYS 滞后于 default.cfg 而阻断 paper runner。
            continue
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
        "history.bar",
        "history.start",
        "history.end",
        "history.max_pages",
        "strategy.donchian.lookback",
        "strategy.ma_cross.fast_window",
        "strategy.ma_cross.slow_window",
        "strategy.macd.fast_alpha",
        "strategy.macd.slow_alpha",
        "strategy.macd.signal_alpha",
        "strategy.ema_slope.alpha",
        "strategy.ema_slope.min_slope",
        "strategy.keltner.alpha",
    "strategy.keltner.multiplier",
    "strategy.volume_spike.alpha",
    "strategy.volume_spike.multiplier",
    "strategy.micro_scalper.min_return",
    "strategy.micro_scalper.min_body_ratio",
    "strategy.spread_capture.alpha",
    "strategy.spread_capture.threshold",
    "strategy.order_flow.volume_alpha",
    "strategy.order_flow.imbalance_threshold",
    "strategy.inventory_skew.neutral_band",
    "strategy.bollinger.window",
        "strategy.bollinger.band_width",
        "strategy.rsi.window",
        "strategy.rsi.oversold",
        "strategy.rsi.overbought",
        "strategy.zscore.window",
        "strategy.zscore.threshold",
        "print_cycles",
        "print_event_stream",
        "metrics.drawdown_stride",
        "initial_cash",
        "optimizer.max_single_weight",
        "optimizer.max_gross",
        "risk.max_single_weight",
        "risk.max_gross",
        "risk.max_order_notional",
        "risk.kill_switch",
        "execution.min_rebalance_delta",
        "execution.max_participation_rate",
        "execution.maker_offset_bps",
        "execution.maker_fee_bps",
        "execution.max_expected_cost_bps",
        "execution.pending_order_ttl_bars",
        "execution.derivatives.enabled",
        "execution.derivatives.inst_type",
        "execution.derivatives.margin_mode",
        "execution.derivatives.position_mode",
        "execution.derivatives.max_exchange_leverage",
        "execution.derivatives.max_effective_leverage",
        "execution.derivatives.max_unit_effective_leverage",
        "execution.trade_unit.base_notional_usdt",
        "execution.trade_unit.agent_leverage_enabled",
        "execution.trade_unit.agent_max_step",
    ]
    lines = ["# generated by KaTrade local platform"]
    written = set()
    for key in ordered:
        if key in current:
            lines.append(f"{key}={current[key]}")
            written.add(key)
    # R13: 保留 ordered 列表中未包含的 key，避免静默丢弃
    for key in sorted(current.keys()):
        if key not in written:
            lines.append(f"{key}={current[key]}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def backup_config_file(path: Path = DEFAULT_CONFIG) -> str:
    if not path.exists():
        return ""
    CONFIG_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    backup = CONFIG_BACKUP_DIR / f"{path.stem}-{stamp}-{uuid4().hex[:8]}{path.suffix}"
    shutil.copy2(path, backup)
    return str(backup)


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


def read_events(
    limit: int = 200,
    config: Optional[dict[str, str]] = None,
    event_log_path: Optional[Path] = None,
) -> list[dict[str, Any]]:
    config = config or parse_config()
    event_log_path = event_log_path or resolve_runtime_path(config.get("event_log_path", "logs/events.jsonl"))
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


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_jsonl_tail(path: Path, limit: int = 100) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def file_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "updated_at": "",
            "updated_at_utc": "",
            "age_seconds": None,
        }
    try:
        stat = path.stat()
    except OSError:
        return {
            "path": str(path),
            "exists": False,
            "updated_at": "",
            "updated_at_utc": "",
            "age_seconds": None,
        }
    updated_at_utc = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
    return {
        "path": str(path),
        "exists": True,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00", time.gmtime(stat.st_mtime + 8 * 60 * 60)),
        "updated_at_utc": updated_at_utc.isoformat(),
        "age_seconds": max(0.0, time.time() - stat.st_mtime),
    }


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


def historyd_get_json(path: str, timeout: float = 12.0) -> dict[str, Any]:
    config = parse_config()
    url = config.get("history.server_url", "http://127.0.0.1:8790").rstrip("/")
    if not url:
        raise RuntimeError("未配置 history.server_url")
    with urllib.request.urlopen(url + path, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    payload["history_server_url"] = url
    return payload


def historyd_post_json(path: str, body: dict[str, Any], timeout: float = 12.0) -> dict[str, Any]:
    config = parse_config()
    url = config.get("history.server_url", "http://127.0.0.1:8790").rstrip("/")
    if not url:
        raise RuntimeError("未配置 history.server_url")
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url + path,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    payload["history_server_url"] = url
    return payload


def historyd_okx_candles_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    query = urlencode({key: values[0] for key, values in params.items() if values})
    path = "/api/okx/candles" + (f"?{query}" if query else "")
    try:
        payload = historyd_get_json(path, timeout=18.0)
        payload["source"] = "historyd"
        return payload
    except Exception as exc:
        fallback = okx_candles_payload(params)
        fallback["source"] = "platform_direct"
        fallback["historyd_error"] = str(exc)
        fallback["warning"] = "historyd 不可用，已降级为平台直连 OKX；历史分页能力受限。"
        return fallback


def historyd_okx_tickers_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    try:
        payload = historyd_get_json("/api/okx/tickers", timeout=8.0)
        payload["source"] = "historyd"
        return payload
    except Exception as exc:
        fallback = okx_tickers_payload(params)
        fallback["source"] = "platform_direct"
        fallback["historyd_error"] = str(exc)
        fallback["warning"] = "historyd 不可用，已降级为平台直连 OKX。"
        return fallback


def historyd_okx_series_payload() -> dict[str, Any]:
    try:
        payload = historyd_get_json("/api/okx/series", timeout=8.0)
        payload["source"] = "historyd"
        return payload
    except Exception as exc:
        return {"ok": False, "error": str(exc), "source": "historyd"}


def historyd_okx_backfill_status_payload() -> dict[str, Any]:
    try:
        payload = historyd_get_json("/api/okx/backfill", timeout=8.0)
        payload["source"] = "historyd"
        return payload
    except Exception as exc:
        return {"ok": False, "error": str(exc), "source": "historyd"}


def historyd_okx_backfill_start_payload(body: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = historyd_post_json("/api/okx/backfill", body, timeout=8.0)
        payload["source"] = "historyd"
        return payload
    except Exception as exc:
        return {"ok": False, "error": str(exc), "source": "historyd"}


def historyd_okx_backfill_cancel_payload(body: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = historyd_post_json("/api/okx/backfill/cancel", body, timeout=8.0)
        payload["source"] = "historyd"
        return payload
    except Exception as exc:
        return {"ok": False, "error": str(exc), "source": "historyd"}


def epoch_ms_from_text(value: str) -> int:
    text = value.strip()
    if not text:
        raise ValueError("empty timestamp")
    if text.isdigit():
        raw = int(text)
        return raw if raw > 10_000_000_000 else raw * 1000
    normalized = text.replace("Z", "+00:00")
    if "T" not in normalized and " " in normalized:
        normalized = normalized.replace(" ", "T", 1)
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def text_from_epoch_ms(epoch_ms: int) -> str:
    dt = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def gold_source_path() -> Path:
    value = get_local_setting("KATRADE_GOLD_1M_PATH", "")
    path = Path(value).expanduser() if value else GOLD_1M_DEFAULT_PATH
    return path if path.is_absolute() else ROOT / path


def load_gold_csv_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "open", "high", "low", "close"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError("gold csv missing fields: " + ", ".join(sorted(missing)))
        for row in reader:
            rows.append(
                {
                    "t": epoch_ms_from_text(row.get("timestamp", "")),
                    "o": float(row.get("open", "0")),
                    "h": float(row.get("high", "0")),
                    "l": float(row.get("low", "0")),
                    "c": float(row.get("close", "0")),
                    "v": float(row.get("volume", "0") or "0"),
                }
            )
    rows.sort(key=lambda item: item["t"])
    return rows


GOLD_CSV_CACHE: dict[str, Any] = {"path": "", "mtime": 0.0, "rows": [], "times": []}


def gold_csv_rows(path: Path) -> list[dict[str, Any]]:
    mtime = path.stat().st_mtime
    if GOLD_CSV_CACHE["path"] != str(path) or GOLD_CSV_CACHE["mtime"] != mtime:
        rows = load_gold_csv_rows(path)
        GOLD_CSV_CACHE["path"] = str(path)
        GOLD_CSV_CACHE["mtime"] = mtime
        GOLD_CSV_CACHE["rows"] = rows
        GOLD_CSV_CACHE["times"] = [int(row["t"]) for row in rows]
    return GOLD_CSV_CACHE["rows"]


def aggregate_csv_gold(rows: list[dict[str, Any]], start_ms: int, end_ms: int, width: int) -> dict[str, Any]:
    if not rows:
        raise ValueError("gold csv has no rows")
    source_start = int(rows[0]["t"])
    source_end = int(rows[-1]["t"])
    start_ms = max(source_start, min(start_ms, source_end))
    end_ms = max(source_start, min(end_ms, source_end))
    if end_ms < start_ms:
        start_ms, end_ms = end_ms, start_ms
    times = GOLD_CSV_CACHE.get("times") or [int(row["t"]) for row in rows]
    left = bisect_left(times, start_ms)
    right = bisect_right(times, end_ms)
    selected = rows[left:right]
    target_points = max(400, min(width, 2400))
    bucket_size = max(1, math.ceil(max(len(selected), 1) / target_points))
    bars: list[dict[str, Any]] = []
    for index in range(0, len(selected), bucket_size):
        bucket = selected[index : index + bucket_size]
        first = bucket[0]
        last = bucket[-1]
        bars.append(
            {
                "t": first["t"],
                "o": round(first["o"], 3),
                "h": round(max(item["h"] for item in bucket), 3),
                "l": round(min(item["l"] for item in bucket), 3),
                "c": round(last["c"], 3),
                "v": round(sum(float(item["v"]) for item in bucket), 2),
                "n": len(bucket),
            }
        )
    return {
        "source": "csv",
        "contract": "XAUUSD.OTC",
        "name": "黄金 1分钟K线",
        "start": source_start,
        "end": source_end,
        "rows": len(rows),
        "visible_rows": len(selected),
        "bucket_minutes": bucket_size,
        "bars": bars,
        "warning": "",
    }


def missing_gold_market_payload() -> dict[str, Any]:
    path = gold_source_path()
    message = f"未配置真实黄金 1m CSV。请设置 KATRADE_GOLD_1M_PATH，或放置文件到 {path}。"
    return {
        "ok": False,
        "source": "missing_real_csv",
        "path": str(path),
        "contract": "XAUUSD.OTC",
        "name": "黄金 1分钟K线",
        "start": 0,
        "end": 0,
        "start_text": "",
        "end_text": "",
        "rows": 0,
        "visible_rows": 0,
        "bucket_minutes": 0,
        "bars": [],
        "warning": message,
        "error": message,
    }


def gold_market_summary() -> dict[str, Any]:
    path = gold_source_path()
    if path.exists():
        rows = gold_csv_rows(path)
        if not rows:
            raise ValueError("gold csv has no rows")
        return {
            "source": "csv",
            "path": str(path),
            "contract": "XAUUSD.OTC",
            "name": "黄金 1分钟K线",
            "start": int(rows[0]["t"]),
            "end": int(rows[-1]["t"]),
            "start_text": text_from_epoch_ms(int(rows[0]["t"])),
            "end_text": text_from_epoch_ms(int(rows[-1]["t"])),
            "rows": len(rows),
            "warning": "",
        }
    return missing_gold_market_payload()


def gold_market_bars(params: dict[str, list[str]]) -> dict[str, Any]:
    summary = gold_market_summary()
    if not summary.get("ok", True):
        return summary
    start_ms = int(params.get("start", [summary["start"]])[0])
    end_ms = int(params.get("end", [summary["end"]])[0])
    width = int(params.get("width", ["1400"])[0])
    width = max(400, min(width, 2400))
    path = gold_source_path()
    payload = aggregate_csv_gold(gold_csv_rows(path), start_ms, end_ms, width)
    payload["start_text"] = text_from_epoch_ms(payload["start"])
    payload["end_text"] = text_from_epoch_ms(payload["end"])
    return payload


def read_report_json(
    config: Optional[dict[str, str]] = None,
    report_json_path: Optional[Path] = None,
) -> dict[str, Any]:
    config = config or parse_config()
    path = report_json_path or resolve_runtime_path(config.get("report_json_path", "logs/last_report.json"))
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def git_code_ref() -> dict[str, Any]:
    head = run_command(["git", "rev-parse", "--short", "HEAD"], timeout=10)
    dirty = run_command(["git", "status", "--porcelain"], timeout=10)
    return {
        "commit": head["output"].strip() if head["returncode"] == 0 else "",
        "dirty": bool(dirty["output"].strip()) if dirty["returncode"] == 0 else True,
    }


def extract_strategy_params(config: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in sorted(config.items()) if key.startswith("strategy.")}


def metrics_from_report(report: dict[str, Any], output: str = "") -> dict[str, Any]:
    summary = dict(report.get("summary") or parse_summary())
    equity_curve = report.get("equity_curve") or parse_equity_curve(output)
    if equity_curve:
        exposures = [abs(float(point.get("gross_exposure", point.get("gross", 0.0)) or 0.0)) for point in equity_curve]
        summary["avg_gross_exposure"] = sum(exposures) / max(len(exposures), 1)
        summary["max_gross_exposure"] = max(exposures)
    cycles = report.get("cycles") or []
    total_signals = 0
    strategy_counts: dict[str, int] = {}
    for cycle in cycles:
        for signal in cycle.get("signals", []):
            total_signals += 1
            strategy_id = str(signal.get("strategy_id", "unknown"))
            strategy_counts[strategy_id] = strategy_counts.get(strategy_id, 0) + 1
    summary["total_signals"] = total_signals
    summary["strategy_count"] = len(strategy_counts)
    summary["strategy_signal_counts"] = dict(sorted(strategy_counts.items()))
    if summary.get("final_equity") and summary.get("total_commission") is not None:
        final_equity = max(float(summary["final_equity"]), 1e-9)
        summary["commission_bps_of_equity"] = float(summary["total_commission"]) / final_equity * 10000.0
    return summary


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


NON_PRODUCTION_DATA_TOKENS = {"demo", "generated", "synthetic", "sample", "mock", "placeholder", "fake"}


def non_production_source_reason(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = text.lower().replace("\\", "/")
    for token in NON_PRODUCTION_DATA_TOKENS:
        if token in normalized:
            return f"来源包含非生产标记 `{token}`。"
    return ""


def runtime_path_is_sample(path: Path) -> bool:
    normalized = root_relative(path).lower().replace("\\", "/")
    return (
        normalized.startswith("data/sample")
        or "/sample" in normalized
        or Path(normalized).name.startswith("sample")
    )


def paper_mode_requires_tick_stream(settings_or_mode: Any) -> bool:
    """Modes that must be backed by traceable OKX tick/stream data."""
    if isinstance(settings_or_mode, dict):
        mode = str(settings_or_mode.get("mode", "realtime")).lower()
    else:
        mode = str(settings_or_mode or "realtime").lower()
    return mode in {"tick", "realtime", "live"}


def data_provenance_payload(
    settings: Optional[dict[str, Any]] = None,
    report: Optional[dict[str, Any]] = None,
    state: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Classify local data sources so fake/sample feeds cannot reach execution.

    Sample CSVs are still valid for tests and backtests.  The hard execution
    gate only applies to live paper ticks and the C++ quality source used by
    automated OKX simulated-order submission.
    """
    config = parse_config()
    state = state or read_paper_state()
    settings = settings or (state.get("settings", {}) if isinstance(state.get("settings"), dict) else {})
    report = report or read_latest_paper_report()
    live = state.get("live", {}) if isinstance(state.get("live"), dict) else {}
    replay_path = resolve_runtime_path(config.get("replay_path", "data/sample_bars.csv"))
    replay_sample = runtime_path_is_sample(replay_path)

    cxx_quality = cxx_market_quality_guard(settings)
    cxx_source = str(cxx_quality.get("source", ""))
    cxx_reason = non_production_source_reason(cxx_source)
    tick_sources: list[dict[str, Any]] = []
    bad_tick_sources: list[str] = []
    mode = str(settings.get("mode", "realtime")).lower().strip()
    auto_enabled = bool_setting_from_any(settings.get("okx_auto_submit"), False)
    wanted_instruments = {
        str(item).upper().strip()
        for item in settings.get("instruments", []) or []
        if str(item).strip()
    }
    for inst_id, row in (live.get("tick_data_source_by_inst", {}) or {}).items():
        if not isinstance(row, dict):
            continue
        normalized_inst = str(inst_id).upper().strip()
        source = str(row.get("source", ""))
        reason = non_production_source_reason(source)
        item = {
            "inst_id": str(inst_id),
            "tracked": (not wanted_instruments) or normalized_inst in wanted_instruments,
            "source": source,
            "stream_status": row.get("stream_status", ""),
            "last_trade_at": row.get("last_trade_at", ""),
            "last_trade_age_seconds": row.get("last_trade_age_seconds"),
            "execution_allowed": not reason,
            "reason": reason,
        }
        tick_sources.append(item)
        if reason:
            bad_tick_sources.append(f"{inst_id}:{source}")
    traced_instruments = {
        str(item.get("inst_id", "")).upper().strip()
        for item in tick_sources
        if item.get("tracked")
    }
    missing_tick_sources = sorted(wanted_instruments - traced_instruments) if wanted_instruments else []
    traceability_required = paper_mode_requires_tick_stream(mode) and auto_enabled
    traceability_ok = (not traceability_required) or (bool(traced_instruments) and not missing_tick_sources)

    gold_summary = gold_market_summary()
    checks = [
        paper_health_check(
            "回测 CSV 来源",
            not replay_sample,
            "warn",
            f"当前 replay_path={root_relative(replay_path)} 是示例数据，仅允许用于测试/回测。"
            if replay_sample
            else f"当前 replay_path={root_relative(replay_path)}。",
            path=str(replay_path),
            execution_blocking=False,
        ),
        paper_health_check(
            "黄金真实数据",
            bool(gold_summary.get("ok", True)),
            "warn",
            gold_summary.get("warning") or "黄金视图使用真实 CSV。",
            path=gold_summary.get("path", ""),
            execution_blocking=False,
        ),
        paper_health_check(
            "逐笔来源可追溯",
            traceability_ok,
            "halt",
            "自动提交逐笔来源已覆盖目标品种。"
            if traceability_required and traceability_ok
            else "自动提交未启用或非逐笔模式，来源追溯不阻断执行。"
            if traceability_ok
            else "自动提交缺少可追溯逐笔来源：" + ", ".join(missing_tick_sources or sorted(wanted_instruments) or ["无目标品种"]),
            required=traceability_required,
            mode=mode,
            missing_sources=missing_tick_sources,
            execution_blocking=True,
        ),
        paper_health_check(
            "逐笔行情来源",
            not bad_tick_sources,
            "halt",
            "最近虚拟盘 tick 来源均未命中 demo/sample/synthetic 标记。"
            if not bad_tick_sources
            else "发现非生产逐笔行情来源：" + ", ".join(bad_tick_sources[:6]),
            bad_sources=bad_tick_sources,
            execution_blocking=True,
        ),
        paper_health_check(
            "C++ 行情质量来源",
            not cxx_reason,
            "halt",
            f"C++ 行情质量源={cxx_source or '-'}。"
            if not cxx_reason
            else f"C++ 行情质量源={cxx_source}，{cxx_reason}",
            source=cxx_source,
            source_matches_market_stream=bool(cxx_quality.get("source_matches_market_stream")),
            execution_blocking=True,
        ),
    ]
    execution_checks = [item for item in checks if item.get("execution_blocking")]
    execution_ready = all(item.get("ok") for item in execution_checks)
    status = paper_health_overall(checks)
    reason = "数据来源门禁通过，自动交易未发现 sample/demo/synthetic 来源。" if execution_ready else next(
        (item.get("message", "") for item in execution_checks if not item.get("ok")),
        "数据来源门禁未通过。",
    )
    return {
        "ok": status != "halt",
        "execution_ready": execution_ready,
        "generated_at": now_iso(),
        "status": status,
        "reason": reason,
        "summary": {
            "replay_path": root_relative(replay_path),
            "replay_sample": replay_sample,
            "gold_source": gold_summary.get("source", ""),
            "gold_ok": bool(gold_summary.get("ok", True)),
            "tick_source_count": len(tick_sources),
            "tick_source_traceable": traceability_ok,
            "missing_tick_sources": missing_tick_sources,
            "bad_tick_source_count": len(bad_tick_sources),
            "cxx_source": cxx_source,
            "cxx_source_matches_market_stream": bool(cxx_quality.get("source_matches_market_stream")),
            "execution_ready": execution_ready,
        },
        "checks": checks,
        "execution_checks": execution_checks,
        "tick_sources": tick_sources,
        "gold": gold_summary,
    }


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
        "data_profile": (not light and data_profile()) or {},
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


def archive_experiment(
    run: dict[str, Any],
    run_metadata: dict[str, Any],
    extra_metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
    experiment_id = f"exp-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}-{uuid4().hex[:8]}"
    destination = EXPERIMENT_DIR / experiment_id
    destination.mkdir(parents=True, exist_ok=True)

    config = parse_config()
    report = read_report_json()
    profile = data_profile()
    metrics = metrics_from_report(report, run.get("output", ""))
    metadata = {
        "id": experiment_id,
        "run_id": run_metadata.get("id", ""),
        "created_at": now_iso(),
        "ok": bool(run.get("ok")),
        "stage": run.get("stage", ""),
        "mode": "backtest",
        "config_hash": json_hash(config),
        "data_hash": json_hash(profile),
        "code_ref": git_code_ref(),
        "strategy_ids": [item.strip() for item in config.get("strategy.enabled", "").split(",") if item.strip()],
        "strategy_params": extract_strategy_params(config),
        "summary": metrics,
        "data_profile": profile,
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    (destination / "experiment.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (destination / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (destination / "stdout.txt").write_text(run.get("output", ""), encoding="utf-8")

    for source, name in [
        (resolve_runtime_path(config.get("report_json_path", "logs/last_report.json")), "report.json"),
        (resolve_runtime_path(config.get("event_log_path", "logs/events.jsonl")), "events.jsonl"),
        (DEFAULT_CONFIG, "config.cfg"),
    ]:
        if source.exists():
            shutil.copyfile(source, destination / name)
    return metadata


def list_experiments() -> list[dict[str, Any]]:
    if not EXPERIMENT_DIR.exists():
        return []
    experiments: list[dict[str, Any]] = []
    for path in sorted(EXPERIMENT_DIR.iterdir(), reverse=True):
        metadata_path = path / "experiment.json"
        if not metadata_path.exists():
            continue
        try:
            experiments.append(json.loads(metadata_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return experiments


def safe_experiment_id(experiment_id: str) -> str:
    value = experiment_id.strip()
    if not EXPERIMENT_ID_RE.fullmatch(value):
        raise ValueError("无效的实验 ID")
    return value


def load_experiment_archive(experiment_id: str) -> dict[str, Any]:
    directory = EXPERIMENT_DIR / safe_experiment_id(experiment_id)
    if not directory.exists():
        raise ValueError("找不到实验档案")

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
    output_path = directory / "stdout.txt"
    if output_path.exists():
        output = output_path.read_text(encoding="utf-8")

    return {
        "metadata": read_json(directory / "experiment.json"),
        "metrics": read_json(directory / "metrics.json"),
        "report": read_json(directory / "report.json"),
        "events": events,
        "output": output,
    }


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


def compact_run_archive_rows(runs: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs[:limit]:
        if not isinstance(run, dict):
            continue
        rows.append(
            {
                "id": run.get("id", ""),
                "created_at": run.get("created_at", ""),
                "ok": bool(run.get("ok")),
                "stage": run.get("stage", ""),
                "summary": copy.deepcopy(run.get("summary", {})) if isinstance(run.get("summary"), dict) else {},
            }
        )
    return rows


def compact_experiment_archive_rows(experiments: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for experiment in experiments[:limit]:
        if not isinstance(experiment, dict):
            continue
        rows.append(
            {
                "id": experiment.get("id", ""),
                "run_id": experiment.get("run_id", ""),
                "created_at": experiment.get("created_at", ""),
                "ok": bool(experiment.get("ok")),
                "stage": experiment.get("stage", ""),
                "mode": experiment.get("mode", ""),
                "code_ref": copy.deepcopy(experiment.get("code_ref", {})) if isinstance(experiment.get("code_ref"), dict) else {},
                "strategy_ids": copy.deepcopy(experiment.get("strategy_ids", [])) if isinstance(experiment.get("strategy_ids"), list) else [],
                "sweep": copy.deepcopy(experiment.get("sweep", {})) if isinstance(experiment.get("sweep"), dict) else {},
                "summary": copy.deepcopy(experiment.get("summary", {})) if isinstance(experiment.get("summary"), dict) else {},
                "crypto": copy.deepcopy(experiment.get("crypto", {})) if isinstance(experiment.get("crypto"), dict) else {},
            }
        )
    return rows


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


def run_quality_check(name: str, ok: bool, severity: str, message: str, value: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "severity": severity,
        "message": message,
        "value": value,
    }


def run_quality_checks(run: dict[str, Any]) -> list[dict[str, Any]]:
    summary = run.get("summary", {}) or {}
    config = run.get("config", {}) or {}
    checks: list[dict[str, Any]] = [
        run_quality_check(
            "运行状态",
            bool(run.get("ok")),
            "ok" if run.get("ok") else "halt",
            "回测成功" if run.get("ok") else f"回测失败 stage={run.get('stage', '-')}",
        )
    ]

    cycles = int(summary.get("cycles", 0) or 0)
    checks.append(
        run_quality_check(
            "周期数",
            cycles > 0,
            "ok" if cycles > 0 else "halt",
            f"{cycles} 个周期",
            cycles,
        )
    )

    final_equity = float(summary.get("final_equity", 0.0) or 0.0)
    initial_cash = config_float(config, "initial_cash", 1_000_000.0)
    checks.append(
        run_quality_check(
            "最终权益",
            final_equity > 0.0,
            "ok" if final_equity > 0.0 else "halt",
            f"{final_equity:.2f}",
            final_equity,
        )
    )

    total_return = float(summary.get("total_return", 0.0) or 0.0)
    checks.append(
        run_quality_check(
            "收益偏离",
            final_equity > initial_cash * 0.5,
            "ok" if final_equity > initial_cash * 0.5 else "halt",
            f"return={total_return:.2%}, initial_cash={initial_cash:.2f}",
            total_return,
        )
    )

    max_drawdown = float(summary.get("max_drawdown", 0.0) or 0.0)
    checks.append(
        run_quality_check(
            "最大回撤",
            max_drawdown < 0.20,
            "ok" if max_drawdown < 0.20 else "warn",
            f"{max_drawdown:.2%}",
            max_drawdown,
        )
    )

    max_gross = float(summary.get("max_gross_exposure", 0.0) or 0.0)
    gross_limit = config_float(config, "risk.max_gross", 0.80)
    checks.append(
        run_quality_check(
            "最大总敞口",
            max_gross <= gross_limit + 1e-9,
            "ok" if max_gross <= gross_limit + 1e-9 else "warn",
            f"max={max_gross:.2%}, limit={gross_limit:.2%}",
            max_gross,
        )
    )

    average_cost = float(summary.get("average_cost_bps", 0.0) or 0.0)
    checks.append(
        run_quality_check(
            "平均成本",
            average_cost <= 25.0,
            "ok" if average_cost <= 25.0 else "warn",
            f"{average_cost:.2f} bps",
            average_cost,
        )
    )

    event_count = int(summary.get("event_count", 0) or 0)
    checks.append(
        run_quality_check(
            "事件流",
            event_count >= cycles,
            "ok" if event_count >= cycles else "warn",
            f"{event_count} events / {cycles} cycles",
            event_count,
        )
    )
    return checks


def run_metric_delta(latest: dict[str, Any], baseline: dict[str, Any], key: str) -> dict[str, Any]:
    latest_value = float((latest.get("summary", {}) or {}).get(key, 0.0) or 0.0)
    baseline_value = float((baseline.get("summary", {}) or {}).get(key, 0.0) or 0.0)
    return {
        "metric": key,
        "latest": latest_value,
        "baseline": baseline_value,
        "delta": latest_value - baseline_value,
    }


def runs_quality_payload() -> dict[str, Any]:
    runs = list_runs()
    if not runs:
        return {"ok": True, "status": "empty", "latest": {}, "checks": [], "comparison": [], "runs": []}
    latest = runs[0]
    checks = run_quality_checks(latest)
    status = "halt" if any(item["severity"] == "halt" for item in checks) else (
        "warn" if any(item["severity"] == "warn" for item in checks) else "ok"
    )
    comparison: list[dict[str, Any]] = []
    baseline = runs[1] if len(runs) > 1 else {}
    if baseline:
        for key in [
            "final_equity",
            "total_return",
            "max_drawdown",
            "annualized_sharpe",
            "average_cost_bps",
            "max_gross_exposure",
        ]:
            comparison.append(run_metric_delta(latest, baseline, key))
    return {
        "ok": status != "halt",
        "status": status,
        "latest": latest,
        "baseline": baseline,
        "checks": checks,
        "comparison": comparison,
        "runs": runs[:20],
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


def backendd_bin_path() -> Optional[Path]:
    for candidate in (BACKENDD_BIN, BACKENDD_CMAKE_BIN):
        if candidate.exists():
            return candidate
    return None


def invoke_backendd_http_route(route: str, timeout_seconds: float = 2.0) -> Optional[dict[str, Any]]:
    """Prefer the long-running C++ backendd service when it is available.

    The command-mode backendd is still useful for debugging and bootstrapping, but
    production UI reads should not fork a C++ process per request.  This helper
    keeps the Python server as an HTTP/UI shell while allowing backend read models
    to be served by the resident C++ process.
    """
    normalized = route if route.startswith("/") else f"/{route}"
    url = f"{BACKENDD_HTTP_BASE}{normalized}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read(2_000_000).decode("utf-8", "ignore")
    except Exception:
        return None
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {
            "ok": False,
            "available": True,
            "transport": "http",
            "route": route,
            "error": "backendd HTTP returned invalid JSON",
            "raw_output": raw[:1000],
        }
    if not isinstance(payload, dict):
        payload = {"ok": False, "error": "backendd HTTP JSON root is not an object"}
    payload["available"] = True
    payload["transport"] = "http"
    payload["route"] = route
    payload["backendd_url"] = url
    return payload


def invoke_backendd_route(route: str, timeout_seconds: float = 2.0) -> dict[str, Any]:
    """Call a read-only C++ backendd route from the Python HTTP/UI shell."""
    http_payload = invoke_backendd_http_route(route, timeout_seconds=timeout_seconds)
    if http_payload is not None:
        return http_payload

    binary = backendd_bin_path()
    if binary is None:
        return {
            "ok": False,
            "available": False,
            "generated_at": now_iso(),
            "route": route,
            "error": "backendd executable is not built; run make backendd",
            "migration": {
                "python_shell": True,
                "cpp_core": False,
                "note": "Python HTTP/UI shell is waiting for C++ backendd.",
            },
        }
    args = [
        str(binary),
        "--root",
        str(ROOT),
        "--config",
        "config/default.cfg",
        "--method",
        "GET",
        "--route",
        route,
    ]
    try:
        result = subprocess.run(
            args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except Exception as exc:
        return {
            "ok": False,
            "available": True,
            "generated_at": now_iso(),
            "binary": str(binary),
            "route": route,
            "error": str(exc),
            "migration": {
                "python_shell": True,
                "cpp_core": False,
                "note": "backendd invocation failed.",
            },
        }
    stdout = result.stdout.strip()
    try:
        payload = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError as exc:
        payload = {
            "ok": False,
            "available": True,
            "generated_at": now_iso(),
            "binary": str(binary),
            "route": route,
            "exit_code": result.returncode,
            "error": f"backendd returned invalid JSON: {exc}",
            "raw_output": stdout[:1000],
        }
    else:
        if not isinstance(payload, dict):
            payload = {"ok": False, "error": "backendd JSON root is not an object"}
        payload["available"] = True
        payload["binary"] = str(binary)
        payload["transport"] = "subprocess"
        payload["route"] = route
        payload["exit_code"] = result.returncode
        if result.returncode != 0:
            payload["ok"] = False
            payload["error"] = result.stderr.strip() or payload.get("error") or f"backendd exited {result.returncode}"
    return payload


def backend_core_status_payload(max_age_seconds: float = 2.0) -> dict[str, Any]:
    """Read the C++ backend summary while Python still owns HTTP/UI serving."""
    now = time.time()
    with BACKEND_CORE_CACHE_LOCK:
        cached = BACKEND_CORE_CACHE.get("payload")
        cached_at = float(BACKEND_CORE_CACHE.get("ts") or 0.0)
        if isinstance(cached, dict) and cached and now - cached_at <= max_age_seconds:
            return copy.deepcopy(cached)

    payload = invoke_backendd_route("/api/backend/summary", timeout_seconds=2.0)

    with BACKEND_CORE_CACHE_LOCK:
        BACKEND_CORE_CACHE["ts"] = time.time()
        BACKEND_CORE_CACHE["payload"] = copy.deepcopy(payload)
    return payload


def execute_backtest(config_arg: str = "config/default.cfg", build_first: bool = True) -> dict[str, Any]:
    LOG_DIR.mkdir(exist_ok=True)
    if build_first:
        build = run_command(["make", "traderd"], timeout=120)
        if build["returncode"] != 0:
            return {
                "ok": False,
                "stage": "build",
                "output": build["output"],
            }
    config_path = resolve_runtime_path(config_arg)
    run_config = parse_config(config_path)
    for stale_path in [
        LOG_DIR / "last_run_summary.txt",
        resolve_runtime_path(run_config.get("report_json_path", "logs/last_report.json")),
        resolve_runtime_path(run_config.get("event_log_path", "logs/events.jsonl")),
    ]:
        try:
            if stale_path.exists():
                stale_path.unlink()
        except OSError:
            pass
    run = run_command(["./traderd", "--config", config_arg], timeout=120)
    LAST_PLATFORM_OUTPUT.write_text(run["output"], encoding="utf-8")
    return {
        "ok": run["returncode"] == 0,
        "stage": "run",
        "output": run["output"],
        "summary": parse_summary(),
        "equity_curve": parse_equity_curve(run["output"]),
        "events": read_events(120, config=run_config),
        "report": read_report_json(config=run_config),
    }


def run_backtest(experiment_metadata: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    payload = execute_backtest()
    if not payload.get("ok") and payload.get("stage") == "build":
        return payload
    payload["run"] = archive_backtest_run(payload)
    payload["experiment"] = archive_experiment(payload, payload["run"], experiment_metadata)
    return payload


def parse_sweep_values(raw_values: Any) -> list[str]:
    if isinstance(raw_values, str):
        values = re.split(r"[\n,]+", raw_values)
    elif isinstance(raw_values, list):
        values = [str(value) for value in raw_values]
    else:
        values = []
    cleaned = [value.strip() for value in values if value and value.strip()]
    unique: list[str] = []
    for value in cleaned:
        if value not in unique:
            unique.append(value)
    if not unique:
        raise ValueError("参数扫描至少需要一个取值")
    if len(unique) > 12:
        raise ValueError("一次参数扫描最多允许 12 个取值，避免本机长时间阻塞")
    return unique


def validate_sweep_value(parameter: str, value: str) -> str:
    options = {item["key"]: item for item in strategy_parameter_options()}
    kind = options.get(parameter, {}).get("kind", "text")
    if kind == "int":
        parsed = int(value)
        return str(parsed)
    if kind == "float":
        parsed = float(value)
        return format(parsed, "g")
    return value


def run_parameter_sweep(body: dict[str, Any]) -> dict[str, Any]:
    # GAP-031: 支持多参数网格搜索
    parameters = body.get("parameters")
    if parameters and isinstance(parameters, list) and len(parameters) > 0:
        return run_grid_search(body, parameters)

    parameter = str(body.get("parameter", "")).strip()
    if parameter not in strategy_parameter_keys():
        raise ValueError("只允许扫描策略目录中登记过的参数")

    values = [validate_sweep_value(parameter, value) for value in parse_sweep_values(body.get("values", []))]
    return _run_single_sweep(parameter, values)


def _run_single_sweep(parameter: str, values: list[Any]) -> dict[str, Any]:
    sweep_id = f"sweep-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}-{uuid4().hex[:8]}"
    started_at = now_iso()
    original_config_text = DEFAULT_CONFIG.read_text(encoding="utf-8") if DEFAULT_CONFIG.exists() else ""
    results: list[dict[str, Any]] = []

    try:
        for index, value in enumerate(values):
            write_config({parameter: value})
            payload = run_backtest({"sweep": {"id": sweep_id, "parameter": parameter, "value": value, "index": index + 1, "total": len(values)}})
            experiment = payload.get("experiment", {})
            results.append({
                "value": value,
                "ok": bool(payload.get("ok")),
                "stage": payload.get("stage", ""),
                "experiment_id": experiment.get("id", ""),
                "summary": experiment.get("summary", payload.get("summary", {})),
                "error": "" if payload.get("ok") else str(payload.get("output", ""))[-2000:],
            })
    finally:
        DEFAULT_CONFIG.write_text(original_config_text, encoding="utf-8")

    metadata = {
        "id": sweep_id,
        "created_at": started_at,
        "completed_at": now_iso(),
        "parameter": parameter,
        "values": values,
        "ok": all(item.get("ok") for item in results),
        "results": results,
    }
    destination = SWEEP_DIR / sweep_id
    destination.mkdir(parents=True, exist_ok=True)
    with open(destination / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    return metadata


def run_grid_search(body: dict[str, Any], parameters: list[dict[str, Any]]) -> dict[str, Any]:
    """GAP-031: 多参数网格搜索."""
    from itertools import product

    # 解析每个参数的取值范围
    param_sets: list[list[tuple[str, Any]]] = []
    for p in parameters:
        name = str(p.get("parameter", "")).strip()
        if name not in strategy_parameter_keys():
            raise ValueError(f"未知参数: {name}")
        vals = [validate_sweep_value(name, v) for v in parse_sweep_values(p.get("values", []))]
        param_sets.append([(name, v) for v in vals])

    if not param_sets:
        raise ValueError("至少需要一个参数")

    # 笛卡尔积生成所有组合
    combinations = list(product(*param_sets))
    sweep_id = f"grid-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}-{uuid4().hex[:8]}"
    started_at = now_iso()
    original_config_text = DEFAULT_CONFIG.read_text(encoding="utf-8") if DEFAULT_CONFIG.exists() else ""
    results: list[dict[str, Any]] = []

    try:
        for index, combo in enumerate(combinations):
            config_updates = {name: val for name, val in combo}
            write_config(config_updates)
            payload = run_backtest({"sweep": {"id": sweep_id, "combo": config_updates, "index": index + 1, "total": len(combinations)}})
            experiment = payload.get("experiment", {})
            s = experiment.get("summary", payload.get("summary", {}))
            results.append({
                "params": dict(combo),
                "ok": bool(payload.get("ok")),
                "total_return": s.get("total_return", 0.0),
                "sharpe": s.get("annualized_sharpe", 0.0),
                "max_drawdown": s.get("max_drawdown", 0.0),
                "error": "" if payload.get("ok") else str(payload.get("output", ""))[-500:],
            })
    finally:
        DEFAULT_CONFIG.write_text(original_config_text, encoding="utf-8")

    # 按 Sharpe 排序，返回最佳组合
    results.sort(key=lambda r: r.get("sharpe", -999.0), reverse=True)
    metadata = {
        "id": sweep_id,
        "created_at": started_at,
        "completed_at": now_iso(),
        "parameters": [p.get("parameter") for p in parameters],
        "total_combinations": len(combinations),
        "best": results[0] if results else None,
        "top10": results[:10],
        "all": results,
    }
    destination = SWEEP_DIR / sweep_id
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "sweep.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": metadata["ok"],
        "sweep": metadata,
        "config": parse_config(),
        "experiments": list_experiments(),
    }


def safe_walk_forward_id(walk_forward_id: str) -> str:
    value = walk_forward_id.strip()
    if not WALK_FORWARD_ID_RE.fullmatch(value):
        raise ValueError("无效的 Walk-forward ID")
    return value


def list_walk_forward_runs() -> list[dict[str, Any]]:
    if not WALK_FORWARD_DIR.exists():
        return []
    runs: list[dict[str, Any]] = []
    for path in sorted(WALK_FORWARD_DIR.iterdir(), reverse=True):
        metadata_path = path / "walk_forward.json"
        if not metadata_path.exists():
            continue
        try:
            runs.append(json.loads(metadata_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return runs


def load_walk_forward_archive(walk_forward_id: str) -> dict[str, Any]:
    directory = WALK_FORWARD_DIR / safe_walk_forward_id(walk_forward_id)
    metadata_path = directory / "walk_forward.json"
    if not metadata_path.exists():
        raise ValueError("找不到 Walk-forward 档案")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def parse_window_size(body: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> int:
    raw_value = body.get(key, default)
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def root_relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def filename_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return (slug or "value")[:48]


def load_replay_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]], list[str]]:
    if not path.exists():
        raise ValueError(f"回测 CSV 不存在: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        required = ["timestamp", "symbol", "exchange", "open", "high", "low", "close", "volume"]
        missing = [field for field in required if field not in fieldnames]
        if missing:
            raise ValueError("CSV 缺少字段: " + ", ".join(missing))
        rows = [dict(row) for row in reader]
    if not rows:
        raise ValueError("CSV 没有可切分的行情行")
    rows.sort(key=lambda row: (row.get("timestamp", ""), row.get("symbol", ""), row.get("exchange", "")))
    timestamps = sorted({row.get("timestamp", "") for row in rows if row.get("timestamp", "")})
    if not timestamps:
        raise ValueError("CSV 没有有效 timestamp")
    return fieldnames, rows, timestamps


def write_replay_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def rows_for_timestamps(rows: list[dict[str, str]], timestamps: set[str]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("timestamp", "") in timestamps]


def score_walk_forward_metrics(metrics: dict[str, Any], metric: str) -> float:
    value = metrics.get(metric)
    if value is None:
        return float("-inf")
    if metric == "max_drawdown":
        return -float(value)
    if metric in {"annualized_sharpe", "final_equity", "total_return"}:
        return float(value)
    fallback = metrics.get("total_return")
    return float(fallback) if fallback is not None else float("-inf")


def aggregate_walk_forward(folds: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [fold for fold in folds if fold.get("ok")]
    test_metrics = [fold.get("test", {}).get("summary", {}) for fold in completed]
    train_metrics = [fold.get("best_train", {}).get("summary", {}) for fold in completed]

    def avg(key: str, rows: list[dict[str, Any]]) -> Optional[float]:
        values = [float(row[key]) for row in rows if row.get(key) is not None]
        return sum(values) / len(values) if values else None

    best_value_counts: dict[str, int] = {}
    for fold in completed:
        value = str(fold.get("best_value", ""))
        if value:
            best_value_counts[value] = best_value_counts.get(value, 0) + 1

    return {
        "fold_count": len(folds),
        "completed_folds": len(completed),
        "ok": bool(folds) and len(completed) == len(folds),
        "avg_train_return": avg("total_return", train_metrics),
        "avg_test_return": avg("total_return", test_metrics),
        "avg_test_sharpe": avg("annualized_sharpe", test_metrics),
        "avg_test_turnover": avg("average_turnover", test_metrics),
        "avg_test_cost_bps": avg("average_cost_bps", test_metrics),
        "max_test_drawdown": max(
            [float(row.get("max_drawdown", 0.0) or 0.0) for row in test_metrics],
            default=None,
        ),
        "best_value_counts": dict(sorted(best_value_counts.items())),
    }


def run_walk_forward(body: dict[str, Any]) -> dict[str, Any]:
    parameter = str(body.get("parameter", "")).strip()
    if parameter not in strategy_parameter_keys():
        raise ValueError("只允许 Walk-forward 验证策略目录中登记过的参数")

    values = [validate_sweep_value(parameter, value) for value in parse_sweep_values(body.get("values", []))]
    if len(values) > 8:
        raise ValueError("Walk-forward 每次最多允许 8 个候选值，避免本机长时间阻塞")

    train_windows = parse_window_size(body, "train_windows", 4, 2, 260)
    test_windows = parse_window_size(body, "test_windows", 2, 1, 120)
    step_windows = parse_window_size(body, "step_windows", test_windows, 1, 120)
    max_folds = parse_window_size(body, "max_folds", 8, 1, 24)
    metric = str(body.get("metric", "total_return")).strip() or "total_return"
    if metric not in {"total_return", "annualized_sharpe", "final_equity", "max_drawdown"}:
        raise ValueError("不支持的 Walk-forward 选择指标")

    base_config = parse_config()
    if base_config.get("history.mode", "local") != "local":
        raise ValueError("Walk-forward 当前只支持本地 CSV；远端历史模式请先导出固定数据集。")

    replay_path = resolve_runtime_path(base_config.get("replay_path", "data/sample_bars.csv"))
    fieldnames, all_rows, timestamps = load_replay_csv_rows(replay_path)
    if len(timestamps) < train_windows + test_windows:
        raise ValueError(
            f"样本窗口不足：共有 {len(timestamps)} 个时间点，至少需要 "
            f"{train_windows + test_windows} 个。"
        )
    fold_starts: list[int] = []
    next_start = 0
    while next_start + train_windows + test_windows <= len(timestamps) and len(fold_starts) < max_folds:
        fold_starts.append(next_start)
        next_start += step_windows

    build = run_command(["make", "traderd"], timeout=120)
    if build["returncode"] != 0:
        return {"ok": False, "stage": "build", "output": build["output"]}

    walk_forward_id = f"wf-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}-{uuid4().hex[:8]}"
    destination = WALK_FORWARD_DIR / walk_forward_id
    destination.mkdir(parents=True, exist_ok=True)
    started_at = now_iso()
    original_config_text = DEFAULT_CONFIG.read_text(encoding="utf-8") if DEFAULT_CONFIG.exists() else ""
    folds: list[dict[str, Any]] = []

    try:
        for fold_index, start in enumerate(fold_starts, start=1):
            train_dates = timestamps[start:start + train_windows]
            test_dates = timestamps[start + train_windows:start + train_windows + test_windows]
            fold_dir = destination / f"fold-{fold_index:02d}"
            train_rows = rows_for_timestamps(all_rows, set(train_dates))
            test_rows = rows_for_timestamps(all_rows, set(test_dates))
            train_csv = fold_dir / "train.csv"
            test_csv = fold_dir / "test.csv"
            write_replay_csv(train_csv, fieldnames, train_rows)
            write_replay_csv(test_csv, fieldnames, test_rows)

            fold_result: dict[str, Any] = {
                "index": fold_index,
                "train_start": train_dates[0],
                "train_end": train_dates[-1],
                "test_start": test_dates[0],
                "test_end": test_dates[-1],
                "train_rows": len(train_rows),
                "test_rows": len(test_rows),
                "candidates": [],
                "ok": False,
            }

            best_candidate: Optional[dict[str, Any]] = None
            best_score = float("-inf")
            for value in values:
                slug = filename_slug(value)
                fold_config = dict(base_config)
                fold_config.update(
                    {
                        "history.mode": "local",
                        "replay_path": root_relative(train_csv),
                        "event_log_path": root_relative(fold_dir / f"train-{slug}-events.jsonl"),
                        "report_json_path": root_relative(fold_dir / f"train-{slug}-report.json"),
                        "print_cycles": "false",
                        "print_event_stream": "false",
                        parameter: value,
                    }
                )
                write_config(fold_config)
                payload = execute_backtest(build_first=False)
                metrics = metrics_from_report(payload.get("report", {}), payload.get("output", ""))
                score = score_walk_forward_metrics(metrics, metric) if payload.get("ok") else float("-inf")
                candidate = {
                    "value": value,
                    "ok": bool(payload.get("ok")),
                    "score": None if score == float("-inf") else score,
                    "summary": metrics,
                    "error": "" if payload.get("ok") else str(payload.get("output", ""))[-1600:],
                }
                fold_result["candidates"].append(candidate)
                if payload.get("ok") and score > best_score:
                    best_score = score
                    best_candidate = candidate

            if best_candidate is None:
                fold_result["error"] = "训练窗口没有成功的候选参数"
                folds.append(fold_result)
                continue

            best_value = str(best_candidate["value"])
            test_config = dict(base_config)
            test_config.update(
                {
                    "history.mode": "local",
                    "replay_path": root_relative(test_csv),
                    "event_log_path": root_relative(fold_dir / "test-events.jsonl"),
                    "report_json_path": root_relative(fold_dir / "test-report.json"),
                    "print_cycles": "false",
                    "print_event_stream": "false",
                    parameter: best_value,
                }
            )
            write_config(test_config)
            test_payload = execute_backtest(build_first=False)
            run_metadata = archive_backtest_run(test_payload)
            experiment_metadata = archive_experiment(
                test_payload,
                run_metadata,
                {
                    "mode": "walk_forward",
                    "walk_forward": {
                        "id": walk_forward_id,
                        "parameter": parameter,
                        "metric": metric,
                        "fold_index": fold_index,
                        "fold_count": len(fold_starts),
                        "best_value": best_value,
                        "train_start": train_dates[0],
                        "train_end": train_dates[-1],
                        "test_start": test_dates[0],
                        "test_end": test_dates[-1],
                    },
                },
            )
            fold_result.update(
                {
                    "ok": bool(test_payload.get("ok")),
                    "best_value": best_value,
                    "best_train": best_candidate,
                    "test": {
                        "ok": bool(test_payload.get("ok")),
                        "summary": experiment_metadata.get("summary", test_payload.get("summary", {})),
                        "experiment_id": experiment_metadata.get("id", ""),
                        "run_id": run_metadata.get("id", ""),
                        "error": "" if test_payload.get("ok") else str(test_payload.get("output", ""))[-1600:],
                    },
                }
            )
            folds.append(fold_result)
    finally:
        DEFAULT_CONFIG.write_text(original_config_text, encoding="utf-8")

    aggregate = aggregate_walk_forward(folds)
    metadata = {
        "id": walk_forward_id,
        "created_at": started_at,
        "completed_at": now_iso(),
        "ok": aggregate["ok"],
        "parameter": parameter,
        "values": values,
        "metric": metric,
        "train_windows": train_windows,
        "test_windows": test_windows,
        "step_windows": step_windows,
        "source_replay_path": str(replay_path),
        "timestamp_count": len(timestamps),
        "row_count": len(all_rows),
        "summary": aggregate,
        "folds": folds,
    }
    (destination / "walk_forward.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": aggregate["ok"],
        "walk_forward": metadata,
        "walk_forward_runs": list_walk_forward_runs(),
        "config": parse_config(),
        "experiments": list_experiments(),
    }


def normalize_okx_inst_ids(
    raw: Any,
    *,
    max_items: int = OKX_MAX_BACKTEST_INSTRUMENTS,
    limit_label: str = "加密回测",
) -> list[str]:
    if isinstance(raw, str):
        items = re.split(r"[\n,]+", raw)
    elif isinstance(raw, list):
        items = [str(item) for item in raw]
    else:
        items = okx_instruments_config()
    normalized: list[str] = []
    for item in items:
        value = item.strip().upper()
        if not value:
            continue
        if not re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+(?:-[A-Z0-9]+)?", value):
            raise ValueError(f"无效 OKX 合约: {value}")
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise ValueError("至少需要一个 OKX 合约")
    if max_items > 0 and len(normalized) > max_items:
        raise ValueError(f"一次{limit_label}最多允许 {max_items} 个合约")
    return normalized


def okx_spot_inst_type(params: dict[str, list[str]]) -> tuple[bool, str, dict[str, Any]]:
    inst_type = params.get("instType", [OKX_EXECUTION_INST_TYPE])[0].upper()
    if inst_type not in {OKX_EXECUTION_INST_TYPE, *OKX_DERIVATIVE_INST_TYPES}:
        return False, inst_type, {
            "ok": False,
            "error": f"当前平台只允许 OKX SPOT/SWAP/FUTURES，不允许 {inst_type}。",
            "config": okx_status(),
        }
    return True, inst_type, {}


def okx_derivative_inst_id(inst_id: str, inst_type: str = "SWAP") -> str:
    value = str(inst_id).upper().strip()
    if inst_type == "SWAP" and value.endswith("-SWAP"):
        return value
    parts = value.split("-")
    if inst_type == "SWAP" and len(parts) == 2:
        return f"{parts[0]}-{parts[1]}-SWAP"
    return value


def okx_source_inst_id(inst_id: str) -> str:
    value = str(inst_id).upper().strip()
    if value.endswith("-SWAP"):
        return value[:-5]
    return value


def okx_order_inst_type(order: dict[str, Any]) -> str:
    explicit = str(order.get("_instType", order.get("instType", ""))).upper().strip()
    if explicit:
        return explicit
    inst_id = str(order.get("instId", "")).upper().strip()
    if inst_id.endswith("-SWAP"):
        return "SWAP"
    return OKX_EXECUTION_INST_TYPE


def okx_instruments_for_type(inst_type: str) -> list[str]:
    normalized = str(inst_type or OKX_EXECUTION_INST_TYPE).upper().strip()
    configured = okx_instruments_config()
    if normalized == "SWAP":
        return [okx_derivative_inst_id(item, "SWAP") for item in configured]
    if normalized == "FUTURES":
        return [
            item.upper().strip()
            for item in configured
            if len(item.upper().strip().split("-")) == 3 and not item.upper().strip().endswith("-SWAP")
        ]
    return configured


def paper_derivatives_enabled(settings: Optional[dict[str, Any]] = None) -> bool:
    config = parse_config()
    config_enabled = parse_bool_setting(config.get("execution.derivatives.enabled", "true"), True)
    if config_enabled:
        return True
    if isinstance(settings, dict):
        return bool_setting_from_any(settings.get("derivatives_enabled", config_enabled), config_enabled)
    return config_enabled


def paper_derivatives_inst_type(settings: Optional[dict[str, Any]] = None) -> str:
    config = parse_config()
    value = str(
        (settings or {}).get("derivatives_inst_type", config.get("execution.derivatives.inst_type", "SWAP"))
    ).upper().strip()
    return value if value in OKX_DERIVATIVE_INST_TYPES else "SWAP"


def paper_derivatives_margin_mode(settings: Optional[dict[str, Any]] = None) -> str:
    config = parse_config()
    value = str(
        (settings or {}).get("derivatives_margin_mode", config.get("execution.derivatives.margin_mode", "isolated"))
    ).lower().strip()
    return value if value in OKX_DERIVATIVE_TD_MODES else "isolated"


def configured_derivatives_position_mode(settings: Optional[dict[str, Any]] = None) -> str:
    config = parse_config()
    value = str(
        (settings or {}).get("derivatives_position_mode", config.get("execution.derivatives.position_mode", "net"))
    ).lower().strip()
    return value if value in {"net", "long_short"} else "net"


def paper_okx_max_live_orders(settings: Optional[dict[str, Any]] = None) -> int:
    if isinstance(settings, dict):
        configured = settings.get("okx_auto_max_live_orders")
        if configured is not None:
            return bounded_int(configured, 10, 1, 20)
    return 10


def bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def bounded_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    parsed = float_from_any(value, default)
    return max(minimum, min(parsed, maximum))


def build_crypto_run_profile(
    body: dict[str, Any],
    default_days: int = 7,
    *,
    max_instruments: int = OKX_MAX_BACKTEST_INSTRUMENTS,
    limit_label: str = "加密回测",
) -> dict[str, Any]:
    instruments = normalize_okx_inst_ids(
        body.get("instruments") or body.get("instIds"),
        max_items=max_instruments,
        limit_label=limit_label,
    )
    bar = str(body.get("bar", "1m")).strip()
    if bar not in OKX_BAR_SECONDS:
        raise ValueError("不支持的 OKX K 线周期")
    raw_days = body.get("lookback_days", body.get("lookbackDays", body.get("days", default_days)))
    days = bounded_int(raw_days, default_days, 1, 730)
    max_pages = bounded_int(body.get("max_pages", body.get("maxPages", 40)), 40, 1, 200)
    server_url = str(body.get("history_server_url", "")).strip() or parse_config().get(
        "history.server_url", "http://127.0.0.1:8790"
    )
    end_value = body.get("end", "")
    start_value = body.get("start", "")
    end_ms = epoch_ms_from_text(str(end_value)) if str(end_value).strip() else int(time.time() * 1000)
    start_ms = epoch_ms_from_text(str(start_value)) if str(start_value).strip() else end_ms - days * DAY_MS
    if end_ms < start_ms:
        start_ms, end_ms = end_ms, start_ms
    window_ms = max(end_ms - start_ms, OKX_BAR_SECONDS[bar] * 1000)
    estimated_cycles = max(1, int(window_ms / (OKX_BAR_SECONDS[bar] * 1000)))
    if estimated_cycles > 12_000:
        raise ValueError("加密回测窗口过大：请缩短天数或选择更大的 K 线周期。")
    contracts = [f"{inst}.OKX" for inst in instruments]
    return {
        "instruments": instruments,
        "contracts": contracts,
        "bar": bar,
        "days": days,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "start": text_from_epoch_ms(start_ms),
        "end": text_from_epoch_ms(end_ms),
        "history_server_url": server_url,
        "max_pages": max_pages,
        "estimated_cycles": estimated_cycles,
    }


def run_crypto_backtest(body: dict[str, Any]) -> dict[str, Any]:
    profile = {"mode": "crypto_backtest", **build_crypto_run_profile(body, default_days=7)}
    original_config_text = DEFAULT_CONFIG.read_text(encoding="utf-8") if DEFAULT_CONFIG.exists() else ""
    started_at = now_iso()
    try:
        write_config(
            {
                "history.mode": "remote",
                "history.server_url": profile["history_server_url"],
                "history.contracts": ",".join(profile["contracts"]),
                "history.bar": profile["bar"],
                "history.start": str(profile["start_ms"]),
                "history.end": str(profile["end_ms"]),
                "history.max_pages": str(profile["max_pages"]),
                "print_cycles": "false",
                "print_event_stream": "false",
            }
        )
        payload = run_backtest({"mode": "crypto_backtest", "crypto": profile})
    finally:
        DEFAULT_CONFIG.write_text(original_config_text, encoding="utf-8")

    payload["crypto"] = profile
    payload["crypto"]["created_at"] = started_at
    payload["config"] = parse_config()
    payload["experiments"] = list_experiments()
    payload["history_server"] = history_server_status({"history.server_url": profile["history_server_url"]})
    return payload


def strategy_wash_score(summary: dict[str, Any]) -> float:
    total_return = float_from_any(summary.get("total_return"), 0.0)
    sharpe = float_from_any(summary.get("annualized_sharpe"), 0.0)
    drawdown = max(float_from_any(summary.get("max_drawdown"), 0.0), 0.0)
    cost_bps = max(float_from_any(summary.get("average_cost_bps"), 0.0), 0.0)
    fills = float_from_any(summary.get("total_fills"), 0.0)
    activity_bonus = min(fills, 20.0) * 0.001
    return total_return * 100.0 + sharpe * 0.35 - drawdown * 35.0 - cost_bps * 0.01 + activity_bonus


def strategy_wash_decision(summary: dict[str, Any], ok: bool) -> str:
    if not ok:
        return "drop"
    total_return = float_from_any(summary.get("total_return"), 0.0)
    sharpe = float_from_any(summary.get("annualized_sharpe"), 0.0)
    drawdown = float_from_any(summary.get("max_drawdown"), 0.0)
    fills = int(float_from_any(summary.get("total_fills"), 0.0))
    if total_return > 0.0 and sharpe >= 0.0 and drawdown <= 0.08 and fills > 0:
        return "keep"
    if total_return > -0.03 and drawdown <= 0.12:
        return "watch"
    return "drop"


def run_strategy_wash(body: dict[str, Any]) -> dict[str, Any]:
    profile = {"mode": "strategy_wash", **build_crypto_run_profile(body, default_days=3)}
    raw_ids = body.get("strategy_ids", body.get("strategyIds", body.get("strategies", "")))
    if isinstance(raw_ids, list):
        strategy_ids = [str(item).strip() for item in raw_ids if str(item).strip()]
    else:
        strategy_ids = [item.strip() for item in str(raw_ids).split(",") if item.strip()]
    if not strategy_ids:
        strategy_ids = [item.strip() for item in parse_config().get("strategy.enabled", "").split(",") if item.strip()]
    catalog = {str(item["id"]): item for item in STRATEGY_CATALOG}
    unknown = [item for item in strategy_ids if item not in catalog]
    if unknown:
        raise ValueError(f"未知策略：{', '.join(unknown)}")
    if not strategy_ids:
        raise ValueError("至少需要一个策略 ID")
    if len(strategy_ids) > 12:
        raise ValueError("一次策略清洗最多允许 12 个策略，避免本机长时间阻塞")

    wash_id = f"wash-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}-{uuid4().hex[:8]}"
    started_at = now_iso()
    original_config_text = DEFAULT_CONFIG.read_text(encoding="utf-8") if DEFAULT_CONFIG.exists() else ""
    rows: list[dict[str, Any]] = []
    try:
        for index, strategy_id in enumerate(strategy_ids):
            write_config(
                {
                    "history.mode": "remote",
                    "history.server_url": profile["history_server_url"],
                    "history.contracts": ",".join(profile["contracts"]),
                    "history.bar": profile["bar"],
                    "history.start": str(profile["start_ms"]),
                    "history.end": str(profile["end_ms"]),
                    "history.max_pages": str(profile["max_pages"]),
                    "strategy.enabled": strategy_id,
                    "print_cycles": "false",
                    "print_event_stream": "false",
                }
            )
            payload = execute_backtest(build_first=index == 0)
            if payload.get("ok"):
                run = archive_backtest_run(payload)
                experiment = archive_experiment(
                    payload,
                    run,
                    {
                        "mode": "strategy_wash",
                        "strategy_wash": {
                            "id": wash_id,
                            "strategy_id": strategy_id,
                            "index": index + 1,
                            "total": len(strategy_ids),
                        },
                        "crypto": profile,
                    },
                )
            else:
                experiment = {}
            summary = experiment.get("summary", payload.get("summary", {}))
            score = strategy_wash_score(summary)
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "display_name": catalog[strategy_id].get("display_name", strategy_id),
                    "style": catalog[strategy_id].get("style", ""),
                    "ok": bool(payload.get("ok")),
                    "score": score,
                    "decision": strategy_wash_decision(summary, bool(payload.get("ok"))),
                    "summary": summary,
                    "experiment_id": experiment.get("id", ""),
                    "error": "" if payload.get("ok") else str(payload.get("output", ""))[-2000:],
                }
            )
    finally:
        DEFAULT_CONFIG.write_text(original_config_text, encoding="utf-8")

    rows.sort(key=lambda item: float(item.get("score", float("-inf"))), reverse=True)
    metadata = {
        "id": wash_id,
        "created_at": started_at,
        "completed_at": now_iso(),
        "ok": all(item.get("ok") for item in rows),
        "crypto": profile,
        "strategy_ids": strategy_ids,
        "results": rows,
    }
    destination = STRATEGY_WASH_DIR / wash_id
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "strategy_wash.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": metadata["ok"],
        "strategy_wash": metadata,
        "config": parse_config(),
        "experiments": list_experiments(),
    }


def default_paper_settings() -> dict[str, Any]:
    config = parse_config()
    strategy_ids = [item.strip() for item in config.get("strategy.enabled", "").split(",") if item.strip()]
    base_notional = bounded_float(config.get("execution.trade_unit.base_notional_usdt", "1"), 1.0, 0.1, 1000.0)
    derivatives_enabled = parse_bool_setting(config.get("execution.derivatives.enabled", "true"), True)
    derivatives_inst_type = config.get("execution.derivatives.inst_type", "SWAP")
    instruments = okx_instruments_config()
    if derivatives_enabled:
        effective_derivatives = set(okx_effective_instruments_for_type(derivatives_inst_type))
        if effective_derivatives:
            instruments = [
                inst_id for inst_id in instruments
                if okx_derivative_inst_id(inst_id, derivatives_inst_type) in effective_derivatives
            ] or instruments
    return {
        "instruments": instruments,
        "bar": "1m",
        "lookback_days": 1,
        "max_pages": 40,
        "poll_seconds": 60,
        "mode": "realtime",
        "okx_auto_submit": paper_okx_auto_submission_required(),
        "okx_auto_max_notional": base_notional,
        "okx_auto_max_orders": 8,
        "okx_auto_max_live_orders": 10,
        "okx_auto_max_market_latency_ms": 30000,
        "okx_auto_max_runtime_ms": 5000,
        "okx_auto_require_stream": False,
        "okx_auto_block_tradeability_warn": False,
        "okx_auto_cancel_stale_orders": True,
        "okx_auto_cancel_min_age_seconds": 180,
        "okx_auto_cancel_max_orders": 5,
        "paper_local_repair_stale_orders": True,
        "paper_local_repair_min_age_seconds": 300,
        "paper_local_repair_max_orders": 20,
        "paper_broker_fill_backfill": True,
        "paper_broker_fill_backfill_max_orders": 50,
        "paper_broker_terminal_sync": True,
        "paper_broker_terminal_sync_max_orders": 20,
        "derivatives_enabled": derivatives_enabled,
        "derivatives_inst_type": derivatives_inst_type,
        "derivatives_margin_mode": config.get("execution.derivatives.margin_mode", "isolated"),
        "derivatives_position_mode": config.get("execution.derivatives.position_mode", "net"),
        "derivatives_max_exchange_leverage": bounded_float(config.get("execution.derivatives.max_exchange_leverage", "3"), 3.0, 1.0, 20.0),
        "derivatives_max_effective_leverage": bounded_float(config.get("execution.derivatives.max_effective_leverage", "2"), 2.0, 0.0, 10.0),
        "derivatives_max_unit_effective_leverage": bounded_float(config.get("execution.derivatives.max_unit_effective_leverage", "1"), 1.0, 0.0, 10.0),
        "trade_unit_base_notional_usdt": base_notional,
        "trade_unit_agent_leverage_enabled": parse_bool_setting(config.get("execution.trade_unit.agent_leverage_enabled", "true"), True),
        "trade_unit_agent_max_step": bounded_float(config.get("execution.trade_unit.agent_max_step", "0.5"), 0.5, 0.0, 5.0),
        "require_cxx_realtime_runner": False,
        "strategy_ids": strategy_ids,
        "history_server_url": config.get("history.server_url", "http://127.0.0.1:8790"),
    }


def paper_okx_auto_submission_required() -> bool:
    """Whether paper trading must be backed by OKX simulated orders.

    The product default is strict because the platform's "virtual trading"
    workflow is meant to be visible on OKX simulated trading, not just in the
    local in-memory paper broker.  A local-only mode is still possible for
    developer diagnostics by setting PAPER_REQUIRE_OKX_AUTO_SUBMIT=false.
    """
    return parse_bool_setting(get_local_setting("PAPER_REQUIRE_OKX_AUTO_SUBMIT", "true"), True)


def paper_execution_policy() -> dict[str, Any]:
    required = paper_okx_auto_submission_required()
    config = parse_config()
    derivatives_enabled = paper_derivatives_enabled()
    return {
        "okx_auto_submit_required": required,
        "execution_venue": "okx_simulated" if required else "local_or_okx_simulated",
        "order_scope": "SWAP/FUTURES isolated/cross limit/post_only" if derivatives_enabled else "SPOT/cash limit/post_only",
        "derivatives_scope": "SWAP/FUTURES simulated gated" if derivatives_enabled else "SWAP/FUTURES shadow",
        "derivatives_enabled": derivatives_enabled,
        "trade_unit_base_notional_usdt": bounded_float(config.get("execution.trade_unit.base_notional_usdt", "1"), 1.0, 0.1, 1000.0),
        "agent_leverage_enabled": parse_bool_setting(config.get("execution.trade_unit.agent_leverage_enabled", "true"), True),
        "confirm": PAPER_OKX_AUTO_CONFIRM,
    }


def paper_okx_auto_state_for_settings(
    settings: dict[str, Any],
    current: Optional[dict[str, Any]] = None,
    message: str = "",
) -> dict[str, Any]:
    current = current if isinstance(current, dict) else {}
    enabled = bool(settings.get("okx_auto_submit"))
    default_message = "OKX 自动提交已武装。" if enabled else "OKX 自动提交未开启。"
    return {
        "enabled": enabled,
        "last_checked_at": current.get("last_checked_at", ""),
        "last_status": "armed" if enabled else "disabled",
        "last_message": message or default_message,
        "submitted_source_order_ids": list(current.get("submitted_source_order_ids", []) or [])[-500:],
        "attempted_source_order_ids": list(current.get("attempted_source_order_ids", []) or [])[-500:],
        "recent": list(current.get("recent", []) or [])[-30:],
        "submission_guard": current.get("submission_guard", {}),
        "last_stale_cancel": current.get("last_stale_cancel", {}),
        "last_local_order_repair": current.get("last_local_order_repair", {}),
        "last_local_order_repair_effective": current.get("last_local_order_repair_effective", {}),
        "last_broker_fill_backfill": current.get("last_broker_fill_backfill", {}),
        "last_broker_fill_backfill_effective": current.get("last_broker_fill_backfill_effective", {}),
        "last_broker_terminal_sync": current.get("last_broker_terminal_sync", {}),
        "last_broker_terminal_sync_effective": current.get("last_broker_terminal_sync_effective", {}),
        "last_stale_broker_reconcile": current.get("last_stale_broker_reconcile", {}),
        "last_stale_broker_reconcile_effective": current.get("last_stale_broker_reconcile_effective", {}),
    }


def ensure_paper_okx_auto_submit_ready(settings: dict[str, Any]) -> dict[str, Any]:
    """Fail fast when the virtual trading runner is expected to place OKX orders."""
    if not settings.get("okx_auto_submit"):
        return {"ready": True, "reason": "OKX 自动提交未启用。", "required": paper_okx_auto_submission_required()}
    # 启动时不阻塞于 OKX 探测——网络可能不通，实际提交时仍有门禁。
    # 用短超时线程避免 okx_request 卡死整个启动流程。
    import threading
    gate_result: dict[str, Any] = {}
    def _probe():
        nonlocal gate_result
        try:
            gate_result = okx_simulated_submit_gate()
        except Exception as e:
            gate_result = {"ready": False, "reason": str(e)}
    t = threading.Thread(target=_probe, daemon=True)
    t.start()
    t.join(timeout=5.0)
    if t.is_alive():
        return {"ready": True, "reason": "OKX 模拟盘探测超时（5秒），放行启动，实际提交时再检查。", "required": paper_okx_auto_submission_required()}
    gate = gate_result if gate_result else {"ready": False, "reason": "探测未返回结果"}
    if not gate.get("ready"):
        reason = str(gate.get("reason", "-"))
        # OKX 网络不可达时，启动不应硬阻断——实际提交时仍有门禁保护
        if "timed out" in reason or "Host is down" in reason or "refused" in reason or "探测超时" in reason:
            return {"ready": True, "reason": f"OKX 提交门禁检查网络超时({reason})，放行启动，实际提交时会再次检查。", "required": paper_okx_auto_submission_required()}
        raise ValueError(f"虚拟盘必须挂到 OKX 模拟盘，但提交门禁未通过：{gate.get('reason', '-')}")
    # 启动/恢复 runner 前先做一次轻量维护，避免历史 live 状态或已终态订单阻塞下一轮。
    state = read_paper_state()
    current = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
    auto_state = paper_okx_auto_state_for_settings(settings, current)
    auto_state = paper_okx_sync_auto_submit_state(auto_state, max_sync=10)
    auto_state = paper_okx_auto_cancel_stale_orders(auto_state, settings)
    auto_state = attach_broker_fill_backfill_result(
        auto_state,
        apply_paper_broker_fill_backfill(settings, source="runner_start_preflight"),
    )
    auto_state = attach_broker_terminal_sync_result(
        auto_state,
        apply_paper_broker_terminal_sync(settings, source="runner_start_preflight"),
    )
    auto_state = attach_stale_broker_reconcile_result(
        auto_state,
        apply_paper_stale_broker_reconcile(settings, source="runner_start_preflight"),
    )
    auto_state = attach_local_order_repair_result(
        auto_state,
        apply_paper_local_order_repair(settings, source="runner_start_preflight"),
    )
    state["okx_auto_submit"] = auto_state
    write_paper_state(state)
    return {**gate, "required": paper_okx_auto_submission_required()}


def paper_settings_with_cached_derivative_filter(settings: dict[str, Any]) -> dict[str, Any]:
    """Sanitize persisted paper settings using cached OKX derivative metadata.

    Old state files may still contain source symbols that have OKX spot data but
    no usable SWAP/FUTURES contract.  Filtering at state-read time keeps resume
    and manual ticks from reintroducing those symbols into the auto-submit path
    without adding REST IO to the hot strategy loop.
    """
    if not paper_derivatives_enabled(settings):
        return settings
    inst_type = paper_derivatives_inst_type(settings)
    if inst_type not in OKX_DERIVATIVE_INST_TYPES:
        return settings
    instruments = [str(item).upper().strip() for item in settings.get("instruments", []) or [] if str(item).strip()]
    if not instruments:
        return settings
    effective = set(okx_effective_instruments_for_type(inst_type))
    if not effective:
        return settings
    supported: list[str] = []
    unsupported: list[dict[str, Any]] = []
    for source_id in instruments:
        derivative_id = okx_derivative_inst_id(source_id, inst_type)
        if derivative_id in effective:
            supported.append(source_id)
        else:
            unsupported.append(
                {
                    "source_inst_id": source_id,
                    "inst_id": derivative_id,
                    "reason": "本地 OKX 合约元数据缓存未确认该品种可用于自动提交。",
                }
            )
    if not unsupported:
        return settings
    updated = dict(settings)
    if supported:
        updated["instruments"] = supported
    updated["instrument_filter"] = {
        "ok": True,
        "filter_applied": True,
        "inst_type": inst_type,
        "source": "cache",
        "supported_source_instruments": supported,
        "unsupported_instruments": unsupported,
        "cache_only": True,
    }
    return updated


def default_paper_state() -> dict[str, Any]:
    return {
        "ok": True,
        "status": "stopped",
        "started_at": "",
        "stopped_at": "",
        "last_tick_at": "",
        "last_success_at": "",
        "next_tick_after": "",
        "run_count": 0,
        "last_run_id": "",
        "last_error": "",
        "last_skip_reason": "",
        "tick_running": False,
        "settings": default_paper_settings(),
        "summary": {},
        "portfolio": {},
        "latest_cycle": {},
        "diagnostics": {},
        "markers_count": 0,
        "live": {},
        "okx_auto_submit": {},
        "cxx_realtime_runner": {},
        "runtime_preflight": {},
        "execution_policy": paper_execution_policy(),
    }


def read_paper_state() -> dict[str, Any]:
    if not PAPER_STATE_PATH.exists():
        return default_paper_state()
    try:
        saved = json.loads(PAPER_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        saved = {}
    state = default_paper_state()
    state.update(saved if isinstance(saved, dict) else {})
    settings = default_paper_settings()
    settings.update(state.get("settings") or {})
    settings["okx_auto_max_live_orders"] = paper_okx_max_live_orders(settings)
    settings["derivatives_enabled"] = paper_derivatives_enabled(settings)
    settings["derivatives_inst_type"] = paper_derivatives_inst_type(settings)
    settings["derivatives_margin_mode"] = paper_derivatives_margin_mode(settings)
    settings = paper_settings_with_cached_derivative_filter(settings)
    state["settings"] = settings
    state["execution_policy"] = paper_execution_policy()
    return state


def write_paper_state(state: dict[str, Any]) -> dict[str, Any]:
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = PAPER_STATE_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(PAPER_STATE_PATH)
    return state


def compact_count_by_key(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): len(rows) if isinstance(rows, list) else 0
        for key, rows in value.items()
    }


def compact_tail_by_key(value: Any, limit: int) -> dict[str, list[Any]]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): list(rows[-limit:]) if isinstance(rows, list) and limit > 0 else []
        for key, rows in value.items()
    }


def compact_paper_cycle_for_response(cycle: Any) -> dict[str, Any]:
    if not isinstance(cycle, dict):
        return {}
    features = cycle.get("features", {}) if isinstance(cycle.get("features"), dict) else {}
    risk = cycle.get("risk_decision", {}) if isinstance(cycle.get("risk_decision"), dict) else {}
    post_portfolio = cycle.get("post_trade_portfolio", {}) if isinstance(cycle.get("post_trade_portfolio"), dict) else {}
    orders = cycle.get("orders", []) if isinstance(cycle.get("orders"), list) else []
    reports = cycle.get("reports", []) if isinstance(cycle.get("reports"), list) else []
    pending_orders = cycle.get("pending_orders", []) if isinstance(cycle.get("pending_orders"), list) else []
    return {
        "cycle_index": cycle.get("cycle_index"),
        "label": cycle.get("label", ""),
        "features": {
            key: copy.deepcopy(features.get(key))
            for key in {
                "engine",
                "tick_count",
                "latest_tick_key",
                "market_latency_ms",
                "runtime_ms",
                "data_source",
                "unsupported_strategies",
            }
            if key in features
        },
        "signal_count": len(cycle.get("signals", []) or []) if isinstance(cycle.get("signals"), list) else 0,
        "order_count": len(orders),
        "fill_count": len([item for item in reports if float_from_any(item.get("last_fill_qty")) > 0.0]),
        "pending_order_count": len(pending_orders),
        "expired_orders": cycle.get("expired_orders", 0),
        "risk_action": risk.get("action", ""),
        "risk_reason": risk.get("reason", ""),
        "equity": post_portfolio.get("equity"),
        "cash": post_portfolio.get("cash"),
        "gross_exposure": post_portfolio.get("gross_exposure"),
    }


def compact_live_paper_state_for_response(live: dict[str, Any]) -> dict[str, Any]:
    """Return a browser-sized live paper state without mutating persisted state.

    The paper runner keeps bounded but still fairly large internals such as
    trade de-duplication IDs, tick history, cycle payloads, and equity samples.
    Those are useful for recovery and diagnostics on disk, but returning them on
    every polling request makes the UI slower as the realtime engine runs.
    """
    if not isinstance(live, dict):
        return {}
    heavy_keys = {"tick_history", "seen_trade_ids", "cycles", "equity_curve", "pending_orders"}
    compact = {
        key: copy.deepcopy(value)
        for key, value in live.items()
        if key not in heavy_keys
    }
    tick_history = live.get("tick_history", {}) if isinstance(live.get("tick_history"), dict) else {}
    seen_trade_ids = live.get("seen_trade_ids", {}) if isinstance(live.get("seen_trade_ids"), dict) else {}
    cycles = live.get("cycles", []) if isinstance(live.get("cycles"), list) else []
    equity_curve = live.get("equity_curve", []) if isinstance(live.get("equity_curve"), list) else []
    pending_orders = live.get("pending_orders", []) if isinstance(live.get("pending_orders"), list) else []

    compact["tick_history_rows_by_inst"] = compact_count_by_key(tick_history)
    compact["tick_history_rows"] = sum(compact["tick_history_rows_by_inst"].values())
    compact["tick_history_tail"] = compact_tail_by_key(tick_history, 3)
    compact.pop("tick_history", None)

    compact["seen_trade_ids_by_inst"] = compact_count_by_key(seen_trade_ids)
    compact["seen_trade_ids_count"] = sum(compact["seen_trade_ids_by_inst"].values())
    compact.pop("seen_trade_ids", None)

    compact["cycle_count_persisted"] = len(cycles)
    compact["cycles_tail"] = [compact_paper_cycle_for_response(cycle) for cycle in cycles[-3:]]
    compact.pop("cycles", None)

    compact["equity_curve_count"] = len(equity_curve)
    compact["equity_curve_tail"] = copy.deepcopy(equity_curve[-30:])
    compact.pop("equity_curve", None)

    compact["pending_order_count"] = len(pending_orders)
    compact["pending_orders"] = copy.deepcopy(pending_orders[-50:])
    return compact


def compact_okx_auto_record_for_response(record: Any) -> dict[str, Any]:
    """Keep OKX auto-submit rows table-sized.

    Full candidate plans, tradeability checks and raw OKX responses are already
    preserved in the execution trace and broker audit journals.  Polling views
    only need enough fields to render state, price/size, cost and error text.
    """
    if not isinstance(record, dict):
        return {}
    order = record.get("order", {}) if isinstance(record.get("order"), dict) else {}
    result = record.get("result", {}) if isinstance(record.get("result"), dict) else {}
    detail = result.get("order_detail", {}) if isinstance(result.get("order_detail"), dict) else {}
    raw_result = result.get("result", {}) if isinstance(result.get("result"), dict) else {}
    candidate = record.get("candidate", {}) if isinstance(record.get("candidate"), dict) else {}
    forecast = candidate.get("execution_forecast", {}) if isinstance(candidate.get("execution_forecast"), dict) else {}
    tradeability = record.get("tradeability", {}) if isinstance(record.get("tradeability"), dict) else {}
    if not tradeability and isinstance(candidate.get("tradeability"), dict):
        tradeability = candidate.get("tradeability", {})
    # Fallback: for guarded/blocked entries, extract order/side/price from candidate
    if not order and isinstance(candidate.get("order"), dict):
        order = candidate["order"]
    if not detail and isinstance(candidate.get("source_order"), dict):
        src = candidate["source_order"]
        inst = src.get("instrument", {}) if isinstance(src.get("instrument"), dict) else {}
        detail = {
            "inst_id": inst.get("symbol", inst.get("key", candidate.get("inst_id", ""))),
            "side": src.get("side", order.get("side", "")),
        }
    return {
        "at": record.get("at", ""),
        "status": record.get("status", ""),
        "source_order_id": record.get("source_order_id", ""),
        "execution_trace_id": record.get("execution_trace_id", ""),
        "audit_id": record.get("audit_id", ""),
        "message": record.get("message", ""),
        "last_order_sync_at": record.get("last_order_sync_at", ""),
        "sync_status": record.get("sync_status", ""),
        "order": {
            key: copy.deepcopy(order.get(key))
            for key in ["instId", "tdMode", "side", "ordType", "px", "sz", "posSide", "reduceOnly"]
            if key in order
        },
        "result": {
            "ok": bool(result.get("ok")),
            "audit_id": result.get("audit_id", ""),
            "error": result.get("error", ""),
            "error_summary": copy.deepcopy(result.get("error_summary", {})) if isinstance(result.get("error_summary"), dict) else {},
            "order_detail": {
                key: copy.deepcopy(detail.get(key))
                for key in [
                    "ord_id",
                    "cl_ord_id",
                    "inst_id",
                    "side",
                    "ord_type",
                    "px",
                    "sz",
                    "state",
                    "acc_fill_sz",
                    "avg_px",
                ]
                if key in detail
            },
            "result": {
                key: copy.deepcopy(raw_result.get(key))
                for key in ["ordId", "ord_id", "clOrdId", "sCode", "sMsg"]
                if key in raw_result
            },
        },
        "tradeability": {"status": tradeability.get("status", "")},
        "candidate": {
            "approved": bool(candidate.get("approved")),
            "message": candidate.get("message", ""),
            "tradeability_status": candidate.get("tradeability_status", tradeability.get("status", "")),
            "planned_notional": candidate.get("planned_notional", 0.0),
            "scale": candidate.get("scale", 0.0),
            "execution_forecast": {
                "expected_cost_usdt": forecast.get("expected_cost_usdt", 0.0),
                "expected_cost_bps": forecast.get("expected_cost_bps", 0.0),
            },
        },
    }


def compact_okx_auto_submit_for_response(auto: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(auto, dict):
        return {}
    heavy_keys = {
        "submitted_source_order_ids",
        "attempted_source_order_ids",
        "recent",
        "last_tradeability",
        "last_execution_forecast",
    }
    response = {
        key: copy.deepcopy(value)
        for key, value in auto.items()
        if key not in heavy_keys
    }
    attempted = list(auto.get("attempted_source_order_ids", []) or [])
    submitted = list(auto.get("submitted_source_order_ids", []) or [])
    recent = list(auto.get("recent", []) or [])
    response["attempted_source_order_count"] = len(attempted)
    response["submitted_source_order_count"] = len(submitted)
    response["attempted_source_order_ids"] = attempted[-50:]
    response["submitted_source_order_ids"] = submitted[-50:]
    response["recent"] = [compact_okx_auto_record_for_response(item) for item in recent[-30:]]
    if isinstance(auto.get("submission_guard"), dict):
        response["submission_guard"] = compact_submission_guard_for_response(auto["submission_guard"])
    if isinstance(auto.get("last_tradeability"), dict):
        response["last_tradeability"] = {
            "summary": copy.deepcopy(auto["last_tradeability"].get("summary", {})),
            "block_warnings": bool(auto["last_tradeability"].get("block_warnings")),
        }
    if isinstance(auto.get("last_execution_forecast"), dict):
        forecast = auto["last_execution_forecast"]
        response["last_execution_forecast"] = {
            "candidate_count": forecast.get("candidate_count", 0),
            "total_expected_cost_usdt": forecast.get("total_expected_cost_usdt", 0.0),
            "weighted_expected_cost_bps": forecast.get("weighted_expected_cost_bps", 0.0),
            "max_expected_cost_bps": forecast.get("max_expected_cost_bps", 0.0),
        }
    return response


def compact_realtime_status_for_response(payload: dict[str, Any], event_tail: int = 0) -> dict[str, Any]:
    """Trim C++ realtime bridge payloads for polling responses.

    Dedicated realtime endpoints can still return the event tail.  Paper/risk
    health panels only need the current status, latest quality report and file
    freshness, so they should not carry repeated event rows on every poll.
    """
    if not isinstance(payload, dict):
        return {}
    response = {
        key: copy.deepcopy(payload.get(key))
        for key in ["ok", "mode", "message", "binaries", "status", "quality", "files"]
        if key in payload
    }
    events = payload.get("events", []) if isinstance(payload.get("events"), list) else []
    response["event_count"] = len(events)
    if event_tail > 0:
        response["events"] = copy.deepcopy(events[-event_tail:])
    return response


def compact_data_quality_for_response(
    data_quality: dict[str, Any],
    *,
    include_rows: bool = True,
    include_realtime: bool = True,
) -> dict[str, Any]:
    if not isinstance(data_quality, dict):
        return {}
    response = {
        key: copy.deepcopy(value)
        for key, value in data_quality.items()
        if key not in {"cxx_realtime", "rows"}
    }
    if include_realtime:
        response["cxx_realtime"] = compact_realtime_status_for_response(
            data_quality.get("cxx_realtime", {}) if isinstance(data_quality.get("cxx_realtime"), dict) else {}
        )
    else:
        response.pop("cxx_runner", None)
    rows = data_quality.get("rows", []) if isinstance(data_quality.get("rows"), list) else []
    response["row_count"] = len(rows)
    if include_rows:
        response["rows"] = copy.deepcopy(rows)
    return response


def compact_submission_guard_for_response(guard: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(guard, dict):
        return {}
    engine_guard = guard.get("engine_guard", {}) if isinstance(guard.get("engine_guard"), dict) else {}
    provenance = guard.get("data_provenance", {}) if isinstance(guard.get("data_provenance"), dict) else {}
    account_mode_guard = guard.get("account_mode_guard", {}) if isinstance(guard.get("account_mode_guard"), dict) else {}
    return {
        "ready": bool(guard.get("ready")),
        "reason": guard.get("reason", ""),
        "max_live_orders": guard.get("max_live_orders"),
        "live_order_count": guard.get("live_order_count"),
        "stale_order_count": guard.get("stale_order_count"),
        "stale_live_limit_seconds": guard.get("stale_live_limit_seconds"),
        "engine_guard": {
            "ready": bool(engine_guard.get("ready")),
            "reason": engine_guard.get("reason", ""),
            "market_latency_ms": engine_guard.get("market_latency_ms"),
            "max_market_latency_ms": engine_guard.get("max_market_latency_ms"),
            "runtime_ms": engine_guard.get("runtime_ms"),
            "max_runtime_ms": engine_guard.get("max_runtime_ms"),
            "require_stream": bool(engine_guard.get("require_stream")),
            "source_count": engine_guard.get("source_count"),
            "non_stream_sources": engine_guard.get("non_stream_sources", []),
            "cxx_quality": engine_guard.get("cxx_quality", {}),
        },
        "account_mode_guard": {
            "ok": bool(account_mode_guard.get("ok", True)),
            "message": account_mode_guard.get("message", ""),
            "cooldown_seconds": account_mode_guard.get("cooldown_seconds"),
            "latest_age_seconds": account_mode_guard.get("latest_age_seconds"),
            "latest_error_key": account_mode_guard.get("latest_error_key", ""),
            "latest_trace_id": account_mode_guard.get("latest_trace_id", ""),
        },
        "data_provenance": {
            "execution_ready": bool(provenance.get("execution_ready", True)),
            "status": provenance.get("status", ""),
            "reason": provenance.get("reason", ""),
            "summary": provenance.get("summary", {}),
        },
    }


def compact_health_payload_for_response(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return {
        key: copy.deepcopy(payload.get(key))
        for key in ["ok", "status", "generated_at", "summary", "checks", "journal_path"]
        if key in payload
    }


def compact_okx_status_for_response(okx: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(okx, dict):
        return {}
    instruments = okx.get("instruments", []) if isinstance(okx.get("instruments"), list) else []
    response = {
        key: copy.deepcopy(okx.get(key))
        for key in [
            "broker_name",
            "base_url",
            "base_urls",
            "request_timeout_seconds",
            "key_configured",
            "secret_configured",
            "passphrase_configured",
            "configured",
            "simulated",
            "trading_enabled",
            "key_source",
            "secret_source",
            "passphrase_source",
            "state",
            "message",
        ]
        if key in okx
    }
    response["instrument_count"] = len(instruments)
    return response


def compact_risk_status_for_response(risk: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(risk, dict):
        return {}
    return {
        key: copy.deepcopy(risk.get(key))
        for key in ["ok", "status", "state", "checks", "limits", "summary"]
        if key in risk
    }


def compact_paper_state_for_response(state: dict[str, Any]) -> dict[str, Any]:
    response = {
        key: copy.deepcopy(value)
        for key, value in state.items()
        if key not in {"live", "okx_auto_submit"}
    } if isinstance(state, dict) else {}
    live = response.get("live", {}) if isinstance(response.get("live"), dict) else {}
    source_live = state.get("live", {}) if isinstance(state, dict) and isinstance(state.get("live"), dict) else live
    response["live"] = compact_live_paper_state_for_response(source_live)
    source_auto = state.get("okx_auto_submit", {}) if isinstance(state, dict) and isinstance(state.get("okx_auto_submit"), dict) else {}
    response["okx_auto_submit"] = compact_okx_auto_submit_for_response(source_auto)
    if isinstance(response.get("data_quality"), dict):
        response["data_quality"] = compact_data_quality_for_response(response["data_quality"], include_rows=True)
    return response


def compact_paper_run_for_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Trim a tick/run payload for HTTP responses while preserving the outcome."""
    if not isinstance(payload, dict):
        return {}
    keys = [
        "ok",
        "stage",
        "skipped",
        "reason",
        "output",
        "runtime_ms",
        "crypto",
        "summary",
        "error",
    ]
    response = {key: copy.deepcopy(payload[key]) for key in keys if key in payload}
    report = payload.get("report", {}) if isinstance(payload.get("report"), dict) else {}
    if report:
        cycles = report.get("cycles", []) if isinstance(report.get("cycles"), list) else []
        equity_curve = report.get("equity_curve", []) if isinstance(report.get("equity_curve"), list) else []
        response["report"] = {
            "summary": copy.deepcopy(report.get("summary", {})),
            "cycles_count": len(cycles),
            "equity_curve_count": len(equity_curve),
            "latest_cycle": latest_cycle_snapshot(report),
        }
    if isinstance(payload.get("live"), dict):
        response["live"] = compact_live_paper_state_for_response(payload["live"])
    return response


def paper_thread_alive() -> bool:
    return PAPER_THREAD is not None and PAPER_THREAD.is_alive()


def default_ops_state() -> dict[str, Any]:
    return {
        "automation_freeze": False,
        "reason": "",
        "updated_at": "",
        "updated_by": "platform",
    }


def read_ops_state() -> dict[str, Any]:
    if not OPS_STATE_PATH.exists():
        return default_ops_state()
    try:
        saved = json.loads(OPS_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        saved = {}
    state = default_ops_state()
    state.update(saved if isinstance(saved, dict) else {})
    state["automation_freeze"] = bool(state.get("automation_freeze"))
    return state


def write_ops_state(automation_freeze: bool, reason: str, updated_by: str = "platform") -> dict[str, Any]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    state_data = read_ops_state()
    state = {
        "automation_freeze": bool(automation_freeze),
        "reason": str(reason or ""),
        "updated_at": now_iso(),
        "updated_by": updated_by,
        "frozen_at": state_data.get("frozen_at", ""),
    }
    if automation_freeze and not state["frozen_at"]:
        state["frozen_at"] = now_iso()
    elif not automation_freeze:
        state["frozen_at"] = ""
    OPS_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state


def ops_automation_freeze_check() -> dict[str, Any]:
    state = read_ops_state()
    frozen = bool(state.get("automation_freeze"))
    if frozen:
        frozen_at = str(state.get("frozen_at", ""))
        if frozen_at:
            try:
                frozen_dt = datetime.fromisoformat(frozen_at)
                age = (datetime.now(datetime.timezone.utc) - frozen_dt).total_seconds()
                if age > 30 * 60:
                    frozen = False
            except (ValueError, TypeError):
                pass
    return paper_health_check(
        "自动化冻结",
        not frozen,
        "halt",
        state.get("reason") or "已冻结，新的策略 tick 和自动提交会被阻断。"
        if frozen
        else "未冻结。",
        updated_at=state.get("updated_at", ""),
        updated_by=state.get("updated_by", ""),
    )


def automation_freeze_skip_payload(state: dict[str, Any], reason: str) -> dict[str, Any]:
    with PAPER_LOCK:
        current = read_paper_state()
        current["tick_running"] = False
        current["last_skip_reason"] = reason
        current["last_runtime_at"] = now_iso()
        write_paper_state(current)
    append_platform_event_throttled(
        "ops.automation_frozen_tick_skipped",
        "ops",
        {"paper_status": current.get("status", ""), "reason": reason},
        throttle_key="ops.automation_frozen_tick_skipped",
        min_interval_seconds=30,
        severity="warn",
        message=reason,
    )
    return {
        "ok": True,
        "skipped": True,
        "reason": reason,
        "output": f"Paper tick skipped: {reason}\n",
        "paper": compact_paper_state_for_response(current),
        "run": {"ok": True, "skipped": True, "reason": reason, "output": f"Paper tick skipped: {reason}\n"},
        "markers": read_paper_markers(limit=300),
    }


def ensure_automation_not_frozen(action: str) -> None:
    state = read_ops_state()
    if state.get("automation_freeze"):
        frozen_at = str(state.get("frozen_at", ""))
        if frozen_at:
            try:
                frozen_dt = datetime.fromisoformat(frozen_at)
                age = (datetime.now(datetime.timezone.utc) - frozen_dt).total_seconds()
                if age > 30 * 60:
                    return
            except (ValueError, TypeError):
                pass
        reason = state.get("reason") or "自动化冻结已开启。"
        raise ValueError(f"{action} 已被自动化冻结阻断：{reason}")






# ---- Market stream alignment for paper trading ----
def paper_market_stream_instruments(settings: dict[str, Any]) -> list[str]:
    """Return OKX public WS instruments required by the current paper runner."""
    instruments = [
        str(item).upper().strip()
        for item in settings.get("instruments", []) or []
        if str(item).strip()
    ] or okx_instruments_config()
    if paper_derivatives_enabled(settings):
        inst_type = paper_derivatives_inst_type(settings)
        mapped = [okx_derivative_inst_id(inst_id, inst_type) for inst_id in instruments]
        effective = set(okx_effective_instruments_for_type(inst_type))
        if effective:
            mapped = [inst_id for inst_id in mapped if inst_id in effective] or mapped
        instruments = mapped
    result: list[str] = []
    seen: set[str] = set()
    for inst_id in instruments:
        if inst_id and inst_id not in seen:
            result.append(inst_id)
            seen.add(inst_id)
        if len(result) >= OKX_MAX_RUNTIME_INSTRUMENTS:
            break
    return result


def ensure_paper_market_stream(settings: dict[str, Any]) -> dict[str, Any]:
    required_instruments = paper_market_stream_instruments(settings)
    required_channels = ["trades", "tickers", "books5"]
    stream = market_stream_snapshot()
    current_instruments = {str(item).upper().strip() for item in stream.get("instruments", []) or []}
    missing = [inst_id for inst_id in required_instruments if inst_id not in current_instruments]
    running = bool(stream.get("running")) and str(stream.get("status", "")) in {"running", "subscribing", "connecting"}
    if running and not missing:
        return {
            "ready": True,
            "action": "already_running",
            "message": "OKX 公共行情流已覆盖当前虚拟盘标的。",
            "instruments": required_instruments,
            "missing_instruments": [],
            "stream": compact_market_stream_for_response(stream),
        }

    if running:
        market_stream_stop_payload({"source": "paper_market_stream_realign"})
        time.sleep(0.5)

    payload = market_stream_start_payload(
        {
            "instIds": ",".join(required_instruments),
            "channels": required_channels,
            "environment": "auto",
        }
    )
    stream = payload.get("stream", {}) if isinstance(payload.get("stream"), dict) else market_stream_snapshot()
    return {
        "ready": bool(payload.get("ok")),
        "action": "started" if payload.get("ok") else "start_failed",
        "message": payload.get("message", "OKX 公共行情流启动结果未知。"),
        "instruments": required_instruments,
        "missing_instruments": [],
        "stream": compact_market_stream_for_response(stream),
    }

def live_find_weight(portfolio: dict[str, Any], instrument: dict[str, Any]) -> float:
    """查找当前持仓权重（与 live_position_key 一致的匹配逻辑）"""
    target_key = live_position_key({"instrument": instrument}) if isinstance(instrument, dict) else str(instrument).upper().strip()
    positions = portfolio.get("positions", []) if isinstance(portfolio, dict) else []
    for p in positions:
        if not isinstance(p, dict): continue
        if live_position_key(p) == target_key:
            return float(p.get("weight", p.get("target_weight", 0.0)) or 0.0)
    return 0.0

def paper_market_stream_guard(settings: dict[str, Any], stream: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    stream = stream if isinstance(stream, dict) else market_stream_snapshot()
    required_instruments = paper_market_stream_instruments(settings)
    required_channels = {"trades", "tickers", "books5"}
    stream_instruments = {str(item).upper().strip() for item in stream.get("instruments", []) or []}
    stream_channels = {str(item) for item in stream.get("channels", []) or []}
    missing_instruments = [inst_id for inst_id in required_instruments if inst_id not in stream_instruments]
    missing_channels = sorted(required_channels - stream_channels)
    running = bool(stream.get("running")) and str(stream.get("status", "")) == "running"
    coverage_ok = running and not missing_instruments and not missing_channels
    return {
        "ready": coverage_ok,
        "coverage_ok": coverage_ok,
        "running": running,
        "status": stream.get("status", ""),
        "message": "OKX 公共行情流覆盖当前虚拟盘标的。"
        if coverage_ok
        else "OKX 公共行情流缺少覆盖："
        + ", ".join(missing_instruments + missing_channels or [str(stream.get("status", "-"))]),
        "instruments": required_instruments,
        "missing_instruments": missing_instruments,
        "missing_channels": missing_channels,
        "fresh_limit_seconds": max(15.0, float(paper_worker_poll_seconds(settings)) * 3.0),
    }

def cxx_market_quality_source_is_okx_public(source: str) -> bool:
    expected = root_relative(MARKET_STREAM_JOURNAL_PATH)
    normalized = source.strip()
    return (
        normalized == expected
        or normalized == str(MARKET_STREAM_JOURNAL_PATH)
        or normalized.endswith("/" + expected)
        or normalized.endswith("logs/market_stream/okx_public.jsonl")
    )

def cxx_market_quality_guard(settings: dict[str, Any]) -> dict[str, Any]:
    report = read_json_file(MARKET_QUALITY_LATEST_PATH)
    max_tick_age_ms = bounded_int(
        settings.get("okx_auto_max_market_latency_ms", 30000),
        30000,
        1000,
        300000,
    )
    poll_seconds = max(float(paper_worker_poll_seconds(settings)), 1.0)
    max_report_age_seconds = max(30.0, poll_seconds * 3.0)
    generated_ms = int(float_from_any(report.get("generated_at_ms"), 0.0)) if report else 0
    now_ms = int(time.time() * 1000)
    age_seconds = (now_ms - generated_ms) / 1000.0 if generated_ms > 0 else None
    tick_age_ms = float_from_any(report.get("last_tick_age_ms"), 0.0) if report else 0.0
    source = str(report.get("source", "")) if report else ""
    decision = str(report.get("decision", "")) if report else "block"
    report_ok = bool(report.get("ok")) if report else False
    source_ok = bool(source and cxx_market_quality_source_is_okx_public(source))
    report_fresh = age_seconds is not None and age_seconds <= max_report_age_seconds
    tick_fresh = tick_age_ms <= float(max_tick_age_ms) if tick_age_ms > 0 else False
    decision_ok = report_ok and decision != "block"

    checks = [
        paper_health_check(
            "C++质量报告存在",
            bool(report),
            "halt",
            "已读取 C++ 行情质量报告。" if report else "缺少 C++ 行情质量报告。",
            path=str(MARKET_QUALITY_LATEST_PATH),
        ),
        paper_health_check(
            "C++报告来源",
            source_ok,
            "halt",
            "报告来自 OKX 公共行情 journal。"
            if source_ok
            else f"报告来源不是 OKX 公共行情 journal：{source or '-'}。",
            source=source,
            expected=root_relative(MARKET_STREAM_JOURNAL_PATH),
        ),
        paper_health_check(
            "C++报告新鲜度",
            report_fresh,
            "halt",
            f"报告 {age_seconds:.1f}s 前生成，上限 {max_report_age_seconds:.1f}s。"
            if age_seconds is not None
            else "报告缺少 generated_at_ms。",
            age_seconds=age_seconds,
            max_age_seconds=max_report_age_seconds,
        ),
        paper_health_check(
            "C++ tick 新鲜度",
            tick_fresh,
            "halt",
            f"最新 tick age={tick_age_ms:.0f}ms，上限 {max_tick_age_ms}ms。"
            if tick_age_ms > 0
            else "报告缺少 last_tick_age_ms。",
            last_tick_age_ms=tick_age_ms,
            max_tick_age_ms=max_tick_age_ms,
        ),
        paper_health_check(
            "C++质量判定",
            decision_ok,
            "halt",
            str(report.get("reason", "C++ 判定通过。")) if decision_ok else str(report.get("reason", "C++ 行情质量判定阻断。")),
            decision=decision,
            report_ok=report_ok,
        ),
    ]
    ready = all(item.get("ok") for item in checks)
    message = "C++ 行情质量报告通过。" if ready else next(
        (str(item.get("message", "")) for item in checks if not item.get("ok")),
        "C++ 行情质量报告未通过。",
    )
    return {
        "ready": ready,
        "active": True,
        "decision": "allow" if ready else "block",
        "message": message,
        "source": source,
        "age_seconds": age_seconds,
        "max_age_seconds": max_report_age_seconds,
        "last_tick_age_ms": tick_age_ms,
        "max_tick_age_ms": max_tick_age_ms,
        "checks": checks,
        "report": {
            "decision": decision,
            "reason": report.get("reason", "") if report else "",
            "generated_at_ms": generated_ms,
            "source": source,
            "summary": report.get("summary", {}) if isinstance(report.get("summary"), dict) else {},
        },
    }


def wait_for_cxx_market_quality_ready(
    settings: dict[str, Any],
    timeout_seconds: float = 8.0,
    interval_seconds: float = 0.5,
) -> dict[str, Any]:
    """Wait briefly for the C++ watch runner to replace stale quality reports.

    启动虚拟盘时，C++ runner 可能刚被拉起，而旧的
    `logs/market_quality/latest.json` 还停留在上一轮进程。这里做一个短暂
    warm-up，避免 runner 第一个 tick 因旧报告被软阻断。
    """
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    latest = cxx_market_quality_guard(settings)
    while not latest.get("ready") and time.monotonic() < deadline:
        time.sleep(max(0.05, interval_seconds))
        latest = cxx_market_quality_guard(settings)
    return latest

# ---- realtime engine runner ----
def ensure_realtime_engine_runner_for_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Keep the C++ read-only quality runner aligned with tick paper trading.

    The Python platform still owns the browser API and OKX simulated-order
    submitter, but tick-mode strategy cycles should only run when the C++
    realtime quality loop is watching the append-only OKX public journal.
    """
    mode = str(settings.get("mode", "tick")).strip().lower()
    required = mode in {"tick", "realtime"}
    current = realtime_engine_runner_state()
    if not required:
        return {
            "required": False,
            "ready": True,
            "running": bool(current.get("running")),
            "started": False,
            "action": "not_required",
            "message": "当前不是逐笔/实时模式，不要求 C++ 常驻行情质量 runner。",
            "runner": current,
        }
    if current.get("running"):
        quality = wait_for_cxx_market_quality_ready(settings, timeout_seconds=3.0)
        return {
            "required": True,
            "ready": bool(quality.get("ready")),
            "running": True,
            "started": False,
            "action": "already_running",
            "message": "C++ 常驻行情质量 runner 已在运行。"
            if quality.get("ready")
            else f"C++ runner 运行中，但质量报告暂未就绪：{quality.get('message', '-')}",
            "runner": current,
            "quality": quality,
        }

    max_tick_age_ms = bounded_int(settings.get("okx_auto_max_market_latency_ms", 30000), 30000, 1000, 300000)
    quality_poll_ms = min(max(max_tick_age_ms // 10, 1000), 5000)
    result = start_realtime_engine_runner_payload(
        {
            "confirm": "START_CXX_REALTIME_WATCH",
            "max_ticks": 1000,
            # C++ 行情质量 runner 是门禁心跳，不应该跟 60s 策略周期绑定。
            # 1-5s 级轮询能让启动预检尽快看到新 OKX 公共行情报告。
            "poll_ms": quality_poll_ms,
            "max_tick_age_ms": max_tick_age_ms,
            "idle_block_ms": max_tick_age_ms,
        }
    )
    runner = result.get("runner", {}) if isinstance(result.get("runner"), dict) else {}
    running = bool(runner.get("running"))
    quality = wait_for_cxx_market_quality_ready(settings, timeout_seconds=8.0) if running else cxx_market_quality_guard(settings)
    return {
        "required": True,
        "ready": running and bool(quality.get("ready")),
        "running": running,
        "started": bool(result.get("started")),
        "action": "started" if running and result.get("started") else "start_failed",
        "message": "C++ 常驻行情质量 runner 已自动启动，质量报告已就绪。"
        if running and quality.get("ready")
        else "C++ 常驻行情质量 runner 已启动，但质量报告仍在等待新 tick。"
        if running
        else str(result.get("error", "C++ 常驻行情质量 runner 启动失败。")),
        "runner": runner,
        "result_ok": bool(result.get("ok")),
        "quality": quality,
    }


def paper_settings_from_body(body: dict[str, Any]) -> dict[str, Any]:
    profile = build_crypto_run_profile(
        body,
        default_days=1,
        max_instruments=OKX_MAX_RUNTIME_INSTRUMENTS,
        limit_label="逐笔虚拟盘",
    )
    mode = str(body.get("mode", body.get("run_mode", body.get("runMode", "realtime")))).strip().lower()
    if mode not in {"tick", "realtime", "replay"}:
        mode = "tick"
    poll_default = 2 if mode == "tick" else 60
    poll_min = 1 if mode == "tick" else 15
    poll_max = 60 if mode == "tick" else 3600
    poll_seconds = bounded_int(
        body.get("poll_seconds", body.get("pollSeconds", poll_default)),
        poll_default,
        poll_min,
        poll_max,
    )
    auto_required = paper_okx_auto_submission_required()
    auto_submit = bool_setting_from_any(body.get("okx_auto_submit", body.get("okxAutoSubmit", auto_required)), auto_required)
    auto_confirm = str(body.get("okx_auto_confirm", body.get("okxAutoConfirm", ""))).strip()
    local_debug_confirm = str(body.get("local_paper_confirm", body.get("localPaperConfirm", ""))).strip()
    if auto_required and not auto_submit and local_debug_confirm != PAPER_LOCAL_DEBUG_CONFIRM:
        raise ValueError("虚拟盘必须挂到 OKX 模拟盘；请启用“自动提交模拟盘”。")
    if auto_submit and auto_confirm != PAPER_OKX_AUTO_CONFIRM:
        raise ValueError(f"开启 OKX 自动提交必须带 okx_auto_confirm={PAPER_OKX_AUTO_CONFIRM}")
    auto_max_notional = float_from_any(body.get("okx_auto_max_notional", body.get("okxAutoMaxNotional", 1)), 1.0)
    auto_max_orders = bounded_int(body.get("okx_auto_max_orders", body.get("okxAutoMaxOrders", 1)), 1, 1, 20)
    auto_max_live_orders = bounded_int(
        body.get("okx_auto_max_live_orders", body.get("okxAutoMaxLiveOrders", 10)),
        10,
        1,
        20,
    )
    auto_max_live_orders = paper_okx_max_live_orders({"okx_auto_max_live_orders": auto_max_live_orders})
    auto_max_market_latency_ms = bounded_int(
        body.get("okx_auto_max_market_latency_ms", body.get("okxAutoMaxMarketLatencyMs", 30000)),
        30000,
        1000,
        300000,
    )
    auto_max_runtime_ms = bounded_int(
        body.get("okx_auto_max_runtime_ms", body.get("okxAutoMaxRuntimeMs", 5000)),
        5000,
        100,
        60000,
    )
    auto_require_stream = bool_setting_from_any(body.get("okx_auto_require_stream", body.get("okxAutoRequireStream", "false")), False)
    auto_block_tradeability_warn = bool_setting_from_any(
        body.get("okx_auto_block_tradeability_warn", body.get("okxAutoBlockTradeabilityWarn", "false")),
        False,
    )
    auto_cancel_stale_orders = bool_setting_from_any(
        body.get("okx_auto_cancel_stale_orders", body.get("okxAutoCancelStaleOrders", "true")),
        True,
    )
    auto_cancel_min_age_seconds = bounded_int(
        body.get("okx_auto_cancel_min_age_seconds", body.get("okxAutoCancelMinAgeSeconds", 180)),
        180,
        30,
        86400,
    )
    auto_cancel_max_orders = bounded_int(
        body.get("okx_auto_cancel_max_orders", body.get("okxAutoCancelMaxOrders", 5)),
        5,
        1,
        50,
    )
    local_repair_stale_orders = bool_setting_from_any(
        body.get("paper_local_repair_stale_orders", body.get("paperLocalRepairStaleOrders", "true")),
        True,
    )
    local_repair_min_age_seconds = bounded_int(
        body.get("paper_local_repair_min_age_seconds", body.get("paperLocalRepairMinAgeSeconds", 300)),
        300,
        30,
        86400,
    )
    local_repair_max_orders = bounded_int(
        body.get("paper_local_repair_max_orders", body.get("paperLocalRepairMaxOrders", 20)),
        20,
        1,
        200,
    )
    broker_fill_backfill = bool_setting_from_any(
        body.get("paper_broker_fill_backfill", body.get("paperBrokerFillBackfill", "true")),
        True,
    )
    broker_fill_backfill_max_orders = bounded_int(
        body.get("paper_broker_fill_backfill_max_orders", body.get("paperBrokerFillBackfillMaxOrders", 50)),
        50,
        1,
        500,
    )
    broker_terminal_sync = bool_setting_from_any(
        body.get("paper_broker_terminal_sync", body.get("paperBrokerTerminalSync", "true")),
        True,
    )
    broker_terminal_sync_max_orders = bounded_int(
        body.get("paper_broker_terminal_sync_max_orders", body.get("paperBrokerTerminalSyncMaxOrders", 20)),
        20,
        1,
        200,
    )
    derivatives_enabled = bool_setting_from_any(
        body.get("derivatives_enabled", body.get("derivativesEnabled", "true")),
        True,
    )
    derivatives_enabled = paper_derivatives_enabled({"derivatives_enabled": derivatives_enabled})
    derivatives_inst_type = str(body.get("derivatives_inst_type", body.get("derivativesInstType", "SWAP"))).upper().strip()
    if derivatives_inst_type not in {"SWAP", "FUTURES"}:
        derivatives_inst_type = "SWAP"
    derivatives_margin_mode = str(body.get("derivatives_margin_mode", body.get("derivativesMarginMode", "isolated"))).lower().strip()
    if derivatives_margin_mode not in {"isolated", "cross"}:
        derivatives_margin_mode = "isolated"
    derivatives_position_mode = str(body.get("derivatives_position_mode", body.get("derivativesPositionMode", "net"))).lower().strip()
    if derivatives_position_mode not in {"net", "long_short"}:
        derivatives_position_mode = "net"
    derivatives_max_exchange_leverage = bounded_float(
        body.get("derivatives_max_exchange_leverage", body.get("derivativesMaxExchangeLeverage", 3)),
        3.0,
        1.0,
        20.0,
    )
    derivatives_max_effective_leverage = bounded_float(
        body.get("derivatives_max_effective_leverage", body.get("derivativesMaxEffectiveLeverage", 2)),
        2.0,
        0.0,
        10.0,
    )
    derivatives_max_unit_effective_leverage = bounded_float(
        body.get("derivatives_max_unit_effective_leverage", body.get("derivativesMaxUnitEffectiveLeverage", 1)),
        1.0,
        0.0,
        10.0,
    )
    trade_unit_base_notional = bounded_float(
        body.get("trade_unit_base_notional_usdt", body.get("tradeUnitBaseNotionalUsdt", 1)),
        1.0,
        0.1,
        1000.0,
    )
    trade_unit_agent_leverage_enabled = bool_setting_from_any(
        body.get("trade_unit_agent_leverage_enabled", body.get("tradeUnitAgentLeverageEnabled", "true")),
        True,
    )
    trade_unit_agent_max_step = bounded_float(
        body.get("trade_unit_agent_max_step", body.get("tradeUnitAgentMaxStep", 0.5)),
        0.5,
        0.0,
        5.0,
    )
    require_cxx_realtime_runner = bool_setting_from_any(
        body.get("require_cxx_realtime_runner", body.get("requireCxxRealtimeRunner", "false")),
        False,  # 默认不要求 C++ runner，避免阻断 tick 模式
    )
    raw_strategies = body.get("strategy_ids", body.get("strategyIds", body.get("strategies", "")))
    if isinstance(raw_strategies, list):
        strategy_ids = [str(item).strip() for item in raw_strategies if str(item).strip()]
    else:
        strategy_ids = [item.strip() for item in str(raw_strategies).split(",") if item.strip()]
    if not strategy_ids:
        strategy_ids = [item.strip() for item in parse_config().get("strategy.enabled", "").split(",") if item.strip()]
    catalog_ids = {str(item["id"]) for item in STRATEGY_CATALOG}
    unknown = [item for item in strategy_ids if item not in catalog_ids]
    if unknown:
        raise ValueError(f"未知策略：{', '.join(unknown)}")
    instrument_filter: dict[str, Any] = {}
    if derivatives_enabled and derivatives_inst_type in OKX_DERIVATIVE_INST_TYPES:
        instrument_filter = okx_filter_source_instruments_for_derivatives(
            profile["instruments"],
            derivatives_inst_type,
        )
        if instrument_filter.get("filter_applied"):
            supported = [
                str(item).upper().strip()
                for item in instrument_filter.get("supported_source_instruments", [])
                if str(item).strip()
            ]
            unsupported = instrument_filter.get("unsupported_instruments", [])
            if not supported:
                examples = " / ".join(
                    f"{item.get('inst_id', '-')}: {item.get('reason', '-')}"
                    for item in unsupported[:3]
                    if isinstance(item, dict)
                )
                raise ValueError(
                    f"所选标的没有可用 OKX {derivatives_inst_type} 合约元数据，无法启动自动提交。"
                    + (f" 样例：{examples}" if examples else "")
                )
            if unsupported:
                filtered_body = {**body, "instruments": ",".join(supported), "instIds": ",".join(supported)}
                profile = build_crypto_run_profile(
                    filtered_body,
                    default_days=1,
                    max_instruments=OKX_MAX_RUNTIME_INSTRUMENTS,
                    limit_label="逐笔虚拟盘",
                )
    return {
        "instruments": profile["instruments"],
        "bar": profile["bar"],
        "lookback_days": profile["days"],
        "max_pages": profile["max_pages"],
        "poll_seconds": poll_seconds,
        "mode": mode,
        "okx_auto_submit": auto_submit,
        "okx_auto_max_notional": max(1.0, min(auto_max_notional, 100.0)),
        "okx_auto_max_orders": auto_max_orders,
        "okx_auto_max_live_orders": auto_max_live_orders,
        "okx_auto_max_market_latency_ms": auto_max_market_latency_ms,
        "okx_auto_max_runtime_ms": auto_max_runtime_ms,
        "okx_auto_require_stream": auto_require_stream,
        "okx_auto_block_tradeability_warn": auto_block_tradeability_warn,
        "okx_auto_cancel_stale_orders": auto_cancel_stale_orders,
        "okx_auto_cancel_min_age_seconds": auto_cancel_min_age_seconds,
        "okx_auto_cancel_max_orders": auto_cancel_max_orders,
        "paper_local_repair_stale_orders": local_repair_stale_orders,
        "paper_local_repair_min_age_seconds": local_repair_min_age_seconds,
        "paper_local_repair_max_orders": local_repair_max_orders,
        "paper_broker_fill_backfill": broker_fill_backfill,
        "paper_broker_fill_backfill_max_orders": broker_fill_backfill_max_orders,
        "paper_broker_terminal_sync": broker_terminal_sync,
        "paper_broker_terminal_sync_max_orders": broker_terminal_sync_max_orders,
        "derivatives_enabled": derivatives_enabled,
        "derivatives_inst_type": derivatives_inst_type,
        "derivatives_margin_mode": derivatives_margin_mode,
        "derivatives_position_mode": derivatives_position_mode,
        "derivatives_max_exchange_leverage": derivatives_max_exchange_leverage,
        "derivatives_max_effective_leverage": derivatives_max_effective_leverage,
        "derivatives_max_unit_effective_leverage": derivatives_max_unit_effective_leverage,
        "trade_unit_base_notional_usdt": trade_unit_base_notional,
        "trade_unit_agent_leverage_enabled": trade_unit_agent_leverage_enabled,
        "trade_unit_agent_max_step": trade_unit_agent_max_step,
        "require_cxx_realtime_runner": require_cxx_realtime_runner,
        "strategy_ids": strategy_ids,
        "history_server_url": profile["history_server_url"],
        "instrument_filter": instrument_filter,
    }


def paper_run_body(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "instruments": settings.get("instruments") or okx_instruments_config(),
        "bar": settings.get("bar", "1m"),
        "lookback_days": settings.get("lookback_days", settings.get("days", 1)),
        "max_pages": settings.get("max_pages", 40),
        "strategy_ids": settings.get("strategy_ids") or settings.get("strategyIds") or [],
        "history_server_url": settings.get("history_server_url", parse_config().get("history.server_url", "http://127.0.0.1:8790")),
    }


def _write_paper_bars_csv(settings: dict[str, Any], profile: dict[str, Any], csv_path: Path) -> None:
    """从 historyd 拉取每个品种的 K 线历史（默认 3 天 1 分钟线 = ~4320 根），写入 CSV 供 C++ 引擎回放。"""
    import csv as csv_module
    import time as _time
    rows: list[list[str]] = []
    bar = str(settings.get("bar", "1m"))
    # 3 天 × 24h × 60min = 4320 bars；OKX 每页最多 300 根，需 ~15 页
    now_ms = int(_time.time() * 1000)
    bar_s = OKX_BAR_SECONDS.get(bar, 60)
    start_ms = now_ms - 3 * 24 * 3600 * 1000  # 3 天前
    max_pages = max(1, int(settings.get("max_pages", 15) or 15))
    for inst_id in settings.get("instruments", []) or []:
        params = {
            "instId": [str(inst_id).upper()],
            "bar": [bar],
            "limit": ["300"],
            "width": [str(bar_s)],  # 不聚合，每根 K 线单独保留
            "start": [str(start_ms)],
            "end": [str(now_ms)],
            "max_pages": [str(max_pages)],
        }
        payload = historyd_okx_candles_payload(params)
        for item in payload.get("bars", []) or []:
            if not isinstance(item, dict):
                continue
            rows.append([
                str(item.get("t", "0")),
                str(inst_id).upper(),
                "OKX",
                str(item.get("o", "0")),
                str(item.get("h", "0")),
                str(item.get("l", "0")),
                str(item.get("c", "0")),
                str(item.get("vol", "0")),
            ])
    # 按时间排序去重
    rows.sort(key=lambda r: r[0])
    seen: set[str] = set()
    deduped: list[list[str]] = []
    for r in rows:
        key = f"{r[0]}:{r[1]}"
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv_module.writer(f)
        w.writerow(["timestamp", "symbol", "exchange", "open", "high", "low", "close", "volume"])
        w.writerows(deduped)

def execute_paper_strategy_run(settings: dict[str, Any], run_dir: Path, build_first: bool) -> dict[str, Any]:
    profile = {
        "mode": "paper_trading",
        **build_crypto_run_profile(
            paper_run_body(settings),
            default_days=1,
            max_instruments=OKX_MAX_RUNTIME_INSTRUMENTS,
            limit_label="虚拟盘",
        ),
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    config_path = run_dir / "paper.cfg"

    # 从 historyd 拉取每个品种的完整 bar 历史，写入本地 CSV 供 C++ 引擎读取
    bars_csv_path = run_dir / "bars.csv"
    _write_paper_bars_csv(settings, profile, bars_csv_path)

    config = dict(parse_config())
    config.update(
        {
            "replay_path": root_relative(bars_csv_path),
            "history.mode": "local",
            "event_log_path": root_relative(run_dir / "events.jsonl"),
            "report_json_path": root_relative(run_dir / "report.json"),
            "print_cycles": "false",
            "print_event_stream": "false",
        }
    )
    strategy_ids = settings.get("strategy_ids") or []
    if strategy_ids:
        config["strategy.enabled"] = ",".join(str(item).strip() for item in strategy_ids if str(item).strip())
    write_config(config, path=config_path)
    payload = execute_backtest(root_relative(config_path), build_first=build_first)
    payload["crypto"] = profile
    payload["config_path"] = str(config_path)
    payload["run_dir"] = str(run_dir)
    return payload


def paper_live_settings_hash(settings: dict[str, Any]) -> str:
    payload = {
        "mode": settings.get("mode", "tick"),
        "instruments": settings.get("instruments") or [],
        "bar": settings.get("bar", "1m"),
        "poll_seconds": settings.get("poll_seconds", 2),
        "strategy_ids": settings.get("strategy_ids") or [],
        "history_server_url": settings.get("history_server_url", ""),
        "initial_cash": parse_config().get("initial_cash", "1000000"),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def new_paper_session_id() -> str:
    return f"paper-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}-{uuid4().hex[:8]}"


def default_live_paper_state(settings: dict[str, Any]) -> dict[str, Any]:
    initial_cash = float_from_any(parse_config().get("initial_cash", "1000000"), 1_000_000.0)
    return {
        "mode": settings.get("mode", "tick"),
        "session_id": new_paper_session_id(),
        "settings_hash": paper_live_settings_hash(settings),
        "initial_cash": initial_cash,
        "cash": initial_cash,
        "equity": initial_cash,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "positions": [],
        "cycle_count": 0,
        "event_count": 0,
        "next_order_seq": 0,
        "total_fills": 0,
        "total_commission": 0.0,
        "peak_equity": initial_cash,
        "max_drawdown": 0.0,
        "turnover_sum": 0.0,
        "cost_bps_sum": 0.0,
        "gross_sum": 0.0,
        "return_sum": 0.0,
        "return_square_sum": 0.0,
        "return_count": 0,
        "previous_equity": initial_cash,
        "last_processed_label": "",
        "last_processed_tick_key": "",
        "last_trade_ids": {},
        "seen_trade_ids": {},
        "tick_history": {},
        "tick_count": 0,
        "pending_orders": [],
        "cycles": [],
        "equity_curve": [],
    }


def ensure_live_paper_state(state: dict[str, Any]) -> dict[str, Any]:
    settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
    live = state.get("live", {}) if isinstance(state.get("live"), dict) else {}
    expected_hash = paper_live_settings_hash(settings)
    if live.get("settings_hash") != expected_hash:
        live = default_live_paper_state(settings)
        state["live"] = live
    elif not live.get("session_id"):
        # Existing paper state from older builds did not carry a session id.
        live["session_id"] = new_paper_session_id()
    return live


def paper_bar_seconds(settings: dict[str, Any]) -> int:
    return OKX_BAR_SECONDS.get(str(settings.get("bar", "1m")), 60)


def paper_worker_poll_seconds(settings: dict[str, Any]) -> int:
    """Return the scheduler delay for the selected paper engine mode."""
    mode = str(settings.get("mode", "realtime")).lower()
    if mode == "tick":
        return bounded_int(settings.get("poll_seconds", 2), 2, 1, 60)
    return bounded_int(settings.get("poll_seconds", 60), 60, 15, 3600)


def latest_confirmed_paper_bars(settings: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    now_ms = int(time.time() * 1000)
    bar_ms = paper_bar_seconds(settings) * 1000
    for inst_id in settings.get("instruments", []) or []:
        params = {
            "instId": [str(inst_id).upper()],
            "bar": [str(settings.get("bar", "1m"))],
            "limit": ["240"],
            "width": ["2400"],
            "max_pages": [str(settings.get("max_pages", 20))],
            "live": ["1"],
            "refresh": ["1"],
        }
        payload = historyd_okx_candles_payload(params)
        bars = [
            item for item in payload.get("bars", []) or []
            if isinstance(item, dict)
            and int(item.get("t", 0) or 0) + bar_ms <= now_ms
            and str(item.get("confirm", "1")) != "0"
        ]
        if bars:
            result[str(inst_id).upper()] = bars[-1]
    return result


def live_position_key(position: dict[str, Any]) -> str:
    instrument = position.get("instrument", {}) if isinstance(position, dict) else {}
    key = str(instrument.get("key", "")).upper()
    symbol = str(instrument.get("symbol", "")).upper()
    exchange = str(instrument.get("exchange", "")).upper()
    return key or (f"{symbol}.{exchange}" if exchange else symbol)


def live_position_for(portfolio: dict[str, Any], instrument: dict[str, Any]) -> Optional[dict[str, Any]]:
    target = live_position_key({"instrument": instrument})
    for position in portfolio.get("positions", []) or []:
        if live_position_key(position) == target:
            return position
    return None


def live_inst_id_from_instrument(instrument: dict[str, Any]) -> str:
    symbol = str(instrument.get("symbol", "")).upper()
    exchange = str(instrument.get("exchange", "")).upper()
    key = str(instrument.get("key", "")).upper()
    if exchange == "OKX" and symbol:
        return symbol
    if key.endswith(".OKX"):
        return key[:-4]
    return symbol or key


def live_portfolio_snapshot(live: dict[str, Any], bars_by_inst: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cash = float_from_any(live.get("cash"), 0.0)
    realized = float_from_any(live.get("realized_pnl"), 0.0)
    market_value_sum = 0.0
    unrealized = 0.0
    positions: list[dict[str, Any]] = []
    for raw_position in live.get("positions", []) or []:
        instrument = raw_position.get("instrument", {}) or {}
        inst_id = live_inst_id_from_instrument(instrument)
        bar = bars_by_inst.get(inst_id)
        market_price = float_from_any(bar.get("c") if bar else raw_position.get("market_price"), 0.0)
        quantity = float_from_any(raw_position.get("quantity"), 0.0)
        avg_cost = float_from_any(raw_position.get("avg_cost"), market_price)
        if abs(quantity) <= 1e-12:
            continue
        market_value = quantity * market_price
        market_value_sum += market_value
        unrealized += quantity * (market_price - avg_cost)
        positions.append(
            {
                "instrument": instrument,
                "quantity": quantity,
                "avg_cost": avg_cost,
                "market_price": market_price,
                "market_value": market_value,
            }
        )
    equity = cash + market_value_sum
    for position in positions:
        position["weight"] = 0.0 if abs(equity) <= 1e-12 else position["market_value"] / equity
    portfolio = {
        "cash": cash,
        "equity": equity,
        "cash_weight": 1.0 if abs(equity) <= 1e-12 else cash / equity,
        "realized_pnl": realized,
        "unrealized_pnl": unrealized,
        "gross_exposure": sum(abs(float_from_any(item.get("weight"))) for item in positions),
        "positions": sorted(positions, key=live_position_key),
    }
    live["equity"] = equity
    live["unrealized_pnl"] = unrealized
    live["positions"] = portfolio["positions"]
    return portfolio




def live_apply_fill(live: dict[str, Any], report: dict[str, Any]) -> None:
    qty = float_from_any(report.get("last_fill_qty"), 0.0)
    if qty <= 1e-12:
        return
    instrument = report.get("instrument", {}) or {}
    side = str(report.get("side", "Buy"))
    signed_qty = qty if side == "Buy" else -qty
    price = float_from_any(report.get("last_fill_price"), 0.0)
    commission = float_from_any(report.get("commission"), 0.0)
    realized_before = float_from_any(live.get("realized_pnl"), 0.0)
    live["cash"] = float_from_any(live.get("cash"), 0.0) - signed_qty * price - commission

    positions = live.get("positions", []) or []
    position = live_position_for({"positions": positions}, instrument)
    if position is None:
        position = {
            "instrument": instrument,
            "quantity": 0.0,
            "avg_cost": 0.0,
            "market_price": price,
            "market_value": 0.0,
            "weight": 0.0,
        }
        positions.append(position)
        live["positions"] = positions

    previous_qty = float_from_any(position.get("quantity"), 0.0)
    previous_cost = float_from_any(position.get("avg_cost"), price)
    closed_qty = 0.0
    opened_qty = 0.0
    close_gross_pnl = 0.0
    close_fee = 0.0
    fill_effect = "open" if abs(previous_qty) <= 1e-12 else "increase"
    if abs(previous_qty) <= 1e-12 or previous_qty * signed_qty > 0.0:
        new_qty = previous_qty + signed_qty
        weighted_cost = abs(previous_qty) * previous_cost + abs(signed_qty) * price
        opened_qty = abs(signed_qty)
        position["quantity"] = new_qty
        position["avg_cost"] = 0.0 if abs(new_qty) <= 1e-12 else weighted_cost / abs(new_qty)
    else:
        closed_qty = min(abs(previous_qty), abs(signed_qty))
        close_gross_pnl = closed_qty * (price - previous_cost) * (1.0 if previous_qty > 0 else -1.0)
        close_fee = commission * min(1.0, closed_qty / max(qty, 1e-12))
        live["realized_pnl"] = float_from_any(live.get("realized_pnl"), 0.0) + close_gross_pnl - close_fee
        new_qty = previous_qty + signed_qty
        opened_qty = max(abs(signed_qty) - closed_qty, 0.0)
        if opened_qty > 1e-12:
            fill_effect = "flip"
        elif abs(new_qty) <= 1e-12:
            fill_effect = "close"
        else:
            fill_effect = "reduce"
        position["quantity"] = new_qty
        if abs(new_qty) <= 1e-12:
            position["avg_cost"] = 0.0
        elif previous_qty * new_qty <= 0.0:
            position["avg_cost"] = price
    position["market_price"] = price
    report.update(
        {
            "position_effect": fill_effect,
            "pre_position_qty": previous_qty,
            "post_position_qty": float_from_any(position.get("quantity"), 0.0),
            "pre_avg_cost": previous_cost,
            "post_avg_cost": float_from_any(position.get("avg_cost"), 0.0),
            "closed_qty": closed_qty,
            "opened_qty": opened_qty,
            "close_gross_pnl": close_gross_pnl,
            "close_fee": close_fee,
            "close_net_pnl": close_gross_pnl - close_fee,
            "realized_pnl_before": realized_before,
            "realized_pnl_after": float_from_any(live.get("realized_pnl"), 0.0),
        }
    )
    live["positions"] = [item for item in live.get("positions", []) or [] if abs(float_from_any(item.get("quantity"))) > 1e-12]


def live_next_order_id(live: dict[str, Any]) -> str:
    seq = int(live.get("next_order_seq", 0) or 0) + 1
    live["next_order_seq"] = seq
    return f"RTPAPER-{seq:08d}"


def live_order_touched(order: dict[str, Any], bar: dict[str, Any]) -> bool:
    limit_price = float_from_any(order.get("limit_price"), float_from_any(order.get("reference_price"), 0.0))
    low = float_from_any(bar.get("l"), limit_price)
    high = float_from_any(bar.get("h"), limit_price)
    side = str(order.get("side", "Buy"))
    return (side == "Buy" and low <= limit_price) or (side == "Sell" and high >= limit_price)


def live_process_pending_orders(
    live: dict[str, Any],
    bars_by_inst: dict[str, dict[str, Any]],
    latest_label: str,
    config: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reports: list[dict[str, Any]] = []
    expired_orders: list[dict[str, Any]] = []
    remaining_orders: list[dict[str, Any]] = []
    max_participation = float_from_any(config.get("execution.max_participation_rate", "0.04"), 0.04)
    maker_fee_bps = float_from_any(config.get("execution.maker_fee_bps", "1.0"), 1.0)
    def expire_order(order: dict[str, Any], reason: str) -> None:
        expired_orders.append(
            {
                **order,
                "status": "Expired",
                "broker_status": "EXPIRED_MAKER",
                "expired_label": latest_label,
                "reason": reason,
            }
        )

    for order in live.get("pending_orders", []) or []:
        instrument = order.get("instrument", {}) or {}
        inst_id = live_inst_id_from_instrument(instrument)
        bar = bars_by_inst.get(inst_id)
        ttl = int(order.get("ttl_bars", 2) or 2)
        if not bar:
            # 数据暂缺时不消耗 TTL，保持挂单存活
            remaining_orders.append(order)
            continue
        if str(order.get("created_label", "")) == latest_label:
            remaining_orders.append(order)
            continue
        if not live_order_touched(order, bar):
            expire_order(order, "下一根 K 线未触价")
            continue

        quantity = float_from_any(order.get("quantity"), 0.0)
        volume_cap = max(float_from_any(bar.get("v"), 0.0), 0.0) * max_participation
        fill_qty = min(quantity, volume_cap)
        if fill_qty <= 1e-12:
            expire_order(order, "成交量上限为零")
            continue
        limit_price = float_from_any(order.get("limit_price"), float_from_any(order.get("reference_price"), 0.0))
        # 用 bar 收盘价作为实际成交价，更贴近真实模拟
        fill_price = float_from_any(bar.get("c"), limit_price)
        commission = max(1.0, fill_qty * fill_price * maker_fee_bps / 10000.0)
        attribution_fields = order_signal_attribution_fields(order)
        reports.append(
            {
                "order_id": order.get("order_id", ""),
                "paper_session_id": order.get("paper_session_id", live.get("session_id", "")),
                "instrument": instrument,
                "side": order.get("side", "Buy"),
                "last_fill_qty": fill_qty,
                "last_fill_price": fill_price,
                "cumulative_filled_qty": fill_qty,
                "remaining_qty": max(0.0, quantity - fill_qty),
                "avg_price": fill_price,
                "commission": commission,
                "slippage_bps": 0.0,
                "status": "Filled" if quantity - fill_qty <= 1e-12 else "PartiallyFilled",
                "broker_status": "REALTIME_PAPER_MAKER",
                **attribution_fields,
            }
        )
        if quantity - fill_qty > 1e-12 and ttl > 1:
            updated = dict(order)
            updated["quantity"] = quantity - fill_qty
            updated["ttl_bars"] = ttl - 1
            remaining_orders.append(updated)
    live["pending_orders"] = remaining_orders
    return reports, expired_orders


def tick_order_key(inst_id: str, trade_id: str) -> str:
    return f"{inst_id}:{trade_id}"




def append_tick_history(live: dict[str, Any], ticks_by_inst: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """Append new trades to a bounded in-memory history used by tick strategies."""
    history = live.setdefault("tick_history", {})
    for inst_id, ticks in ticks_by_inst.items():
        rows = [item for item in history.get(inst_id, []) or [] if isinstance(item, dict)]
        rows.extend(ticks)
        history[inst_id] = rows[-500:]
    live["tick_count"] = int(live.get("tick_count", 0) or 0) + sum(len(ticks) for ticks in ticks_by_inst.values())
    return history












def signal_attribution_summary(signals: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize why a target/order exists.

    Raw net score explains direction.  Weighted score is the value actually
    used by the tick target builder because it multiplies score by confidence.
    Shares use absolute weighted score so opposing strategies can both receive
    attribution before their views cancel in the final target.
    """
    rows: dict[str, dict[str, Any]] = {}
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        strategy_id = str(signal.get("strategy_id", "unknown"))
        score = float_from_any(signal.get("score"))
        confidence = bounded_float(signal.get("confidence", 0), 0.0, 0.0, 1.0)
        weighted = score * confidence
        row = rows.setdefault(
            strategy_id,
            {
                "strategy_id": strategy_id,
                "signal_count": 0,
                "net_score": 0.0,
                "weighted_score": 0.0,
                "abs_weighted_score": 0.0,
                "confidence_sum": 0.0,
            },
        )
        row["signal_count"] += 1
        row["net_score"] += score
        row["weighted_score"] += weighted
        row["abs_weighted_score"] += abs(weighted)
        row["confidence_sum"] += confidence

    total_abs_weighted = sum(float_from_any(row.get("abs_weighted_score")) for row in rows.values())
    strategies: list[dict[str, Any]] = []
    for row in rows.values():
        count = max(int(row.get("signal_count", 0) or 0), 1)
        share = (
            float_from_any(row.get("abs_weighted_score")) / total_abs_weighted
            if total_abs_weighted > 1e-12
            else 1.0 / max(len(rows), 1)
        )
        row["avg_confidence"] = float_from_any(row.get("confidence_sum")) / count
        row["share"] = share
        row["direction"] = "long" if float_from_any(row.get("weighted_score")) > 0 else "short" if float_from_any(row.get("weighted_score")) < 0 else "flat"
        strategies.append(row)
    strategies.sort(key=lambda item: float_from_any(item.get("abs_weighted_score")), reverse=True)
    return {
        "signal_count": sum(int(row.get("signal_count", 0) or 0) for row in rows.values()),
        "net_score": sum(float_from_any(row.get("net_score")) for row in rows.values()),
        "weighted_score": sum(float_from_any(row.get("weighted_score")) for row in rows.values()),
        "abs_score": sum(abs(float_from_any(row.get("net_score"))) for row in rows.values()),
        "abs_weighted_score": total_abs_weighted,
        "strategies": strategies,
    }


def signal_attribution_by_inst(signals: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        inst_id = instrument_from_report_item(signal).get("inst_id", "")
        if inst_id:
            grouped.setdefault(inst_id, []).append(signal)
    return {inst_id: signal_attribution_summary(rows) for inst_id, rows in grouped.items()}


def order_signal_attribution_fields(source: dict[str, Any], fallback: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    attribution = source.get("signal_attribution") if isinstance(source.get("signal_attribution"), list) else None
    if attribution is None and isinstance(source.get("strategy_attribution"), list):
        attribution = source.get("strategy_attribution")
    summary = fallback if isinstance(fallback, dict) else {}
    if attribution is None:
        attribution = summary.get("strategies", []) if isinstance(summary.get("strategies"), list) else []
    strategy_ids = [str(row.get("strategy_id", "")) for row in attribution if isinstance(row, dict) and row.get("strategy_id")]
    context = source_order_attribution_context(
        {**source, "strategy_attribution": attribution, "strategy_ids": strategy_ids},
        summary,
    )
    return {
        **context,
        "strategy_attribution": attribution,
        "strategy_ids": strategy_ids,
        "signal_net_score": float_from_any(source.get("signal_net_score", summary.get("net_score", 0.0))),
        "signal_weighted_score": float_from_any(source.get("signal_weighted_score", summary.get("weighted_score", 0.0))),
        "signal_abs_score": float_from_any(source.get("signal_abs_score", summary.get("abs_score", 0.0))),
        "signal_count": int(float_from_any(source.get("signal_count", summary.get("signal_count", 0)))),
    }




def live_process_pending_tick_orders(
    live: dict[str, Any],
    ticks_by_inst: dict[str, list[dict[str, Any]]],
    latest_label: str,
    config: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Match local maker orders against subsequent public trades.

    This is still a simulator: public trades do not expose our queue position.
    The fill model therefore requires price touch and caps fill size by a small
    participation rate against the observed trade size.
    """
    reports: list[dict[str, Any]] = []
    expired_orders: list[dict[str, Any]] = []
    remaining_orders: list[dict[str, Any]] = []
    max_participation = float_from_any(config.get("execution.max_participation_rate", "0.04"), 0.04)
    maker_fee_bps = float_from_any(config.get("execution.maker_fee_bps", "1.0"), 1.0)
    for order in live.get("pending_orders", []) or []:
        instrument = order.get("instrument", {}) or {}
        inst_id = live_inst_id_from_instrument(instrument)
        ticks = ticks_by_inst.get(inst_id, [])
        ttl = int(order.get("ttl_ticks", order.get("ttl_bars", 3)) or 3) - 1
        quantity_left = float_from_any(order.get("quantity"), 0.0)
        limit_price = float_from_any(order.get("limit_price"), float_from_any(order.get("reference_price"), 0.0))
        side = str(order.get("side", "Buy"))
        filled_qty = 0.0
        for tick in ticks:
            touched = (side == "Buy" and float_from_any(tick.get("price")) <= limit_price) or (
                side == "Sell" and float_from_any(tick.get("price")) >= limit_price
            )
            if not touched:
                continue
            fill_qty = min(quantity_left, float_from_any(tick.get("size")) * max_participation)
            if fill_qty <= 1e-12:
                continue
            filled_qty += fill_qty
            quantity_left -= fill_qty
            if quantity_left <= 1e-12:
                break
        if filled_qty > 1e-12:
            commission = max(0.01, filled_qty * limit_price * maker_fee_bps / 10000.0)
            attribution_fields = order_signal_attribution_fields(order)
            reports.append(
                {
                    "order_id": order.get("order_id", ""),
                    "paper_session_id": order.get("paper_session_id", live.get("session_id", "")),
                    "instrument": instrument,
                    "side": side,
                    "last_fill_qty": filled_qty,
                    "last_fill_price": limit_price,
                    "cumulative_filled_qty": filled_qty,
                    "remaining_qty": max(0.0, quantity_left),
                    "avg_price": limit_price,
                    "commission": commission,
                    "slippage_bps": 0.0,
                    "status": "Filled" if quantity_left <= 1e-12 else "PartiallyFilled",
                    "broker_status": "TICK_PAPER_MAKER",
                    **attribution_fields,
                }
            )
        if quantity_left > 1e-12 and ttl > 0:
            updated = dict(order)
            updated["quantity"] = quantity_left
            updated["ttl_ticks"] = ttl
            remaining_orders.append(updated)
        elif quantity_left > 1e-12:
            expired_orders.append({**order, "quantity": quantity_left, "status": "Expired", "broker_status": "EXPIRED_TICK_MAKER", "expired_label": latest_label, "reason": "tick TTL 到期未触价"})
    live["pending_orders"] = remaining_orders
    return reports, expired_orders


def live_summary(live: dict[str, Any]) -> dict[str, Any]:
    cycles = int(live.get("cycle_count", 0) or 0)
    equity = float_from_any(live.get("equity"), float_from_any(live.get("initial_cash"), 0.0))
    initial = max(float_from_any(live.get("initial_cash"), equity), 1e-12)
    return {
        "cycles": cycles,
        "event_count": int(live.get("event_count", 0) or 0),
        "total_fills": int(live.get("total_fills", 0) or 0),
        "total_commission": float_from_any(live.get("total_commission"), 0.0),
        "total_return": equity / initial - 1.0,
        "max_drawdown": float_from_any(live.get("max_drawdown"), 0.0),
        "annualized_sharpe": 0.0,
        "average_turnover": float_from_any(live.get("turnover_sum"), 0.0) / max(cycles, 1),
        "average_cost_bps": float_from_any(live.get("cost_bps_sum"), 0.0) / max(cycles, 1),
        "average_gross_exposure": float_from_any(live.get("gross_sum"), 0.0) / max(cycles, 1),
        "max_gross_exposure": max((float_from_any(item.get("gross_exposure"), 0.0) for item in live.get("equity_curve", []) or []), default=0.0),
        "final_equity": equity,
        "pending_orders": len(live.get("pending_orders", []) or []),
        "tick_count": int(live.get("tick_count", 0) or 0),
    }


def latest_tick_bars(live: dict[str, Any], ticks_by_inst: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """Build mark-to-market bar-like snapshots from the latest trade history."""
    bars: dict[str, dict[str, Any]] = {}
    history = live.get("tick_history", {}) if isinstance(live.get("tick_history"), dict) else {}
    for inst_id, rows in history.items():
        if not rows:
            continue
        window = rows[-40:]
        latest = window[-1]
        prices = [float_from_any(row.get("price")) for row in window]
        new_volume = sum(float_from_any(row.get("size")) for row in ticks_by_inst.get(inst_id, []))
        bars[inst_id] = {
            "t": int(latest.get("t", 0) or 0),
            "o": prices[0],
            "h": max(prices),
            "l": min(prices),
            "c": prices[-1],
            "v": new_volume if new_volume > 0 else sum(float_from_any(row.get("size")) for row in window),
            "confirm": "tick",
        }
    return bars




def paper_live_run_tick(state: dict[str, Any], run_dir: Path, build_first: bool) -> dict[str, Any]:
    settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
    live = ensure_live_paper_state(state)
    bars_by_inst = latest_confirmed_paper_bars(settings)
    if not bars_by_inst:
        report = read_latest_paper_report()
        return {
            "ok": True,
            "skipped": True,
            "reason": "暂无已闭合 K 线",
            "output": "Realtime paper tick skipped: no closed bar\n",
            "paper": state,
            "report": report,
            "summary": report.get("summary", state.get("summary", {})),
            "markers": read_paper_markers(limit=5000),
            "live": live,
        }

    latest_ts = max(int(bar.get("t", 0) or 0) for bar in bars_by_inst.values())
    latest_label = text_from_epoch_ms(latest_ts)
    if latest_label == live.get("last_processed_label"):
        live_portfolio_snapshot(live, bars_by_inst)
        report = read_latest_paper_report()
        return {
            "ok": True,
            "skipped": True,
            "reason": f"等待新 K 线：{latest_label}",
            "output": f"Realtime paper tick skipped: waiting for next closed bar after {latest_label}\n",
            "paper": state,
            "report": report,
            "summary": report.get("summary", state.get("summary", {})),
            "markers": read_paper_markers(limit=5000),
            "live": live,
        }

    payload = execute_paper_strategy_run(settings, run_dir, build_first=build_first)
    if not payload.get("ok"):
        return payload
    report = payload.get("report", {}) if isinstance(payload.get("report"), dict) else {}
    cycles = report.get("cycles", []) or []
    if not cycles:
        return {"ok": False, "output": "no strategy cycles in realtime signal report", "report": report}
    signal_cycle = next((cycle for cycle in reversed(cycles) if str(cycle.get("label", "")) == latest_label), cycles[-1])

    config = parse_config()
    pre_portfolio = live_portfolio_snapshot(live, bars_by_inst)
    reports, expired_order_records = live_process_pending_orders(live, bars_by_inst, latest_label, config)
    for report_row in reports:
        live_apply_fill(live, report_row)
    portfolio_for_targets = live_portfolio_snapshot(live, bars_by_inst)
    adjusted = (signal_cycle.get("risk_decision", {}) or {}).get("adjusted_portfolio", {}) or {}
    risk_action = str((signal_cycle.get("risk_decision", {}) or {}).get("action", ""))
    target_positions = adjusted.get("positions", []) if risk_action not in {"Reject", "Halt"} else []
    target_by_key: dict[str, dict[str, Any]] = {}
    for target in target_positions or []:
        instrument = target.get("instrument", {}) or {}
        target_by_key[live_position_key({"instrument": instrument})] = target
    for position in portfolio_for_targets.get("positions", []) or []:
        key = live_position_key(position)
        target_by_key.setdefault(key, {"instrument": position.get("instrument", {}) or {}, "target_weight": 0.0})

    min_delta = float_from_any(config.get("execution.min_rebalance_delta", "0.02"), 0.02)
    max_participation = float_from_any(config.get("execution.max_participation_rate", "0.04"), 0.04)
    maker_offset_bps = float_from_any(config.get("execution.maker_offset_bps", "2.0"), 2.0)
    maker_fee_bps = float_from_any(config.get("execution.maker_fee_bps", "1.0"), 1.0)
    pending_ttl = max(1, int(float_from_any(config.get("execution.pending_order_ttl_bars", "1"), 1.0)))
    account_equity = max(float_from_any(portfolio_for_targets.get("equity"), live.get("initial_cash")), 1.0)
    orders: list[dict[str, Any]] = []
    turnover = 0.0
    attribution_by_inst = signal_attribution_by_inst(signal_cycle.get("signals", []) if isinstance(signal_cycle.get("signals"), list) else [])

    for index, target in enumerate(target_by_key.values(), start=1):
        instrument = target.get("instrument", {}) or {}
        inst_id = live_inst_id_from_instrument(instrument)
        bar = bars_by_inst.get(inst_id)
        if not bar:
            continue
        current_weight = live_find_weight(portfolio_for_targets, instrument)
        target_weight = float_from_any(target.get("target_weight"), 0.0)
        delta = target_weight - current_weight
        if abs(delta) < min_delta:
            continue
        reference_price = max(float_from_any(bar.get("c"), 0.0), 1.0)
        side = "Buy" if delta >= 0.0 else "Sell"
        limit_price = reference_price * (1.0 - maker_offset_bps / 10000.0 if side == "Buy" else 1.0 + maker_offset_bps / 10000.0)
        desired_qty = abs(delta) * account_equity / max(limit_price, 1.0)
        volume_cap = max(float_from_any(bar.get("v"), 0.0), 0.0) * max_participation
        quantity = min(desired_qty, volume_cap) if volume_cap > 0.0 else desired_qty
        if quantity <= 1e-12:
            continue
        turnover += quantity * limit_price / account_equity
        order_id = live_next_order_id(live)
        attribution_fields = order_signal_attribution_fields(target, attribution_by_inst.get(inst_id, {}))
        order_row = {
            "order_id": order_id,
            "paper_session_id": live.get("session_id", ""),
            "instrument": instrument,
            "side": side,
            "type": "Limit",
            "quantity": quantity,
            "reference_price": limit_price,
            "limit_price": limit_price,
            "mark_price": reference_price,
            "time_in_force": "post_only",
            "parent_decision_id": "realtime-maker-rebalance",
            "status": "Pending",
            "broker_status": "PENDING_MAKER",
            **attribution_fields,
        }
        orders.append(order_row)
        live.setdefault("pending_orders", []).append(
            {
                **order_row,
                "created_label": latest_label,
                "ttl_bars": pending_ttl,
                "maker_offset_bps": maker_offset_bps,
                "maker_fee_bps": maker_fee_bps,
            }
        )

    post_portfolio = live_portfolio_snapshot(live, bars_by_inst)
    cycle_index = int(live.get("cycle_count", 0) or 0) + 1
    live["cycle_count"] = cycle_index
    live["event_count"] = int(live.get("event_count", 0) or 0) + 4 + len(orders) + len(reports) + len(expired_order_records)
    live["total_fills"] = int(live.get("total_fills", 0) or 0) + sum(1 for item in reports if float_from_any(item.get("last_fill_qty")) > 0.0)
    live["total_commission"] = float_from_any(live.get("total_commission"), 0.0) + sum(float_from_any(item.get("commission")) for item in reports)
    live["turnover_sum"] = float_from_any(live.get("turnover_sum"), 0.0) + turnover
    live["cost_bps_sum"] = float_from_any(live.get("cost_bps_sum"), 0.0) + turnover * maker_fee_bps
    live["gross_sum"] = float_from_any(live.get("gross_sum"), 0.0) + float_from_any(post_portfolio.get("gross_exposure"), 0.0)
    previous_equity = float_from_any(live.get("previous_equity"), post_portfolio.get("equity"))
    equity = float_from_any(post_portfolio.get("equity"), previous_equity)
    if previous_equity > 0.0 and cycle_index > 1:
        period_return = equity / previous_equity - 1.0
        live["return_sum"] = float_from_any(live.get("return_sum"), 0.0) + period_return
        live["return_square_sum"] = float_from_any(live.get("return_square_sum"), 0.0) + period_return * period_return
        live["return_count"] = int(live.get("return_count", 0) or 0) + 1
    live["previous_equity"] = equity
    live["peak_equity"] = max(float_from_any(live.get("peak_equity"), equity), equity)
    peak = max(float_from_any(live.get("peak_equity"), equity), 1e-12)
    live["max_drawdown"] = max(float_from_any(live.get("max_drawdown"), 0.0), (peak - equity) / peak)
    live["last_processed_label"] = latest_label

    live_cycle = {
        "cycle_index": cycle_index,
        "label": latest_label,
        "features": {
            **(signal_cycle.get("features", {}) if isinstance(signal_cycle.get("features"), dict) else {}),
            "engine": "realtime",
            "market_latency_ms": max(0, int(time.time() * 1000) - int(latest_ts)),
            "bar_timestamp_ms": latest_ts,
        },
        "regime": signal_cycle.get("regime", {}),
        "signals": signal_cycle.get("signals", []),
        "target_portfolio": signal_cycle.get("target_portfolio", {}),
        "risk_decision": signal_cycle.get("risk_decision", {}),
        "pre_trade_portfolio": pre_portfolio,
        "post_trade_portfolio": post_portfolio,
        "orders": orders,
        "order_records": [],
        "reports": reports,
        "pending_orders": live.get("pending_orders", []),
        "expired_orders": len(expired_order_records),
        "expired_order_records": expired_order_records,
    }
    live["cycles"] = (live.get("cycles", []) or [])[-999:] + [live_cycle]
    live["equity_curve"] = (live.get("equity_curve", []) or [])[-4999:] + [
        {
            "cycle_index": cycle_index,
            "label": latest_label,
            "equity": post_portfolio.get("equity"),
            "cash": post_portfolio.get("cash"),
            "gross_exposure": post_portfolio.get("gross_exposure"),
            "realized_pnl": post_portfolio.get("realized_pnl"),
            "unrealized_pnl": post_portfolio.get("unrealized_pnl"),
        }
    ]
    live_report = {
        "summary": live_summary(live),
        "equity_curve": live["equity_curve"],
        "cycles": live["cycles"],
    }
    return {
        "ok": True,
        "stage": "realtime",
        "output": f"Realtime paper tick applied: {latest_label}, orders={len(orders)}, fills={len(reports)}\n",
        "summary": live_report["summary"],
        "equity_curve": live_report["equity_curve"],
        "events": [],
        "report": live_report,
        "signal_report": report,
        "crypto": payload.get("crypto", {}),
        "config_path": payload.get("config_path", ""),
        "run_dir": payload.get("run_dir", str(run_dir)),
        "live": live,
    }


def instrument_from_report_item(item: dict[str, Any]) -> dict[str, str]:
    instrument = item.get("instrument") or item.get("intent", {}).get("instrument") or {}
    symbol = str(instrument.get("symbol", "")).upper()
    exchange = str(instrument.get("exchange", "")).upper()
    key = str(instrument.get("key", "")).upper()
    if exchange == "OKX" and symbol:
        inst_id = symbol
    elif key.endswith(".OKX"):
        inst_id = key[:-4]
    else:
        inst_id = key or (f"{symbol}.{exchange}" if exchange else symbol)
    return {"inst_id": inst_id, "key": key or inst_id}


def marker_time_ms(label: str) -> Optional[int]:
    try:
        return epoch_ms_from_text(label)
    except Exception:
        return None


def report_chart_annotations(report: dict[str, Any]) -> dict[str, Any]:
    enrich_report_fill_pnl(report)
    markers: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    equity_by_cycle = {
        int(point.get("cycle_index", 0) or 0): point
        for point in report.get("equity_curve", [])
        if isinstance(point, dict)
    }

    for cycle in report.get("cycles", []) or []:
        label = str(cycle.get("label", ""))
        timestamp = marker_time_ms(label)
        if timestamp is None:
            continue
        cycle_index = int(cycle.get("cycle_index", 0) or 0)
        equity = equity_by_cycle.get(cycle_index, {})
        risk = cycle.get("risk_decision", {}) or {}
        portfolio = cycle.get("post_trade_portfolio", {}) or {}
        metrics.append(
            {
                "t": timestamp,
                "label": label,
                "cycle_index": cycle_index,
                "equity": equity.get("equity", portfolio.get("equity")),
                "cash": equity.get("cash", portfolio.get("cash")),
                "gross_exposure": equity.get("gross_exposure", portfolio.get("gross_exposure")),
                "realized_pnl": equity.get("realized_pnl", portfolio.get("realized_pnl")),
                "unrealized_pnl": equity.get("unrealized_pnl", portfolio.get("unrealized_pnl")),
                "risk_action": risk.get("action", ""),
                "risk_reason": risk.get("reason", ""),
            }
        )

        signal_groups: dict[str, dict[str, Any]] = {}
        for signal in cycle.get("signals", []) or []:
            instrument = instrument_from_report_item(signal)
            inst_id = instrument["inst_id"]
            group = signal_groups.setdefault(
                inst_id,
                {
                    "type": "signal",
                    "t": timestamp,
                    "label": label,
                    "cycle_index": cycle_index,
                    "inst_id": inst_id,
                    "score": 0.0,
                    "confidence_sum": 0.0,
                    "strategy_count": 0,
                    "strategies": [],
                },
            )
            score = float(signal.get("score", 0.0) or 0.0)
            confidence = float(signal.get("confidence", 0.0) or 0.0)
            group["score"] += score
            group["confidence_sum"] += confidence
            group["strategy_count"] += 1
            group["strategies"].append(str(signal.get("strategy_id", "unknown")))
        for group in signal_groups.values():
            count = max(int(group.pop("strategy_count", 0) or 0), 1)
            group["confidence"] = group.pop("confidence_sum", 0.0) / count
            group["side"] = "Buy" if group["score"] >= 0 else "Sell"
            group["text"] = f"{count} 个信号，净分 {group['score']:.4f}"
            markers.append(group)

        for order in cycle.get("orders", []) or []:
            instrument = instrument_from_report_item(order)
            markers.append(
                {
                    "type": "order",
                    "t": timestamp,
                    "label": label,
                    "cycle_index": cycle_index,
                    "inst_id": instrument["inst_id"],
                    "side": order.get("side", ""),
                    "price": order.get("reference_price"),
                    "quantity": order.get("quantity"),
                    "parent_decision_id": order.get("parent_decision_id", ""),
                    "text": f"{order.get('side', '-')} 计划 {format(float(order.get('quantity', 0.0) or 0.0), '.6g')}",
                }
            )

        for expired in cycle.get("expired_order_records", []) or []:
            instrument = instrument_from_report_item(expired)
            markers.append(
                {
                    "type": "expired",
                    "t": timestamp,
                    "label": label,
                    "cycle_index": cycle_index,
                    "inst_id": instrument["inst_id"],
                    "side": expired.get("side", ""),
                    "order_id": expired.get("order_id", ""),
                    "price": expired.get("limit_price", expired.get("reference_price")),
                    "quantity": expired.get("quantity"),
                    "status": expired.get("status", "Expired"),
                    "reason": expired.get("reason", ""),
                    "text": f"{expired.get('side', '-')} 挂单过期：{expired.get('reason', '')}",
                }
            )

        for fill in cycle.get("reports", []) or []:
            if float(fill.get("last_fill_qty", 0.0) or 0.0) <= 0.0:
                continue
            instrument = instrument_from_report_item(fill)
            markers.append(
                {
                    "type": "fill",
                    "t": timestamp,
                    "label": label,
                    "cycle_index": cycle_index,
                    "inst_id": instrument["inst_id"],
                    "side": fill.get("side", ""),
                    "order_id": fill.get("order_id", ""),
                    "price": fill.get("last_fill_price"),
                    "quantity": fill.get("last_fill_qty"),
                    "avg_price": fill.get("avg_price"),
                    "commission": fill.get("commission"),
                    "slippage_bps": fill.get("slippage_bps"),
                    "position_effect": fill.get("position_effect", ""),
                    "closed_qty": fill.get("closed_qty", 0.0),
                    "close_gross_pnl": fill.get("close_gross_pnl", 0.0),
                    "close_fee": fill.get("close_fee", 0.0),
                    "close_net_pnl": fill.get("close_net_pnl", 0.0),
                    "realized_pnl_after": fill.get("realized_pnl_after", 0.0),
                    "status": fill.get("status", ""),
                    "text": (
                        f"{fill.get('side', '-')} 成交 {format(float(fill.get('last_fill_qty', 0.0) or 0.0), '.6g')}"
                        + (
                            f"，平仓盈亏 {float_from_any(fill.get('close_net_pnl')):.2f}"
                            if float_from_any(fill.get("closed_qty")) > 1e-12
                            else ""
                        )
                    ),
                }
            )

        action = str(risk.get("action", ""))
        if action and action != "Approve":
            adjusted = risk.get("adjusted_portfolio", {}) or {}
            positions = adjusted.get("positions", []) or []
            for position in positions:
                instrument = instrument_from_report_item(position)
                markers.append(
                    {
                        "type": "risk",
                        "t": timestamp,
                        "label": label,
                        "cycle_index": cycle_index,
                        "inst_id": instrument["inst_id"],
                        "risk_action": action,
                        "reason": risk.get("reason", ""),
                        "target_weight": position.get("target_weight"),
                        "gross_exposure": adjusted.get("gross_exposure"),
                        "text": f"{action}: {risk.get('reason', '')}",
                    }
                )

    markers.sort(key=lambda item: (int(item.get("t", 0)), str(item.get("type", ""))))
    if len(markers) > 20000:
        markers = markers[-20000:]
    return {
        "generated_at": now_iso(),
        "summary": report.get("summary", {}),
        "markers": markers,
        "metrics": metrics[-5000:],
    }


def filter_annotations(payload: dict[str, Any], inst_id: str = "", limit: int = 0) -> dict[str, Any]:
    value = inst_id.strip().upper()
    markers = payload.get("markers", []) or []
    if value:
        markers = [item for item in markers if str(item.get("inst_id", "")).upper() == value]
    if limit > 0:
        markers = markers[-limit:]
    metrics = payload.get("metrics", []) or []
    metrics = metrics[-limit:] if limit > 0 else metrics[-1000:]
    return {
        **payload,
        "markers": markers,
        "metrics": metrics,
        "markers_count": len(markers),
        "inst_id": value,
    }


def read_paper_markers(inst_id: str = "", limit: int = 0) -> dict[str, Any]:
    if not PAPER_MARKERS_PATH.exists():
        return filter_annotations({"generated_at": "", "summary": {}, "markers": [], "metrics": []}, inst_id, limit)
    try:
        payload = json.loads(PAPER_MARKERS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {"generated_at": "", "summary": {}, "markers": [], "metrics": []}
    return filter_annotations(payload, inst_id, limit)


def latest_cycle_snapshot(report: dict[str, Any]) -> dict[str, Any]:
    cycles = report.get("cycles", []) or []
    if not cycles:
        return {}
    cycle = cycles[-1]
    features = cycle.get("features", {}) if isinstance(cycle.get("features"), dict) else {}
    return {
        "cycle_index": cycle.get("cycle_index"),
        "label": cycle.get("label"),
        "regime": cycle.get("regime", {}),
        "risk_decision": cycle.get("risk_decision", {}),
        "signal_count": len(cycle.get("signals", []) or []),
        "order_count": len(cycle.get("orders", []) or []),
        "fill_count": len([item for item in cycle.get("reports", []) or [] if float(item.get("last_fill_qty", 0.0) or 0.0) > 0.0]),
        "engine": features.get("engine", ""),
        "runtime_ms": float_from_any(features.get("runtime_ms")),
        "market_latency_ms": float_from_any(features.get("market_latency_ms")),
        "tick_count": int(float_from_any(features.get("tick_count"))),
        "latest_tick_key": features.get("latest_tick_key", ""),
        "data_source": features.get("data_source", {}),
    }


def percentile_float(values: list[float], percentile: float) -> float:
    rows = sorted(float_from_any(value) for value in values if value is not None)
    if not rows:
        return 0.0
    index = int(math.ceil(percentile * len(rows))) - 1
    return rows[max(0, min(len(rows) - 1, index))]


def paper_performance_snapshot(report: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    live = state.get("live", {}) if isinstance(state.get("live"), dict) else {}
    cycles = [row for row in report.get("cycles", []) or [] if isinstance(row, dict)]
    recent = cycles[-200:]
    runtime_values: list[float] = []
    latency_values: list[float] = []
    tick_values: list[float] = []
    order_counts: list[float] = []
    fill_counts: list[float] = []
    expired_counts: list[float] = []
    for cycle in recent:
        features = cycle.get("features", {}) if isinstance(cycle.get("features"), dict) else {}
        runtime = float_from_any(features.get("runtime_ms"))
        latency = float_from_any(features.get("market_latency_ms"))
        if runtime > 0.0:
            runtime_values.append(runtime)
        if latency > 0.0:
            latency_values.append(latency)
        tick_values.append(float_from_any(features.get("tick_count")))
        orders = cycle.get("orders", []) or []
        reports = cycle.get("reports", []) or []
        expired = cycle.get("expired_order_records", []) or []
        order_counts.append(float(len(orders)))
        fill_counts.append(float(len([item for item in reports if float_from_any(item.get("last_fill_qty")) > 0.0])))
        expired_counts.append(float(len(expired)))

    latest = recent[-1] if recent else {}
    latest_features = latest.get("features", {}) if isinstance(latest.get("features"), dict) else {}
    source_rows = []
    for inst_id, row in (live.get("tick_data_source_by_inst", {}) or {}).items():
        if not isinstance(row, dict):
            continue
        source_rows.append(
            {
                "inst_id": inst_id,
                "source": row.get("source", ""),
                "stream_status": row.get("stream_status", ""),
                "last_trade_at": row.get("last_trade_at", ""),
                "last_trade_age_seconds": row.get("last_trade_age_seconds"),
            }
        )
    history = live.get("tick_history", {}) if isinstance(live.get("tick_history"), dict) else {}
    seen = live.get("seen_trade_ids", {}) if isinstance(live.get("seen_trade_ids"), dict) else {}
    return {
        "generated_at": now_iso(),
        "engine": latest_features.get("engine") or live.get("mode") or state.get("settings", {}).get("mode", ""),
        "sample_cycles": len(recent),
        "total_cycles": len(cycles),
        "last_runtime_ms": float_from_any(latest_features.get("runtime_ms"), float_from_any(state.get("last_runtime_ms"))),
        "avg_runtime_ms": mean_float(runtime_values),
        "p95_runtime_ms": percentile_float(runtime_values, 0.95),
        "max_runtime_ms": max(runtime_values) if runtime_values else 0.0,
        "last_market_latency_ms": float_from_any(latest_features.get("market_latency_ms"), float_from_any(state.get("last_market_latency_ms"))),
        "avg_market_latency_ms": mean_float(latency_values),
        "p95_market_latency_ms": percentile_float(latency_values, 0.95),
        "tick_count_total": int(live.get("tick_count", 0) or 0),
        "avg_ticks_per_cycle": mean_float(tick_values),
        "avg_orders_per_cycle": mean_float(order_counts),
        "avg_fills_per_cycle": mean_float(fill_counts),
        "avg_expired_per_cycle": mean_float(expired_counts),
        "pending_orders": len(live.get("pending_orders", []) or []),
        "tick_history_rows": sum(len(rows) for rows in history.values() if isinstance(rows, list)),
        "seen_trade_ids": sum(len(rows) for rows in seen.values() if isinstance(rows, list)),
        "sources": sorted(source_rows, key=lambda item: str(item.get("inst_id", ""))),
    }


def market_trade_quality(inst_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize ordering and duplicate quality for one in-memory trade buffer."""
    trade_ids = [str(row.get("trade_id", "")) for row in rows if isinstance(row, dict) and str(row.get("trade_id", ""))]
    duplicate_count = len(trade_ids) - len(set(trade_ids))
    out_of_order = 0
    previous_ts = -1
    for row in rows:
        ts = int(float_from_any(row.get("t"), 0.0))
        if previous_ts > ts:
            out_of_order += 1
        previous_ts = ts
    latest = rows[-1] if rows else {}
    latest_ts = int(float_from_any(latest.get("t"), 0.0))
    latest_at = text_from_epoch_ms(latest_ts) if latest_ts > 0 else ""
    latest_age = max(0.0, time.time() - latest_ts / 1000.0) if latest_ts > 0 else None
    return {
        "inst_id": inst_id,
        "stream_rows": len(rows),
        "duplicate_trade_ids": duplicate_count,
        "out_of_order_ticks": out_of_order,
        "latest_stream_trade_at": latest_at,
        "latest_stream_trade_age_seconds": latest_age,
    }


def paper_data_quality_snapshot(state: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    """Read-only data quality view for tick-driven paper trading."""
    settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
    live = state.get("live", {}) if isinstance(state.get("live"), dict) else {}
    stream = market_stream_snapshot()
    stream_guard = paper_market_stream_guard(settings, stream)
    cxx_quality = cxx_market_quality_guard(settings)
    latest_cycle = latest_cycle_snapshot(report)
    data_source = latest_cycle.get("data_source", {}) if isinstance(latest_cycle.get("data_source"), dict) else {}
    history = live.get("tick_history", {}) if isinstance(live.get("tick_history"), dict) else {}
    seen = live.get("seen_trade_ids", {}) if isinstance(live.get("seen_trade_ids"), dict) else {}
    instruments = [str(item).upper().strip() for item in settings.get("instruments", []) or [] if str(item).strip()]
    if not instruments:
        instruments = okx_instruments_config()

    rows: list[dict[str, Any]] = []
    rest_fallbacks = 0
    stale_sources = 0
    duplicate_total = 0
    out_of_order_total = 0
    missing_stream_rows = 0
    for inst_id in instruments:
        stream_rows = [item for item in (stream.get("recent_trades", {}) or {}).get(inst_id, []) if isinstance(item, dict)]
        stream_quality = market_trade_quality(inst_id, stream_rows)
        source = data_source.get(inst_id, {}) if isinstance(data_source.get(inst_id), dict) else {}
        source_name = str(source.get("source", ""))
        source_age = source.get("last_trade_age_seconds")
        if source_name == "rest":
            rest_fallbacks += 1
        if source_age is not None and float_from_any(source_age) > float_from_any(stream_guard.get("fresh_limit_seconds"), 15.0):
            stale_sources += 1
        if not stream_rows:
            missing_stream_rows += 1
        duplicate_total += int(stream_quality.get("duplicate_trade_ids", 0) or 0)
        out_of_order_total += int(stream_quality.get("out_of_order_ticks", 0) or 0)
        rows.append(
            {
                **stream_quality,
                "expected": True,
                "latest_source": source_name or "-",
                "latest_source_status": source.get("stream_status", ""),
                "latest_source_trade_at": source.get("last_trade_at", ""),
                "latest_source_age_seconds": source_age,
                "tick_history_rows": len(history.get(inst_id, []) or []) if isinstance(history.get(inst_id, []), list) else 0,
                "seen_trade_ids": len(seen.get(inst_id, []) or []) if isinstance(seen.get(inst_id, []), list) else 0,
            }
        )

    checks = [
        paper_health_check(
            "WS 行情覆盖",
            bool(stream_guard.get("ready")),
            "warn",
            stream_guard.get("message", "-"),
        ),
        paper_health_check(
            "C++ 行情质量",
            bool(cxx_quality.get("ready")),
            "halt",
            str(cxx_quality.get("message", "")),
            active=bool(cxx_quality.get("active")),
            decision=cxx_quality.get("decision", ""),
            age_seconds=cxx_quality.get("age_seconds"),
        ),
        paper_health_check(
            "逐笔缓存",
            missing_stream_rows == 0,
            "warn",
            "所有目标合约都有 WS 成交缓存。" if missing_stream_rows == 0 else f"{missing_stream_rows} 个目标合约暂无 WS 成交缓存。",
        ),
        paper_health_check(
            "重复成交ID",
            duplicate_total == 0,
            "warn",
            "未发现重复 trade_id。" if duplicate_total == 0 else f"发现 {duplicate_total} 个重复 trade_id。",
        ),
        paper_health_check(
            "时间戳顺序",
            out_of_order_total == 0,
            "warn",
            "tick 时间戳单调。" if out_of_order_total == 0 else f"发现 {out_of_order_total} 个乱序 tick。",
        ),
        paper_health_check(
            "REST 兜底",
            rest_fallbacks == 0,
            "warn",
            "最近周期全部使用 WS 行情。" if rest_fallbacks == 0 else f"最近周期 {rest_fallbacks} 个合约使用 REST 兜底。",
        ),
        paper_health_check(
            "源新鲜度",
            stale_sources == 0,
            "warn",
            "最近数据源未超出新鲜度阈值。" if stale_sources == 0 else f"{stale_sources} 个合约数据源超过新鲜度阈值。",
        ),
    ]
    status = paper_health_overall(checks)
    return {
        "generated_at": now_iso(),
        "status": status,
        "ok": status != "halt",
        "checks": checks,
        "summary": {
            "instrument_count": len(instruments),
            "stream_running": bool(stream.get("running")),
            "stream_status": stream.get("status", ""),
            "stream_events": stream.get("events", 0),
            "stream_messages": stream.get("messages", 0),
            "stream_reconnects": stream.get("reconnects", 0),
            "missing_stream_rows": missing_stream_rows,
            "duplicate_trade_ids": duplicate_total,
            "out_of_order_ticks": out_of_order_total,
            "rest_fallbacks": rest_fallbacks,
            "stale_sources": stale_sources,
            "latest_cycle_label": latest_cycle.get("label", ""),
            "latest_cycle_tick_count": latest_cycle.get("tick_count", 0),
            "latest_market_latency_ms": latest_cycle.get("market_latency_ms", 0),
        },
        "stream_guard": stream_guard,
        "cxx_quality": cxx_quality,
        "rows": rows,
    }


def compact_signal_rows(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for signal in signals[:12]:
        instrument = instrument_from_report_item(signal)
        rows.append(
            {
                "strategy_id": signal.get("strategy_id", ""),
                "inst_id": instrument.get("inst_id", ""),
                "score": float_from_any(signal.get("score")),
                "confidence": float_from_any(signal.get("confidence")),
            }
        )
    return rows


def compact_order_rows(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for order in orders[:12]:
        instrument = order.get("instrument", {}) if isinstance(order.get("instrument"), dict) else {}
        rows.append(
            {
                "order_id": order.get("order_id", ""),
                "inst_id": live_inst_id_from_instrument(instrument),
                "side": order.get("side", ""),
                "type": order.get("type", ""),
                "quantity": float_from_any(order.get("quantity")),
                "limit_price": float_from_any(order.get("limit_price", order.get("reference_price"))),
                "status": order.get("status", ""),
                "strategy_ids": order.get("strategy_ids", []),
                "signal_weighted_score": float_from_any(order.get("signal_weighted_score")),
            }
        )
    return rows


def compact_fill_rows(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for report in reports[:12]:
        instrument = report.get("instrument", {}) if isinstance(report.get("instrument"), dict) else {}
        rows.append(
            {
                "order_id": report.get("order_id", ""),
                "inst_id": live_inst_id_from_instrument(instrument),
                "side": report.get("side", ""),
                "last_fill_qty": float_from_any(report.get("last_fill_qty")),
                "last_fill_price": float_from_any(report.get("last_fill_price", report.get("avg_price"))),
                "commission": float_from_any(report.get("commission")),
                "closed_qty": float_from_any(report.get("closed_qty")),
                "close_net_pnl": float_from_any(report.get("close_net_pnl")),
                "realized_pnl_after": float_from_any(report.get("realized_pnl_after")),
                "position_effect": report.get("position_effect", ""),
                "status": report.get("status", ""),
                "broker_status": report.get("broker_status", ""),
                "strategy_ids": report.get("strategy_ids", []),
                "signal_weighted_score": float_from_any(report.get("signal_weighted_score")),
            }
        )
    return rows


def simulated_position_effect(
    previous_qty: float,
    previous_cost: float,
    signed_qty: float,
    price: float,
    commission: float,
) -> dict[str, Any]:
    qty = abs(signed_qty)
    closed_qty = 0.0
    opened_qty = 0.0
    close_gross_pnl = 0.0
    close_fee = 0.0
    effect = "open" if abs(previous_qty) <= 1e-12 else "increase"
    if abs(previous_qty) <= 1e-12 or previous_qty * signed_qty > 0.0:
        new_qty = previous_qty + signed_qty
        weighted_cost = abs(previous_qty) * previous_cost + qty * price
        opened_qty = qty
        post_cost = 0.0 if abs(new_qty) <= 1e-12 else weighted_cost / abs(new_qty)
    else:
        closed_qty = min(abs(previous_qty), qty)
        close_gross_pnl = closed_qty * (price - previous_cost) * (1.0 if previous_qty > 0 else -1.0)
        close_fee = commission * min(1.0, closed_qty / max(qty, 1e-12))
        new_qty = previous_qty + signed_qty
        opened_qty = max(qty - closed_qty, 0.0)
        if opened_qty > 1e-12:
            effect = "flip"
        elif abs(new_qty) <= 1e-12:
            effect = "close"
        else:
            effect = "reduce"
        post_cost = 0.0 if abs(new_qty) <= 1e-12 else price if previous_qty * new_qty <= 0.0 else previous_cost
    return {
        "position_effect": effect,
        "pre_position_qty": previous_qty,
        "post_position_qty": new_qty,
        "pre_avg_cost": previous_cost,
        "post_avg_cost": post_cost,
        "closed_qty": closed_qty,
        "opened_qty": opened_qty,
        "close_gross_pnl": close_gross_pnl,
        "close_fee": close_fee,
        "close_net_pnl": close_gross_pnl - close_fee,
    }


def enrich_report_fill_pnl(report: dict[str, Any]) -> None:
    """Backfill per-fill close PnL for older live paper reports.

    New fills get these fields from `live_apply_fill`.  This read-time pass
    makes existing reports immediately useful in the UI without mutating files.
    """
    positions: dict[str, dict[str, float]] = {}
    realized_pnl = 0.0
    cycles = report.get("cycles", []) if isinstance(report.get("cycles"), list) else []
    for cycle in cycles:
        if not isinstance(cycle, dict):
            continue
        for fill in cycle.get("reports", []) or []:
            if not isinstance(fill, dict) or float_from_any(fill.get("last_fill_qty")) <= 0.0:
                continue
            instrument = instrument_from_report_item(fill)
            inst_id = instrument.get("inst_id", "")
            price = float_from_any(fill.get("last_fill_price"), float_from_any(fill.get("avg_price")))
            qty = float_from_any(fill.get("last_fill_qty"))
            side = str(fill.get("side", "Buy"))
            signed_qty = qty if side == "Buy" else -qty
            commission = float_from_any(fill.get("commission"))
            position = positions.setdefault(inst_id, {"quantity": 0.0, "avg_cost": price})
            previous_qty = float_from_any(position.get("quantity"))
            previous_cost = float_from_any(position.get("avg_cost"), price)
            effect = simulated_position_effect(previous_qty, previous_cost, signed_qty, price, commission)
            realized_pnl = realized_pnl - commission + float_from_any(effect.get("close_gross_pnl"))
            for key, value in effect.items():
                fill.setdefault(key, value)
            fill.setdefault("realized_pnl_after", realized_pnl)
            position["quantity"] = float_from_any(effect.get("post_position_qty"))
            position["avg_cost"] = float_from_any(effect.get("post_avg_cost"))


def append_paper_run_events(run_id: str, payload: dict[str, Any], report: dict[str, Any], settings: dict[str, Any]) -> None:
    mode = str(settings.get("mode", "tick"))
    if payload.get("skipped"):
        append_platform_event(
            "paper.tick_skipped",
            "paper_engine",
            {
                "run_id": run_id,
                "mode": mode,
                "reason": payload.get("reason", ""),
                "stage": payload.get("stage", ""),
                "instruments": settings.get("instruments", []),
            },
            severity="debug",
            message=str(payload.get("reason", "虚拟盘 tick 跳过")),
        )
        return
    cycles = report.get("cycles", []) or []
    if not cycles:
        return
    cycle = cycles[-1]
    signals = cycle.get("signals", []) or []
    orders = cycle.get("orders", []) or []
    reports = cycle.get("reports", []) or []
    fills = [item for item in reports if float_from_any(item.get("last_fill_qty")) > 0.0]
    risk_decision = cycle.get("risk_decision", {}) if isinstance(cycle.get("risk_decision"), dict) else {}
    features = cycle.get("features", {}) if isinstance(cycle.get("features"), dict) else {}
    cycle_payload = {
        "run_id": run_id,
        "mode": mode,
        "cycle_index": cycle.get("cycle_index"),
        "label": cycle.get("label"),
        "instruments": settings.get("instruments", []),
        "signal_count": len(signals),
        "order_count": len(orders),
        "fill_count": len(fills),
        "pending_order_count": len(cycle.get("pending_orders", []) or []),
        "expired_order_count": len(cycle.get("expired_order_records", []) or []),
        "risk_action": risk_decision.get("action", ""),
        "risk_reason": risk_decision.get("reason", ""),
        "latest_tick_key": features.get("latest_tick_key", ""),
        "data_source": features.get("data_source", {}),
    }
    append_order_journal_events_from_cycle(run_id, cycle)
    append_platform_event(
        "paper.tick_completed",
        "paper_engine",
        cycle_payload,
        message=f"虚拟盘 tick 完成：信号 {len(signals)}，委托 {len(orders)}，成交 {len(fills)}",
    )
    append_platform_event(
        "paper.risk_decision",
        "risk",
        {**cycle_payload, "risk_decision": risk_decision},
        severity="warn" if risk_decision.get("action") in {"Reject", "Halt", "Reduce"} else "info",
        message=f"风控 {risk_decision.get('action', '-')}: {risk_decision.get('reason', '-')}",
    )
    if signals:
        append_platform_event(
            "paper.signals",
            "strategy_engine",
            {**cycle_payload, "signals": compact_signal_rows(signals), "signals_total": len(signals)},
            message=f"策略信号 {len(signals)} 条",
        )
    if orders:
        append_platform_event(
            "paper.orders_created",
            "paper_broker",
            {**cycle_payload, "orders": compact_order_rows(orders), "orders_total": len(orders)},
            message=f"纸面委托 {len(orders)} 单",
        )
    if fills:
        append_platform_event(
            "paper.fills",
            "paper_broker",
            {**cycle_payload, "reports": compact_fill_rows(fills), "fills_total": len(fills)},
            message=f"纸面成交 {len(fills)} 笔",
        )
    expired = cycle.get("expired_order_records", []) or []
    if expired:
        append_platform_event(
            "paper.orders_expired",
            "paper_broker",
            {**cycle_payload, "orders": compact_order_rows(expired), "expired_total": len(expired)},
            severity="warn",
            message=f"纸面挂单过期 {len(expired)} 单",
        )


def fill_realized_delta(fill: dict[str, Any]) -> float:
    if fill.get("realized_pnl_before") is not None and fill.get("realized_pnl_after") is not None:
        return float_from_any(fill.get("realized_pnl_after")) - float_from_any(fill.get("realized_pnl_before"))
    return float_from_any(fill.get("close_gross_pnl")) - float_from_any(fill.get("commission"))


def fill_strategy_allocations(fill: dict[str, Any], attribution_by_inst: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    attribution = fill.get("strategy_attribution") if isinstance(fill.get("strategy_attribution"), list) else []
    if not attribution:
        inst_id = instrument_from_report_item(fill).get("inst_id", "")
        summary = attribution_by_inst.get(inst_id, {}) if inst_id else {}
        attribution = summary.get("strategies", []) if isinstance(summary.get("strategies"), list) else []
    if not attribution:
        return [{"strategy_id": "unknown", "share": 1.0, "direction": "unknown"}]

    weighted_total = sum(max(0.0, float_from_any(row.get("share"))) for row in attribution if isinstance(row, dict))
    if weighted_total <= 1e-12:
        weighted_total = sum(abs(float_from_any(row.get("weighted_score"))) for row in attribution if isinstance(row, dict))
    allocations: list[dict[str, Any]] = []
    for row in attribution:
        if not isinstance(row, dict):
            continue
        strategy_id = str(row.get("strategy_id", "unknown"))
        if not strategy_id:
            strategy_id = "unknown"
        raw_share = max(0.0, float_from_any(row.get("share")))
        if raw_share <= 1e-12 and weighted_total > 1e-12:
            raw_share = abs(float_from_any(row.get("weighted_score")))
        share = raw_share / weighted_total if weighted_total > 1e-12 else 1.0 / max(len(attribution), 1)
        allocations.append(
            {
                "strategy_id": strategy_id,
                "share": share,
                "direction": row.get("direction", "unknown"),
                "weighted_score": float_from_any(row.get("weighted_score")),
                "net_score": float_from_any(row.get("net_score")),
            }
        )
    if not allocations:
        return [{"strategy_id": "unknown", "share": 1.0, "direction": "unknown"}]
    share_sum = sum(float_from_any(row.get("share")) for row in allocations)
    if share_sum > 1e-12:
        for row in allocations:
            row["share"] = float_from_any(row.get("share")) / share_sum
    return allocations


def paper_strategy_diagnostics(report: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    cycles = report.get("cycles", []) or []
    latest = cycles[-1] if cycles else {}
    signals = latest.get("signals", []) if isinstance(latest, dict) else []
    orders = latest.get("orders", []) if isinstance(latest, dict) else []
    reports = latest.get("reports", []) if isinstance(latest, dict) else []
    configured = state.get("settings", {}).get("strategy_ids", []) or []
    catalog = {str(item["id"]): item for item in STRATEGY_CATALOG}

    strategy_rows: dict[str, dict[str, Any]] = {}
    instrument_rows: dict[str, dict[str, Any]] = {}
    for signal in signals:
        strategy_id = str(signal.get("strategy_id", "unknown"))
        score = float_from_any(signal.get("score"))
        confidence = float_from_any(signal.get("confidence"))
        instrument = instrument_from_report_item(signal)
        inst_id = instrument["inst_id"]
        strategy = strategy_rows.setdefault(
            strategy_id,
            {
                "strategy_id": strategy_id,
                "display_name": catalog.get(strategy_id, {}).get("display_name", strategy_id),
                "style": catalog.get(strategy_id, {}).get("style", "unknown"),
                "signal_count": 0,
                "net_score": 0.0,
                "weighted_score": 0.0,
                "abs_score": 0.0,
                "abs_weighted_score": 0.0,
                "confidence_sum": 0.0,
                "instruments": {},
            },
        )
        weighted_score = score * confidence
        strategy["signal_count"] += 1
        strategy["net_score"] += score
        strategy["weighted_score"] += weighted_score
        strategy["abs_score"] += abs(score)
        strategy["abs_weighted_score"] += abs(weighted_score)
        strategy["confidence_sum"] += confidence
        strategy["instruments"][inst_id] = strategy["instruments"].get(inst_id, 0) + 1

        instrument_row = instrument_rows.setdefault(
            inst_id,
            {
                "inst_id": inst_id,
                "signal_count": 0,
                "net_score": 0.0,
                "weighted_score": 0.0,
                "abs_score": 0.0,
                "abs_weighted_score": 0.0,
                "confidence_sum": 0.0,
                "strategies": {},
            },
        )
        instrument_row["signal_count"] += 1
        instrument_row["net_score"] += score
        instrument_row["weighted_score"] += weighted_score
        instrument_row["abs_score"] += abs(score)
        instrument_row["abs_weighted_score"] += abs(weighted_score)
        instrument_row["confidence_sum"] += confidence
        instrument_row["strategies"][strategy_id] = instrument_row["strategies"].get(strategy_id, 0) + 1

    strategy_diagnostics = []
    for row in strategy_rows.values():
        count = max(int(row["signal_count"]), 1)
        instruments = sorted(row.pop("instruments").items(), key=lambda item: (-item[1], item[0]))
        row["avg_confidence"] = row["confidence_sum"] / count
        row["top_instruments"] = [item[0] for item in instruments[:4]]
        strategy_diagnostics.append(row)
    strategy_diagnostics.sort(key=lambda item: float(item.get("abs_score", 0.0)), reverse=True)

    instrument_diagnostics = []
    for row in instrument_rows.values():
        count = max(int(row["signal_count"]), 1)
        strategies = sorted(row.pop("strategies").items(), key=lambda item: (-item[1], item[0]))
        row["avg_confidence"] = row["confidence_sum"] / count
        row["top_strategies"] = [item[0] for item in strategies[:4]]
        instrument_diagnostics.append(row)
    instrument_diagnostics.sort(key=lambda item: float(item.get("abs_score", 0.0)), reverse=True)

    report_states: dict[str, int] = {}
    filled_qty = 0.0
    commission = 0.0
    close_net_pnl = 0.0
    realized_delta = 0.0
    attribution_by_inst = signal_attribution_by_inst(signals)
    fill_strategy_rows: dict[str, dict[str, Any]] = {}
    fill_instrument_rows: dict[str, dict[str, Any]] = {}
    for item in reports:
        status = str(item.get("status", "") or item.get("broker_status", "") or "unknown")
        report_states[status] = report_states.get(status, 0) + 1
        item_qty = float_from_any(item.get("last_fill_qty"))
        item_price = float_from_any(item.get("last_fill_price"), float_from_any(item.get("avg_price")))
        item_notional = item_qty * item_price
        item_commission = float_from_any(item.get("commission"))
        item_close_net = float_from_any(item.get("close_net_pnl"))
        item_realized_delta = fill_realized_delta(item)
        item_closed_qty = float_from_any(item.get("closed_qty"))
        filled_qty += item_qty
        commission += item_commission
        close_net_pnl += item_close_net
        realized_delta += item_realized_delta
        if item_qty <= 1e-12:
            continue
        inst_id = instrument_from_report_item(item).get("inst_id", "")
        inst_row = fill_instrument_rows.setdefault(
            inst_id or "unknown",
            {
                "inst_id": inst_id or "unknown",
                "fill_count": 0,
                "filled_qty": 0.0,
                "notional": 0.0,
                "commission": 0.0,
                "closed_qty": 0.0,
                "close_net_pnl": 0.0,
                "realized_delta": 0.0,
            },
        )
        inst_row["fill_count"] += 1
        inst_row["filled_qty"] += item_qty
        inst_row["notional"] += item_notional
        inst_row["commission"] += item_commission
        inst_row["closed_qty"] += item_closed_qty
        inst_row["close_net_pnl"] += item_close_net
        inst_row["realized_delta"] += item_realized_delta

        for allocation in fill_strategy_allocations(item, attribution_by_inst):
            strategy_id = str(allocation.get("strategy_id", "unknown"))
            share = float_from_any(allocation.get("share"))
            row = fill_strategy_rows.setdefault(
                strategy_id,
                {
                    "strategy_id": strategy_id,
                    "display_name": catalog.get(strategy_id, {}).get("display_name", strategy_id),
                    "style": catalog.get(strategy_id, {}).get("style", "unknown"),
                    "fill_count": 0,
                    "allocation_share_sum": 0.0,
                    "filled_qty": 0.0,
                    "notional": 0.0,
                    "commission": 0.0,
                    "closed_qty": 0.0,
                    "close_net_pnl": 0.0,
                    "realized_delta": 0.0,
                    "long_fill_count": 0,
                    "short_fill_count": 0,
                    "instruments": {},
                },
            )
            row["fill_count"] += 1
            row["allocation_share_sum"] += share
            row["filled_qty"] += item_qty * share
            row["notional"] += item_notional * share
            row["commission"] += item_commission * share
            row["closed_qty"] += item_closed_qty * share
            row["close_net_pnl"] += item_close_net * share
            row["realized_delta"] += item_realized_delta * share
            if str(item.get("side", "")).lower() == "buy":
                row["long_fill_count"] += 1
            elif str(item.get("side", "")).lower() == "sell":
                row["short_fill_count"] += 1
            if inst_id:
                row["instruments"][inst_id] = row["instruments"].get(inst_id, 0) + share

    fill_diagnostics = []
    for row in fill_strategy_rows.values():
        instruments = sorted(row.pop("instruments").items(), key=lambda item: (-item[1], item[0]))
        row["top_instruments"] = [item[0] for item in instruments[:4]]
        row["pnl_bps"] = (
            float_from_any(row.get("realized_delta")) / float_from_any(row.get("notional")) * 10000.0
            if float_from_any(row.get("notional")) > 1e-12
            else 0.0
        )
        fill_diagnostics.append(row)
    fill_diagnostics.sort(key=lambda item: (abs(float_from_any(item.get("realized_delta"))), float_from_any(item.get("notional"))), reverse=True)

    fill_instrument_diagnostics = list(fill_instrument_rows.values())
    fill_instrument_diagnostics.sort(key=lambda item: (abs(float_from_any(item.get("realized_delta"))), float_from_any(item.get("notional"))), reverse=True)

    risk = latest.get("risk_decision", {}) if isinstance(latest.get("risk_decision"), dict) else {}
    adjusted = risk.get("adjusted_portfolio", {}) if isinstance(risk.get("adjusted_portfolio"), dict) else {}
    target = latest.get("target_portfolio", {}) if isinstance(latest.get("target_portfolio"), dict) else {}
    known_configured = [item for item in configured if item in catalog]
    unknown_configured = [item for item in configured if item not in catalog]
    poll_seconds = paper_worker_poll_seconds(state.get("settings", {}))
    last_success = str(state.get("last_success_at", ""))
    freshness = "unknown"
    if last_success:
        try:
            age_seconds = max(0.0, time.time() - epoch_ms_from_text(last_success) / 1000.0)
            freshness = "fresh" if age_seconds <= poll_seconds * 2.5 else "stale"
        except Exception:
            freshness = "unknown"

    checks = [
        okx_check("策略配置", len(unknown_configured) == 0, "ok" if not unknown_configured else "warn", f"{len(known_configured)} 个已识别，{len(unknown_configured)} 个未知。"),
        okx_check("最近信号", bool(signals), "ok" if signals else "warn", f"最近周期 {len(signals)} 个信号。"),
        okx_check("风控动作", str(risk.get("action", "")) != "Halt", "ok" if str(risk.get("action", "")) != "Halt" else "halt", str(risk.get("reason", "-"))),
        okx_check("订单回报", bool(reports), "ok" if reports else "warn", f"{len(reports)} 条订单回报，成交数量 {filled_qty:.8g}。"),
        okx_check("刷新时效", freshness != "stale", "ok" if freshness != "stale" else "warn", f"last_success_at={last_success or '-'}"),
    ]
    status = "halt" if any(item["severity"] == "halt" for item in checks) else (
        "warn" if any(item["severity"] == "warn" for item in checks) else "ok"
    )
    return {
        "status": status,
        "checks": checks,
        "configured_strategy_count": len(configured),
        "known_strategy_count": len(known_configured),
        "unknown_strategies": unknown_configured,
        "latest_cycle_label": latest.get("label", ""),
        "strategy_diagnostics": strategy_diagnostics,
        "instrument_diagnostics": instrument_diagnostics,
        "risk": {
            "action": risk.get("action", ""),
            "reason": risk.get("reason", ""),
            "target_gross_exposure": target.get("gross_exposure", ""),
            "adjusted_gross_exposure": adjusted.get("gross_exposure", ""),
            "expected_turnover": adjusted.get("expected_turnover", target.get("expected_turnover", "")),
            "expected_cost_bps": adjusted.get("expected_cost_bps", target.get("expected_cost_bps", "")),
        },
        "orders": {
            "orders_count": len(orders),
            "reports_count": len(reports),
            "filled_qty": filled_qty,
            "commission": commission,
            "close_net_pnl": close_net_pnl,
            "realized_delta": realized_delta,
            "states": dict(sorted(report_states.items())),
        },
        "fill_diagnostics": fill_diagnostics,
        "fill_instrument_diagnostics": fill_instrument_diagnostics,
    }


def read_latest_paper_report() -> dict[str, Any]:
    if not PAPER_LATEST_REPORT_PATH.exists():
        return {}
    try:
        report = json.loads(PAPER_LATEST_REPORT_PATH.read_text(encoding="utf-8"))
        if isinstance(report, dict):
            enrich_report_fill_pnl(report)
            return report
        return {}
    except json.JSONDecodeError:
        return {}


def okx_bridge_max_notional(params: dict[str, list[str]]) -> Decimal:
    configured = decimal_value(get_local_setting("OKX_BRIDGE_MAX_ORDER_NOTIONAL_USDT", "25"))
    requested = decimal_value(params.get("maxNotional", [""])[0]) if params.get("maxNotional") else None
    value = requested if requested is not None else configured
    if value is None or value <= 0:
        value = Decimal("25")
    risk_limit = decimal_value(parse_config().get("risk.max_order_notional", "50000"))
    if risk_limit is not None and risk_limit > 0:
        value = min(value, risk_limit)
    return max(Decimal("1"), value)


def okx_latest_quote(inst_id: str) -> dict[str, Optional[Decimal]]:
    row, _source = okx_ticker_row_for_inst(inst_id)
    item = row if row else {}
    return {
        "bid": decimal_value(item.get("bid")),
        "ask": decimal_value(item.get("ask")),
        "last": decimal_value(item.get("last")),
    }


def okx_maker_limit_price(side: str, reference_price: Decimal, tick_size: Optional[Decimal], inst_id: str) -> Decimal:
    quote = okx_latest_quote(inst_id)
    maker_offset_bps = Decimal(str(max(0.0, min(float_from_any(parse_config().get("execution.maker_offset_bps", "2.0"), 2.0), 100.0))))
    maker_offset = maker_offset_bps / Decimal("10000")
    if side == "buy":
        base = quote.get("bid") or quote.get("last") or reference_price
        offset_price = base * (Decimal("1") - maker_offset)
        if tick_size is not None and tick_size > 0 and base > tick_size:
            return decimal_floor_to_step(min(base - tick_size, offset_price), tick_size)
        return decimal_floor_to_step(offset_price, tick_size)
    base = quote.get("ask") or quote.get("last") or reference_price
    offset_price = base * (Decimal("1") + maker_offset)
    if tick_size is not None and tick_size > 0:
        return decimal_ceil_to_step(max(base + tick_size, offset_price), tick_size)
    return decimal_ceil_to_step(offset_price, tick_size)


def okx_min_notional_lift_cap() -> Decimal:
    """Hard cap for lifting tiny strategy units to exchange minimum size.

    The strategy layer may intentionally emit 1 USDT statistical units, but OKX
    derivatives trade in contract lots.  The bridge may lift a simulated order
    to minSz only within this existing bridge/risk cap; otherwise it blocks with
    a precise min-notional reason.
    """
    return okx_bridge_max_notional({})


def paper_order_to_okx_candidate(
    source_order: dict[str, Any],
    max_notional: Decimal,
    rules_cache: dict[str, Optional[dict[str, Any]]],
    settings: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    settings = settings if isinstance(settings, dict) else {}
    instrument = instrument_from_report_item(source_order)
    source_inst_id = instrument["inst_id"].upper()
    side_text = str(source_order.get("side", "")).lower()
    side = "buy" if side_text == "buy" else "sell" if side_text == "sell" else ""
    price = decimal_value(source_order.get("reference_price"))
    quantity = decimal_value(source_order.get("quantity"))
    derivatives_enabled = paper_derivatives_enabled(settings)
    inst_type = paper_derivatives_inst_type(settings) if derivatives_enabled else OKX_EXECUTION_INST_TYPE
    inst_id = okx_derivative_inst_id(source_inst_id, inst_type) if derivatives_enabled else source_inst_id
    if not (source_inst_id.endswith("-USDT") or source_inst_id.endswith("-SWAP")) or side not in {"buy", "sell"}:
        return {
            "ok": False,
            "reason": "仅支持 OKX USDT 候选订单",
            "inst_id": inst_id,
            "source_inst_id": source_inst_id,
            "inst_type": inst_type,
            "source_order": source_order,
        }
    if price is None or price <= 0 or quantity is None or quantity <= 0:
        return {
            "ok": False,
            "reason": "源订单缺少有效价格或数量",
            "inst_id": inst_id,
            "source_inst_id": source_inst_id,
            "inst_type": inst_type,
            "source_order": source_order,
        }

    rules_key = f"{inst_type}:{inst_id}"
    if rules_key not in rules_cache:
        rules, _ = okx_instrument_rules(inst_id, inst_type)
        rules_cache[rules_key] = rules
    rules = rules_cache.get(rules_key) or {}
    if derivatives_enabled and not rules:
        return {
            "ok": False,
            "reason": f"OKX {inst_type} 元数据未包含 {inst_id}，无法把基础委托转换为合约张数。",
            "inst_id": inst_id,
            "source_inst_id": source_inst_id,
            "inst_type": inst_type,
            "source_order": source_order,
            "instrument_rules": rules,
        }
    lot_size = decimal_value(rules.get("lot_size"))
    min_size = decimal_value(rules.get("min_size"))
    tick_size = decimal_value(rules.get("tick_size"))
    ct_val = decimal_value(rules.get("ct_val"))
    source_notional = quantity * price
    requested_notional = min(source_notional, max_notional)
    planned_notional = min(source_notional, max_notional)
    min_notional: Optional[Decimal] = None
    min_size_lifted = False
    planned_before_lift = planned_notional
    lift_cap = max(max_notional, okx_min_notional_lift_cap())

    limit_price = okx_maker_limit_price(side, price, tick_size, inst_id)
    if limit_price <= 0:
        return {
            "ok": False,
            "reason": "无法生成有效挂单价格",
            "inst_id": inst_id,
            "source_inst_id": source_inst_id,
            "inst_type": inst_type,
            "source_order": source_order,
        }

    if derivatives_enabled:
        if ct_val is None or ct_val <= 0:
            return {
                "ok": False,
                "reason": "OKX 合约规则缺少有效 ctVal，无法把 USDT 名义金额换算为张数。",
                "inst_id": inst_id,
                "source_inst_id": source_inst_id,
                "inst_type": inst_type,
                "source_order": source_order,
                "instrument_rules": rules,
            }
        contract_notional = limit_price * ct_val
    else:
        contract_notional = limit_price

    if min_size is not None and min_size > 0:
        min_notional = min_size * contract_notional
    base_size = decimal_floor_to_step(planned_notional / contract_notional, lot_size)
    if min_size is not None and base_size < min_size and min_notional is not None and min_notional <= lift_cap:
        # Simulated derivatives often need more than the 1 USDT base strategy
        # unit to satisfy OKX minSz.  Lift to the smallest legal lot instead of
        # silently producing sz=0, and make the lift visible in the candidate.
        base_size = decimal_ceil_to_step(min_size, lot_size)
        planned_before_lift = planned_notional
        planned_notional = base_size * contract_notional
        min_size_lifted = True
    else:
        planned_notional = base_size * contract_notional
    if min_size is not None and base_size < min_size:
        return {
            "ok": False,
            "reason": (
                f"按单笔上限折算后数量 {decimal_plain(base_size)} 小于 minSz={rules.get('min_size')}；"
                f"该合约最小名义金额约 {decimal_plain(min_notional or Decimal('0'))} USDT，"
                f"当前可抬升上限 {decimal_plain(lift_cap)} USDT。"
            ),
            "inst_id": inst_id,
            "source_inst_id": source_inst_id,
            "inst_type": inst_type,
            "source_order": source_order,
            "instrument_rules": rules,
            "min_notional_usdt": float(min_notional or Decimal("0")),
            "min_lift_cap_usdt": float(lift_cap),
        }
    if base_size <= 0:
        return {
            "ok": False,
            "reason": "按单笔上限折算后数量为 0",
            "inst_id": inst_id,
            "source_inst_id": source_inst_id,
            "inst_type": inst_type,
            "source_order": source_order,
        }
    order = {
        "instId": inst_id,
        "tdMode": paper_derivatives_margin_mode(settings) if derivatives_enabled else OKX_EXECUTION_TD_MODE,
        "side": side,
        "ordType": "post_only",
        "sz": decimal_plain(base_size),
        "px": decimal_plain(limit_price),
    }
    if derivatives_enabled:
        controls = trading_unit_settings(settings)
        pos_side = okx_position_side_for_order(side, settings)
        effective_leverage = max(
            0.0,
            min(
                float_from_any(controls.get("max_unit_effective_leverage"), 1.0),
                float_from_any(controls.get("max_effective_leverage"), 2.0),
            ),
        )
        exchange_leverage = max(
            1.0,
            min(
                float_from_any(controls.get("max_exchange_leverage"), 3.0),
                math.ceil(max(1.0, effective_leverage)),
            ),
        )
        if pos_side != "net":
            order["posSide"] = pos_side
        order.update(
            {
                "_instType": inst_type,
                "_posSide": pos_side,
                "_notional_usdt": decimal_plain(planned_notional),
                "_ctVal": decimal_plain(ct_val or Decimal("0")),
                "_min_size_lifted": min_size_lifted,
                "_requested_notional_usdt": decimal_plain(requested_notional),
                "_planned_before_lift_usdt": decimal_plain(planned_before_lift),
                "_exchange_leverage": exchange_leverage,
                "_effective_leverage": effective_leverage,
                "_unit_effective_leverage": effective_leverage,
            }
        )

    allowed, message, risk = okx_pre_trade_check(order, submission_context=True)
    return {
        "ok": True,
        "approved": bool(allowed),
        "message": message,
        "inst_id": inst_id,
        "source_inst_id": source_inst_id,
        "inst_type": inst_type,
        "execution_scope": "derivatives" if derivatives_enabled else "spot",
        "source_order": source_order,
        "source_notional": float(source_notional),
        "requested_notional": float(requested_notional),
        "planned_notional": float(planned_notional),
        "scale": float(planned_notional / source_notional) if source_notional > 0 else 0.0,
        "configured_max_notional": float(max_notional),
        "min_notional_usdt": float(min_notional) if min_notional is not None else None,
        "min_lift_cap_usdt": float(lift_cap),
        "min_size_lifted": min_size_lifted,
        "planned_before_lift_usdt": float(planned_before_lift),
        "order": order,
        "instrument_rules": rules,
        "risk": risk,
    }


def paper_okx_tradeability_failure(inst_id: str, message: str) -> dict[str, Any]:
    """Return a synthetic blocking tradeability row when live OKX data is unavailable."""
    return {
        "inst_id": inst_id,
        "status": "block",
        "checks": [
            okx_check(
                "可交易性评估",
                False,
                "halt",
                message or "OKX 可交易性评估不可用，自动提交暂停。",
            )
        ],
    }


def paper_okx_tradeability_map_for_candidates(
    candidates: list[dict[str, Any]],
    max_notional: Decimal,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Evaluate OKX market tradeability once for all candidate instruments.

    The automatic bridge should not submit an order only because order syntax
    and C++ hard limits pass.  It also needs current exchange facts: instrument
    state, quote availability, spread, minimum size, WS depth, and 24h volume.
    This helper batches those checks so a cycle with multiple candidate orders
    does not fan out into repeated OKX reference-data calls.
    """
    grouped: dict[str, list[str]] = {}
    notional_by_type: dict[str, Decimal] = {}
    for candidate in candidates:
        if not candidate.get("ok"):
            continue
        inst_id = str(candidate.get("inst_id") or candidate.get("order", {}).get("instId") or "").upper().strip()
        inst_type = str(candidate.get("inst_type") or okx_order_inst_type(candidate.get("order", {}) if isinstance(candidate.get("order"), dict) else {})).upper().strip()
        key = inst_type or OKX_EXECUTION_INST_TYPE
        if inst_id and inst_id not in grouped.setdefault(key, []):
            grouped[key].append(inst_id)
        candidate_notional = decimal_value(candidate.get("planned_notional")) or max_notional
        notional_by_type[key] = max(notional_by_type.get(key, Decimal("0")), candidate_notional, max_notional)
    if not grouped:
        return {"ok": True, "summary": {"pass": 0, "warn": 0, "block": 0}, "tradeability": []}, {}

    all_rows: list[dict[str, Any]] = []
    by_inst: dict[str, dict[str, Any]] = {}
    payloads: list[dict[str, Any]] = []
    ok = True
    errors: list[str] = []
    summary = {"pass": 0, "warn": 0, "block": 0}
    for inst_type, inst_ids in grouped.items():
        payload = okx_tradeability_payload(
            {
                "instType": [inst_type],
                "instIds": [",".join(inst_ids)],
                "notional": [decimal_plain(notional_by_type.get(inst_type, max_notional))],
            }
        )
        payloads.append(
            {
                "inst_type": inst_type,
                "ok": bool(payload.get("ok")),
                "summary": payload.get("summary", {}),
                "error": payload.get("error", ""),
            }
        )
        if not payload.get("ok"):
            ok = False
            message = str(payload.get("error") or "OKX 可交易性评估失败。")
            errors.append(f"{inst_type}: {message}")
            rows = [
                paper_okx_tradeability_failure(inst_id, f"OKX {inst_type} 可交易性评估失败：{message}")
                for inst_id in inst_ids
            ]
        else:
            rows = [row for row in payload.get("tradeability", []) if isinstance(row, dict)]
        for row in rows:
            inst_id = str(row.get("inst_id", "")).upper()
            if inst_id:
                by_inst[inst_id] = row
                all_rows.append(row)
                status = str(row.get("status", "block"))
                summary[status if status in summary else "block"] += 1
        for inst_id in inst_ids:
            if inst_id not in by_inst:
                row = paper_okx_tradeability_failure(inst_id, f"OKX 可交易性结果缺少该 {inst_type} 合约，自动提交暂停。")
                by_inst[inst_id] = row
                all_rows.append(row)
                summary["block"] += 1
    return {
        "ok": ok,
        "summary": summary,
        "tradeability": all_rows,
        "payloads": payloads,
        "error": "；".join(errors),
    }, by_inst


def paper_okx_apply_tradeability_to_candidate(
    candidate: dict[str, Any],
    tradeability_by_inst: dict[str, dict[str, Any]],
    block_warnings: bool = False,
) -> dict[str, Any]:
    """Attach tradeability to a candidate and block unsafe auto-submission paths."""
    if not candidate.get("ok"):
        return candidate
    inst_id = str(candidate.get("inst_id") or candidate.get("order", {}).get("instId") or "").upper().strip()
    row = tradeability_by_inst.get(inst_id) or paper_okx_tradeability_failure(
        inst_id,
        "OKX 可交易性结果缺失，自动提交暂停。",
    )
    candidate["tradeability"] = row
    candidate["execution_forecast"] = paper_okx_execution_forecast(candidate, row)
    status = str(row.get("status", "")).lower().strip()
    candidate["tradeability_status"] = status or "unknown"
    failed_messages = [
        str(item.get("message", "")).strip()
        for item in (row.get("checks", []) or [])
        if isinstance(item, dict) and not item.get("ok") and str(item.get("message", "")).strip()
    ]
    detail = " / ".join(failed_messages[:3]) or "未通过 OKX 可交易性门禁。"

    should_block = status == "block" or (status == "warn" and block_warnings)
    if should_block:
        candidate["pre_tradeability_approved"] = bool(candidate.get("approved"))
        candidate["approved"] = False
        candidate["message"] = (
            "OKX 可交易性阻断："
            if status == "block"
            else "OKX 可交易性警告已按配置阻断："
        ) + detail
    elif status == "warn":
        candidate["tradeability_warning"] = detail
    return candidate


def paper_okx_execution_forecast(candidate: dict[str, Any], tradeability: dict[str, Any]) -> dict[str, Any]:
    """Estimate pre-trade execution cost for one mapped OKX simulated order."""
    planned_notional = decimal_value(candidate.get("planned_notional")) or Decimal("0")
    spread_bps = decimal_value(tradeability.get("spread_bps")) or Decimal("0")
    maker_fee_bps = decimal_value(tradeability.get("maker_fee_bps")) or Decimal(str(float_from_any(parse_config().get("execution.maker_fee_bps", "1.0"), 1.0)))
    max_expected_cost_bps = Decimal(str(float_from_any(parse_config().get("execution.max_expected_cost_bps", "50"), 50.0)))
    depth = tradeability.get("depth", {}) if isinstance(tradeability.get("depth"), dict) else {}
    usable_depth = Decimal(str(float_from_any(depth.get("usable_depth_usdt"))))
    spread_cost_bps = spread_bps / Decimal("2") if spread_bps > 0 else Decimal("0")
    if usable_depth > 0 and planned_notional > 0:
        depth_cost_bps = min(Decimal("100"), (planned_notional / usable_depth) * max(spread_bps, Decimal("1")))
    else:
        depth_cost_bps = Decimal("0")
    expected_cost_bps = maker_fee_bps + spread_cost_bps + depth_cost_bps
    expected_cost_usdt = planned_notional * expected_cost_bps / Decimal("10000") if planned_notional > 0 else Decimal("0")
    return {
        "planned_notional_usdt": float(planned_notional),
        "maker_fee_bps": float(maker_fee_bps),
        "spread_bps": float(spread_bps),
        "spread_cost_bps": float(spread_cost_bps),
        "depth_cost_bps": float(depth_cost_bps),
        "expected_cost_bps": float(expected_cost_bps),
        "expected_cost_usdt": float(expected_cost_usdt),
        "max_expected_cost_bps": float(max_expected_cost_bps),
        "cost_ok": expected_cost_bps <= max_expected_cost_bps,
    }


def paper_okx_execution_forecast_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    forecasts = [item.get("execution_forecast", {}) for item in candidates if isinstance(item.get("execution_forecast"), dict)]
    total_notional = sum(float_from_any(item.get("planned_notional_usdt")) for item in forecasts)
    total_cost = sum(float_from_any(item.get("expected_cost_usdt")) for item in forecasts)
    weighted_bps = total_cost / total_notional * 10000.0 if total_notional > 0 else 0.0
    high_cost = [item for item in forecasts if item.get("cost_ok") is False]
    return {
        "candidate_count": len(forecasts),
        "total_planned_notional_usdt": total_notional,
        "total_expected_cost_usdt": total_cost,
        "weighted_expected_cost_bps": weighted_bps,
        "high_cost_count": len(high_cost),
    }


def paper_okx_execution_plan_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    report = read_latest_paper_report()
    state = read_paper_state()
    settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
    cycles = report.get("cycles", []) or []
    if not cycles:
        return {"ok": False, "error": "暂无虚拟盘报告，请先运行一次 paper tick。", "plan": [], "config": okx_status()}
    latest = cycles[-1]
    max_orders = bounded_int(params.get("maxOrders", ["20"])[0], 20, 1, 50)
    max_notional = okx_bridge_max_notional(params)
    rules_cache: dict[str, Optional[dict[str, Any]]] = {}
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for source_order in (latest.get("orders", []) or [])[:max_orders]:
        candidate = paper_order_to_okx_candidate(source_order, max_notional, rules_cache, settings)
        if candidate.get("ok"):
            candidates.append(candidate)
        else:
            skipped.append(candidate)

    tradeability_payload, tradeability_by_inst = paper_okx_tradeability_map_for_candidates(candidates, max_notional)
    for candidate in candidates:
        paper_okx_apply_tradeability_to_candidate(candidate, tradeability_by_inst)
    execution_forecast_summary = paper_okx_execution_forecast_summary(candidates)

    submit_gate = okx_simulated_submit_gate()
    gate = submit_gate.get("config", okx_status())
    submit_ready = bool(submit_gate.get("ready"))
    if candidates and not submit_ready:
        for candidate in candidates:
            candidate["preflight_approved"] = bool(candidate.get("approved"))
            if candidate.get("approved"):
                candidate["approved"] = False
                candidate["message"] = f"{submit_gate.get('reason', 'OKX 模拟盘提交未就绪')} 候选单只能审查和填入工单。"
    return {
        "ok": True,
        "generated_at": now_iso(),
        "cycle": latest_cycle_snapshot(report),
        "max_notional": float(max_notional),
        "tradeability": {
            "ok": bool(tradeability_payload.get("ok")),
            "summary": tradeability_payload.get("summary", {}),
            "thresholds": tradeability_payload.get("thresholds", {}),
            "error": tradeability_payload.get("error", ""),
        },
        "execution_forecast": execution_forecast_summary,
        "submit_ready": submit_ready,
        "submit_gate": submit_gate,
        "submit_note": "虚拟盘 runner 已要求自动提交；候选计划仅用于审查最近周期会如何映射到 OKX 模拟盘。",
        "plan": candidates,
        "skipped": skipped,
        "config": gate,
    }


def paper_okx_source_order_id(cycle: dict[str, Any], order: dict[str, Any], index: int) -> str:
    raw = str(order.get("order_id", "")).strip()
    session_id = str(order.get("paper_session_id", "")).strip()
    if raw:
        return f"{session_id}:{raw}" if session_id else raw
    session_prefix = f"{session_id}:" if session_id else ""
    return f"{session_prefix}cycle-{cycle.get('cycle_index', 0)}-{cycle.get('label', '')}-{index}"


def paper_okx_guard_trace_candidate(source_order: dict[str, Any], message: str, guard: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal execution candidate when submission is stopped before OKX mapping."""
    instrument = instrument_from_report_item(source_order)
    inst_id = instrument["inst_id"].upper()
    side_text = str(source_order.get("side", "")).lower()
    side = "buy" if side_text == "buy" else "sell" if side_text == "sell" else side_text
    price = float_from_any(
        source_order.get("reference_price")
        or source_order.get("price")
        or source_order.get("limit_price")
    )
    quantity = float_from_any(source_order.get("quantity"))
    return {
        "ok": False,
        "approved": False,
        "reason": message,
        "message": message,
        "inst_id": inst_id,
        "source_order": source_order,
        "source_notional": price * quantity if price > 0 and quantity > 0 else 0.0,
        "planned_notional": 0.0,
        "scale": 0.0,
        "order": {
            "instId": inst_id,
            "tdMode": OKX_EXECUTION_TD_MODE,
            "side": side,
            "ordType": "post_only",
        },
        "tradeability_status": "not_checked",
        "risk": {
            "cxx_policy_checks": [
                {
                    "name": "OKX 自动提交门禁",
                    "ok": False,
                    "severity": "warn",
                    "message": message,
                }
            ],
            "submission_guard": guard,
        },
    }


def append_okx_auto_guard_execution_traces(
    auto_state: dict[str, Any],
    latest: dict[str, Any],
    source_orders: list[dict[str, Any]],
    *,
    message: str,
    guard: dict[str, Any],
    max_orders: int,
) -> dict[str, Any]:
    """Trace strategy orders that were intentionally held back by automation gates."""
    recent = [dict(item) for item in (auto_state.get("recent", []) or []) if isinstance(item, dict)]
    guarded_ids = set(str(item) for item in (auto_state.get("guarded_source_order_ids", []) or []))
    traced = 0
    for index, source_order in enumerate(source_orders[:max_orders], start=1):
        source_order_id = paper_okx_source_order_id(latest, source_order, index)
        if source_order_id in guarded_ids:
            continue
        candidate = paper_okx_guard_trace_candidate(source_order, message, guard)
        trace = append_execution_trace_event(
            "execution.guarded",
            source_order_id,
            candidate,
            latest,
            status="guarded",
            message=message,
            result={"ok": False, "error": message, "result": guard},
        )
        recent.append(
            {
                "at": now_iso(),
                "source_order_id": source_order_id,
                "status": "guarded",
                "message": message,
                "candidate": candidate,
                "execution_trace_id": trace.get("id", ""),
                "result": {"ok": False, "error": message},
            }
        )
        guarded_ids.add(source_order_id)
        traced += 1
    auto_state["recent"] = recent[-30:]
    auto_state["guarded_source_order_ids"] = list(guarded_ids)[-500:]
    auto_state["last_guard_trace_count"] = traced
    return auto_state


def paper_okx_auto_client_order_id(source_order_id: str, cycle: dict[str, Any]) -> str:
    raw = f"{source_order_id}|{cycle.get('cycle_index', '')}|{cycle.get('label', '')}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    return f"KTA{digest[:26]}"


def paper_okx_auto_order_detail(record: dict[str, Any]) -> dict[str, Any]:
    result = record.get("result", {}) if isinstance(record.get("result"), dict) else {}
    detail = result.get("order_detail", {}) if isinstance(result.get("order_detail"), dict) else {}
    return detail


def paper_okx_auto_record_state(record: dict[str, Any]) -> str:
    return str(paper_okx_auto_order_detail(record).get("state") or record.get("status", "")).lower().strip()


def paper_okx_auto_order_identity(record: dict[str, Any]) -> Optional[dict[str, str]]:
    result = record.get("result", {}) if isinstance(record.get("result"), dict) else {}
    detail = result.get("order_detail", {}) if isinstance(result.get("order_detail"), dict) else {}
    order = record.get("order", {}) if isinstance(record.get("order"), dict) else {}
    submit_result = result.get("result", {}) if isinstance(result.get("result"), dict) else {}
    inst_id = str(detail.get("inst_id") or order.get("instId") or submit_result.get("instId") or "").upper().strip()
    ord_id = str(detail.get("ord_id") or submit_result.get("ordId") or order.get("ordId") or "").strip()
    cl_ord_id = str(detail.get("cl_ord_id") or order.get("clOrdId") or submit_result.get("clOrdId") or "").strip()
    if not inst_id or not (ord_id or cl_ord_id):
        return None
    return {"instId": inst_id, "ordId": ord_id, "clOrdId": cl_ord_id}


def okx_order_identity_key(identity: dict[str, str]) -> str:
    return str(identity.get("ordId") or identity.get("clOrdId") or "").strip()


def okx_audit_live_order_rows(limit: int = 5000) -> list[dict[str, Any]]:
    """Return latest locally audited OKX simulated orders still believed live.

    The paper auto-submit state intentionally keeps only a bounded recent tail for
    UI speed.  Stale-order automation must use the append-only OKX audit journal
    as the durable source, otherwise yesterday's live orders can disappear from
    memory and stop being managed.
    """
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in read_okx_audit(limit):
        if not isinstance(row, dict):
            continue
        action = str(row.get("action", ""))
        if action not in {"order_submitted", "order_synced", "order_cancelled", "paper_auto_order_synced"}:
            continue
        identity = okx_audit_order_identity(row)
        if not identity:
            continue
        key = okx_order_identity_key(identity)
        if not key or key in seen:
            continue
        seen.add(key)
        snapshot = okx_audit_order_snapshot(row)
        state = "canceled" if action == "order_cancelled" else str(snapshot.get("state", "")).lower()
        if state not in {"live", "partially_filled"}:
            continue
        order = row.get("order", {}) if isinstance(row.get("order"), dict) else {}
        detail = row.get("order_detail", {}) if isinstance(row.get("order_detail"), dict) else {}
        age = age_seconds_from_text(row.get("ts")) or 0.0
        rows.append(
            {
                "source_order_id": row.get("source_order_id", ""),
                "source_audit_id": row.get("id", ""),
                "inst_id": identity["instId"],
                "side": detail.get("side") or order.get("side", ""),
                "state": state,
                "age_seconds": age,
                "px": detail.get("px") or order.get("px", ""),
                "sz": detail.get("sz") or order.get("sz", ""),
                "ord_id": identity.get("ordId", ""),
                "cl_ord_id": identity.get("clOrdId", ""),
                "last_order_sync_at": row.get("ts", ""),
                "source": "okx_audit",
            }
        )
    return rows


def okx_latest_audit_order_index(limit: int = 5000) -> dict[str, dict[str, Any]]:
    """Index the latest audited OKX state by exchange order identity.

    The in-memory paper auto-submit `recent` list is intentionally bounded for
    UI speed.  For automation gates we still need the freshest OKX state that
    has been audited locally, otherwise an old `live` row in `recent` can keep
    blocking new orders after a later sync already proved the order filled or
    was cancelled.

    中文说明：这个索引用来解决“昨天的挂单在 auto.recent 里还是 live，但 OKX 审计
    后已经 filled/canceled”的问题。预检和自动撤单都应该相信最新审计，而不是相信
    只为 UI 截断保存的 recent 列表。
    """
    latest: dict[str, dict[str, Any]] = {}
    for row in read_okx_audit(limit):
        if not isinstance(row, dict):
            continue
        action = str(row.get("action", ""))
        if action not in {"order_submitted", "order_synced", "order_cancelled", "paper_auto_order_synced"}:
            continue
        identity = okx_audit_order_identity(row)
        if not identity:
            continue
        key = okx_order_identity_key(identity)
        if not key or key in latest:
            continue
        snapshot = okx_audit_order_snapshot(row)
        detail = row.get("order_detail", {}) if isinstance(row.get("order_detail"), dict) else {}
        order = row.get("order", {}) if isinstance(row.get("order"), dict) else {}
        state = "canceled" if action == "order_cancelled" else str(snapshot.get("state", "")).lower().strip()
        latest[key] = {
            "source_order_id": row.get("source_order_id", ""),
            "source_audit_id": row.get("id", ""),
            "action": action,
            "inst_id": identity["instId"],
            "side": detail.get("side") or order.get("side", ""),
            "state": state,
            "px": detail.get("px") or order.get("px", ""),
            "sz": detail.get("sz") or order.get("sz", ""),
            "ord_id": identity.get("ordId", ""),
            "cl_ord_id": identity.get("clOrdId", ""),
            "last_order_sync_at": row.get("ts", ""),
        }
    return latest


def paper_okx_auto_sync_due(record: dict[str, Any], now_ms: int) -> bool:
    result = record.get("result", {}) if isinstance(record.get("result"), dict) else {}
    if record.get("status") != "submitted" or not result.get("ok"):
        return False
    if not paper_okx_auto_order_identity(record):
        return False
    state = paper_okx_auto_record_state(record)
    if state in OKX_TERMINAL_ORDER_STATES:
        return False
    last_sync_at = str(record.get("last_order_sync_at") or record.get("at") or "").strip()
    if not last_sync_at:
        return True
    try:
        return now_ms - epoch_ms_from_text(last_sync_at) >= 20_000
    except ValueError:
        return True


def paper_okx_auto_order_health(auto: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    recent = [item for item in (auto.get("recent", []) or []) if isinstance(item, dict)]
    poll_seconds = paper_worker_poll_seconds(settings)
    stale_live_limit = max(poll_seconds * 3, 180)
    state_counts: dict[str, int] = {}
    stale_orders: list[dict[str, Any]] = []
    live_orders: list[dict[str, Any]] = []
    live_keys: set[str] = set()
    # auto.recent 为了 UI 性能只保留最近记录，可能缺少后续同步出来的终态。
    # 因此健康检查先建立一份“最新 OKX 审计索引”，让后来的 filled/canceled 覆盖
    # 旧的 submitted/live，避免昨天的挂单在本地无限阻断新委托。
    latest_audit = okx_latest_audit_order_index()
    for record in recent:
        detail = paper_okx_auto_order_detail(record)
        identity = paper_okx_auto_order_identity(record) or {}
        order = record.get("order", {}) if isinstance(record.get("order"), dict) else {}
        key = okx_order_identity_key(identity)
        audited = latest_audit.get(key, {}) if key else {}
        # 如果审计日志里已经有更新的交易所状态，优先采用审计状态；只有没有审计
        # 快照时才回退到 auto.recent 中的本地提交状态。
        order_state = str(audited.get("state") or paper_okx_auto_record_state(record) or record.get("status", "")).lower()
        state_counts[order_state] = state_counts.get(order_state, 0) + 1
        if order_state not in {"live", "partially_filled"}:
            if key:
                live_keys.add(key)
            continue
        age = age_seconds_from_text(record.get("at")) or 0.0
        row = {
            "source_order_id": audited.get("source_order_id") or record.get("source_order_id", ""),
            "inst_id": audited.get("inst_id") or detail.get("inst_id") or order.get("instId", ""),
            "side": audited.get("side") or detail.get("side") or order.get("side", ""),
            "state": order_state,
            "age_seconds": age,
            "px": audited.get("px") or detail.get("px") or order.get("px", ""),
            "sz": audited.get("sz") or detail.get("sz") or order.get("sz", ""),
            "ord_id": audited.get("ord_id") or identity.get("ordId", ""),
            "cl_ord_id": audited.get("cl_ord_id") or identity.get("clOrdId", ""),
            "last_order_sync_at": audited.get("last_order_sync_at") or record.get("last_order_sync_at", ""),
            "source": "auto_recent",
        }
        if key:
            live_keys.add(key)
        live_orders.append(row)
        if age >= stale_live_limit:
            stale_orders.append(row)

    for row in okx_audit_live_order_rows():
        identity = {"ordId": str(row.get("ord_id", "")), "clOrdId": str(row.get("cl_ord_id", ""))}
        key = okx_order_identity_key(identity)
        if key and key in live_keys:
            continue
        live_orders.append(row)
        if key:
            live_keys.add(key)
        if float_from_any(row.get("age_seconds"), 0.0) >= stale_live_limit:
            stale_orders.append(row)
    return {
        "state_counts": state_counts,
        "stale_orders": stale_orders,
        "live_orders": live_orders,
        "stale_live_limit_seconds": stale_live_limit,
    }


def clear_paper_okx_guard(body: dict[str, Any]) -> dict[str, Any]:
    """清除 OKX 自动提交门禁的账户模式错误冷却期。

    将 execution_trace 中最近 200 条记录里的 51010 错误
    标记为已确认，这样 guard 就不会再读取到这些错误。
    """
    trace_path = EXECUTION_TRACE_PATH
    if not trace_path.exists():
        return {"ok": True, "message": "没有执行轨迹记录，无需清除。"}
    entries: list[dict[str, Any]] = []
    cleared = 0
    try:
        with open(trace_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    entries.append(json.loads("{}"))
                    continue
                if execution_failure_is_okx_account_mode(entry) and not entry.get("acknowledged"):
                    entry["acknowledged"] = True
                    entry["acknowledged_at"] = now_iso()
                    cleared += 1
                entries.append(entry)
        if cleared > 0:
            trace_path.write_text(
                "\n".join(json.dumps(e, ensure_ascii=False, separators=(",", ":"), default=str) for e in entries) + "\n",
                encoding="utf-8",
            )
        return {"ok": True, "cleared": cleared, "message": f"已确认 {cleared} 条 51010 错误记录，冷却期已解除。"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def okx_account_mode_submission_guard(settings: dict[str, Any]) -> dict[str, Any]:
    """Temporarily stop new submits after OKX rejects the account mode."""
    cooldown_seconds = bounded_int(
        settings.get("okx_auto_account_mode_error_cooldown_seconds", 60),
        60,
        0,
        86400,
    )
    if cooldown_seconds <= 0:
        return {
            "ok": True,
            "message": "OKX 账户模式错误冷却门禁未启用。",
            "cooldown_seconds": cooldown_seconds,
        }
    latest_match: dict[str, Any] = {}
    latest_age: Optional[float] = None
    for row in read_execution_trace(200):
        if not isinstance(row, dict) or not execution_failure_is_okx_account_mode(row):
            continue
        if row.get("acknowledged"):
            continue  # 用户已确认，跳过
        latest_match = row
        latest_age = age_seconds_from_text(row.get("ts"))
        break
    if not latest_match:
        return {
            "ok": True,
            "message": "最近执行轨迹未发现 OKX 账户模式拒单。",
            "cooldown_seconds": cooldown_seconds,
        }
    error_key = execution_failure_okx_error_key(latest_match)
    if latest_age is None or latest_age <= cooldown_seconds:
        age_text = "未知时间" if latest_age is None else f"{latest_age:.0f} 秒前"
        return {
            "ok": False,
            "message": f"最近 {age_text} 出现 OKX 账户模式拒单：{error_key or 'sCode=51010'}；先停止新提交，避免重复失败。",
            "cooldown_seconds": cooldown_seconds,
            "latest_age_seconds": latest_age,
            "latest_error_key": error_key,
            "latest_trace_id": latest_match.get("id", ""),
            "latest_ts": latest_match.get("ts", ""),
        }
    return {
        "ok": True,
        "message": f"上次 OKX 账户模式拒单已超过冷却时间：{latest_age:.0f}/{cooldown_seconds} 秒。",
        "cooldown_seconds": cooldown_seconds,
        "latest_age_seconds": latest_age,
        "latest_error_key": error_key,
        "latest_trace_id": latest_match.get("id", ""),
        "latest_ts": latest_match.get("ts", ""),
    }


def paper_engine_submission_guard(
    settings: dict[str, Any],
    report: Optional[dict[str, Any]] = None,
    state: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Protect auto-submission from stale market data or slow tick cycles."""
    report = report if isinstance(report, dict) else {}
    state = state if isinstance(state, dict) else {}
    latest = latest_cycle_snapshot(report)
    performance = paper_performance_snapshot(report, state)
    runtime_ms = float_from_any(latest.get("runtime_ms"), float_from_any(state.get("last_runtime_ms")))
    latency_ms = float_from_any(latest.get("market_latency_ms"), float_from_any(state.get("last_market_latency_ms")))
    mode = str(settings.get("mode", "")).lower().strip()
    max_latency_ms = bounded_int(settings.get("okx_auto_max_market_latency_ms", 30000), 30000, 1000, 300000)
    if mode == "realtime":
        # 当前 realtime paper runner 使用已闭合 1m K线生成策略周期，行情延迟
        # 天然会落在 60-120s。这里仅放宽 OKX 提交前的 K线样本延迟门禁；
        # C++ 逐笔质量报告仍继续使用 30s 级 freshness 门禁。
        max_latency_ms = max(max_latency_ms, 180000)
    max_runtime_ms = bounded_int(settings.get("okx_auto_max_runtime_ms", 5000), 5000, 100, 60000)
    runtime_sample_ttl_seconds = max(float(paper_worker_poll_seconds(settings) * 5), 30.0)
    sample_ages = [
        age
        for age in [
            age_seconds_from_text(state.get("last_runtime_at")),
            age_seconds_from_text(latest.get("label")),
        ]
        if age is not None
    ]
    runtime_sample_age = min(sample_ages) if sample_ages else None
    runtime_sample_fresh = runtime_sample_age is None or runtime_sample_age <= runtime_sample_ttl_seconds
    require_stream = parse_bool_setting(str(settings.get("okx_auto_require_stream", "false")), False)
    cxx_quality = cxx_market_quality_guard(settings)
    data_source = latest.get("data_source") if isinstance(latest.get("data_source"), dict) else {}
    if not data_source and isinstance(state.get("live"), dict):
        data_source = state.get("live", {}).get("tick_data_source_by_inst", {}) or {}
    wanted_instruments = {
        str(item).upper().strip()
        for item in settings.get("instruments", []) or []
        if str(item).strip()
    }
    if wanted_instruments and not runtime_sample_fresh:
        stream = market_stream_snapshot()
        stream_instruments = {str(item).upper().strip() for item in stream.get("instruments", []) or []}
        stream_status = str(stream.get("status", ""))
        recent_trades = stream.get("recent_trades", {}) if isinstance(stream.get("recent_trades"), dict) else {}
        data_source = {
            inst_id: {
                "source": "stream" if inst_id in stream_instruments and recent_trades.get(inst_id) else "missing",
                "stream_status": stream_status,
                "last_trade_at": stream.get("last_trade_at", ""),
                "last_trade_age_seconds": age_seconds_from_text(stream.get("last_trade_at")),
            }
            for inst_id in sorted(wanted_instruments)
        }
    if wanted_instruments and isinstance(data_source, dict):
        data_source = {
            inst_id: row
            for inst_id, row in data_source.items()
            if str(inst_id).upper().strip() in wanted_instruments
        }
    source_rows = [row for row in data_source.values() if isinstance(row, dict)] if isinstance(data_source, dict) else []
    non_stream = [
        f"{inst_id}:{row.get('source', '-')}/{row.get('stream_status', '-')}"
        for inst_id, row in (data_source.items() if isinstance(data_source, dict) else [])
        if isinstance(row, dict) and (row.get("source") != "stream" or row.get("stream_status") != "running")
    ]
    stream_ok = (not require_stream) or (bool(source_rows) and not non_stream)
    effective_latency_ms = latency_ms if runtime_sample_fresh else 0.0
    effective_runtime_ms = runtime_ms if runtime_sample_fresh else 0.0
    latency_ok = effective_latency_ms <= 0.0 or effective_latency_ms <= max_latency_ms
    runtime_ok = effective_runtime_ms <= 0.0 or effective_runtime_ms <= max_runtime_ms
    checks = [
        paper_health_check(
            "行情延迟门禁",
            latency_ok,
            "warn",
            f"上一 tick 样本已过期 {runtime_sample_age:.0f} 秒，等待下一次 tick 重新评估行情延迟。"
            if latency_ms > 0.0 and not runtime_sample_fresh and runtime_sample_age is not None
            else
            f"最近行情延迟 {latency_ms:.0f} ms，上限 {max_latency_ms} ms。"
            if latency_ms > 0.0
            else f"尚无行情延迟样本，上限 {max_latency_ms} ms。",
            latency_ms=latency_ms,
            effective_latency_ms=effective_latency_ms,
            limit_ms=max_latency_ms,
            sample_age_seconds=runtime_sample_age,
            sample_ttl_seconds=runtime_sample_ttl_seconds,
        ),
        paper_health_check(
            "引擎耗时门禁",
            runtime_ok,
            "warn",
            f"上一 tick 耗时样本已过期 {runtime_sample_age:.0f} 秒，不再阻断自动提交；下一次 tick 后重新评估。"
            if runtime_ms > 0.0 and not runtime_sample_fresh and runtime_sample_age is not None
            else
            f"最近 tick 耗时 {runtime_ms:.1f} ms，上限 {max_runtime_ms} ms。"
            if runtime_ms > 0.0
            else f"尚无 tick 耗时样本，上限 {max_runtime_ms} ms。",
            runtime_ms=runtime_ms,
            effective_runtime_ms=effective_runtime_ms,
            limit_ms=max_runtime_ms,
            sample_age_seconds=runtime_sample_age,
            sample_ttl_seconds=runtime_sample_ttl_seconds,
        ),
        paper_health_check(
            "WS 来源门禁",
            stream_ok,
            "warn",
            "未强制 WS 行情来源。"
            if not require_stream
            else "全部合约来自运行中的 WS 行情流。"
            if stream_ok
            else f"非 WS 或未运行来源：{', '.join(non_stream[:5]) or '无行情源'}。",
            require_stream=require_stream,
            non_stream_sources=non_stream,
        ),
        paper_health_check(
            "C++ 行情质量门禁",
            bool(cxx_quality.get("ready")),
            "halt" if cxx_quality.get("decision") == "block" else "warn",
            str(cxx_quality.get("message", "")),
            active=bool(cxx_quality.get("active")),
            decision=cxx_quality.get("decision", ""),
            source=cxx_quality.get("source", ""),
            age_seconds=cxx_quality.get("age_seconds"),
            max_age_seconds=cxx_quality.get("max_age_seconds"),
        ),
    ]
    ready = all(item.get("ok") for item in checks)
    reason = "引擎与行情门禁通过。" if ready else next(
        (item.get("message", "") for item in checks if not item.get("ok")),
        "引擎与行情门禁未通过。",
    )
    return {
        "ready": ready,
        "reason": reason,
        "engine": latest.get("engine") or performance.get("engine", ""),
        "runtime_ms": runtime_ms,
        "effective_runtime_ms": effective_runtime_ms,
        "runtime_sample_age_seconds": runtime_sample_age,
        "runtime_sample_ttl_seconds": runtime_sample_ttl_seconds,
        "market_latency_ms": latency_ms,
        "effective_market_latency_ms": effective_latency_ms,
        "max_market_latency_ms": max_latency_ms,
        "max_runtime_ms": max_runtime_ms,
        "require_stream": require_stream,
        "source_count": len(source_rows),
        "non_stream_sources": non_stream,
        "cxx_quality": {
            "ready": bool(cxx_quality.get("ready")),
            "active": bool(cxx_quality.get("active")),
            "decision": cxx_quality.get("decision", ""),
            "message": cxx_quality.get("message", ""),
            "age_seconds": cxx_quality.get("age_seconds"),
            "max_age_seconds": cxx_quality.get("max_age_seconds"),
        },
        "checks": checks,
    }


def paper_okx_auto_submission_guard(
    settings: dict[str, Any],
    auto_state: dict[str, Any],
    report: Optional[dict[str, Any]] = None,
    state: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    health = paper_okx_auto_order_health(auto_state, settings)
    engine_guard = paper_engine_submission_guard(settings, report, state)
    provenance = data_provenance_payload(settings, report, state)
    account_mode_guard = okx_account_mode_submission_guard(settings)
    max_live_orders = paper_okx_max_live_orders(settings)
    live_count = len(health["live_orders"])
    stale_count = len(health["stale_orders"])
    checks = [
        ops_automation_freeze_check(),
        paper_health_check(
            "陈旧 OKX 挂单",
            stale_count == 0,
            "warn",
            "未发现陈旧挂单。"
            if stale_count == 0
            else f"{stale_count} 个挂单超过 {health['stale_live_limit_seconds']} 秒未终态，暂停继续发新挂单。",
        ),
        paper_health_check(
            "OKX 活跃挂单上限",
            live_count < max_live_orders,
            "warn",
            f"当前 {live_count}/{max_live_orders} 个活跃挂单。"
            if live_count < max_live_orders
            else f"当前 {live_count}/{max_live_orders} 个活跃挂单，达到上限后暂停继续发新挂单。",
        ),
        paper_health_check(
            "数据真实性门禁",
            bool(provenance.get("execution_ready")),
            "halt",
            provenance.get("reason", "数据来源门禁未通过。"),
        ),
        paper_health_check(
            "OKX 账户模式",
            bool(account_mode_guard.get("ok")),
            "halt",
            str(account_mode_guard.get("message", "")),
            cooldown_seconds=account_mode_guard.get("cooldown_seconds"),
            latest_age_seconds=account_mode_guard.get("latest_age_seconds"),
            latest_error_key=account_mode_guard.get("latest_error_key", ""),
            latest_trace_id=account_mode_guard.get("latest_trace_id", ""),
        ),
    ]
    checks.extend(engine_guard["checks"])
    ready = all(item.get("ok") for item in checks)
    reason = "OKX 自动提交门禁通过。"
    if not ready:
        reason = next((item.get("message", "") for item in checks if not item.get("ok")), "OKX 自动提交门禁未通过。")
    return {
        "ready": ready,
        "reason": reason,
        "max_live_orders": max_live_orders,
        "live_order_count": live_count,
        "stale_order_count": stale_count,
        "stale_live_limit_seconds": health["stale_live_limit_seconds"],
        "checks": checks,
        "engine_guard": engine_guard,
        "account_mode_guard": account_mode_guard,
        "data_provenance": provenance,
        "live_orders": health["live_orders"][:30],
        "stale_orders": health["stale_orders"][:30],
    }


def paper_broker_fill_backfill_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Return controls for reconciling OKX fills into the local order journal."""
    return {
        "enabled": bool_setting_from_any(settings.get("paper_broker_fill_backfill", True), True),
        "max_orders": bounded_int(settings.get("paper_broker_fill_backfill_max_orders", 50), 50, 1, 500),
    }


def latest_okx_filled_details_by_source(limit: int = 1000) -> dict[str, dict[str, Any]]:
    """Join submit audits and later order syncs by source_order_id.

    The submit audit carries platform-only sizing metadata such as `_ctVal`;
    later sync audits carry the latest OKX accFillSz/state.  Joining them lets
    the repair path convert contract fills into the base quantity used by the
    local paper portfolio without calling OKX again.
    """
    submissions = latest_okx_submission_orders_by_source(limit)
    details: dict[str, dict[str, Any]] = {}
    for row in reversed(read_okx_audit(limit)):
        action = str(row.get("action", ""))
        if action not in {"order_submitted", "order_synced", "order_cancelled", "paper_auto_order_synced"}:
            continue
        source_order_id = str(row.get("source_order_id", "")).strip()
        if not source_order_id:
            continue
        detail = row.get("order_detail", {}) if isinstance(row.get("order_detail"), dict) else {}
        if float_from_any(detail.get("acc_fill_sz")) <= BROKER_FILL_EPS:
            continue
        identity = row.get("identity", {}) if isinstance(row.get("identity"), dict) else {}
        if not identity:
            identity = okx_audit_order_identity(row) or {}
        order = row.get("order", {}) if isinstance(row.get("order"), dict) else {}
        if not order:
            order = submissions.get(source_order_id, {})
        details[source_order_id] = {
            "source_order_id": source_order_id,
            "audit_id": row.get("id", ""),
            "audit_ts": row.get("ts", ""),
            "audit_action": action,
            "identity": identity,
            "detail": detail,
            "order": order,
        }
    return details


def paper_broker_fill_backfill_plan_payload(
    params: dict[str, list[str]],
    settings_override: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    state = read_paper_state()
    settings = settings_override if isinstance(settings_override, dict) else state.get("settings", {})
    settings = settings if isinstance(settings, dict) else {}
    controls = paper_broker_fill_backfill_settings(settings)
    max_orders = bounded_int(
        params.get("maxOrders", [str(controls["max_orders"])])[0],
        controls["max_orders"],
        1,
        500,
    )
    state_by_key = order_state_index(5000)
    actions: list[dict[str, Any]] = []
    keep: list[dict[str, Any]] = []
    normalizable = 0
    for source_order_id, record in latest_okx_filled_details_by_source(2000).items():
        row = state_by_key.get(source_order_id, {"order_key": source_order_id})
        action = broker_fill_backfill_action_from_state(
            row,
            source_order_id=source_order_id,
            identity=record.get("identity", {}) if isinstance(record.get("identity"), dict) else {},
            detail=record.get("detail", {}) if isinstance(record.get("detail"), dict) else {},
            order=record.get("order", {}) if isinstance(record.get("order"), dict) else {},
            audit_id=str(record.get("audit_id", "")),
        )
        action["audit_ts"] = record.get("audit_ts", "")
        action["audit_action"] = record.get("audit_action", "")
        action["identity"] = record.get("identity", {}) if isinstance(record.get("identity"), dict) else {}
        action["detail"] = record.get("detail", {}) if isinstance(record.get("detail"), dict) else {}
        action["order"] = record.get("order", {}) if isinstance(record.get("order"), dict) else {}
        if broker_sync_normalization_needed(row, action):
            normalizable += 1
        if bool(controls["enabled"]) and action.get("eligible"):
            actions.append(action)
        else:
            keep.append(action)
    actions.sort(
        key=lambda item: (
            float_from_any(item.get("broker_fill_delta_qty")),
            str(item.get("audit_ts", "")),
        ),
        reverse=True,
    )
    actionable_total = len(actions)
    actionable_delta_total = sum(float_from_any(item.get("broker_fill_delta_qty")) for item in actions)
    actions = actions[:max_orders]
    public_actions = [
        {key: value for key, value in action.items() if key not in {"identity", "detail", "order"}}
        for action in actions
    ]
    public_keep = [
        {key: value for key, value in action.items() if key not in {"identity", "detail", "order"}}
        for action in keep[:max_orders]
    ]
    return {
        "ok": True,
        "generated_at": now_iso(),
        "execution_mode": "dry_run",
        "auto_apply_enabled": bool(controls["enabled"]),
        "max_orders": max_orders,
        "summary": {
            "filled_audit_orders": actionable_total + len(keep),
            "actionable": actionable_total,
            "returned_actions": len(actions),
            "normalizable_syncs": normalizable,
            "kept": len(keep),
            "broker_fill_delta_qty": actionable_delta_total,
        },
        "actions": public_actions,
        "keep": public_keep,
    }


def apply_paper_broker_fill_backfill(
    settings: dict[str, Any],
    *,
    source: str,
    max_orders: Optional[int] = None,
) -> dict[str, Any]:
    controls = paper_broker_fill_backfill_settings(settings)
    summary: dict[str, Any] = {
        "enabled": controls["enabled"],
        "checked_at": now_iso(),
        "source": source,
        "max_orders": max_orders or controls["max_orders"],
        "requested": 0,
        "backfilled": 0,
        "normalized": 0,
        "synced": 0,
        "skipped": "",
        "events": [],
    }
    if not controls["enabled"]:
        summary["skipped"] = "OKX 成交回补未启用。"
        return summary
    raw_records = latest_okx_filled_details_by_source(2000)
    state_by_key = order_state_index(5000)
    actions: list[dict[str, Any]] = []
    normalize_actions: list[dict[str, Any]] = []
    for source_order_id, record in raw_records.items():
        row = state_by_key.get(source_order_id, {"order_key": source_order_id})
        action = broker_fill_backfill_action_from_state(
            row,
            source_order_id=source_order_id,
            identity=record.get("identity", {}) if isinstance(record.get("identity"), dict) else {},
            detail=record.get("detail", {}) if isinstance(record.get("detail"), dict) else {},
            order=record.get("order", {}) if isinstance(record.get("order"), dict) else {},
            audit_id=str(record.get("audit_id", "")),
        )
        if action.get("eligible"):
            action["identity"] = record.get("identity", {}) if isinstance(record.get("identity"), dict) else {}
            action["detail"] = record.get("detail", {}) if isinstance(record.get("detail"), dict) else {}
            action["order"] = record.get("order", {}) if isinstance(record.get("order"), dict) else {}
            actions.append(action)
        elif broker_sync_normalization_needed(row, action):
            action["identity"] = record.get("identity", {}) if isinstance(record.get("identity"), dict) else {}
            action["detail"] = record.get("detail", {}) if isinstance(record.get("detail"), dict) else {}
            action["order"] = record.get("order", {}) if isinstance(record.get("order"), dict) else {}
            normalize_actions.append(action)
    actions.sort(
        key=lambda item: float_from_any(item.get("broker_fill_delta_qty")),
        reverse=True,
    )
    max_count = max_orders or controls["max_orders"]
    actions = actions[:max_count]
    normalize_actions = normalize_actions[:max(0, max_count - len(actions))]
    summary["requested"] = len(actions) + len(normalize_actions)
    if not actions and not normalize_actions:
        summary["skipped"] = "未发现需要按 OKX broker_sync 回补的成交。"
        return summary

    for action in actions:
        fill_event = append_broker_fill_backfill_event(action, source=source)
        if not fill_event:
            continue
        sync_event = append_broker_order_journal_sync(
            action.get("order_key", ""),
            action.get("identity", {}) if isinstance(action.get("identity"), dict) else {},
            action.get("detail", {}) if isinstance(action.get("detail"), dict) else {},
            order=action.get("order", {}) if isinstance(action.get("order"), dict) else {},
            audit_id=str(action.get("audit_id", "")),
            sync_status="broker_fill_backfill",
            reason="OKX 成交回补后刷新 broker_sync 归一化数量。",
        )
        summary["backfilled"] += 1
        if sync_event:
            summary["synced"] += 1
        summary["events"].append(
            {
                "fill_event_id": fill_event.get("id", ""),
                "sync_event_id": sync_event.get("id", "") if sync_event else "",
                "order_key": action.get("order_key", ""),
                "delta_qty": action.get("broker_fill_delta_qty", 0.0),
                "broker_order_id": action.get("broker_order_id", ""),
            }
        )

    for action in normalize_actions:
        sync_event = append_broker_order_journal_sync(
            action.get("order_key", ""),
            action.get("identity", {}) if isinstance(action.get("identity"), dict) else {},
            action.get("detail", {}) if isinstance(action.get("detail"), dict) else {},
            order=action.get("order", {}) if isinstance(action.get("order"), dict) else {},
            audit_id=str(action.get("audit_id", "")),
            sync_status="broker_quantity_normalized",
            reason="刷新历史 broker_sync 的合约 ctVal/base 数量字段。",
        )
        if sync_event:
            summary["normalized"] += 1
            summary["synced"] += 1
            summary["events"].append(
                {
                    "fill_event_id": "",
                    "sync_event_id": sync_event.get("id", ""),
                    "order_key": action.get("order_key", ""),
                    "delta_qty": 0.0,
                    "broker_order_id": action.get("broker_order_id", ""),
                    "normalized_only": True,
                }
            )

    append_platform_event(
        "paper.broker_fills_backfilled",
        "paper_engine",
        {
            "source": source,
            "requested": summary["requested"],
            "backfilled": summary["backfilled"],
            "normalized": summary["normalized"],
            "synced": summary["synced"],
            "events": summary["events"],
        },
        severity="warn" if summary["backfilled"] else "info",
        message=f"OKX 成交回补到本地订单状态机 {summary['backfilled']} 笔，归一化 {summary['normalized']} 笔。",
    )
    return summary


def attach_broker_fill_backfill_result(auto_state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    auto_state["last_broker_fill_backfill"] = result
    if int(result.get("backfilled", 0) or 0) > 0 or int(result.get("normalized", 0) or 0) > 0:
        auto_state["last_broker_fill_backfill_effective"] = result
    return auto_state


def latest_effective_broker_fill_backfill_from_events() -> dict[str, Any]:
    for event in read_platform_events(100, event_type="paper.broker_fills_backfilled"):
        if int(event.get("backfilled", 0) or 0) <= 0 and int(event.get("normalized", 0) or 0) <= 0:
            continue
        return {
            "checked_at": event.get("ts", ""),
            "source": event.get("source", ""),
            "requested": event.get("requested", 0),
            "backfilled": event.get("backfilled", 0),
            "normalized": event.get("normalized", 0),
            "event_id": event.get("id", ""),
        }
    return {}


def apply_paper_broker_fill_backfill_payload(body: dict[str, Any]) -> dict[str, Any]:
    if str(body.get("confirm", "")) != "BACKFILL_OKX_BROKER_FILLS":
        return {
            "ok": False,
            "error": "OKX 成交回补必须带 confirm=BACKFILL_OKX_BROKER_FILLS。",
            "requires_confirmation": True,
        }
    with PAPER_LOCK:
        state = read_paper_state()
        settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
    controls = paper_broker_fill_backfill_settings(settings)
    max_orders = bounded_int(
        body.get("max_orders", body.get("maxOrders", controls["max_orders"])),
        controls["max_orders"],
        1,
        500,
    )
    result = apply_paper_broker_fill_backfill(
        settings,
        source="manual_orders_page",
        max_orders=max_orders,
    )
    with PAPER_LOCK:
        state = read_paper_state()
        auto = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
        auto = attach_broker_fill_backfill_result(auto, result)
        state["okx_auto_submit"] = auto
        write_paper_state(state)
    return {
        "ok": True,
        "backfill": result,
        "plan": paper_broker_fill_backfill_plan_payload({}),
        "paper": compact_paper_state_for_response(read_paper_state()),
    }


def paper_broker_terminal_sync_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Return controls for syncing OKX terminal audit states into paper orders.

    这条链路只做本地 journal 回补：OKX 审计已经证明订单终态，但本地状态机仍
    停在 pending/live 时，写入 `order.broker_sync` 让 UI、风控和订单上限看到终态。
    它不向 OKX 发送下单、撤单或改单请求。
    """
    return {
        "enabled": bool_setting_from_any(settings.get("paper_broker_terminal_sync", True), True),
        "max_orders": bounded_int(settings.get("paper_broker_terminal_sync_max_orders", 20), 20, 1, 200),
    }


def paper_broker_terminal_sync_plan_payload(
    params: dict[str, list[str]],
    settings_override: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    state = read_paper_state()
    settings = settings_override if isinstance(settings_override, dict) else state.get("settings", {})
    settings = settings if isinstance(settings, dict) else {}
    controls = paper_broker_terminal_sync_settings(settings)
    max_orders = bounded_int(
        params.get("maxOrders", params.get("max_orders", [str(controls["max_orders"])]))[0],
        controls["max_orders"],
        1,
        200,
    )
    stale_seconds = bounded_int(
        params.get("staleSeconds", params.get("stale_seconds", ["600"]))[0],
        600,
        30,
        86400,
    )
    backend_query = urlencode(
        {
            "limit": "5000",
            "max_orders": str(max_orders),
            "stale_seconds": str(stale_seconds),
            "enabled": "true" if controls["enabled"] else "false",
        }
    )
    backend_plan = invoke_backendd_route(
        f"/api/backend/orders/broker_terminal_sync_plan?{backend_query}",
        timeout_seconds=3.0,
    )
    if (
        isinstance(backend_plan, dict)
        and backend_plan.get("service") == "backendd"
        and isinstance(backend_plan.get("actions"), list)
    ):
        backend_plan["engine"] = "cpp_backendd"
        backend_plan["auto_apply_enabled"] = bool(controls["enabled"])
        backend_plan["max_orders"] = max_orders
        return backend_plan
    return {
        "ok": False,
        "generated_at": now_iso(),
        "engine": "python_proxy",
        "execution_mode": "dry_run",
        "auto_apply_enabled": bool(controls["enabled"]),
        "max_orders": max_orders,
        "summary": {"terminal_mismatch_issues": 0, "actionable": 0, "kept": 0},
        "actions": [],
        "keep": [],
        "error": backend_plan.get("error", "C++ backendd 终态同步计划不可用。") if isinstance(backend_plan, dict) else "C++ backendd 终态同步计划不可用。",
    }


def broker_terminal_sync_action_allowed(action: dict[str, Any], current_state: dict[str, Any]) -> tuple[bool, str]:
    if not action.get("eligible"):
        return False, "C++ 计划未标记为可回补。"
    if str(action.get("action", "")) != "backfill_broker_terminal_state":
        return False, "不是 broker 终态回补动作。"
    if current_state.get("terminal"):
        return False, "本地订单已经是终态，无需重复回补。"
    source_key = str(action.get("source_order_id") or action.get("order_key") or "").strip()
    if not source_key:
        return False, "缺少本地 source_order_id。"
    audit_state = str(action.get("audit_state") or "").lower().strip()
    if audit_state not in OKX_TERMINAL_ORDER_STATES:
        return False, "OKX 审计状态不是终态。"
    broker_ord_id = str(action.get("broker_order_id") or "").strip()
    broker_cl_ord_id = str(action.get("broker_cl_ord_id") or "").strip()
    audit_ord_id = str(action.get("audit_ord_id") or "").strip()
    audit_cl_ord_id = str(action.get("audit_cl_ord_id") or "").strip()
    same_ord = bool(broker_ord_id and audit_ord_id and broker_ord_id == audit_ord_id)
    same_cl_ord = bool(broker_cl_ord_id and audit_cl_ord_id and broker_cl_ord_id == audit_cl_ord_id)
    if not (same_ord or same_cl_ord):
        return False, "OKX 审计 ordId/clOrdId 与本地 broker identity 不匹配。"
    if audit_state == "filled":
        raw_fill = float_from_any(action.get("broker_filled_qty"))
        base_fill = float_from_any(action.get("broker_filled_base_qty"))
        if raw_fill <= BROKER_FILL_EPS and base_fill <= BROKER_FILL_EPS:
            return False, "OKX filled 终态缺少成交数量，避免把未知成交写成已成交。"
    return True, "OKX 审计终态和本地 broker identity 已匹配。"


def broker_terminal_sync_detail_from_action(action: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    inst_id = str(action.get("inst_id") or "").upper().strip()
    audit_state = str(action.get("audit_state") or "").lower().strip()
    ord_id = str(action.get("audit_ord_id") or action.get("broker_order_id") or "").strip()
    cl_ord_id = str(action.get("audit_cl_ord_id") or action.get("broker_cl_ord_id") or "").strip()
    px = float_from_any(action.get("limit_price"))
    raw_order_qty = float_from_any(action.get("broker_order_qty"))
    raw_filled_qty = float_from_any(action.get("broker_filled_qty"))
    contract_value = float_from_any(action.get("broker_contract_value"))
    identity = {"instId": inst_id, "ordId": ord_id, "clOrdId": cl_ord_id}
    detail = {
        "inst_id": inst_id,
        "state": audit_state,
        "ord_id": ord_id,
        "cl_ord_id": cl_ord_id,
        "side": action.get("side", ""),
        "ord_type": "post_only",
        "px": px,
        "sz": raw_order_qty,
        "acc_fill_sz": raw_filled_qty,
        "avg_px": px if raw_filled_qty > BROKER_FILL_EPS else "",
        "ctVal": contract_value,
        "u_time": now_iso(),
    }
    order = {
        "instId": inst_id,
        "ordType": "post_only",
        "px": px,
        "sz": raw_order_qty,
        "_ctVal": contract_value,
    }
    return identity, detail, order


def apply_paper_broker_terminal_sync(
    settings: dict[str, Any],
    *,
    source: str,
    max_orders: Optional[int] = None,
) -> dict[str, Any]:
    controls = paper_broker_terminal_sync_settings(settings)
    summary: dict[str, Any] = {
        "enabled": controls["enabled"],
        "checked_at": now_iso(),
        "source": source,
        "max_orders": max_orders or controls["max_orders"],
        "requested": 0,
        "synced": 0,
        "skipped": "",
        "events": [],
        "plan": {},
    }
    if not controls["enabled"]:
        summary["skipped"] = "OKX 终态回补未启用。"
        return summary
    plan = paper_broker_terminal_sync_plan_payload(
        {"maxOrders": [str(max_orders or controls["max_orders"])]},
        settings_override=settings,
    )
    summary["plan"] = {"summary": plan.get("summary", {}), "engine": plan.get("engine", "")}
    actions = [item for item in (plan.get("actions", []) or []) if isinstance(item, dict)]
    summary["requested"] = len(actions)
    if not actions:
        summary["skipped"] = "未发现 OKX 已终态但本地仍活跃的订单。"
        return summary

    state_by_key = order_state_index(5000)
    submissions = latest_okx_submission_orders_by_source(2000)
    for action in actions:
        source_key = str(action.get("source_order_id") or action.get("order_key") or "").strip()
        current_state = state_by_key.get(source_key, {})
        allowed, reason = broker_terminal_sync_action_allowed(action, current_state)
        if not allowed:
            summary["events"].append({"order_key": source_key, "skipped": True, "reason": reason})
            continue

        identity, detail, order = broker_terminal_sync_detail_from_action(action)
        submission_order = submissions.get(source_key, {})
        if isinstance(submission_order, dict):
            order.update({key: value for key, value in submission_order.items() if value not in (None, "")})
        for key in ("strategy_id", "agent_id", "trading_unit_id", "trading_unit_name", "strategy_ids", "strategy_attribution"):
            if current_state.get(key):
                order[key] = current_state.get(key)
        sync_event = append_broker_order_journal_sync(
            source_key,
            identity,
            detail,
            order=order,
            audit_id=str(action.get("audit_id", "")),
            sync_status="broker_terminal_backfill",
            reason="OKX 审计已记录终态，本地订单状态机回补 broker_sync 终态。",
        )
        if not sync_event:
            summary["events"].append({"order_key": source_key, "skipped": True, "reason": "写入 order.broker_sync 失败。"})
            continue
        summary["synced"] += 1
        summary["events"].append(
            {
                "sync_event_id": sync_event.get("id", ""),
                "order_key": source_key,
                "broker_order_id": identity.get("ordId", ""),
                "broker_cl_ord_id": identity.get("clOrdId", ""),
                "audit_id": action.get("audit_id", ""),
                "audit_state": action.get("audit_state", ""),
            }
        )

    if summary["synced"] <= 0:
        summary["skipped"] = "没有订单通过最终本地安全校验。"
        return summary
    append_platform_event(
        "paper.broker_terminal_synced",
        "paper_engine",
        {
            "source": source,
            "requested": summary["requested"],
            "synced": summary["synced"],
            "events": summary["events"],
        },
        severity="warn",
        message=f"OKX 终态回补到本地订单状态机 {summary['synced']} 笔。",
    )
    return summary


def attach_broker_terminal_sync_result(auto_state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    auto_state["last_broker_terminal_sync"] = result
    if int(result.get("synced", 0) or 0) > 0:
        auto_state["last_broker_terminal_sync_effective"] = result
    return auto_state


def latest_effective_broker_terminal_sync_from_events() -> dict[str, Any]:
    for event in read_platform_events(100, event_type="paper.broker_terminal_synced"):
        if int(event.get("synced", 0) or 0) <= 0:
            continue
        return {
            "checked_at": event.get("ts", ""),
            "source": event.get("source", ""),
            "requested": event.get("requested", 0),
            "synced": event.get("synced", 0),
            "event_id": event.get("id", ""),
        }
    return {}


def apply_paper_broker_terminal_sync_payload(body: dict[str, Any]) -> dict[str, Any]:
    if str(body.get("confirm", "")) != "SYNC_OKX_TERMINAL_PAPER_ORDERS":
        return {
            "ok": False,
            "error": "OKX 终态回补必须带 confirm=SYNC_OKX_TERMINAL_PAPER_ORDERS。",
            "requires_confirmation": True,
        }
    with PAPER_LOCK:
        state = read_paper_state()
        settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
    controls = paper_broker_terminal_sync_settings(settings)
    max_orders = bounded_int(
        body.get("max_orders", body.get("maxOrders", controls["max_orders"])),
        controls["max_orders"],
        1,
        200,
    )
    result = apply_paper_broker_terminal_sync(
        settings,
        source="manual_orders_page",
        max_orders=max_orders,
    )
    with PAPER_LOCK:
        state = read_paper_state()
        auto = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
        auto = attach_broker_terminal_sync_result(auto, result)
        state["okx_auto_submit"] = auto
        write_paper_state(state)
    return {
        "ok": True,
        "terminal_sync": result,
        "plan": paper_broker_terminal_sync_plan_payload({}),
        "paper": compact_paper_state_for_response(read_paper_state()),
    }


def paper_stale_broker_reconcile_plan_payload(
    params: dict[str, list[str]],
    settings_override: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Return C++ plan for stale active orders that already have OKX identity."""
    state = read_paper_state()
    settings = settings_override if isinstance(settings_override, dict) else state.get("settings", {})
    settings = settings if isinstance(settings, dict) else {}
    controls = paper_auto_cancel_settings(settings)
    min_age = bounded_int(
        params.get("minAgeSeconds", params.get("min_age_seconds", [str(controls["min_age_seconds"])]))[0],
        controls["min_age_seconds"],
        30,
        86400,
    )
    max_orders = bounded_int(
        params.get("maxOrders", params.get("max_orders", [str(controls["max_orders"])]))[0],
        controls["max_orders"],
        1,
        200,
    )
    backend_query = urlencode(
        {
            "limit": "5000",
            "min_age_seconds": str(min_age),
            "max_orders": str(max_orders),
            "enabled": "true" if controls["enabled"] else "false",
        }
    )
    backend_plan = invoke_backendd_route(
        f"/api/backend/orders/stale_broker_reconcile_plan?{backend_query}",
        timeout_seconds=3.0,
    )
    if (
        isinstance(backend_plan, dict)
        and backend_plan.get("service") == "backendd"
        and isinstance(backend_plan.get("actions"), list)
    ):
        backend_plan["engine"] = "cpp_backendd"
        backend_plan["auto_cancel_enabled"] = bool(controls["enabled"])
        backend_plan["min_age_seconds"] = min_age
        backend_plan["max_orders"] = max_orders
        return backend_plan
    return {
        "ok": False,
        "generated_at": now_iso(),
        "engine": "python_proxy",
        "execution_mode": "dry_run",
        "auto_cancel_enabled": bool(controls["enabled"]),
        "min_age_seconds": min_age,
        "max_orders": max_orders,
        "summary": {"stale_broker_issues": 0, "actionable": 0, "kept": 0},
        "actions": [],
        "keep": [],
        "error": backend_plan.get("error", "C++ backendd 陈旧 broker 订单计划不可用。") if isinstance(backend_plan, dict) else "C++ backendd 陈旧 broker 订单计划不可用。",
    }


def stale_broker_reconcile_identity(action: dict[str, Any]) -> dict[str, str]:
    return {
        "instId": str(action.get("inst_id") or "").upper().strip(),
        "ordId": str(action.get("broker_order_id") or "").strip(),
        "clOrdId": str(action.get("broker_cl_ord_id") or "").strip(),
    }


def stale_broker_reconcile_submission_order(source_key: str, action: dict[str, Any], submissions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    order = dict(submissions.get(source_key, {}) if isinstance(submissions.get(source_key), dict) else {})
    order.setdefault("instId", action.get("inst_id", ""))
    order.setdefault("ordType", "post_only")
    order.setdefault("px", action.get("limit_price", ""))
    order.setdefault("sz", action.get("broker_order_qty", ""))
    if float_from_any(order.get("_ctVal")) <= BROKER_FILL_EPS and float_from_any(action.get("broker_contract_value")) > BROKER_FILL_EPS:
        order["_ctVal"] = action.get("broker_contract_value")
    for key in ("strategy_id", "agent_id", "trading_unit_id", "trading_unit_name"):
        if action.get(key):
            order[key] = action.get(key)
    return order


def apply_paper_stale_broker_reconcile(
    settings: dict[str, Any],
    *,
    source: str,
    max_orders: Optional[int] = None,
    cancel_live: Optional[bool] = None,
) -> dict[str, Any]:
    """Query OKX for stale broker-backed orders, then sync terminal or cancel live.

    这是修复“昨天的模拟盘挂单一直留在本地 active”的主入口。它只处理已有
    ordId/clOrdId 的订单：先查 OKX 私有订单详情；如果 OKX 已终态，回补本地
    broker_sync；如果 OKX 仍 live 且自动撤单允许，再走模拟盘撤单。
    """
    controls = paper_auto_cancel_settings(settings)
    should_cancel_live = controls["enabled"] if cancel_live is None else bool(cancel_live)
    summary: dict[str, Any] = {
        "enabled": controls["enabled"],
        "checked_at": now_iso(),
        "source": source,
        "min_age_seconds": controls["min_age_seconds"],
        "max_orders": max_orders or controls["max_orders"],
        "cancel_live": should_cancel_live,
        "requested": 0,
        "queried": 0,
        "terminal_synced": 0,
        "cancel_requested": 0,
        "cancel_succeeded": 0,
        "cancel_failed": 0,
        "sync_failed": 0,
        "skipped": "",
        "events": [],
    }
    if not settings.get("okx_auto_submit"):
        summary["skipped"] = "OKX 自动提交未启用，不执行陈旧 broker 订单对账。"
        return summary
    if should_cancel_live:
        gate = okx_simulated_submit_gate()
        if not gate.get("ready"):
            summary["skipped"] = str(gate.get("reason", "OKX 模拟盘交易门禁未通过。"))
            summary["gate"] = gate
            return summary

    plan = paper_stale_broker_reconcile_plan_payload(
        {
            "minAgeSeconds": [str(controls["min_age_seconds"])],
            "maxOrders": [str(max_orders or controls["max_orders"])],
        },
        settings_override=settings,
    )
    actions = [item for item in (plan.get("actions", []) or []) if isinstance(item, dict)]
    summary["requested"] = len(actions)
    summary["plan"] = {"summary": plan.get("summary", {}), "engine": plan.get("engine", "")}
    if not actions:
        summary["skipped"] = "未发现需要主动查 OKX 的陈旧 broker 订单。"
        return summary

    submissions = latest_okx_submission_orders_by_source(2000)
    for action in actions:
        source_key = str(action.get("source_order_id") or action.get("order_key") or "").strip()
        identity = stale_broker_reconcile_identity(action)
        if not identity["instId"] or not (identity["ordId"] or identity["clOrdId"]):
            summary["sync_failed"] += 1
            summary["events"].append({"order_key": source_key, "ok": False, "error": "缺少 OKX instId/ordId/clOrdId。"})
            continue
        detail_payload = okx_order_detail_payload(identity)
        summary["queried"] += 1
        if not detail_payload.get("ok"):
            audit = append_okx_audit(
                "paper_stale_broker_order_sync_failed",
                {
                    "ok": False,
                    "source_order_id": source_key,
                    "identity": identity,
                    "error": detail_payload.get("error", "OKX 订单详情查询失败。"),
                    "result": detail_payload,
                    "request_id": detail_payload.get("request_id", ""),
                },
            )
            summary["sync_failed"] += 1
            summary["events"].append(
                {
                    "order_key": source_key,
                    "ok": False,
                    "error": detail_payload.get("error", ""),
                    "audit_id": audit.get("id", ""),
                }
            )
            continue

        detail = detail_payload.get("order", {}) if isinstance(detail_payload.get("order"), dict) else {}
        broker_state = str(detail.get("state", "")).lower().strip()
        audit = append_okx_audit(
            "paper_stale_broker_order_synced",
            {
                "ok": True,
                "source_order_id": source_key,
                "identity": identity,
                "previous_detail": {
                    "state": action.get("broker_state", ""),
                    "px": action.get("limit_price", ""),
                    "sz": action.get("broker_order_qty", ""),
                },
                "order_detail": detail,
                "request_id": detail_payload.get("request_id", ""),
            },
        )
        order = stale_broker_reconcile_submission_order(source_key, action, submissions)
        terminal_before_cancel = broker_state in OKX_TERMINAL_ORDER_STATES
        if terminal_before_cancel:
            sync_event = append_broker_order_journal_sync(
                source_key,
                identity,
                detail,
                order=order,
                audit_id=str(audit.get("id", "")),
                sync_status="stale_broker_terminal_sync",
                reason="陈旧 broker 订单主动查单发现 OKX 已终态，回补本地订单状态。",
            )
            summary["terminal_synced"] += 1 if sync_event else 0
            summary["events"].append(
                {
                    "order_key": source_key,
                    "ok": bool(sync_event),
                    "state": broker_state,
                    "sync_event_id": sync_event.get("id", "") if sync_event else "",
                    "audit_id": audit.get("id", ""),
                }
            )
            continue

        if not should_cancel_live:
            summary["events"].append(
                {
                    "order_key": source_key,
                    "ok": True,
                    "state": broker_state or "unknown",
                    "action": "kept_live_after_query",
                    "audit_id": audit.get("id", ""),
                }
            )
            continue

        cancel_payload = {
            "confirm": "CANCEL_OKX_SIMULATED_ORDER",
            "instId": identity["instId"],
            "ordId": identity["ordId"],
            "clOrdId": identity["clOrdId"],
            "_source_order_id": source_key,
        }
        cancel_result = okx_cancel_order(cancel_payload)
        summary["cancel_requested"] += 1
        detail_after = detail
        if identity["instId"] and (identity["ordId"] or identity["clOrdId"]):
            detail_after_payload = okx_order_detail_payload(identity)
            if detail_after_payload.get("ok"):
                detail_after = detail_after_payload.get("order", {}) if isinstance(detail_after_payload.get("order"), dict) else detail_after
        terminal_after_cancel = str(detail_after.get("state", "")).lower().strip() in OKX_TERMINAL_ORDER_STATES
        effective_ok = bool(cancel_result.get("ok")) or terminal_after_cancel
        if effective_ok:
            summary["cancel_succeeded"] += 1
        else:
            summary["cancel_failed"] += 1
        sync_event = append_broker_order_journal_sync(
            source_key,
            identity,
            detail_after,
            order=order,
            audit_id=str(cancel_result.get("audit_id", "")),
            sync_status="stale_broker_cancel_requested" if not terminal_after_cancel else "stale_broker_cancelled",
            reason="陈旧 broker 订单主动查单后执行 OKX 模拟盘撤单并同步状态。",
        )
        summary["events"].append(
            {
                "order_key": source_key,
                "ok": effective_ok,
                "state": detail_after.get("state", broker_state),
                "cancel_ok": bool(cancel_result.get("ok")),
                "terminal_after_cancel": terminal_after_cancel,
                "sync_event_id": sync_event.get("id", "") if sync_event else "",
                "audit_id": cancel_result.get("audit_id", ""),
                "error": "" if effective_ok else cancel_result.get("error", ""),
            }
        )

    if not summary["events"]:
        summary["skipped"] = "陈旧 broker 订单计划为空。"
        return summary
    append_platform_event(
        "paper.stale_broker_orders_reconciled",
        "paper_engine",
        {
            "source": source,
            "requested": summary["requested"],
            "queried": summary["queried"],
            "terminal_synced": summary["terminal_synced"],
            "cancel_requested": summary["cancel_requested"],
            "cancel_succeeded": summary["cancel_succeeded"],
            "cancel_failed": summary["cancel_failed"],
            "sync_failed": summary["sync_failed"],
            "events": summary["events"],
        },
        severity="warn" if summary["cancel_failed"] or summary["sync_failed"] else "info",
        message=(
            f"陈旧 OKX broker 订单对账 {summary['queried']} 笔，"
            f"终态回补 {summary['terminal_synced']}，撤单 {summary['cancel_succeeded']}/{summary['cancel_requested']}。"
        ),
    )
    return summary


def attach_stale_broker_reconcile_result(auto_state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    auto_state["last_stale_broker_reconcile"] = result
    if (
        int(result.get("terminal_synced", 0) or 0) > 0
        or int(result.get("cancel_succeeded", 0) or 0) > 0
        or int(result.get("cancel_requested", 0) or 0) > 0
    ):
        auto_state["last_stale_broker_reconcile_effective"] = result
    return auto_state


def latest_effective_stale_broker_reconcile_from_events() -> dict[str, Any]:
    for event in read_platform_events(100, event_type="paper.stale_broker_orders_reconciled"):
        if (
            int(event.get("terminal_synced", 0) or 0) <= 0
            and int(event.get("cancel_succeeded", 0) or 0) <= 0
            and int(event.get("cancel_requested", 0) or 0) <= 0
        ):
            continue
        return {
            "checked_at": event.get("ts", ""),
            "source": event.get("source", ""),
            "requested": event.get("requested", 0),
            "queried": event.get("queried", 0),
            "terminal_synced": event.get("terminal_synced", 0),
            "cancel_requested": event.get("cancel_requested", 0),
            "cancel_succeeded": event.get("cancel_succeeded", 0),
            "event_id": event.get("id", ""),
        }
    return {}


def apply_paper_stale_broker_reconcile_payload(body: dict[str, Any]) -> dict[str, Any]:
    if str(body.get("confirm", "")) != "RECONCILE_STALE_OKX_BROKER_ORDERS":
        return {
            "ok": False,
            "error": "陈旧 OKX broker 订单对账必须带 confirm=RECONCILE_STALE_OKX_BROKER_ORDERS。",
            "requires_confirmation": True,
        }
    cancel_live = bool_setting_from_any(body.get("cancel_live", body.get("cancelLive", "false")), False)
    if cancel_live and str(body.get("cancel_confirm", body.get("cancelConfirm", ""))) != "CANCEL_STALE_OKX_SIMULATED_ORDERS":
        return {
            "ok": False,
            "error": "撤销陈旧 OKX 模拟盘挂单必须额外带 cancel_confirm=CANCEL_STALE_OKX_SIMULATED_ORDERS。",
            "requires_cancel_confirmation": True,
        }
    with PAPER_LOCK:
        state = read_paper_state()
        settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
    controls = paper_auto_cancel_settings(settings)
    max_orders = bounded_int(
        body.get("max_orders", body.get("maxOrders", controls["max_orders"])),
        controls["max_orders"],
        1,
        200,
    )
    result = apply_paper_stale_broker_reconcile(
        settings,
        source="manual_orders_page",
        max_orders=max_orders,
        cancel_live=cancel_live,
    )
    with PAPER_LOCK:
        state = read_paper_state()
        auto = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
        auto = attach_stale_broker_reconcile_result(auto, result)
        state["okx_auto_submit"] = auto
        write_paper_state(state)
    return {
        "ok": True,
        "reconcile": result,
        "plan": paper_stale_broker_reconcile_plan_payload({}),
        "paper": compact_paper_state_for_response(read_paper_state()),
    }


def paper_local_order_repair_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Return controls for repairing local-only stale paper orders.

    This is different from OKX stale-order cancellation.  It only writes local
    `order.expired` journal events for orders that never obtained an OKX order
    id and have no successful submitted trace.  It must not hide real broker
    orders, so anything with ordId/clOrdId or a latest submitted trace is left
    for OKX reconciliation/cancel logic instead.
    """
    return {
        "enabled": bool_setting_from_any(settings.get("paper_local_repair_stale_orders", True), True),
        "min_age_seconds": bounded_int(settings.get("paper_local_repair_min_age_seconds", 300), 300, 30, 86400),
        "max_orders": bounded_int(settings.get("paper_local_repair_max_orders", 20), 20, 1, 200),
    }


def local_repair_issue_actionable(issue: dict[str, Any], min_age_seconds: int) -> bool:
    if not isinstance(issue, dict):
        return False
    if str(issue.get("broker_order_id", "")).strip():
        return False
    age = float_from_any(issue.get("age_seconds"), -1.0)
    if age < min_age_seconds:
        return False
    code = str(issue.get("code", ""))
    latest_trace_status = str(issue.get("latest_trace_status", "")).lower().strip()
    if latest_trace_status == "submitted":
        return False
    return code in {
        "active_without_okx_submit",
        "active_after_failed_execution",
        "stale_active_order",
    }


def paper_local_order_repair_plan_payload(
    params: dict[str, list[str]],
    settings_override: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    state = read_paper_state()
    settings = settings_override if isinstance(settings_override, dict) else state.get("settings", {})
    settings = settings if isinstance(settings, dict) else {}
    controls = paper_local_order_repair_settings(settings)
    min_age = bounded_int(
        params.get("minAgeSeconds", [str(controls["min_age_seconds"])])[0],
        controls["min_age_seconds"],
        30,
        86400,
    )
    max_orders = bounded_int(
        params.get("maxOrders", [str(controls["max_orders"])])[0],
        controls["max_orders"],
        1,
        200,
    )
    backend_query = urlencode(
        {
            "limit": "5000",
            "min_age_seconds": str(min_age),
            "max_orders": str(max_orders),
            "stale_seconds": str(min_age),
            "enabled": "true" if controls["enabled"] else "false",
        }
    )
    backend_plan = invoke_backendd_route(
        f"/api/backend/orders/local_repair_plan?{backend_query}",
        timeout_seconds=3.0,
    )
    if (
        isinstance(backend_plan, dict)
        and backend_plan.get("service") == "backendd"
        and isinstance(backend_plan.get("actions"), list)
    ):
        backend_plan["engine"] = "cpp_backendd"
        backend_plan["auto_apply_enabled"] = bool(controls["enabled"])
        backend_plan["min_age_seconds"] = min_age
        backend_plan["max_orders"] = max_orders
        return backend_plan

    consistency = invoke_backendd_route("/api/backend/orders/consistency", timeout_seconds=3.0)
    order_state = order_state_payload({"limit": ["5000"]})
    state_rows = order_state.get("orders", []) if isinstance(order_state.get("orders"), list) else []
    state_by_key = {
        str(row.get("order_key", "")): row
        for row in state_rows
        if isinstance(row, dict) and str(row.get("order_key", ""))
    }

    actions: list[dict[str, Any]] = []
    keep: list[dict[str, Any]] = []
    seen: set[str] = set()
    issues = consistency.get("issues", []) if isinstance(consistency.get("issues"), list) else []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        order_key = str(issue.get("order_key", "")).strip()
        if not order_key or order_key in seen:
            continue
        seen.add(order_key)
        row = state_by_key.get(order_key, {})
        terminal = bool(row.get("terminal"))
        has_broker_id = bool(str(row.get("broker_order_id", "") or row.get("broker_cl_ord_id", "")).strip())
        actionable = (
            bool(controls["enabled"])
            and not terminal
            and not has_broker_id
            and local_repair_issue_actionable(issue, min_age)
        )
        session_id, order_id = split_paper_source_order_id(order_key)
        plan_row = {
            "order_key": order_key,
            "paper_session_id": row.get("paper_session_id", session_id),
            "order_id": row.get("order_id", order_id),
            "inst_id": row.get("inst_id", issue.get("inst_id", "")),
            "side": row.get("side", issue.get("side", "")),
            "state": row.get("state", issue.get("state", "")),
            "broker_status": row.get("broker_status", issue.get("broker_status", "")),
            "remaining_qty": float_from_any(row.get("remaining_qty")),
            "limit_price": float_from_any(row.get("limit_price")),
            "age_seconds": float_from_any(issue.get("age_seconds"), -1.0),
            "issue_code": issue.get("code", ""),
            "latest_trace_status": issue.get("latest_trace_status", ""),
            "action": "expire_local_order" if actionable else "keep",
            "eligible": actionable,
            "reason": (
                f"C++一致性诊断 {issue.get('code', '-')}: {issue.get('message', '')}"
                if actionable
                else "未达到本地修复条件，或可能存在 OKX 侧订单，需要交给对账/撤单链路。"
            ),
        }
        if actionable:
            actions.append(plan_row)
        else:
            keep.append(plan_row)

    actions.sort(key=lambda item: float_from_any(item.get("age_seconds"), 0.0), reverse=True)
    actions = actions[:max_orders]
    return {
        "ok": bool(consistency.get("ok", True)),
        "generated_at": now_iso(),
        "execution_mode": "dry_run",
        "auto_apply_enabled": bool(controls["enabled"]),
        "min_age_seconds": min_age,
        "max_orders": max_orders,
        "summary": {
            "consistency_issues": consistency.get("summary", {}).get("issues", 0)
            if isinstance(consistency.get("summary"), dict)
            else 0,
            "actionable": len(actions),
            "kept": len(keep),
        },
        "actions": actions,
        "keep": keep[:max_orders],
        "consistency": {
            "summary": consistency.get("summary", {}) if isinstance(consistency.get("summary"), dict) else {},
            "route": consistency.get("route", "/api/backend/orders/consistency"),
            "error": consistency.get("error", ""),
        },
    }


def apply_paper_local_order_repair(
    settings: dict[str, Any],
    *,
    source: str,
    max_orders: Optional[int] = None,
) -> dict[str, Any]:
    controls = paper_local_order_repair_settings(settings)
    summary: dict[str, Any] = {
        "enabled": controls["enabled"],
        "checked_at": now_iso(),
        "source": source,
        "min_age_seconds": controls["min_age_seconds"],
        "max_orders": max_orders or controls["max_orders"],
        "requested": 0,
        "expired": 0,
        "skipped": "",
        "events": [],
    }
    if not controls["enabled"]:
        summary["skipped"] = "本地陈旧订单修复未启用。"
        return summary
    plan = paper_local_order_repair_plan_payload(
        {
            "minAgeSeconds": [str(controls["min_age_seconds"])],
            "maxOrders": [str(max_orders or controls["max_orders"])],
        },
        settings_override=settings,
    )
    actions = [item for item in (plan.get("actions", []) or []) if isinstance(item, dict)]
    summary["requested"] = len(actions)
    if not actions:
        summary["skipped"] = "未发现可安全本地过期的陈旧虚拟盘订单。"
        summary["plan"] = {"summary": plan.get("summary", {})}
        return summary
    for action in actions:
        event = append_order_journal_event(
            "order.expired",
            {
                "source": "paper_local_repair",
                "paper_session_id": action.get("paper_session_id", ""),
                "order_id": action.get("order_id", ""),
                "inst_id": action.get("inst_id", ""),
                "side": action.get("side", ""),
                "remaining_qty": float_from_any(action.get("remaining_qty")),
                "limit_price": float_from_any(action.get("limit_price")),
                "state": "expired",
                "broker_status": "LOCAL_REPAIR_EXPIRED",
                "reason": action.get("reason", "本地陈旧订单自动过期。"),
                "repair_code": action.get("issue_code", ""),
                "repair_source": source,
            },
        )
        summary["expired"] += 1
        summary["events"].append(
            {
                "id": event.get("id", ""),
                "order_key": event.get("order_key", ""),
                "issue_code": action.get("issue_code", ""),
            }
        )
    append_platform_event(
        "paper.local_orders_repaired",
        "paper_engine",
        {
            "source": source,
            "requested": summary["requested"],
            "expired": summary["expired"],
            "min_age_seconds": controls["min_age_seconds"],
            "events": summary["events"],
        },
        severity="warn",
        message=f"本地陈旧虚拟盘订单自动过期 {summary['expired']} 笔。",
    )
    return summary


def attach_local_order_repair_result(auto_state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    auto_state["last_local_order_repair"] = result
    if int(result.get("expired", 0) or 0) > 0:
        auto_state["last_local_order_repair_effective"] = result
    return auto_state


def latest_effective_local_order_repair_from_events() -> dict[str, Any]:
    for event in read_platform_events(100, event_type="paper.local_orders_repaired"):
        if int(event.get("expired", 0) or 0) <= 0:
            continue
        return {
            "checked_at": event.get("ts", ""),
            "source": event.get("source", ""),
            "requested": event.get("requested", 0),
            "expired": event.get("expired", 0),
            "min_age_seconds": event.get("min_age_seconds", 0),
            "event_id": event.get("id", ""),
        }
    return {}


def apply_paper_local_order_repair_payload(body: dict[str, Any]) -> dict[str, Any]:
    if str(body.get("confirm", "")) != "EXPIRE_LOCAL_STALE_PAPER_ORDERS":
        return {
            "ok": False,
            "error": "本地陈旧虚拟盘订单修复必须带 confirm=EXPIRE_LOCAL_STALE_PAPER_ORDERS。",
            "requires_confirmation": True,
        }
    with PAPER_LOCK:
        state = read_paper_state()
        settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
    controls = paper_local_order_repair_settings(settings)
    effective_settings = dict(settings)
    if body.get("min_age_seconds") is not None or body.get("minAgeSeconds") is not None:
        effective_settings["paper_local_repair_min_age_seconds"] = bounded_int(
            body.get("min_age_seconds", body.get("minAgeSeconds", controls["min_age_seconds"])),
            controls["min_age_seconds"],
            30,
            86400,
        )
    max_orders = bounded_int(
        body.get("max_orders", body.get("maxOrders", controls["max_orders"])),
        controls["max_orders"],
        1,
        200,
    )
    result = apply_paper_local_order_repair(
        effective_settings,
        source="manual_orders_page",
        max_orders=max_orders,
    )
    with PAPER_LOCK:
        state = read_paper_state()
        auto = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
        auto = attach_local_order_repair_result(auto, result)
        state["okx_auto_submit"] = auto
        write_paper_state(state)
    return {
        "ok": True,
        "repair": result,
        "plan": paper_local_order_repair_plan_payload({}),
        "paper": compact_paper_state_for_response(read_paper_state()),
    }


def paper_auto_cancel_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Return stale-order auto-cancel controls for OKX simulated paper trading."""
    return {
        "enabled": bool_setting_from_any(settings.get("okx_auto_cancel_stale_orders", True), True),
        "min_age_seconds": bounded_int(settings.get("okx_auto_cancel_min_age_seconds", 180), 180, 30, 86400),
        "max_orders": bounded_int(settings.get("okx_auto_cancel_max_orders", 5), 5, 1, 50),
    }


def stale_order_actions_from_live_orders(
    live_orders: list[dict[str, Any]],
    min_age_seconds: int,
    max_orders: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    actions: list[dict[str, Any]] = []
    keep: list[dict[str, Any]] = []
    for row in live_orders:
        if not isinstance(row, dict):
            continue
        age = float_from_any(row.get("age_seconds"), 0.0)
        identity_ok = bool(row.get("inst_id") and (row.get("ord_id") or row.get("cl_ord_id")))
        eligible = age >= min_age_seconds and identity_ok
        plan_row = {
            "source_order_id": row.get("source_order_id", ""),
            "inst_id": row.get("inst_id", ""),
            "side": row.get("side", ""),
            "state": row.get("state", ""),
            "age_seconds": age,
            "px": row.get("px", ""),
            "sz": row.get("sz", ""),
            "ord_id": row.get("ord_id", ""),
            "cl_ord_id": row.get("cl_ord_id", ""),
            "last_order_sync_at": row.get("last_order_sync_at", ""),
            "action": "cancel" if eligible else "keep",
            "eligible": eligible,
            "reason": f"挂单 {int(age)} 秒未终态，超过阈值 {min_age_seconds} 秒。" if eligible else "未达到陈旧阈值或缺少订单标识。",
        }
        if eligible:
            plan_row["cancel_payload"] = {
                "instId": row.get("inst_id", ""),
                "ordId": row.get("ord_id", ""),
                "clOrdId": row.get("cl_ord_id", ""),
                "_source_order_id": row.get("source_order_id", ""),
                "_expected_price": row.get("px", ""),
                "confirm": "CANCEL_OKX_SIMULATED_ORDER",
            }
            actions.append(plan_row)
        else:
            keep.append(plan_row)
    actions = sorted(actions, key=lambda item: float_from_any(item.get("age_seconds"), 0.0), reverse=True)[:max_orders]
    return actions, keep


def update_auto_state_after_cancel_result(
    auto_state: dict[str, Any],
    action: dict[str, Any],
    cancel_result: dict[str, Any],
    detail: dict[str, Any],
    detail_error: str,
) -> bool:
    source_order_id = str(action.get("source_order_id", ""))
    ord_id = str(action.get("ord_id", ""))
    cl_ord_id = str(action.get("cl_ord_id", ""))
    recent = [dict(item) for item in (auto_state.get("recent", []) or []) if isinstance(item, dict)]
    updated = False
    for record in recent:
        identity = paper_okx_auto_order_identity(record) or {}
        same_source = source_order_id and source_order_id == str(record.get("source_order_id", ""))
        same_ord = ord_id and ord_id == str(identity.get("ordId", ""))
        same_cl_ord = cl_ord_id and cl_ord_id == str(identity.get("clOrdId", ""))
        if not (same_source or same_ord or same_cl_ord):
            continue
        result = dict(record.get("result", {}) if isinstance(record.get("result"), dict) else {})
        if detail:
            result["order_detail"] = detail
        record["result"] = result
        record["cancel_requested_at"] = now_iso()
        record["cancel_status"] = "submitted" if cancel_result.get("ok") else "failed"
        record["cancel_error"] = cancel_result.get("error", "")
        record["cancel_audit_id"] = cancel_result.get("audit_id", "")
        record["last_order_sync_at"] = record["cancel_requested_at"]
        record["sync_status"] = "synced" if detail else "cancel_requested"
        record["sync_error"] = detail_error
        updated = True
        break
    if updated:
        auto_state["recent"] = recent[-30:]
        auto_state["last_order_sync_at"] = now_iso()
    return updated


def paper_okx_auto_cancel_stale_orders(auto_state: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    """Cancel stale OKX simulated paper orders before new auto-submission.

    This is intentionally tied to the existing paper auto-submit switch and OKX
    simulated-trading gate.  It never targets real trading and only cancels
    orders that the platform already submitted and still sees as live.
    """
    controls = paper_auto_cancel_settings(settings)
    summary: dict[str, Any] = {
        "enabled": controls["enabled"],
        "checked_at": now_iso(),
        "min_age_seconds": controls["min_age_seconds"],
        "max_orders": controls["max_orders"],
        "requested": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped": "",
        "results": [],
    }
    if not controls["enabled"]:
        summary["skipped"] = "陈旧挂单自动撤单未启用。"
        auto_state["last_stale_cancel"] = summary
        return auto_state
    if not settings.get("okx_auto_submit"):
        summary["skipped"] = "OKX 自动提交未启用，不执行自动撤单。"
        auto_state["last_stale_cancel"] = summary
        return auto_state

    gate = okx_simulated_submit_gate()
    if not gate.get("ready"):
        summary["skipped"] = str(gate.get("reason", "OKX 模拟盘交易门禁未通过。"))
        summary["gate"] = gate
        auto_state["last_stale_cancel"] = summary
        return auto_state

    health = paper_okx_auto_order_health(auto_state, settings)
    actions, _ = stale_order_actions_from_live_orders(
        health["live_orders"],
        controls["min_age_seconds"],
        controls["max_orders"],
    )
    summary["requested"] = len(actions)
    if not actions:
        summary["skipped"] = "未发现达到 TTL 的 OKX 模拟盘挂单。"
        auto_state["last_stale_cancel"] = summary
        return auto_state

    for action in actions:
        payload = dict(action.get("cancel_payload", {}) if isinstance(action.get("cancel_payload"), dict) else {})
        payload["confirm"] = "CANCEL_OKX_SIMULATED_ORDER"
        detail: dict[str, Any] = {}
        detail_error = ""
        inst_id = str(action.get("inst_id", ""))
        ord_id = str(action.get("ord_id", ""))
        cl_ord_id = str(action.get("cl_ord_id", ""))
        if inst_id and (ord_id or cl_ord_id):
            detail_payload = okx_order_detail_payload({"instId": inst_id, "ordId": ord_id, "clOrdId": cl_ord_id})
            if detail_payload.get("ok"):
                detail = detail_payload.get("order", {})
            else:
                detail_error = str(detail_payload.get("error", "撤单后订单详情读取失败"))
        terminal_before_cancel = str(detail.get("state", "")).lower() in OKX_TERMINAL_ORDER_STATES
        if terminal_before_cancel:
            cancel_result = {
                "ok": True,
                "result": {},
                "audit_id": "",
                "request_id": "",
                "message": "订单同步时已经终态，无需撤单。",
            }
            if detail:
                append_okx_audit(
                    "paper_auto_order_synced",
                    {
                        "ok": True,
                        "source_order_id": action.get("source_order_id", ""),
                        "identity": {"instId": inst_id, "ordId": ord_id, "clOrdId": cl_ord_id},
                        "previous_detail": {
                            "state": action.get("state", ""),
                            "px": action.get("px", ""),
                            "sz": action.get("sz", ""),
                        },
                        "order_detail": detail,
                    },
                )
        else:
            cancel_result = okx_cancel_order(payload)
            if inst_id and (ord_id or cl_ord_id):
                detail_payload = okx_order_detail_payload({"instId": inst_id, "ordId": ord_id, "clOrdId": cl_ord_id})
                if detail_payload.get("ok"):
                    detail = detail_payload.get("order", {})
                    detail_error = ""
                else:
                    detail_error = str(detail_payload.get("error", "撤单后订单详情读取失败"))
        terminal_after_cancel = str(detail.get("state", "")).lower() in OKX_TERMINAL_ORDER_STATES
        effective_ok = bool(cancel_result.get("ok")) or terminal_after_cancel
        updated = update_auto_state_after_cancel_result(auto_state, action, cancel_result, detail, detail_error)
        if detail:
            append_broker_order_journal_sync(
                action.get("source_order_id", ""),
                {"instId": inst_id, "ordId": ord_id, "clOrdId": cl_ord_id},
                detail,
                order={},
                audit_id=str(cancel_result.get("audit_id", "")),
                sync_status="cancel_requested" if not terminal_after_cancel else "synced",
                reason="陈旧挂单自动撤单后同步 OKX 状态。",
            )
        result_row = {
            "source_order_id": action.get("source_order_id", ""),
            "inst_id": inst_id,
            "ord_id": ord_id,
            "cl_ord_id": cl_ord_id,
            "ok": effective_ok,
            "cancel_ok": bool(cancel_result.get("ok")),
            "terminal_after_cancel": terminal_after_cancel,
            "state": detail.get("state", ""),
            "error": "" if effective_ok else cancel_result.get("error", detail_error),
            "audit_id": cancel_result.get("audit_id", ""),
            "request_id": cancel_result.get("request_id", ""),
            "state_updated": updated,
        }
        summary["results"].append(result_row)
        if effective_ok:
            summary["succeeded"] += 1
        else:
            summary["failed"] += 1

    append_okx_audit(
        "paper_stale_orders_auto_cancel_requested",
        {
            "ok": summary["failed"] == 0,
            "requested": summary["requested"],
            "succeeded": summary["succeeded"],
            "failed": summary["failed"],
            "source_order_ids": [item.get("source_order_id", "") for item in actions],
        },
    )
    append_platform_event(
        "paper.stale_orders_auto_cancelled",
        "paper_engine",
        {
            "requested": summary["requested"],
            "succeeded": summary["succeeded"],
            "failed": summary["failed"],
            "min_age_seconds": controls["min_age_seconds"],
        },
        severity="warn" if summary["failed"] else "info",
        message=f"自动撤陈旧 OKX 模拟盘挂单：{summary['succeeded']}/{summary['requested']} 成功。",
    )
    auto_state["last_stale_cancel"] = summary
    return auto_state


def paper_okx_sync_auto_submit_state(auto_state: dict[str, Any], max_sync: int = 5) -> dict[str, Any]:
    recent = [dict(item) for item in (auto_state.get("recent", []) or []) if isinstance(item, dict)]
    now_text = now_iso()
    now_ms = int(time.time() * 1000)
    synced = 0
    changed = 0
    errors = 0
    latest_error = ""

    for record in reversed(recent):
        if synced >= max_sync:
            break
        if not paper_okx_auto_sync_due(record, now_ms):
            continue
        identity = paper_okx_auto_order_identity(record)
        if not identity:
            continue
        previous = paper_okx_auto_order_detail(record)
        detail_payload = okx_order_detail_payload(identity)
        synced += 1
        record["last_order_sync_at"] = now_text
        if not detail_payload.get("ok"):
            errors += 1
            latest_error = str(detail_payload.get("error", "订单状态同步失败"))
            record["sync_status"] = "failed"
            record["sync_error"] = latest_error
            audit = append_okx_audit(
                "paper_auto_order_sync_failed",
                {
                    "ok": False,
                    "source_order_id": record.get("source_order_id", ""),
                    "identity": identity,
                    "error": latest_error,
                    "result": detail_payload,
                    "request_id": detail_payload.get("request_id", ""),
                },
            )
            record["sync_audit_id"] = audit["id"]
            continue
        current = detail_payload.get("order", {})
        result = dict(record.get("result", {}) if isinstance(record.get("result"), dict) else {})
        result["order_detail"] = current
        record["result"] = result
        record["sync_status"] = "synced"
        record["sync_error"] = ""
        record["sync_request_id"] = detail_payload.get("request_id", "")
        if okx_detail_changed(previous, current):
            audit = append_okx_audit(
                "paper_auto_order_synced",
                {
                    "ok": True,
                    "source_order_id": record.get("source_order_id", ""),
                    "identity": identity,
                    "previous_detail": previous,
                    "order_detail": current,
                    "request_id": detail_payload.get("request_id", ""),
                },
            )
            record["sync_audit_id"] = audit["id"]
            append_broker_order_journal_sync(
                record.get("source_order_id", ""),
                identity,
                current,
                order=record.get("order", {}) if isinstance(record.get("order"), dict) else {},
                audit_id=str(audit.get("id", "")),
                sync_status="synced",
            )
            changed += 1

    auto_state["recent"] = recent[-30:]
    auto_state["last_order_sync_at"] = now_text if synced else auto_state.get("last_order_sync_at", "")
    auto_state["last_order_sync_count"] = synced
    auto_state["last_order_sync_changed"] = changed
    auto_state["last_order_sync_error_count"] = errors
    auto_state["last_order_sync_error"] = latest_error
    return auto_state


def paper_okx_auto_submit_from_report(state: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
    current = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
    auto_state = paper_okx_auto_state_for_settings(settings, current)
    auto_state["last_checked_at"] = now_iso()
    auto_state["last_status"] = "disabled"
    auto_state["last_message"] = (
        "虚拟盘要求挂到 OKX 模拟盘，但当前 runner 未启用自动提交；请重新启动或恢复虚拟盘。"
        if paper_okx_auto_submission_required()
        else "OKX 自动提交未开启。"
    )
    if not auto_state["enabled"]:
        return auto_state
    auto_state = paper_okx_sync_auto_submit_state(auto_state)
    auto_state = paper_okx_auto_cancel_stale_orders(auto_state, settings)
    auto_state = attach_broker_fill_backfill_result(
        auto_state,
        apply_paper_broker_fill_backfill(settings, source="strategy_tick"),
    )
    auto_state = attach_broker_terminal_sync_result(
        auto_state,
        apply_paper_broker_terminal_sync(settings, source="strategy_tick"),
    )
    auto_state = attach_stale_broker_reconcile_result(
        auto_state,
        apply_paper_stale_broker_reconcile(settings, source="strategy_tick"),
    )
    auto_state = attach_local_order_repair_result(
        auto_state,
        apply_paper_local_order_repair(settings, source="strategy_tick"),
    )

    cycles = report.get("cycles", []) or []
    if not cycles:
        auto_state["last_status"] = "no_report"
        auto_state["last_message"] = "暂无可自动提交的虚拟盘报告。"
        return auto_state
    latest = cycles[-1]
    source_orders = latest.get("orders", []) or []
    if not source_orders:
        auto_state["last_status"] = "no_orders"
        auto_state["last_message"] = "最近周期没有虚拟盘挂单。"
        return auto_state
    max_orders = int(settings.get("okx_auto_max_orders", 1) or 1)

    gate = okx_simulated_submit_gate()
    if not gate.get("ready"):
        auto_state["last_status"] = "blocked"
        auto_state["last_message"] = str(gate.get("reason", "OKX 模拟盘提交未就绪。"))
        auto_state = append_okx_auto_guard_execution_traces(
            auto_state,
            latest,
            source_orders,
            message=auto_state["last_message"],
            guard=gate,
            max_orders=max_orders,
        )
        append_okx_audit(
            "paper_auto_submit_blocked",
            {"ok": False, "reason": auto_state["last_message"], "cycle": latest_cycle_snapshot(report), "submit_gate": gate},
        )
        return auto_state

    submission_guard = paper_okx_auto_submission_guard(settings, auto_state, report, state)
    auto_state["submission_guard"] = submission_guard
    if not submission_guard.get("ready"):
        auto_state["last_status"] = "guarded"
        auto_state["last_message"] = str(submission_guard.get("reason", "OKX 自动提交门禁未通过。"))
        auto_state = append_okx_auto_guard_execution_traces(
            auto_state,
            latest,
            source_orders,
            message=auto_state["last_message"],
            guard=submission_guard,
            max_orders=max_orders,
        )
        return auto_state

    max_notional = Decimal(str(settings.get("okx_auto_max_notional", 10) or 10))
    rules_cache: dict[str, Optional[dict[str, Any]]] = {}
    attempted = 0
    submitted = 0
    blocked = 0
    recent = auto_state["recent"]
    attempted_ids = set(str(item) for item in auto_state["attempted_source_order_ids"])
    submitted_ids = set(str(item) for item in auto_state["submitted_source_order_ids"])
    block_tradeability_warn = bool(settings.get("okx_auto_block_tradeability_warn", False))
    pending_candidates: list[tuple[str, dict[str, Any]]] = []

    for index, source_order in enumerate(source_orders[:max_orders], start=1):
        source_order_id = paper_okx_source_order_id(latest, source_order, index)
        if source_order_id in attempted_ids or source_order_id in submitted_ids:
            continue
        attempted += 1
        attempted_ids.add(source_order_id)
        candidate = paper_order_to_okx_candidate(source_order, max_notional, rules_cache, settings)
        pending_candidates.append((source_order_id, candidate))

    tradeability_payload, tradeability_by_inst = paper_okx_tradeability_map_for_candidates(
        [candidate for _, candidate in pending_candidates],
        max_notional,
    )
    auto_state["last_tradeability"] = {
        "ok": bool(tradeability_payload.get("ok")),
        "summary": tradeability_payload.get("summary", {}),
        "thresholds": tradeability_payload.get("thresholds", {}),
        "error": tradeability_payload.get("error", ""),
        "block_warnings": block_tradeability_warn,
    }

    for source_order_id, candidate in pending_candidates:
        paper_okx_apply_tradeability_to_candidate(candidate, tradeability_by_inst, block_tradeability_warn)
    auto_state["last_execution_forecast"] = paper_okx_execution_forecast_summary(
        [candidate for _, candidate in pending_candidates]
    )

    for source_order_id, candidate in pending_candidates:
        if not candidate.get("ok") or not candidate.get("approved"):
            blocked += 1
            tradeability_status = str(candidate.get("tradeability_status", "")).lower()
            message = candidate.get("message") or candidate.get("reason", "候选单未通过预检。")
            trace = append_execution_trace_event(
                "execution.blocked",
                source_order_id,
                candidate,
                latest,
                status="blocked_tradeability" if tradeability_status in {"block", "warn"} else "blocked",
                message=message,
            )
            recent.append(
                {
                    "at": now_iso(),
                    "source_order_id": source_order_id,
                    "status": "blocked_tradeability" if tradeability_status in {"block", "warn"} else "blocked",
                    "message": message,
                    "candidate": candidate,
                    "tradeability": candidate.get("tradeability", {}),
                    "execution_trace_id": trace.get("id", ""),
                }
            )
            continue

        order = dict(candidate.get("order", {}))
        order["clOrdId"] = paper_okx_auto_client_order_id(source_order_id, latest)
        source_order = candidate.get("source_order", {}) if isinstance(candidate.get("source_order"), dict) else {}
        attribution_context = source_order_attribution_context(source_order)
        order["_source_order_id"] = source_order_id
        if attribution_context.get("strategy_id"):
            order["_strategy_id"] = attribution_context["strategy_id"]
        if attribution_context.get("agent_id"):
            order["_agent_id"] = attribution_context["agent_id"]
        if attribution_context.get("trading_unit_id"):
            order["_trading_unit_id"] = attribution_context["trading_unit_id"]
        result = okx_submit_order(
            {
                **order,
                "confirm": "OKX_SIMULATED_ONLY",
                "_source_order_id": source_order_id,
                "_strategy_id": attribution_context.get("strategy_id", ""),
                "_agent_id": attribution_context.get("agent_id", ""),
                "_trading_unit_id": attribution_context.get("trading_unit_id", ""),
                "_expected_price": candidate.get("tradeability", {}).get("last", order.get("px", ""))
                if isinstance(candidate.get("tradeability"), dict)
                else order.get("px", ""),
                "_cycle_index": latest.get("cycle_index", ""),
                "_cycle_label": latest.get("label", ""),
            }
        )
        trace = append_execution_trace_event(
            "execution.submitted" if result.get("ok") else "execution.failed",
            source_order_id,
            candidate,
            latest,
            status="submitted" if result.get("ok") else "failed",
            message="submitted" if result.get("ok") else str(result.get("error", "OKX 提交失败。")),
            result={
                key: result.get(key)
                for key in [
                    "ok",
                    "error",
                    "result",
                    "order_detail",
                    "audit_id",
                    "request_id",
                    "status_code",
                    "base_url",
                    "okx_code",
                    "okx_msg",
                    "data_errors",
                    "error_summary",
                    "raw_okx",
                    "fallback_errors",
                ]
                if key in result
            },
        )
        if result.get("ok"):
            submit_item = result.get("result", {}) if isinstance(result.get("result"), dict) else {}
            detail = result.get("order_detail", {}) if isinstance(result.get("order_detail"), dict) else {}
            append_broker_order_journal_sync(
                source_order_id,
                {
                    "instId": detail.get("inst_id") or order.get("instId", ""),
                    "ordId": detail.get("ord_id") or submit_item.get("ordId", ""),
                    "clOrdId": detail.get("cl_ord_id") or submit_item.get("clOrdId") or order.get("clOrdId", ""),
                },
                detail,
                order=order,
                audit_id=str(result.get("audit_id", "")),
                sync_status="submitted",
            )
        recent.append(
            {
                "at": now_iso(),
                "source_order_id": source_order_id,
                "status": "submitted" if result.get("ok") else "failed",
                "message": "submitted" if result.get("ok") else result.get("error", "OKX 提交失败。"),
                "order": order,
                "candidate": candidate,
                "tradeability": candidate.get("tradeability", {}),
                "execution_trace_id": trace.get("id", ""),
                "result": {
                    key: result.get(key)
                    for key in [
                        "ok",
                        "error",
                        "result",
                        "order_detail",
                        "audit_id",
                        "request_id",
                        "status_code",
                        "base_url",
                        "okx_code",
                        "okx_msg",
                        "data_errors",
                        "error_summary",
                        "raw_okx",
                        "fallback_errors",
                    ]
                    if key in result
                },
            }
        )
        if result.get("ok"):
            submitted += 1
            submitted_ids.add(source_order_id)
        else:
            blocked += 1

    auto_state["attempted_source_order_ids"] = list(attempted_ids)[-500:]
    auto_state["submitted_source_order_ids"] = list(submitted_ids)[-500:]
    auto_state["recent"] = recent[-30:]
    auto_state["submission_guard"] = paper_okx_auto_submission_guard(settings, auto_state, report, state)
    auto_state["last_status"] = "submitted" if submitted else "blocked" if blocked else "deduped"
    auto_state["last_message"] = f"本轮尝试 {attempted} 单，提交 {submitted} 单，阻断/失败 {blocked} 单。"
    return auto_state


def paper_okx_auto_maintenance_state(state: dict[str, Any]) -> dict[str, Any]:
    """Maintain OKX simulated paper orders even when the strategy tick is skipped."""
    settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
    current = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
    auto_state = paper_okx_auto_state_for_settings(settings, current)
    auto_state["last_checked_at"] = now_iso()
    auto_state["last_status"] = "disabled"
    auto_state["last_message"] = (
        "虚拟盘要求挂到 OKX 模拟盘，但当前 runner 未启用自动提交；请重新启动或恢复虚拟盘。"
        if paper_okx_auto_submission_required()
        else "OKX 自动提交未开启。"
    )
    if not auto_state["enabled"]:
        return auto_state

    auto_state = paper_okx_sync_auto_submit_state(auto_state, max_sync=10)
    auto_state = paper_okx_auto_cancel_stale_orders(auto_state, settings)
    auto_state = attach_broker_fill_backfill_result(
        auto_state,
        apply_paper_broker_fill_backfill(settings, source="maintenance"),
    )
    auto_state = attach_broker_terminal_sync_result(
        auto_state,
        apply_paper_broker_terminal_sync(settings, source="maintenance"),
    )
    auto_state = attach_stale_broker_reconcile_result(
        auto_state,
        apply_paper_stale_broker_reconcile(settings, source="maintenance"),
    )
    auto_state = attach_local_order_repair_result(
        auto_state,
        apply_paper_local_order_repair(settings, source="maintenance"),
    )
    report = read_latest_paper_report()
    submission_guard = paper_okx_auto_submission_guard(settings, auto_state, report, state)
    auto_state["submission_guard"] = submission_guard
    stale_cancel = auto_state.get("last_stale_cancel", {}) if isinstance(auto_state.get("last_stale_cancel"), dict) else {}
    broker_backfill = auto_state.get("last_broker_fill_backfill", {}) if isinstance(auto_state.get("last_broker_fill_backfill"), dict) else {}
    broker_terminal_sync = auto_state.get("last_broker_terminal_sync", {}) if isinstance(auto_state.get("last_broker_terminal_sync"), dict) else {}
    stale_broker_reconcile = auto_state.get("last_stale_broker_reconcile", {}) if isinstance(auto_state.get("last_stale_broker_reconcile"), dict) else {}
    local_repair = auto_state.get("last_local_order_repair", {}) if isinstance(auto_state.get("last_local_order_repair"), dict) else {}
    if int(stale_cancel.get("requested", 0) or 0) > 0:
        auto_state["last_status"] = "maintenance_cancelled" if int(stale_cancel.get("failed", 0) or 0) == 0 else "maintenance_warn"
        auto_state["last_message"] = f"自动撤陈旧 OKX 模拟盘挂单 {stale_cancel.get('succeeded', 0)}/{stale_cancel.get('requested', 0)}。"
    elif int(broker_backfill.get("backfilled", 0) or 0) > 0:
        auto_state["last_status"] = "maintenance_backfilled"
        auto_state["last_message"] = f"OKX 成交回补到本地订单状态机 {broker_backfill.get('backfilled', 0)} 笔。"
    elif int(broker_terminal_sync.get("synced", 0) or 0) > 0:
        auto_state["last_status"] = "maintenance_terminal_synced"
        auto_state["last_message"] = f"OKX 终态回补到本地订单状态机 {broker_terminal_sync.get('synced', 0)} 笔。"
    elif int(stale_broker_reconcile.get("cancel_requested", 0) or 0) > 0 or int(stale_broker_reconcile.get("terminal_synced", 0) or 0) > 0:
        auto_state["last_status"] = "maintenance_stale_broker_reconciled"
        auto_state["last_message"] = (
            f"陈旧 OKX broker 订单对账 {stale_broker_reconcile.get('queried', 0)} 笔，"
            f"终态回补 {stale_broker_reconcile.get('terminal_synced', 0)}，"
            f"撤单 {stale_broker_reconcile.get('cancel_succeeded', 0)}/{stale_broker_reconcile.get('cancel_requested', 0)}。"
        )
    elif int(local_repair.get("expired", 0) or 0) > 0:
        auto_state["last_status"] = "maintenance_repaired"
        auto_state["last_message"] = f"自动过期本地陈旧虚拟盘订单 {local_repair.get('expired', 0)} 笔。"
    elif not submission_guard.get("ready"):
        auto_state["last_status"] = "guarded"
        auto_state["last_message"] = str(submission_guard.get("reason", "OKX 自动提交门禁未通过。"))
    else:
        auto_state["last_status"] = "maintenance"
        auto_state["last_message"] = "OKX 自动提交维护完成，暂无陈旧挂单需要撤。"
    return auto_state


def float_from_any(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def okx_balance_detail_map(account: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in account.get("details", []) or []:
        ccy = str(item.get("ccy", "")).upper().strip()
        if ccy:
            result[ccy] = item
    return result


def latest_paper_portfolio_snapshot() -> dict[str, Any]:
    state = read_paper_state()
    portfolio = state.get("portfolio", {}) if isinstance(state.get("portfolio"), dict) else {}
    report = read_latest_paper_report()
    cycles = report.get("cycles", []) or []
    if not portfolio.get("positions") and cycles:
        portfolio = cycles[-1].get("post_trade_portfolio", {}) or {}
    return {
        "state": state,
        "report": report,
        "portfolio": portfolio,
        "cycle": latest_cycle_snapshot(report),
    }


def paper_position_index(portfolio: dict[str, Any]) -> dict[str, dict[str, Any]]:
    positions = portfolio.get("positions", []) if isinstance(portfolio, dict) else []
    result: dict[str, dict[str, Any]] = {}
    for position in positions:
        instrument = instrument_from_report_item(position)
        inst_id = instrument["inst_id"]
        if "-" not in inst_id:
            continue
        base_ccy = inst_id.split("-", 1)[0]
        result[inst_id] = {
            "inst_id": inst_id,
            "base_ccy": base_ccy,
            "quantity": float_from_any(position.get("quantity")),
            "market_price": float_from_any(position.get("market_price")),
            "market_value": float_from_any(position.get("market_value")),
            "weight": float_from_any(position.get("weight")),
        }
    return result


def okx_balance_snapshot(account: dict[str, Any]) -> dict[str, dict[str, Any]]:
    balances: dict[str, dict[str, Any]] = {}
    for ccy, item in sorted(okx_balance_detail_map(account).items()):
        balances[ccy] = {
            "ccy": ccy,
            "eq": item.get("eq", ""),
            "cash_bal": item.get("cash_bal", ""),
            "avail_bal": item.get("avail_bal", ""),
            "frozen_bal": item.get("frozen_bal", ""),
            "eq_usd": item.get("eq_usd", ""),
        }
    return balances


def read_paper_okx_baseline() -> dict[str, Any]:
    if not PAPER_OKX_BASELINE_PATH.exists():
        return {}
    try:
        saved = json.loads(PAPER_OKX_BASELINE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return saved if isinstance(saved, dict) else {}


def paper_okx_baseline_summary(baseline: dict[str, Any]) -> dict[str, Any]:
    balances = baseline.get("balances", {}) if isinstance(baseline.get("balances"), dict) else {}
    paper_positions = baseline.get("paper_positions", {}) if isinstance(baseline.get("paper_positions"), dict) else {}
    paper = baseline.get("paper", {}) if isinstance(baseline.get("paper"), dict) else {}
    cycle = paper.get("cycle", {}) if isinstance(paper.get("cycle"), dict) else {}
    return {
        "exists": bool(baseline.get("created_at")),
        "created_at": baseline.get("created_at", ""),
        "paper_cycle_label": cycle.get("label", ""),
        "paper_status": paper.get("status", ""),
        "paper_equity": paper.get("equity", ""),
        "paper_positions_count": len(paper_positions),
        "balances_count": len(balances),
        "account_total_eq": baseline.get("account_total_eq", ""),
        "used_simulated": baseline.get("used_simulated", ""),
    }


def paper_okx_baseline_status_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "baseline": paper_okx_baseline_summary(read_paper_okx_baseline()),
        "config": okx_status(),
    }


def save_paper_okx_baseline_payload(body: dict[str, Any]) -> dict[str, Any]:
    if body.get("confirm") != "SAVE_OKX_BASELINE":
        return {"ok": False, "error": "保存 OKX 对账基准必须带 confirm=SAVE_OKX_BASELINE。", "config": okx_status()}
    snapshot = latest_paper_portfolio_snapshot()
    portfolio = snapshot["portfolio"] if isinstance(snapshot.get("portfolio"), dict) else {}
    balance = okx_balance_payload()
    if not balance.get("ok"):
        return {
            "ok": False,
            "error": balance.get("error", "OKX 余额读取失败"),
            "baseline": paper_okx_baseline_summary(read_paper_okx_baseline()),
            "config": balance.get("config", okx_status()),
        }
    account = balance.get("account", {}) if isinstance(balance.get("account"), dict) else {}
    baseline = {
        "created_at": now_iso(),
        "account_total_eq": account.get("total_eq", ""),
        "account_adj_eq": account.get("adj_eq", ""),
        "balances": okx_balance_snapshot(account),
        "paper": {
            "status": snapshot["state"].get("status", ""),
            "last_success_at": snapshot["state"].get("last_success_at", ""),
            "cash": portfolio.get("cash", ""),
            "equity": portfolio.get("equity", ""),
            "cycle": snapshot["cycle"],
        },
        "paper_positions": paper_position_index(portfolio),
        "request_id": balance.get("request_id", ""),
        "used_simulated": balance.get("used_simulated", okx_config().get("simulated")),
    }
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    PAPER_OKX_BASELINE_PATH.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = append_okx_audit(
        "paper_okx_baseline_saved",
        {
            "ok": True,
            "created_at": baseline["created_at"],
            "balances_count": len(baseline["balances"]),
            "paper_positions_count": len(baseline["paper_positions"]),
            "request_id": balance.get("request_id", ""),
        },
    )
    return {
        "ok": True,
        "baseline": paper_okx_baseline_summary(baseline),
        "config": okx_status(),
        "audit_id": audit["id"],
        "request_id": balance.get("request_id", ""),
    }


def reconciliation_check_counts(checks: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for check in checks:
        severity = str(check.get("severity") or ("ok" if check.get("ok") else "warn"))
        counts[severity] = counts.get(severity, 0) + 1
    return dict(sorted(counts.items()))


def append_paper_okx_reconciliation_event(payload: dict[str, Any]) -> dict[str, Any]:
    # The reconciliation journal is an observability artifact: it records the
    # read-only comparison result and never submits or cancels exchange orders.
    positions = payload.get("positions", []) if isinstance(payload.get("positions"), list) else []
    mismatches = [row for row in positions if isinstance(row, dict) and not bool(row.get("matched", True))]
    order_changes = payload.get("order_changes", []) if isinstance(payload.get("order_changes"), list) else []
    event = {
        "id": f"rec-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}-{uuid4().hex[:8]}",
        "ts": now_iso(),
        "status": payload.get("status", "halt"),
        "ok": bool(payload.get("ok")),
        "cycle_label": payload.get("cycle", {}).get("label", "") if isinstance(payload.get("cycle"), dict) else "",
        "paper": payload.get("paper", {}),
        "okx_account": payload.get("okx_account", {}),
        "baseline": payload.get("baseline", {}),
        "checks": payload.get("checks", []),
        "check_counts": reconciliation_check_counts(payload.get("checks", []) if isinstance(payload.get("checks"), list) else []),
        "positions_count": len(positions),
        "mismatch_count": len(mismatches),
        "order_count": len(payload.get("orders", []) if isinstance(payload.get("orders"), list) else []),
        "order_change_count": len(order_changes),
        "mismatches": [
            {
                "inst_id": row.get("inst_id", ""),
                "paper_net_qty": row.get("paper_net_qty", 0.0),
                "okx_net_qty": row.get("okx_net_qty", 0.0),
                "diff_qty": row.get("diff_qty", 0.0),
                "tolerance": row.get("tolerance", 0.0),
            }
            for row in mismatches[:20]
        ],
        "order_changes": [
            {
                "id": row.get("id", ""),
                "action": row.get("action", ""),
                "identity": row.get("identity", {}),
                "order_detail": row.get("order_detail", {}),
            }
            for row in order_changes[:20]
            if isinstance(row, dict)
        ],
    }
    RECONCILIATION_DIR.mkdir(parents=True, exist_ok=True)
    with RECONCILIATION_LOCK:
        with RECONCILIATION_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    return event


def read_paper_okx_reconciliation_history(limit: int = 50) -> list[dict[str, Any]]:
    limit = max(0, min(int(limit), 1000))
    if limit <= 0:
        return []
    with RECONCILIATION_LOCK:
        rows = read_jsonl_tail(RECONCILIATION_PATH, limit)
    return rows


def paper_okx_reconciliation_history_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    limit = bounded_int(params.get("limit", ["50"])[0], 50, 1, 1000)
    rows = read_paper_okx_reconciliation_history(limit)
    status_counts: dict[str, int] = {}
    mismatch_total = 0
    order_change_total = 0
    for row in rows:
        status = str(row.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        mismatch_total += int(float_from_any(row.get("mismatch_count"), 0.0))
        order_change_total += int(float_from_any(row.get("order_change_count"), 0.0))
    return {
        "ok": True,
        "generated_at": now_iso(),
        "journal_path": str(RECONCILIATION_PATH),
        "summary": {
            "events": len(rows),
            "status_counts": dict(sorted(status_counts.items())),
            "mismatch_total": mismatch_total,
            "order_change_total": order_change_total,
            "latest_status": rows[0].get("status", "") if rows else "",
            "latest_at": rows[0].get("ts", "") if rows else "",
            "latest_mismatch_count": rows[0].get("mismatch_count", 0) if rows else 0,
            "latest_order_change_count": rows[0].get("order_change_count", 0) if rows else 0,
        },
        "history": rows,
    }


def format_duration_for_message(seconds: Optional[float]) -> str:
    if seconds is None:
        return "-"
    if seconds < 60:
        return f"{int(seconds)} 秒"
    if seconds < 3600:
        return f"{int(seconds // 60)} 分钟"
    return f"{seconds / 3600.0:.1f} 小时"


def paper_okx_reconciliation_health_payload(settings: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    settings = settings or {}
    history = paper_okx_reconciliation_history_payload({"limit": ["100"]})
    rows = history.get("history", []) if isinstance(history.get("history"), list) else []
    latest = rows[0] if rows else {}
    baseline = paper_okx_baseline_summary(read_paper_okx_baseline())
    latest_age = age_seconds_from_text(latest.get("ts")) if latest else None
    auto_enabled = bool(settings.get("okx_auto_submit"))
    max_age = max(300, int(float_from_any(settings.get("reconciliation_max_age_seconds"), 1800.0)))
    latest_status = str(latest.get("status", ""))
    mismatch_count = int(float_from_any(latest.get("mismatch_count"), 0.0))
    checks = [
        paper_health_check(
            "OKX 对账基准",
            bool(baseline.get("exists")),
            "warn",
            f"基准时间 {baseline.get('created_at', '-')}"
            if baseline.get("exists")
            else "尚未保存 OKX 对账基准。",
        ),
        paper_health_check(
            "OKX 对账流水",
            bool(rows),
            "warn",
            f"最近对账 {format_duration_for_message(latest_age)} 前。"
            if rows
            else "尚无 OKX 对账记录。",
        ),
        paper_health_check(
            "OKX 对账时效",
            (not auto_enabled) or (latest_age is not None and latest_age <= max_age),
            "warn",
            f"最近对账 {format_duration_for_message(latest_age)} 前，阈值 {max_age} 秒。"
            if latest_age is not None
            else "自动提交已开启但尚无对账记录。",
            max_age_seconds=max_age,
            age_seconds=latest_age,
        ),
        paper_health_check(
            "OKX 持仓差异",
            mismatch_count == 0 and latest_status != "halt",
            "warn" if latest_status != "halt" else "halt",
            f"最近对账 {mismatch_count} 个现货存在差异，status={latest_status or '-'}。"
            if rows
            else "等待第一次对账。",
        ),
    ]
    status = paper_health_overall(checks)
    return {
        "ok": status == "ok",
        "status": status,
        "generated_at": now_iso(),
        "summary": {
            **(history.get("summary", {}) if isinstance(history.get("summary"), dict) else {}),
            "baseline_exists": bool(baseline.get("exists")),
            "latest_age_seconds": latest_age,
            "max_age_seconds": max_age,
        },
        "checks": checks,
        "latest": latest,
        "journal_path": str(RECONCILIATION_PATH),
    }


def paper_okx_reconciliation_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    snapshot = latest_paper_portfolio_snapshot()
    portfolio = snapshot["portfolio"]
    current_positions = paper_position_index(portfolio if isinstance(portfolio, dict) else {})
    baseline = read_paper_okx_baseline()
    baseline_summary = paper_okx_baseline_summary(baseline)
    has_baseline = bool(baseline_summary.get("exists"))
    baseline_balances = baseline.get("balances", {}) if isinstance(baseline.get("balances"), dict) else {}
    baseline_positions = baseline.get("paper_positions", {}) if isinstance(baseline.get("paper_positions"), dict) else {}
    balance = okx_balance_payload()
    if not balance.get("ok"):
        payload = {
            "ok": False,
            "status": "halt",
            "error": balance.get("error", "OKX 余额读取失败"),
            "paper": snapshot["state"],
            "cycle": snapshot["cycle"],
            "baseline": baseline_summary,
            "checks": [
                okx_check("OKX 余额读取", False, "halt", balance.get("error", "OKX 余额读取失败")),
            ],
            "config": balance.get("config", okx_status()),
        }
        event = append_paper_okx_reconciliation_event(payload)
        payload["reconciliation_event"] = event
        payload["reconciliation_journal_path"] = str(RECONCILIATION_PATH)
        payload["history"] = read_paper_okx_reconciliation_history(20)
        return payload
    order_sync = okx_sync_recent_orders_payload({"limit": params.get("limit", ["20"])})
    details = okx_balance_detail_map(balance.get("account", {}))
    rows: list[dict[str, Any]] = []
    mismatches = 0
    for inst_id in sorted(set(current_positions) | set(baseline_positions)):
        if "-" not in inst_id:
            continue
        position = current_positions.get(inst_id, {})
        baseline_position = baseline_positions.get(inst_id, {}) if has_baseline else {}
        base_ccy = str(position.get("base_ccy") or baseline_position.get("base_ccy") or inst_id.split("-", 1)[0]).upper()
        paper_qty = float_from_any(position.get("quantity"))
        paper_baseline_qty = float_from_any(baseline_position.get("quantity")) if has_baseline else 0.0
        paper_net_qty = paper_qty - paper_baseline_qty if has_baseline else paper_qty
        paper_price = float_from_any(position.get("market_price") or baseline_position.get("market_price"))
        paper_value = float_from_any(position.get("market_value"))
        detail = details.get(base_ccy, {})
        baseline_detail = baseline_balances.get(base_ccy, {}) if has_baseline and isinstance(baseline_balances.get(base_ccy), dict) else {}
        okx_raw_qty = float_from_any(detail.get("eq"))
        okx_baseline_qty = float_from_any(baseline_detail.get("eq")) if has_baseline else 0.0
        okx_net_qty = okx_raw_qty - okx_baseline_qty if has_baseline else okx_raw_qty
        diff = okx_net_qty - paper_net_qty
        quote = okx_latest_quote(inst_id)
        quote_price = float(quote.get("last") or quote.get("bid") or quote.get("ask") or Decimal(str(paper_price or 0)))
        okx_value = okx_net_qty * quote_price if quote_price > 0 else 0.0
        okx_raw_value = okx_raw_qty * quote_price if quote_price > 0 else 0.0
        paper_net_value = paper_net_qty * quote_price if quote_price > 0 else 0.0
        tolerance = max(abs(paper_net_qty) * 0.001, 1e-8)
        matched = abs(diff) <= tolerance
        if not matched:
            mismatches += 1
        rows.append(
            {
                "inst_id": inst_id,
                "base_ccy": base_ccy,
                "paper_qty": paper_qty,
                "paper_baseline_qty": paper_baseline_qty,
                "paper_net_qty": paper_net_qty,
                "paper_price": paper_price,
                "paper_value": paper_value,
                "paper_net_value": paper_net_value,
                "paper_weight": float_from_any(position.get("weight")),
                "okx_qty": okx_net_qty,
                "okx_raw_qty": okx_raw_qty,
                "okx_baseline_qty": okx_baseline_qty,
                "okx_net_qty": okx_net_qty,
                "okx_avail": float_from_any(detail.get("avail_bal")),
                "okx_frozen": float_from_any(detail.get("frozen_bal")),
                "okx_value": okx_value,
                "okx_raw_value": okx_raw_value,
                "diff_qty": diff,
                "matched": matched,
                "tolerance": tolerance,
            }
        )

    usdt = details.get("USDT", {})
    usdt_baseline = baseline_balances.get("USDT", {}) if has_baseline and isinstance(baseline_balances.get("USDT"), dict) else {}
    usdt_eq = float_from_any(usdt.get("eq"))
    usdt_baseline_eq = float_from_any(usdt_baseline.get("eq")) if has_baseline else 0.0
    usdt_net_eq = usdt_eq - usdt_baseline_eq if has_baseline else usdt_eq
    checks = [
        okx_check("OKX 余额读取", True, "ok", f"totalEq={balance.get('account', {}).get('total_eq', '-')}"),
        okx_check("OKX 对账基准", has_baseline, "ok" if has_baseline else "warn", f"基准时间 {baseline_summary.get('created_at', '-')}" if has_baseline else "尚未保存基准；当前仅用 OKX 原始余额做临时对比。"),
        okx_check("订单状态同步", bool(order_sync.get("ok")), "ok" if order_sync.get("ok") else "warn", f"同步 {len(order_sync.get('synced', []))} 单，变化 {len(order_sync.get('changed', []))} 条。"),
        okx_check("虚拟盘持仓", bool(current_positions or baseline_positions), "ok" if current_positions or baseline_positions else "warn", f"当前 {len(current_positions)} 个持仓，基准 {len(baseline_positions) if has_baseline else 0} 个持仓。"),
        okx_check("持仓差异", mismatches == 0, "ok" if mismatches == 0 else "warn", f"{mismatches} 个现货的基准后净变化与虚拟盘不一致。"),
    ]
    status = "halt" if any(item["severity"] == "halt" for item in checks) else (
        "warn" if any(item["severity"] == "warn" for item in checks) else "ok"
    )
    payload = {
        "ok": status != "halt",
        "status": status,
        "generated_at": now_iso(),
        "cycle": snapshot["cycle"],
        "paper": {
            "status": snapshot["state"].get("status", ""),
            "last_success_at": snapshot["state"].get("last_success_at", ""),
            "cash": portfolio.get("cash", ""),
            "equity": portfolio.get("equity", ""),
            "positions_count": len(current_positions),
            "baseline_positions_count": len(baseline_positions) if has_baseline else 0,
        },
        "okx_account": {
            "total_eq": balance.get("account", {}).get("total_eq", ""),
            "usdt_eq": usdt_eq,
            "usdt_baseline_eq": usdt_baseline_eq if has_baseline else "",
            "usdt_net_eq": usdt_net_eq,
            "usdt_avail": usdt.get("avail_bal", ""),
            "usdt_frozen": usdt.get("frozen_bal", ""),
        },
        "baseline": baseline_summary,
        "checks": checks,
        "positions": rows,
        "orders": order_sync.get("synced", []),
        "order_changes": order_sync.get("changed", []),
        "config": okx_status(),
    }
    event = append_paper_okx_reconciliation_event(payload)
    payload["reconciliation_event"] = event
    payload["reconciliation_journal_path"] = str(RECONCILIATION_PATH)
    payload["history"] = read_paper_okx_reconciliation_history(20)
    return payload


def compact_ops_preflight_for_state(preflight: dict[str, Any]) -> dict[str, Any]:
    checks = preflight.get("checks", []) if isinstance(preflight.get("checks"), list) else []
    failed = [
        {
            "name": str(row.get("name", "")),
            "severity": str(row.get("severity", "")),
            "message": str(row.get("message", "")),
        }
        for row in checks
        if isinstance(row, dict) and not row.get("ok")
    ]
    return {
        "generated_at": preflight.get("generated_at", now_iso()),
        "status": preflight.get("status", ""),
        "decision": preflight.get("decision", ""),
        "summary": preflight.get("summary", {}) if isinstance(preflight.get("summary"), dict) else {},
        "failed_checks": failed[:12],
    }


def runtime_preflight_for_settings(settings: dict[str, Any]) -> dict[str, Any]:
    try:
        return ops_preflight_payload(
            {
                **settings,
                "profile": "simulated",
                "okx_auto_confirm": PAPER_OKX_AUTO_CONFIRM,
            }
        )
    except Exception as exc:
        return {
            "ok": False,
            "generated_at": now_iso(),
            "profile": "simulated",
            "status": "halt",
            "decision": "block",
            "summary": {},
            "checks": [
                paper_health_check(
                    "运行预检异常",
                    False,
                    "halt",
                    str(exc),
                )
            ],
            "actions": [{"priority": "P0", "action": "修复运行预检异常后再恢复 runner。"}],
        }


def preflight_blocking_checks(preflight: dict[str, Any]) -> list[dict[str, Any]]:
    checks = preflight.get("checks", []) if isinstance(preflight.get("checks"), list) else []
    return [
        row for row in checks
        if isinstance(row, dict) and not row.get("ok") and row.get("severity") == "halt"
    ]


# 数据临时不可用导致的阻断应 skip tick 而非 stop runner。
_SOFT_BLOCK_NAMES = {"OKX WS 行情覆盖", "C++ 行情质量"}


def has_hard_block(blocking: list[dict[str, Any]]) -> bool:
    """是否有需要停止 runner 的硬阻断（非数据临时不可用）。"""
    for row in blocking:
        name = str(row.get("name", ""))
        if name not in _SOFT_BLOCK_NAMES:
            return True
    return False


def paper_skip_tick_payload(state: dict[str, Any], reason: str) -> dict[str, Any]:
    """跳过本轮 tick 但不停止 runner，等数据恢复后自动继续。"""
    with PAPER_LOCK:
        current = read_paper_state()
        current["tick_running"] = False
        current["last_skip_reason"] = reason
        current["last_runtime_at"] = now_iso()
        write_paper_state(current)
    append_platform_event_throttled(
        "paper.tick_skipped",
        "ops",
        {"paper_status": current.get("status", ""), "reason": reason},
        throttle_key="paper.tick_skipped",
        min_interval_seconds=30,
        severity="warn",
        message=reason,
    )
    return {
        "ok": True,
        "skipped": True,
        "reason": reason,
        "paper": compact_paper_state_for_response(current),
    }


def paper_runtime_safety_halt_payload(
    state: dict[str, Any],
    preflight: dict[str, Any],
    *,
    manual: bool = False,
    settings_override: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    blocking = preflight_blocking_checks(preflight)
    first = blocking[0] if blocking else {}
    reason = f"运行中熔断：{first.get('name', '启动预检')} - {first.get('message', '预检阻断')}"
    compact = compact_ops_preflight_for_state(preflight)
    with PAPER_LOCK:
        current = read_paper_state()
        if settings_override:
            current["settings"] = settings_override
        current["tick_running"] = False
        current["last_skip_reason"] = reason
        current["last_error"] = ""
        current["last_runtime_at"] = now_iso()
        current["runtime_preflight"] = compact
        if current.get("status") in {"running", "manual", "stopping"}:
            current["status"] = "paused"
            current["paused_at"] = now_iso()
            current["next_tick_after"] = ""
        write_paper_state(current)
    append_platform_event(
        "paper.runtime_safety_halt",
        "ops",
        {
            "manual": manual,
            "paper_status": state.get("status", ""),
            "reason": reason,
            "decision": preflight.get("decision", ""),
            "status": preflight.get("status", ""),
            "blocking_checks": [
                {"name": row.get("name", ""), "message": row.get("message", "")}
                for row in blocking[:8]
            ],
        },
        severity="halt",
        message=reason,
    )
    append_ops_incident(
        "runtime_safety_halt",
        "halt",
        "运行中熔断",
        reason,
        {
            "manual": manual,
            "paper_status": state.get("status", ""),
            "decision": preflight.get("decision", ""),
            "status": preflight.get("status", ""),
            "blocking_checks": [
                {"name": row.get("name", ""), "message": row.get("message", "")}
                for row in blocking[:8]
            ],
        },
    )
    return {
        "ok": True,
        "skipped": True,
        "runtime_halt": True,
        "reason": reason,
        "preflight": compact,
        "output": f"Paper tick halted by runtime safety: {reason}\n",
        "paper": compact_paper_state_for_response(read_paper_state()),
        "run": {"ok": True, "skipped": True, "runtime_halt": True, "reason": reason},
        "markers": read_paper_markers(limit=300),
    }


def paper_run_tick(
    manual: bool = False,
    build_first: Optional[bool] = None,
    settings_override: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    freeze = read_ops_state()
    if freeze.get("automation_freeze"):
        reason = freeze.get("reason") or "自动化冻结已开启，跳过新的策略 tick。"
        return automation_freeze_skip_payload(read_paper_state(), reason)
    with PAPER_LOCK:
        state = read_paper_state()
        if state.get("tick_running"):
            return {"ok": False, "error": "已有虚拟盘 tick 正在运行", "paper": compact_paper_state_for_response(state)}
        if manual and settings_override:
            state["settings"] = settings_override
        runtime_settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}

    preflight = runtime_preflight_for_settings(runtime_settings)
    if preflight.get("decision") == "block":
        blocking = preflight_blocking_checks(preflight)
        first = blocking[0] if blocking else {}
        reason = f"预检阻断：{first.get('name', '未知')} - {first.get('message', '未知原因')}"
        if not has_hard_block(blocking):
            # 只有软阻断（如数据临时不可用），跳过本轮 tick，不停止 runner
            return paper_skip_tick_payload(state, reason)
        return paper_runtime_safety_halt_payload(
            state,
            preflight,
            manual=manual,
            settings_override=settings_override if manual else None,
        )
    if preflight.get("decision") == "watch":
        append_platform_event_throttled(
            "paper.runtime_preflight_watch",
            "ops",
            {
                "manual": manual,
                "status": preflight.get("status", ""),
                "decision": preflight.get("decision", ""),
                "failed_checks": compact_ops_preflight_for_state(preflight).get("failed_checks", []),
            },
            throttle_key="paper.runtime_preflight_watch",
            min_interval_seconds=60,
            severity="warn",
            message="运行预检有观察项，runner 继续执行。",
        )

    with PAPER_LOCK:
        state = read_paper_state()
        if state.get("tick_running"):
            return {"ok": False, "error": "已有虚拟盘 tick 正在运行", "paper": compact_paper_state_for_response(state)}
        if manual and settings_override:
            state["settings"] = settings_override
        state["runtime_preflight"] = compact_ops_preflight_for_state(preflight)
        state["tick_running"] = False  # tick mode removed, always realtime
        state["last_tick_at"] = now_iso()
        if state.get("status") != "running" and manual:
            state["status"] = "manual"
        write_paper_state(state)

    run_id = f"paper-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}-{uuid4().hex[:8]}"
    run_dir = PAPER_RUN_DIR / run_id
    start_settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
    append_platform_event(
        "paper.tick_started",
        "paper_engine",
        {
            "run_id": run_id,
            "manual": manual,
            "mode": start_settings.get("mode", "tick"),
            "instruments": start_settings.get("instruments", []),
            "strategy_count": len(start_settings.get("strategy_ids", []) or []),
        },
        message=f"虚拟盘 tick 开始：{start_settings.get('mode', 'tick')}",
    )
    should_build = build_first if build_first is not None else not (ROOT / "traderd").exists()
    summary_path = LOG_DIR / "last_run_summary.txt"
    previous_summary_text = summary_path.read_text(encoding="utf-8") if summary_path.exists() else None
    previous_output_text = LAST_PLATFORM_OUTPUT.read_text(encoding="utf-8") if LAST_PLATFORM_OUTPUT.exists() else None
    started_perf = time.perf_counter()
    try:
        try:
            settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
            mode = str(settings.get("mode", "realtime")).strip().lower()
            # 只支持 realtime 模式（调用 C++ 完整策略引擎）
            payload = paper_live_run_tick(state, run_dir, build_first=bool(should_build))
        finally:
            if summary_path.exists():
                run_dir.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(summary_path, run_dir / "summary.txt")
            if previous_summary_text is None:
                summary_path.unlink(missing_ok=True)
            else:
                summary_path.write_text(previous_summary_text, encoding="utf-8")
            if previous_output_text is None:
                LAST_PLATFORM_OUTPUT.unlink(missing_ok=True)
            else:
                LAST_PLATFORM_OUTPUT.write_text(previous_output_text, encoding="utf-8")
        runtime_ms = (time.perf_counter() - started_perf) * 1000.0
        payload["runtime_ms"] = runtime_ms
        output_text = str(payload.get("output", ""))
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "paper_run.json").write_text(
            json.dumps(
                {
                    "id": run_id,
                    "created_at": now_iso(),
                    "ok": bool(payload.get("ok")),
                    "stage": payload.get("stage", ""),
                    "crypto": payload.get("crypto", {}),
                    "summary": payload.get("report", {}).get("summary", payload.get("summary", {})),
                    "error": "" if payload.get("ok") else output_text[-2000:],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        PAPER_LATEST_OUTPUT_PATH.write_text(output_text, encoding="utf-8")

        report = payload.get("report", {}) if isinstance(payload.get("report"), dict) else {}
        cycles_for_runtime = report.get("cycles", []) if isinstance(report.get("cycles"), list) else []
        if cycles_for_runtime:
            latest_features = cycles_for_runtime[-1].setdefault("features", {})
            if isinstance(latest_features, dict):
                latest_features["runtime_ms"] = runtime_ms
        if payload.get("skipped"):
            annotations = payload.get("markers", read_paper_markers(limit=5000))
        else:
            annotations = report_chart_annotations(report)
            PAPER_MARKERS_PATH.write_text(json.dumps(annotations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if report:
                PAPER_LATEST_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        append_paper_run_events(run_id, payload, report, settings)
        # OKX 提交放后台线程，不阻塞策略 tick 循环
        # 网络不通时 tick 仍能正常产出信号和订单，OKX 提交独立重试
        okx_auto_submit_state = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
        def _submit_okx_background():
            nonlocal okx_auto_submit_state
            try:
                okx_auto_submit_state = (
                    paper_okx_auto_submit_from_report(state, report)
                    if bool(payload.get("ok")) and not bool(payload.get("skipped"))
                    else paper_okx_auto_maintenance_state(state)
                )
            except Exception:
                okx_auto_submit_state = paper_okx_auto_maintenance_state(state)
        import threading
        t = threading.Thread(target=_submit_okx_background, daemon=True)
        t.start()
        t.join(timeout=8.0)  # 最多等 8 秒，超时就继续

        with PAPER_LOCK:
            next_state = read_paper_state()
            cycles = report.get("cycles", []) or []
            latest_portfolio = cycles[-1].get("post_trade_portfolio", {}) if cycles else next_state.get("portfolio", {})
            applied_tick = bool(payload.get("ok")) and not bool(payload.get("skipped"))
            next_state.update(
                {
                    "ok": bool(payload.get("ok")),
                    "tick_running": False,
                    "last_run_id": run_id,
                    "last_success_at": now_iso() if payload.get("ok") else next_state.get("last_success_at", ""),
                    "last_error": "" if payload.get("ok") else output_text[-2000:],
                    "run_count": int(next_state.get("run_count", 0) or 0) + (1 if applied_tick else 0),
                    "summary": report.get("summary", payload.get("summary", next_state.get("summary", {}))),
                    "portfolio": latest_portfolio,
                    "latest_cycle": latest_cycle_snapshot(report),
                    "markers_count": len(annotations.get("markers", [])),
                    "last_skip_reason": str(payload.get("reason", "")) if payload.get("skipped") else "",
                    "last_runtime_ms": runtime_ms,
                    "last_runtime_at": now_iso(),
                }
            )
            latest_snapshot = next_state.get("latest_cycle", {}) if isinstance(next_state.get("latest_cycle"), dict) else {}
            if latest_snapshot.get("market_latency_ms"):
                next_state["last_market_latency_ms"] = latest_snapshot.get("market_latency_ms")
            if isinstance(payload.get("live"), dict):
                next_state["live"] = payload["live"]
                if isinstance(payload["live"].get("market_stream_guard"), dict):
                    next_state["market_stream_guard"] = payload["live"]["market_stream_guard"]
            if isinstance(okx_auto_submit_state, dict):
                next_state["okx_auto_submit"] = okx_auto_submit_state
            if next_state.get("status") == "manual":
                next_state["status"] = "stopped"
            write_paper_state(next_state)
        return {
            "ok": bool(payload.get("ok")),
            "paper": compact_paper_state_for_response(read_paper_state()),
            "run": compact_paper_run_for_response(payload),
            "markers": annotations,
        }
    except Exception as exc:
        with PAPER_LOCK:
            failed = read_paper_state()
            failed["ok"] = False
            failed["tick_running"] = False
            failed["last_error"] = str(exc)
            if failed.get("status") == "manual":
                failed["status"] = "stopped"
            write_paper_state(failed)
        append_platform_event(
            "paper.tick_failed",
            "paper_engine",
            {"run_id": run_id, "error": str(exc), "mode": start_settings.get("mode", "tick"), "instruments": start_settings.get("instruments", [])},
            severity="error",
            message=f"虚拟盘 tick 失败：{exc}",
        )
        return {"ok": False, "error": str(exc), "paper": compact_paper_state_for_response(read_paper_state())}


def paper_worker_loop() -> None:
    first_run = True
    paused_since: Optional[float] = None
    while not PAPER_STOP_EVENT.is_set():
        with PAPER_LOCK:
            state = read_paper_state()
            status = state.get("status", "")
        if status == "stopped":
            break
        if status == "paused":
            if paused_since is None:
                paused_since = time.time()
            poll = paper_worker_poll_seconds(state.get("settings", {}))
            # 暂停超过 30 分钟后自动重试预检，看阻断条件是否已消除
            if time.time() - paused_since < 30 * 60:
                if PAPER_STOP_EVENT.wait(poll):
                    break
                continue
            # 超时，尝试重新运行预检
            runtime_settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
            preflight = runtime_preflight_for_settings(runtime_settings)
            if preflight.get("decision") == "block":
                blocking = preflight_blocking_checks(preflight)
                if has_hard_block(blocking):
                    paused_since = time.time()  # 重置计时，继续等
                    if PAPER_STOP_EVENT.wait(poll):
                        break
                    continue
            # 阻断已消除，恢复运行
            with PAPER_LOCK:
                current = read_paper_state()
                current["status"] = "running"
                current["paused_at"] = ""
                write_paper_state(current)
            paused_since = None
            first_run = True
            append_platform_event(
                "paper.auto_resumed", "ops",
                {"reason": "预检阻断条件已消除，自动恢复运行。"},
                severity="info", message="虚拟盘自动恢复运行。",
            )

        result = paper_run_tick(build_first=first_run)
        first_run = False
        with PAPER_LOCK:
            state = read_paper_state()
            status = state.get("status", "")
            if status == "stopped":
                break
            if status == "paused":
                continue
            poll_seconds = paper_worker_poll_seconds(state.get("settings", {}))
            state["next_tick_after"] = text_from_epoch_ms(int((time.time() + poll_seconds) * 1000))
            if not result.get("ok"):
                state["last_error"] = result.get("error", state.get("last_error", ""))
            write_paper_state(state)
        if PAPER_STOP_EVENT.wait(poll_seconds):
            break
    with PAPER_LOCK:
        state = read_paper_state()
        state["tick_running"] = False
        if state.get("status") in {"running", "stopping", "paused"}:
            state["status"] = "stopped"
            state["stopped_at"] = now_iso()
            state["next_tick_after"] = ""
        write_paper_state(state)


def spawn_paper_worker_thread() -> None:
    global PAPER_THREAD
    PAPER_STOP_EVENT.clear()
    PAPER_THREAD = threading.Thread(target=paper_worker_loop, name="katrade-paper-runner", daemon=True)
    PAPER_THREAD.start()


def start_paper_runner(body: dict[str, Any]) -> dict[str, Any]:
    if str(body.get("confirm", "")) != "PAPER_TRADING_ONLY":
        raise ValueError("启动虚拟盘必须带 confirm=PAPER_TRADING_ONLY")
    ensure_automation_not_frozen("启动虚拟盘 runner")
    settings = paper_settings_from_body(body)
    okx_submit_gate = ensure_paper_okx_auto_submit_ready(settings)
    market_guard = ensure_paper_market_stream(settings)
    cxx_runner = ensure_realtime_engine_runner_for_settings(settings)
    with PAPER_LOCK:
        if paper_thread_alive():
            state = read_paper_state()
            previous_auto = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
            state["settings"] = settings
            state["execution_policy"] = paper_execution_policy()
            state["market_stream_guard"] = market_guard
            state["cxx_realtime_runner"] = cxx_runner
            state["okx_submit_gate"] = okx_submit_gate
            state["okx_auto_submit"] = paper_okx_auto_state_for_settings(
                settings,
                previous_auto,
                "OKX 自动提交已写入运行中 runner；下一个 tick 生成的合格订单会提交到 OKX 模拟盘。"
                if settings.get("okx_auto_submit")
                else "OKX 自动提交未开启。",
            )
            write_paper_state(state)
            return {
                "ok": True,
                "reused": True,
                "settings_updated": True,
                "paper": compact_paper_state_for_response(read_paper_state()),
                "markers": read_paper_markers(limit=300),
            }
        PAPER_STOP_EVENT.clear()
        state = read_paper_state()
        previous_auto = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
        state.update(
            {
                "ok": True,
                "status": "running",
                "started_at": now_iso(),
                "stopped_at": "",
                "last_tick_at": "",
                "last_success_at": "",
                "next_tick_after": "",
                "run_count": 0,
                "last_run_id": "",
                "last_error": "",
                "last_skip_reason": "",
                "settings": settings,
                "summary": {},
                "portfolio": {},
                "latest_cycle": {},
                "diagnostics": {},
                "market_stream_guard": market_guard,
                "cxx_realtime_runner": cxx_runner,
                "okx_submit_gate": okx_submit_gate,
                "markers_count": 0,
                "live": default_live_paper_state(settings) if settings.get("mode", "realtime") != "replay" else {},
                "okx_auto_submit": paper_okx_auto_state_for_settings(settings, previous_auto),
                "execution_policy": paper_execution_policy(),
            }
        )
        PAPER_DIR.mkdir(parents=True, exist_ok=True)
        empty_report = {"summary": {}, "equity_curve": [], "cycles": []}
        empty_markers = {"generated_at": now_iso(), "summary": {}, "markers": [], "metrics": []}
        PAPER_LATEST_REPORT_PATH.write_text(json.dumps(empty_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        PAPER_MARKERS_PATH.write_text(json.dumps(empty_markers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        PAPER_LATEST_OUTPUT_PATH.write_text("", encoding="utf-8")
        write_paper_state(state)
        spawn_paper_worker_thread()
        return {
            "ok": True,
            "reused": False,
            "paper": compact_paper_state_for_response(read_paper_state()),
            "markers": read_paper_markers(limit=300),
        }


def resume_paper_runner(body: dict[str, Any]) -> dict[str, Any]:
    if str(body.get("confirm", "")) != "RESUME_PAPER_TRADING_ONLY":
        raise ValueError("恢复虚拟盘必须带 confirm=RESUME_PAPER_TRADING_ONLY")
    ensure_automation_not_frozen("恢复虚拟盘 runner")
    with PAPER_LOCK:
        if paper_thread_alive():
            state = read_paper_state()
            settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
            if paper_okx_auto_submission_required() and not settings.get("okx_auto_submit"):
                if str(body.get("okx_auto_confirm", body.get("okxAutoConfirm", ""))).strip() != PAPER_OKX_AUTO_CONFIRM:
                    raise ValueError(f"运行中的虚拟盘需要挂到 OKX 模拟盘，必须带 okx_auto_confirm={PAPER_OKX_AUTO_CONFIRM}")
                settings = {**settings, "okx_auto_submit": True}
                state["settings"] = settings
                previous_auto = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
                state["okx_submit_gate"] = ensure_paper_okx_auto_submit_ready(settings)
                state["okx_auto_submit"] = paper_okx_auto_state_for_settings(
                    settings,
                    previous_auto,
                    "OKX 自动提交已写入运行中 runner；下一个 tick 生成的合格订单会提交到 OKX 模拟盘。",
                )
                state["cxx_realtime_runner"] = ensure_realtime_engine_runner_for_settings(settings)
                state["execution_policy"] = paper_execution_policy()
                write_paper_state(state)
                return {
                    "ok": True,
                    "reused": True,
                    "settings_updated": True,
                    "paper": compact_paper_state_for_response(read_paper_state()),
                    "markers": read_paper_markers(limit=300),
                }
            state["cxx_realtime_runner"] = ensure_realtime_engine_runner_for_settings(settings)
            state["execution_policy"] = paper_execution_policy()
            write_paper_state(state)
            return {"ok": True, "reused": True, "paper": compact_paper_state_for_response(state), "markers": read_paper_markers(limit=300)}
        state = read_paper_state()
        settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
        if not settings:
            return {"ok": False, "error": "没有可恢复的虚拟盘 settings。", "paper": compact_paper_state_for_response(state)}
        auto_required = paper_okx_auto_submission_required()
        if auto_required and not settings.get("okx_auto_submit"):
            if str(body.get("okx_auto_confirm", body.get("okxAutoConfirm", ""))).strip() != PAPER_OKX_AUTO_CONFIRM:
                raise ValueError(f"恢复虚拟盘会挂到 OKX 模拟盘，必须带 okx_auto_confirm={PAPER_OKX_AUTO_CONFIRM}")
            settings = {**settings, "okx_auto_submit": True}
            state["settings"] = settings
        elif settings.get("okx_auto_submit") and str(body.get("okx_auto_confirm", body.get("okxAutoConfirm", ""))).strip() != PAPER_OKX_AUTO_CONFIRM:
            raise ValueError(f"恢复 OKX 自动提交虚拟盘必须带 okx_auto_confirm={PAPER_OKX_AUTO_CONFIRM}")
        okx_submit_gate = ensure_paper_okx_auto_submit_ready(settings)
        market_guard = ensure_paper_market_stream(settings)
        cxx_runner = ensure_realtime_engine_runner_for_settings(settings)
        previous_auto = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
        state.update(
            {
                "ok": True,
                "status": "running",
                "tick_running": False,
                "stopped_at": "",
                "last_error": "",
                "last_skip_reason": "恢复后台线程，保留已有虚拟盘状态。",
                "resumed_at": now_iso(),
                "market_stream_guard": market_guard,
                "cxx_realtime_runner": cxx_runner,
                "okx_submit_gate": okx_submit_gate,
                "okx_auto_submit": paper_okx_auto_state_for_settings(
                    settings,
                    previous_auto,
                    "OKX 自动提交已随恢复动作武装；下一个 tick 生成的合格订单会提交到 OKX 模拟盘。"
                    if settings.get("okx_auto_submit")
                    else "OKX 自动提交未开启。",
                ),
                "execution_policy": paper_execution_policy(),
            }
        )
        write_paper_state(state)
        spawn_paper_worker_thread()
        return {
            "ok": True,
            "reused": False,
            "paper": compact_paper_state_for_response(read_paper_state()),
            "markers": read_paper_markers(limit=300),
        }


def stop_paper_runner(body: dict[str, Any]) -> dict[str, Any]:
    if str(body.get("confirm", "")) != "STOP_PAPER_TRADING":
        raise ValueError("停止虚拟盘必须带 confirm=STOP_PAPER_TRADING")
    PAPER_STOP_EVENT.set()
    with PAPER_LOCK:
        state = read_paper_state()
        state["status"] = "stopping" if state.get("tick_running") else "stopped"
        state["stopped_at"] = now_iso()
        state["next_tick_after"] = ""
        write_paper_state(state)
    return {"ok": True, "paper": compact_paper_state_for_response(read_paper_state()), "markers": read_paper_markers(limit=300)}


def read_trading_unit_agent_state() -> dict[str, Any]:
    if not TRADING_UNIT_AGENT_STATE_PATH.exists():
        return {"ok": True, "source": "none", "units": {}}
    try:
        payload = json.loads(TRADING_UNIT_AGENT_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "source": str(TRADING_UNIT_AGENT_STATE_PATH), "error": str(exc), "units": {}}
    units = payload.get("units", {}) if isinstance(payload, dict) and isinstance(payload.get("units"), dict) else {}
    return {
        "ok": True,
        "source": str(TRADING_UNIT_AGENT_STATE_PATH),
        "updated_at": payload.get("updated_at", "") if isinstance(payload, dict) else "",
        "units": units,
    }


def write_trading_unit_agent_state(body: dict[str, Any]) -> dict[str, Any]:
    if str(body.get("confirm", "")) != "UPDATE_TRADING_UNIT_AGENT_LEVERAGE":
        raise ValueError("写入交易单元杠杆建议必须带 confirm=UPDATE_TRADING_UNIT_AGENT_LEVERAGE")
    known_units = {str(unit.get("id", "")) for unit in TRADING_UNIT_DEFINITIONS}
    state = read_paper_state()
    settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
    controls = trading_unit_settings(settings)
    max_unit_leverage = float_from_any(controls.get("max_unit_effective_leverage"))
    raw_units = body.get("units", {})
    if isinstance(raw_units, list):
        raw_units = {
            str(row.get("unit_id", row.get("id", ""))): row
            for row in raw_units
            if isinstance(row, dict)
        }
    if not isinstance(raw_units, dict):
        raise ValueError("units 必须是对象或数组")

    normalized_units: dict[str, dict[str, Any]] = {}
    for unit_id, row in raw_units.items():
        unit_id = str(unit_id).strip()
        if unit_id not in known_units:
            raise ValueError(f"未知交易单元：{unit_id}")
        if not isinstance(row, dict):
            raise ValueError(f"{unit_id} 的建议必须是对象")
        requested = bounded_float(
            row.get("requested_effective_leverage", row.get("leverage", row.get("target_leverage", 0))),
            0.0,
            0.0,
            max_unit_leverage,
        )
        normalized_units[unit_id] = {
            "agent_id": str(row.get("agent_id", body.get("agent_id", "agent")) or "agent")[:80],
            "requested_effective_leverage": requested,
            "confidence": bounded_float(row.get("confidence", 0), 0.0, 0.0, 1.0),
            "statistical_edge": bounded_float(row.get("statistical_edge", 0), 0.0, -1.0, 1.0),
            "reason": str(row.get("reason", ""))[:500],
            "updated_at": now_iso(),
        }

    AGENT_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "updated_at": now_iso(),
        "source": str(body.get("source", "api")),
        "agent_id": str(body.get("agent_id", "agent"))[:80],
        "units": normalized_units,
    }
    temp = TRADING_UNIT_AGENT_STATE_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(TRADING_UNIT_AGENT_STATE_PATH)
    append_platform_event(
        "trading_unit.agent_leverage_updated",
        "agent",
        {
            "unit_ids": sorted(normalized_units),
            "source": payload["source"],
            "agent_id": payload["agent_id"],
        },
        message=f"交易单元 agent 杠杆建议已更新：{', '.join(sorted(normalized_units)) or '空'}",
    )
    return {
        "ok": True,
        "agent_state": read_trading_unit_agent_state(),
        "trading_units": paper_trading_units_payload(include_agent_brief=True, persist_agent_brief=True),
    }


def latest_cycle_for_trading_units(report: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    cycles = report.get("cycles", []) if isinstance(report.get("cycles"), list) else []
    if cycles:
        return cycles[-1]
    latest = state.get("latest_cycle", {}) if isinstance(state.get("latest_cycle"), dict) else {}
    return latest


def trading_unit_cycle_key(cycle: dict[str, Any]) -> str:
    cycle_index = cycle.get("cycle_index")
    if cycle_index is not None:
        return f"cycle:{cycle_index}"
    label = str(cycle.get("label", "") or "")
    return f"label:{label}" if label else ""


def read_trading_unit_allocation_state() -> dict[str, Any]:
    if not TRADING_UNIT_ALLOCATION_STATE_PATH.exists():
        return {"schema_version": 1, "units": {}}
    try:
        payload = json.loads(TRADING_UNIT_ALLOCATION_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "units": {}}
    if not isinstance(payload, dict):
        return {"schema_version": 1, "units": {}}
    if not isinstance(payload.get("units"), dict):
        payload["units"] = {}
    return payload


def write_trading_unit_allocation_state(payload: dict[str, Any]) -> None:
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    temp = TRADING_UNIT_ALLOCATION_STATE_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(TRADING_UNIT_ALLOCATION_STATE_PATH)


def trading_unit_settings(settings: dict[str, Any]) -> dict[str, Any]:
    config = parse_config()
    return {
        "derivatives_enabled": paper_derivatives_enabled(settings),
        "derivatives_inst_type": paper_derivatives_inst_type(settings),
        "derivatives_margin_mode": paper_derivatives_margin_mode(settings),
        "derivatives_position_mode": str(settings.get("derivatives_position_mode", config.get("execution.derivatives.position_mode", "net")) or "net").lower(),
        "max_exchange_leverage": bounded_float(
            settings.get("derivatives_max_exchange_leverage", config.get("execution.derivatives.max_exchange_leverage", "3")),
            3.0,
            1.0,
            20.0,
        ),
        "max_effective_leverage": bounded_float(
            settings.get("derivatives_max_effective_leverage", config.get("execution.derivatives.max_effective_leverage", "2")),
            2.0,
            0.0,
            10.0,
        ),
        "max_unit_effective_leverage": bounded_float(
            settings.get("derivatives_max_unit_effective_leverage", config.get("execution.derivatives.max_unit_effective_leverage", "1")),
            1.0,
            0.0,
            10.0,
        ),
        "base_notional_usdt": bounded_float(
            settings.get("trade_unit_base_notional_usdt", config.get("execution.trade_unit.base_notional_usdt", "1")),
            1.0,
            0.1,
            1000.0,
        ),
        "agent_leverage_enabled": bool_setting_from_any(
            settings.get("trade_unit_agent_leverage_enabled", config.get("execution.trade_unit.agent_leverage_enabled", "true")),
            True,
        ),
        "agent_max_step": bounded_float(
            settings.get("trade_unit_agent_max_step", config.get("execution.trade_unit.agent_max_step", "0.5")),
            0.5,
            0.0,
            5.0,
        ),
    }


def trading_unit_signal_stats(signals: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [float_from_any(row.get("score")) for row in signals if isinstance(row, dict)]
    confidences = [bounded_float(row.get("confidence", 0), 0.0, 0.0, 1.0) for row in signals if isinstance(row, dict)]
    confidence_sum = sum(confidences)
    weighted_score = (
        sum(score * confidence for score, confidence in zip(scores, confidences)) / confidence_sum
        if confidence_sum > 1e-12
        else mean_float(scores)
    )
    avg_confidence = mean_float(confidences)
    dispersion = math.sqrt(mean_float([(score - weighted_score) ** 2 for score in scores])) if scores else 0.0
    return {
        "signal_count": len(scores),
        "weighted_score": weighted_score,
        "avg_confidence": avg_confidence,
        "confidence_sum": confidence_sum,
        "long_votes": len([score for score in scores if score > 0]),
        "short_votes": len([score for score in scores if score < 0]),
        "flat_votes": len([score for score in scores if abs(score) <= 1e-12]),
        "dispersion": dispersion,
    }


def trading_unit_agent_proposal(unit: dict[str, Any], stats: dict[str, Any], controls: dict[str, Any], agent_state: dict[str, Any]) -> dict[str, Any]:
    unit_id = str(unit.get("id", ""))
    overrides = agent_state.get("units", {}) if isinstance(agent_state.get("units"), dict) else {}
    override = overrides.get(unit_id, {}) if isinstance(overrides.get(unit_id), dict) else {}
    baseline = abs(float_from_any(stats.get("weighted_score"))) * float_from_any(stats.get("avg_confidence"))
    statistical_leverage = min(float_from_any(controls["max_unit_effective_leverage"]), baseline * float_from_any(controls["max_unit_effective_leverage"]))
    if stats.get("signal_count") and statistical_leverage <= 0:
        statistical_leverage = min(0.25, float_from_any(controls["max_unit_effective_leverage"]))
    requested = bounded_float(
        override.get("requested_effective_leverage", statistical_leverage),
        statistical_leverage,
        0.0,
        float_from_any(controls["max_unit_effective_leverage"]),
    )
    confidence = bounded_float(override.get("confidence", stats.get("avg_confidence", 0)), 0.0, 0.0, 1.0)
    return {
        "agent_id": override.get("agent_id", "statistical_baseline"),
        "unit_id": unit_id,
        "source": "agent_file" if override else "statistical_baseline",
        "requested_effective_leverage": requested,
        "confidence": confidence,
        "statistical_edge": baseline,
        "reason": override.get("reason") or "按交易单元信号强度和平均置信度生成的基线建议。",
    }


def trading_unit_policy_bin_path() -> Optional[Path]:
    for candidate in (TRADING_UNIT_POLICY_BIN, TRADING_UNIT_POLICY_CMAKE_BIN):
        if candidate.exists():
            return candidate
    return None


def trading_unit_cxx_policy_decision(
    proposal: dict[str, Any],
    controls: dict[str, Any],
    current_effective_leverage: float,
    remaining_effective_budget: float,
) -> Optional[dict[str, Any]]:
    policy_bin = trading_unit_policy_bin_path()
    if policy_bin is None:
        return None
    args = [
        str(policy_bin),
        "--unit-id",
        str(proposal.get("unit_id", "")),
        "--agent-id",
        str(proposal.get("agent_id", "agent")),
        "--derivatives-enabled",
        "true" if controls.get("derivatives_enabled") else "false",
        "--agent-enabled",
        "true" if controls.get("agent_leverage_enabled") else "false",
        "--base-notional",
        str(controls.get("base_notional_usdt", 1)),
        "--max-exchange-leverage",
        str(controls.get("max_exchange_leverage", 3)),
        "--max-effective-leverage",
        str(max(0.0, remaining_effective_budget)),
        "--max-unit-effective-leverage",
        str(controls.get("max_unit_effective_leverage", 1)),
        "--max-agent-step",
        str(controls.get("agent_max_step", 0.5)),
        "--current-effective-leverage",
        str(current_effective_leverage),
        "--requested-effective-leverage",
        str(proposal.get("requested_effective_leverage", 0)),
        "--confidence",
        str(proposal.get("confidence", 0)),
        "--statistical-edge",
        str(proposal.get("statistical_edge", 0)),
        "--reason",
        str(proposal.get("reason", "")),
    ]
    try:
        completed = subprocess.run(
            args,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        payload = json.loads(completed.stdout or "{}")
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict) or not payload.get("ok"):
        return None
    payload["available"] = True
    payload["exit_code"] = completed.returncode
    payload["policy_engine"] = "cxx_trading_unit_policy"
    return payload


def trading_unit_leverage_decision(
    proposal: dict[str, Any],
    controls: dict[str, Any],
    current_effective_leverage: float,
    remaining_effective_budget: float,
    policy_engine: str = "python",
) -> dict[str, Any]:
    if policy_engine == "cxx":
        cxx_decision = trading_unit_cxx_policy_decision(
            proposal,
            controls,
            current_effective_leverage,
            remaining_effective_budget,
        )
        if cxx_decision is not None:
            return cxx_decision

    max_step = float_from_any(controls["agent_max_step"])
    max_unit = float_from_any(controls["max_unit_effective_leverage"])
    max_total = max(0.0, remaining_effective_budget)
    requested = float_from_any(proposal.get("requested_effective_leverage"))
    step_limited = min(requested, current_effective_leverage + max_step)
    effective = max(0.0, min(step_limited, max_unit, max_total))
    exchange_leverage = max(1.0, min(float_from_any(controls["max_exchange_leverage"]), math.ceil(max(1.0, effective))))
    checks = [
        paper_health_check(
            "合约执行开关",
            bool(controls.get("derivatives_enabled")),
            "warn",
            "合约模拟盘可进入风控。"
            if controls.get("derivatives_enabled")
            else "合约仍是影子模式，只展示交易单元建议。",
        ),
        paper_health_check(
            "基础单元",
            float_from_any(controls.get("base_notional_usdt")) > 0,
            "halt",
            f"基础策略下单单位 {controls.get('base_notional_usdt')} USDT。",
        ),
        paper_health_check(
            "调杠步长",
            effective <= current_effective_leverage + max_step + 1e-9,
            "halt",
            f"本次从 {current_effective_leverage:.2f}x 到 {effective:.2f}x，步长上限 {max_step:.2f}x。",
        ),
        paper_health_check(
            "交易单元上限",
            effective <= max_unit + 1e-9,
            "halt",
            f"交易单元上限 {max_unit:.2f}x。",
        ),
        paper_health_check(
            "总有效杠杆预算",
            effective <= max_total + 1e-9,
            "halt",
            f"剩余预算 {max_total:.2f}x。",
        ),
    ]
    has_halt = any(not item.get("ok") and item.get("severity") == "halt" for item in checks)
    return {
        "approved": not has_halt,
        "mode": "simulated_ready" if controls.get("derivatives_enabled") else "shadow",
        "effective_leverage": effective,
        "exchange_leverage": exchange_leverage,
        "policy_engine": "python_fallback" if policy_engine == "cxx" else "python",
        "checks": checks,
        "reason": "交易单元杠杆建议通过。"
        if not has_halt and controls.get("derivatives_enabled")
        else "影子模式建议，暂不提交合约订单。"
        if not has_halt
        else "交易单元杠杆建议被硬风控阻断。",
    }


def trading_unit_agent_brief(payload: dict[str, Any]) -> dict[str, Any]:
    units = []
    payload_units = payload.get("units", [])
    if not isinstance(payload_units, list):
        payload_units = []
    for unit in payload_units:
        units.append(
            {
                "id": unit.get("id", ""),
                "display_name": unit.get("display_name", ""),
                "role": unit.get("role", ""),
                "strategy_ids": unit.get("strategy_ids", []),
                "active_strategy_ids": unit.get("active_strategy_ids", []),
                "stats": unit.get("stats", {}),
                "current_effective_leverage": unit.get("current_effective_leverage", 0.0),
                "previous_effective_leverage": unit.get("previous_effective_leverage", 0.0),
                "current_agent_proposal": unit.get("agent_proposal", {}),
                "current_policy_decision": unit.get("leverage_decision", {}),
                "base_order_notional_usdt": unit.get("base_order_notional_usdt", 1.0),
                "base_order_units": unit.get("base_order_units", 0),
            }
        )
    return {
        "schema_version": 1,
        "generated_at": payload.get("generated_at", now_iso()),
        "write_endpoint": "/api/paper/trading_units/agent_leverage",
        "write_confirm": "UPDATE_TRADING_UNIT_AGENT_LEVERAGE",
        "controls": payload.get("controls", {}),
        "cycle": payload.get("cycle", {}),
        "summary": payload.get("summary", {}),
        "units": units,
    }


def persist_trading_unit_agent_brief(brief: dict[str, Any]) -> None:
    AGENT_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    temp = TRADING_UNIT_AGENT_BRIEF_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(TRADING_UNIT_AGENT_BRIEF_PATH)


def paper_trading_units_payload(
    state: Optional[dict[str, Any]] = None,
    report: Optional[dict[str, Any]] = None,
    *,
    include_agent_brief: bool = False,
    persist_agent_brief: bool = False,
    persist_allocation_state: bool = False,
    policy_engine: str = "python",
) -> dict[str, Any]:
    state = state if isinstance(state, dict) else read_paper_state()
    report = report if isinstance(report, dict) else read_latest_paper_report()
    settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
    controls = trading_unit_settings(settings)
    cycle = latest_cycle_for_trading_units(report, state)
    cycle_key = trading_unit_cycle_key(cycle)
    signals = cycle.get("signals", []) if isinstance(cycle.get("signals"), list) else []
    agent_state = read_trading_unit_agent_state()
    allocation_state = read_trading_unit_allocation_state()
    allocation_units = allocation_state.get("units", {}) if isinstance(allocation_state.get("units"), dict) else {}
    remaining_budget = float_from_any(controls["max_effective_leverage"])
    units: list[dict[str, Any]] = []
    next_allocation_units: dict[str, Any] = dict(allocation_units)
    allocation_changed = False

    for unit in TRADING_UNIT_DEFINITIONS:
        unit_id = str(unit.get("id", ""))
        allocation_row = allocation_units.get(unit_id, {}) if isinstance(allocation_units.get(unit_id), dict) else {}
        current_effective = max(0.0, float_from_any(allocation_row.get("current_effective_leverage", 0.0)))
        strategy_ids = set(unit.get("strategy_ids", []))
        rows = [
            row for row in signals
            if isinstance(row, dict) and str(row.get("strategy_id", "")) in strategy_ids
        ]
        stats = trading_unit_signal_stats(rows)
        proposal = trading_unit_agent_proposal(unit, stats, controls, agent_state)
        decision = trading_unit_leverage_decision(proposal, controls, current_effective, remaining_budget, policy_engine)
        decision_effective = max(0.0, float_from_any(decision.get("effective_leverage")))
        remaining_budget = max(0.0, remaining_budget - float_from_any(decision.get("effective_leverage")))
        base_units = max(0, int(stats.get("signal_count", 0) or 0))
        planned_notional = (
            base_units
            * float_from_any(controls["base_notional_usdt"])
            * decision_effective
        )
        allocation_persisted = False
        last_cycle_key = str(allocation_row.get("last_cycle_key", ""))
        if persist_allocation_state and cycle_key and last_cycle_key != cycle_key:
            next_allocation_units[unit_id] = {
                "unit_id": unit_id,
                "current_effective_leverage": decision_effective,
                "previous_effective_leverage": current_effective,
                "last_cycle_key": cycle_key,
                "last_cycle_label": cycle.get("label", ""),
                "last_cycle_index": cycle.get("cycle_index"),
                "last_decision_reason": decision.get("reason", ""),
                "last_policy_engine": decision.get("policy_engine", "python"),
                "last_agent_id": proposal.get("agent_id", ""),
                "last_agent_source": proposal.get("source", ""),
                "updated_at": now_iso(),
            }
            allocation_changed = True
            allocation_persisted = True
        units.append(
            {
                **unit,
                "active_strategy_ids": sorted({str(row.get("strategy_id", "")) for row in rows if row.get("strategy_id")}),
                "stats": stats,
                "agent_proposal": proposal,
                "leverage_decision": decision,
                "current_effective_leverage": current_effective,
                "previous_effective_leverage": float_from_any(allocation_row.get("previous_effective_leverage", 0.0)),
                "last_allocation_cycle_key": last_cycle_key,
                "allocation_persisted": allocation_persisted,
                "base_order_notional_usdt": controls["base_notional_usdt"],
                "base_order_units": base_units,
                "planned_shadow_notional_usdt": planned_notional,
            }
        )

    payload = {
        "ok": True,
        "generated_at": now_iso(),
        "mode": "shadow" if not controls.get("derivatives_enabled") else "simulated_gated",
        "controls": controls,
        "agent_state": {key: agent_state.get(key) for key in ["ok", "source", "updated_at", "error"]},
        "cycle": {
            "cycle_index": cycle.get("cycle_index"),
            "label": cycle.get("label", ""),
            "signal_count": len(signals),
        },
        "summary": {
            "unit_count": len(units),
            "active_units": len([unit for unit in units if unit.get("stats", {}).get("signal_count")]),
            "base_order_notional_usdt": controls["base_notional_usdt"],
            "max_effective_leverage": controls["max_effective_leverage"],
            "max_exchange_leverage": controls["max_exchange_leverage"],
            "derivatives_enabled": controls["derivatives_enabled"],
            "allocation_state_path": str(TRADING_UNIT_ALLOCATION_STATE_PATH),
            "allocation_state_updated": bool(allocation_changed),
        },
        "units": units,
    }
    if persist_allocation_state and allocation_changed:
        allocation_state = {
            "schema_version": 1,
            "updated_at": now_iso(),
            "last_cycle_key": cycle_key,
            "last_cycle_label": cycle.get("label", ""),
            "last_cycle_index": cycle.get("cycle_index"),
            "units": next_allocation_units,
        }
        write_trading_unit_allocation_state(allocation_state)
    if include_agent_brief:
        brief = trading_unit_agent_brief(payload)
        payload["agent_brief"] = brief
        payload["agent_brief_path"] = str(TRADING_UNIT_AGENT_BRIEF_PATH)
        if persist_agent_brief:
            persist_trading_unit_agent_brief(brief)
    return payload


def paper_status_payload(inst_id: str = "", limit: int = 300) -> dict[str, Any]:
    with PAPER_LOCK:
        state = read_paper_state()
        if state.get("status") == "running" and not paper_thread_alive():
            stale_tick = bool(state.get("tick_running"))
            state["status"] = "stopped"
            state["tick_running"] = False
            state["stopped_at"] = state.get("stopped_at") or now_iso()
            state["next_tick_after"] = ""
            if stale_tick:
                state["last_skip_reason"] = "平台进程内没有后台 runner 线程，已把陈旧运行状态恢复为 stopped。"
            write_paper_state(state)
    state = read_paper_state()
    report = read_latest_paper_report()
    state["diagnostics"] = paper_strategy_diagnostics(report, state)
    state["performance"] = paper_performance_snapshot(report, state)
    state["market_stream_guard"] = paper_market_stream_guard(state.get("settings", {}))
    data_quality = paper_data_quality_snapshot(state, report)
    data_quality["cxx_realtime"] = realtime_engine_status_payload({"limit": ["5"]})
    data_quality["cxx_runner"] = realtime_engine_runner_state()
    state["data_quality"] = data_quality
    state["execution_policy"] = paper_execution_policy()
    auto_state = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
    if paper_okx_auto_submission_required() and not state.get("settings", {}).get("okx_auto_submit"):
        auto_state = {
            **auto_state,
            "enabled": False,
            "last_status": "policy_required",
            "last_message": "虚拟盘执行策略要求挂到 OKX 模拟盘；当前 runner 仍是本地模式，请重新启动或恢复。",
        }
    state["okx_auto_submit"] = {
        **auto_state,
        "submission_guard": paper_okx_auto_submission_guard(state.get("settings", {}), auto_state, report, state),
    }
    state["trading_units"] = paper_trading_units_payload(
        state,
        report,
        persist_allocation_state=True,
    )
    return {"ok": True, "paper": compact_paper_state_for_response(state), "markers": read_paper_markers(inst_id, limit=limit)}


def market_data_quality_payload() -> dict[str, Any]:
    state = read_paper_state()
    report = read_latest_paper_report()
    return {
        "ok": True,
        "data_quality": paper_data_quality_snapshot(state, report),
        "cxx_runner": realtime_engine_runner_state(),
        "cxx_realtime": realtime_engine_status_payload({"limit": ["20"]}),
    }


def realtime_engine_status_payload(params: Optional[dict[str, list[str]]] = None) -> dict[str, Any]:
    params = params or {}
    limit = bounded_int(params.get("limit", ["100"])[0], 100, 0, 1000)
    status = read_json_file(REALTIME_ENGINE_STATUS_PATH)
    quality = read_json_file(MARKET_QUALITY_LATEST_PATH)
    events = read_jsonl_tail(REALTIME_ENGINE_EVENTS_PATH, limit)
    status_file = file_state(REALTIME_ENGINE_STATUS_PATH)
    quality_file = file_state(MARKET_QUALITY_LATEST_PATH)
    event_file = file_state(REALTIME_ENGINE_EVENTS_PATH)
    return {
        "ok": True,
        "mode": "read_only",
        "message": "C++ 实时引擎状态只读桥接；当前平台不会通过该接口启动进程或提交订单。",
        "binaries": {
            "realtime_engine": REALTIME_ENGINE_BIN.exists(),
            "cmake_realtime_engine": REALTIME_ENGINE_CMAKE_BIN.exists(),
        },
        "status": status,
        "quality": quality,
        "events": events,
        "files": {
            "status": status_file,
            "quality": quality_file,
            "events": event_file,
        },
    }


def realtime_engine_runner_state() -> dict[str, Any]:
    global REALTIME_ENGINE_PROCESS, REALTIME_ENGINE_PROCESS_META
    with REALTIME_ENGINE_PROCESS_LOCK:
        process = REALTIME_ENGINE_PROCESS
        running = bool(process is not None and process.poll() is None)
        returncode = None if process is None else process.poll()
        if process is not None and returncode is not None:
            REALTIME_ENGINE_PROCESS = None
        meta = dict(REALTIME_ENGINE_PROCESS_META)
    return {
        "running": running,
        "pid": process.pid if process is not None and running else None,
        "returncode": returncode,
        "meta": meta,
        "watch_log": str(REALTIME_ENGINE_WATCH_LOG_PATH),
        "status_file": file_state(REALTIME_ENGINE_STATUS_PATH),
        "quality_file": file_state(MARKET_QUALITY_LATEST_PATH),
    }


def realtime_engine_runner_payload(params: Optional[dict[str, list[str]]] = None) -> dict[str, Any]:
    return {
        "ok": True,
        "generated_at": now_iso(),
        "runner": realtime_engine_runner_state(),
        "realtime": realtime_engine_status_payload(params or {"limit": ["20"]}),
    }


def cxx_runner_age_seconds() -> Optional[float]:
    """C++ realtime_engine watch 进程已运行秒数，未启动返回 None。"""
    state = realtime_engine_runner_state()
    if not state.get("running"):
        return None
    started_at = str(state.get("meta", {}).get("started_at", ""))
    if not started_at:
        return None
    try:
        # Python 3.9 的 fromisoformat 不认识末尾 Z，替换为 +00:00
        normalized = started_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except Exception:
        return None




def start_realtime_engine_runner_payload(body: dict[str, Any]) -> dict[str, Any]:
    global REALTIME_ENGINE_PROCESS, REALTIME_ENGINE_PROCESS_META
    if str(body.get("confirm", "")) != "START_CXX_REALTIME_WATCH":
        return {
            "ok": False,
            "error": "启动 C++ 实时质量 runner 必须带 confirm=START_CXX_REALTIME_WATCH。",
        }

    binary = realtime_engine_executable()
    if binary is None:
        build = run_command(["make", "realtime_engine"], timeout=180)
        if build["returncode"] != 0:
            return {"ok": False, "error": "realtime_engine 构建失败", "output": build["output"]}
        binary = realtime_engine_executable()
    if binary is None:
        return {"ok": False, "error": "未找到 realtime_engine 可执行文件。"}

    max_ticks = bounded_int(str(body.get("max_ticks", body.get("maxTicks", "1000"))), 1000, 1, 200_000)
    poll_ms = bounded_int(str(body.get("poll_ms", body.get("pollMs", "1000"))), 1000, 100, 60_000)
    max_tick_age_ms = bounded_int(
        str(body.get("max_tick_age_ms", body.get("maxTickAgeMs", "30000"))),
        30_000,
        1_000,
        300_000,
    )
    idle_block_ms = bounded_int(
        str(body.get("idle_block_ms", body.get("idleBlockMs", str(max_tick_age_ms)))),
        max_tick_age_ms,
        1_000,
        300_000,
    )
    batch_size = bounded_int(str(body.get("batch_size", body.get("batchSize", "1"))), 1, 1, 10_000)
    require_trade_id = parse_bool_setting(str(body.get("require_trade_id", body.get("requireTradeId", "true"))), True)
    watch_from_end = parse_bool_setting(str(body.get("watch_from_end", body.get("watchFromEnd", "true"))), True)

    args = [
        str(binary),
        "--market-stream-journal",
        root_relative(MARKET_STREAM_JOURNAL_PATH),
        "--watch",
        "--watch-from-end",
        "true" if watch_from_end else "false",
        "--status",
        root_relative(REALTIME_ENGINE_STATUS_PATH),
        "--event-log",
        root_relative(REALTIME_ENGINE_EVENTS_PATH),
        "--quality-report",
        root_relative(MARKET_QUALITY_LATEST_PATH),
        "--batch-size",
        str(batch_size),
        "--max-ticks",
        str(max_ticks),
        "--max-tick-age-ms",
        str(max_tick_age_ms),
        "--idle-block-ms",
        str(idle_block_ms),
        "--poll-ms",
        str(poll_ms),
        "--require-trade-id",
        "true" if require_trade_id else "false",
    ]

    REALTIME_ENGINE_DIR.mkdir(parents=True, exist_ok=True)
    with REALTIME_ENGINE_PROCESS_LOCK:
        if REALTIME_ENGINE_PROCESS is not None and REALTIME_ENGINE_PROCESS.poll() is None:
            return {"ok": True, "reused": True, "runner": realtime_engine_runner_state()}
        log_handle = REALTIME_ENGINE_WATCH_LOG_PATH.open("a", encoding="utf-8")
        log_handle.write(f"\n[{now_iso()}] starting {' '.join(args)}\n")
        log_handle.flush()
        process = subprocess.Popen(
            args,
            cwd=ROOT,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        log_handle.close()
        REALTIME_ENGINE_PROCESS = process
        REALTIME_ENGINE_PROCESS_META = {
            "started_at": now_iso(),
            "args": args,
            "mode": "watch_market_stream",
            "poll_ms": poll_ms,
            "max_ticks": max_ticks,
            "max_tick_age_ms": max_tick_age_ms,
            "idle_block_ms": idle_block_ms,
            "watch_from_end": watch_from_end,
            "read_only": True,
        }

    append_platform_event(
        "realtime.runner_started",
        "realtime_engine",
        {"pid": process.pid, "poll_ms": poll_ms, "max_tick_age_ms": max_tick_age_ms},
        message="C++ 实时行情质量 runner 已启动。",
    )
    return {"ok": True, "started": True, "runner": realtime_engine_runner_state()}


def stop_realtime_engine_runner_payload(body: dict[str, Any]) -> dict[str, Any]:
    global REALTIME_ENGINE_PROCESS, REALTIME_ENGINE_PROCESS_META
    if str(body.get("confirm", "")) != "STOP_CXX_REALTIME_WATCH":
        return {
            "ok": False,
            "error": "停止 C++ 实时质量 runner 必须带 confirm=STOP_CXX_REALTIME_WATCH。",
        }
    with REALTIME_ENGINE_PROCESS_LOCK:
        process = REALTIME_ENGINE_PROCESS
        if process is None or process.poll() is not None:
            REALTIME_ENGINE_PROCESS = None
            return {"ok": True, "stopped": False, "runner": realtime_engine_runner_state()}
        pid = process.pid
        process.terminate()
        try:
            returncode = process.wait(timeout=5)
            killed = False
        except subprocess.TimeoutExpired:
            process.kill()
            returncode = process.wait(timeout=5)
            killed = True
        REALTIME_ENGINE_PROCESS = None
        REALTIME_ENGINE_PROCESS_META = {**REALTIME_ENGINE_PROCESS_META, "stopped_at": now_iso(), "returncode": returncode}
    append_platform_event(
        "realtime.runner_stopped",
        "realtime_engine",
        {"pid": pid, "returncode": returncode, "killed": killed},
        severity="warn" if killed else "info",
        message="C++ 实时行情质量 runner 已停止。",
    )
    return {
        "ok": True,
        "stopped": True,
        "pid": pid,
        "returncode": returncode,
        "killed": killed,
        "runner": realtime_engine_runner_state(),
    }


def realtime_engine_executable() -> Optional[Path]:
    if REALTIME_ENGINE_BIN.exists():
        return REALTIME_ENGINE_BIN
    if REALTIME_ENGINE_CMAKE_BIN.exists():
        return REALTIME_ENGINE_CMAKE_BIN
    return None


def safe_realtime_ticks_path(value: str) -> Path:
    requested = value.strip() or "data/sample_ticks.csv"
    path = resolve_runtime_path(requested).resolve()
    root = ROOT.resolve()
    if path != root and root not in path.parents:
        raise ValueError("C++ 实时引擎回放只允许读取项目目录内的 tick CSV。")
    if not path.exists() or not path.is_file():
        raise ValueError(f"找不到 tick CSV: {root_relative(path)}")
    return path


def run_realtime_engine_replay_payload(body: dict[str, Any]) -> dict[str, Any]:
    if str(body.get("confirm", "")) != "RUN_CXX_REALTIME_REPLAY":
        return {
            "ok": False,
            "error": "运行 C++ 实时引擎本地回放必须带 confirm=RUN_CXX_REALTIME_REPLAY。",
        }

    binary = realtime_engine_executable()
    if binary is None:
        build = run_command(["make", "realtime_engine"], timeout=180)
        if build["returncode"] != 0:
            return {"ok": False, "error": "realtime_engine 构建失败", "output": build["output"]}
        binary = realtime_engine_executable()
    if binary is None:
        return {"ok": False, "error": "未找到 realtime_engine 可执行文件。"}

    source = str(body.get("source", "csv")).strip().lower() or "csv"
    if source not in {"csv", "market_stream"}:
        return {"ok": False, "error": "source 只能是 csv 或 market_stream。"}

    ticks_path: Optional[Path] = None
    market_stream_path: Optional[Path] = None
    if source == "market_stream":
        raw_path = str(body.get("market_stream_journal", body.get("marketStreamJournal", root_relative(MARKET_STREAM_JOURNAL_PATH))))
        market_stream_path = safe_realtime_ticks_path(raw_path)
    else:
        ticks_path = safe_realtime_ticks_path(str(body.get("ticks_path", body.get("ticksPath", "data/sample_ticks.csv"))))
    batch_size = bounded_int(str(body.get("batch_size", body.get("batchSize", "1"))), 1, 1, 10_000)
    max_ticks = bounded_int(str(body.get("max_ticks", body.get("maxTicks", "1000"))), 1000, 0, 200_000)
    max_tick_age_ms = bounded_int(
        str(body.get("max_tick_age_ms", body.get("maxTickAgeMs", "30000"))),
        30_000,
        1,
        24 * 60 * 60 * 1000,
    )
    require_trade_id = parse_bool_setting(str(body.get("require_trade_id", body.get("requireTradeId", "true"))), True)
    args = [
        str(binary),
        "--status",
        root_relative(REALTIME_ENGINE_STATUS_PATH),
        "--event-log",
        root_relative(REALTIME_ENGINE_EVENTS_PATH),
        "--quality-report",
        root_relative(MARKET_QUALITY_LATEST_PATH),
        "--batch-size",
        str(batch_size),
        "--max-ticks",
        str(max_ticks),
        "--max-tick-age-ms",
        str(max_tick_age_ms),
        "--require-trade-id",
        "true" if require_trade_id else "false",
    ]
    if source == "market_stream" and market_stream_path is not None:
        args[1:1] = ["--market-stream-journal", root_relative(market_stream_path)]
    elif ticks_path is not None:
        args[1:1] = ["--ticks", root_relative(ticks_path)]

    run = run_command(args, timeout=180)
    status_payload = realtime_engine_status_payload({"limit": ["20"]})
    return {
        "ok": run["returncode"] == 0,
        "mode": "local_replay",
        "source": source,
        "ticks_path": root_relative(ticks_path) if ticks_path is not None else "",
        "market_stream_journal": root_relative(market_stream_path) if market_stream_path is not None else "",
        "max_ticks": max_ticks,
        "returncode": run["returncode"],
        "output": run["output"],
        "realtime": status_payload,
        "error": "" if run["returncode"] == 0 else "C++ realtime_engine 回放失败。",
    }


def order_report_price(row: dict[str, Any]) -> float:
    return float_from_any(
        row.get("limit_price"),
        float_from_any(
            row.get("reference_price"),
            float_from_any(row.get("last_fill_price"), float_from_any(row.get("avg_price"), 0.0)),
        ),
    )


def safe_ratio(numerator: float, denominator: float) -> float:
    return 0.0 if abs(denominator) <= 1e-12 else numerator / denominator


def mean_float(values: list[float]) -> float:
    rows = [float_from_any(value) for value in values if value is not None]
    return sum(rows) / len(rows) if rows else 0.0


def clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def execution_calibration_value_text(key: str, value: Any) -> str:
    number = float_from_any(value)
    if key == "execution.pending_order_ttl_bars":
        return str(max(1, int(round(number))))
    if key == "execution.max_participation_rate":
        return f"{clamp_float(number, 0.002, 0.20):.6f}".rstrip("0").rstrip(".")
    if key == "execution.maker_offset_bps":
        return f"{clamp_float(number, 0.1, 20.0):.4f}".rstrip("0").rstrip(".")
    return str(value)


def execution_calibration_patch_rows(suggestions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in suggestions:
        key = str(row.get("key", ""))
        if key not in {
            "execution.max_participation_rate",
            "execution.pending_order_ttl_bars",
            "execution.maker_offset_bps",
        }:
            continue
        if not bool(row.get("changed")):
            continue
        value_text = execution_calibration_value_text(key, row.get("suggested"))
        rows.append({**row, "value": value_text, "line": f"{key}={value_text}"})
    return rows


def side_adverse_slippage_bps(side: str, limit_price: float, fill_price: float) -> float:
    if limit_price <= 0.0 or fill_price <= 0.0:
        return 0.0
    normalized = str(side or "").lower()
    if normalized in {"buy", "buying"}:
        return (fill_price - limit_price) / limit_price * 10000.0
    if normalized in {"sell", "selling"}:
        return (limit_price - fill_price) / limit_price * 10000.0
    return (fill_price - limit_price) / limit_price * 10000.0


def execution_calibration_plan(
    config: dict[str, str],
    paper_fill_rate: float,
    okx_fill_rate: float,
    paper_avg_slippage: float,
    okx_avg_slippage: float,
    okx_sample_count: int,
) -> dict[str, Any]:
    current_participation = float_from_any(config.get("execution.max_participation_rate"), 0.04)
    current_offset = float_from_any(config.get("execution.maker_offset_bps"), 2.0)
    current_ttl = int(float_from_any(config.get("execution.pending_order_ttl_bars"), 1.0))
    fill_rate_gap = okx_fill_rate - paper_fill_rate
    slippage_gap_bps = okx_avg_slippage - paper_avg_slippage
    if okx_sample_count < 5:
        severity = "warming"
        state = "样本积累中"
    elif abs(fill_rate_gap) >= 0.40 or abs(slippage_gap_bps) >= 5.0:
        severity = "critical"
        state = "偏差较大"
    elif abs(fill_rate_gap) >= 0.20 or abs(slippage_gap_bps) >= 2.0:
        severity = "warn"
        state = "需要校准"
    else:
        severity = "ok"
        state = "基本一致"
    confidence = clamp_float(okx_sample_count / 50.0, 0.0, 1.0)

    suggested_participation = current_participation
    suggested_ttl = current_ttl
    fill_reason = "成交率差异未达到调整阈值。"
    if okx_sample_count >= 5 and abs(fill_rate_gap) >= 0.20:
        if fill_rate_gap > 0.0:
            ratio = safe_ratio(okx_fill_rate, max(paper_fill_rate, 0.02))
            suggested_participation = clamp_float(current_participation * math.sqrt(max(ratio, 1.0)), 0.002, 0.20)
            suggested_ttl = min(max(current_ttl, 1) + 1, 6)
            fill_reason = "OKX 审计成交率高于虚拟盘，虚拟成交模型偏保守。"
        else:
            ratio = safe_ratio(max(okx_fill_rate, 0.02), paper_fill_rate)
            suggested_participation = clamp_float(current_participation * math.sqrt(max(ratio, 0.05)), 0.002, 0.20)
            suggested_ttl = max(current_ttl - 1, 1)
            fill_reason = "虚拟盘成交率高于 OKX 审计，虚拟成交模型偏乐观。"

    suggested_offset = current_offset
    offset_reason = "滑点差异未达到调整阈值。"
    if okx_sample_count >= 5 and abs(slippage_gap_bps) >= 2.0:
        suggested_offset = clamp_float(current_offset + slippage_gap_bps * 0.5, 0.1, 20.0)
        offset_reason = "OKX 审计滑点与虚拟盘差异较大，应校准 maker offset。"

    suggestions = [
        {
            "key": "execution.max_participation_rate",
            "current": current_participation,
            "suggested": suggested_participation,
            "unit": "ratio",
            "reason": fill_reason,
            "changed": abs(suggested_participation - current_participation) > 1e-9,
        },
        {
            "key": "execution.pending_order_ttl_bars",
            "current": current_ttl,
            "suggested": suggested_ttl,
            "unit": "ticks/bars",
            "reason": fill_reason,
            "changed": suggested_ttl != current_ttl,
        },
        {
            "key": "execution.maker_offset_bps",
            "current": current_offset,
            "suggested": suggested_offset,
            "unit": "bps",
            "reason": offset_reason,
            "changed": abs(suggested_offset - current_offset) > 1e-9,
        },
    ]
    patch_rows = execution_calibration_patch_rows(suggestions)
    can_apply = okx_sample_count >= 5 and bool(patch_rows)
    if okx_sample_count < 5:
        apply_reason = "OKX 审计样本少于 5 单，暂不建议写入配置。"
    elif patch_rows:
        apply_reason = "可写入本地 config/default.cfg；不会提交交易所订单。"
    else:
        apply_reason = "当前建议值与配置一致，无需写入。"

    return {
        "state": state,
        "severity": severity,
        "confidence": confidence,
        "current": {
            "execution.max_participation_rate": current_participation,
            "execution.maker_offset_bps": current_offset,
            "execution.pending_order_ttl_bars": current_ttl,
        },
        "suggested": suggestions,
        "patch": {
            "dry_run": True,
            "can_apply": can_apply,
            "reason": apply_reason,
            "confirm": "APPLY_EXECUTION_CALIBRATION",
            "config_path": str(DEFAULT_CONFIG),
            "changed_count": len(patch_rows),
            "changed": patch_rows,
            "lines": [row["line"] for row in patch_rows],
        },
    }


def okx_audit_execution_key(row: dict[str, Any]) -> str:
    detail = row.get("order_detail") if isinstance(row.get("order_detail"), dict) else {}
    order = row.get("order") if isinstance(row.get("order"), dict) else {}
    identity = row.get("identity") if isinstance(row.get("identity"), dict) else {}
    ord_id = str(detail.get("ord_id") or identity.get("ordId") or row.get("ord_id") or "").strip()
    cl_ord_id = str(detail.get("cl_ord_id") or order.get("clOrdId") or identity.get("clOrdId") or row.get("cl_ord_id") or "").strip()
    inst_id = str(detail.get("inst_id") or order.get("instId") or identity.get("instId") or row.get("inst_id") or "").strip()
    return ord_id or cl_ord_id or f"{inst_id}:{row.get('id', '')}"


def okx_audit_order_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    detail = row.get("order_detail") if isinstance(row.get("order_detail"), dict) else {}
    order = row.get("order") if isinstance(row.get("order"), dict) else {}
    identity = row.get("identity") if isinstance(row.get("identity"), dict) else {}
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    state = str(detail.get("state") or row.get("state") or row.get("status") or "").lower()
    inst_id = str(detail.get("inst_id") or order.get("instId") or identity.get("instId") or row.get("inst_id") or "").upper()
    side = str(detail.get("side") or order.get("side") or row.get("side") or "")
    px = float_from_any(detail.get("px"), float_from_any(order.get("px"), float_from_any(row.get("px"))))
    avg_px = float_from_any(detail.get("avg_px"), float_from_any(row.get("avg_px")))
    sz = float_from_any(detail.get("sz"), float_from_any(order.get("sz"), float_from_any(row.get("sz"))))
    acc_fill_sz = float_from_any(detail.get("acc_fill_sz"), float_from_any(row.get("acc_fill_sz")))
    if acc_fill_sz <= 0.0 and state == "filled" and sz > 0.0:
        acc_fill_sz = sz
    return {
        "audit_id": row.get("id", ""),
        "ts": row.get("ts", ""),
        "action": row.get("action", ""),
        "identity": okx_audit_execution_key(row),
        "inst_id": inst_id,
        "side": side,
        "state": state or str(result.get("sCode") or ""),
        "px": px,
        "avg_px": avg_px,
        "sz": sz,
        "acc_fill_sz": acc_fill_sz,
        "fill_ratio": safe_ratio(acc_fill_sz, sz),
        "slippage_bps": side_adverse_slippage_bps(side, px, avg_px) if acc_fill_sz > 0.0 else 0.0,
    }


def paper_execution_quality_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    limit = bounded_int(params.get("limit", ["1000"])[0], 1000, 1, 5000)
    config = parse_config()
    report = read_latest_paper_report()
    cycles = report.get("cycles", []) if isinstance(report.get("cycles"), list) else []
    paper_orders: list[dict[str, Any]] = []
    paper_fills: list[dict[str, Any]] = []
    expired_count = 0
    for cycle in cycles:
        if not isinstance(cycle, dict):
            continue
        paper_orders.extend([row for row in cycle.get("orders", []) or [] if isinstance(row, dict)])
        paper_fills.extend(
            [
                row for row in cycle.get("reports", []) or []
                if isinstance(row, dict) and float_from_any(row.get("last_fill_qty")) > 0.0
            ]
        )
        expired_count += len([row for row in cycle.get("expired_order_records", []) or [] if isinstance(row, dict)])

    filled_order_ids = {str(row.get("order_id", "")) for row in paper_fills if row.get("order_id")}
    paper_slippage = [float_from_any(row.get("slippage_bps")) for row in paper_fills]
    close_pnls = [float_from_any(row.get("close_net_pnl")) for row in paper_fills if float_from_any(row.get("closed_qty")) > 0.0]

    latest_okx_by_identity: dict[str, dict[str, Any]] = {}
    for row in read_okx_audit(limit):
        if not isinstance(row, dict) or not row.get("ok"):
            continue
        if str(row.get("action", "")) not in {"order_submitted", "order_synced", "paper_auto_order_synced"}:
            continue
        snapshot = okx_audit_order_snapshot(row)
        identity = str(snapshot.get("identity", ""))
        if identity and identity not in latest_okx_by_identity:
            latest_okx_by_identity[identity] = snapshot
    okx_orders = list(latest_okx_by_identity.values())
    okx_filled = [row for row in okx_orders if float_from_any(row.get("acc_fill_sz")) > 0.0 or str(row.get("state")) == "filled"]
    okx_slippage = [float_from_any(row.get("slippage_bps")) for row in okx_filled]
    okx_fill_ratios = [min(1.0, max(0.0, float_from_any(row.get("fill_ratio")))) for row in okx_orders if float_from_any(row.get("sz")) > 0.0]
    state_counts: dict[str, int] = {}
    for row in okx_orders:
        state = str(row.get("state") or "unknown")
        state_counts[state] = state_counts.get(state, 0) + 1

    paper_fill_rate = safe_ratio(float(len(filled_order_ids)), float(len(paper_orders)))
    okx_fill_rate = safe_ratio(float(len(okx_filled)), float(len(okx_orders)))
    paper_avg_slippage = mean_float(paper_slippage)
    okx_avg_slippage = mean_float(okx_slippage)
    fill_rate_gap = okx_fill_rate - paper_fill_rate
    slippage_gap_bps = okx_avg_slippage - paper_avg_slippage
    calibration = execution_calibration_plan(
        config,
        paper_fill_rate,
        okx_fill_rate,
        paper_avg_slippage,
        okx_avg_slippage,
        len(okx_orders),
    )
    recommendations: list[str] = []
    if okx_orders and abs(fill_rate_gap) >= 0.20:
        if fill_rate_gap < 0:
            recommendations.append("模拟成交率高于 OKX 审计样本，建议下调 execution.max_participation_rate 或缩短挂单有效期。")
        else:
            recommendations.append("OKX 审计成交率高于虚拟盘，当前虚拟成交模型可能偏保守，可提高参与率或放宽触价假设。")
    if okx_orders and abs(slippage_gap_bps) >= 2.0:
        recommendations.append("OKX 审计滑点与虚拟盘差异超过 2 bps，建议用审计均值校准 maker_offset_bps 和手续费/滑点模型。")
    if not recommendations:
        recommendations.append("样本差异暂未触发校准阈值；继续积累模拟盘审计样本。")

    return {
        "ok": True,
        "generated_at": now_iso(),
        "paper": {
            "orders": len(paper_orders),
            "filled_orders": len(filled_order_ids),
            "fills": len(paper_fills),
            "expired_orders": expired_count,
            "fill_rate": paper_fill_rate,
            "avg_slippage_bps": paper_avg_slippage,
            "close_net_pnl": sum(close_pnls),
            "avg_close_net_pnl": mean_float(close_pnls),
        },
        "okx": {
            "orders": len(okx_orders),
            "filled_orders": len(okx_filled),
            "fill_rate": okx_fill_rate,
            "avg_fill_ratio": mean_float(okx_fill_ratios),
            "avg_slippage_bps": okx_avg_slippage,
            "state_counts": dict(sorted(state_counts.items())),
            "sample": okx_orders[: min(20, limit)],
        },
        "comparison": {
            "fill_rate_gap": fill_rate_gap,
            "slippage_gap_bps": slippage_gap_bps,
            "sample_ready": len(okx_orders) >= 5,
            "calibration": calibration,
            "recommendations": recommendations,
        },
    }


def apply_execution_calibration_payload(body: dict[str, Any]) -> dict[str, Any]:
    """Apply the current execution calibration proposal to local config only.

    The calibration is intentionally based on local journals and OKX audit rows.
    This endpoint never talks to OKX and never submits/cancels orders; it only
    rewrites execution.* keys in config/default.cfg after an explicit confirm.
    """
    if str(body.get("confirm", "")) != "APPLY_EXECUTION_CALIBRATION":
        raise ValueError("应用执行校准必须带 confirm=APPLY_EXECUTION_CALIBRATION")
    limit = bounded_int(str(body.get("limit", "1000")), 1000, 1, 5000)
    before_quality = paper_execution_quality_payload({"limit": [str(limit)]})
    calibration = before_quality.get("comparison", {}).get("calibration", {})
    patch = calibration.get("patch", {}) if isinstance(calibration.get("patch"), dict) else {}
    rows = patch.get("changed", []) if isinstance(patch.get("changed"), list) else []
    if not patch.get("can_apply") or not rows:
        return {
            "ok": False,
            "error": patch.get("reason") or "暂无可写入的执行校准参数。",
            "execution_quality": before_quality,
            "config": parse_config(),
        }

    values: dict[str, str] = {}
    applied: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key", ""))
        value = str(row.get("value", ""))
        if key not in CONFIG_KEYS or not key.startswith("execution."):
            continue
        values[key] = value
        applied.append({**row, "value": value})
    if not values:
        return {
            "ok": False,
            "error": "校准结果没有可写入的 execution.* 配置。",
            "execution_quality": before_quality,
            "config": parse_config(),
        }

    backup_path = backup_config_file(DEFAULT_CONFIG)
    write_config(values)
    event = append_platform_event(
        "orders.execution_calibration_applied",
        "platform",
        {
            "changed_count": len(applied),
            "changes": applied,
            "backup_path": backup_path,
            "confidence": calibration.get("confidence"),
            "severity": calibration.get("severity"),
        },
        message=f"应用执行校准 {len(applied)} 项",
    )
    after_quality = paper_execution_quality_payload({"limit": [str(limit)]})
    return {
        "ok": True,
        "applied": applied,
        "backup_path": backup_path,
        "event": event,
        "config": parse_config(),
        "execution_quality_before": before_quality,
        "execution_quality": after_quality,
    }


def paper_order_center_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    """Build the read-only order center payload from local artifacts.

    This endpoint deliberately reads only local paper state, latest report and
    OKX audit files.  It does not poll broker private endpoints or mutate order
    state, so opening the /orders page cannot submit, cancel, or sync orders.
    """
    limit = bounded_int(params.get("limit", ["200"])[0], 200, 1, 2000)
    include_backend = bool_setting_from_any(
        params.get("backend", params.get("includeBackend", ["false"]))[0],
        False,
    )
    state = read_paper_state()
    report = read_latest_paper_report()
    cycles = report.get("cycles", []) if isinstance(report.get("cycles"), list) else []
    paper_orders: list[dict[str, Any]] = []
    fills: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    expired: list[dict[str, Any]] = []

    for cycle in cycles:
        if not isinstance(cycle, dict):
            continue
        cycle_index = int(cycle.get("cycle_index", 0) or 0)
        label = str(cycle.get("label", ""))
        for order in cycle.get("orders", []) or []:
            if not isinstance(order, dict):
                continue
            instrument = instrument_from_report_item(order)
            paper_orders.append(
                {
                    "cycle_index": cycle_index,
                    "label": label,
                    "order_id": order.get("order_id", ""),
                    "inst_id": instrument.get("inst_id", ""),
                    "side": order.get("side", ""),
                    "type": order.get("type", ""),
                    "quantity": float_from_any(order.get("quantity")),
                    "price": order_report_price(order),
                    "status": order.get("status", ""),
                    "broker_status": order.get("broker_status", ""),
                    "time_in_force": order.get("time_in_force", ""),
                    "parent_decision_id": order.get("parent_decision_id", ""),
                }
            )
        for fill in cycle.get("reports", []) or []:
            if not isinstance(fill, dict):
                continue
            instrument = instrument_from_report_item(fill)
            fills.append(
                {
                    "cycle_index": cycle_index,
                    "label": label,
                    "order_id": fill.get("order_id", ""),
                    "inst_id": instrument.get("inst_id", ""),
                    "side": fill.get("side", ""),
                    "quantity": float_from_any(fill.get("last_fill_qty")),
                    "price": float_from_any(fill.get("last_fill_price"), float_from_any(fill.get("avg_price"))),
                    "avg_price": float_from_any(fill.get("avg_price")),
                    "commission": float_from_any(fill.get("commission")),
                    "slippage_bps": float_from_any(fill.get("slippage_bps")),
                    "position_effect": fill.get("position_effect", ""),
                    "pre_position_qty": float_from_any(fill.get("pre_position_qty")),
                    "post_position_qty": float_from_any(fill.get("post_position_qty")),
                    "pre_avg_cost": float_from_any(fill.get("pre_avg_cost")),
                    "post_avg_cost": float_from_any(fill.get("post_avg_cost")),
                    "closed_qty": float_from_any(fill.get("closed_qty")),
                    "opened_qty": float_from_any(fill.get("opened_qty")),
                    "close_gross_pnl": float_from_any(fill.get("close_gross_pnl")),
                    "close_fee": float_from_any(fill.get("close_fee")),
                    "close_net_pnl": float_from_any(fill.get("close_net_pnl")),
                    "realized_pnl_after": float_from_any(fill.get("realized_pnl_after")),
                    "status": fill.get("status", ""),
                }
            )
        for row in cycle.get("pending_orders", []) or []:
            if not isinstance(row, dict):
                continue
            instrument = instrument_from_report_item(row)
            pending.append(
                {
                    "cycle_index": cycle_index,
                    "label": row.get("created_label", label),
                    "order_id": row.get("order_id", ""),
                    "inst_id": instrument.get("inst_id", ""),
                    "side": row.get("side", ""),
                    "quantity": float_from_any(row.get("quantity")),
                    "price": order_report_price(row),
                    "status": row.get("status", ""),
                    "broker_status": row.get("broker_status", ""),
                    "ttl": row.get("ttl_ticks", row.get("ttl_bars", "")),
                    "reason": row.get("reason", ""),
                    "kind": "pending",
                }
            )
        for row in cycle.get("expired_order_records", []) or []:
            if not isinstance(row, dict):
                continue
            instrument = instrument_from_report_item(row)
            expired.append(
                {
                    "cycle_index": cycle_index,
                    "label": row.get("expired_label", label),
                    "order_id": row.get("order_id", ""),
                    "inst_id": instrument.get("inst_id", ""),
                    "side": row.get("side", ""),
                    "quantity": float_from_any(row.get("quantity")),
                    "price": order_report_price(row),
                    "status": row.get("status", "Expired"),
                    "broker_status": row.get("broker_status", ""),
                    "ttl": row.get("ttl_ticks", row.get("ttl_bars", "")),
                    "reason": row.get("reason", ""),
                    "kind": "expired",
                }
            )

    audit_rows: list[dict[str, Any]] = []
    for row in read_okx_audit(limit):
        if not isinstance(row, dict):
            continue
        detail = row.get("order_detail") if isinstance(row.get("order_detail"), dict) else {}
        order = row.get("order") if isinstance(row.get("order"), dict) else {}
        identity = row.get("identity") if isinstance(row.get("identity"), dict) else {}
        audit_rows.append(
            {
                "id": row.get("id", ""),
                "ts": row.get("ts", ""),
                "action": row.get("action", ""),
                "ok": bool(row.get("ok")),
                "source_order_id": row.get("source_order_id", row.get("source_audit_id", "")),
                "inst_id": detail.get("inst_id") or order.get("instId") or identity.get("instId") or "",
                "side": detail.get("side") or order.get("side") or "",
                "ord_type": detail.get("ord_type") or order.get("ordType") or "",
                "px": detail.get("px") or order.get("px") or "",
                "sz": detail.get("sz") or order.get("sz") or "",
                "acc_fill_sz": detail.get("acc_fill_sz", ""),
                "avg_px": detail.get("avg_px", ""),
                "state": detail.get("state") or row.get("status", ""),
                "ord_id": detail.get("ord_id") or identity.get("ordId") or "",
                "cl_ord_id": detail.get("cl_ord_id") or order.get("clOrdId") or identity.get("clOrdId") or "",
                "error": row.get("error", ""),
                "error_summary": row.get("error_summary", {}) if isinstance(row.get("error_summary"), dict) else {},
            }
        )

    paper_orders.sort(key=lambda row: (row.get("cycle_index", 0), row.get("label", ""), row.get("order_id", "")), reverse=True)
    fills.sort(key=lambda row: (row.get("cycle_index", 0), row.get("label", ""), row.get("order_id", "")), reverse=True)
    lifecycle_rows = sorted(pending + expired, key=lambda row: (row.get("cycle_index", 0), row.get("label", ""), row.get("order_id", "")), reverse=True)
    order_state = order_state_payload({"limit": [str(limit)]})
    execution_quality = paper_execution_quality_payload({"limit": [str(max(limit, 1000))]})
    execution_trace = execution_trace_payload({"limit": [str(limit)]})
    execution_ledger = execution_ledger_payload({"limit": [str(limit)]})
    execution_failures = execution_failure_analysis_payload({"limit": [str(max(limit, 500))]})
    reconciliation_history = paper_okx_reconciliation_history_payload({"limit": [str(min(limit, 100))]})
    backend_order_center = (
        invoke_backendd_route("/api/backend/orders/center", timeout_seconds=3.0)
        if include_backend
        else {
            "enabled": False,
            "route": "/api/backend/orders/center",
            "note": "Pass backend=1 to include the C++ order center read model.",
        }
    )
    backend_order_consistency = (
        invoke_backendd_route("/api/backend/orders/consistency", timeout_seconds=3.0)
        if include_backend
        else {
            "enabled": False,
            "route": "/api/backend/orders/consistency",
            "note": "Pass backend=1 to include the C++ order consistency diagnostics.",
        }
    )
    status_counts: dict[str, int] = {}
    for row in paper_orders + lifecycle_rows:
        key = str(row.get("broker_status") or row.get("status") or "unknown")
        status_counts[key] = status_counts.get(key, 0) + 1
    okx_state_counts: dict[str, int] = {}
    for row in audit_rows:
        key = str(row.get("state") or row.get("action") or "unknown")
        okx_state_counts[key] = okx_state_counts.get(key, 0) + 1
    auto_state = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
    local_repair = auto_state.get("last_local_order_repair", {}) if isinstance(auto_state.get("last_local_order_repair"), dict) else {}
    broker_backfill = auto_state.get("last_broker_fill_backfill", {}) if isinstance(auto_state.get("last_broker_fill_backfill"), dict) else {}
    broker_terminal_sync = auto_state.get("last_broker_terminal_sync", {}) if isinstance(auto_state.get("last_broker_terminal_sync"), dict) else {}
    stale_broker_reconcile = auto_state.get("last_stale_broker_reconcile", {}) if isinstance(auto_state.get("last_stale_broker_reconcile"), dict) else {}
    broker_backfill_effective = (
        auto_state.get("last_broker_fill_backfill_effective", {})
        if isinstance(auto_state.get("last_broker_fill_backfill_effective"), dict)
        else {}
    )
    if not broker_backfill_effective:
        broker_backfill_effective = latest_effective_broker_fill_backfill_from_events()
    broker_terminal_sync_effective = (
        auto_state.get("last_broker_terminal_sync_effective", {})
        if isinstance(auto_state.get("last_broker_terminal_sync_effective"), dict)
        else {}
    )
    if not broker_terminal_sync_effective:
        broker_terminal_sync_effective = latest_effective_broker_terminal_sync_from_events()
    stale_broker_reconcile_effective = (
        auto_state.get("last_stale_broker_reconcile_effective", {})
        if isinstance(auto_state.get("last_stale_broker_reconcile_effective"), dict)
        else {}
    )
    if not stale_broker_reconcile_effective:
        stale_broker_reconcile_effective = latest_effective_stale_broker_reconcile_from_events()
    local_repair_effective = (
        auto_state.get("last_local_order_repair_effective", {})
        if isinstance(auto_state.get("last_local_order_repair_effective"), dict)
        else {}
    )
    if not local_repair_effective:
        local_repair_effective = latest_effective_local_order_repair_from_events()

    return {
        "ok": True,
        "generated_at": now_iso(),
        "paper_status": state.get("status", ""),
        "paper_run_id": state.get("last_run_id", ""),
        "summary": {
            "paper_orders": len(paper_orders),
            "paper_fills": len(fills),
            "paper_closed_qty": sum(float_from_any(row.get("closed_qty")) for row in fills),
            "paper_close_net_pnl": sum(float_from_any(row.get("close_net_pnl")) for row in fills),
            "paper_pending": len(pending),
            "paper_expired": len(expired),
            "okx_audit": len(audit_rows),
            "paper_status_counts": dict(sorted(status_counts.items())),
            "okx_state_counts": dict(sorted(okx_state_counts.items())),
            "order_state_orders": order_state.get("summary", {}).get("orders", 0),
            "order_state_events": order_state.get("summary", {}).get("events", 0),
            "order_state_counts": order_state.get("summary", {}).get("state_counts", {}),
            "execution_trace_events": execution_trace.get("summary", {}).get("events", 0),
            "execution_trace_status_counts": execution_trace.get("summary", {}).get("status_counts", {}),
            "execution_ledger_events": execution_ledger.get("summary", {}).get("events", 0),
            "execution_ledger_type_counts": execution_ledger.get("summary", {}).get("type_counts", {}),
            "execution_ledger_error_counts": execution_ledger.get("summary", {}).get("error_counts", {}),
            "execution_failure_decision": execution_failures.get("summary", {}).get("decision", ""),
            "execution_failure_clusters": len(execution_failures.get("clusters", []) if isinstance(execution_failures.get("clusters"), list) else []),
            "reconciliation_events": reconciliation_history.get("summary", {}).get("events", 0),
            "reconciliation_status_counts": reconciliation_history.get("summary", {}).get("status_counts", {}),
            "reconciliation_latest_status": reconciliation_history.get("summary", {}).get("latest_status", ""),
            "reconciliation_latest_mismatches": reconciliation_history.get("summary", {}).get("latest_mismatch_count", 0),
            "broker_fill_backfill_checked_at": broker_backfill.get("checked_at", ""),
            "broker_fill_backfill_requested": broker_backfill.get("requested", 0),
            "broker_fill_backfill_count": broker_backfill.get("backfilled", 0),
            "broker_fill_backfill_effective_at": broker_backfill_effective.get("checked_at", ""),
            "broker_fill_backfill_effective_count": broker_backfill_effective.get("backfilled", 0),
            "broker_terminal_sync_checked_at": broker_terminal_sync.get("checked_at", ""),
            "broker_terminal_sync_requested": broker_terminal_sync.get("requested", 0),
            "broker_terminal_sync_count": broker_terminal_sync.get("synced", 0),
            "broker_terminal_sync_effective_at": broker_terminal_sync_effective.get("checked_at", ""),
            "broker_terminal_sync_effective_count": broker_terminal_sync_effective.get("synced", 0),
            "stale_broker_reconcile_checked_at": stale_broker_reconcile.get("checked_at", ""),
            "stale_broker_reconcile_requested": stale_broker_reconcile.get("requested", 0),
            "stale_broker_reconcile_queried": stale_broker_reconcile.get("queried", 0),
            "stale_broker_reconcile_cancel_requested": stale_broker_reconcile.get("cancel_requested", 0),
            "stale_broker_reconcile_cancel_succeeded": stale_broker_reconcile.get("cancel_succeeded", 0),
            "stale_broker_reconcile_effective_at": stale_broker_reconcile_effective.get("checked_at", ""),
            "stale_broker_reconcile_effective_cancel_succeeded": stale_broker_reconcile_effective.get("cancel_succeeded", 0),
            "local_repair_checked_at": local_repair.get("checked_at", ""),
            "local_repair_requested": local_repair.get("requested", 0),
            "local_repair_expired": local_repair.get("expired", 0),
            "local_repair_skipped": local_repair.get("skipped", ""),
            "local_repair_effective_at": local_repair_effective.get("checked_at", ""),
            "local_repair_effective_expired": local_repair_effective.get("expired", 0),
            "last_success_at": state.get("last_success_at", ""),
            "total_fills": state.get("summary", {}).get("total_fills", 0),
            "pending_orders": state.get("summary", {}).get("pending_orders", 0),
        },
        "paper_orders": paper_orders[:limit],
        "fills": fills[:limit],
        "lifecycle": lifecycle_rows[:limit],
        "order_state": order_state.get("orders", []),
        "order_events": order_state.get("events", []),
        "order_journal_path": order_state.get("journal_path", ""),
        "execution_trace": execution_trace,
        "execution_ledger": execution_ledger,
        "execution_failures": execution_failures,
        "execution_quality": execution_quality,
        "backend_order_center": backend_order_center,
        "backend_order_consistency": backend_order_consistency,
        "reconciliation_history": reconciliation_history,
        "okx_audit": audit_rows[:limit],
        "baseline": read_paper_okx_baseline(),
    }


def age_seconds_from_text(value: Any) -> Optional[float]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return max(0.0, (int(time.time() * 1000) - epoch_ms_from_text(text)) / 1000.0)
    except ValueError:
        return None


def seconds_until_text(value: Any) -> Optional[float]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return (epoch_ms_from_text(text) - int(time.time() * 1000)) / 1000.0
    except ValueError:
        return None


def paper_health_check(name: str, ok: bool, severity: str, message: str, **extra: Any) -> dict[str, Any]:
    row = {"name": name, "ok": bool(ok), "severity": "ok" if ok else severity, "message": message}
    row.update(extra)
    return row


def paper_health_overall(checks: list[dict[str, Any]]) -> str:
    severities = {str(item.get("severity", "ok")) for item in checks if not item.get("ok")}
    if "halt" in severities:
        return "halt"
    if severities:
        return "warn"
    return "ok"


def paper_automation_health_payload() -> dict[str, Any]:
    state = paper_status_payload(limit=0).get("paper", {})
    settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
    summary = state.get("summary", {}) if isinstance(state.get("summary"), dict) else {}
    data_quality = state.get("data_quality", {}) if isinstance(state.get("data_quality"), dict) else {}
    auto = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
    risk = crypto_risk_status()
    ops = read_ops_state()
    okx = okx_status()
    history = history_server_status(parse_config())
    stream = market_stream_snapshot()
    stream_guard = paper_market_stream_guard(settings, stream)

    poll_seconds = paper_worker_poll_seconds(settings)
    bar_seconds = paper_bar_seconds(settings)
    stream_required = paper_mode_requires_tick_stream(settings)
    freshness_limit = poll_seconds * 3 + 10 if stream_required else max(poll_seconds * 2 + 10, bar_seconds * 2 + 10)
    stream_trade_age = age_seconds_from_text(stream.get("last_trade_at"))
    last_success_age = age_seconds_from_text(state.get("last_success_at"))
    next_tick_delay = seconds_until_text(state.get("next_tick_after"))
    next_tick_overdue = abs(next_tick_delay) if next_tick_delay is not None and next_tick_delay < 0 else 0.0
    thread_alive = paper_thread_alive()
    status = str(state.get("status", "stopped"))

    recent = [item for item in (auto.get("recent", []) or []) if isinstance(item, dict)]
    order_health = paper_okx_auto_order_health(auto, settings)
    state_counts = order_health["state_counts"]
    stale_orders = order_health["stale_orders"]
    live_orders = order_health["live_orders"]
    stale_live_limit = order_health["stale_live_limit_seconds"]
    report = read_latest_paper_report()
    submission_guard = paper_okx_auto_submission_guard(settings, auto, report, state)
    provenance = submission_guard.get("data_provenance", {}) if isinstance(submission_guard.get("data_provenance"), dict) else data_provenance_payload(settings, report, state)
    max_live_orders = paper_okx_max_live_orders(settings)

    live_pending = state.get("live", {}).get("pending_orders", []) if isinstance(state.get("live"), dict) else []
    auto_required = paper_okx_auto_submission_required()
    auto_enabled = bool(settings.get("okx_auto_submit"))
    trace_health = execution_trace_health_payload(settings, report, auto)
    reconciliation_health = paper_okx_reconciliation_health_payload(settings)
    auto_recent_count = len(recent)
    sync_error_count = int(auto.get("last_order_sync_error_count", 0) or 0)
    gross_exposure = float_from_any(summary.get("max_gross_exposure") or state.get("portfolio", {}).get("gross_exposure"), 0.0)
    max_gross = float_from_any(risk.get("limits", {}).get("risk.max_gross"), 0.8)

    checks = [
        ops_automation_freeze_check(),
        paper_health_check(
            "虚拟盘线程",
            status == "running" and thread_alive,
            "halt",
            f"status={status}, thread_alive={thread_alive}",
        ),
        paper_health_check(
            "Tick 新鲜度",
            last_success_age is not None and last_success_age <= freshness_limit,
            "warn",
            f"最近成功 {int(last_success_age)} 秒前，阈值 {freshness_limit} 秒。" if last_success_age is not None else "尚无成功 tick。",
            age_seconds=last_success_age,
            limit_seconds=freshness_limit,
        ),
        paper_health_check(
            "OKX WS 行情流",
            (not stream_required) or (bool(stream.get("running")) and stream_trade_age is not None and stream_trade_age <= max(15, poll_seconds * 3)),
            "warn",
            f"状态={stream.get('status')}，最近成交 {int(stream_trade_age)} 秒前。"
            if stream_trade_age is not None
            else f"状态={stream.get('status')}，尚无 WS 成交；tick 引擎会使用 REST 兜底。",
            status=stream.get("status"),
            last_trade_age_seconds=stream_trade_age,
        ),
        paper_health_check(
            "逐笔行情覆盖",
            bool(stream_guard.get("ready")),
            "warn",
            stream_guard.get("message", "-"),
            missing_instruments=stream_guard.get("missing_instruments", []),
            missing_channels=stream_guard.get("missing_channels", []),
        ),
        paper_health_check(
            "数据质量",
            str(data_quality.get("status", "")) == "ok",
            "warn",
            f"status={data_quality.get('status', '-')}, REST兜底={data_quality.get('summary', {}).get('rest_fallbacks', 0)}, 重复ID={data_quality.get('summary', {}).get('duplicate_trade_ids', 0)}。",
        ),
        paper_health_check(
            "数据真实性",
            bool(provenance.get("execution_ready")),
            "halt",
            provenance.get("reason", "数据来源门禁未通过。"),
        ),
        paper_health_check(
            "下一轮调度",
            bool(state.get("tick_running")) or next_tick_overdue <= max(poll_seconds, 60),
            "warn",
            "tick 执行中。"
            if state.get("tick_running")
            else "尚未写入下一轮时间。"
            if next_tick_delay is None
            else f"下一轮约 {int(max(next_tick_delay, 0))} 秒后。"
            if next_tick_delay >= 0
            else f"next_tick_after 已逾期 {int(next_tick_overdue)} 秒。",
            delay_seconds=next_tick_delay,
        ),
        paper_health_check(
            "historyd",
            bool(history.get("ok")),
            "warn",
            history.get("status") or history.get("error") or "historyd 可用",
            url=history.get("url", ""),
        ),
        paper_health_check(
            "OKX 模拟盘配置",
            bool(okx.get("configured") and okx.get("simulated") and okx.get("trading_enabled")),
            "halt",
            okx.get("message", "-"),
        ),
        paper_health_check(
            "Kill switch",
            not bool(risk.get("state", {}).get("kill_switch")),
            "halt",
            risk.get("state", {}).get("reason") or "关闭",
        ),
        paper_health_check(
            "自动提交",
            auto_enabled if auto_required else True,
            "halt" if auto_required and not auto_enabled else "warn",
            f"OKX 自动提交已武装；当前门禁：{submission_guard.get('reason', '-')}"
            if auto_enabled
            else "OKX 自动提交未开启。"
            if not auto_required
            else "虚拟盘执行策略要求挂到 OKX 模拟盘，但当前 runner 未启用自动提交。",
        ),
        paper_health_check(
            "订单状态同步",
            sync_error_count == 0,
            "warn",
            auto.get("last_order_sync_error") or f"最近同步 {auto.get('last_order_sync_count', 0) or 0} 单，更新 {auto.get('last_order_sync_changed', 0) or 0} 单。",
        ),
        paper_health_check(
            "OKX 陈旧挂单",
            not stale_orders,
            "warn",
            f"{len(stale_orders)} 个 OKX 模拟盘挂单超过 {stale_live_limit} 秒未终态。" if stale_orders else "未发现陈旧挂单。",
        ),
        paper_health_check(
            "敞口上限",
            gross_exposure <= max_gross,
            "halt",
            f"当前/最大敞口 {gross_exposure:.2%}，上限 {max_gross:.2%}。",
        ),
    ]
    if auto_enabled:
        checks.extend((submission_guard.get("engine_guard", {}) or {}).get("checks", []))
        checks.extend(trace_health.get("checks", []))
        checks.extend(reconciliation_health.get("checks", []))
    overall = paper_health_overall(checks)
    return {
        "ok": overall != "halt",
        "generated_at": now_iso(),
        "status": overall,
        "state": {
            "paper_status": status,
            "thread_alive": thread_alive,
            "tick_running": bool(state.get("tick_running")),
            "run_count": int(state.get("run_count", 0) or 0),
            "last_success_at": state.get("last_success_at", ""),
            "last_success_age_seconds": last_success_age,
            "next_tick_after": state.get("next_tick_after", ""),
            "poll_seconds": poll_seconds,
            "bar_seconds": bar_seconds,
            "stale_live_limit_seconds": stale_live_limit,
        },
        "summary": {
            "instruments": settings.get("instruments", []),
            "strategy_count": len(settings.get("strategy_ids", []) or []),
            "automation_freeze": bool(ops.get("automation_freeze")),
            "automation_freeze_reason": ops.get("reason", ""),
            "paper_pending_orders": len(live_pending),
            "okx_live_orders": len(live_orders),
            "okx_auto_max_live_orders": max_live_orders,
            "okx_stale_orders": len(stale_orders),
            "okx_auto_recent": auto_recent_count,
            "okx_order_state_counts": state_counts,
            "gross_exposure": gross_exposure,
            "max_gross": max_gross,
            "market_stream_guard": stream_guard,
            "data_quality": data_quality.get("summary", {}),
            "data_provenance": provenance.get("summary", {}),
            "submission_guard": compact_submission_guard_for_response(submission_guard),
            "execution_trace": trace_health.get("summary", {}),
            "reconciliation": reconciliation_health.get("summary", {}),
        },
        "checks": checks,
        "stale_orders": stale_orders[:30],
        "live_orders": live_orders[:30],
        "execution_trace": compact_health_payload_for_response(trace_health),
        "reconciliation": compact_health_payload_for_response(reconciliation_health),
        "historyd": {
            key: copy.deepcopy(history.get(key))
            for key in ["ok", "status", "url", "message"]
            if key in history
        },
        "market_stream": compact_market_stream_for_response(stream),
        "data_quality": compact_data_quality_for_response(data_quality, include_rows=False, include_realtime=False),
        "data_provenance": provenance,
        "okx": compact_okx_status_for_response(okx),
        "risk": compact_risk_status_for_response(risk),
    }


def ops_readiness_payload() -> dict[str, Any]:
    """Aggregate production-readiness signals for automated paper trading.

    This is a read-only operations gate.  It intentionally does not submit,
    cancel, or sync orders; it only combines already-local platform state into a
    concise decision surface that can be polled by the UI.
    """
    paper = paper_status_payload(limit=0).get("paper", {})
    automation = paper_automation_health_payload()
    ops = read_ops_state()
    settings = paper.get("settings", {}) if isinstance(paper.get("settings"), dict) else {}
    risk = automation.get("risk", {}) if isinstance(automation.get("risk"), dict) else crypto_risk_status()
    okx = automation.get("okx", {}) if isinstance(automation.get("okx"), dict) else okx_status()
    data_quality = automation.get("data_quality", {}) if isinstance(automation.get("data_quality"), dict) else {}
    data_summary = data_quality.get("summary", {}) if isinstance(data_quality.get("summary"), dict) else {}
    data_provenance = automation.get("data_provenance", {}) if isinstance(automation.get("data_provenance"), dict) else {}
    data_provenance_summary = data_provenance.get("summary", {}) if isinstance(data_provenance.get("summary"), dict) else {}
    stream = automation.get("market_stream", {}) if isinstance(automation.get("market_stream"), dict) else market_stream_snapshot()
    stream_guard = paper_market_stream_guard(settings, stream)
    auto = paper.get("okx_auto_submit", {}) if isinstance(paper.get("okx_auto_submit"), dict) else {}
    submission_guard = (auto.get("submission_guard") if isinstance(auto.get("submission_guard"), dict) else {}) or (
        automation.get("summary", {}).get("submission_guard", {})
        if isinstance(automation.get("summary"), dict)
        else {}
    )
    report = read_latest_paper_report()
    trace_health = execution_trace_health_payload(settings, report, auto)
    trace_summary = trace_health.get("summary", {}) if isinstance(trace_health.get("summary"), dict) else {}
    reconciliation_health = paper_okx_reconciliation_health_payload(settings)
    reconciliation_summary = reconciliation_health.get("summary", {}) if isinstance(reconciliation_health.get("summary"), dict) else {}

    paper_status = str(paper.get("status", "stopped"))
    mode = str(settings.get("mode", "realtime")).lower()
    auto_required = paper_okx_auto_submission_required()
    auto_enabled = bool(settings.get("okx_auto_submit") or auto.get("enabled"))
    thread_alive = paper_thread_alive()
    stale_orders = automation.get("stale_orders", []) if isinstance(automation.get("stale_orders"), list) else []
    live_orders = automation.get("live_orders", []) if isinstance(automation.get("live_orders"), list) else []
    last_success_age = age_seconds_from_text(paper.get("last_success_at"))
    poll_seconds = paper_worker_poll_seconds(settings)
    stale_running_state = paper_status == "running" and not thread_alive and not bool(paper.get("tick_running"))

    recent_events = read_platform_events(80)
    error_events = [
        event for event in recent_events
        if str(event.get("severity", "")).lower() in {"error", "critical", "halt"}
    ]
    warn_events = [
        event for event in recent_events
        if str(event.get("severity", "")).lower() == "warn"
    ]

    checks = [
        ops_automation_freeze_check(),
        paper_health_check(
            "Runner 状态一致性",
            not stale_running_state,
            "halt",
            "状态文件与当前进程一致。"
            if not stale_running_state
            else "状态文件显示 running，但当前平台进程没有后台 runner 线程。",
        ),
        paper_health_check(
            "Runner 运行状态",
            paper_status == "running" and thread_alive,
            "warn",
            f"当前 {paper_status}，自动策略未持续运行。"
            if paper_status != "running" or not thread_alive
            else "后台 runner 正在运行。",
            paper_status=paper_status,
            thread_alive=thread_alive,
        ),
        paper_health_check(
            "最近成功 tick",
            last_success_age is not None and last_success_age <= max(60, poll_seconds * 5),
            "warn",
            f"最近成功 tick {int(last_success_age)} 秒前。"
            if last_success_age is not None
            else "尚无成功 tick 样本。",
            age_seconds=last_success_age,
        ),
        paper_health_check(
            "OKX 模拟盘下单环境",
            bool(okx.get("configured") and okx.get("simulated") and okx.get("trading_enabled")),
            "halt",
            okx.get("message", "-"),
        ),
        paper_health_check(
            "自动提交策略",
            (not auto_required) or auto_enabled,
            "halt",
            "虚拟盘新委托会提交到 OKX 模拟盘。"
            if auto_enabled
            else "平台策略要求 OKX 模拟盘自动提交，但当前 runner 未武装。",
        ),
        paper_health_check(
            "自动提交门禁",
            (not auto_enabled) or bool(submission_guard.get("ready")),
            "warn",
            submission_guard.get("reason", "自动提交未开启。"),
        ),
        paper_health_check(
            "Kill switch",
            not bool(risk.get("state", {}).get("kill_switch")),
            "halt",
            risk.get("state", {}).get("reason") or "关闭",
        ),
        paper_health_check(
            "逐笔行情覆盖",
            (not paper_mode_requires_tick_stream(mode)) or bool(stream_guard.get("ready")),
            "warn",
            stream_guard.get("message", "-"),
            mode=mode,
        ),
        paper_health_check(
            "数据质量",
            str(data_quality.get("status", "")) == "ok",
            "warn",
            f"status={data_quality.get('status', '-')}, REST兜底={data_summary.get('rest_fallbacks', 0)}, 重复ID={data_summary.get('duplicate_trade_ids', 0)}。",
        ),
        paper_health_check(
            "数据真实性",
            bool(data_provenance.get("execution_ready", True)),
            "halt",
            data_provenance.get("reason", "数据来源门禁未返回状态。"),
        ),
        paper_health_check(
            "陈旧 OKX 挂单",
            len(stale_orders) == 0,
            "warn",
            f"{len(stale_orders)} 个模拟盘挂单超过阈值未终态。"
            if stale_orders
            else "未发现陈旧模拟盘挂单。",
        ),
        paper_health_check(
            "事件错误",
            len(error_events) == 0,
            "warn",
            f"最近事件流有 {len(error_events)} 条错误。"
            if error_events
            else f"最近事件流无错误，warn={len(warn_events)}。",
        ),
    ]
    if auto_enabled:
        checks.extend(trace_health.get("checks", []))
        checks.extend(reconciliation_health.get("checks", []))

    status = paper_health_overall(checks)
    actions: list[dict[str, str]] = []
    if paper_status != "running":
        actions.append({"priority": "P0", "action": "确认 OKX 模拟盘、风控和行情后，在 /paper 启动 runner。"})
    if ops.get("automation_freeze"):
        actions.append({"priority": "P0", "action": "排查冻结原因后，在 /risk 解除自动化冻结。"})
    if risk.get("state", {}).get("kill_switch"):
        actions.append({"priority": "P0", "action": "排查原因后在 /risk 关闭 kill switch。"})
    if not bool(okx.get("configured") and okx.get("simulated") and okx.get("trading_enabled")):
        actions.append({"priority": "P0", "action": "在 /live 或本地配置修复 OKX simulated trading key 与下单开关。"})
    if stale_orders:
        actions.append({"priority": "P1", "action": "在 /paper 生成陈旧挂单计划；确认后再撤销 OKX 模拟盘挂单。"})
    if paper_mode_requires_tick_stream(mode) and not stream_guard.get("ready"):
        actions.append({"priority": "P1", "action": "启动或恢复 OKX 公共 WS 行情流，减少 REST 兜底。"})
    if error_events:
        actions.append({"priority": "P1", "action": "查看 /events 中最近错误，确认是否影响策略运行。"})
    if auto_enabled and trace_health.get("status") == "warn":
        actions.append({"priority": "P1", "action": "查看 /orders 的执行决策轨迹，确认策略委托是否被门禁阻断或 trace 是否断流。"})
    if auto_enabled and reconciliation_health.get("status") == "warn":
        actions.append({"priority": "P1", "action": "在 /paper 运行 OKX 对账，确认虚拟盘与 OKX 模拟盘的基准后净变化。"})
    if not actions:
        actions.append({"priority": "P2", "action": "继续积累 OKX 模拟盘成交样本，用执行质量校准成本/滑点/成交模型。"})

    return {
        "ok": status == "ok",
        "generated_at": now_iso(),
        "status": status,
        "decision": "allow" if status == "ok" else "block" if status == "halt" else "watch",
        "summary": {
            "paper_status": paper_status,
            "thread_alive": thread_alive,
            "mode": mode,
            "instruments": settings.get("instruments", []),
            "strategy_count": len(settings.get("strategy_ids", []) or []),
            "last_success_at": paper.get("last_success_at", ""),
            "last_success_age_seconds": last_success_age,
            "okx_state": okx.get("state", ""),
            "okx_simulated": bool(okx.get("simulated")),
            "okx_trading_enabled": bool(okx.get("trading_enabled")),
            "auto_required": auto_required,
            "auto_enabled": auto_enabled,
            "submission_ready": bool(submission_guard.get("ready")),
            "live_order_count": len(live_orders),
            "stale_order_count": len(stale_orders),
            "event_errors": len(error_events),
            "event_warnings": len(warn_events),
            "execution_trace_events": trace_summary.get("events", 0),
            "execution_trace_latest_age_seconds": trace_summary.get("latest_event_age_seconds"),
            "execution_trace_status": trace_health.get("status", ""),
            "execution_trace_failure_ratio": trace_summary.get("failure_ratio", 0.0),
            "execution_trace_blocked_ratio": trace_summary.get("blocked_ratio", 0.0),
            "execution_trace_cost_bps": trace_summary.get("weighted_expected_cost_bps", 0.0),
            "reconciliation_events": reconciliation_summary.get("events", 0),
            "reconciliation_latest_age_seconds": reconciliation_summary.get("latest_age_seconds"),
            "reconciliation_status": reconciliation_health.get("status", ""),
            "reconciliation_latest_mismatches": reconciliation_summary.get("latest_mismatch_count", 0),
            "automation_freeze": bool(ops.get("automation_freeze")),
            "automation_freeze_reason": ops.get("reason", ""),
            "automation_freeze_updated_at": ops.get("updated_at", ""),
            "market_stream_status": stream.get("status", ""),
            "data_quality_status": data_quality.get("status", ""),
            "data_provenance_status": data_provenance.get("status", ""),
            "data_provenance_execution_ready": bool(data_provenance.get("execution_ready", True)),
            "data_provenance_replay_sample": bool(data_provenance_summary.get("replay_sample")),
            "data_provenance_tick_source_traceable": bool(data_provenance_summary.get("tick_source_traceable", True)),
            "data_provenance_missing_tick_sources": data_provenance_summary.get("missing_tick_sources", []),
            "data_provenance_bad_tick_sources": int(data_provenance_summary.get("bad_tick_source_count", 0) or 0),
            "data_provenance_cxx_source": data_provenance_summary.get("cxx_source", ""),
        },
        "checks": checks,
        "actions": actions,
        "automation": {
            "status": automation.get("status", ""),
            "summary": automation.get("summary", {}),
        },
        "execution_trace": trace_health,
        "reconciliation": reconciliation_health,
        "data_provenance": data_provenance,
        "recent_events": error_events[:10] + warn_events[:10],
    }


def ops_preflight_payload(body: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Hard launch gate for automated paper execution.

    Readiness is a continuous operations view and naturally warns when the runner
    is stopped.  Preflight is narrower: it answers whether a *new* automated
    paper runner may be launched without inheriting stale or unsafe state.
    """
    body = body if isinstance(body, dict) else {}
    profile = str(body.get("profile", "simulated")).strip().lower()
    raw_settings = body.get("settings") if isinstance(body.get("settings"), dict) else body
    if raw_settings:
        settings = paper_settings_from_body(raw_settings)
    else:
        paper = paper_status_payload(limit=0).get("paper", {})
        settings = dict(paper.get("settings", {}) if isinstance(paper.get("settings"), dict) else {})
        if not settings:
            settings = paper_settings_from_body(
                {
                    "instruments": ["BTC-USDT", "ETH-USDT"],
                    "bar": "1m",
                    "lookback_days": 1,
                    "max_pages": 40,
                    "mode": "realtime",
                    "poll_seconds": 2,
                    "okx_auto_submit": True,
                    "okx_auto_confirm": PAPER_OKX_AUTO_CONFIRM,
                    "okx_auto_max_live_orders": paper_okx_max_live_orders({}),
                    "derivatives_enabled": True,
                    "derivatives_inst_type": "SWAP",
                    "derivatives_margin_mode": "isolated",
                    "require_cxx_realtime_runner": False,
                }
            )

    ops = read_ops_state()
    risk = crypto_risk_status()
    okx = okx_status()
    history = history_server_status(parse_config())
    stream = market_stream_snapshot()
    stream_guard = paper_market_stream_guard(settings, stream)
    cxx_runner = realtime_engine_runner_state()
    cxx_quality = cxx_market_quality_guard(settings)
    auto_enabled = bool(settings.get("okx_auto_submit"))
    auto_required = paper_okx_auto_submission_required()
    derivatives_enabled = bool(settings.get("derivatives_enabled"))
    derivatives_inst_type = str(settings.get("derivatives_inst_type", "SWAP")).upper()
    max_live_orders = paper_okx_max_live_orders(settings)

    state = read_paper_state()
    auto = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
    order_health = paper_okx_auto_order_health(auto, settings)
    live_order_count = len(order_health.get("live_orders", []) if isinstance(order_health.get("live_orders"), list) else [])
    stale_order_count = len(order_health.get("stale_orders", []) if isinstance(order_health.get("stale_orders"), list) else [])
    reconciliation_health = paper_okx_reconciliation_health_payload(settings)
    reconciliation_summary = reconciliation_health.get("summary", {}) if isinstance(reconciliation_health.get("summary"), dict) else {}
    mismatch_count = int(reconciliation_summary.get("latest_mismatch_count", 0) or 0)

    checks = [
        paper_health_check(
            "实盘权限边界",
            profile in {"simulated", "paper", "okx-simulated", "okx_simulated"},
            "halt",
            "当前平台启动门禁只允许 OKX simulated trading；真实实盘需要单独的生产审批链路。"
            if profile not in {"simulated", "paper", "okx-simulated", "okx_simulated"}
            else "仅允许 OKX simulated trading 自动提交。",
            profile=profile,
        ),
        ops_automation_freeze_check(),
        paper_health_check(
            "OKX 模拟盘配置",
            bool(okx.get("configured") and okx.get("simulated") and okx.get("trading_enabled")),
            "halt",
            okx.get("message", "-"),
        ),
        paper_health_check(
            "Kill switch",
            not bool(risk.get("state", {}).get("kill_switch")),
            "halt",
            risk.get("state", {}).get("reason") or "关闭",
        ),
        paper_health_check(
            "启动配置",
            str(settings.get("mode", "")).lower() in {"realtime", "tick"},
            "halt",
            "realtime 模式已就绪。"
            if str(settings.get("mode", "")).lower() in {"realtime", "tick"}
            else "仅支持 realtime 模式运行虚拟盘。",
            mode=settings.get("mode", ""),
        ),
        paper_health_check(
            "合约执行链路",
            derivatives_enabled and derivatives_inst_type in OKX_DERIVATIVE_INST_TYPES,
            "halt",
            f"合约链路 {derivatives_inst_type or '-'} 已启用。"
            if derivatives_enabled and derivatives_inst_type in OKX_DERIVATIVE_INST_TYPES
            else "当前策略启动要求走 OKX SWAP/FUTURES 模拟盘链路。",
            derivatives_enabled=derivatives_enabled,
            derivatives_inst_type=derivatives_inst_type,
        ),
        paper_health_check(
            "自动提交策略",
            (not auto_required) or auto_enabled,
            "halt",
            "OKX 自动提交已武装。"
            if auto_enabled
            else "平台要求虚拟盘委托自动提交到 OKX 模拟盘，但启动配置未武装。",
        ),
        # 活跃挂单达到上限时只给 warn，不阻断 runner 启动。原因是自动化系统需要
        # 继续同步成交/撤单并清理陈旧订单；真正的新委托提交会在提交前容量门禁里暂停。
        paper_health_check(
            "活跃挂单容量",
            live_order_count < max_live_orders,
            "warn",
            f"活跃挂单 {live_order_count}/{max_live_orders}。",
            live_order_count=live_order_count,
            max_live_orders=max_live_orders,
        ),
        paper_health_check(
            "陈旧挂单",
            stale_order_count == 0,
            "warn",
            f"{stale_order_count} 个 OKX 模拟盘挂单超过阈值未终态。"
            if stale_order_count
            else "未发现陈旧模拟盘挂单。",
        ),
        paper_health_check(
            "OKX WS 行情覆盖",
            bool(stream_guard.get("ready")),
            # 仅当品种/频道覆盖本身有问题时才 halt；数据不够新鲜只是 warn，
            # 避免市场安静时段（如深夜）因短暂无成交而误熔断。
            "halt" if not stream_guard.get("coverage_ok") else "warn",
            stream_guard.get("message", "-"),
            missing_instruments=stream_guard.get("missing_instruments", []),
            missing_channels=stream_guard.get("missing_channels", []),
        ),
        paper_health_check(
            "C++ 实时 runner",
            True,  # realtime 模式不需要常驻 runner，此检查仅作信息展示
            "warn",
            "realtime 模式不要求 C++ 常驻 runner。" if not cxx_runner.get("running") else "C++ 实时行情质量 runner 正在运行。",
        ),
        paper_health_check(
            "C++ 行情质量",
            bool(cxx_quality.get("ready")),
            # 报告未就绪≠数据有问题。仅当 quality 明确判定 block 时才 halt。
            # 报告过期/源不匹配时降为 warn，不阻断启动。
            "halt" if cxx_quality.get("decision") == "block" else "warn",
            cxx_quality.get("message", "-"),
            decision=cxx_quality.get("decision", ""),
            age_seconds=cxx_quality.get("age_seconds"),
            max_age_seconds=cxx_quality.get("max_age_seconds"),
        ),
        paper_health_check(
            "historyd",
            bool(history.get("ok")),
            "warn",
            history.get("status") or history.get("error") or "historyd 可用。",
            url=history.get("url", ""),
        ),
        paper_health_check(
            "OKX 对账差异",
            mismatch_count == 0,
            "halt",
            f"最近 OKX 对账有 {mismatch_count} 个差异，启动前必须先处理。"
            if mismatch_count
            else "最近 OKX 对账未发现持仓差异；无对账样本时保持观察。",
            latest_mismatch_count=mismatch_count,
            reconciliation_status=reconciliation_health.get("status", ""),
        ),
    ]

    status = paper_health_overall(checks)
    blocking = [row for row in checks if isinstance(row, dict) and not row.get("ok") and row.get("severity") == "halt"]
    warnings = [row for row in checks if isinstance(row, dict) and not row.get("ok") and row.get("severity") != "halt"]
    decision = "block" if blocking else "watch" if warnings else "allow"
    actions: list[dict[str, str]] = []
    for row in blocking[:8]:
        actions.append({"priority": "P0", "action": f"处理阻断项：{row.get('name', '-')}: {row.get('message', '-')}"})
    for row in warnings[:5]:
        actions.append({"priority": "P1", "action": f"观察项：{row.get('name', '-')}: {row.get('message', '-')}"})
    if not actions:
        actions.append({"priority": "P2", "action": "预检通过；可以启动逐笔虚拟盘 runner。"})

    result = {
        "ok": decision != "block",
        "generated_at": now_iso(),
        "profile": profile,
        "status": status,
        "decision": decision,
        "summary": {
            "instruments": settings.get("instruments", []),
            "mode": settings.get("mode", ""),
            "poll_seconds": paper_worker_poll_seconds(settings),
            "okx_simulated": bool(okx.get("simulated")),
            "okx_trading_enabled": bool(okx.get("trading_enabled")),
            "auto_enabled": auto_enabled,
            "derivatives_enabled": derivatives_enabled,
            "derivatives_inst_type": derivatives_inst_type,
            "live_order_count": live_order_count,
            "stale_order_count": stale_order_count,
            "max_live_orders": max_live_orders,
            "market_stream_status": stream.get("status", ""),
            "cxx_quality_decision": cxx_quality.get("decision", ""),
            "reconciliation_status": reconciliation_health.get("status", ""),
            "reconciliation_latest_mismatches": mismatch_count,
        },
        "checks": checks,
        "actions": actions,
        "settings": {
            key: settings.get(key)
            for key in [
                "instruments",
                "bar",
                "mode",
                "poll_seconds",
                "okx_auto_submit",
                "okx_auto_max_live_orders",
                "derivatives_enabled",
                "derivatives_inst_type",
                "derivatives_margin_mode",
                "require_cxx_realtime_runner",
            ]
        },
        "market_stream_guard": stream_guard,
        "cxx_quality": cxx_quality,
        "order_health": order_health,
        "reconciliation": reconciliation_health,
    }
    if bool_setting_from_any(body.get("record_incident"), False) and decision == "block":
        first_action = actions[0].get("action", "") if actions and isinstance(actions[0], dict) else ""
        append_ops_incident(
            "startup_preflight_block",
            "halt",
            "启动预检阻断",
            first_action or "启动预检阻断虚拟盘 runner。",
            {
                "source": str(body.get("source", "api"))[:80],
                "profile": profile,
                "status": status,
                "decision": decision,
                "summary": result["summary"],
                "blocking_checks": [
                    {"name": row.get("name", ""), "message": row.get("message", "")}
                    for row in blocking[:8]
                ],
                "warnings": [
                    {"name": row.get("name", ""), "message": row.get("message", "")}
                    for row in warnings[:5]
                ],
            },
        )
    return result


def paper_stale_order_plan_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    health = paper_automation_health_payload()
    state = read_paper_state()
    settings = state.get("settings", {}) if isinstance(state.get("settings"), dict) else {}
    auto_cancel = paper_auto_cancel_settings(settings)
    default_min_age = int(auto_cancel.get("min_age_seconds") or health.get("state", {}).get("stale_live_limit_seconds", 180) or 180)
    min_age = bounded_int(params.get("minAgeSeconds", [str(default_min_age)])[0], default_min_age, 30, 3600)
    max_orders = bounded_int(params.get("maxOrders", [str(auto_cancel.get("max_orders", 20))])[0], int(auto_cancel.get("max_orders", 20)), 1, 50)
    live_orders = health.get("live_orders", []) if isinstance(health.get("live_orders"), list) else []
    actions, keep = stale_order_actions_from_live_orders(live_orders, min_age, max_orders)
    return {
        "ok": True,
        "generated_at": now_iso(),
        "execution_mode": "dry_run",
        "requires_confirmation": True,
        "confirmation": "手动执行计划仍要求确认；虚拟盘 runner 会按自动撤单配置处理陈旧 OKX 模拟盘挂单。",
        "auto_cancel": auto_cancel,
        "min_age_seconds": min_age,
        "max_orders": max_orders,
        "summary": {
            "live_orders": len(live_orders),
            "actionable": len(actions),
            "kept": len(keep),
            "health_status": health.get("status", ""),
        },
        "actions": actions,
        "keep": keep[:max_orders],
        "health": {
            "status": health.get("status", ""),
            "generated_at": health.get("generated_at", ""),
            "checks": health.get("checks", []),
        },
    }


def paper_update_auto_record_after_cancel(action: dict[str, Any], cancel_result: dict[str, Any]) -> dict[str, Any]:
    source_order_id = str(action.get("source_order_id", ""))
    ord_id = str(action.get("ord_id", ""))
    cl_ord_id = str(action.get("cl_ord_id", ""))
    inst_id = str(action.get("inst_id", ""))
    detail: dict[str, Any] = {}
    detail_error = ""
    if inst_id and (ord_id or cl_ord_id):
        detail_payload = okx_order_detail_payload({"instId": inst_id, "ordId": ord_id, "clOrdId": cl_ord_id})
        if detail_payload.get("ok"):
            detail = detail_payload.get("order", {})
        else:
            detail_error = str(detail_payload.get("error", "撤单后订单详情读取失败"))

    with PAPER_LOCK:
        state = read_paper_state()
        auto = state.get("okx_auto_submit", {}) if isinstance(state.get("okx_auto_submit"), dict) else {}
        recent = [dict(item) for item in (auto.get("recent", []) or []) if isinstance(item, dict)]
        updated = False
        for record in recent:
            identity = paper_okx_auto_order_identity(record) or {}
            same_source = source_order_id and source_order_id == str(record.get("source_order_id", ""))
            same_ord = ord_id and ord_id == str(identity.get("ordId", ""))
            same_cl_ord = cl_ord_id and cl_ord_id == str(identity.get("clOrdId", ""))
            if not (same_source or same_ord or same_cl_ord):
                continue
            result = dict(record.get("result", {}) if isinstance(record.get("result"), dict) else {})
            if detail:
                result["order_detail"] = detail
            record["result"] = result
            record["cancel_requested_at"] = now_iso()
            record["cancel_status"] = "submitted" if cancel_result.get("ok") else "failed"
            record["cancel_error"] = cancel_result.get("error", "")
            record["cancel_audit_id"] = cancel_result.get("audit_id", "")
            record["last_order_sync_at"] = record["cancel_requested_at"]
            record["sync_status"] = "synced" if detail else "cancel_requested"
            record["sync_error"] = detail_error
            updated = True
            break
        if updated:
            auto["recent"] = recent[-30:]
            auto["last_order_sync_at"] = now_iso()
            state["okx_auto_submit"] = auto
            write_paper_state(state)
    return {"updated": updated, "detail": detail, "detail_error": detail_error}


def cancel_paper_stale_orders_payload(body: dict[str, Any]) -> dict[str, Any]:
    if str(body.get("confirm", "")) != "CANCEL_STALE_OKX_SIMULATED_ORDERS":
        return {
            "ok": False,
            "error": "执行陈旧挂单撤单必须带 confirm=CANCEL_STALE_OKX_SIMULATED_ORDERS。",
            "requires_confirmation": True,
        }
    params = {
        "minAgeSeconds": [str(body.get("min_age_seconds", body.get("minAgeSeconds", "")) or "")],
        "maxOrders": [str(body.get("max_orders", body.get("maxOrders", "20")) or "20")],
    }
    if not params["minAgeSeconds"][0]:
        params.pop("minAgeSeconds")
    plan = paper_stale_order_plan_payload(params)
    requested_ids = {
        str(item).strip()
        for item in (body.get("source_order_ids") or body.get("sourceOrderIds") or [])
        if str(item).strip()
    }
    actions = [
        action
        for action in (plan.get("actions", []) or [])
        if isinstance(action, dict) and (not requested_ids or str(action.get("source_order_id", "")) in requested_ids)
    ]
    max_orders = bounded_int(str(body.get("max_orders", body.get("maxOrders", plan.get("max_orders", 20)))), 20, 1, 50)
    actions = actions[:max_orders]
    results: list[dict[str, Any]] = []
    for action in actions:
        payload = dict(action.get("cancel_payload", {}) if isinstance(action.get("cancel_payload"), dict) else {})
        payload["confirm"] = "CANCEL_OKX_SIMULATED_ORDER"
        inst_id = str(action.get("inst_id", ""))
        ord_id = str(action.get("ord_id", ""))
        cl_ord_id = str(action.get("cl_ord_id", ""))
        detail: dict[str, Any] = {}
        if inst_id and (ord_id or cl_ord_id):
            detail_payload = okx_order_detail_payload({"instId": inst_id, "ordId": ord_id, "clOrdId": cl_ord_id})
            if detail_payload.get("ok"):
                detail = detail_payload.get("order", {})
        terminal_before_cancel = str(detail.get("state", "")).lower() in OKX_TERMINAL_ORDER_STATES
        if terminal_before_cancel:
            result = {
                "ok": True,
                "result": {},
                "audit_id": "",
                "request_id": "",
                "message": "订单同步时已经终态，无需撤单。",
            }
            append_okx_audit(
                "paper_auto_order_synced",
                {
                    "ok": True,
                    "source_order_id": action.get("source_order_id", ""),
                    "identity": {"instId": inst_id, "ordId": ord_id, "clOrdId": cl_ord_id},
                    "previous_detail": {
                        "state": action.get("state", ""),
                        "px": action.get("px", ""),
                        "sz": action.get("sz", ""),
                    },
                    "order_detail": detail,
                },
            )
        else:
            result = okx_cancel_order(payload)
            if inst_id and (ord_id or cl_ord_id):
                detail_payload = okx_order_detail_payload({"instId": inst_id, "ordId": ord_id, "clOrdId": cl_ord_id})
                if detail_payload.get("ok"):
                    detail = detail_payload.get("order", {})
        terminal_after_cancel = str(detail.get("state", "")).lower() in OKX_TERMINAL_ORDER_STATES
        effective_ok = bool(result.get("ok")) or terminal_after_cancel
        state_update = paper_update_auto_record_after_cancel(action, result)
        if detail:
            append_broker_order_journal_sync(
                action.get("source_order_id", ""),
                {"instId": inst_id, "ordId": ord_id, "clOrdId": cl_ord_id},
                detail,
                order={},
                audit_id=str(result.get("audit_id", "")),
                sync_status="manual_cancel" if not terminal_after_cancel else "synced",
                reason="手动陈旧挂单处理后同步 OKX 状态。",
            )
        results.append(
            {
                "source_order_id": action.get("source_order_id", ""),
                "inst_id": inst_id,
                "ord_id": ord_id,
                "cl_ord_id": cl_ord_id,
                "ok": effective_ok,
                "cancel_ok": bool(result.get("ok")),
                "terminal_after_cancel": terminal_after_cancel,
                "state": detail.get("state", ""),
                "error": "" if effective_ok else result.get("error", ""),
                "result": result.get("result", {}),
                "audit_id": result.get("audit_id", ""),
                "request_id": result.get("request_id", ""),
                "state_update": state_update,
            }
        )
    audit = append_okx_audit(
        "paper_stale_orders_cancel_requested",
        {
            "ok": all(item.get("ok") for item in results) if results else True,
            "requested": len(actions),
            "succeeded": sum(1 for item in results if item.get("ok")),
            "failed": sum(1 for item in results if not item.get("ok")),
            "source_order_ids": [item.get("source_order_id", "") for item in actions],
        },
    )
    refreshed_plan = paper_stale_order_plan_payload({})
    return {
        "ok": all(item.get("ok") for item in results) if results else True,
        "generated_at": now_iso(),
        "requested": len(actions),
        "succeeded": sum(1 for item in results if item.get("ok")),
        "failed": sum(1 for item in results if not item.get("ok")),
        "results": results,
        "audit_id": audit["id"],
        "plan_before": plan,
        "plan_after": refreshed_plan,
        "paper": compact_paper_state_for_response(read_paper_state()),
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
    report = read_report_json()
    return json.dumps(
        {
            "config": config,
            "summary": summary,
            "structured_report": report,
            "data_profile": (not light and data_profile()) or {},
            "recent_events": events,
            "recent_experiments": list_experiments()[:10],
            "recent_walk_forward": list_walk_forward_runs()[:5],
            "paper_trading": paper_status_payload().get("paper", {}),
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
    session = default_agent_session(provider or DEFAULT_AGENT_PROVIDER, model or DEFAULT_AGENT_MODEL)
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
            session = default_agent_session(provider_key or DEFAULT_AGENT_PROVIDER, model or DEFAULT_AGENT_MODEL)
            save_agent_session(session)

        history = history_for_agent(session.get("messages", []))
        session["provider"] = provider_key or session.get("provider", DEFAULT_AGENT_PROVIDER)
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


def read_risk_state() -> dict[str, Any]:
    if not RISK_STATE_PATH.exists():
        return {
            "kill_switch": parse_bool_setting(parse_config().get("risk.kill_switch", "false"), False),
            "reason": "",
            "updated_at": "",
            "updated_by": "config",
        }
    try:
        state = json.loads(RISK_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        state = {}
    return {
        "kill_switch": bool(state.get("kill_switch", False)),
        "reason": str(state.get("reason", "")),
        "updated_at": str(state.get("updated_at", "")),
        "updated_by": str(state.get("updated_by", "platform")),
    }


def write_risk_state(kill_switch: bool, reason: str, updated_by: str = "platform") -> dict[str, Any]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    state = {
        "kill_switch": bool(kill_switch),
        "reason": reason.strip(),
        "updated_at": now_iso(),
        "updated_by": updated_by,
    }
    tmp_path = RISK_STATE_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(RISK_STATE_PATH)
    write_config({"risk.kill_switch": "true" if kill_switch else "false"})
    return state


def config_float(config: dict[str, str], key: str, default: float) -> float:
    try:
        return float(config.get(key, default))
    except (TypeError, ValueError):
        return default


def latest_drawdown() -> float:
    summary = parse_summary()
    try:
        return float(summary.get("max_drawdown", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def crypto_risk_status() -> dict[str, Any]:
    config = parse_config()
    state = read_risk_state()
    summary = parse_summary()
    market_quality = read_json_file(MARKET_QUALITY_LATEST_PATH)
    runtime_budget = market_quality.get("risk_budget", {}) if isinstance(market_quality.get("risk_budget"), dict) else {}
    max_order_notional = config_float(config, "risk.max_order_notional", 50_000.0)
    max_gross = config_float(config, "risk.max_gross", 0.80)
    max_single = config_float(config, "risk.max_single_weight", 0.30)
    max_drawdown = latest_drawdown()
    checks = [
        {
            "name": "Kill switch",
            "ok": not state["kill_switch"],
            "severity": "halt" if state["kill_switch"] else "ok",
            "message": state["reason"] or ("已开启" if state["kill_switch"] else "未开启"),
        },
        {
            "name": "单笔名义金额",
            "ok": max_order_notional > 0.0,
            "severity": "ok" if max_order_notional > 0.0 else "warn",
            "message": f"上限 {max_order_notional:.2f} USDT",
        },
        {
            "name": "组合敞口",
            "ok": max_gross <= 1.0,
            "severity": "ok" if max_gross <= 1.0 else "warn",
            "message": f"gross <= {max_gross:.2f}, single <= {max_single:.2f}",
        },
        {
            "name": "最近回撤",
            "ok": max_drawdown < 0.20,
            "severity": "ok" if max_drawdown < 0.20 else "warn",
            "message": f"last max drawdown {max_drawdown:.2%}",
        },
    ]
    runtime_budget_checks = runtime_budget.get("checks", []) if isinstance(runtime_budget.get("checks"), list) else []
    for item in runtime_budget_checks:
        if not isinstance(item, dict):
            continue
        checks.append(
            {
                "name": f"C++预算/{item.get('name', '-')}",
                "ok": bool(item.get("ok", False)),
                "severity": str(item.get("severity", "warn")),
                "message": str(item.get("message", "")),
            }
        )
    if runtime_budget and not runtime_budget_checks:
        action = str(runtime_budget.get("action", ""))
        checks.append(
            {
                "name": "C++预算/action",
                "ok": action not in {"Halt", "Reject"},
                "severity": "halt" if action in {"Halt", "Reject"} else "ok",
                "message": f"{action or '-'} / {runtime_budget.get('reason', '')}",
            }
        )
    status = "halt" if any(item["severity"] == "halt" for item in checks) else (
        "warn" if any(item["severity"] == "warn" for item in checks) else "ok"
    )
    return {
        "ok": status == "ok",
        "status": status,
        "state": state,
        "checks": checks,
        "limits": {
            "risk.max_single_weight": max_single,
            "risk.max_gross": max_gross,
            "risk.max_order_notional": max_order_notional,
        },
        "summary": summary,
        "runtime_budget": {
            "action": runtime_budget.get("action", ""),
            "reason": runtime_budget.get("reason", ""),
            "scale": runtime_budget.get("scale", 1.0),
            "source": str(market_quality.get("source", "")),
            "generated_at_ms": market_quality.get("generated_at_ms", 0),
        },
        "okx": okx_status(),
    }


def update_kill_switch(body: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(body.get("enabled", False))
    confirm = str(body.get("confirm", ""))
    if enabled and confirm != "ENABLE_KILL_SWITCH":
        raise ValueError("开启 kill switch 必须带 confirm=ENABLE_KILL_SWITCH")
    if not enabled and confirm != "DISABLE_KILL_SWITCH":
        raise ValueError("关闭 kill switch 必须带 confirm=DISABLE_KILL_SWITCH")
    reason = str(body.get("reason", "manual platform update"))
    write_risk_state(enabled, reason)
    append_ops_incident(
        "kill_switch_changed",
        "halt" if enabled else "info",
        f"Kill switch {'开启' if enabled else '关闭'}",
        reason,
        {"enabled": enabled, "reason": reason},
    )
    return {"ok": True, "risk": crypto_risk_status(), "config": parse_config()}


def update_ops_automation_freeze(body: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(body.get("enabled", False))
    confirm = str(body.get("confirm", ""))
    if enabled and confirm != "ENABLE_AUTOMATION_FREEZE":
        raise ValueError("开启自动化冻结必须带 confirm=ENABLE_AUTOMATION_FREEZE")
    if not enabled and confirm != "DISABLE_AUTOMATION_FREEZE":
        raise ValueError("解除自动化冻结必须带 confirm=DISABLE_AUTOMATION_FREEZE")
    reason = str(body.get("reason", "")).strip() or ("manual automation freeze" if enabled else "manual automation resume")
    state = write_ops_state(enabled, reason)
    append_platform_event(
        "ops.automation_freeze_changed",
        "ops",
        {"automation_freeze": enabled, "reason": reason},
        severity="warn" if enabled else "info",
        message=f"自动化冻结{'开启' if enabled else '解除'}：{reason}",
    )
    append_ops_incident(
        "automation_freeze_changed",
        "warn" if enabled else "info",
        f"自动化冻结{'开启' if enabled else '解除'}",
        reason,
        {"automation_freeze": enabled, "reason": reason},
    )
    return {"ok": True, "ops": state, "readiness": ops_readiness_payload()}


def read_ops_alert_ack() -> dict[str, Any]:
    if not OPS_ALERT_ACK_PATH.exists():
        return {}
    try:
        payload = json.loads(OPS_ALERT_ACK_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_ops_alert_ack(payload: dict[str, Any]) -> dict[str, Any]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    OPS_ALERT_ACK_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def ops_alert_id(source: str, name: str, message: str) -> str:
    digest = hashlib.sha256(f"{source}|{name}|{message}".encode("utf-8")).hexdigest()[:12]
    return f"ops-{digest}"


def ops_alert_action(name: str) -> str:
    mapping = {
        "自动化冻结": "在 /risk 排查原因后解除自动化冻结。",
        "Runner 状态一致性": "刷新状态；若无后台线程，保持 stopped 后重新启动 runner。",
        "Runner 运行状态": "确认门禁后在 /paper 启动 runner。",
        "最近成功 tick": "检查行情源、runner 状态和最近事件错误。",
        "OKX 模拟盘下单环境": "在 /live 或本地配置修复 OKX 模拟盘 key 与下单开关。",
        "自动提交策略": "重新启动或恢复虚拟盘，使自动提交按策略要求武装。",
        "自动提交门禁": "查看自动提交门禁原因，先处理行情延迟、引擎耗时或挂单上限。",
        "Kill switch": "排查风险原因后在 /risk 关闭 kill switch。",
        "逐笔行情覆盖": "启动或恢复 OKX 公共 WS 行情流。",
        "数据质量": "查看 /market 数据质量；减少 REST 兜底并确认成交 ID 顺序。",
        "陈旧 OKX 挂单": "在 /paper 生成陈旧挂单计划，确认后再撤单。",
        "事件错误": "打开 /events 查看最近错误事件。",
    }
    return mapping.get(name, "查看自动化门禁和事件流，确认影响范围。")


def ops_alerts_payload() -> dict[str, Any]:
    readiness = ops_readiness_payload()
    ack = read_ops_alert_ack()
    alerts: list[dict[str, Any]] = []
    for check in readiness.get("checks", []) or []:
        if not isinstance(check, dict) or check.get("ok"):
            continue
        name = str(check.get("name", "unknown"))
        message = str(check.get("message", ""))
        alert_id = ops_alert_id("readiness", name, message)
        severity = str(check.get("severity", "warn"))
        ack_row = ack.get(alert_id, {}) if isinstance(ack.get(alert_id), dict) else {}
        alerts.append(
            {
                "id": alert_id,
                "source": "readiness",
                "name": name,
                "severity": severity,
                "priority": "P0" if severity == "halt" else "P1",
                "message": message,
                "action": ops_alert_action(name),
                "active": True,
                "acknowledged": bool(ack_row.get("acknowledged")),
                "acknowledged_at": ack_row.get("acknowledged_at", ""),
                "acknowledged_by": ack_row.get("acknowledged_by", ""),
                "note": ack_row.get("note", ""),
            }
        )
    for event in readiness.get("recent_events", []) or []:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type", "event"))
        message = str(event.get("message", event_type))
        severity = str(event.get("severity", "warn"))
        if severity not in {"warn", "error", "critical", "halt"}:
            continue
        alert_id = ops_alert_id("event", event_type, message)
        if any(row.get("id") == alert_id for row in alerts):
            continue
        ack_row = ack.get(alert_id, {}) if isinstance(ack.get(alert_id), dict) else {}
        alerts.append(
            {
                "id": alert_id,
                "source": "event",
                "name": event_type,
                "severity": "halt" if severity in {"critical", "halt"} else severity,
                "priority": "P0" if severity in {"critical", "halt"} else "P1",
                "message": message,
                "action": "打开 /events 查看该事件上下文。",
                "active": True,
                "acknowledged": bool(ack_row.get("acknowledged")),
                "acknowledged_at": ack_row.get("acknowledged_at", ""),
                "acknowledged_by": ack_row.get("acknowledged_by", ""),
                "note": ack_row.get("note", ""),
                "event_id": event.get("id", ""),
                "event_ts": event.get("ts", ""),
            }
        )

    active_ids = {row["id"] for row in alerts}
    resolved = []
    for alert_id, ack_row in ack.items():
        if alert_id in active_ids or not isinstance(ack_row, dict):
            continue
        resolved.append({**ack_row, "id": alert_id, "active": False})
    alerts.sort(key=lambda row: (0 if row.get("severity") == "halt" else 1, row.get("acknowledged", False), row.get("name", "")))
    return {
        "ok": True,
        "generated_at": now_iso(),
        "status": readiness.get("status", ""),
        "decision": readiness.get("decision", ""),
        "summary": {
            "active": len(alerts),
            "unacknowledged": sum(1 for row in alerts if not row.get("acknowledged")),
            "halt": sum(1 for row in alerts if row.get("severity") == "halt"),
            "warn": sum(1 for row in alerts if row.get("severity") == "warn"),
            "resolved_acknowledged": len(resolved),
        },
        "alerts": alerts,
        "resolved": resolved[-20:],
    }


def acknowledge_ops_alert(body: dict[str, Any]) -> dict[str, Any]:
    if str(body.get("confirm", "")) != "ACK_OPS_ALERT":
        raise ValueError("确认运维告警必须带 confirm=ACK_OPS_ALERT")
    alert_id = str(body.get("alert_id", body.get("alertId", ""))).strip()
    if not alert_id:
        raise ValueError("缺少 alert_id")
    payload = read_ops_alert_ack()
    payload[alert_id] = {
        "acknowledged": True,
        "acknowledged_at": now_iso(),
        "acknowledged_by": "platform",
        "note": str(body.get("note", ""))[:500],
    }
    write_ops_alert_ack(payload)
    append_platform_event(
        "ops.alert_acknowledged",
        "ops",
        {"alert_id": alert_id, "note": payload[alert_id]["note"]},
        message=f"运维告警已确认：{alert_id}",
    )
    return {"ok": True, "alert_id": alert_id, "alerts": ops_alerts_payload()}


def append_ops_incident(
    kind: str,
    severity: str,
    title: str,
    message: str,
    payload: Optional[dict[str, Any]] = None,
    *,
    source: str = "ops",
) -> dict[str, Any]:
    """Append an immutable operations incident for post-mortem style review."""
    OPS_INCIDENT_DIR.mkdir(parents=True, exist_ok=True)
    now_ms = int(time.time() * 1000)
    normalized_severity = severity if severity in {"info", "warn", "error", "critical", "halt"} else "warn"
    incident = {
        "id": f"inc-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}-{uuid4().hex[:8]}",
        "event": "open",
        "kind": str(kind or "unknown")[:80],
        "severity": normalized_severity,
        "priority": "P0" if normalized_severity in {"critical", "halt"} else "P1" if normalized_severity in {"warn", "error"} else "P2",
        "title": str(title or kind or "运维事故")[:160],
        "message": str(message or "")[:1000],
        "source": str(source or "ops")[:80],
        "status": "open",
        "at": now_iso(),
        "at_ms": now_ms,
        "payload": compact_event_value(payload or {}),
    }
    with OPS_INCIDENT_LOCK:
        with OPS_INCIDENT_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(incident, ensure_ascii=False, separators=(",", ":")) + "\n")
    return incident


def append_ops_incident_ack(incident_id: str, note: str = "") -> dict[str, Any]:
    OPS_INCIDENT_DIR.mkdir(parents=True, exist_ok=True)
    ack = {
        "id": f"incack-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}-{uuid4().hex[:8]}",
        "event": "ack",
        "incident_id": incident_id,
        "at": now_iso(),
        "at_ms": int(time.time() * 1000),
        "acknowledged_by": "platform",
        "note": note[:500],
    }
    with OPS_INCIDENT_LOCK:
        with OPS_INCIDENT_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(ack, ensure_ascii=False, separators=(",", ":")) + "\n")
    return ack


def read_ops_incident_events(limit: int = 1000) -> list[dict[str, Any]]:
    with OPS_INCIDENT_LOCK:
        return read_jsonl_tail(OPS_INCIDENT_PATH, limit)


def ops_incident_action(kind: str) -> str:
    mapping = {
        "startup_preflight_block": "按阻断项修复 /risk 启动预检，再重新一键启动或恢复 runner。",
        "runtime_safety_halt": "先处理运行中熔断项；确认 OKX、行情、C++ 质量和对账都恢复后再启动 runner。",
        "kill_switch_changed": "Kill switch 开启时禁止新订单；恢复前先确认没有未处理风险。",
        "automation_freeze_changed": "自动化冻结期间不跑新 tick；恢复前确认当前挂单和行情状态。",
    }
    return mapping.get(kind, "查看 /risk、/paper、/orders 和 /events，确认影响范围。")


def ops_incidents_payload(params: Optional[dict[str, list[str]]] = None) -> dict[str, Any]:
    params = params or {}
    limit = bounded_int((params.get("limit", ["200"]) or ["200"])[0], 200, 1, 1000)
    events = read_ops_incident_events(max(limit * 5, limit))
    incidents: dict[str, dict[str, Any]] = {}
    acknowledgements: dict[str, dict[str, Any]] = {}
    for event in events:
        event_type = str(event.get("event", "open"))
        if event_type == "open":
            incident_id = str(event.get("id", "")).strip()
            if not incident_id:
                continue
            kind = str(event.get("kind", "unknown"))
            incidents[incident_id] = {
                "id": incident_id,
                "kind": kind,
                "severity": str(event.get("severity", "warn")),
                "priority": str(event.get("priority", "")) or ("P0" if event.get("severity") == "halt" else "P1"),
                "title": str(event.get("title", kind)),
                "message": str(event.get("message", "")),
                "source": str(event.get("source", "ops")),
                "status": "open",
                "at": event.get("at", ""),
                "at_ms": int(event.get("at_ms") or 0),
                "payload": event.get("payload", {}),
                "action": ops_incident_action(kind),
                "acknowledged": False,
                "acknowledged_at": "",
                "acknowledged_by": "",
                "note": "",
            }
        elif event_type == "ack":
            incident_id = str(event.get("incident_id", "")).strip()
            if incident_id:
                acknowledgements[incident_id] = event

    for incident_id, ack in acknowledgements.items():
        if incident_id not in incidents:
            continue
        incidents[incident_id].update(
            {
                "status": "acknowledged",
                "acknowledged": True,
                "acknowledged_at": ack.get("at", ""),
                "acknowledged_by": ack.get("acknowledged_by", ""),
                "note": ack.get("note", ""),
            }
        )

    rows = sorted(incidents.values(), key=lambda row: int(row.get("at_ms") or 0), reverse=True)
    open_count = sum(1 for row in rows if not row.get("acknowledged"))
    halt_count = sum(1 for row in rows if row.get("severity") in {"halt", "critical"} and not row.get("acknowledged"))
    warn_count = sum(1 for row in rows if row.get("severity") in {"warn", "error"} and not row.get("acknowledged"))
    return {
        "ok": True,
        "generated_at": now_iso(),
        "journal_path": str(OPS_INCIDENT_PATH),
        "summary": {
            "total": len(rows),
            "open": open_count,
            "acknowledged": sum(1 for row in rows if row.get("acknowledged")),
            "halt_open": halt_count,
            "warn_open": warn_count,
            "latest_at": rows[0].get("at", "") if rows else "",
        },
        "incidents": rows[:limit],
    }


def acknowledge_ops_incident(body: dict[str, Any]) -> dict[str, Any]:
    if str(body.get("confirm", "")) != "ACK_OPS_INCIDENT":
        raise ValueError("确认运维事故必须带 confirm=ACK_OPS_INCIDENT")
    incident_id = str(body.get("incident_id", body.get("incidentId", ""))).strip()
    if not incident_id:
        raise ValueError("缺少 incident_id")
    note = str(body.get("note", ""))[:500]
    append_ops_incident_ack(incident_id, note)
    append_platform_event(
        "ops.incident_acknowledged",
        "ops",
        {"incident_id": incident_id, "note": note},
        message=f"运维事故已确认：{incident_id}",
    )
    return {"ok": True, "incident_id": incident_id, "incidents": ops_incidents_payload()}


def ops_check_bin_path() -> Optional[Path]:
    for candidate in (OPS_CHECK_BIN, OPS_CHECK_CMAKE_BIN):
        if candidate.exists():
            return candidate
    return None


def cli_bool(value: bool) -> str:
    return "true" if value else "false"


def ops_death_modes_payload() -> dict[str, Any]:
    """Run the C++ production-death-mode diagnosis over current platform state."""
    binary = ops_check_bin_path()
    if binary is None:
        return {
            "ok": False,
            "generated_at": now_iso(),
            "error": "ops_check executable is not built; run make ops_check",
            "summary": {"decision": "block", "score": 0.0, "source": "missing_binary"},
            "modes": [],
            "actions": ["先构建 C++ ops_check，再查看生产死亡方式诊断。"],
        }

    config = parse_config()
    paper = paper_status_payload(limit=0).get("paper", {})
    readiness = ops_readiness_payload()
    readiness_summary = readiness.get("summary", {}) if isinstance(readiness.get("summary"), dict) else {}
    preflight = ops_preflight_payload({})
    automation = readiness.get("automation", {}) if isinstance(readiness.get("automation"), dict) else {}
    automation_summary = automation.get("summary", {}) if isinstance(automation.get("summary"), dict) else {}
    execution_summary = readiness_summary
    reconciliation_summary = (
        readiness.get("reconciliation", {}).get("summary", {})
        if isinstance(readiness.get("reconciliation"), dict)
        else {}
    )
    incidents = ops_incidents_payload({"limit": ["200"]})
    incident_summary = incidents.get("summary", {}) if isinstance(incidents.get("summary"), dict) else {}
    data_payload = market_data_quality_payload()
    data_quality = (
        data_payload.get("data_quality", {})
        if isinstance(data_payload.get("data_quality"), dict)
        else {}
    )
    data_summary = data_quality.get("summary", {}) if isinstance(data_quality.get("summary"), dict) else {}
    stream_guard = (
        data_quality.get("stream_guard", {})
        if isinstance(data_quality.get("stream_guard"), dict)
        else {}
    )
    cxx_quality = (
        data_quality.get("cxx_quality", {})
        if isinstance(data_quality.get("cxx_quality"), dict)
        else {}
    )
    okx = readiness.get("okx", {}) if isinstance(readiness.get("okx"), dict) else okx_status()
    historyd = readiness.get("historyd", {}) if isinstance(readiness.get("historyd"), dict) else history_server_status(config)
    risk = crypto_risk_status()
    portfolio = paper.get("portfolio", {}) if isinstance(paper.get("portfolio"), dict) else {}
    positions = portfolio.get("positions", []) if isinstance(portfolio.get("positions"), list) else []
    max_position_weight = 0.0
    for row in positions:
        if not isinstance(row, dict):
            continue
        max_position_weight = max(max_position_weight, abs(float_from_any(row.get("weight"), 0.0)))
    settings = paper.get("settings", {}) if isinstance(paper.get("settings"), dict) else {}
    paper_summary = paper.get("summary", {}) if isinstance(paper.get("summary"), dict) else {}
    experiments = list_experiments()
    walk_forward = list_walk_forward_runs()
    reconciliation_events = int(reconciliation_summary.get("events") or 0)
    reconciliation_age = reconciliation_summary.get("latest_age_seconds")
    reconciliation_max_age = float_from_any(reconciliation_summary.get("max_age_seconds"), 1800.0)
    reconciliation_fresh = (
        reconciliation_events > 0
        and reconciliation_age is not None
        and float_from_any(reconciliation_age, reconciliation_max_age + 1.0) <= reconciliation_max_age
    )
    runner_running = readiness_summary.get("paper_status") == "running" and bool(readiness_summary.get("thread_alive"))
    current_effective_leverage = max(
        float_from_any(portfolio.get("gross_exposure"), 0.0),
        float_from_any(settings.get("derivatives_max_unit_effective_leverage"), 0.0),
    )
    strategy_decay_ready = bool(walk_forward) and int(paper_summary.get("cycles") or 0) >= 100
    args = [
        str(binary),
        "--death-modes",
        "true",
        "--runner-running",
        cli_bool(runner_running),
        "--preflight-blocked",
        cli_bool(preflight.get("decision") == "block"),
        "--automation-freeze",
        cli_bool(bool(readiness_summary.get("automation_freeze"))),
        "--kill-switch",
        cli_bool(bool(risk.get("state", {}).get("kill_switch"))),
        "--okx-ready",
        cli_bool(bool(okx.get("configured") and okx.get("simulated") and okx.get("trading_enabled"))),
        "--historyd-ok",
        cli_bool(bool(historyd.get("ok"))),
        "--market-stream-ready",
        cli_bool(bool(stream_guard.get("ready"))),
        "--data-quality-ok",
        cli_bool(str(data_quality.get("status", "")) == "ok"),
        "--cxx-quality-ready",
        cli_bool(bool(cxx_quality.get("ready"))),
        "--reconciliation-fresh",
        cli_bool(reconciliation_fresh),
        "--correlation-monitor-ready",
        "false",
        "--strategy-decay-monitor-ready",
        cli_bool(strategy_decay_ready),
        "--regulatory-review-ready",
        "false",
        "--stale-order-count",
        str(int(automation_summary.get("okx_stale_orders") or readiness_summary.get("stale_order_count") or 0)),
        "--live-order-count",
        str(int(automation_summary.get("okx_live_orders") or readiness_summary.get("live_order_count") or 0)),
        "--max-live-orders",
        str(paper_okx_max_live_orders(settings)),
        "--event-error-count",
        str(int(readiness_summary.get("event_errors") or 0)),
        "--incident-open-count",
        str(int(incident_summary.get("open") or 0)),
        "--unack-incident-count",
        str(int(incident_summary.get("open") or 0)),
        "--experiment-count",
        str(len(experiments)),
        "--walk-forward-count",
        str(len(walk_forward)),
        "--cycle-count",
        str(int(paper_summary.get("cycles") or 0)),
        "--reconciliation-events",
        str(reconciliation_events),
        "--reconciliation-mismatch-count",
        str(int(reconciliation_summary.get("latest_mismatch_count") or 0)),
        "--rest-fallback-count",
        str(int(data_summary.get("rest_fallbacks") or 0)),
        "--manual-intervention-count",
        str(int(incident_summary.get("total") or 0)),
        "--execution-failure-ratio",
        str(float_from_any(execution_summary.get("execution_trace_failure_ratio"), 0.0)),
        "--execution-blocked-ratio",
        str(float_from_any(execution_summary.get("execution_trace_blocked_ratio"), 0.0)),
        "--expected-cost-bps",
        str(float_from_any(execution_summary.get("execution_trace_cost_bps"), 0.0)),
        "--max-expected-cost-bps",
        str(config_float(config, "execution.max_expected_cost_bps", 50.0)),
        "--gross-exposure",
        str(float_from_any(portfolio.get("gross_exposure"), 0.0)),
        "--max-gross-exposure",
        str(config_float(config, "risk.max_gross", 0.80)),
        "--max-position-weight",
        str(max_position_weight),
        "--current-effective-leverage",
        str(current_effective_leverage),
        "--max-effective-leverage",
        str(config_float(config, "execution.derivatives.max_effective_leverage", 2.0)),
        "--last-success-age-seconds",
        str(float_from_any(readiness_summary.get("last_success_age_seconds"), -1.0)),
    ]
    try:
        result = subprocess.run(
            args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:
        return {
            "ok": False,
            "generated_at": now_iso(),
            "error": str(exc),
            "summary": {"decision": "block", "score": 0.0, "source": "cpp_exception"},
            "modes": [],
            "actions": ["修复 ops_check 调用异常后再使用生产死亡方式诊断。"],
        }
    if result.returncode != 0:
        return {
            "ok": False,
            "generated_at": now_iso(),
            "error": result.stderr.strip() or result.stdout.strip() or f"ops_check exited {result.returncode}",
            "summary": {"decision": "block", "score": 0.0, "source": "cpp_error"},
            "modes": [],
            "actions": ["修复 C++ ops_check 诊断错误。"],
        }
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "generated_at": now_iso(),
            "error": f"ops_check returned invalid JSON: {exc}",
            "summary": {"decision": "block", "score": 0.0, "source": "invalid_json"},
            "modes": [],
            "actions": ["修复 C++ ops_check JSON 输出。"],
        }
    modes = report.get("modes", []) if isinstance(report.get("modes"), list) else []
    halt = sum(1 for row in modes if isinstance(row, dict) and row.get("severity") == "halt")
    warn = sum(1 for row in modes if isinstance(row, dict) and row.get("severity") == "warn")
    ok_count = sum(1 for row in modes if isinstance(row, dict) and row.get("severity") == "ok")
    return {
        "ok": True,
        "generated_at": now_iso(),
        "source": "cpp_ops_check",
        "binary": str(binary),
        "summary": {
            "decision": report.get("decision", ""),
            "score": report.get("score", 0.0),
            "halt": halt,
            "warn": warn,
            "ok": ok_count,
            "total": len(modes),
            "paper_status": readiness_summary.get("paper_status", ""),
            "runner_running": runner_running,
            "preflight_decision": preflight.get("decision", ""),
        },
        "modes": modes,
        "actions": report.get("actions", []) if isinstance(report.get("actions"), list) else [],
        "inputs": {
            "experiments": len(experiments),
            "walk_forward": len(walk_forward),
            "cycle_count": int(paper_summary.get("cycles") or 0),
            "execution_failure_ratio": execution_summary.get("execution_trace_failure_ratio", 0.0),
            "execution_blocked_ratio": execution_summary.get("execution_trace_blocked_ratio", 0.0),
            "incident_open_count": incident_summary.get("open", 0),
        },
    }


def okx_latest_price(inst_id: str) -> Optional[float]:
    result = okx_public_request(f"/api/v5/market/ticker?{urlencode({'instId': inst_id})}")
    if not result.get("ok"):
        return None
    data = result.get("data", [])
    if not data:
        return None
    try:
        return float(data[0].get("last", "0") or 0)
    except (TypeError, ValueError):
        return None


def okx_policy_bin_path() -> Optional[Path]:
    for candidate in (OKX_POLICY_BIN, OKX_POLICY_CMAKE_BIN):
        if candidate.exists():
            return candidate
    return None


def okx_cxx_policy_payload(order: dict[str, Any], submission_context: bool) -> dict[str, Any]:
    policy_bin = okx_policy_bin_path()
    if policy_bin is None:
        return {
            "ok": False,
            "available": False,
            "error": "okx_policy executable is not built; run make okx_policy or cmake --build build --target okx_policy",
        }
    config = parse_config()
    okx_gate = okx_config()
    risk = crypto_risk_status()
    max_notional = config_float(config, "risk.max_order_notional", 50_000.0)
    # 非提交路径只校验订单语义和风控，不把“未配置 key / 下单开关关闭”
    # 混入订单规则结果；真正提交路径必须使用真实上下文。
    context_configured = bool(okx_gate.get("configured")) if submission_context else True
    context_simulated = bool(okx_gate.get("simulated")) if submission_context else True
    context_trading_enabled = bool(okx_gate.get("trading_enabled")) if submission_context else True
    inst_type = okx_order_inst_type(order)
    derivatives = inst_type in OKX_DERIVATIVE_INST_TYPES
    config_derivatives_enabled = paper_derivatives_enabled()
    max_exchange_leverage = config_float(config, "execution.derivatives.max_exchange_leverage", 3.0)
    max_effective_leverage = config_float(config, "execution.derivatives.max_effective_leverage", 2.0)
    max_unit_effective_leverage = config_float(config, "execution.derivatives.max_unit_effective_leverage", 1.0)
    effective_leverage = float_from_any(order.get("_effective_leverage", max_unit_effective_leverage), max_unit_effective_leverage)
    unit_effective_leverage = float_from_any(order.get("_unit_effective_leverage", effective_leverage), effective_leverage)
    exchange_leverage = float_from_any(order.get("_exchange_leverage", max(1.0, math.ceil(max(effective_leverage, 1.0)))), 1.0)
    args = [
        str(policy_bin),
        "--product",
        inst_type.lower() if derivatives else "spot",
        "--configured",
        "true" if context_configured else "false",
        "--simulated",
        "true" if context_simulated else "false",
        "--trading-enabled",
        "true" if context_trading_enabled else "false",
        "--kill-switch",
        "true" if risk["state"].get("kill_switch") else "false",
        "--max-order-notional",
        str(max_notional),
        "--whitelist",
        ",".join(okx_effective_whitelist_for_cxx(inst_type)),
        "--inst-id",
        str(order.get("instId", "")),
        "--td-mode",
        str(order.get("tdMode", "")),
        "--side",
        str(order.get("side", "")),
        "--ord-type",
        str(order.get("ordType", "")),
        "--px",
        str(order.get("px", "0") or "0"),
        "--sz",
        str(order.get("sz", "0") or "0"),
    ]
    if derivatives:
        args.extend(
            [
                "--inst-type",
                inst_type,
                "--pos-side",
                str(order.get("posSide", order.get("_posSide", "net")) or "net"),
                "--notional",
                str(order.get("_notional_usdt", order.get("notional", "0")) or "0"),
                "--derivatives-enabled",
                "true" if config_derivatives_enabled else "false",
                "--exchange-leverage",
                str(exchange_leverage),
                "--effective-leverage",
                str(effective_leverage),
                "--unit-effective-leverage",
                str(unit_effective_leverage),
                "--max-exchange-leverage",
                str(max_exchange_leverage),
                "--max-effective-leverage",
                str(max_effective_leverage),
                "--max-unit-effective-leverage",
                str(max_unit_effective_leverage),
                "--reduce-only",
                "true" if bool(order.get("reduceOnly", False)) else "false",
            ]
        )
    try:
        completed = subprocess.run(
            args,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        payload = json.loads(completed.stdout or "{}")
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "available": True, "error": str(exc)}
    if not isinstance(payload, dict):
        return {"ok": False, "available": True, "error": "okx_policy returned non-object JSON"}
    payload["available"] = True
    payload["exit_code"] = completed.returncode
    payload["submission_context"] = submission_context
    return payload


def okx_pre_trade_check(order: dict[str, Any], submission_context: bool = False) -> tuple[bool, str, dict[str, Any]]:
    risk = crypto_risk_status()
    cxx_policy = okx_cxx_policy_payload(order, submission_context)
    risk["cxx_policy"] = cxx_policy
    cxx_checks = cxx_policy.get("checks", []) if isinstance(cxx_policy.get("checks"), list) else []
    risk["cxx_policy_checks"] = cxx_checks
    if isinstance(cxx_policy.get("estimated_notional"), (int, float)):
        risk["estimated_order_notional"] = float(cxx_policy.get("estimated_notional", 0.0))
        risk["estimated_order_notional_method"] = "cxx_policy_px_sz"
    if cxx_policy.get("ok"):
        if not cxx_policy.get("approved"):
            failed = next((item for item in cxx_checks if not item.get("ok") and item.get("severity") == "halt"), {})
            return False, str(failed.get("message", "C++ OKX 执行门禁未通过。")), risk
    elif submission_context:
        return False, f"C++ OKX 执行门禁不可用：{cxx_policy.get('error', 'unknown error')}", risk
    elif risk["state"]["kill_switch"]:
        return False, "kill switch 已开启，禁止提交新的 OKX 模拟盘订单。", risk
    rule_checks, rules = okx_validate_order_rules(order)
    risk["order_rule_checks"] = rule_checks
    risk["instrument_rules"] = rules or {}
    if any(item.get("severity") == "halt" for item in rule_checks):
        failed = next((item for item in rule_checks if item.get("severity") == "halt"), {})
        return False, str(failed.get("message", "订单未通过 OKX 合约规则检查。")), risk
    config = parse_config()
    max_notional = config_float(config, "risk.max_order_notional", 50_000.0)
    needs_latest_price = not order.get("px") and not (
        order.get("ordType") == "market"
        and order.get("side") == "buy"
        and order.get("tgtCcy") == "quote_ccy"
    )
    latest_price = okx_latest_price(str(order.get("instId", ""))) if needs_latest_price else None
    notional, notional_method = okx_estimate_order_notional(order, latest_price)
    if notional is None:
        return False, notional_method, risk
    risk["estimated_order_notional"] = notional
    risk["estimated_order_notional_method"] = notional_method
    if latest_price is not None:
        risk["latest_price"] = latest_price
    if max_notional > 0.0 and notional > max_notional:
        return False, f"订单名义金额 {notional:.2f} 超过上限 {max_notional:.2f}。", risk
    return True, "approved", risk


def okx_order_preflight_payload(body: dict[str, Any]) -> dict[str, Any]:
    try:
        order = normalize_okx_order(body)
    except ValueError as exc:
        return {"ok": False, "approved": False, "error": str(exc), "config": okx_status()}
    allowed, message, risk = okx_pre_trade_check(order)
    okx_gate = okx_config()
    submit_ready = bool(allowed and okx_gate.get("simulated") and okx_gate.get("trading_enabled"))
    display_message = message
    if allowed and not okx_gate.get("trading_enabled"):
        display_message = "订单规则和风控通过；OKX_TRADING_ENABLED=false，当前不会提交订单。"
    if allowed and not okx_gate.get("simulated"):
        display_message = "订单规则和风控通过；OKX_SIMULATED_TRADING=false，平台仍会拒绝下单。"
    if allowed and okx_gate.get("simulated") and okx_gate.get("trading_enabled"):
        display_message = "订单规则和风控通过；最终提交前还会再次验证 OKX 模拟盘 key 环境。"
    trading_enabled = bool(okx_gate.get("trading_enabled"))
    checks = [
        okx_check("模拟盘模式", bool(okx_gate.get("simulated")), "ok" if okx_gate.get("simulated") else "halt", "OKX_SIMULATED_TRADING 必须保持 true 才能通过平台下单。"),
        okx_check(
            "下单开关",
            trading_enabled,
            "ok" if trading_enabled else "warn",
            "OKX_TRADING_ENABLED=true，允许进入模拟盘提交前最终检查。"
            if trading_enabled
            else "OKX_TRADING_ENABLED=false 时只能做预检，不会提交订单。",
        ),
        *risk.get("cxx_policy_checks", []),
        *risk.get("order_rule_checks", []),
    ]
    return {
        "ok": True,
        "approved": submit_ready,
        "risk_approved": bool(allowed),
        "message": display_message,
        "order": order,
        "checks": checks,
        "risk": risk,
        "config": okx_status(),
    }


def okx_trial_order_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    default_inst_id = (okx_effective_instruments_for_type("SWAP") or okx_instruments_for_type("SWAP") or [okx_derivative_inst_id(okx_instruments_config()[0])])[0]
    inst_id = params.get("instId", [default_inst_id])[0].upper().strip()
    if not inst_id.endswith("-SWAP") and inst_id.count("-") == 1:
        inst_id = okx_derivative_inst_id(inst_id)
    inst_type = "SWAP" if inst_id.endswith("-SWAP") else OKX_EXECUTION_INST_TYPE
    derivatives = inst_type in OKX_DERIVATIVE_INST_TYPES
    side = params.get("side", ["buy"])[0].lower().strip()
    notional = decimal_value(params.get("notional", ["5"])[0]) if params.get("notional") else Decimal("5")
    if side not in {"buy", "sell"}:
        return {"ok": False, "approved": False, "error": "side must be buy or sell", "config": okx_status()}
    if inst_id not in set(okx_effective_instruments_for_type(inst_type)):
        return {"ok": False, "approved": False, "error": f"{inst_id} 不在有效 OKX {inst_type} 合约元数据白名单内", "config": okx_status()}
    if notional is None or notional <= 0:
        notional = Decimal("5")
    risk_limit = decimal_value(parse_config().get("risk.max_order_notional", "50000"))
    if risk_limit is not None and risk_limit > 0:
        notional = min(notional, risk_limit)
    notional = max(Decimal("1"), min(notional, Decimal("25")))

    rules, rules_result = okx_instrument_rules(inst_id, inst_type)
    if not rules:
        return {
            "ok": False,
            "approved": False,
            "error": rules_result.get("error", "无法读取 OKX 合约规则。"),
            "config": okx_status(),
        }
    tick_size = decimal_value(rules.get("tick_size"))
    lot_size = decimal_value(rules.get("lot_size"))
    min_size = decimal_value(rules.get("min_size"))
    ct_val = decimal_value(rules.get("ct_val"))
    quote = okx_latest_quote(inst_id)
    reference_price = quote.get("last") or quote.get("bid") or quote.get("ask")
    if reference_price is None or reference_price <= 0:
        return {"ok": False, "approved": False, "error": "无法读取有效 ticker 价格。", "config": okx_status()}
    price = okx_maker_limit_price(side, reference_price, tick_size, inst_id)
    if price <= 0:
        return {"ok": False, "approved": False, "error": "无法生成有效挂单价格。", "config": okx_status()}
    if derivatives:
        if ct_val is None or ct_val <= 0:
            return {"ok": False, "approved": False, "error": "OKX 合约规则缺少 ctVal。", "config": okx_status()}
        size = decimal_floor_to_step(notional / (price * ct_val), lot_size)
        effective_notional = size * price * ct_val
    else:
        size = decimal_floor_to_step(notional / price, lot_size)
        effective_notional = size * price
    if size <= 0 or (min_size is not None and size < min_size):
        min_text = rules.get("min_size", "-")
        return {
            "ok": False,
            "approved": False,
            "error": f"试挂单数量 {decimal_plain(size)} 小于 minSz={min_text}，请提高名义金额。",
            "instrument_rules": rules,
            "config": okx_status(),
        }
    order = {
        "instId": inst_id,
        "tdMode": paper_derivatives_margin_mode() if derivatives else OKX_EXECUTION_TD_MODE,
        "side": side,
        "ordType": "post_only",
        "sz": decimal_plain(size),
        "px": decimal_plain(price),
    }
    if derivatives:
        pos_side = okx_position_side_for_order(side)
        order.update(
            {
                "_instType": inst_type,
                "_posSide": pos_side,
                "_notional_usdt": decimal_plain(effective_notional),
                "_ctVal": decimal_plain(ct_val or Decimal("0")),
                "_exchange_leverage": 1,
                "_effective_leverage": 1,
                "_unit_effective_leverage": 1,
            }
        )
        if pos_side != "net":
            order["posSide"] = pos_side
    allowed, message, risk = okx_pre_trade_check(order)
    submit_gate = okx_simulated_submit_gate()
    return {
        "ok": True,
        "approved": bool(allowed and submit_gate.get("ready")),
        "risk_approved": bool(allowed),
        "message": message if allowed else message,
        "notional": float(effective_notional),
        "requested_notional": float(notional),
        "order": order,
        "quote": {key: decimal_plain(value) if value is not None else "" for key, value in quote.items()},
        "instrument_rules": rules,
        "risk": risk,
        "submit_gate": submit_gate,
        "config": okx_status(),
    }


def okx_readiness_payload(body: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    body = body or {}
    public_check = okx_bool_from_body(body, "public_check", True)
    private_check = okx_bool_from_body(body, "private_check", False)
    if private_check and str(body.get("confirm", "")) != "OKX_READ_ONLY_CHECK":
        raise ValueError("OKX 只读私有预检必须带 confirm=OKX_READ_ONLY_CHECK")

    status = okx_status()
    raw_config = okx_config()
    risk = crypto_risk_status()
    effective_swap_instruments = okx_effective_instruments_for_type("SWAP")
    checks: list[dict[str, Any]] = [
        okx_check("Base URL", str(status.get("base_url", "")).startswith("https://"), "ok" if str(status.get("base_url", "")).startswith("https://") else "warn", status.get("base_url", "-")),
        okx_check("API Key", bool(status.get("key_configured")), "ok" if status.get("key_configured") else "warn", "已配置" if status.get("key_configured") else "未配置；只能使用公开行情。"),
        okx_check("Secret", bool(status.get("secret_configured")), "ok" if status.get("secret_configured") else "warn", "已配置" if status.get("secret_configured") else "未配置。"),
        okx_check("Passphrase", bool(status.get("passphrase_configured")), "ok" if status.get("passphrase_configured") else "warn", "已配置" if status.get("passphrase_configured") else "未配置。"),
        okx_check("模拟盘 Header", bool(status.get("simulated")), "ok" if status.get("simulated") else "halt", "x-simulated-trading=1" if status.get("simulated") else "未开启；平台会拒绝下单。"),
        okx_check("下单开关", not bool(status.get("trading_enabled")), "ok" if not status.get("trading_enabled") else "warn", "默认关闭，准备好后再改为 true。" if not status.get("trading_enabled") else "已打开；只能用于 OKX 模拟盘。"),
        okx_check("Kill switch", not risk["state"]["kill_switch"], "ok" if not risk["state"]["kill_switch"] else "halt", risk["state"].get("reason") or ("关闭" if not risk["state"]["kill_switch"] else "已开启")),
        okx_check("执行范围", True, "ok", "默认走 OKX SWAP/FUTURES 模拟盘，isolated/cross，limit/post_only 挂单。"),
        okx_check("合约白名单", bool(effective_swap_instruments), "ok" if effective_swap_instruments else "halt", ", ".join(effective_swap_instruments or [])),
    ]
    payload: dict[str, Any] = {
        "ok": True,
        "config": status,
        "checks": checks,
        "risk": risk,
        "network": okx_network_probe_payload(),
        "public": {},
        "private": {},
        "ready_for_private_read": bool(raw_config.get("configured")),
        "ready_for_simulated_order": bool(raw_config.get("configured") and raw_config.get("simulated") and raw_config.get("trading_enabled") and not risk["state"]["kill_switch"]),
    }

    if public_check:
        inst_id = (effective_swap_instruments or okx_instruments_for_type("SWAP") or [okx_derivative_inst_id((status.get("instruments") or OKX_DEFAULT_INSTRUMENTS)[0])])[0]
        tickers = okx_tickers_payload({"instType": ["SWAP"]})
        checks.append(okx_check("公开行情", bool(tickers.get("ok")), "ok" if tickers.get("ok") else "halt", f"tickers ok, {len(tickers.get('tickers', []))} 条" if tickers.get("ok") else tickers.get("error", "ticker 失败")))
        rules, rules_result = okx_instrument_rules(inst_id, "SWAP")
        checks.append(okx_check("合约规则读取", bool(rules), "ok" if rules else "halt", f"{inst_id} minSz={rules.get('min_size')} lotSz={rules.get('lot_size')} tickSz={rules.get('tick_size')}" if rules else rules_result.get("error", "读取失败")))
        payload["public"] = {
            "ticker_count": len(tickers.get("tickers", [])) if tickers.get("ok") else 0,
            "sample_inst_id": inst_id,
            "sample_rules": rules or {},
            "request_id": tickers.get("request_id", ""),
        }

    if private_check:
        account_config = okx_account_config_payload()
        checks.append(okx_check("账户配置读取", bool(account_config.get("ok")), "ok" if account_config.get("ok") else "halt", "已读取账户模式。" if account_config.get("ok") else account_config.get("error", "读取失败")))
        if account_config.get("environment_warning"):
            checks.append(okx_check("API 环境匹配", False, "warn", account_config["environment_warning"]))
        balance = okx_balance_payload()
        checks.append(okx_check("余额读取", bool(balance.get("ok")), "ok" if balance.get("ok") else "halt", "已读取余额。" if balance.get("ok") else balance.get("error", "读取失败")))
        if balance.get("environment_warning"):
            checks.append(okx_check("余额读取环境", False, "warn", balance["environment_warning"]))
        orders = okx_orders_payload({"instType": ["SWAP"]})
        checks.append(okx_check("当前委托读取", bool(orders.get("ok")), "ok" if orders.get("ok") else "warn", f"{len(orders.get('orders', []))} 条当前委托。" if orders.get("ok") else orders.get("error", "读取失败")))
        if orders.get("environment_warning"):
            checks.append(okx_check("委托读取环境", False, "warn", orders["environment_warning"]))
        payload["private"] = {
            "account_config": account_config.get("account_config", {}),
            "account": balance.get("account", {}),
            "open_orders_count": len(orders.get("orders", [])) if orders.get("ok") else 0,
            "used_simulated": {
                "account_config": account_config.get("used_simulated", raw_config.get("simulated")),
                "balance": balance.get("used_simulated", raw_config.get("simulated")),
                "orders": orders.get("used_simulated", raw_config.get("simulated")),
            },
            "request_ids": {
                "account_config": account_config.get("request_id", ""),
                "balance": balance.get("request_id", ""),
                "orders": orders.get("request_id", ""),
            },
        }
        used_values = payload["private"]["used_simulated"]
        if any(value != raw_config.get("simulated") for value in used_values.values()):
            payload["ready_for_simulated_order"] = False

    payload["status"] = "halt" if any(item["severity"] == "halt" for item in checks) else (
        "warn" if any(item["severity"] == "warn" for item in checks) else "ok"
    )
    payload["ok"] = payload["status"] != "halt"
    return payload


def broker_status() -> dict[str, Any]:
    okx = okx_status()
    return {
        "broker_name": PRIMARY_BROKER_NAME,
        "display_name": "OKX 欧意",
        "base_url": okx.get("base_url", ""),
        "account_id": "",
        "configured": bool(okx.get("configured")),
        "trading_enabled": bool(okx.get("trading_enabled")),
        "dry_run": True,
        "state": okx.get("state", "等待 OKX 配置"),
        "message": "当前平台唯一交易券商为 OKX/欧意；执行范围仍限制为模拟盘 SPOT/cash limit/post_only。",
        "instruments": okx.get("instruments", []),
    }


def okx_instruments_config() -> list[str]:
    raw = get_local_setting("OKX_CRYPTO_INSTRUMENTS", ",".join(OKX_DEFAULT_INSTRUMENTS))
    values = [item.strip().upper() for item in raw.split(",") if item.strip()]
    return values or OKX_DEFAULT_INSTRUMENTS


def okx_base_urls_config() -> list[str]:
    raw = get_local_setting("OKX_BASE_URLS", "")
    if not raw:
        raw = get_local_setting("OKX_BASE_URL", OKX_BASE_URL)
    values: list[str] = []
    for item in re.split(r"[\n,]+", raw):
        value = item.strip().rstrip("/")
        if not value:
            continue
        if value in OKX_BLOCKED_BASE_URLS:
            continue
        if not value.startswith("https://"):
            continue
        if value not in values:
            values.append(value)
    return values or [OKX_BASE_URL]


# GAP-021: Token bucket 速率限制
_OKX_RATE_LIMIT_TOKENS = 20.0       # 桶容量
_OKX_RATE_LIMIT_REFILL = 10.0        # 每秒补充令牌数
_OKX_RATE_LIMIT_LAST = time.monotonic()

def _okx_rate_limit_wait() -> None:
    """Token bucket: 确保请求不超出 OKX 频率限制."""
    global _OKX_RATE_LIMIT_TOKENS, _OKX_RATE_LIMIT_LAST
    now = time.monotonic()
    elapsed = now - _OKX_RATE_LIMIT_LAST
    _OKX_RATE_LIMIT_TOKENS = min(20.0, _OKX_RATE_LIMIT_TOKENS + elapsed * _OKX_RATE_LIMIT_REFILL)
    _OKX_RATE_LIMIT_LAST = now
    if _OKX_RATE_LIMIT_TOKENS < 1.0:
        sleep_time = (1.0 - _OKX_RATE_LIMIT_TOKENS) / _OKX_RATE_LIMIT_REFILL
        time.sleep(sleep_time)
        _OKX_RATE_LIMIT_TOKENS = 0.0
    else:
        _OKX_RATE_LIMIT_TOKENS -= 1.0


def okx_request_timeout_seconds() -> float:
    value = decimal_value(get_local_setting("OKX_REQUEST_TIMEOUT_SECONDS", "4"))
    if value is None:
        return 4.0
    return float(max(2.0, min(float(value), 20.0)))


def okx_config() -> dict[str, Any]:
    api_key = get_local_setting("OKX_API_KEY", "")
    secret_key = get_local_setting("OKX_SECRET_KEY", "")
    passphrase = get_local_setting("OKX_PASSPHRASE", "")
    base_urls = okx_base_urls_config()
    base_url = base_urls[0]
    simulated = parse_bool_setting(get_local_setting("OKX_SIMULATED_TRADING", "true"), True)
    trading_enabled = parse_bool_setting(get_local_setting("OKX_TRADING_ENABLED", "false"), False)
    configured = bool(api_key and secret_key and passphrase and base_url)
    if not configured:
        state = "未配置"
        message = "公开行情可用；设置 OKX_API_KEY、OKX_SECRET_KEY、OKX_PASSPHRASE 后可读取账户。"
    elif simulated and trading_enabled:
        state = "已配置，模拟盘下单已打开"
        message = "仅允许 OKX simulated trading header 下的模拟盘订单。"
    elif simulated:
        state = "已配置，只读模拟盘"
        message = "可读取账户和订单；模拟盘下单接口默认关闭。"
    else:
        state = "已配置，只读实盘"
        message = "当前不会提交 OKX 实盘订单；请保持 OKX_TRADING_ENABLED=false。"
    return {
        "broker_name": "okx",
        "base_url": base_url,
        "base_urls": base_urls,
        "request_timeout_seconds": okx_request_timeout_seconds(),
        "api_key": api_key,
        "secret_key": secret_key,
        "passphrase": passphrase,
        "masked_api_key": mask_value(api_key),
        "key_configured": bool(api_key),
        "secret_configured": bool(secret_key),
        "passphrase_configured": bool(passphrase),
        "configured": configured,
        "simulated": simulated,
        "trading_enabled": trading_enabled,
        "instruments": okx_instruments_config(),
        "key_source": local_setting_source("OKX_API_KEY"),
        "secret_source": local_setting_source("OKX_SECRET_KEY"),
        "passphrase_source": local_setting_source("OKX_PASSPHRASE"),
        "state": state,
        "message": message,
    }


def okx_status() -> dict[str, Any]:
    config = okx_config()
    return {
        "broker_name": config["broker_name"],
        "base_url": config["base_url"],
        "base_urls": config["base_urls"],
        "request_timeout_seconds": config["request_timeout_seconds"],
        "api_key": config["masked_api_key"],
        "key_configured": config["key_configured"],
        "secret_configured": config["secret_configured"],
        "passphrase_configured": config["passphrase_configured"],
        "configured": config["configured"],
        "simulated": config["simulated"],
        "trading_enabled": config["trading_enabled"],
        "instruments": config["instruments"],
        "key_source": config["key_source"],
        "secret_source": config["secret_source"],
        "passphrase_source": config["passphrase_source"],
        "state": config["state"],
        "message": config["message"],
    }

def save_okx_api_key(body: dict[str, Any]) -> dict[str, Any]:
    """保存 OKX API 密钥到 config/api_key.config"""
    keys = {
        "OKX_API_KEY": str(body.get("okx_api_key", "")).strip(),
        "OKX_SECRET_KEY": str(body.get("okx_secret_key", "")).strip(),
        "OKX_PASSPHRASE": str(body.get("okx_passphrase", "")).strip(),
    }
    # 只更新非空值
    current = parse_key_value_file(API_KEY_CONFIG)
    for k, v in keys.items():
        if v:
            current[k] = v
    # 写回文件
    lines = []
    for k, v in current.items():
        lines.append(f"{k}={v}")
    API_KEY_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    API_KEY_CONFIG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True, "saved": [k for k, v in keys.items() if v]}


def okx_public_ws_url(environment: str = "auto") -> tuple[str, str]:
    """Return the official OKX public WebSocket endpoint.

    The platform keeps this public-data only.  Trading/order state still goes
    through the existing guarded REST adapter, so enabling the stream cannot
    submit or cancel orders.
    """
    mode = str(environment or "auto").strip().lower()
    if mode in {"sim", "simulated", "paper"}:
        return OKX_PUBLIC_WS_SIMULATED_URL, "simulated"
    if mode in {"prod", "production", "real"}:
        return OKX_PUBLIC_WS_URL, "production"
    return (OKX_PUBLIC_WS_SIMULATED_URL, "simulated") if okx_config().get("simulated") else (OKX_PUBLIC_WS_URL, "production")


def market_stream_thread_alive() -> bool:
    return MARKET_STREAM_THREAD is not None and MARKET_STREAM_THREAD.is_alive()


def market_stream_config_from_body(body: dict[str, Any]) -> dict[str, Any]:
    raw_instruments = body.get("instIds", body.get("instruments", body.get("instrument", "")))
    instruments = (
        normalize_okx_inst_ids(
            raw_instruments,
            max_items=OKX_MAX_RUNTIME_INSTRUMENTS,
            limit_label="OKX 实时行情订阅",
        )
        if str(raw_instruments).strip()
        else okx_instruments_config()
    )
    raw_channels = body.get("channels", ["trades", "tickers", "books5"])
    if isinstance(raw_channels, str):
        channel_values = [item.strip() for item in re.split(r"[\s,]+", raw_channels) if item.strip()]
    else:
        channel_values = [str(item).strip() for item in raw_channels if str(item).strip()]
    channels = [item for item in channel_values if item in MARKET_STREAM_ALLOWED_CHANNELS]
    if not channels:
        channels = ["trades"]
    url, environment = okx_public_ws_url(str(body.get("environment", body.get("env", "auto"))))
    return {
        "url": url,
        "environment": environment,
        "instruments": instruments,
        "channels": channels,
    }


def ws_read_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionError("websocket closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def ws_connect(url: str, timeout: float = 10.0) -> socket.socket:
    """Open a minimal RFC6455 WebSocket connection with Python stdlib only."""
    parsed = urlparse(url)
    if parsed.scheme != "wss" or not parsed.hostname:
        raise ValueError("OKX WebSocket URL must be wss://")
    port = parsed.port or 443
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    raw_sock = socket.create_connection((parsed.hostname, port), timeout=timeout)
    context = ssl.create_default_context()
    sock = context.wrap_socket(raw_sock, server_hostname=parsed.hostname)
    sock.settimeout(timeout)
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    host_header = parsed.hostname if port == 443 else f"{parsed.hostname}:{port}"
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host_header}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "User-Agent: KaTradeOKXPublicStream/0.1\r\n"
        "\r\n"
    ).encode("ascii")
    sock.sendall(request)
    response = b""
    while b"\r\n\r\n" not in response:
        response += ws_read_exact(sock, 1)
        if len(response) > 8192:
            raise ConnectionError("websocket handshake response too large")
    header_text = response.decode("iso-8859-1", "replace")
    if " 101 " not in header_text.split("\r\n", 1)[0]:
        raise ConnectionError(header_text.split("\r\n", 1)[0])
    accept = ""
    for line in header_text.split("\r\n")[1:]:
        if line.lower().startswith("sec-websocket-accept:"):
            accept = line.split(":", 1)[1].strip()
            break
    expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()).decode("ascii")
    if accept != expected:
        raise ConnectionError("websocket handshake accept mismatch")
    sock.settimeout(1.0)
    return sock


def ws_send_frame(sock: socket.socket, opcode: int, payload: bytes = b"") -> None:
    """Send a masked client frame.  OKX accepts plain text JSON messages."""
    first = 0x80 | (opcode & 0x0F)
    length = len(payload)
    if length < 126:
        header = struct.pack("!BB", first, 0x80 | length)
    elif length < (1 << 16):
        header = struct.pack("!BBH", first, 0x80 | 126, length)
    else:
        header = struct.pack("!BBQ", first, 0x80 | 127, length)
    mask = os.urandom(4)
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    sock.sendall(header + mask + masked)


def ws_send_text(sock: socket.socket, text: str) -> None:
    ws_send_frame(sock, 0x1, text.encode("utf-8"))


def ws_recv_frame(sock: socket.socket) -> tuple[int, bytes]:
    header = ws_read_exact(sock, 2)
    opcode = header[0] & 0x0F
    masked = bool(header[1] & 0x80)
    length = header[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", ws_read_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", ws_read_exact(sock, 8))[0]
    mask = ws_read_exact(sock, 4) if masked else b""
    payload = ws_read_exact(sock, length) if length else b""
    if masked:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return opcode, payload


def normalize_okx_trade_item(inst_id: str, item: dict[str, Any]) -> Optional[dict[str, Any]]:
    trade_id = str(item.get("tradeId", "")).strip()
    timestamp = int(item.get("ts", 0) or 0)
    price = decimal_value(item.get("px"))
    size = decimal_value(item.get("sz"))
    if not trade_id or timestamp <= 0 or price is None or size is None or size <= 0:
        return None
    return {
        "inst_id": inst_id,
        "trade_id": trade_id,
        "t": timestamp,
        "price": float(price),
        "size": float(size),
        "side": str(item.get("side", "")).lower(),
    }


def normalize_okx_book5_item(inst_id: str, item: dict[str, Any]) -> dict[str, Any]:
    def levels(name: str) -> list[dict[str, Any]]:
        rows = []
        for level in item.get(name, []) or []:
            if not isinstance(level, list) or len(level) < 2:
                continue
            rows.append(
                {
                    "price": float_from_any(level[0]),
                    "size": float_from_any(level[1]),
                    "orders": int(float_from_any(level[3] if len(level) > 3 else 0, 0.0)),
                }
            )
        return rows

    return {
        "inst_id": inst_id,
        "t": int(item.get("ts", 0) or 0),
        "bids": levels("bids"),
        "asks": levels("asks"),
    }


def market_stream_snapshot() -> dict[str, Any]:
    with MARKET_STREAM_LOCK:
        recent_trades = {
            inst: list(rows[-100:])
            for inst, rows in (MARKET_STREAM_STATE.get("recent_trades", {}) or {}).items()
            if isinstance(rows, list)
        }
        return {
            **{key: value for key, value in MARKET_STREAM_STATE.items() if key not in {"recent_trades", "tickers", "books5"}},
            "running": market_stream_thread_alive(),
            "recent_trades": recent_trades,
            "tickers": dict(MARKET_STREAM_STATE.get("tickers", {}) or {}),
            "books5": dict(MARKET_STREAM_STATE.get("books5", {}) or {}),
            "journal_path": str(MARKET_STREAM_JOURNAL_PATH),
        }


def compact_market_stream_for_response(stream: dict[str, Any]) -> dict[str, Any]:
    """Return a light public stream snapshot for frequently-polled UI panels."""
    if not isinstance(stream, dict):
        return {}
    recent = stream.get("recent_trades", {}) if isinstance(stream.get("recent_trades"), dict) else {}
    tickers = stream.get("tickers", {}) if isinstance(stream.get("tickers"), dict) else {}
    books = stream.get("books5", {}) if isinstance(stream.get("books5"), dict) else {}
    recent_counts = {
        str(inst): len(rows)
        for inst, rows in recent.items()
        if isinstance(rows, list)
    }
    response = {
        key: copy.deepcopy(value)
        for key, value in stream.items()
        if key not in {"recent_trades", "tickers", "books5"}
    }
    response["recent_trade_counts"] = recent_counts
    response["recent_trade_count"] = sum(recent_counts.values())
    response["ticker_count"] = len(tickers)
    response["book_count"] = len(books)
    response["ticker_instruments"] = sorted(str(inst) for inst in tickers.keys())
    response["book_instruments"] = sorted(str(inst) for inst in books.keys())
    return response


def append_market_stream_journal(event: dict[str, Any]) -> None:
    MARKET_STREAM_DIR.mkdir(parents=True, exist_ok=True)
    with MARKET_STREAM_JOURNAL_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def market_stream_record(channel: str, arg: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    now_text = now_iso()
    inst_id = str(arg.get("instId", "")).upper().strip()
    event = {
        "ts": int(time.time() * 1000),
        "received_at": now_text,
        "channel": channel,
        "inst_id": inst_id,
        "rows": rows,
    }
    with MARKET_STREAM_LOCK:
        MARKET_STREAM_STATE["messages"] = int(MARKET_STREAM_STATE.get("messages", 0) or 0) + 1
        MARKET_STREAM_STATE["events"] = int(MARKET_STREAM_STATE.get("events", 0) or 0) + len(rows)
        MARKET_STREAM_STATE["last_message_at"] = now_text
        if channel == "trades":
            MARKET_STREAM_STATE["last_trade_at"] = now_text
            recent = MARKET_STREAM_STATE.setdefault("recent_trades", {}).setdefault(inst_id, [])
            recent.extend(rows)
            recent.sort(key=lambda row: (int(row.get("t", 0)), str(row.get("trade_id", ""))))
            MARKET_STREAM_STATE["recent_trades"][inst_id] = recent[-2000:]
        elif channel == "tickers" and rows:
            MARKET_STREAM_STATE["last_ticker_at"] = now_text
            MARKET_STREAM_STATE.setdefault("tickers", {})[inst_id] = rows[-1]
        elif channel == "books5" and rows:
            MARKET_STREAM_STATE["last_books_at"] = now_text
            MARKET_STREAM_STATE.setdefault("books5", {})[inst_id] = rows[-1]
    append_market_stream_journal(event)
    summary: dict[str, Any] = {"channel": channel, "inst_id": inst_id, "row_count": len(rows)}
    if channel == "trades" and rows:
        latest = rows[-1]
        summary.update(
            {
                "trade_id": latest.get("trade_id", ""),
                "price": latest.get("price"),
                "size": latest.get("size"),
                "side": latest.get("side", ""),
                "exchange_ts": latest.get("t", 0),
            }
        )
        append_platform_event_throttled(
            "market.trades",
            "okx_ws",
            summary,
            throttle_key=f"market.trades:{inst_id}",
            min_interval_seconds=1.0,
            message=f"{inst_id} WS 成交 {len(rows)} 笔，最新 {latest.get('price')}",
        )
    elif channel == "tickers" and rows:
        latest = rows[-1]
        summary.update({"last": latest.get("last"), "bid": latest.get("bid"), "ask": latest.get("ask"), "timestamp": latest.get("timestamp")})
        append_platform_event_throttled(
            "market.ticker",
            "okx_ws",
            summary,
            throttle_key=f"market.ticker:{inst_id}",
            min_interval_seconds=5.0,
            message=f"{inst_id} ticker {latest.get('last')}",
        )
    elif channel == "books5" and rows:
        latest = rows[-1]
        bid = (latest.get("bids") or [{}])[0]
        ask = (latest.get("asks") or [{}])[0]
        summary.update({"best_bid": bid.get("price"), "best_ask": ask.get("price"), "book_ts": latest.get("t", 0)})
        append_platform_event_throttled(
            "market.book5",
            "okx_ws",
            summary,
            throttle_key=f"market.book5:{inst_id}",
            min_interval_seconds=5.0,
            message=f"{inst_id} book5 {bid.get('price')} / {ask.get('price')}",
        )


def market_stream_handle_message(message: str) -> None:
    if message == "pong":
        with MARKET_STREAM_LOCK:
            MARKET_STREAM_STATE["last_message_at"] = now_iso()
        return
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return
    if not isinstance(payload, dict):
        return
    now_text = now_iso()
    event_name = str(payload.get("event", ""))
    if event_name:
        with MARKET_STREAM_LOCK:
            MARKET_STREAM_STATE["last_message_at"] = now_text
            if event_name == "subscribe":
                sub = payload.get("arg", {})
                if sub not in MARKET_STREAM_STATE.get("subscriptions", []):
                    MARKET_STREAM_STATE.setdefault("subscriptions", []).append(sub)
            elif event_name == "error":
                MARKET_STREAM_STATE["last_error"] = str(payload.get("msg", "OKX stream error"))
        append_market_stream_journal({"ts": int(time.time() * 1000), "received_at": now_text, "event": event_name, "payload": payload})
        return
    arg = payload.get("arg", {}) if isinstance(payload.get("arg"), dict) else {}
    channel = str(arg.get("channel", ""))
    inst_id = str(arg.get("instId", "")).upper().strip()
    data = payload.get("data", [])
    if channel not in MARKET_STREAM_ALLOWED_CHANNELS or not inst_id or not isinstance(data, list):
        return
    rows: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if channel == "trades":
            trade = normalize_okx_trade_item(inst_id, item)
            if trade:
                rows.append(trade)
        elif channel == "tickers":
            rows.append(sanitize_okx_ticker(item))
        elif channel == "books5":
            rows.append(normalize_okx_book5_item(inst_id, item))
    if rows:
        market_stream_record(channel, arg, rows)


def market_stream_worker(config: dict[str, Any]) -> None:
    url = str(config.get("url", OKX_PUBLIC_WS_URL))
    instruments = [str(item).upper().strip() for item in config.get("instruments", []) if str(item).strip()]
    channels = [str(item) for item in config.get("channels", []) if str(item) in MARKET_STREAM_ALLOWED_CHANNELS]
    args = [{"channel": channel, "instId": inst_id} for inst_id in instruments for channel in channels]
    backoff = 1.0
    with MARKET_STREAM_LOCK:
        MARKET_STREAM_STATE.update(
            {
                "status": "connecting",
                "running": True,
                "url": url,
                "environment": config.get("environment", ""),
                "started_at": now_iso(),
                "stopped_at": "",
                "last_message_at": "",
                "last_trade_at": "",
                "last_ticker_at": "",
                "last_books_at": "",
                "last_error": "",
                "messages": 0,
                "events": 0,
                "subscriptions": [],
                "channels": channels,
                "instruments": instruments,
                "recent_trades": {},
                "tickers": {},
                "books5": {},
            }
        )
    while not MARKET_STREAM_STOP_EVENT.is_set():
        sock: Optional[socket.socket] = None
        try:
            sock = ws_connect(url, timeout=10.0)
            backoff = 1.0
            with MARKET_STREAM_LOCK:
                MARKET_STREAM_STATE["status"] = "subscribing"
                MARKET_STREAM_STATE["last_error"] = ""
            ws_send_text(sock, json.dumps({"op": "subscribe", "args": args}, separators=(",", ":")))
            last_ping = time.monotonic()
            with MARKET_STREAM_LOCK:
                MARKET_STREAM_STATE["status"] = "running"
            while not MARKET_STREAM_STOP_EVENT.is_set():
                try:
                    opcode, payload = ws_recv_frame(sock)
                except socket.timeout:
                    if time.monotonic() - last_ping >= 20.0:
                        ws_send_text(sock, "ping")
                        last_ping = time.monotonic()
                    continue
                if opcode == 0x8:
                    raise ConnectionError("websocket close frame")
                if opcode == 0x9:
                    ws_send_frame(sock, 0xA, payload)
                    continue
                if opcode == 0xA:
                    continue
                if opcode != 0x1:
                    continue
                text = payload.decode("utf-8", "replace")
                if text == "ping":
                    ws_send_text(sock, "pong")
                    continue
                market_stream_handle_message(text)
        except Exception as exc:
            with MARKET_STREAM_LOCK:
                MARKET_STREAM_STATE["status"] = "reconnecting" if not MARKET_STREAM_STOP_EVENT.is_set() else "stopping"
                MARKET_STREAM_STATE["last_error"] = str(exc)
                MARKET_STREAM_STATE["reconnects"] = int(MARKET_STREAM_STATE.get("reconnects", 0) or 0) + 1
            if not MARKET_STREAM_STOP_EVENT.is_set():
                append_platform_event(
                    "market.stream_error",
                    "okx_ws",
                    {"url": url, "error": str(exc), "reconnects": MARKET_STREAM_STATE.get("reconnects", 0)},
                    severity="warn",
                    message=f"OKX WS 行情流异常：{exc}",
                )
            if MARKET_STREAM_STOP_EVENT.wait(backoff):
                break
            backoff = min(backoff * 2.0, 30.0)
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
    with MARKET_STREAM_LOCK:
        MARKET_STREAM_STATE["status"] = "stopped"
        MARKET_STREAM_STATE["running"] = False
        MARKET_STREAM_STATE["stopped_at"] = now_iso()


def market_stream_start_payload(body: dict[str, Any]) -> dict[str, Any]:
    global MARKET_STREAM_THREAD
    config = market_stream_config_from_body(body)
    if market_stream_thread_alive():
        return {"ok": True, "message": "OKX 行情流已经运行", "stream": market_stream_snapshot()}
    MARKET_STREAM_STOP_EVENT.clear()
    MARKET_STREAM_THREAD = threading.Thread(target=market_stream_worker, args=(config,), name="okx-public-stream", daemon=True)
    MARKET_STREAM_THREAD.start()
    append_platform_event(
        "market.stream_started",
        "platform",
        {"environment": config.get("environment"), "url": config.get("url"), "instruments": config.get("instruments"), "channels": config.get("channels")},
        message=f"OKX 公共行情流启动：{','.join(config.get('instruments', []))}",
    )
    return {"ok": True, "message": "OKX 公共行情流已启动", "stream": market_stream_snapshot()}


def market_stream_stop_payload(body: dict[str, Any]) -> dict[str, Any]:
    del body
    MARKET_STREAM_STOP_EVENT.set()
    thread = MARKET_STREAM_THREAD
    if thread is not None and thread.is_alive():
        thread.join(timeout=2.0)
    append_platform_event("market.stream_stopped", "platform", {}, message="OKX 公共行情流停止")
    return {"ok": True, "message": "OKX 公共行情流已停止", "stream": market_stream_snapshot()}


def market_stream_trades_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    inst_id = params.get("instId", [okx_instruments_config()[0]])[0].upper().strip()
    limit = bounded_int(params.get("limit", ["100"])[0], 100, 1, 2000)
    with MARKET_STREAM_LOCK:
        rows = list((MARKET_STREAM_STATE.get("recent_trades", {}) or {}).get(inst_id, [])[-limit:])
        status = str(MARKET_STREAM_STATE.get("status", "stopped"))
        last_trade_at = str(MARKET_STREAM_STATE.get("last_trade_at", ""))
    age = age_seconds_from_text(last_trade_at)
    return {
        "ok": True,
        "source": "stream",
        "inst_id": inst_id,
        "trades": rows,
        "fresh": age is not None and age <= 10.0,
        "last_trade_at": last_trade_at,
        "last_trade_age_seconds": age,
        "stream_status": status,
        "config": okx_status(),
    }


def okx_bool_from_body(body: dict[str, Any], key: str, default: bool) -> bool:
    value = body.get(key, default)
    if isinstance(value, bool):
        return value
    return parse_bool_setting(str(value), default)


def save_okx_local_config(body: dict[str, Any]) -> dict[str, Any]:
    if str(body.get("confirm", "")) != "SAVE_OKX_LOCAL_CONFIG":
        raise ValueError("保存 OKX 本地配置必须带 confirm=SAVE_OKX_LOCAL_CONFIG")

    updates: dict[str, str] = {}
    base_url = str(body.get("base_url", body.get("baseUrl", ""))).strip().rstrip("/")
    base_urls_raw = str(body.get("base_urls", body.get("baseUrls", ""))).strip()
    base_urls: list[str] = []
    if base_urls_raw:
        for item in re.split(r"[\n,]+", base_urls_raw):
            value = item.strip().rstrip("/")
            if not value:
                continue
            if value in OKX_BLOCKED_BASE_URLS:
                continue
            if not value.startswith("https://"):
                raise ValueError("OKX_BASE_URLS 必须使用 https://")
            if value not in base_urls:
                base_urls.append(value)
        if not base_urls:
            raise ValueError("OKX_BASE_URLS 不能为空")
        updates["OKX_BASE_URLS"] = ",".join(base_urls)
        updates["OKX_BASE_URL"] = base_urls[0]
    if base_url:
        if not base_url.startswith("https://"):
            raise ValueError("OKX_BASE_URL 必须使用 https://")
        if base_url in OKX_BLOCKED_BASE_URLS:
            raise ValueError("aws.okx.com 已停止服务，请使用 https://www.okx.com")
        if "OKX_BASE_URLS" not in updates:
            updates["OKX_BASE_URL"] = base_url

    timeout_value = str(body.get("request_timeout_seconds", body.get("requestTimeoutSeconds", ""))).strip()
    if timeout_value:
        timeout = decimal_value(timeout_value)
        if timeout is None:
            raise ValueError("OKX_REQUEST_TIMEOUT_SECONDS 必须是数字")
        updates["OKX_REQUEST_TIMEOUT_SECONDS"] = str(max(2.0, min(float(timeout), 20.0)))

    for source_key, target_key in [
        ("api_key", "OKX_API_KEY"),
        ("secret_key", "OKX_SECRET_KEY"),
        ("passphrase", "OKX_PASSPHRASE"),
    ]:
        value = str(body.get(source_key, "")).strip()
        if value:
            updates[target_key] = value

    instruments_raw = body.get("instruments", "")
    if str(instruments_raw).strip():
        updates["OKX_CRYPTO_INSTRUMENTS"] = ",".join(
            normalize_okx_inst_ids(
                instruments_raw,
                max_items=OKX_MAX_RUNTIME_INSTRUMENTS,
                limit_label="OKX 使用标的配置",
            )
        )

    simulated = okx_bool_from_body(body, "simulated", True)
    trading_enabled = okx_bool_from_body(body, "trading_enabled", False)
    if trading_enabled and not simulated:
        raise ValueError("平台只允许在 OKX_SIMULATED_TRADING=true 时打开 OKX_TRADING_ENABLED")
    if trading_enabled and str(body.get("trading_confirm", "")) != "ENABLE_OKX_SIMULATED_TRADING":
        raise ValueError("打开 OKX 模拟盘下单必须带 trading_confirm=ENABLE_OKX_SIMULATED_TRADING")
    updates["OKX_SIMULATED_TRADING"] = "true" if simulated else "false"
    updates["OKX_TRADING_ENABLED"] = "true" if trading_enabled else "false"

    write_key_value_file_updates(API_KEY_CONFIG, updates)
    status = okx_status()
    append_okx_audit(
        "config_saved",
        {
            "ok": True,
            "updates": {
                key: (mask_value(value) if key in {"OKX_API_KEY", "OKX_SECRET_KEY", "OKX_PASSPHRASE"} else value)
                for key, value in updates.items()
            },
            "config": status,
        },
    )
    return {"ok": True, "config": status, "audit": read_okx_audit(20)}


def okx_signature(secret_key: str, timestamp: str, method: str, request_path: str, body_text: str) -> str:
    prehash = f"{timestamp}{method.upper()}{request_path}{body_text}"
    digest = hmac.new(secret_key.encode("utf-8"), prehash.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def okx_data_error_rows(body: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in body.get("data", []) if isinstance(body.get("data"), list) else []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("sCode", "") or "")
        message = str(item.get("sMsg", "") or "")
        if code and code != "0" or message:
            rows.append(
                {
                    "sCode": code,
                    "sMsg": message,
                    "ordId": item.get("ordId", ""),
                    "clOrdId": item.get("clOrdId", ""),
                    "tag": item.get("tag", ""),
                }
            )
    return rows


def okx_error_summary(result: dict[str, Any]) -> dict[str, Any]:
    body = result.get("body", {}) if isinstance(result.get("body"), dict) else {}
    data_errors = result.get("data_errors", [])
    if not isinstance(data_errors, list):
        data_errors = okx_data_error_rows(body)
    first = data_errors[0] if data_errors and isinstance(data_errors[0], dict) else {}
    data = result.get("data", []) if isinstance(result.get("data"), list) else []
    if not first and data and isinstance(data[0], dict):
        item = data[0]
        first = {
            "sCode": str(item.get("sCode", "") or ""),
            "sMsg": str(item.get("sMsg", "") or ""),
            "ordId": item.get("ordId", ""),
            "clOrdId": item.get("clOrdId", ""),
        }
    return {
        "status_code": result.get("status_code", 0),
        "base_url": result.get("base_url", ""),
        "request_id": result.get("request_id", ""),
        "okx_code": result.get("okx_code", body.get("code", "")),
        "okx_msg": result.get("okx_msg", body.get("msg", "")),
        "s_code": first.get("sCode", ""),
        "s_msg": first.get("sMsg", ""),
        "error": result.get("error", ""),
        "error_type": result.get("error_type", ""),
        "fallback_errors": result.get("fallback_errors", []),
        "data_errors": data_errors[:10],
    }


def okx_compact_raw_body(result: dict[str, Any]) -> dict[str, Any]:
    body = result.get("body", {}) if isinstance(result.get("body"), dict) else {}
    if not body:
        return {}
    return {
        "code": body.get("code", ""),
        "msg": body.get("msg", ""),
        "data": body.get("data", [])[:5] if isinstance(body.get("data"), list) else body.get("data", []),
    }


def okx_reconcile_positions() -> dict[str, Any]:
    """GAP-023: 对账 paper 本地仓位与 OKX 实际仓位，记录差异."""
    try:
        # 获取 paper 本地仓位
        paper_state = read_paper_state()
        live = paper_state.get("live", {}) if isinstance(paper_state.get("live"), dict) else {}
        paper_positions: dict[str, float] = {}
        for pos in (live.get("positions", []) or []):
            if not isinstance(pos, dict):
                continue
            inst = pos.get("instrument", {}) if isinstance(pos.get("instrument"), dict) else {}
            symbol = str(inst.get("symbol", ""))
            exchange = str(inst.get("exchange", ""))
            if not symbol:
                continue
            key = f"{symbol}-USDT-SWAP" if exchange == "OKX" else symbol
            qty = float(pos.get("quantity", 0) or 0)
            paper_positions[key] = paper_positions.get(key, 0.0) + qty

        # 获取 OKX 实际仓位
        result = okx_private_read_request("/api/v5/account/positions")
        okx_positions: dict[str, float] = {}
        if result.get("ok"):
            for p in (result.get("data", []) or []):
                if not isinstance(p, dict):
                    continue
                inst_id = str(p.get("instId", ""))
                pos_qty = float(p.get("pos", 0) or 0)
                pos_side = str(p.get("posSide", "") or "").lower()
                if pos_side == "short":
                    pos_qty = -pos_qty
                elif pos_side == "net":
                    pos_qty = float(p.get("pos", 0) or 0)
                okx_positions[inst_id] = okx_positions.get(inst_id, 0.0) + pos_qty

        # 比对
        all_keys = set(paper_positions.keys()) | set(okx_positions.keys())
        diffs = []
        for key in sorted(all_keys):
            paper_qty = paper_positions.get(key, 0.0)
            okx_qty = okx_positions.get(key, 0.0)
            diff = abs(paper_qty - okx_qty)
            if diff > 1e-6:
                diffs.append({
                    "inst_id": key,
                    "paper_qty": paper_qty,
                    "okx_qty": okx_qty,
                    "diff": paper_qty - okx_qty,
                })

        # 写入对账日志
        entry = {
            "at": now_iso(),
            "ok": len(diffs) == 0,
            "paper_count": len(paper_positions),
            "okx_count": len(okx_positions),
            "diff_count": len(diffs),
            "diffs": diffs[:20],
        }
        RECONCILIATION_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RECONCILIATION_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")

        if diffs:
            append_platform_event(
                "reconciliation_diff",
                "okx",
                {"diffs": len(diffs), "detail": diffs[:5]},
                severity="warn" if len(diffs) <= 2 else "error",
                message=f"仓位对账发现 {len(diffs)} 处差异",
            )
        return entry
    except Exception as exc:
        return {"ok": False, "error": str(exc), "at": now_iso()}


def okx_funding_rate_map() -> dict[str, dict[str, Any]]:
    """拉取所有永续合约的当前资金费率 (GAP-010)."""
    funding_map: dict[str, dict[str, Any]] = {}
    try:
        # 批量获取所有 SWAP 的资金费率
        result = okx_request("GET", "/api/v5/public/funding-rate", auth=False)
        if result.get("ok"):
            for item in (result.get("data", []) or []):
                if not isinstance(item, dict):
                    continue
                inst_id = str(item.get("instId", ""))
                if not inst_id:
                    continue
                funding_map[inst_id] = {
                    "funding_rate": str(item.get("fundingRate", "")),
                    "funding_time": str(item.get("fundingTime", "")),
                    "next_funding_rate": str(item.get("nextFundingRate", "")),
                    "next_funding_time": str(item.get("nextFundingTime", "")),
                }
    except Exception:
        pass  # 资金费率获取失败不阻塞持仓查询
    return funding_map


def okx_request(
    method: str,
    path: str,
    payload: Optional[dict[str, Any]] = None,
    auth: bool = False,
    *,
    allow_fallback: Optional[bool] = None,
    simulated_override: Optional[bool] = None,
) -> dict[str, Any]:
    _okx_rate_limit_wait()  # GAP-021: 令牌桶限流
    config = okx_config()
    if auth and not config["configured"]:
        return {
            "ok": False,
            "status_code": 0,
            "error": config["message"],
            "config": okx_status(),
        }
    method_upper = method.upper()
    if allow_fallback is None:
        allow_fallback = method_upper == "GET"
    body_text = ""
    data = None
    if payload is not None:
        body_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        data = body_text.encode("utf-8")
    base_urls = config["base_urls"] if allow_fallback else config["base_urls"][:1]
    errors: list[dict[str, Any]] = []
    timeout_seconds = float(config.get("request_timeout_seconds", 4.0))
    for base_url in base_urls:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "KaTradeLocalOKXAdapter/0.1",
        }
        simulated_header = config["simulated"] if simulated_override is None else simulated_override
        if simulated_header:
            headers["x-simulated-trading"] = "1"
        if auth:
            timestamp = now_iso_millis()
            headers.update(
                {
                    "OK-ACCESS-KEY": config["api_key"],
                    "OK-ACCESS-SIGN": okx_signature(config["secret_key"], timestamp, method_upper, path, body_text),
                    "OK-ACCESS-TIMESTAMP": timestamp,
                    "OK-ACCESS-PASSPHRASE": config["passphrase"],
                }
            )
        request = urllib.request.Request(
            f"{base_url}{path}",
            data=data,
            method=method_upper,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                text = response.read().decode("utf-8")
                body = json.loads(text) if text else {}
                ok = str(body.get("code", "0")) == "0"
                data_errors = okx_data_error_rows(body)
                return {
                    "ok": ok,
                    "status_code": response.status,
                    "base_url": base_url,
                    "request_id": response.headers.get("OK-Request-ID", ""),
                    "error": "" if ok else str(body.get("msg", "OKX API error")),
                    "okx_code": str(body.get("code", "")),
                    "okx_msg": str(body.get("msg", "")),
                    "data_errors": data_errors,
                    "data": body.get("data", []),
                    "body": body,
                    "config": okx_status(),
                }
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", "replace")
            try:
                body = json.loads(text) if text else {}
            except json.JSONDecodeError:
                body = {"msg": text[:500]}
            error = {
                "base_url": base_url,
                "status_code": exc.code,
                "request_id": exc.headers.get("OK-Request-ID", ""),
                "error": str(body.get("msg") or body.get("message") or f"HTTP {exc.code}"),
                "okx_code": str(body.get("code", "")),
                "okx_msg": str(body.get("msg", "")),
                "data_errors": okx_data_error_rows(body),
                "body": body,
            }
            errors.append(error)
            if exc.code < 500 or not allow_fallback:
                return {"ok": False, **error, "fallback_errors": errors, "config": okx_status()}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            errors.append(
                {
                    "base_url": base_url,
                    "status_code": 0,
                    "error": str(reason),
                    "error_type": type(reason).__name__,
                }
            )
            if not allow_fallback:
                break
    return {
        "ok": False,
        "status_code": 0,
        "base_url": base_urls[0] if base_urls else config["base_url"],
        "error": "; ".join(f"{item.get('base_url')}: {item.get('error')}" for item in errors) or "OKX request failed",
        "error_type": "fallback_exhausted",
        "fallback_errors": errors,
        "config": okx_status(),
    }


def okx_public_request(path: str) -> dict[str, Any]:
    # Public market/reference data is not environment-specific. Keeping the
    # simulated header off here gives the full OKX spot rule set while private
    # account/order calls still require OKX simulated trading.
    return okx_request("GET", path, simulated_override=False)


def okx_probe_base_url(base_url: str) -> dict[str, Any]:
    config = okx_config()
    started = time.monotonic()
    headers = {
        "Accept": "application/json",
        "User-Agent": "KaTradeLocalOKXAdapter/0.1",
    }
    if config["simulated"]:
        headers["x-simulated-trading"] = "1"
    request = urllib.request.Request(
        f"{base_url}/api/v5/public/time",
        method="GET",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=float(config.get("request_timeout_seconds", 4.0))) as response:
            text = response.read().decode("utf-8")
            body = json.loads(text) if text else {}
            ok = str(body.get("code", "0")) == "0"
            return {
                "base_url": base_url,
                "ok": ok,
                "status_code": response.status,
                "latency_ms": round((time.monotonic() - started) * 1000.0, 2),
                "server_time": (body.get("data") or [{}])[0].get("ts", "") if isinstance(body.get("data"), list) else "",
                "error": "" if ok else str(body.get("msg", "OKX API error")),
            }
    except Exception as exc:
        return {
            "base_url": base_url,
            "ok": False,
            "status_code": 0,
            "latency_ms": round((time.monotonic() - started) * 1000.0, 2),
            "error": str(getattr(exc, "reason", exc)),
        }


def okx_network_probe_payload() -> dict[str, Any]:
    probes = [okx_probe_base_url(base_url) for base_url in okx_base_urls_config()]
    return {
        "ok": any(item.get("ok") for item in probes),
        "mode": "mainland",
        "message": "中国大陆网络建议使用官方 REST https://www.okx.com；aws.okx.com 官方已停止服务。",
        "probes": probes,
        "config": okx_status(),
    }


def okx_environment_mismatch(result: dict[str, Any]) -> bool:
    text = json.dumps(result.get("body", {}), ensure_ascii=False) + " " + str(result.get("error", ""))
    return "does not match current environment" in text


def okx_private_read_request(path: str) -> dict[str, Any]:
    result = okx_request("GET", path, auth=True)
    if result.get("ok") or not okx_environment_mismatch(result):
        return result
    configured_simulated = bool(okx_config().get("simulated"))
    alternate = not configured_simulated
    retry = okx_request("GET", path, auth=True, simulated_override=alternate)
    retry["environment_retry"] = True
    retry["configured_simulated"] = configured_simulated
    retry["used_simulated"] = alternate
    retry["environment_warning"] = (
        "当前 OKX key 与 OKX_SIMULATED_TRADING 配置不匹配；只读请求已用相反环境重试。"
        if retry.get("ok")
        else "当前 OKX key 与 OKX_SIMULATED_TRADING 配置不匹配；相反环境重试仍失败。"
    )
    retry["original_error"] = result.get("error", "")
    return retry


def okx_simulated_submit_gate() -> dict[str, Any]:
    status = okx_status()
    if not status.get("configured"):
        return {"ready": False, "reason": "OKX API key 未配置。", "config": status}
    if not status.get("simulated"):
        return {"ready": False, "reason": "OKX_SIMULATED_TRADING=false，平台拒绝下单。", "config": status}
    if not status.get("trading_enabled"):
        return {"ready": False, "reason": "OKX_TRADING_ENABLED=false，模拟盘下单开关关闭。", "config": status}
    raw_key = "|".join(
        [
            get_api_key("OKX_API_KEY"),
            status.get("base_url", ""),
            "simulated" if status.get("simulated") else "live",
        ]
    )
    cache_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    now_monotonic = time.monotonic()
    with OKX_SUBMIT_GATE_LOCK:
        cached = OKX_SUBMIT_GATE_CACHE.get("payload", {}) if OKX_SUBMIT_GATE_CACHE.get("key") == cache_key else {}
        if cached:
            checked_at = float_from_any(OKX_SUBMIT_GATE_CACHE.get("checked_at"), 0.0)
            ttl_seconds = 30.0 if cached.get("ready") else 8.0
            if now_monotonic - checked_at <= ttl_seconds:
                return {**cached, "config": status, "cached": True, "cache_ttl_seconds": ttl_seconds}
    probe = okx_request("GET", "/api/v5/account/config", auth=True, simulated_override=True)
    if not probe.get("ok"):
        payload = {
            "ready": False,
            "reason": f"当前 API key 不能用于 OKX 模拟盘环境：{probe.get('error', '检查失败')}",
            "config": status,
            "probe": {key: probe.get(key) for key in ["status_code", "base_url", "error", "request_id"]},
        }
        with OKX_SUBMIT_GATE_LOCK:
            OKX_SUBMIT_GATE_CACHE.update({"key": cache_key, "checked_at": now_monotonic, "payload": payload})
        return payload
    payload = {"ready": True, "reason": "OKX 模拟盘 key 环境检查通过。", "config": status}
    with OKX_SUBMIT_GATE_LOCK:
        OKX_SUBMIT_GATE_CACHE.update({"key": cache_key, "checked_at": now_monotonic, "payload": payload})
    return payload


def sanitize_okx_ticker(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "inst_type": item.get("instType", item.get("inst_type", "")),
        "inst_id": item.get("instId", item.get("inst_id", "")),
        "last": item.get("last", ""),
        "bid": item.get("bidPx", item.get("bid", "")),
        "ask": item.get("askPx", item.get("ask", "")),
        "open_24h": item.get("open24h", item.get("open_24h", "")),
        "high_24h": item.get("high24h", item.get("high_24h", "")),
        "low_24h": item.get("low24h", item.get("low_24h", "")),
        "volume_24h": item.get("vol24h", item.get("volume_24h", "")),
        "volume_ccy_24h": item.get("volCcy24h", item.get("volume_ccy_24h", "")),
        "timestamp": item.get("ts", item.get("timestamp", "")),
    }


def okx_ticker_cache_ttl_seconds() -> int:
    return bounded_int(get_local_setting("OKX_TICKER_CACHE_TTL_SECONDS", "2"), 2, 1, 30)


def okx_ticker_row_timestamp_ms(row: dict[str, Any]) -> int:
    for key in ["timestamp", "ts", "updated_at_ms", "_cached_at_ms"]:
        value = int(float_from_any(row.get(key), 0.0))
        if value > 0:
            return value if value > 10_000_000_000 else value * 1000
    return 0


def okx_ticker_age_seconds(row: dict[str, Any], fallback_time: str = "") -> Optional[float]:
    timestamp_ms = okx_ticker_row_timestamp_ms(row)
    if timestamp_ms <= 0 and fallback_time:
        try:
            timestamp_ms = epoch_ms_from_text(fallback_time)
        except (ValueError, TypeError):
            timestamp_ms = 0
    if timestamp_ms <= 0:
        return None
    return max(0.0, (int(time.time() * 1000) - timestamp_ms) / 1000.0)


def okx_ticker_cache_write(rows: list[dict[str, Any]], source: str) -> None:
    now_ms = int(time.time() * 1000)
    ttl_ms = okx_ticker_cache_ttl_seconds() * 1000
    with OKX_TICKER_CACHE_LOCK:
        for item in rows:
            row = sanitize_okx_ticker(item)
            inst_id = str(row.get("inst_id", "")).upper().strip()
            if not inst_id:
                continue
            OKX_TICKER_CACHE[inst_id] = {
                **row,
                "_source": source,
                "_cached_at_ms": now_ms,
            }
        stale_keys = [
            inst_id for inst_id, row in OKX_TICKER_CACHE.items()
            if now_ms - int(float_from_any(row.get("_cached_at_ms"), 0.0)) > ttl_ms * 10
        ]
        for inst_id in stale_keys:
            OKX_TICKER_CACHE.pop(inst_id, None)


def okx_ticker_from_stream(inst_id: str) -> Optional[dict[str, Any]]:
    wanted = str(inst_id).upper().strip()
    with MARKET_STREAM_LOCK:
        raw = dict((MARKET_STREAM_STATE.get("tickers", {}) or {}).get(wanted, {}) or {})
        last_ticker_at = str(MARKET_STREAM_STATE.get("last_ticker_at", ""))
        status = str(MARKET_STREAM_STATE.get("status", ""))
    if not raw:
        return None
    row = sanitize_okx_ticker(raw)
    if not row.get("inst_id"):
        row["inst_id"] = wanted
    age = okx_ticker_age_seconds(row, last_ticker_at)
    max_age = max(5.0, float(okx_ticker_cache_ttl_seconds() * 3))
    if age is not None and age > max_age:
        return None
    row.update(
        {
            "_source": "stream",
            "_source_age_seconds": round(age, 3) if age is not None else None,
            "_stream_status": status,
        }
    )
    return row


def okx_ticker_from_cache(inst_id: str) -> Optional[dict[str, Any]]:
    wanted = str(inst_id).upper().strip()
    with OKX_TICKER_CACHE_LOCK:
        cached = dict(OKX_TICKER_CACHE.get(wanted, {}) or {})
    if not cached:
        return None
    cached_at = int(float_from_any(cached.get("_cached_at_ms"), 0.0))
    age = max(0.0, (int(time.time() * 1000) - cached_at) / 1000.0) if cached_at > 0 else None
    if age is None or age > okx_ticker_cache_ttl_seconds():
        return None
    cached["_source"] = "cache"
    cached["_source_age_seconds"] = round(age, 3)
    return cached


def okx_ticker_row_for_inst(inst_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    wanted = str(inst_id).upper().strip()
    for loader in [okx_ticker_from_stream, okx_ticker_from_cache]:
        row = loader(wanted)
        if row:
            if row.get("_source") == "stream":
                okx_ticker_cache_write([row], "stream")
            return row, {"source": row.get("_source", ""), "request_id": "", "cached": row.get("_source") != "rest"}
    result = okx_public_request(f"/api/v5/market/ticker?{urlencode({'instId': wanted})}")
    if not result.get("ok"):
        return {}, result
    data = result.get("data", []) if isinstance(result.get("data"), list) else []
    row = sanitize_okx_ticker(data[0]) if data and isinstance(data[0], dict) else {}
    if row:
        okx_ticker_cache_write([row], "rest")
        row["_source"] = "rest"
        row["_source_age_seconds"] = 0.0
    return row, {"source": "rest", "request_id": result.get("request_id", ""), "cached": False}


def okx_tickers_from_fast_path(inst_type: str, configured: list[str]) -> dict[str, Any]:
    wanted = [str(item).upper().strip() for item in configured if str(item).strip()]
    if not wanted:
        return {"ok": False, "error": "batch_rest_required"}
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    source_counts: dict[str, int] = {}
    for inst_id in wanted:
        row = okx_ticker_from_stream(inst_id) or okx_ticker_from_cache(inst_id)
        if row:
            rows.append(row)
            source = str(row.get("_source", "cache"))
            source_counts[source] = source_counts.get(source, 0) + 1
        else:
            missing.append(inst_id)
    if not missing:
        stream_rows = [row for row in rows if row.get("_source") == "stream"]
        if stream_rows:
            okx_ticker_cache_write(stream_rows, "stream")
        return {
            "ok": True,
            "tickers": rows,
            "source": "stream_cache",
            "cached": True,
            "request_id": "",
            "missing": [],
            "source_counts": source_counts,
        }
    result = okx_public_request(f"/api/v5/market/tickers?{urlencode({'instType': inst_type})}")
    if not result.get("ok"):
        if rows:
            return {
                "ok": True,
                "tickers": rows,
                "source": "stream_cache_partial",
                "cached": True,
                "partial": True,
                "missing": missing,
                "rest_error": result.get("error", "OKX ticker refresh failed"),
                "request_id": result.get("request_id", ""),
                "source_counts": source_counts,
            }
        return result
    configured_set = set(wanted)
    rest_rows = [
        sanitize_okx_ticker(item)
        for item in result.get("data", [])
        if isinstance(item, dict) and str(item.get("instId", item.get("inst_id", ""))).upper().strip() in configured_set
    ]
    returned = {str(row.get("inst_id", "")).upper().strip() for row in rest_rows}
    rest_missing = [inst_id for inst_id in wanted if inst_id not in returned]
    okx_ticker_cache_write(rest_rows, "rest")
    for row in rest_rows:
        row["_source"] = "rest"
        row["_source_age_seconds"] = 0.0
    return {
        "ok": True,
        "tickers": rest_rows,
        "source": "rest",
        "cached": False,
        "request_id": result.get("request_id", ""),
        "partial": bool(rest_missing),
        "missing": rest_missing,
        "source_counts": {"rest": len(rest_rows)},
    }


def okx_ticker_inst_ids_from_params(
    params: dict[str, list[str]],
    inst_type: str,
    configured: list[str],
) -> tuple[Optional[list[str]], Optional[dict[str, Any]]]:
    raw = params.get("instIds", params.get("instruments", [""]))[0].strip()
    if not raw:
        return configured, None
    configured_set = set(configured)
    values: list[str] = []
    for item in re.split(r"[\s,]+", raw):
        value = item.strip().upper()
        if not value:
            continue
        if inst_type == "SWAP":
            value = okx_derivative_inst_id(value, "SWAP")
        if not re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+(?:-[A-Z0-9]+)?", value):
            return None, {"ok": False, "error": f"无效 OKX 合约: {value}", "config": okx_status()}
        if configured_set and value not in configured_set:
            return None, {"ok": False, "error": f"{value} 不在有效 OKX {inst_type} 白名单内。", "config": okx_status()}
        if value not in values:
            values.append(value)
    return values or configured, None


def sanitize_okx_instrument(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "inst_type": item.get("instType", ""),
        "inst_id": item.get("instId", ""),
        "base_ccy": item.get("baseCcy", ""),
        "quote_ccy": item.get("quoteCcy", ""),
        "state": item.get("state", ""),
        "min_size": item.get("minSz", ""),
        "lot_size": item.get("lotSz", ""),
        "tick_size": item.get("tickSz", ""),
        "ct_val": item.get("ctVal", ""),
        "ct_mult": item.get("ctMult", ""),
        "ct_type": item.get("ctType", ""),
        "settle_ccy": item.get("settleCcy", ""),
    }


def okx_instrument_cache_path(inst_type: str) -> Path:
    normalized = str(inst_type or OKX_EXECUTION_INST_TYPE).upper().strip()
    return OKX_REFERENCE_DIR / f"instruments_{normalized.lower()}.json"


def okx_instrument_cache_ttl_seconds() -> int:
    return bounded_int(get_local_setting("OKX_INSTRUMENT_CACHE_TTL_SECONDS", "21600"), 21600, 60, 7 * 24 * 3600)


def read_okx_instrument_cache(inst_type: str) -> dict[str, Any]:
    path = okx_instrument_cache_path(inst_type)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def okx_instrument_cache_fresh(payload: dict[str, Any]) -> bool:
    generated_ms = int(float_from_any(payload.get("generated_at_ms"), 0.0))
    if generated_ms <= 0:
        return False
    age_seconds = max(0.0, (int(time.time() * 1000) - generated_ms) / 1000.0)
    return age_seconds <= okx_instrument_cache_ttl_seconds()


def okx_instrument_cache_rows(payload: dict[str, Any], inst_id: str = "") -> list[dict[str, Any]]:
    rows = payload.get("instruments", []) if isinstance(payload.get("instruments"), list) else []
    wanted = str(inst_id or "").upper().strip()
    return [
        row for row in rows
        if isinstance(row, dict) and (not wanted or str(row.get("inst_id", "")).upper() == wanted)
    ]


def write_okx_instrument_cache(inst_type: str, rows: list[dict[str, Any]], request_id: str = "") -> dict[str, Any]:
    payload = {
        "ok": True,
        "inst_type": str(inst_type or OKX_EXECUTION_INST_TYPE).upper().strip(),
        "generated_at": now_iso(),
        "generated_at_ms": int(time.time() * 1000),
        "request_id": request_id,
        "ttl_seconds": okx_instrument_cache_ttl_seconds(),
        "instruments": rows,
    }
    OKX_REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    with OKX_INSTRUMENT_CACHE_LOCK:
        okx_instrument_cache_path(inst_type).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return payload


def okx_cached_instruments(inst_type: str, *, force_refresh: bool = False, inst_id: str = "") -> dict[str, Any]:
    """Read OKX reference-data rules through a persistent local cache.

    Contract metadata changes slowly, while the execution bridge asks for it on
    every candidate conversion.  Caching keeps the hot path deterministic and
    also lets simulated trading continue to produce precise minSz/ctVal errors
    when the public REST endpoint is temporarily unavailable.
    """
    normalized = str(inst_type or OKX_EXECUTION_INST_TYPE).upper().strip()
    with OKX_INSTRUMENT_CACHE_LOCK:
        cached = read_okx_instrument_cache(normalized)
    if cached and not force_refresh and okx_instrument_cache_fresh(cached):
        rows = okx_instrument_cache_rows(cached, inst_id)
        return {
            "ok": True,
            "inst_type": normalized,
            "source": "cache",
            "stale": False,
            "cache_path": str(okx_instrument_cache_path(normalized)),
            "generated_at": cached.get("generated_at", ""),
            "request_id": cached.get("request_id", ""),
            "instruments": rows,
            "config": okx_status(),
        }

    query = {"instType": normalized}
    result = okx_public_request(f"/api/v5/public/instruments?{urlencode(query)}")
    if result.get("ok"):
        rows = [sanitize_okx_instrument(item) for item in result.get("data", []) if isinstance(item, dict)]
        cached = write_okx_instrument_cache(normalized, rows, str(result.get("request_id", "")))
        return {
            "ok": True,
            "inst_type": normalized,
            "source": "rest",
            "stale": False,
            "cache_path": str(okx_instrument_cache_path(normalized)),
            "generated_at": cached.get("generated_at", ""),
            "request_id": result.get("request_id", ""),
            "instruments": okx_instrument_cache_rows(cached, inst_id),
            "config": okx_status(),
        }

    if cached:
        rows = okx_instrument_cache_rows(cached, inst_id)
        return {
            "ok": True,
            "inst_type": normalized,
            "source": "cache_stale",
            "stale": True,
            "cache_path": str(okx_instrument_cache_path(normalized)),
            "generated_at": cached.get("generated_at", ""),
            "refresh_error": result.get("error", "OKX instrument refresh failed"),
            "request_id": cached.get("request_id", ""),
            "instruments": rows,
            "config": okx_status(),
        }
    return result


def sanitize_okx_account_config(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "acct_lv": item.get("acctLv", ""),
        "acct_stp_mode": item.get("acctStpMode", ""),
        "auto_loan": item.get("autoLoan", ""),
        "ct_iso_mode": item.get("ctIsoMode", ""),
        "greeks_type": item.get("greeksType", ""),
        "level": item.get("level", ""),
        "level_tmp": item.get("levelTmp", ""),
        "mgn_iso_mode": item.get("mgnIsoMode", ""),
        "pos_mode": item.get("posMode", ""),
        "spot_offset_type": item.get("spotOffsetType", ""),
        "uid": mask_value(str(item.get("uid", "")), visible=3),
    }


def okx_check(name: str, ok: bool, severity: str, message: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "severity": severity, "message": message}


def decimal_value(value: Any) -> Optional[Decimal]:
    try:
        text = str(value).strip()
        if not text:
            return None
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def decimal_multiple(value: Decimal, step: Decimal) -> bool:
    if step <= 0:
        return True
    try:
        return value.remainder_near(step) == 0
    except InvalidOperation:
        return False


def decimal_floor_to_step(value: Decimal, step: Optional[Decimal]) -> Decimal:
    if step is None or step <= 0:
        return value
    return (value // step) * step


def decimal_ceil_to_step(value: Decimal, step: Optional[Decimal]) -> Decimal:
    if step is None or step <= 0:
        return value
    return (value / step).to_integral_value(rounding=ROUND_CEILING) * step


def decimal_plain(value: Decimal) -> str:
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def okx_derivative_rule_health(row: dict[str, Any], inst_type: str) -> tuple[bool, str]:
    """Validate the cached exchange metadata needed to size derivative orders."""
    if not row:
        return False, "OKX 合约元数据未包含该 instId。"
    state = str(row.get("state", "")).lower()
    if state != "live":
        return False, f"OKX instrument state={row.get('state', '-')}, 暂不可交易。"
    if inst_type in OKX_DERIVATIVE_INST_TYPES:
        ct_val = decimal_value(row.get("ct_val"))
        if ct_val is None or ct_val <= 0:
            return False, "OKX 合约元数据缺少有效 ctVal。"
    min_size = decimal_value(row.get("min_size"))
    lot_size = decimal_value(row.get("lot_size"))
    tick_size = decimal_value(row.get("tick_size"))
    if min_size is None or min_size <= 0:
        return False, "OKX 合约元数据缺少有效 minSz。"
    if lot_size is None or lot_size <= 0:
        return False, "OKX 合约元数据缺少有效 lotSz。"
    if tick_size is None or tick_size <= 0:
        return False, "OKX 合约元数据缺少有效 tickSz。"
    return True, "OKX 合约元数据可用于下单数量折算。"


def okx_cached_live_derivative_rows(inst_type: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Return tradeable derivative metadata from the local cache without REST IO.

    This helper is used in hot whitelist/pre-trade paths.  It intentionally does
    not refresh the cache; cache refresh happens through okx_cached_instruments()
    in endpoints/startup paths where a short REST call is acceptable.
    """
    normalized = str(inst_type or "SWAP").upper().strip()
    cached = read_okx_instrument_cache(normalized)
    if not cached:
        return {}, {"cache_available": False, "cache_path": str(okx_instrument_cache_path(normalized))}
    rows: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, str]] = []
    for row in okx_instrument_cache_rows(cached):
        if not isinstance(row, dict):
            continue
        inst_id = str(row.get("inst_id", "")).upper().strip()
        if not inst_id:
            continue
        ok, reason = okx_derivative_rule_health(row, normalized)
        if ok:
            rows[inst_id] = row
        else:
            rejected.append({"inst_id": inst_id, "reason": reason})
    return rows, {
        "cache_available": True,
        "cache_path": str(okx_instrument_cache_path(normalized)),
        "cache_generated_at": cached.get("generated_at", ""),
        "stale": not okx_instrument_cache_fresh(cached),
        "live_count": len(rows),
        "rejected_count": len(rejected),
        "rejected": rejected[:20],
    }


def okx_effective_instruments_for_type(inst_type: str) -> list[str]:
    """Configured OKX whitelist after applying cached derivative metadata."""
    configured = okx_instruments_for_type(inst_type)
    normalized = str(inst_type or OKX_EXECUTION_INST_TYPE).upper().strip()
    if normalized not in OKX_DERIVATIVE_INST_TYPES:
        return configured
    live_rows, meta = okx_cached_live_derivative_rows(normalized)
    if not meta.get("cache_available"):
        return configured
    live_ids = set(live_rows)
    return [inst_id for inst_id in configured if inst_id in live_ids]


def okx_effective_whitelist_for_cxx(inst_type: str) -> list[str]:
    """C++ policy treats an empty whitelist as allow-all, so keep a deny sentinel."""
    effective = okx_effective_instruments_for_type(inst_type)
    if effective:
        return effective
    if str(inst_type or "").upper().strip() in OKX_DERIVATIVE_INST_TYPES:
        return ["__NO_OKX_DERIVATIVE_METADATA__"]
    return effective


def okx_filter_source_instruments_for_derivatives(
    instruments: list[str],
    inst_type: str,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Filter spot-style source symbols to derivatives with usable OKX rules."""
    normalized = str(inst_type or "SWAP").upper().strip()
    source_values: list[str] = []
    for item in instruments:
        source_id = okx_source_inst_id(str(item).upper().strip())
        if source_id and source_id not in source_values:
            source_values.append(source_id)
    result = okx_cached_instruments(normalized, force_refresh=force_refresh)
    if not result.get("ok"):
        return {
            "ok": False,
            "filter_applied": False,
            "reason": result.get("error", "OKX 合约元数据刷新失败。"),
            "source": result.get("source", ""),
            "supported_source_instruments": source_values,
            "unsupported_instruments": [],
            "cache_path": result.get("cache_path", ""),
        }
    rows_by_inst = {
        str(row.get("inst_id", "")).upper().strip(): row
        for row in result.get("instruments", [])
        if isinstance(row, dict)
    }
    supported: list[str] = []
    unsupported: list[dict[str, Any]] = []
    for source_id in source_values:
        derivative_id = okx_derivative_inst_id(source_id, normalized)
        row = rows_by_inst.get(derivative_id, {})
        ok, reason = okx_derivative_rule_health(row, normalized)
        if ok:
            supported.append(source_id)
        else:
            unsupported.append(
                {
                    "source_inst_id": source_id,
                    "inst_id": derivative_id,
                    "reason": reason,
                    "state": row.get("state", "") if isinstance(row, dict) else "",
                }
            )
    return {
        "ok": True,
        "filter_applied": True,
        "inst_type": normalized,
        "source": result.get("source", ""),
        "stale": bool(result.get("stale")),
        "cache_path": result.get("cache_path", ""),
        "cache_generated_at": result.get("generated_at", ""),
        "supported_source_instruments": supported,
        "unsupported_instruments": unsupported,
    }


def okx_instrument_rules(inst_id: str, inst_type: Optional[str] = None) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    resolved_type = (inst_type or ("SWAP" if str(inst_id).upper().endswith("-SWAP") else "SPOT")).upper()
    result = okx_cached_instruments(resolved_type, inst_id=str(inst_id).upper().strip())
    if not result.get("ok"):
        return None, result
    data = result.get("instruments", [])
    if not data:
        return None, {"ok": False, "error": f"OKX 未返回 {inst_id} 的 {resolved_type} 规则", "config": okx_status()}
    return data[0], result


def okx_validate_order_rules(order: dict[str, Any]) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    inst_id = str(order.get("instId", "")).upper()
    inst_type = okx_order_inst_type(order)
    derivatives = inst_type in OKX_DERIVATIVE_INST_TYPES
    td_mode = str(order.get("tdMode", "")).lower()
    ord_type = str(order.get("ordType", "")).lower()
    checks.append(
        okx_check(
            "交易范围",
            td_mode in OKX_DERIVATIVE_TD_MODES if derivatives else td_mode == OKX_EXECUTION_TD_MODE,
            "ok" if (td_mode in OKX_DERIVATIVE_TD_MODES if derivatives else td_mode == OKX_EXECUTION_TD_MODE) else "halt",
            f"OKX {inst_type} {td_mode} 模式。"
            if derivatives
            else "仅允许 OKX 现货 cash 模式。"
        )
    )
    checks.append(
        okx_check(
            "订单类型",
            ord_type in OKX_ALLOWED_ORDER_TYPES,
            "ok" if ord_type in OKX_ALLOWED_ORDER_TYPES else "halt",
            "仅允许 limit/post_only 限价挂单；市价、IOC、FOK 暂时禁用。"
        )
    )
    configured = set(okx_effective_instruments_for_type(inst_type))
    if inst_type in OKX_DERIVATIVE_INST_TYPES and not configured:
        checks.append(okx_check("合约白名单", False, "halt", f"当前 OKX {inst_type} 标的池没有有效合约元数据。"))
        return checks, None
    if configured and inst_id not in configured:
        checks.append(okx_check("合约白名单", False, "halt", f"{inst_id} 不在有效 OKX {inst_type} 合约元数据白名单内。"))
        return checks, None
    checks.append(okx_check("合约白名单", True, "ok", f"{inst_id} 已在本地白名单内。"))

    rules, rules_result = okx_instrument_rules(inst_id, inst_type)
    if not rules:
        checks.append(okx_check("合约规则", False, "halt", rules_result.get("error", "无法读取 OKX 合约规则。")))
        return checks, None
    state = str(rules.get("state", "")).lower()
    checks.append(okx_check("合约状态", state == "live", "ok" if state == "live" else "halt", f"OKX state={rules.get('state', '-')}."))

    size = decimal_value(order.get("sz"))
    min_size = decimal_value(rules.get("min_size"))
    lot_size = decimal_value(rules.get("lot_size"))
    if size is None or size <= 0:
        checks.append(okx_check("数量格式", False, "halt", "sz 必须是大于 0 的数字。"))
    else:
        if min_size is not None and size < min_size:
            checks.append(okx_check("最小数量", False, "halt", f"sz={size} 小于 minSz={min_size}。"))
        else:
            checks.append(okx_check("最小数量", True, "ok", f"sz={size}, minSz={rules.get('min_size', '-')}。"))
        if lot_size is not None and not decimal_multiple(size, lot_size):
            checks.append(okx_check("数量步长", False, "halt", f"sz={size} 不是 lotSz={lot_size} 的整数倍。"))
        else:
            checks.append(okx_check("数量步长", True, "ok", f"lotSz={rules.get('lot_size', '-')}。"))

    price = decimal_value(order.get("px"))
    tick_size = decimal_value(rules.get("tick_size"))
    if order.get("ordType") != "market":
        if price is None or price <= 0:
            checks.append(okx_check("价格格式", False, "halt", "非市价单必须提供大于 0 的 px。"))
        elif tick_size is not None and not decimal_multiple(price, tick_size):
            checks.append(okx_check("价格步长", False, "halt", f"px={price} 不是 tickSz={tick_size} 的整数倍。"))
        else:
            checks.append(okx_check("价格步长", True, "ok", f"tickSz={rules.get('tick_size', '-')}。"))
    return checks, rules


def okx_estimate_order_notional(order: dict[str, Any], latest_price: Optional[float]) -> tuple[Optional[float], str]:
    notional_override = decimal_value(order.get("_notional_usdt", order.get("notional_usdt", order.get("notional", ""))))
    if notional_override is not None and notional_override > 0:
        return float(notional_override), "provided_notional"
    size = decimal_value(order.get("sz"))
    if size is None or size <= 0:
        return None, "订单数量无效。"
    if order.get("ordType") == "market" and order.get("side") == "buy" and order.get("tgtCcy") == "quote_ccy":
        return float(size), "market_buy_quote_ccy"

    price = decimal_value(order.get("px"))
    if price is None:
        if latest_price is None or latest_price <= 0:
            return None, "无法估算订单名义金额，已按风控阻断。"
        price = Decimal(str(latest_price))
    if price <= 0:
        return None, "订单价格无效。"
    ct_val = decimal_value(order.get("_ctVal", ""))
    if okx_order_inst_type(order) in OKX_DERIVATIVE_INST_TYPES and ct_val is not None and ct_val > 0:
        return float(size * price * ct_val), "contracts_times_price_ctval"
    return float(size * price), "size_times_price"


def sanitize_okx_balance(data: list[Any]) -> dict[str, Any]:
    if not data:
        return {"total_eq": "", "details": []}
    account = data[0] if isinstance(data[0], dict) else {}
    wanted = {inst.split("-")[0] for inst in okx_instruments_config()} | {"USDT", "USD"}
    details = []
    for item in account.get("details", []) or []:
        ccy = item.get("ccy", "")
        eq = float(item.get("eq", "0") or 0)
        if ccy in wanted or abs(eq) > 1e-12:
            details.append(
                {
                    "ccy": ccy,
                    "eq": item.get("eq", ""),
                    "cash_bal": item.get("cashBal", ""),
                    "avail_bal": item.get("availBal", ""),
                    "frozen_bal": item.get("frozenBal", ""),
                    "upl": item.get("upl", ""),
                    "eq_usd": item.get("eqUsd", ""),
                }
            )
    return {
        "total_eq": account.get("totalEq", ""),
        "adj_eq": account.get("adjEq", ""),
        "iso_eq": account.get("isoEq", ""),
        "details": details,
    }


def sanitize_okx_order(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "ord_id": item.get("ordId", ""),
        "cl_ord_id": item.get("clOrdId", ""),
        "inst_id": item.get("instId", ""),
        "td_mode": item.get("tdMode", ""),
        "side": item.get("side", ""),
        "ord_type": item.get("ordType", ""),
        "px": item.get("px", ""),
        "sz": item.get("sz", ""),
        "acc_fill_sz": item.get("accFillSz", ""),
        "avg_px": item.get("avgPx", ""),
        "state": item.get("state", ""),
        "c_time": item.get("cTime", ""),
        "u_time": item.get("uTime", ""),
    }


def okx_tickers_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    allowed, inst_type, error = okx_spot_inst_type(params)
    if not allowed:
        return error
    configured_values = okx_effective_instruments_for_type(inst_type)
    configured = set(configured_values)
    if inst_type in OKX_DERIVATIVE_INST_TYPES and not configured:
        return {
            "ok": True,
            "tickers": [],
            "config": okx_status(),
            "request_id": "",
            "metadata_warning": f"当前 OKX {inst_type} 标的池没有有效合约元数据。",
        }
    target_values, target_error = okx_ticker_inst_ids_from_params(params, inst_type, configured_values)
    if target_error:
        return target_error
    target_values = target_values or []
    target = set(target_values)
    if target_values:
        result = okx_tickers_from_fast_path(inst_type, target_values)
    else:
        result = okx_public_request(f"/api/v5/market/tickers?{urlencode({'instType': inst_type})}")
        if result.get("ok"):
            result = {
                **result,
                "tickers": [sanitize_okx_ticker(item) for item in result.get("data", []) if isinstance(item, dict)],
                "source": "rest",
                "cached": False,
            }
    if not result.get("ok"):
        return result
    tickers = [
        sanitize_okx_ticker(item)
        for item in result.get("tickers", [])
        if (not target or item.get("inst_id") in target) and (not configured or item.get("inst_id") in configured)
    ]
    return {
        "ok": True,
        "tickers": tickers,
        "config": okx_status(),
        "request_id": result.get("request_id", ""),
        "source": result.get("source", ""),
        "cached": bool(result.get("cached")),
        "partial": bool(result.get("partial")),
        "missing": result.get("missing", []),
        "requested": target_values,
        "source_counts": result.get("source_counts", {}),
        "rest_error": result.get("rest_error", ""),
        "cache_ttl_seconds": okx_ticker_cache_ttl_seconds(),
    }


def okx_instruments_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    allowed, inst_type, error = okx_spot_inst_type(params)
    if not allowed:
        return error
    force_refresh = str(params.get("refresh", ["false"])[0]).lower() in TRUTHY_VALUES
    result = okx_cached_instruments(inst_type, force_refresh=force_refresh)
    if not result.get("ok"):
        return result
    configured = set(okx_effective_instruments_for_type(inst_type))
    if inst_type in OKX_DERIVATIVE_INST_TYPES and not configured:
        return {
            "ok": True,
            "instruments": [],
            "source": result.get("source", ""),
            "stale": bool(result.get("stale")),
            "cache_path": result.get("cache_path", ""),
            "cache_generated_at": result.get("generated_at", ""),
            "refresh_error": result.get("refresh_error", ""),
            "metadata_warning": f"当前 OKX {inst_type} 标的池没有有效合约元数据。",
            "config": okx_status(),
            "request_id": result.get("request_id", ""),
        }
    instruments = [
        item
        for item in result.get("instruments", [])
        if not configured or item.get("inst_id") in configured
    ]
    return {
        "ok": True,
        "instruments": instruments,
        "source": result.get("source", ""),
        "stale": bool(result.get("stale")),
        "cache_path": result.get("cache_path", ""),
        "cache_generated_at": result.get("generated_at", ""),
        "refresh_error": result.get("refresh_error", ""),
        "config": okx_status(),
        "request_id": result.get("request_id", ""),
    }


def okx_tradeability_inst_ids(params: dict[str, list[str]]) -> list[str]:
    raw = params.get("instIds", params.get("instruments", [""]))[0].strip()
    _, inst_type, _ = okx_spot_inst_type(params)
    configured = okx_effective_instruments_for_type(inst_type)
    if inst_type in OKX_DERIVATIVE_INST_TYPES and not configured:
        raise ValueError(f"当前 OKX {inst_type} 标的池没有有效合约元数据")
    if not raw:
        return configured
    requested = [item.strip().upper() for item in re.split(r"[\s,]+", raw) if item.strip()]
    values = []
    for inst_id in requested:
        if inst_type == "SWAP":
            inst_id = okx_derivative_inst_id(inst_id, "SWAP")
        if not re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+(?:-[A-Z0-9]+)?", inst_id):
            raise ValueError(f"无效 OKX 合约: {inst_id}")
        if inst_id not in configured:
            raise ValueError(f"{inst_id} 不在有效 OKX {inst_type} 合约元数据白名单内")
        if inst_id not in values:
            values.append(inst_id)
    return values or configured


def okx_book_depth_from_stream(inst_id: str) -> dict[str, Any]:
    with MARKET_STREAM_LOCK:
        book = dict((MARKET_STREAM_STATE.get("books5", {}) or {}).get(inst_id, {}) or {})
    bids = book.get("bids", []) if isinstance(book.get("bids"), list) else []
    asks = book.get("asks", []) if isinstance(book.get("asks"), list) else []
    bid_depth = sum(float_from_any(level.get("price")) * float_from_any(level.get("size")) for level in bids if isinstance(level, dict))
    ask_depth = sum(float_from_any(level.get("price")) * float_from_any(level.get("size")) for level in asks if isinstance(level, dict))
    return {
        "source": "stream" if bids or asks else "missing",
        "updated_at_ms": int(float_from_any(book.get("t"), 0.0)) if book else 0,
        "bid_depth_usdt": bid_depth,
        "ask_depth_usdt": ask_depth,
        "usable_depth_usdt": min(value for value in [bid_depth, ask_depth] if value > 0.0) if bid_depth > 0.0 or ask_depth > 0.0 else 0.0,
    }


def okx_tradeability_status(checks: list[dict[str, Any]]) -> str:
    if any(item.get("severity") == "halt" for item in checks):
        return "block"
    if any(item.get("severity") == "warn" for item in checks):
        return "warn"
    return "pass"


def okx_tradeability_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    allowed, inst_type, error = okx_spot_inst_type(params)
    if not allowed:
        return error
    try:
        inst_ids = okx_tradeability_inst_ids(params)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "config": okx_status()}

    notional = max(Decimal("1"), decimal_value(params.get("notional", [""])[0]) or okx_bridge_max_notional(params))
    config = parse_config()
    max_spread_bps = max(Decimal("1"), decimal_value(params.get("maxSpreadBps", [""])[0]) or Decimal(str(float_from_any(config.get("execution.max_slippage_bps", "50"), 50.0))))
    min_depth_multiple = max(Decimal("0"), decimal_value(params.get("minDepthMultiple", [""])[0]) or Decimal("3"))
    min_24h_volume = max(Decimal("0"), decimal_value(params.get("min24hVolumeUsdt", [""])[0]) or Decimal("1000000"))
    maker_fee_bps = Decimal(str(float_from_any(config.get("execution.maker_fee_bps", "1.0"), 1.0)))
    max_expected_cost_bps = max(
        Decimal("0"),
        decimal_value(params.get("maxExpectedCostBps", [""])[0])
        or Decimal(str(float_from_any(config.get("execution.max_expected_cost_bps", "50"), 50.0))),
    )

    instruments_payload = okx_instruments_payload({"instType": [inst_type]})
    tickers_payload = okx_tickers_payload({"instType": [inst_type], "instIds": [",".join(inst_ids)]})
    if not instruments_payload.get("ok"):
        return instruments_payload
    if not tickers_payload.get("ok"):
        return tickers_payload

    rules_by_inst = {row.get("inst_id"): row for row in instruments_payload.get("instruments", []) if isinstance(row, dict)}
    tickers_by_inst = {row.get("inst_id"): row for row in tickers_payload.get("tickers", []) if isinstance(row, dict)}
    rows: list[dict[str, Any]] = []
    summary = {"pass": 0, "warn": 0, "block": 0}

    for inst_id in inst_ids:
        rules = rules_by_inst.get(inst_id, {})
        ticker = tickers_by_inst.get(inst_id, {})
        bid = decimal_value(ticker.get("bid"))
        ask = decimal_value(ticker.get("ask"))
        last = decimal_value(ticker.get("last"))
        mid = (bid + ask) / Decimal("2") if bid is not None and ask is not None and bid > 0 and ask > 0 else last
        spread_bps = ((ask - bid) / mid * Decimal("10000")) if bid is not None and ask is not None and mid is not None and mid > 0 and ask >= bid else None
        min_size = decimal_value(rules.get("min_size"))
        lot_size = decimal_value(rules.get("lot_size"))
        ct_val = decimal_value(rules.get("ct_val"))
        reference_price = ask or last or mid
        if inst_type in OKX_DERIVATIVE_INST_TYPES and ct_val is not None and ct_val > 0 and reference_price is not None and reference_price > 0:
            estimated_size = decimal_floor_to_step(notional / (reference_price * ct_val), lot_size)
            min_notional = min_size * reference_price * ct_val if min_size is not None else None
        else:
            estimated_size = decimal_floor_to_step(notional / reference_price, lot_size) if reference_price is not None and reference_price > 0 else Decimal("0")
            min_notional = (min_size * reference_price) if min_size is not None and reference_price is not None else None
        if (
            min_size is not None
            and min_notional is not None
            and estimated_size < min_size
            and notional >= min_notional * Decimal("0.98")
        ):
            estimated_size = min_size
        volume_24h = decimal_value(ticker.get("volume_ccy_24h"))
        if (volume_24h is None or volume_24h <= 0) and last is not None and last > 0:
            base_volume = decimal_value(ticker.get("volume_24h"))
            volume_24h = base_volume * last if base_volume is not None else None
        depth = okx_book_depth_from_stream(inst_id)
        usable_depth = Decimal(str(float_from_any(depth.get("usable_depth_usdt"))))
        required_depth = notional * min_depth_multiple
        spread_cost_bps = (spread_bps or Decimal("0")) / Decimal("2") if spread_bps is not None else Decimal("0")
        if usable_depth > 0 and notional > 0:
            depth_cost_bps = min(Decimal("100"), (notional / usable_depth) * max(spread_bps or Decimal("1"), Decimal("1")))
        else:
            depth_cost_bps = Decimal("0")
        expected_cost_bps = maker_fee_bps + spread_cost_bps + depth_cost_bps
        expected_cost_usdt = notional * expected_cost_bps / Decimal("10000")
        checks = [
            okx_check("规则状态", rules.get("state") == "live", "ok" if rules.get("state") == "live" else "halt", f"state={rules.get('state', '-')}."),
            okx_check("盘口报价", bid is not None and ask is not None and bid > 0 and ask > 0 and ask >= bid, "ok" if bid is not None and ask is not None and bid > 0 and ask > 0 and ask >= bid else "halt", f"bid={bid or '-'} ask={ask or '-'}."),
            okx_check("价差", spread_bps is not None and spread_bps <= max_spread_bps, "ok" if spread_bps is not None and spread_bps <= max_spread_bps else "warn", f"spread={decimal_plain(spread_bps) if spread_bps is not None else '-'} bps / max={decimal_plain(max_spread_bps)} bps."),
            okx_check("最小下单", estimated_size > 0 and (min_size is None or estimated_size >= min_size), "ok" if estimated_size > 0 and (min_size is None or estimated_size >= min_size) else "halt", f"目标 {decimal_plain(notional)} USDT -> sz={decimal_plain(estimated_size)}, minSz={rules.get('min_size', '-')}."),
            okx_check("五档深度", usable_depth <= 0 or usable_depth >= required_depth, "ok" if usable_depth <= 0 or usable_depth >= required_depth else "warn", "WS books5 未就绪，仅用 ticker/规则评估。" if usable_depth <= 0 else f"usable={float(usable_depth):.2f} USDT / required={float(required_depth):.2f} USDT."),
            okx_check("24h成交量", volume_24h is not None and volume_24h >= min_24h_volume, "ok" if volume_24h is not None and volume_24h >= min_24h_volume else "warn", f"volume≈{float(volume_24h or Decimal('0')):.2f} USDT / min={float(min_24h_volume):.2f}."),
            okx_check("预计成本", expected_cost_bps <= max_expected_cost_bps, "ok" if expected_cost_bps <= max_expected_cost_bps else "warn", f"expected={decimal_plain(expected_cost_bps)} bps / max={decimal_plain(max_expected_cost_bps)} bps."),
        ]
        status = okx_tradeability_status(checks)
        summary[status] += 1
        rows.append(
            {
                "inst_id": inst_id,
                "status": status,
                "state": rules.get("state", ""),
                "bid": decimal_plain(bid) if bid is not None else "",
                "ask": decimal_plain(ask) if ask is not None else "",
                "last": decimal_plain(last) if last is not None else "",
                "spread_bps": float(spread_bps) if spread_bps is not None else None,
                "spread_cost_bps": float(spread_cost_bps),
                "depth_cost_bps": float(depth_cost_bps),
                "maker_fee_bps": float(maker_fee_bps),
                "expected_cost_bps": float(expected_cost_bps),
                "expected_cost_usdt": float(expected_cost_usdt),
                "target_notional_usdt": float(notional),
                "estimated_size": decimal_plain(estimated_size),
                "min_size": rules.get("min_size", ""),
                "min_notional_usdt": float(min_notional) if min_notional is not None else None,
                "lot_size": rules.get("lot_size", ""),
                "tick_size": rules.get("tick_size", ""),
                "ct_val": rules.get("ct_val", ""),
                "depth": depth,
                "volume_24h_usdt": float(volume_24h) if volume_24h is not None else None,
                "checks": checks,
            }
        )

    rows.sort(key=lambda row: ({"pass": 0, "warn": 1, "block": 2}.get(row["status"], 3), row["inst_id"]))
    return {
        "ok": True,
        "inst_type": inst_type,
        "target_notional_usdt": float(notional),
        "thresholds": {
            "max_spread_bps": float(max_spread_bps),
            "min_depth_multiple": float(min_depth_multiple),
            "min_24h_volume_usdt": float(min_24h_volume),
            "maker_fee_bps": float(maker_fee_bps),
            "max_expected_cost_bps": float(max_expected_cost_bps),
        },
        "summary": summary,
        "tradeability": rows,
        "config": okx_status(),
    }


def okx_candles_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    inst_id = params.get("instId", [okx_instruments_config()[0]])[0].upper()
    bar = params.get("bar", ["1m"])[0]
    limit_text = params.get("limit", ["300"])[0]
    try:
        limit = max(1, min(int(limit_text), 300))
    except ValueError:
        limit = 300
    max_pages_str = params.get("max_pages", ["1"])[0]
    try:
        max_pages = max(1, min(int(max_pages_str), 20))
    except ValueError:
        max_pages = 1
    # 多页获取（OKX 每页最多 300 根，用 after 参数翻页）
    all_bars: list[dict[str, Any]] = []
    after = ""
    for _page in range(max_pages):
        query_parts = {"instId": inst_id, "bar": bar, "limit": str(limit)}
        if after:
            query_parts["after"] = after
        result = okx_public_request(f"/api/v5/market/candles?{urlencode(query_parts)}")
        if not result.get("ok"):
            break
        rows = result.get("data", []) or []
        if not rows:
            break
        for row in rows:
            if not isinstance(row, list) or len(row) < 6:
                continue
            all_bars.append({
                "t": int(row[0]),
                "o": float(row[1]),
                "h": float(row[2]),
                "l": float(row[3]),
                "c": float(row[4]),
                "v": float(row[5]),
                "confirm": row[8] if len(row) > 8 else "",
            })
        after = str(int(rows[-1][0]) + 1)
        if len(rows) < limit:
            break
        time.sleep(0.06)
    all_bars.sort(key=lambda item: item["t"])
    return {
        "ok": True,
        "inst_id": inst_id,
        "bar": bar,
        "bars": all_bars,
        "pages": _page + 1,
        "config": okx_status(),
    }


def okx_trades_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    """Read recent OKX public trades for the tick-driven paper engine.

    When the public WebSocket stream is healthy, this returns the in-memory
    stream buffer.  Otherwise it falls back to the public REST endpoint.  OKX
    REST returns newest trades first; both paths normalize to event-time order.
    """
    inst_id = params.get("instId", [okx_instruments_config()[0]])[0].upper().strip()
    limit = bounded_int(params.get("limit", ["100"])[0], 100, 1, 100)
    source = str(params.get("source", ["auto"])[0]).strip().lower()
    if source in {"auto", "stream", "ws", "websocket"}:
        stream_payload = market_stream_trades_payload({"instId": [inst_id], "limit": [str(max(limit, 100))]})
        if stream_payload.get("trades") and (source != "auto" or stream_payload.get("fresh")):
            trades = stream_payload.get("trades", [])[-limit:]
            return {**stream_payload, "trades": trades, "limit": limit}
        if source in {"stream", "ws", "websocket"}:
            return {**stream_payload, "limit": limit}
    result = okx_public_request(f"/api/v5/market/trades?{urlencode({'instId': inst_id, 'limit': str(limit)})}")
    if not result.get("ok"):
        return result
    trades: list[dict[str, Any]] = []
    for item in result.get("data", []) or []:
        if not isinstance(item, dict):
            continue
        trade = normalize_okx_trade_item(inst_id, item)
        if trade:
            trades.append(trade)
    trades.sort(key=lambda row: (int(row.get("t", 0)), str(row.get("trade_id", ""))))
    return {
        "ok": True,
        "source": "rest",
        "inst_id": inst_id,
        "trades": trades,
        "config": okx_status(),
        "request_id": result.get("request_id", ""),
    }


def okx_balance_payload() -> dict[str, Any]:
    result = okx_private_read_request("/api/v5/account/balance")
    if not result.get("ok"):
        return result
    return {
        "ok": True,
        "account": sanitize_okx_balance(result.get("data", [])),
        "config": okx_status(),
        "request_id": result.get("request_id", ""),
        "environment_warning": result.get("environment_warning", ""),
        "used_simulated": result.get("used_simulated", okx_config().get("simulated")),
    }


def okx_account_config_payload() -> dict[str, Any]:
    result = okx_private_read_request("/api/v5/account/config")
    if not result.get("ok"):
        return result
    rows = result.get("data", [])
    return {
        "ok": True,
        "account_config": sanitize_okx_account_config(rows[0] if rows and isinstance(rows[0], dict) else {}),
        "config": okx_status(),
        "request_id": result.get("request_id", ""),
        "environment_warning": result.get("environment_warning", ""),
        "used_simulated": result.get("used_simulated", okx_config().get("simulated")),
    }


def okx_account_config_cached(force_refresh: bool = False, ttl_seconds: float = 60.0) -> dict[str, Any]:
    """Cache OKX account config so hot order conversion can adapt posSide cheaply."""
    now = time.time()
    with OKX_ACCOUNT_CONFIG_CACHE_LOCK:
        cached = OKX_ACCOUNT_CONFIG_CACHE.get("payload", {})
        checked_at = float_from_any(OKX_ACCOUNT_CONFIG_CACHE.get("checked_at"), 0.0)
        if cached and not force_refresh and now - checked_at <= ttl_seconds:
            return cached
    payload = okx_account_config_payload()
    if payload.get("ok"):
        account_config = payload.get("account_config", {}) if isinstance(payload.get("account_config"), dict) else {}
        with OKX_ACCOUNT_CONFIG_CACHE_LOCK:
            OKX_ACCOUNT_CONFIG_CACHE["checked_at"] = now
            OKX_ACCOUNT_CONFIG_CACHE["payload"] = account_config
        return account_config
    return cached if isinstance(cached, dict) else {}


def okx_normalized_position_mode(value: Any) -> str:
    normalized = str(value or "").lower().strip().replace("-", "_")
    if normalized in {"long_short", "long_short_mode", "hedge", "hedge_mode"}:
        return "long_short"
    if normalized in {"net", "net_mode"}:
        return "net"
    return ""


def okx_effective_position_mode(settings: Optional[dict[str, Any]] = None) -> str:
    account_mode = okx_normalized_position_mode(okx_account_config_cached().get("pos_mode"))
    if account_mode:
        return account_mode
    return configured_derivatives_position_mode(settings)


def okx_position_side_for_order(side: str, settings: Optional[dict[str, Any]] = None) -> str:
    mode = okx_effective_position_mode(settings)
    if mode == "long_short":
        return "long" if str(side).lower() == "buy" else "short"
    return "net"


def okx_orders_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    allowed, inst_type, error = okx_spot_inst_type(params)
    if not allowed:
        return error
    query = {"instType": inst_type}
    inst_id = params.get("instId", [""])[0].upper().strip()
    if inst_id:
        query["instId"] = inst_id
    result = okx_private_read_request(f"/api/v5/trade/orders-pending?{urlencode(query)}")
    if not result.get("ok"):
        return result
    return {
        "ok": True,
        "orders": [sanitize_okx_order(item) for item in result.get("data", [])],
        "config": okx_status(),
        "request_id": result.get("request_id", ""),
        "environment_warning": result.get("environment_warning", ""),
        "used_simulated": result.get("used_simulated", okx_config().get("simulated")),
    }


def okx_order_detail_payload(params: dict[str, Any]) -> dict[str, Any]:
    def first_value(name: str) -> str:
        value = params.get(name, "") if isinstance(params, dict) else ""
        if isinstance(value, list):
            return str(value[0]) if value else ""
        return str(value)

    inst_id = first_value("instId").upper().strip()
    ord_id = first_value("ordId").strip()
    cl_ord_id = first_value("clOrdId").strip()
    if not inst_id or not (ord_id or cl_ord_id):
        return {"ok": False, "error": "instId and ordId/clOrdId are required", "config": okx_status()}
    query = {"instId": inst_id}
    if ord_id:
        query["ordId"] = ord_id
    if cl_ord_id:
        query["clOrdId"] = cl_ord_id
    result = okx_private_read_request(f"/api/v5/trade/order?{urlencode(query)}")
    if not result.get("ok"):
        return result
    data = result.get("data", [])
    return {
        "ok": True,
        "order": sanitize_okx_order(data[0]) if data and isinstance(data[0], dict) else {},
        "config": okx_status(),
        "request_id": result.get("request_id", ""),
    }


def okx_audit_order_identity(row: dict[str, Any]) -> Optional[dict[str, str]]:
    detail = row.get("order_detail", {}) if isinstance(row.get("order_detail"), dict) else {}
    order = row.get("order", {}) if isinstance(row.get("order"), dict) else {}
    result = row.get("result", {}) if isinstance(row.get("result"), dict) else {}
    payload = row.get("payload", {}) if isinstance(row.get("payload"), dict) else {}
    inst_id = str(detail.get("inst_id") or order.get("instId") or result.get("instId") or payload.get("instId") or "").upper().strip()
    ord_id = str(detail.get("ord_id") or order.get("ordId") or result.get("ordId") or payload.get("ordId") or "").strip()
    cl_ord_id = str(detail.get("cl_ord_id") or order.get("clOrdId") or result.get("clOrdId") or payload.get("clOrdId") or "").strip()
    if not inst_id or not (ord_id or cl_ord_id):
        return None
    return {"instId": inst_id, "ordId": ord_id, "clOrdId": cl_ord_id}


def okx_detail_changed(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    keys = ["state", "acc_fill_sz", "avg_px", "u_time"]
    return any(str(previous.get(key, "")) != str(current.get(key, "")) for key in keys)


def okx_sync_recent_orders_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    limit = bounded_int(params.get("limit", ["20"])[0], 20, 1, 50)
    rows = read_okx_audit(500)
    seen: set[str] = set()
    synced: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    for row in rows:
        if row.get("action") not in {"order_submitted", "order_synced", "order_cancelled", "paper_auto_order_synced"}:
            continue
        identity = okx_audit_order_identity(row)
        if not identity:
            continue
        key = identity.get("ordId") or identity.get("clOrdId") or ""
        if key in seen:
            continue
        seen.add(key)
        detail_payload = okx_order_detail_payload(identity)
        item = {
            "source_audit_id": row.get("id", ""),
            "inst_id": identity["instId"],
            "ord_id": identity.get("ordId", ""),
            "cl_ord_id": identity.get("clOrdId", ""),
            "ok": bool(detail_payload.get("ok")),
            "order": detail_payload.get("order", {}),
            "error": detail_payload.get("error", ""),
        }
        if not detail_payload.get("ok"):
            audit = append_okx_audit(
                "order_sync_failed",
                {
                    "ok": False,
                    "source_audit_id": row.get("id", ""),
                    "source_order_id": row.get("source_order_id", ""),
                    "identity": identity,
                    "error": detail_payload.get("error", "订单详情同步失败"),
                    "result": detail_payload,
                    "request_id": detail_payload.get("request_id", ""),
                },
            )
            item["audit_id"] = audit["id"]
        if detail_payload.get("ok"):
            previous = row.get("order_detail", {}) if isinstance(row.get("order_detail"), dict) else {}
            current = detail_payload.get("order", {})
            if okx_detail_changed(previous, current):
                audit = append_okx_audit(
                    "order_synced",
                    {
                        "ok": True,
                        "source_audit_id": row.get("id", ""),
                        "source_order_id": row.get("source_order_id", ""),
                        "identity": identity,
                        "previous_detail": previous,
                        "order_detail": current,
                        "request_id": detail_payload.get("request_id", ""),
                    },
                )
                item["audit_id"] = audit["id"]
                append_broker_order_journal_sync(
                    row.get("source_order_id", ""),
                    identity,
                    current,
                    order=row.get("order", {}) if isinstance(row.get("order"), dict) else {},
                    audit_id=str(audit.get("id", "")),
                    sync_status="synced",
                )
                changed.append(audit)
        synced.append(item)
        if len(synced) >= limit:
            break
    return {
        "ok": True,
        "synced": synced,
        "changed": changed,
        "audit": read_okx_audit(50),
        "config": okx_status(),
    }


def okx_trade_item_result(result: dict[str, Any]) -> tuple[bool, dict[str, Any], str]:
    data = result.get("data", [])
    item = data[0] if data and isinstance(data[0], dict) else {}
    code = str(item.get("sCode", "0") or "0")
    message = str(item.get("sMsg", "") or result.get("error", ""))
    return code == "0", item, message


def normalize_okx_order(body: dict[str, Any]) -> dict[str, Any]:
    inst_id = str(body.get("instId", "")).upper().strip()
    inst_type = okx_order_inst_type({**body, "instId": inst_id})
    derivatives = inst_type in OKX_DERIVATIVE_INST_TYPES
    side = str(body.get("side", "")).lower()
    ord_type = str(body.get("ordType", "post_only")).lower()
    td_mode_default = paper_derivatives_margin_mode() if derivatives else OKX_EXECUTION_TD_MODE
    td_mode = str(body.get("tdMode", td_mode_default)).lower()
    if not inst_id:
        raise ValueError("instId is required")
    if side not in {"buy", "sell"}:
        raise ValueError("side must be buy or sell")
    if ord_type not in OKX_ALLOWED_ORDER_TYPES:
        raise ValueError("当前平台只允许 OKX 限价挂单：ordType 必须是 limit 或 post_only")
    if derivatives:
        if td_mode not in OKX_DERIVATIVE_TD_MODES:
            raise ValueError("OKX 合约订单 tdMode 必须是 isolated 或 cross")
    elif td_mode != OKX_EXECUTION_TD_MODE:
        raise ValueError("OKX 现货订单只允许 cash 模式")
    effective_instruments = set(okx_effective_instruments_for_type(inst_type))
    if inst_type in OKX_DERIVATIVE_INST_TYPES and not effective_instruments:
        raise ValueError(f"当前 OKX {inst_type} 标的池没有有效合约元数据")
    if inst_id not in effective_instruments:
        raise ValueError(f"{inst_id} 不在有效 OKX {inst_type} 合约元数据白名单内")
    order = {
        "instId": inst_id,
        "tdMode": td_mode,
        "side": side,
        "ordType": ord_type,
        "sz": str(body.get("sz", "")).strip(),
    }
    if not order["sz"]:
        raise ValueError("sz is required")
    px = str(body.get("px", "")).strip()
    if not px:
        raise ValueError("限价挂单必须填写 px")
    order["px"] = px
    tgt_ccy = str(body.get("tgtCcy", "")).strip()
    if tgt_ccy:
        raise ValueError("当前平台禁用市价买入口径 tgtCcy；请使用限价挂单的基础币数量 sz")
    cl_ord_id = str(body.get("clOrdId", "")).strip()
    if cl_ord_id and not re.fullmatch(r"[A-Za-z0-9]{1,32}", cl_ord_id):
        raise ValueError("clOrdId 只能包含 1-32 位英文字母或数字")
    order["clOrdId"] = cl_ord_id or f"KT{uuid4().hex[:20].upper()}"
    for key in ["_source_order_id", "_strategy_id", "_agent_id", "_trading_unit_id"]:
        if key in body:
            order[key] = body[key]
    if derivatives:
        raw_pos_side = str(body.get("posSide", body.get("_posSide", "")) or "").lower().strip()
        if raw_pos_side in {"long", "short"}:
            pos_side = raw_pos_side
        else:
            pos_side = okx_position_side_for_order(side)
        if pos_side not in {"net", "long", "short"}:
            raise ValueError("posSide 必须是 net/long/short")
        if pos_side != "net":
            order["posSide"] = pos_side
        order["_instType"] = inst_type
        order["_posSide"] = pos_side
        for key in [
            "_notional_usdt",
            "_ctVal",
            "_min_size_lifted",
            "_requested_notional_usdt",
            "_planned_before_lift_usdt",
            "_exchange_leverage",
            "_effective_leverage",
            "_unit_effective_leverage",
        ]:
            if key in body:
                order[key] = body[key]
        if bool_setting_from_any(body.get("reduceOnly", body.get("_reduceOnly", False)), False):
            order["reduceOnly"] = True
    return order


def okx_api_order_payload(order: dict[str, Any]) -> dict[str, Any]:
    """Strip platform-only metadata before sending an order to OKX."""
    payload = {
        "instId": order["instId"],
        "tdMode": order["tdMode"],
        "side": order["side"],
        "ordType": order["ordType"],
        "sz": order["sz"],
        "px": order["px"],
        "clOrdId": order["clOrdId"],
    }
    if okx_order_inst_type(order) in OKX_DERIVATIVE_INST_TYPES:
        pos_side = str(order.get("posSide", order.get("_posSide", "net")) or "net").lower().strip()
        if pos_side and pos_side != "net":
            payload["posSide"] = pos_side
        if bool(order.get("reduceOnly")):
            payload["reduceOnly"] = True
        # 附加止盈止损 (GAP-009)
        tp_sl = okx_tp_sl_attachment(order)
        if tp_sl:
            payload["attachAlgoOrds"] = tp_sl
    return payload


def okx_tp_sl_attachment(order: dict[str, Any]) -> Optional[list[dict[str, Any]]]:
    """为衍生品订单生成附带止盈止损 (GAP-009)."""
    if okx_order_inst_type(order) not in OKX_DERIVATIVE_INST_TYPES:
        return None
    if order.get("ordType") == "post_only" or bool(order.get("reduceOnly")):
        return None  # 只挂单/只减仓不加TP/SL
    config = parse_config()
    tp_ratio = config_float(config, "execution.tp_ratio", 0.0)
    sl_ratio = config_float(config, "execution.sl_ratio", 0.0)
    if tp_ratio <= 0.0 and sl_ratio <= 0.0:
        return None
    px = decimal_value(order.get("px", "")) or Decimal("0")
    if px <= Decimal("0"):
        return None  # 无价格无法计算
    side = str(order.get("side", "")).lower()
    tp_px = None
    sl_px = None
    if side == "buy":
        if tp_ratio > 0:
            tp_px = px * (Decimal("1") + round(Decimal(str(tp_ratio)), 6))
        if sl_ratio > 0:
            sl_px = px * (Decimal("1") - round(Decimal(str(sl_ratio)), 6))
    elif side == "sell":
        if tp_ratio > 0:
            tp_px = px * (Decimal("1") - round(Decimal(str(tp_ratio)), 6))
        if sl_ratio > 0:
            sl_px = px * (Decimal("1") + round(Decimal(str(sl_ratio)), 6))
    if tp_px is None and sl_px is None:
        return None
    algo = {"attachAlgoClOrdId": str(order.get("clOrdId", "")) + "_tpsl"}
    if tp_px is not None:
        algo["tpTriggerPx"] = decimal_plain(tp_px)
        algo["tpOrdPx"] = "-1"  # 市价
    if sl_px is not None:
        algo["slTriggerPx"] = decimal_plain(sl_px)
        algo["slOrdPx"] = "-1"
    return [algo]


def okx_set_derivative_leverage(order: dict[str, Any]) -> dict[str, Any]:
    """Set OKX leverage for simulated derivatives before the order is posted."""
    if okx_order_inst_type(order) not in OKX_DERIVATIVE_INST_TYPES:
        return {"ok": True, "skipped": True, "reason": "非合约订单无需设置杠杆。"}
    leverage = max(
        Decimal("1"),
        decimal_value(order.get("_exchange_leverage", "")) or Decimal("1"),
    )
    payload = {
        "instId": order["instId"],
        "lever": decimal_plain(leverage),
        "mgnMode": str(order.get("tdMode", paper_derivatives_margin_mode())).lower(),
    }
    pos_side = str(order.get("posSide", order.get("_posSide", "net")) or "net").lower().strip()
    if pos_side in {"long", "short"}:
        payload["posSide"] = pos_side
    result = okx_request("POST", "/api/v5/account/set-leverage", payload, auth=True)
    append_okx_audit(
        "derivative_leverage_set" if result.get("ok") else "derivative_leverage_set_failed",
        {
            "ok": bool(result.get("ok")),
            "payload": payload,
            "result": {key: result.get(key) for key in ["ok", "error", "data", "request_id", "status_code", "okx_code", "okx_msg", "data_errors"]},
            "error_summary": okx_error_summary(result) if not result.get("ok") else {},
            "raw_okx": okx_compact_raw_body(result) if not result.get("ok") else {},
        },
    )
    if not result.get("ok"):
        return {
            "ok": False,
            "error": result.get("error", "OKX 合约杠杆设置失败。"),
            "result": result,
            "error_summary": okx_error_summary(result),
            "raw_okx": okx_compact_raw_body(result),
            "config": okx_status(),
        }
    return {
        "ok": True,
        "payload": payload,
        "result": result.get("data", []),
        "request_id": result.get("request_id", ""),
    }


def okx_order_audit_context(body: dict[str, Any]) -> dict[str, Any]:
    """Carry paper-run context through OKX audit and ExecutionLedger rows."""
    context = {
        "source_order_id": str(body.get("_source_order_id") or body.get("source_order_id") or body.get("sourceOrderId") or "").strip(),
        "strategy_id": str(body.get("_strategy_id") or body.get("strategy_id") or body.get("strategyId") or "").strip(),
        "agent_id": str(body.get("_agent_id") or body.get("agent_id") or body.get("agentId") or "").strip(),
        "trading_unit_id": str(body.get("_trading_unit_id") or body.get("trading_unit_id") or body.get("tradingUnitId") or "").strip(),
        "expected_price": float_from_any(body.get("_expected_price") or body.get("expected_price") or body.get("expectedPrice")),
        "cycle_index": body.get("_cycle_index", body.get("cycle_index", "")),
        "cycle_label": str(body.get("_cycle_label") or body.get("cycle_label") or "").strip(),
    }
    return {key: value for key, value in context.items() if value not in {"", None, 0.0}}


def okx_submit_order(body: dict[str, Any]) -> dict[str, Any]:
    config = okx_config()
    if not config["simulated"]:
        return {"ok": False, "error": "OKX_SIMULATED_TRADING=false，当前不允许通过平台提交 OKX 实盘订单。", "config": okx_status()}
    if not config["trading_enabled"]:
        return {"ok": False, "error": "OKX_TRADING_ENABLED=false，OKX 模拟盘下单接口已关闭。", "config": okx_status()}
    if str(body.get("confirm", "")) != "OKX_SIMULATED_ONLY":
        return {"ok": False, "error": "提交 OKX 模拟盘订单必须带 confirm=OKX_SIMULATED_ONLY。", "config": okx_status()}
    audit_context = okx_order_audit_context(body)
    try:
        order = normalize_okx_order(body)
    except ValueError as exc:
        append_okx_audit(
            "order_blocked",
            {
                "ok": False,
                "error": str(exc),
                "order": {key: body.get(key) for key in ["instId", "tdMode", "side", "ordType", "sz", "px", "clOrdId", "posSide"] if key in body},
                **audit_context,
            },
        )
        return {"ok": False, "error": str(exc), "config": okx_status()}
    submit_gate = okx_simulated_submit_gate()
    if not submit_gate.get("ready"):
        append_okx_audit("order_blocked", {"ok": False, "error": submit_gate.get("reason", "OKX 模拟盘提交未就绪"), "order": order, "submit_gate": submit_gate, **audit_context})
        return {
            "ok": False,
            "error": submit_gate.get("reason", "OKX 模拟盘提交未就绪"),
            "config": okx_status(),
            "submit_gate": submit_gate,
        }
    allowed, message, risk = okx_pre_trade_check(order, submission_context=True)
    if not allowed:
        append_okx_audit("order_blocked", {"ok": False, "error": message, "order": order, "risk": risk, **audit_context})
        return {"ok": False, "error": message, "config": okx_status(), "risk": risk}
    leverage_result = okx_set_derivative_leverage(order)
    if not leverage_result.get("ok"):
        append_okx_audit("order_blocked", {"ok": False, "error": leverage_result.get("error", "OKX 合约杠杆设置失败。"), "order": order, "risk": risk, "leverage": leverage_result, **audit_context})
        return {
            "ok": False,
            "error": leverage_result.get("error", "OKX 合约杠杆设置失败。"),
            "config": okx_status(),
            "risk": risk,
            "leverage": leverage_result,
            "error_summary": leverage_result.get("error_summary", {}),
            "raw_okx": leverage_result.get("raw_okx", {}),
            "status_code": leverage_result.get("result", {}).get("status_code", 0) if isinstance(leverage_result.get("result"), dict) else 0,
            "okx_code": leverage_result.get("error_summary", {}).get("okx_code", "") if isinstance(leverage_result.get("error_summary"), dict) else "",
            "okx_msg": leverage_result.get("error_summary", {}).get("okx_msg", "") if isinstance(leverage_result.get("error_summary"), dict) else "",
            "data_errors": leverage_result.get("error_summary", {}).get("data_errors", []) if isinstance(leverage_result.get("error_summary"), dict) else [],
        }
    api_order = okx_api_order_payload(order)
    result = okx_request("POST", "/api/v5/trade/order", api_order, auth=True)
    if not result.get("ok"):
        error_summary = okx_error_summary(result)
        raw_okx = okx_compact_raw_body(result)
        audit = append_okx_audit(
            "order_submit_failed",
            {
                "ok": False,
                "order": order,
                "payload": api_order,
                "result": result,
                "error_summary": error_summary,
                "raw_okx": raw_okx,
                "risk": risk,
                "leverage": leverage_result,
                **audit_context,
            },
        )
        return {**result, "error_summary": error_summary, "raw_okx": raw_okx, "audit_id": audit["id"]}
    item_ok, item, item_message = okx_trade_item_result(result)
    if not item_ok:
        rejected_result = {**result, "error": item_message or result.get("error", ""), "data": [item]}
        error_summary = okx_error_summary(rejected_result)
        raw_okx = okx_compact_raw_body(result)
        audit = append_okx_audit(
            "order_submit_failed",
            {
                "ok": False,
                "order": order,
                "payload": api_order,
                "result": result,
                "error_summary": error_summary,
                "raw_okx": raw_okx,
                "risk": risk,
                "leverage": leverage_result,
                **audit_context,
            },
        )
        return {
            "ok": False,
            "error": item_message or "OKX 拒绝订单。",
            "result": item,
            "error_summary": error_summary,
            "raw_okx": raw_okx,
            "config": okx_status(),
            "risk": risk,
            "request_id": result.get("request_id", ""),
            "audit_id": audit["id"],
        }
    detail = {}
    detail_error = ""
    ord_id = str(item.get("ordId", "")).strip()
    cl_ord_id = str(item.get("clOrdId", order.get("clOrdId", ""))).strip()
    if ord_id or cl_ord_id:
        detail_payload = okx_order_detail_payload({"instId": order["instId"], "ordId": ord_id, "clOrdId": cl_ord_id})
        if detail_payload.get("ok"):
            detail = detail_payload.get("order", {})
        else:
            detail_error = str(detail_payload.get("error", "订单详情读取失败"))
    audit = append_okx_audit(
        "order_submitted",
        {
            "ok": True,
            "order": order,
            "payload": api_order,
            "result": item,
            "order_detail": detail,
            "detail_error": detail_error,
            "risk": risk,
            "leverage": leverage_result,
            "request_id": result.get("request_id", ""),
            **audit_context,
        },
    )
    return {
        "ok": True,
        "result": item,
        "order_detail": detail,
        "detail_error": detail_error,
        "config": okx_status(),
        "risk": risk,
        "audit_id": audit["id"],
        "request_id": result.get("request_id", ""),
    }


def okx_cancel_order(body: dict[str, Any]) -> dict[str, Any]:
    config = okx_config()
    if not config["simulated"]:
        return {"ok": False, "error": "OKX_SIMULATED_TRADING=false，当前不允许通过平台撤销 OKX 实盘订单。", "config": okx_status()}
    if not config["trading_enabled"]:
        return {"ok": False, "error": "OKX_TRADING_ENABLED=false，OKX 模拟盘撤单接口已关闭。", "config": okx_status()}
    if str(body.get("confirm", "")) != "CANCEL_OKX_SIMULATED_ORDER":
        return {"ok": False, "error": "撤销 OKX 模拟盘订单必须带 confirm=CANCEL_OKX_SIMULATED_ORDER。", "config": okx_status()}
    audit_context = okx_order_audit_context(body)
    payload = {"instId": str(body.get("instId", "")).upper().strip()}
    ord_id = str(body.get("ordId", "")).strip()
    cl_ord_id = str(body.get("clOrdId", "")).strip()
    if not payload["instId"] or not (ord_id or cl_ord_id):
        return {"ok": False, "error": "instId and ordId/clOrdId are required", "config": okx_status()}
    if ord_id:
        payload["ordId"] = ord_id
    if cl_ord_id:
        payload["clOrdId"] = cl_ord_id
    result = okx_request("POST", "/api/v5/trade/cancel-order", payload, auth=True)
    if not result.get("ok"):
        error_summary = okx_error_summary(result)
        raw_okx = okx_compact_raw_body(result)
        audit = append_okx_audit("order_cancel_failed", {"ok": False, "payload": payload, "result": result, "error_summary": error_summary, "raw_okx": raw_okx, **audit_context})
        return {**result, "error_summary": error_summary, "raw_okx": raw_okx, "audit_id": audit["id"]}
    item_ok, item, item_message = okx_trade_item_result(result)
    if not item_ok:
        rejected_result = {**result, "error": item_message or result.get("error", ""), "data": [item]}
        error_summary = okx_error_summary(rejected_result)
        raw_okx = okx_compact_raw_body(result)
        audit = append_okx_audit("order_cancel_failed", {"ok": False, "payload": payload, "result": result, "error_summary": error_summary, "raw_okx": raw_okx, **audit_context})
        return {
            "ok": False,
            "error": item_message or "OKX 拒绝撤单。",
            "result": item,
            "error_summary": error_summary,
            "raw_okx": raw_okx,
            "config": okx_status(),
            "request_id": result.get("request_id", ""),
            "audit_id": audit["id"],
        }
    audit = append_okx_audit(
        "order_cancelled",
        {"ok": True, "payload": payload, "result": item, "request_id": result.get("request_id", ""), **audit_context},
    )
    return {
        "ok": True,
        "result": item,
        "config": okx_status(),
        "audit_id": audit["id"],
        "request_id": result.get("request_id", ""),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "KaTradePlatform/0.1"

    # 静默高频轮询端点，避免终端日志刷屏
    _SILENT_PATHS = {"/api/health", "/api/market/quality", "/api/status", "/api/events/stream", "/api/paper/status"}
    def log_message(self, fmt: str, *args: Any) -> None:
        path = self.path.split("?")[0] if hasattr(self, "path") else ""
        if path in self._SILENT_PATHS:
            return
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
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            return

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
        # 开发阶段禁用静态文件缓存，确保 UI 修改即时生效
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_GET(self) -> None:
        try:
            route = urlparse(self.path)
            path = route.path
            params = parse_qs(route.query)
            if path in {
                "/",
                "/index.html",
                "/dashboard",
                "/runs",
                "/report",
                "/strategies",
                "/experiments",
                "/market",
                "/crypto",
                "/paper",
                "/live",
                "/orders",
                "/risk",
                "/data",
                "/events",
                "/config",
                "/agent",
                "/agents",
            }:
                self.send_static(STATIC_DIR / "index.html")
                return
            if path == "/styles.css":
                self.send_static(STATIC_DIR / "styles.css")
                return
            if path == "/app.js":
                self.send_static(STATIC_DIR / "app.js")
                return
            if path == "/api/health":
                self.send_json({"ok": True})
                return
            if path == "/api/status":
                config = parse_config()
                light = (params.get("light", [""])[0] or "").strip() == "1"
                # 每个组件用 _s() 包裹，单个失败不影响整体响应
                def _s(fn, fallback=None):
                    try: return fn()
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        return fallback if fallback is not None else {}
                self.send_json(
                    {
                        "ok": True,
                        "config": config,
                        "summary": _s(parse_summary, {}),
                        "equity_curve": _s(parse_equity_curve, []),
                        "events": _s(lambda: read_events(80), []),
                        "report": _s(read_report_json, {}),
                        "data_profile": {} if light else _s(data_profile, {}),
                        "data_provenance": {} if light else _s(data_provenance_payload, {}),
                        "history_server": history_server_status(config)
                        if config.get("history.mode", "local") == "remote"
                        else {},
                        "strategies": STRATEGY_CATALOG,
                        "sweep_parameters": _s(strategy_parameter_options, []),
                        "runs": [] if light else _s(lambda: compact_run_archive_rows(list_runs(), limit=10), []),
                        "experiments": [] if light else _s(lambda: compact_experiment_archive_rows(list_experiments(), limit=10), []),
                        "walk_forward_runs": [] if light else _s(lambda: list_walk_forward_runs()[:5], []),
                        "broker": _s(broker_status, {}),
                        "okx": _s(okx_status, {}),
                        "market_stream": _s(lambda: compact_market_stream_for_response(market_stream_snapshot()), {}),
                        "risk": _s(crypto_risk_status, {}),
                        "ops_readiness": {} if light else _s(ops_readiness_payload, {}),
                        "backend_core": _s(backend_core_status_payload, {}),
                        "market_quality": _s(lambda: read_json_file(MARKET_QUALITY_LATEST_PATH), {}),
                        "paper": _s(lambda: paper_status_payload(limit=1).get("paper", {}), {}),
                        "paper_markers": _s(lambda: read_paper_markers(limit=300), []),
                        "providers": _s(lambda: {
                            key: provider_status(value)
                            for key, value in PROVIDERS.items()
                        }, {}),
                        "agent_defaults": {
                            "provider": DEFAULT_AGENT_PROVIDER,
                            "model": provider_default_model(PROVIDERS[DEFAULT_AGENT_PROVIDER]),
                        },
                        "binaries": {
                            "backendd": BACKENDD_BIN.exists() or BACKENDD_CMAKE_BIN.exists(),
                            "traderd": (ROOT / "traderd").exists(),
                            "realtime_engine": REALTIME_ENGINE_BIN.exists() or REALTIME_ENGINE_CMAKE_BIN.exists(),
                            "replay_check": (ROOT / "replay_check").exists(),
                            "option_demo": (ROOT / "option_demo").exists(),
                            "pricing_check": (ROOT / "pricing_check").exists(),
                            "trading_unit_policy": TRADING_UNIT_POLICY_BIN.exists() or TRADING_UNIT_POLICY_CMAKE_BIN.exists(),
                        },
                    }
                )
                return
            if path == "/api/backend/summary":
                self.send_json({"backend_core": backend_core_status_payload(max_age_seconds=0.0)})
                return
            def _backend_route(route_path: str) -> str:
                query = urlencode(params, doseq=True)
                return route_path + (("?" + query) if query else "")
            if path == "/api/backend/orders/summary":
                self.send_json({"backend_orders": invoke_backendd_route(_backend_route("/api/backend/orders/summary"), timeout_seconds=3.0)})
                return
            if path == "/api/backend/orders/state":
                self.send_json({"backend_orders": invoke_backendd_route(_backend_route("/api/backend/orders/state"), timeout_seconds=3.0)})
                return
            if path == "/api/backend/orders/center":
                self.send_json({"backend_orders": invoke_backendd_route(_backend_route("/api/backend/orders/center"), timeout_seconds=3.0)})
                return
            if path == "/api/backend/orders/consistency":
                self.send_json({"backend_orders": invoke_backendd_route(_backend_route("/api/backend/orders/consistency"), timeout_seconds=3.0)})
                return
            if path == "/api/backend/orders/local_repair_plan":
                self.send_json({"backend_orders": invoke_backendd_route(_backend_route("/api/backend/orders/local_repair_plan"), timeout_seconds=3.0)})
                return
            if path == "/api/backend/orders/broker_terminal_sync_plan":
                self.send_json({"backend_orders": invoke_backendd_route(_backend_route("/api/backend/orders/broker_terminal_sync_plan"), timeout_seconds=3.0)})
                return
            if path == "/api/backend/orders/stale_broker_reconcile_plan":
                self.send_json({"backend_orders": invoke_backendd_route(_backend_route("/api/backend/orders/stale_broker_reconcile_plan"), timeout_seconds=3.0)})
                return
            if path == "/api/backend/account/positions":
                self.send_json({"backend_account": invoke_backendd_route(_backend_route("/api/backend/account/positions"), timeout_seconds=3.0)})
                return
            if path == "/api/backend/account/pnl":
                self.send_json({"backend_account": invoke_backendd_route(_backend_route("/api/backend/account/pnl"), timeout_seconds=3.0)})
                return
            if path == "/api/backend/account/attribution":
                self.send_json({"backend_account": invoke_backendd_route(_backend_route("/api/backend/account/attribution"), timeout_seconds=3.0)})
                return
            if path == "/api/backend/account/portfolio":
                self.send_json({"backend_account": invoke_backendd_route(_backend_route("/api/backend/account/portfolio"), timeout_seconds=3.0)})
                return
            if path == "/api/backend/account/equity":
                self.send_json({"backend_account": invoke_backendd_route(_backend_route("/api/backend/account/equity"), timeout_seconds=3.0)})
                return
            if path == "/api/backend/execution/trace_summary":
                self.send_json({"backend_execution_trace": invoke_backendd_route(_backend_route("/api/backend/execution/trace_summary"), timeout_seconds=3.0)})
                return
            if path == "/api/backend/execution/trace":
                self.send_json({"backend_execution_trace": invoke_backendd_route(_backend_route("/api/backend/execution/trace"), timeout_seconds=3.0)})
                return
            if path == "/api/backend/market/quality":
                self.send_json({"backend_market_quality": invoke_backendd_route(_backend_route("/api/backend/market/quality"), timeout_seconds=3.0)})
                return
            if path == "/api/config":
                self.send_json({"config": parse_config()})
                return
            if path == "/api/report":
                self.send_json({"report": read_report_json()})
                return
            if path == "/api/events/journal":
                self.send_json(platform_events_payload(params))
                return
            if path == "/api/events/stream":
                # GAP-028: SSE 实时推送平台事件
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                last_sent = 0
                started_at = time.monotonic()
                max_duration = 300  # R15: 5 分钟超时
                try:
                    while True:
                        if time.monotonic() - started_at > max_duration:
                            self.wfile.write(b"data: {\"event\":\"timeout\"}\n\n")
                            self.wfile.flush()
                            break
                        events = platform_events_payload({})
                        recent = (events.get("events", []) or [])[-20:]
                        latest_ts = 0
                        for e in recent:
                            ts = e.get("ts", 0)
                            if ts > last_sent:
                                data = json.dumps(e, ensure_ascii=False)
                                self.wfile.write(f"data: {data}\n\n".encode())
                                self.wfile.flush()
                                latest_ts = max(latest_ts, ts)
                        if latest_ts > last_sent:
                            last_sent = latest_ts
                        else:
                            self.wfile.write(b": heartbeat\n\n")
                            self.wfile.flush()
                        time.sleep(3)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                return
            if path == "/api/data/profile":
                self.send_json({"profile": data_profile()})
                return
            if path == "/api/data/provenance":
                self.send_json(data_provenance_payload())
                return
            if path == "/api/market/quality":
                mq = read_json_file(MARKET_QUALITY_LATEST_PATH) if MARKET_QUALITY_LATEST_PATH.exists() else {}
                self.send_json({"ok": True, "regime": mq.get("regime", {}) if isinstance(mq, dict) else {},
                                "regime_by_instrument": mq.get("regime_by_instrument", {}) if isinstance(mq, dict) else {},
                                "generated_at_ms": mq.get("generated_at_ms", 0) if isinstance(mq, dict) else 0})
                return
            if path == "/api/market/gold/summary":
                self.send_json({"summary": gold_market_summary()})
                return
            if path == "/api/market/gold/bars":
                self.send_json(gold_market_bars(params))
                return
            if path == "/api/market/okx/tickers":
                self.send_json(historyd_okx_tickers_payload(params))
                return
            if path == "/api/market/okx/candles":
                self.send_json(historyd_okx_candles_payload(params))
                return
            if path == "/api/market/okx/trades":
                self.send_json(okx_trades_payload(params))
                return
            if path == "/api/market/okx/stream/status":
                snapshot = market_stream_snapshot()
                response = compact_market_stream_for_response(snapshot)
                # 附加 ticker 数据供行情页展示
                response["tickers"] = snapshot.get("tickers", {})
                response["recent_trade_counts"] = {
                    str(inst): len(rows) if isinstance(rows, list) else 0
                    for inst, rows in (snapshot.get("recent_trades", {}) or {}).items()
                }
                response["recent_trade_count"] = sum(response["recent_trade_counts"].values())
                self.send_json({"ok": True, "stream": response, "config": okx_status()})
                return
            if path == "/api/market/okx/stream/trades":
                self.send_json(market_stream_trades_payload(params))
                return
            if path == "/api/market/data_quality":
                self.send_json(market_data_quality_payload())
                return
            if path == "/api/realtime/status":
                self.send_json(realtime_engine_status_payload(params))
                return
            if path == "/api/realtime/runner":
                self.send_json(realtime_engine_runner_payload(params))
                return
            if path == "/api/market/okx/series":
                self.send_json(historyd_okx_series_payload())
                return
            if path == "/api/market/okx/backfill":
                self.send_json(historyd_okx_backfill_status_payload())
                return
            if path == "/api/okx/positions":
                # 直接查 OKX 模拟盘持仓（独立于 paper engine 的本地账本）
                try:
                    result = okx_private_read_request("/api/v5/account/positions")
                    raw_positions = result.get("data", []) if result.get("ok") else []
                    # 并行拉取资金费率 (GAP-010)
                    funding_map = okx_funding_rate_map()
                    positions = []
                    for p in raw_positions:
                        pos = float(p.get("pos", 0) or 0)
                        if abs(pos) < 1e-10: continue
                        pos_side = (p.get("posSide") or "").lower()
                        if not pos_side or pos_side == "net":
                            pos_side = "long" if pos > 0 else "short"
                        inst_id = p.get("instId", "")
                        funding = funding_map.get(inst_id, {})
                        # 强平距离计算 (GAP-011)
                        liq_px = p.get("liqPx", "") or ""
                        mark_px = p.get("markPx", "") or ""
                        liq_warning = False
                        liq_distance_pct = None
                        try:
                            lp = float(liq_px)
                            mp = float(mark_px)
                            if lp > 0 and mp > 0:
                                liq_distance_pct = abs(mp - lp) / mp
                                liq_warning = liq_distance_pct < 0.05  # 5% 以内告警
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass
                        positions.append({
                            "inst_id": inst_id,
                            "pos": pos,
                            "side": pos_side,
                            "avg_px": p.get("avgPx", ""),
                            "mark_px": mark_px,
                            "liq_px": liq_px,
                            "liq_distance_pct": liq_distance_pct,
                            "liq_warning": liq_warning,
                            "upl": p.get("upl", ""),
                            "lever": p.get("lever", ""),
                            "mgn_mode": p.get("mgnMode", ""),
                            "funding_rate": funding.get("funding_rate", ""),
                            "funding_time": funding.get("funding_time", ""),
                            "funding_fee": p.get("fundingFee", ""),
                        })
                    self.send_json({"ok": True, "positions": positions, "count": len(positions)})
                except Exception as e:
                    self.send_json({"ok": False, "error": str(e), "positions": []})
                return
            if path == "/api/okx/reconcile":
                self.send_json(okx_reconcile_positions())
                return
            if path == "/api/crypto/okx/status":
                self.send_json({"okx": okx_status()})
                return
            if path == "/api/crypto/okx/tickers":
                self.send_json(okx_tickers_payload(params))
                return
            if path == "/api/crypto/okx/instruments":
                self.send_json(okx_instruments_payload(params))
                return
            if path == "/api/crypto/okx/candles":
                self.send_json(okx_candles_payload(params))
                return
            if path == "/api/paper/status":
                limit = bounded_int(params.get("limit", ["300"])[0], 300, 0, 20000)
                self.send_json(paper_status_payload(params.get("instId", [""])[0], limit=limit))
                return
            if path == "/api/orders/summary":
                self.send_json(paper_order_center_payload(params))
                return
            if path == "/api/orders/state":
                self.send_json(order_state_payload(params))
                return
            if path == "/api/orders/execution_trace":
                self.send_json(execution_trace_payload(params))
                return
            if path == "/api/orders/execution_ledger":
                self.send_json(execution_ledger_payload(params))
                return
            if path == "/api/orders/execution_failures":
                self.send_json(execution_failure_analysis_payload(params))
                return
            if path == "/api/orders/execution_quality":
                self.send_json(paper_execution_quality_payload(params))
                return
            if path == "/api/paper/automation_health":
                self.send_json(paper_automation_health_payload())
                return
            if path == "/api/paper/trading_units":
                engine = params.get("engine", ["python"])[0].lower()
                self.send_json(
                    paper_trading_units_payload(
                        include_agent_brief=True,
                        persist_agent_brief=True,
                        policy_engine="cxx" if engine == "cxx" else "python",
                    )
                )
                return
            if path == "/api/paper/stale_order_plan":
                self.send_json(paper_stale_order_plan_payload(params))
                return
            if path == "/api/paper/local_order_repair_plan":
                self.send_json(paper_local_order_repair_plan_payload(params))
                return
            if path == "/api/paper/broker_fill_backfill_plan":
                self.send_json(paper_broker_fill_backfill_plan_payload(params))
                return
            if path == "/api/paper/broker_terminal_sync_plan":
                self.send_json(paper_broker_terminal_sync_plan_payload(params))
                return
            if path == "/api/paper/stale_broker_reconcile_plan":
                self.send_json(paper_stale_broker_reconcile_plan_payload(params))
                return
            if path == "/api/paper/markers":
                limit = bounded_int(params.get("limit", ["0"])[0], 0, 0, 20000)
                self.send_json({"ok": True, "markers": read_paper_markers(params.get("instId", [""])[0], limit=limit)})
                return
            if path == "/api/paper/okx_plan":
                self.send_json(paper_okx_execution_plan_payload(params))
                return
            if path == "/api/paper/okx_baseline":
                self.send_json(paper_okx_baseline_status_payload())
                return
            if path == "/api/paper/okx_reconcile":
                self.send_json(paper_okx_reconciliation_payload(params))
                return
            if path == "/api/paper/okx_reconcile_history":
                self.send_json(paper_okx_reconciliation_history_payload(params))
                return
            if path == "/api/live/status":
                self.send_json({"broker": broker_status()})
                return
            if path == "/api/risk/status":
                self.send_json({"risk": crypto_risk_status()})
                return
            if path == "/api/ops/readiness":
                self.send_json({"readiness": ops_readiness_payload()})
                return
            if path == "/api/ops/preflight":
                self.send_json({"preflight": ops_preflight_payload({})})
                return
            if path == "/api/ops/alerts":
                self.send_json({"alerts": ops_alerts_payload()})
                return
            if path == "/api/ops/incidents":
                self.send_json({"incidents": ops_incidents_payload(params)})
                return
            if path == "/api/ops/death_modes":
                self.send_json({"death_modes": ops_death_modes_payload()})
                return
            if path == "/api/broker/okx/balance":
                self.send_json(okx_balance_payload())
                return
            if path == "/api/broker/okx/account_config":
                self.send_json(okx_account_config_payload())
                return
            if path == "/api/broker/okx/instruments":
                self.send_json(okx_instruments_payload(params))
                return
            if path == "/api/broker/okx/tradeability":
                self.send_json(okx_tradeability_payload(params))
                return
            if path == "/api/broker/okx/orders":
                self.send_json(okx_orders_payload(params))
                return
            if path == "/api/broker/okx/order_detail":
                self.send_json(okx_order_detail_payload(params))
                return
            if path == "/api/broker/okx/order_sync":
                self.send_json(okx_sync_recent_orders_payload(params))
                return
            if path == "/api/broker/okx/trades":
                self.send_json(okx_trades_payload(params))
                return
            if path == "/api/broker/okx/trial_order":
                self.send_json(okx_trial_order_payload(params))
                return
            if path == "/api/broker/okx/audit":
                limit = bounded_int(params.get("limit", ["100"])[0], 100, 0, 1000)
                self.send_json({"ok": True, "audit": read_okx_audit(limit), "config": okx_status()})
                return
            if path == "/api/broker/okx/network":
                self.send_json(okx_network_probe_payload())
                return
            if path == "/api/broker/okx/readiness":
                self.send_json(okx_readiness_payload({"public_check": params.get("public", ["true"])[0].lower() != "false"}))
                return
            if path == "/api/strategies":
                self.send_json({"strategies": STRATEGY_CATALOG})
                return
            if path == "/api/runs":
                self.send_json({"runs": list_runs()})
                return
            if path == "/api/runs/quality":
                self.send_json({"quality": runs_quality_payload()})
                return
            if path == "/api/run":
                params = parse_qs(route.query)
                run_id = params.get("id", [""])[0]
                self.send_json({"run": load_run_archive(run_id)})
                return
            if path == "/api/experiments":
                self.send_json({"experiments": list_experiments()})
                return
            if path == "/api/experiment":
                params = parse_qs(route.query)
                experiment_id = params.get("id", [""])[0]
                self.send_json({"experiment": load_experiment_archive(experiment_id)})
                return
            if path == "/api/walk_forward":
                walk_forward_id = params.get("id", [""])[0]
                if walk_forward_id:
                    self.send_json({"walk_forward": load_walk_forward_archive(walk_forward_id)})
                else:
                    self.send_json({"walk_forward_runs": list_walk_forward_runs()})
                return
            if path == "/api/agent/sessions":
                with AGENT_LOCK:
                    self.send_json({"sessions": list_agent_sessions()})
                return
            if path == "/api/agent/capital":
                agent_state_path = LOG_DIR / "agent" / "state.json"
                data = read_json_file(agent_state_path) if agent_state_path.exists() else {}
                self.send_json({"ok": True, "agent_capital": data, "attribution": agent_trade_attribution_payload({"limit": ["20000"], "recent": ["50"]})})
                return
            if path == "/api/agent/attribution":
                self.send_json(agent_trade_attribution_payload(params))
                return
            if path == "/api/agent/session":
                params = parse_qs(route.query)
                session_id = params.get("id", [""])[0]
                with AGENT_LOCK:
                    self.send_json({"session": load_agent_session(session_id)})
                return
            self.send_error(404)
        except Exception as exc:
            try:
                self.send_json({"ok": False, "error": str(exc)}, status=500)
            except Exception:
                pass

    def _check_auth(self) -> bool:
        """R16: 检查 API 认证。若设置了 KATRADE_API_TOKEN 则要求 X-API-Key 匹配。"""
        token = os.environ.get("KATRADE_API_TOKEN", "")
        if not token:
            return True  # 未配置 token 时允许所有请求（localhost 默认行为）
        try:
            api_key = self.headers.get("X-API-Key", "")
            return api_key == token
        except Exception:
            return False

    def do_POST(self) -> None:
        try:
            path = urlparse(self.path).path
            # R16: 受保护的端点列表
            _protected = {
                "/api/config",
                "/api/backtest",
                "/api/crypto/backtest",
                "/api/strategy_wash",
                "/api/parameter_sweep",
                "/api/paper/start",
                "/api/paper/stop",
                "/api/paper/resume",
                "/api/paper/okx/clear-guard",
                "/api/paper/trading_units/agent_leverage",
                "/api/paper/tick",
                "/api/paper/okx_baseline",
                "/api/paper/stale_order_cancel",
                "/api/paper/local_order_repair",
                "/api/paper/broker_fill_backfill",
                "/api/paper/broker_terminal_sync",
                "/api/paper/stale_broker_reconcile",
                "/api/orders/execution_calibration",
                "/api/realtime/replay",
                "/api/realtime/runner/start",
                "/api/realtime/runner/stop",
                "/api/okx/apikey",
                "/api/walk_forward",
                "/api/check",
                "/api/pricing",
                "/api/agent",
                "/api/agent/session",
                "/api/agent/message",
                "/api/market/okx/backfill",
                "/api/market/okx/backfill/cancel",
                "/api/broker/okx/order", "/api/broker/okx/cancel_order",
                "/api/broker/okx/config",
                "/api/broker/okx/order_preflight",
                "/api/risk/kill_switch", "/api/market/okx/stream/start",
                "/api/market/okx/stream/stop",
                "/api/ops/freeze",
                "/api/ops/preflight",
                "/api/ops/alerts/ack",
                "/api/ops/incidents/ack",
            }
            if path in _protected and not self._check_auth():
                self.send_json({"ok": False, "error": "unauthorized"}, status=401)
                return
            if path == "/api/config":
                body = self.read_json()
                write_config(body.get("config", {}))
                self.send_json({"ok": True, "config": parse_config()})
                return
            if path == "/api/backtest":
                self.send_json(run_backtest())
                return
            if path == "/api/crypto/backtest":
                self.send_json(run_crypto_backtest(self.read_json()))
                return
            if path == "/api/strategy_wash":
                self.send_json(run_strategy_wash(self.read_json()))
                return
            if path == "/api/paper/start":
                self.send_json(start_paper_runner(self.read_json()))
                return
            if path == "/api/paper/stop":
                self.send_json(stop_paper_runner(self.read_json()))
                return
            if path == "/api/paper/resume":
                self.send_json(resume_paper_runner(self.read_json()))
                return
            if path == "/api/paper/okx/clear-guard":
                self.send_json(clear_paper_okx_guard(self.read_json()))
                return
            if path == "/api/paper/trading_units/agent_leverage":
                self.send_json(write_trading_unit_agent_state(self.read_json()))
                return
            if path == "/api/realtime/replay":
                self.send_json(run_realtime_engine_replay_payload(self.read_json()))
                return
            if path == "/api/realtime/runner/start":
                self.send_json(start_realtime_engine_runner_payload(self.read_json()))
                return
            if path == "/api/realtime/runner/stop":
                self.send_json(stop_realtime_engine_runner_payload(self.read_json()))
                return
            if path == "/api/paper/tick":
                body = self.read_json()
                settings = paper_settings_from_body(body) if body else None
                if settings:
                    ensure_paper_okx_auto_submit_ready(settings)
                self.send_json(
                    paper_run_tick(
                        manual=True,
                        build_first=not (ROOT / "traderd").exists(),
                        settings_override=settings,
                    )
                )
                return
            if path == "/api/paper/okx_baseline":
                self.send_json(save_paper_okx_baseline_payload(self.read_json()))
                return
            if path == "/api/paper/stale_order_cancel":
                self.send_json(cancel_paper_stale_orders_payload(self.read_json()))
                return
            if path == "/api/paper/local_order_repair":
                self.send_json(apply_paper_local_order_repair_payload(self.read_json()))
                return
            if path == "/api/paper/broker_fill_backfill":
                self.send_json(apply_paper_broker_fill_backfill_payload(self.read_json()))
                return
            if path == "/api/paper/broker_terminal_sync":
                self.send_json(apply_paper_broker_terminal_sync_payload(self.read_json()))
                return
            if path == "/api/paper/stale_broker_reconcile":
                self.send_json(apply_paper_stale_broker_reconcile_payload(self.read_json()))
                return
            if path == "/api/orders/execution_calibration":
                self.send_json(apply_execution_calibration_payload(self.read_json()))
                return
            if path == "/api/parameter_sweep":
                self.send_json(run_parameter_sweep(self.read_json()))
                return
            if path == "/api/okx/apikey":
                self.send_json(save_okx_api_key(self.read_json()))
                return
            if path == "/api/walk_forward":
                self.send_json(run_walk_forward(self.read_json()))
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
                            str(body.get("provider", DEFAULT_AGENT_PROVIDER)),
                            str(body.get("model", DEFAULT_AGENT_MODEL)),
                        ),
                    }
                )
                return
            if path == "/api/agent/message":
                body = self.read_json()
                self.send_json(
                    send_agent_message(
                        str(body.get("session_id", "")),
                        str(body.get("provider", DEFAULT_AGENT_PROVIDER)),
                        str(body.get("model", DEFAULT_AGENT_MODEL)),
                        str(body.get("prompt", "")),
                    )
                )
                return
            if path == "/api/market/okx/backfill":
                self.send_json(historyd_okx_backfill_start_payload(self.read_json()))
                return
            if path == "/api/market/okx/backfill/cancel":
                self.send_json(historyd_okx_backfill_cancel_payload(self.read_json()))
                return
            if path == "/api/market/okx/stream/start":
                payload = market_stream_start_payload(self.read_json())
                if isinstance(payload.get("stream"), dict):
                    payload["stream"] = compact_market_stream_for_response(payload["stream"])
                self.send_json(payload)
                return
            if path == "/api/market/okx/stream/stop":
                payload = market_stream_stop_payload(self.read_json())
                if isinstance(payload.get("stream"), dict):
                    payload["stream"] = compact_market_stream_for_response(payload["stream"])
                self.send_json(payload)
                return
            if path == "/api/broker/okx/order":
                self.send_json(okx_submit_order(self.read_json()))
                return
            if path == "/api/broker/okx/config":
                self.send_json(save_okx_local_config(self.read_json()))
                return
            if path == "/api/broker/okx/order_preflight":
                self.send_json(okx_order_preflight_payload(self.read_json()))
                return
            if path == "/api/broker/okx/readiness":
                self.send_json(okx_readiness_payload(self.read_json()))
                return
            if path == "/api/broker/okx/cancel_order":
                self.send_json(okx_cancel_order(self.read_json()))
                return
            if path == "/api/risk/kill_switch":
                self.send_json(update_kill_switch(self.read_json()))
                return
            if path == "/api/ops/freeze":
                self.send_json(update_ops_automation_freeze(self.read_json()))
                return
            if path == "/api/ops/preflight":
                self.send_json({"preflight": ops_preflight_payload(self.read_json())})
                return
            if path == "/api/ops/alerts/ack":
                self.send_json(acknowledge_ops_alert(self.read_json()))
                return
            if path == "/api/ops/incidents/ack":
                self.send_json(acknowledge_ops_incident(self.read_json()))
                return
            self.send_error(404)
        except Exception as exc:
            try:
                self.send_json({"ok": False, "error": str(exc)}, status=500)
            except Exception:
                pass


def _auto_start_market_stream() -> None:
    """平台启动时自动连接 OKX 公共行情流（如果尚未运行）。"""
    try:
        if market_stream_thread_alive():
            return
        instruments = okx_instruments_config()
        url, env = okx_public_ws_url("auto")
        config = {"url": url, "environment": env, "instruments": instruments, "channels": ["trades", "tickers", "books5"]}
        print(f"[platform] 自动启动 OKX 行情流: {len(instruments)} 品种, {url}")
        market_stream_start_payload({"instIds": ",".join(instruments), "channels": ["trades", "tickers", "books5"], "environment": "auto"})
    except Exception as exc:
        print(f"[platform] 自动启动 OKX 行情流失败: {exc}")


def main() -> int:
    host = os.environ.get("KATRADE_HOST", "127.0.0.1")
    port = int(os.environ.get("KATRADE_PORT", "8787"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"KaTrade platform listening on http://{host}:{port}")
    print(f"Project root: {ROOT}")
    # 自动启动 OKX 行情流（在独立线程中，避免阻塞 HTTP 启动）
    threading.Thread(target=_auto_start_market_stream, name="auto-market-stream", daemon=True).start()
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
