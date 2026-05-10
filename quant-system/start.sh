#!/usr/bin/env bash
# ============================================================
# KaTrade — 一键启动
# 用法: bash start.sh  或  双击 启动交易平台.command
# ============================================================
set -eo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { printf "${GREEN}[start]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[warn]${NC}  %s\n" "$*"; }
err()  { printf "${RED}[err]${NC}   %s\n" "$*"; }

PLATFORM_PORT="${KATRADE_PORT:-8787}"
HISTORYD_PORT="${KATRADE_HISTORY_PORT:-8790}"
BACKENDD_PORT="${KATRADE_BACKENDD_PORT:-8791}"
PID_DIR="$ROOT/logs"
AUTOSTART_PAPER="${KATRADE_AUTOSTART_PAPER:-true}"
STARTUP_LOG_DIR="$ROOT/logs/startup"
AUTH_HEADER=()
if [[ -n "${KATRADE_API_TOKEN:-}" ]]; then
    AUTH_HEADER=(-H "X-API-Key: $KATRADE_API_TOKEN")
fi

cleanup() {
    echo ""
    warn "正在停止所有服务..."
    kill $(jobs -p) 2>/dev/null || true
    wait 2>/dev/null || true
    rm -f "$PID_DIR/platform.pid" "$PID_DIR/historyd.pid"
    warn "已停止。"
    echo ""
    echo "按回车键关闭此窗口..."
    read -r
    exit 0
}
trap cleanup SIGINT SIGTERM

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║       KaTrade 量化交易平台               ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# ---- 1. 编译 C++ 引擎 ----
log "检查 C++ 实时引擎..."
NEED_REBUILD=0
if [[ ! -f realtime_engine || ! -f backendd ]]; then
    NEED_REBUILD=1
else
    # 检查源码或 Makefile 是否比二进制新
    if [[ -n "$(find src apps include Makefile -newer realtime_engine -type f 2>/dev/null | head -1)" ]] || \
       [[ -n "$(find src/backend apps/backendd include/qt/backend Makefile -newer backendd -type f 2>/dev/null | head -1)" ]]; then
        NEED_REBUILD=1
    fi
fi

if [[ "$NEED_REBUILD" -eq 1 ]]; then
    warn "源码有更新，重新编译（约 30 秒）..."
    make realtime_engine backendd
    log "编译完成。"
else
    log "已是最新。"
fi

# ---- 2. 日志与 PID 目录 ----
mkdir -p "$PID_DIR" logs/market_stream logs/realtime_engine logs/market_quality logs/paper_trading logs/agent_sessions "$STARTUP_LOG_DIR"

# ---- 3. 启动 historyd ----
if lsof -i ":$HISTORYD_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    warn "historyd 已在运行（端口 $HISTORYD_PORT）。"
else
    log "启动 historyd（端口 $HISTORYD_PORT）..."
    python3 apps/historyd/server.py > "$STARTUP_LOG_DIR/historyd.log" 2>&1 &
    echo $! > "$PID_DIR/historyd.pid"
    sleep 1.5
fi

# ---- 4. 启动 C++ backendd ----
if lsof -i ":$BACKENDD_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    warn "backendd 已在运行（端口 $BACKENDD_PORT）。"
else
    log "启动 C++ backendd（端口 $BACKENDD_PORT）..."
    ./backendd serve --root "$ROOT" --config config/default.cfg --host 127.0.0.1 --port "$BACKENDD_PORT" > "$STARTUP_LOG_DIR/backendd.log" 2>&1 &
    echo $! > "$PID_DIR/backendd.pid"
    sleep 0.5
fi

# ---- 5. 启动 platform ----
if lsof -i ":$PLATFORM_PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    err "端口 $PLATFORM_PORT 已被占用！请先运行 stop.sh 停止旧进程。"
    exit 1
fi

log "启动平台（端口 $PLATFORM_PORT）..."
python3 apps/platform/server.py > "$STARTUP_LOG_DIR/platform.log" 2>&1 &
PLATFORM_PID=$!
echo $PLATFORM_PID > "$PID_DIR/platform.pid"

# ---- 6. 等待就绪 + 打开浏览器 ----
log "等待服务就绪..."
READY=0
for i in $(seq 1 30); do
    if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PLATFORM_PORT/api/health" 2>/dev/null | grep -q 200; then
        log "服务就绪！"
        READY=1
        break
    fi
    sleep 1
