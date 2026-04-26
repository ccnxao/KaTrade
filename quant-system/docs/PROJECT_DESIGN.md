# KaTrade Project Design

本文档定义 KaTrade 从“本地回测样机”演进到“可研究、可验证、可纸面交易、可接近实盘准备”的项目设计。

重要边界：平台不能保证赚钱。平台的目标是把研究、数据、回测、风控、执行、监控做成可复现闭环，降低假收益、过拟合、错误数据、执行滑点和失控订单造成的风险。

## 1. 项目定位

KaTrade 的目标是本地优先的量化研究与交易平台：

- 支持 C++ 核心回测和交易逻辑。
- 支持独立历史数据服务器，可运行在另一台 Mac。
- 支持本地 Web 客户端，用于运行、配置、查看报告和管理策略。
- 支持 Kimi / DeepSeek / Kimi Code 类 Agent 作为研究助手。
- 默认只运行离线回测和 paper trading，不默认连接实盘券商。

非目标：

- 不承诺策略收益。
- 不在默认配置中执行实盘交易。
- 不把 API key、broker key、个人配置上传到 Git。
- 不让 Agent 默认修改项目文件或发出真实交易动作。

## 2. 设计原则

1. 数据先于策略：没有可验证的数据版本、交易日历、复权和坏点检测，策略收益不可信。

2. 研究与交易分层：策略只输出信号，组合层决定仓位，风控层裁剪，OMS 负责订单生命周期。

3. 回测必须接近真实执行：手续费、滑点、成交量限制、延迟、拒单和限价单都应进入模拟。

4. 所有实验必须可复现：每次回测都保存代码版本、配置、数据版本、策略参数、指标和报告。

5. 实盘能力默认关闭：live trading 必须经过独立配置、权限检查、风控检查和显式开关。

6. 风控不可绕过：任何订单进入 broker 前必须经过 pre-trade risk。

7. 本地隐私优先：API key 和交易凭证只保存在本地 ignored 配置或系统安全存储中。

## 3. 总体架构

```text
Data Plane
  historyd
  live_market_data
  reference_data
  calendar
  corporate_actions
  data_quality
  feature_store

Research Plane
  strategy_sdk
  strategy_catalog
  feature_engineering
  experiment_tracker
  parameter_sweep
  walk_forward_validation

Backtest Plane
  event_driven_simulator
  cost_model
  slippage_model
  fill_model
  benchmark_engine
  report_engine

Portfolio / Risk Plane
  portfolio_optimizer
  exposure_limits
  drawdown_control
  pre_trade_risk
  kill_switch
  risk_report

Execution Plane
  OMS
  paper_broker
  broker_adapters
  order_router
  reconciliation
  trade_journal

Platform Plane
  config_service
  job_runner
  scheduler
  artifact_store
  report_service
  agent_service
  auth / secrets

UI Client
  dashboard
  strategy_lab
  experiments
  backtests
  data_quality
  risk_center
  orders
  reports
  agent
```

## 4. 目标运行流

### 4.1 回测流

```mermaid
flowchart LR
  UI["Web UI"] --> Platform["platform server"]
  Platform --> JobRunner["job runner"]
  JobRunner --> TraderD["traderd"]
  TraderD --> ReplaySource["ReplayDataSource"]
  ReplaySource --> HistoryClient["HistoryDataClient"]
  HistoryClient --> HistoryD["historyd"]
  ReplaySource --> Engine["BacktestEngine"]
  Engine --> Strategy["Strategy Agents"]
  Strategy --> Optimizer["PortfolioOptimizer"]
  Optimizer --> Risk["RiskAgent"]
  Risk --> OMS["OMS / PaperBroker"]
  OMS --> Report["ReportWriter"]
  Report --> ArtifactStore["logs / experiments"]
  ArtifactStore --> UI
```

### 4.2 Paper Trading 流

