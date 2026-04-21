# Quant System

一个基于 `cpp_quant_trading_system_architecture.md` 的最小 C++20 量化交易系统骨架。

当前版本先打通这条主链，并补上一个简化的事件驱动回测闭环：

`Regime -> Signal Agents -> Portfolio Optimizer -> Risk Agent -> OMS -> Execution -> Paper Broker -> Backtest`

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
- `TraderEngine`
- `BacktestEngine`

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

`traderd` 现在会跑一个三阶段的小回测：

1. 趋势市场
2. 轮动市场
3. 危机市场

输出内容包括：

- 每个周期的 `Regime`
- 策略信号
- 风控决策
- OMS 跟踪的订单记录
- 成交回报
- 事件流日志
- 整体回测汇总

## 下一步扩展

1. 接入真实行情和历史数据读取。
2. 把事件总线从内存版升级为可重放事件日志。
3. 把回测引擎从样例驱动扩成历史数据驱动。
4. 增加更多风控规则和 OMS 状态机。
5. 引入真实券商网关或模拟盘接口。