done

if [[ "$READY" -ne 1 ]]; then
    err "平台健康检查超时，请查看 $STARTUP_LOG_DIR/platform.log 或终端输出。"
    exit 1
fi

# ---- 7. 默认恢复虚拟盘 runner ----
# 这个动作只会走 OKX simulated trading 门禁。真实实盘、市价单、IOC/FOK 仍由平台阻断。
# 如只想启动 UI，不恢复自动策略，可执行：
#   KATRADE_AUTOSTART_PAPER=false bash start.sh
if [[ "$AUTOSTART_PAPER" == "true" || "$AUTOSTART_PAPER" == "1" || "$AUTOSTART_PAPER" == "yes" ]]; then
    log "恢复虚拟盘 runner（OKX simulated trading，仅限模拟盘）..."
    AUTOSTART_RESPONSE="$STARTUP_LOG_DIR/autostart_paper.json"
    AUTOSTART_STATUS="$STARTUP_LOG_DIR/autostart_paper.status"
    rm -f "$AUTOSTART_RESPONSE" "$AUTOSTART_STATUS"
    if curl -fsS \
        -X POST "http://127.0.0.1:$PLATFORM_PORT/api/paper/resume" \
        "${AUTH_HEADER[@]}" \
        -H "Content-Type: application/json" \
        -d '{"confirm":"RESUME_PAPER_TRADING_ONLY","okx_auto_confirm":"AUTO_OKX_SIMULATED_ONLY","source":"one_click_start"}' \
        -o "$AUTOSTART_RESPONSE" 2>"$STARTUP_LOG_DIR/autostart_paper.err"; then
        python3 - "$AUTOSTART_RESPONSE" > "$AUTOSTART_STATUS" <<'PY' || true
import json
import sys

path = sys.argv[1]
try:
    payload = json.load(open(path, encoding="utf-8"))
except Exception as exc:
    print(f"warn|无法解析虚拟盘恢复结果: {exc}")
    raise SystemExit(0)

paper = payload.get("paper") if isinstance(payload.get("paper"), dict) else {}
status = paper.get("status", "-")
settings = paper.get("settings") if isinstance(paper.get("settings"), dict) else {}
instruments = ",".join(str(x) for x in settings.get("instruments", [])[:6]) if isinstance(settings.get("instruments"), list) else "-"
last_skip = paper.get("last_skip_reason") or paper.get("last_error") or payload.get("error") or "-"
if payload.get("ok"):
    print(f"ok|虚拟盘 runner 已恢复: status={status}, instruments={instruments}")
else:
    print(f"warn|虚拟盘 runner 未恢复: {last_skip}")
PY
        IFS='|' read -r AUTOSTART_LEVEL AUTOSTART_MESSAGE < "$AUTOSTART_STATUS" || true
        if [[ "$AUTOSTART_LEVEL" == "ok" ]]; then
            log "$AUTOSTART_MESSAGE"
        else
            warn "${AUTOSTART_MESSAGE:-虚拟盘恢复结果未知，请查看 $AUTOSTART_RESPONSE}"
        fi
    else
        warn "虚拟盘 runner 自动恢复失败；平台仍已启动。详情见 $STARTUP_LOG_DIR/autostart_paper.err"
    fi
else
    warn "已跳过虚拟盘 runner 自动恢复（KATRADE_AUTOSTART_PAPER=$AUTOSTART_PAPER）。"
fi

echo ""
echo "  ${CYAN}总览:${NC}    http://127.0.0.1:$PLATFORM_PORT/dashboard"
echo "  ${CYAN}虚拟盘:${NC}  http://127.0.0.1:$PLATFORM_PORT/paper"
echo "  ${CYAN}行情:${NC}    http://127.0.0.1:$PLATFORM_PORT/market"
echo "  ${CYAN}配置:${NC}    http://127.0.0.1:$PLATFORM_PORT/config"
echo ""

# 自动打开浏览器
log "打开浏览器..."
sleep 1
open "http://127.0.0.1:$PLATFORM_PORT/dashboard" 2>/dev/null || true

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  平台运行中。按 Ctrl+C 停止所有服务。"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 等待 platform 进程
wait "$PLATFORM_PID" 2>/dev/null || true
cleanup
