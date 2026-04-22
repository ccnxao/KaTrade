# Quant System

一个基于 `cpp_quant_trading_system_architecture.md` 的最小 C++20 量化交易系统骨架。

当前版本已经具备一个可继续扩展的离线回测内核：

`CSV Replay -> Regime -> Signal Agents -> Portfolio Optimizer -> Risk Agent -> OMS -> Simulated Broker -> PortfolioBook -> Backtest`

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

## 当前演示

`traderd` 现在默认会读取 `data/sample_bars.csv`，跑一个多周期回测。

也可以传入你自己的 CSV：

```bash
./traderd data/sample_bars.csv
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
4. 如果指标漂移超出容差，返回非 0 退出码

每次运行 `traderd` 还会生成：

- [`events.jsonl`](/Users/snlnfy/Documents/量化交易/quant-system/logs/events.jsonl)
- [`last_run_summary.txt`](/Users/snlnfy/Documents/量化交易/quant-system/logs/last_run_summary.txt)

## 下一步扩展

1. 接入真实行情和历史数据读取。
2. 把内存事件总线升级成 append-only 事件存储。
3. 增加限价单、撤单原因、部分成交超时策略。
4. 引入真实券商网关或模拟盘接口。
5. 接入更长历史数据和参数化 Walk-forward 验证。
