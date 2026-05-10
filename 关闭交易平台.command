#!/usr/bin/env bash
cd "$(dirname "$0")/quant-system" || exit 1

echo "╔══════════════════════════════════════════╗"
echo "║       KaTrade 量化交易平台 — 关闭        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

bash stop.sh

if [[ -t 0 ]]; then
    echo ""
    echo "按回车键关闭此窗口..."
    read -r
fi
