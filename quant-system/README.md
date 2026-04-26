# Quant System

一个基于 `cpp_quant_trading_system_architecture.md` 的最小 C++20 量化交易系统骨架。

当前版本定位为本地研究和纸面交易平台，不连接实盘券商，也不会替用户发出真实交易指令。
它已经具备一个可继续扩展的离线回测内核：

`CSV Replay -> Regime -> Signal Agents -> Portfolio Optimizer -> Risk Agent -> OMS -> Simulated Broker -> PortfolioBook -> Backtest`

同时已经开始补衍生品定价模块：

`Binomial Option Pricer -> European/American Call/Put -> Pricing Checks`

## 目录

```text
quant-system/
  include/qt/
  src/
    strategies/
  apps/traderd/
  apps/platform/
  docs/
  Makefile
  CMakeLists.txt
```

项目设计见 [`PROJECT_DESIGN.md`](/Users/snlnfy/Documents/量化交易/quant-system/docs/PROJECT_DESIGN.md)。
架构和扩展约定见 [`ARCHITECTURE.md`](/Users/snlnfy/Documents/量化交易/quant-system/docs/ARCHITECTURE.md)。

## 已实现模块

- `RuleBasedRegimeAgent`
- `MomentumAgent`
- `MeanReversionAgent`
- `DefensiveAgent`
- `DonchianBreakoutAgent`
- `MovingAverageCrossAgent`
- `MacdTrendAgent`
- `BollingerReversionAgent`
- `RsiReversionAgent`
- `RangeFadeAgent`
- `StrategyCatalog / StrategyFactory`
- `SimplePortfolioOptimizer`
- `RiskAgent`
- `EventBus`
- `OrderManagementSystem`
- `NaiveExecutionAlgo`
- `PaperBrokerGateway`
- `PortfolioBook`
- `TraderEngine`
- `BacktestEngine`
- `CsvReplayLoader`
- `HistoryDataClient`
- `RuntimeConfig`
- `Event log / report writers`
- `replay_check`
- `BinomialOptionPricer`
- `option_demo`
- `pricing_check`

## 本地运行

```bash
cd quant-system
make run
```

如果本机装了 CMake，也可以用：

```bash
cmake -S . -B build
cmake --build build
./build/traderd
```

默认运行会读取 [`config/default.cfg`](/Users/snlnfy/Documents/量化交易/quant-system/config/default.cfg)。

```bash
./traderd config/default.cfg
```

二叉树期权定价 demo：

```bash
./option_demo
```

本地中文 UI 客户端：

```bash
make platform
```

然后打开：

```text
http://127.0.0.1:8787
```

独立历史数据服务：

```bash
make historyd
```

默认监听：

```text
http://127.0.0.1:8790
```

如果历史服务跑在另一台 Mac 上，可以在那台机器上设置：

```bash
export KATRADE_HISTORY_HOST=0.0.0.0
export KATRADE_HISTORY_PORT=8790
export KATRADE_HISTORY_REPLAY_PATH=/path/to/bars.csv
make historyd
```

## 当前演示

`traderd` 现在默认会读取 `data/sample_bars.csv`，跑一个多周期回测。

也可以复制一份配置文件，然后把 `replay_path` 改成你自己的 CSV：

```bash
cp config/default.cfg config/my_run.cfg
# 编辑 config/my_run.cfg 里的 replay_path
./traderd config/my_run.cfg
```

CSV 格式：

```text
timestamp,symbol,exchange,open,high,low,close,volume
2026-01-02,AAPL,NASDAQ,180,187,179,186.5,5200
```

配置格式是简单的 `key=value`：

```text
replay_path=data/sample_bars.csv
event_log_path=logs/events.jsonl
report_json_path=logs/last_report.json
strategy.enabled=momentum,mean_reversion,defensive,donchian_breakout,ma_cross,macd_trend,bollinger_reversion,rsi_reversion,range_fade
history.mode=local
history.server_url=http://127.0.0.1:8790
history.contracts=AAPL.NASDAQ,MSFT.NASDAQ,GLD.ARCA
history.cache_dir=logs/cache/history
history.cache_ttl_seconds=1800
strategy.donchian.lookback=3
strategy.ma_cross.fast_window=2
strategy.ma_cross.slow_window=4
strategy.macd.fast_alpha=0.55
strategy.macd.slow_alpha=0.30
strategy.macd.signal_alpha=0.45
strategy.bollinger.window=4
strategy.bollinger.band_width=1.2
strategy.rsi.window=4
strategy.rsi.oversold=35
strategy.rsi.overbought=65
initial_cash=1000000
optimizer.max_single_weight=0.35
```

默认策略分组：

- 趋势市：`momentum`、`donchian_breakout`、`ma_cross`、`macd_trend`
- 震荡市：`mean_reversion`、`bollinger_reversion`、`rsi_reversion`、`range_fade`
- 防御/压力环境：`defensive`

历史数据模式：

- `history.mode=local`：直接读取 `replay_path`。
- `history.mode=remote`：从 `history.server_url` 按 `history.contracts` 拉取数据。
- 本地只保存短期缓存，缓存目录为 `history.cache_dir`。
- `history.cache_ttl_seconds=1800` 表示合约数据半小时不用就会在下一次拉数前删除。

远端历史服务配置样例见：

```bash
cp config/remote_history.example.cfg config/my_remote_history.local.cfg
./traderd config/my_remote_history.local.cfg
```