```mermaid
flowchart LR
  LiveData["Live Market Data"] --> FeatureStore["Feature Store"]
  FeatureStore --> StrategyRuntime["Strategy Runtime"]
  StrategyRuntime --> Portfolio["Portfolio Optimizer"]
  Portfolio --> PreTradeRisk["Pre-Trade Risk"]
  PreTradeRisk --> OMS["OMS"]
  OMS --> PaperBroker["Paper Broker"]
  PaperBroker --> Reconcile["Reconciliation"]
  Reconcile --> RiskMonitor["Risk Monitor"]
  RiskMonitor --> UI["Risk Center"]
```

### 4.3 Live Trading 流

Live trading 在项目早期保持关闭。启用条件：

- broker adapter 已实现。
- pre-trade risk 已覆盖硬限制。
- kill switch 可用。
- paper trading 连续稳定运行。
- 对账差异可解释。
- 用户显式启用 live mode。

```mermaid
flowchart LR
  StrategyRuntime["Strategy Runtime"] --> PreTradeRisk["Pre-Trade Risk"]
  PreTradeRisk --> KillSwitch{"Kill Switch"}
  KillSwitch -->|allow| OMS["OMS"]
  KillSwitch -->|halt| Block["Block Orders"]
  OMS --> BrokerAdapter["Broker Adapter"]
  BrokerAdapter --> Broker["Broker API"]
  Broker --> ExecutionReports["Execution Reports"]
  ExecutionReports --> Reconciliation["Reconciliation"]
  Reconciliation --> AuditLog["Audit Log"]
```

## 5. 模块设计

### 5.1 Data Plane

职责：

- 提供历史行情、未来 live 行情、合约元数据、交易日历、复权信息。
- 检测坏点、缺口、重复行、异常价格、异常成交量。
- 给回测和研究提供可复现的数据版本。

当前已有：

- `apps/historyd/server.py`
- `HistoryDataClient`
- `ReplayDataSource`
- 短期缓存 TTL：`history.cache_ttl_seconds`

下一步设计：

```text
apps/historyd/
  server.py
  historyd/
    datasets.py
    contracts.py
    calendar.py
    quality.py
    storage.py
```

目标接口：

- `GET /api/health`
- `GET /api/datasets`
- `GET /api/contracts`
- `GET /api/bars.csv?contract=AAPL.NASDAQ&from=2020-01-01&to=2026-01-01`
- `GET /api/calendar?exchange=NASDAQ`
- `GET /api/quality?dataset=us_daily_v1`

数据版本字段：

```text
dataset_id
source
vendor
adjustment_mode
calendar_id
created_at
content_hash
row_count
quality_status
```

验收标准：

- 同一 `dataset_id` 多次回测结果一致。
- 缺失字段、重复 timestamp、非正价格、异常跳变能被报告。
- 本地交易系统只缓存远端数据，不长期保存。

### 5.2 Research Plane

职责：

- 管理策略目录、策略参数、实验配置。
- 支持参数扫描、walk-forward、样本内/样本外拆分。
- 保存每次实验的输入和输出。

当前已有：

- `StrategyCatalog / StrategyFactory`
- `/strategies` 策略管理页面
- 策略参数从 `config/default.cfg` 注入构造函数

目标策略接口保持：

```cpp
class ISignalAgent {
public:
    virtual std::vector<Signal> generate_signals(
        const std::vector<Bar>& bars,
        const FeatureFrame& features,
        const PortfolioSnapshot& portfolio,
        const RegimeState& regime) = 0;
};
```

策略规则：

- 策略不得直接下单。
- 策略不得读未来数据。
- 策略输出分数和置信度。
- 参数必须进入 catalog 和配置文件。

目标实验对象：

```json
{
  "experiment_id": "exp_20260426_001",
  "strategy_ids": ["ma_cross", "rsi_reversion"],
  "params": {
    "strategy.ma_cross.fast_window": "2",
    "strategy.ma_cross.slow_window": "8"
  },
  "dataset_id": "sample_bars_v1",
  "code_ref": "git commit or dirty hash",
  "run_mode": "backtest",
  "created_at": "2026-04-26T00:00:00Z"
}
```

