# Quant System

一个基于 `cpp_quant_trading_system_architecture.md` 的最小 C++20 量化交易系统骨架。

当前版本先打通这条主链：

`Regime -> Signal Agents -> Portfolio Optimizer -> Risk Agent -> Execution -> Paper Broker`

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
- `NaiveExecutionAlgo`
- `PaperBrokerGateway`
- `TraderEngine`

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

## 下一步扩展

1. 接入真实行情和历史数据读取。
2. 加入事件总线和可重放事件日志。
3. 把回测引擎从单次调仓扩成多周期事件驱动。
4. 增加更多风控规则和 OMS 状态机。
5. 引入真实券商网关或模拟盘接口。