输出内容包括：

- 每个周期的 `Regime`
- 策略信号
- 风控决策
- OMS 跟踪的订单记录和状态
- 成交回报
- 账本净值、现金、已实现/未实现盈亏
- 事件流日志
- 结构化 JSON 报告、整体回测汇总和净值曲线

## 回归校验

项目现在自带一个 golden replay 检查器：

```bash
make check
```

它会：

1. 读取 [`config/default.cfg`](/Users/snlnfy/Documents/量化交易/quant-system/config/default.cfg)
2. 跑完整回测
3. 和 [`sample_metrics.txt`](/Users/snlnfy/Documents/量化交易/quant-system/tests/golden/sample_metrics.txt) 对比
4. 运行二叉树期权定价校验
5. 如果指标漂移超出容差，返回非 0 退出码

每次运行 `traderd` 还会生成：

- [`events.jsonl`](/Users/snlnfy/Documents/量化交易/quant-system/logs/events.jsonl)
- [`last_run_summary.txt`](/Users/snlnfy/Documents/量化交易/quant-system/logs/last_run_summary.txt)
- `last_report.json`

## UI 客户端与 Agent

[`platform`](/Users/snlnfy/Documents/量化交易/quant-system/apps/platform/server.py) 是一个本地 Web 控制台，后端只使用 Python 标准库。它可以：

- 运行回测
- 运行回归检查
- 运行期权定价 demo
- 编辑 `config/default.cfg`
- 查看事件日志、净值曲线、回测摘要
- 查看结构化回测报告：持仓、成交、信号、风控周期
- 查看并管理策略池：策略 ID、中文名、市场类型、启用状态、关键参数
- 检查 CSV 行情数据质量
- 保存每次运行档案到 `logs/runs/`
- 调用 Kimi 或 DeepSeek 作为研究 Agent

策略页可以直接保存 `strategy.enabled` 和策略参数。保存后运行回测时，
C++ 策略工厂会使用配置文件中的参数创建策略实例。

Agent API key 优先从服务端环境变量读取：

```bash
export MOONSHOT_API_KEY=your_kimi_key
export DEEPSEEK_API_KEY=your_deepseek_key
make platform
```

也可以复制本地专用配置文件：

```bash
cp config/api_key.config.example config/api_key.config
```

然后编辑 `config/api_key.config`：

```text
MOONSHOT_API_KEY=your_kimi_key
DEEPSEEK_API_KEY=your_deepseek_key

# 可选：如果你的 Kimi key 来自另一套平台，可以切换 endpoint。
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2.6

# Kimi Coding Plan 通过本机 Kimi Code CLI 桥接。
# KIMI_CLI_PATH 可选；平台会优先自动使用 VS Code 扩展里自带的 CLI。
KIMI_CLI_PATH=
KIMI_CODING_API_KEY=
KIMI_CODING_BASE_URL=https://api.kimi.com/coding/v1
KIMI_CODING_MODEL=kimi-code/kimi-for-coding
KIMI_CLI_MAX_STEPS=1
```

`config/api_key.config` 已经被 `.gitignore` 忽略，不会上传 GitHub。不要把真实
API key 写入任何会提交到仓库的配置文件。

Kimi Coding Plan 当前由本机 Kimi Code CLI 桥接。平台会把运行上下文和问题传给
CLI 的非交互 `--quiet` 模式，并把 CLI 工作目录限制在 `/tmp/katrade-kimi-agent-work`，
避免它直接修改项目文件。
如果你没有用 `kimi login` 完成 CLI 登录，可以在本地 `config/api_key.config` 中设置
`KIMI_CODING_API_KEY`，平台会只在启动 Kimi CLI 子进程时映射成官方文档里的
`KIMI_API_KEY`。

默认模型：

- Kimi: `kimi-k2.6`
- Kimi Coding Plan: `kimi-code/kimi-for-coding`
- DeepSeek: `deepseek-v4-flash`

平台页面：

- `/dashboard`: 总览和净值曲线
- `/runs`: 运行回测、检查、期权定价，并查看运行档案
- `/report`: 结构化复盘持仓、成交、信号和风控
- `/data`: CSV 行情数据体检
- `/events`: 事件流
- `/config`: 本地运行配置
- `/agent`: 多轮研究助手

## 期权定价模块

当前已经有一个 CRR 二叉树定价器：

- 欧式看涨 / 看跌
- 美式看涨 / 看跌
- Delta / Gamma / Theta 近似
- 与 Black-Scholes 的欧式价格对照

相关代码：

- [`pricing.hpp`](/Users/snlnfy/Documents/量化交易/quant-system/include/qt/pricing.hpp)
- [`pricing.cpp`](/Users/snlnfy/Documents/量化交易/quant-system/src/pricing.cpp)
- [`option_demo`](/Users/snlnfy/Documents/量化交易/quant-system/apps/option_demo/main.cpp)
- [`pricing_check`](/Users/snlnfy/Documents/量化交易/quant-system/apps/pricing_check/main.cpp)

## 下一步扩展

1. 接入真实行情和历史数据读取。
2. 把内存事件总线升级成 append-only 事件存储。
3. 增加限价单、撤单原因、部分成交超时策略。
4. 把二叉树定价器接进统一的 `pricing engine` 接口。
5. 补 Black-Scholes Greeks 和 Monte Carlo pricer。