需要新增：

- `ExperimentTracker`
- `ParameterSweepRunner`
- `WalkForwardRunner`
- `/experiments` 页面

验收标准：

- 每次回测都有实验 ID。
- UI 能比较多次实验收益、回撤、换手、成交次数。
- 参数扫描结果可排序、可复跑。

### 5.3 Backtest Plane

职责：

- 模拟真实市场执行路径。
- 输出净值曲线、订单、成交、风险、策略贡献。

当前已有：

- `BacktestEngine`
- `TraderEngine`
- `PaperBrokerGateway`
- `ReportWriter`

缺口：

- 成本模型过于简单。
- 成交模型不够真实。
- 没有延迟、限价单、拒单、涨跌停、盘口流动性。
- 没有 benchmark 对比。

目标撮合模型：

```text
OrderIntent
  -> PreTradeRisk
  -> ExecutionAlgo
  -> SimulatedExchange
  -> FillModel
  -> ExecutionReport
  -> PortfolioBook
```

成本模型：

- 固定佣金。
- 按成交额佣金。
- 印花税或交易税。
- 最小费用。
- 交易所费用。

滑点模型：

- fixed bps
- spread based
- volatility based
- participation rate based
- market impact model

成交限制：

- `max_participation_rate`
- `max_order_notional`
- `limit_price`
- `volume_available`
- `bar_high_low_constraint`

核心指标：

- total return
- annualized return
- volatility
- Sharpe / Sortino
- max drawdown
- turnover
- win rate
- profit factor
- exposure
- cost bps
- capacity estimate

验收标准：

- 回测报告能解释每笔成交价格来源。
- 成本翻倍后策略仍可评估。
- 修改成交模型会写入实验记录。

### 5.4 Portfolio / Risk Plane

职责：

- 把多策略信号变成目标组合。
- 在订单进入 OMS 前执行硬风控。
- 监控运行中风险。

当前已有：

- `SimplePortfolioOptimizer`
- `RiskAgent`
- gross / single weight 限制

目标风控层：

```text
Signal
  -> Signal Aggregation
  -> Portfolio Optimizer
  -> Portfolio Risk Check
  -> Order Intent
  -> Pre-Trade Risk Check
  -> OMS
```

硬限制：

- 单标的最大权重。
- 单策略最大权重。
- 单资产类别最大敞口。
- 最大总杠杆。
- 单笔最大订单金额。
- 单日最大交易金额。
- 单日最大亏损。
- 最大回撤熔断。
- 异常价格偏离限制。
- 重复订单限制。
- 交易时间限制。

Kill switch：

- 手动停止。
- 当日亏损超过阈值自动停止。
- broker 连接异常自动停止。
- 行情延迟超过阈值自动停止。
- 对账差异超过阈值自动停止。

监管参考：

- SEC Rule 15c3-5 强调市场接入前的金融与监管风险控制、错误订单限制、执行报告和定期审查。
- FINRA Market Access 也强调 broker-dealer 对市场接入风险控制和监督程序的要求。

这些规则不是说个人本地平台必须等同 broker-dealer 系统，而是说明真实交易系统的最低工程方向：订单不能绕过预交易风控。

验收标准：

- 所有订单都有 risk decision。
- 被拒订单必须记录原因。
- kill switch 开启后没有新订单进入 broker adapter。
- 风控配置可在 UI 查看，但 live 风控修改需要单独确认。

### 5.5 Execution Plane

职责：

- 管理订单生命周期。
- 支持 paper broker 和真实 broker adapter。
- 做成交回报、持仓对账、现金对账。

订单状态机：

```text
Created
  -> Submitted
  -> PartiallyFilled
  -> Filled
  -> Cancelled
  -> Rejected
```

目标扩展状态：

```text
PendingRisk
PendingSubmit
SubmitFailed
PendingCancel
CancelFailed
Expired
```

