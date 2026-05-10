# KaTrade — C++20 量化交易平台

这是一个本地加密量化研究、回测和 OKX/欧意模拟盘联调平台。项目目标是逐步把交易核心、策略、风控、执行、订单状态、行情处理和生产门禁迁到 Modern C++20；浏览器 UI 和过渡期本地 API 仍保留在 Python/HTML/CSS/JS 中。

当前唯一券商方向是 OKX/欧意。平台只允许 simulated trading 模拟盘自动提交，市价单、IOC、FOK 和真实实盘下单仍应被门禁阻断。

## 一键启动与关闭

双击根目录启动入口：

```text
/Users/snlnfy/Documents/量化交易/启动交易平台.command
```

当前启动链路会进入 `quant-system/start.sh`，检查并按需编译 C++ `realtime_engine`，启动 `historyd` 和本地 Web 平台，默认尝试恢复虚拟盘 runner，然后打开：

```text
http://127.0.0.1:8787/dashboard
```

双击根目录关闭入口：

```text
/Users/snlnfy/Documents/量化交易/关闭交易平台.command
```

关闭脚本调用 `quant-system/stop.sh`，只停止本机平台服务、historyd 和本项目残留 runner。它不会自动撤销 OKX 模拟盘已有挂单；撤单属于交易动作，必须走平台里的订单/执行链路。

如果只想打开 UI、不想自动恢复虚拟盘 runner，可以在终端执行：

```bash
cd /Users/snlnfy/Documents/量化交易/quant-system
KATRADE_AUTOSTART_PAPER=false bash start.sh
```

## 当前真实目录

```text
量化交易/
├── 启动交易平台.command
├── 关闭交易平台.command
├── doc/
│   ├── 00-醒来先看-平台状态与继续开发说明.md
│   └── 03-当前项目审查与改进指导书.md
└── quant-system/
    ├── Makefile
    ├── CMakeLists.txt
    ├── config/
    ├── data/
    ├── include/qt/
    │   ├── agent/
    │   ├── analysis/
    │   ├── data/
    │   ├── execution/
    │   ├── ops/
    │   ├── risk/
    │   └── storage/
    ├── src/
    │   ├── agent/
    │   ├── analysis/
    │   ├── data/
    │   ├── risk/
    │   ├── storage/
    │   └── strategies/
    ├── apps/
    │   ├── historyd/
    │   ├── platform/
    │   ├── realtime_engine/
    │   ├── replay_check/
    │   └── traderd/
    ├── tests/golden/
    ├── start.sh
    └── stop.sh
```

## 常用命令

```bash
cd /Users/snlnfy/Documents/量化交易/quant-system

# C++ 回放和定价回归
make check

# 编译实时 C++ 引擎
make realtime_engine

# 启动本地平台
bash start.sh

# 停止本地平台
bash stop.sh
```

每次改 C++ 核心后，至少执行：

```bash
make check
git diff --check
```

每次改 Python/前端后，至少执行：

```bash
python3 -m py_compile apps/platform/server.py apps/historyd/server.py
node --check apps/platform/static/app.js
```

## 已实现主线

- C++20 策略池、Regime、组合优化、风控、OMS、模拟 broker、组合账本、真实 broker 回报驱动的回测成交流与 golden replay。
- C++ `realtime_engine` 逐笔行情 runner 雏形。
- Python 本地 Web 平台，包含 `/dashboard`、`/market`、`/paper`、`/orders`、`/risk`、`/strategies` 等页面。
- OKX 公共行情、OKX simulated trading 配置、订单审计、执行轨迹、对账和陈旧挂单撤单基础设施。
- Kimi/DeepSeek 研究 Agent 接入，其中当前默认优先 Kimi。
- `traderd` 报告包含基础可追溯元数据：数据源、数据 hash、配置 hash、代码版本占位、成交模型版本和覆盖区间。

## 当前优先改进

详细指导书在：

```text
/Users/snlnfy/Documents/量化交易/doc/00-醒来先看-平台状态与继续开发说明.md
/Users/snlnfy/Documents/量化交易/doc/03-当前项目审查与改进指导书.md
```

下一阶段重点不是继续堆 UI，而是补齐生产化基础：

1. 保持 `make validate`、C++ 回放、启动链路和实时行情质量门禁持续可信。
2. 把 `traderd` 已有报告 metadata 推广到 C++ `BacktestReport`、walk-forward、参数扫描和 UI 展示。
3. 把 OKX 合约元数据、数量折算、失败码、撤单和对账链路进一步收敛到 C++20。
4. 拆分 `apps/platform/server.py` 中过大的交易业务逻辑，Python 只保留本地 UI/API 壳层。
5. 让 `/paper` 和 `/orders` 更直观展示每轮策略 tick、门禁阻断、OKX 提交结果和 broker fill 生命周期。

## 参考来源

- [Wayland Zhang《AI量化交易：从0到1》](https://www.waylandz.com/quant-book/)
