# Quant System

一个基于 `cpp_quant_trading_system_architecture.md` 的最小 C++20 量化交易系统骨架。

当前版本已经具备一个可继续扩展的离线回测内核：

`CSV Replay -> Regime -> Signal Agents -> Portfolio Optimizer -> Risk Agent -> OMS -> Simulated Broker -> PortfolioBook -> Backtest`

同时已经开始补衍生品定价模块：

`Binomial Option Pricer -> European/American Call/Put -> Pricing Checks`

## 目录

```text
quant-system/
  include/qt/
  src/
  apps/traderd/
  Makefile
  CMakeLists.txt
```

## 已实现模块

- `RuleBasedRegimeAgent`
- `MomentumAgent`
- `MeanReversionAgent`
- `DefensiveAgent`
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
initial_cash=1000000
optimizer.max_single_weight=0.35
```

输出内容包括：

- 每个周期的 `Regime`
- 策略信号
- 风控决策
- OMS 跟踪的订单记录和状态
- 成交回报
- 账本净值、现金、已实现/未实现盈亏
- 事件流日志
- 整体回测汇总和净值曲线

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

## UI 客户端与 Agent

[`platform`](/Users/snlnfy/Documents/量化交易/quant-system/apps/platform/server.py) 是一个本地 Web 控制台，后端只使用 Python 标准库。它可以：

- 运行回测
- 运行回归检查
- 运行期权定价 demo
- 编辑 `config/default.cfg`
- 查看事件日志、净值曲线、回测摘要
- 调用 Kimi 或 DeepSeek 作为研究 Agent

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
```

`config/api_key.config` 已经被 `.gitignore` 忽略，不会上传 GitHub。不要把真实
API key 写入任何会提交到仓库的配置文件。

默认模型：

- Kimi: `kimi-k2.6`
- DeepSeek: `deepseek-v4-flash`

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