Broker adapter 接口：

```cpp
class IBrokerAdapter {
public:
    virtual SubmitResult submit(const OrderIntent& order) = 0;
    virtual CancelResult cancel(const std::string& broker_order_id) = 0;
    virtual std::vector<ExecutionReport> poll_reports() = 0;
    virtual BrokerPositions positions() = 0;
    virtual BrokerCash cash() = 0;
};
```

对账：

- 本地订单 vs broker 订单。
- 本地持仓 vs broker 持仓。
- 本地现金 vs broker cash。
- 本地成交 vs broker fills。

验收标准：

- paper 和 live 使用同一个 OMS 接口。
- 断线重连后能恢复订单状态。
- 重复提交不会生成重复订单。

### 5.6 Platform Plane

当前 `apps/platform/server.py` 是单文件零依赖服务，适合早期。本项目继续扩大后需要拆分：

```text
apps/platform/
  server.py
  platform/
    routes.py
    config_store.py
    job_runner.py
    experiment_store.py
    report_service.py
    strategy_service.py
    data_service.py
    agent_sessions.py
    providers.py
    security.py
```

Job Runner：

- 统一运行 `traderd`、`replay_check`、参数扫描。
- 捕获 stdout/stderr。
- 生成 run id / experiment id。
- 写 artifact。
- 支持队列和状态查询。

Artifact Store：

```text
logs/
  experiments/
    exp_.../
      experiment.json
      config.cfg
      report.json
      events.jsonl
      stdout.txt
      metrics.json
```

目标 API：

- `GET /api/status`
- `GET /api/strategies`
- `POST /api/strategies/config`
- `POST /api/backtests`
- `GET /api/backtests/:id`
- `GET /api/experiments`
- `GET /api/experiments/:id`
- `POST /api/sweeps`
- `GET /api/risk/status`
- `POST /api/risk/kill-switch`

### 5.7 UI Client

页面规划：

- `/dashboard`: 总览、最近运行、风险状态。
- `/strategies`: 策略池、启停、参数配置。
- `/experiments`: 实验列表、指标排序、参数对比。
- `/backtests`: 回测任务、运行日志。
- `/report`: 单次报告细节。
- `/data`: 数据质量、远端历史服务状态。
- `/risk`: 风控规则、敞口、kill switch。
- `/orders`: 订单、成交、对账。
- `/agent`: 多轮研究助手。

关键 UI 原则：

- 策略配置修改不直接触发真实交易。
- live mode 独立显示，默认关闭。
- 风控状态必须全局可见。
- 报告页面必须能追溯到实验配置。

### 5.8 Agent Service

Agent 的定位是研究助手：

- 解释回测结果。
- 检查指标异常。
- 建议实验方案。
- 总结风险。

默认限制：

- 不直接修改项目文件。
- 不发送订单。
- 不读取或输出真实 API key。
- 不绕过风控。

后续可扩展：

- 只读代码索引。
- 只读实验结果索引。
- 自动生成实验建议。
- 自动生成 PR 草案，但提交前需要用户确认。

## 6. 配置设计

当前配置仍是 `key=value`。短期继续保持简单，后续可迁移到 TOML/YAML。

核心配置组：

```text
history.*
strategy.*
optimizer.*
risk.*
execution.*
report.*
agent.*
```

策略配置：

```text
strategy.enabled=momentum,ma_cross,rsi_reversion
strategy.ma_cross.fast_window=2
strategy.ma_cross.slow_window=8
strategy.rsi.window=14
strategy.rsi.oversold=30
strategy.rsi.overbought=70
```

风控配置：

```text
risk.max_single_weight=0.30
risk.max_gross=0.80
risk.max_order_notional=50000
risk.max_daily_loss=10000
risk.kill_switch=false
```

执行配置：

```text
execution.mode=paper
execution.min_rebalance_delta=0.02
execution.max_participation_rate=0.04
execution.max_slippage_bps=50
```

