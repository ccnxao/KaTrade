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

输出内容包括：

- 每个周期的 `Regime`
- 策略信号
- 风控决策
- OMS 跟踪的订单记录和状态
- 成交回报
- 账本净值、现金、已实现/未实现盈亏
- 事件流日志
- 整体回测汇总和净值曲线

## 下一步扩展

1. 接入真实行情和历史数据读取。
2. 把事件总线从内存版升级为可重放事件日志。
3. 增加限价单、撤单原因、部分成交超时策略。
4. 引入真实券商网关或模拟盘接口。
5. 接入更长历史数据和参数化 Walk-forward 验证。
