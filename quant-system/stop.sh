#!/usr/bin/env bash
# ============================================================
# KaTrade 量化平台 — 一键清理脚本
# 停止所有相关进程：platform, historyd, realtime_engine
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { printf "${GREEN}[stop]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[warn]${NC} %s\n" "$*"; }
err()  { printf "${RED}[err]${NC}  %s\n" "$*"; }

PLATFORM_PORT="${KATRADE_PORT:-8787}"
HISTORYD_PORT="${KATRADE_HISTORY_PORT:-8790}"
BACKENDD_PORT="${KATRADE_BACKENDD_PORT:-8791}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
PID_DIR="$ROOT/logs"

KILLED=0

kill_port() {
    local port="$1" name="$2"
    local pids
    pids=$(lsof -i ":$port" -sTCP:LISTEN -t 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        while IFS= read -r pid; do
            if [[ -n "$pid" ]]; then
                log "停止 $name (PID=$pid, 端口 $port)..."
                kill "$pid" 2>/dev/null || true
                KILLED=$((KILLED + 1))
                for _ in $(seq 1 10); do
                    if ! kill -0 "$pid" 2>/dev/null; then
                        log "  $name 已退出。"
                        break
                    fi
                    sleep 0.5
                done
                if kill -0 "$pid" 2>/dev/null; then
                    warn "  $name 未响应，强制终止..."
                    kill -9 "$pid" 2>/dev/null || true
                fi
            fi
        done <<< "$pids"
    fi
}

kill_by_pidfile() {
    local pidfile="$1" name="$2"
    if [[ -f "$pidfile" ]]; then
        local pid
        pid=$(cat "$pidfile" 2>/dev/null || true)
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            log "停止 $name (PID=$pid, 来自 $pidfile)..."
            kill "$pid" 2>/dev/null || true
            KILLED=$((KILLED + 1))
            for _ in $(seq 1 10); do
                if ! kill -0 "$pid" 2>/dev/null; then break; fi
                sleep 0.5
            done
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$pidfile"
    fi
}

kill_by_name() {
    local pattern="$1" name="$2"
    local pids
    pids=$(pgrep -f "$pattern" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        while IFS= read -r pid; do
            if [[ -n "$pid" ]]; then
                log "停止 $name (PID=$pid)..."
                kill "$pid" 2>/dev/null || true
                KILLED=$((KILLED + 1))
                for _ in $(seq 1 10); do
                    if ! kill -0 "$pid" 2>/dev/null; then break; fi
                    sleep 0.5
                done
                if kill -0 "$pid" 2>/dev/null; then
                    kill -9 "$pid" 2>/dev/null || true
                fi
            fi
        done <<< "$pids"
    fi
}

echo ""
log "KaTrade 平台 — 停止所有服务"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. 尝试 PID 文件停止（更精确）
kill_by_pidfile "$PID_DIR/platform.pid" "platform server"
kill_by_pidfile "$PID_DIR/historyd.pid" "historyd"
kill_by_pidfile "$PID_DIR/backendd.pid" "backendd"

# 2. 端口占用兜底
kill_port "$PLATFORM_PORT" "platform server (端口)"
kill_port "$HISTORYD_PORT" "historyd (端口)"
kill_port "$BACKENDD_PORT" "backendd (端口)"

# 3. 残留进程清理
kill_by_name "backendd serve" "backendd (残留)"
kill_by_name "realtime_engine" "realtime_engine (残留)"
kill_by_name "apps/platform/server.py" "platform server (残留)"
kill_by_name "apps/historyd/server.py" "historyd (残留)"

# 4. 最终验证
echo ""
REMAIN_PLATFORM=$(lsof -i ":$PLATFORM_PORT" -sTCP:LISTEN -t 2>/dev/null || true)
REMAIN_HISTORY=$(lsof -i ":$HISTORYD_PORT" -sTCP:LISTEN -t 2>/dev/null || true)
REMAIN_BACKENDD=$(lsof -i ":$BACKENDD_PORT" -sTCP:LISTEN -t 2>/dev/null || true)
REMAIN_ENGINE=$(pgrep -f "realtime_engine" 2>/dev/null || true)

if [[ -z "$REMAIN_PLATFORM" && -z "$REMAIN_HISTORY" && -z "$REMAIN_BACKENDD" && -z "$REMAIN_ENGINE" ]]; then
    log "所有服务已停止。"
else
    warn "仍有残留进程，请手动检查："
    [[ -n "$REMAIN_PLATFORM" ]] && warn "  platform (端口 $PLATFORM_PORT): $REMAIN_PLATFORM"
    [[ -n "$REMAIN_HISTORY" ]]  && warn "  historyd (端口 $HISTORYD_PORT): $REMAIN_HISTORY"
    [[ -n "$REMAIN_BACKENDD" ]] && warn "  backendd (端口 $BACKENDD_PORT): $REMAIN_BACKENDD"
    [[ -n "$REMAIN_ENGINE" ]]   && warn "  realtime_engine: $REMAIN_ENGINE"
fi

echo ""
exit 0