## 7. 数据存储设计

短期继续使用文件：

- `config/default.cfg`
- `logs/events.jsonl`
- `logs/last_report.json`
- `logs/runs/*`
- `logs/experiments/*`

中期建议引入 SQLite：

```text
state/katrade.db
```

核心表：

```text
experiments
  id
  name
  status
  dataset_id
  config_hash
  code_ref
  created_at
  completed_at

experiment_metrics
  experiment_id
  total_return
  max_drawdown
  sharpe
  turnover
  total_cost
  final_equity

orders
  order_id
  experiment_id
  mode
  symbol
  exchange
  side
  quantity
  status
  created_at

fills
  fill_id
  order_id
  price
  quantity
  commission
  slippage_bps
  timestamp

risk_events
  id
  experiment_id
  severity
  rule_id
  action
  message
  created_at
```

## 8. 安全设计

必须保持：

- `config/api_key.config` ignored。
- `logs/` ignored。
- live broker key 不进入 Git。
- API response 不返回真实 key。
- Agent prompt 不包含真实 key。

后续增强：

- macOS Keychain 存储 broker secrets。
- 平台页面只显示 masked key 状态。
- live mode 需要独立配置文件，例如 `config/live.local.cfg`。
- 实盘开关需要二次确认。

## 9. 监控与审计

必须记录：

- 策略信号。
- 组合目标。
- 风控决策。
- 订单意图。
- OMS 状态变化。
- 成交回报。
- 对账结果。
- 用户配置修改。
- kill switch 变化。

监控指标：

- data freshness
- job status
- strategy heartbeat
- order latency
- reject rate
- daily pnl
- drawdown
- gross exposure
- broker connection status

## 10. 路线图

### P0 当前状态

已有：

- C++ 回测主链路。
- 本地 Web 平台。
- 独立历史数据服务。
- 策略 catalog 和策略参数。
- 结构化报告。
- Agent 会话。

### P1 研究可用

目标：

- Experiment Tracker。
- 参数扫描。
- 实验对比 UI。
- 数据质量报告。
- 指标扩展：Sharpe、turnover、cost、exposure。

验收：

- 每次回测可复现。
- 参数扫描结果可排序。
- 任意报告可追溯到配置和数据版本。

### P2 回测可信

目标：

- 事件驱动模拟器。
- 成本模型。
- 滑点模型。
- 成交量和延迟模型。
- benchmark 对比。

验收：

- 同一策略在不同成本假设下可对比。
- 每笔成交能解释价格来源。
- 报告包含成本敏感性。

### P3 Paper Trading

目标：

- paper runtime。
- 实时行情接入。
- OMS 状态恢复。
- 对账。
- 风控中心。

验收：

- paper 连续运行不丢订单状态。
- 风控触发能阻断订单。
- 对账差异可见。

### P4 Live Readiness

目标：

- broker adapter。
- live config 隔离。
- kill switch。
- 审计日志。
- 权限和确认机制。

验收：

- live mode 默认关闭。
- 所有 live 订单经过 pre-trade risk。
- 断线恢复后订单状态一致。
- 手动 kill switch 可立即阻断新订单。

## 11. 近期实现顺序

建议下一步按这个顺序做：

1. `ExperimentTracker` 文件版实现。
2. `/experiments` 页面。
3. 扩展 report metrics：Sharpe、turnover、cost bps、exposure。
4. 参数扫描 job。
5. 数据质量 job。
6. 风控中心页面。
7. 成本/滑点模型模块化。
8. paper runtime。

这个顺序的理由：先把研究闭环和可复现性做出来，再提升回测真实性，最后接近交易执行。

## 12. 参考

- SEC Rule 15c3-5: Risk Management Controls for Brokers or Dealers With Market Access
  - https://www.sec.gov/rules-regulations/2011/06/risk-management-controls-brokers-or-dealers-market-access
- FINRA Market Access
  - https://www.finra.org/rules-guidance/key-topics/market-access
