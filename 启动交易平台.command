#!/usr/bin/env bash
cd "$(dirname "$0")/quant-system" || exit 1

echo "╔══════════════════════════════════════════╗"
echo "║       KaTrade 量化交易平台               ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# 先通过项目停止脚本清理旧进程，避免端口冲突。
echo "[setup] 检查残留进程..."
bash stop.sh
sleep 1

# 启动
exec bash start.sh
