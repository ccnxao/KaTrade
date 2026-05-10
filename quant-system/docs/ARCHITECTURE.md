# KaTrade Architecture

KaTrade 的当前定位是本地量化研究、纸面交易与 OKX/欧意 simulated trading 联调平台。
系统默认不连接真实资金交易通道，也不会自动发出真实交易指令。

更完整的项目级设计、路线图和验收标准见
[`PROJECT_DESIGN.md`](/Users/snlnfy/Documents/量化交易/quant-system/docs/PROJECT_DESIGN.md)。

语言边界：除浏览器 UI 和过渡期本地 HTTP 壳层外，交易核心、策略、风控、执行、订单状态、行情处理和运维门禁优先使用 Modern C++20。Python 平台服务中的交易业务逻辑应逐步迁回 `include/qt/`、`src/` 和 `apps/*`。

## 目录结构

```text
quant-system/
  apps/
    traderd/              # C++ 回测主程序
    realtime_engine/      # C++ 逐笔 tick 运行时入口
    replay_check/         # golden replay 回归检查
    realtime_engine_check/# C++ 实时引擎回归检查
    option_demo/          # 期权定价演示
    pricing_check/        # 期权定价回归检查
    historyd/             # 独立历史行情 HTTP 服务
    platform/             # 本地 Web 平台
      server.py           # 标准库 HTTP 后端
      static/             # 前端页面、路由和样式
  config/
    default.cfg           # 可提交的默认运行配置
    api_key.config.example
  data/                   # 示例 CSV 行情
  docs/
    ARCHITECTURE.md       # 架构和扩展约定
  include/qt/             # C++ 公共接口
  src/
    strategies/           # 具体策略实现
      factory.cpp         # strategy.enabled 到策略对象的映射
      trend.cpp           # 趋势策略
      mean_reversion.cpp  # 震荡/均值回归策略
    agents.cpp            # 元策略、基础策略、防御策略
    history_client.cpp    # 远端历史数据客户端和短期缓存
  tests/golden/           # 回归基准
```

## C++ 分层

核心回测链路：

```text
ReplayDataSource
  -> CsvReplayLoader / HistoryDataClient
  -> TraderEngine
  -> RegimeAgent
  -> SignalAgents
  -> PortfolioOptimizer
  -> RiskAgent
  -> ExecutionAlgo
  -> OMS / PaperBrokerGateway
  -> PortfolioBook
  -> ReportWriters
```

主要接口边界：

- `types.hpp`: 领域对象，如 `Bar`、`Signal`、`TargetPortfolio`、`OrderRecord`。
- `agents.hpp`: Agent/策略接口和策略类声明。
- `portfolio.hpp`: 将多策略信号合成为目标组合。
- `risk.hpp`: 组合约束和风险裁剪。
- `execution.hpp` / `oms.hpp`: 纸面执行、OKX 模拟盘下单前门禁和订单生命周期。
- `market_data.hpp`: 逐笔 tick、数据质量检查和 allow/watch/block 决策。
- `realtime_engine.hpp`: tick 批次到策略周期的 C++ 实时运行接口。
- `report_io.hpp`: 事件、摘要和结构化 JSON 报告输出。
- `runtime_config.hpp`: `config/default.cfg` 的结构化读取。

C++ 实时链路：

```text
MarketTick CSV / platform OKX market_stream journal
  -> MarketDataQualityMonitor
  -> RealtimeEngine
  -> TraderEngine
  -> OMS / PaperBrokerGateway
  -> status.json / events.jsonl / market_quality/latest.json
```

当前 `apps/realtime_engine` 是本地回放入口，用于验证实时内核和状态输出；它已经能读取 tick CSV 和平台 OKX 公共行情 journal。平台 `/paper` 还没有完全改为由该进程接管，后续会把 Python runner 缩减为启动、停止和读取状态的壳层。

## 历史数据服务

历史数据服务独立放在 `apps/historyd/server.py`，可以运行在另一台 Mac 上。
交易系统和历史服务之间只通过 HTTP 通信，不共享进程内状态。

服务端接口：

- `GET /api/health`: 服务健康、数据行数、合约数量。
- `GET /api/contracts`: 可用合约列表。
- `GET /api/bars.csv?contract=AAPL.NASDAQ`: 单合约 CSV。
- `GET /api/replay.csv?contracts=AAPL.NASDAQ,MSFT.NASDAQ`: 多合约 CSV。
- `GET /api/okx/candles?instId=BTC-USDT&bar=1m&start=...&end=...&width=1200`: OKX 历史 K 线，服务端分页、缓存、聚合。
- `GET /api/okx/tickers`: OKX 配置合约 ticker。
- `GET /api/okx/bars.csv?contract=BTC-USDT.OKX&bar=1m`: OKX 合约 CSV，供回测远端模式复用。
- `GET /api/okx/series`: 查看 OKX 按天分片缓存覆盖。
- `GET /api/okx/backfill`: 查看后台回填任务。
- `POST /api/okx/backfill`: 启动 OKX 历史回填任务。
- `POST /api/okx/backfill/cancel`: 请求取消回填任务。

客户端配置：

```text
history.mode=remote
history.server_url=http://192.168.1.20:8790
history.contracts=AAPL.NASDAQ,MSFT.NASDAQ,GLD.ARCA
history.cache_dir=logs/cache/history
history.cache_ttl_seconds=1800
history.bar=1m
history.start=2026-04-01T00:00:00Z
history.end=2026-04-26T00:00:00Z
history.max_pages=40
```

缓存约束：

- 本地只缓存远端返回的合约 CSV，不作为长期数据仓库。
- 缓存按合约拆分，文件放在 `history.cache_dir` 下。
- 每次使用缓存都会刷新文件时间。
- 超过 `history.cache_ttl_seconds` 未使用的合约文件会在下一次拉数前删除。
- `history.cache_ttl_seconds=1800` 表示半小时，可按需要修改。
- OKX 分片缓存同样受 historyd 的 `KATRADE_HISTORY_CACHE_TTL_SECONDS` 控制；回填任务只是短期缓存预热，不是永久数据仓库。

## 策略放置约定

新增策略时按市场状态放置：

- 趋势市策略放在 `src/strategies/trend.cpp`
- 震荡/均值回归策略放在 `src/strategies/mean_reversion.cpp`
- 防御、现金管理、压力环境策略暂放在 `src/agent/agents.cpp`
- 策略创建逻辑只放在 `src/strategies/factory.cpp`

每个策略需要满足：

- 不读取未来数据。滚动窗口策略必须先用历史数据生成信号，再写入当前 bar。
- 输出 `Signal`，不直接下单。
- 分数保持在 `[-1, 1]` 附近，最终仓位由组合优化器和风控层决定。
- 注释要说明策略适用市场、输入假设和避免未来函数的位置。

## 平台后端约定

`apps/platform/server.py` 目前仍是单文件后端，原因是保持零依赖和本地可运行。
后续继续扩展时应拆为：

```text
apps/platform/
  server.py               # HTTP 路由和启动
  platform/
    config_store.py       # 配置读写
    reports.py            # 报告、运行档案、数据体检
    experiment_store.py   # 实验、参数扫描和 Walk-forward 归档
    agent_sessions.py     # Agent 会话和上下文
    providers.py          # Kimi/DeepSeek/Kimi CLI 适配
```

后端约束：

- 不输出真实 API key。
- 只写 `logs/`、`config/default.cfg` 等明确的本地工作文件。
- Agent 默认只读，不直接修改项目文件。
- 删除、上传、外部提交等动作必须单独确认。

虚拟盘接口：

- `GET /api/paper/status`: 当前 paper runner 状态、设置、执行策略、持仓、摘要、权益指标和标注；响应层会压缩 tick 历史、去重 ID、周期明细和权益样本，只返回计数与尾部摘要。
- `POST /api/paper/start`: 启动后台轮询，要求 `confirm=PAPER_TRADING_ONLY`；默认还要求 `okx_auto_confirm=AUTO_OKX_SIMULATED_ONLY` 并通过 OKX simulated key 环境检查。
- `POST /api/paper/stop`: 请求停止后台轮询，要求 `confirm=STOP_PAPER_TRADING`。
- `POST /api/paper/tick`: 手动运行一次策略链路，可按请求体临时更新虚拟盘设置；若 OKX 自动提交已武装，新生成的合格委托会走模拟盘提交门禁和 OKX 可交易性门禁。
- `GET /api/paper/markers?instId=BTC-USDT`: 读取指定合约的 K 线标注。
- `GET /api/paper/okx_plan?maxNotional=25`: 从最新虚拟盘订单生成 OKX SWAP/FUTURES 的 post_only 候选计划，按单笔 USDT 上限换算为合约张数并执行 C++ 预检与 OKX 可交易性评估，用于审查自动提交映射。
- `GET /api/paper/trading_units`: 读取交易单元影子分配，按趋势、均值回归、做市/高频单元聚合基础策略信号，并展示统计/agent 杠杆建议、有效杠杆裁剪和基础单元名义金额。可加 `?engine=cxx` 用 C++ `trading_unit_policy` 做一次策略单元风控决策验证。
- `POST /api/paper/trading_units/agent_leverage`: 由 agent 写回交易单元杠杆建议，必须带 `confirm=UPDATE_TRADING_UNIT_AGENT_LEVERAGE`，写入 `logs/agent_sessions/trading_unit_leverage.json`，再由平台风控裁剪。
- `logs/paper_trading/trading_unit_state.json`: 交易单元状态账本，记录当前有效杠杆、上次处理周期、上次 agent 来源和策略单元风控结果。账本只在新策略周期推进，避免 UI 刷新造成重复调杠。
- `GET /api/paper/okx_baseline`: 读取本地 OKX 对账基准摘要。
- `POST /api/paper/okx_baseline`: 保存当前 OKX 模拟盘余额和虚拟盘持仓为对账基准，要求 `confirm=SAVE_OKX_BASELINE`。
- `GET /api/paper/okx_reconcile`: 只读对账本地虚拟盘与 OKX 模拟盘从基准之后的持仓净变化，并同步最近订单状态。
- `GET /api/paper/okx_reconcile_history?limit=50`: 只读读取本地 OKX 对账流水 `logs/reconciliation/okx_reconcile.jsonl`，用于回看每次对账状态、持仓差异、订单状态变化和检查分布。

OKX 公共行情接口：

- `GET /api/market/okx/stream/status`: 读取平台内置 OKX 公共 WebSocket 行情泵状态、订阅、最近消息、缓存 tick 和本地日志路径。
- `POST /api/market/okx/stream/start`: 启动只读公共行情流，默认订阅配置合约的 `trades`、`tickers`、`books5`。
- `POST /api/market/okx/stream/stop`: 停止公共行情流。
- `GET /api/market/okx/stream/trades?instId=BTC-USDT&limit=100`: 读取 WS 缓冲中的最近逐笔成交。
- `GET /api/market/okx/trades?instId=BTC-USDT&limit=100`: 自动优先返回新鲜 WS 缓冲；WS 未运行或不新鲜时回退 REST 公开成交。

统一事件接口：

- `GET /api/events/journal?limit=200`: 读取 `logs/event_journal/events.jsonl` 中的轻量实时事件摘要，覆盖行情流、虚拟盘 tick、策略信号、风控、纸面委托和纸面成交。
- `GET /api/realtime/status?limit=100`: 只读读取 C++ 实时引擎输出的 `status.json`、`events.jsonl` 和 `market_quality/latest.json`；该接口不启动进程、不连接 OKX、不下单。
- `POST /api/realtime/replay`: 要求 `confirm=RUN_CXX_REALTIME_REPLAY`，`source=csv` 时运行项目目录内 tick CSV 回放，`source=market_stream` 时读取平台 OKX 公共行情 journal；该接口不连接 OKX 私有 API、不下单。
- `GET /api/realtime/runner`: 查看 C++ 实时行情质量 runner 是否常驻运行，以及最新状态/质量文件。
- `POST /api/realtime/runner/start`: 要求 `confirm=START_CXX_REALTIME_WATCH`，启动 C++ `realtime_engine --watch` 尾读 `logs/market_stream/okx_public.jsonl`，持续刷新 `logs/market_quality/latest.json`；只读公共行情 journal，不连接 OKX 私有 API、不下单。逐笔 `/paper` runner 启动和恢复时会自动准备该进程。
- `POST /api/realtime/runner/stop`: 要求 `confirm=STOP_CXX_REALTIME_WATCH`，停止 C++ 实时行情质量 runner。

运维门禁接口：

- `GET /api/ops/readiness`: 只读聚合 runner、行情流、OKX 模拟盘、自动提交、kill switch、数据质量、执行决策轨迹、OKX 对账健康、陈旧挂单和事件错误，给出 allow/watch/block 决策与建议动作。
- `POST /api/ops/freeze`: 开关自动化冻结；开启要求 `confirm=ENABLE_AUTOMATION_FREEZE`，解除要求 `confirm=DISABLE_AUTOMATION_FREEZE`。冻结只阻断新的策略 tick、runner 启动/恢复和 OKX 自动提交，不撤销已有挂单。
- `GET /api/ops/alerts`: 从 readiness 失败项和最近事件错误生成本地运维告警。
- `POST /api/ops/alerts/ack`: 本地确认运维告警，要求 `confirm=ACK_OPS_ALERT`；确认不改变真实门禁状态。

订单状态接口：

- `GET /api/orders/summary?limit=300`: 只读汇总本地虚拟盘订单生命周期、成交回报、挂单/过期记录、订单状态机、OKX 对账流水和 OKX 本地审计。
- `GET /api/orders/state?limit=300`: 读取 `logs/order_journal/orders.jsonl` 并按 `paper_session_id + order_id` 归约订单状态，用于执行回放、UI 排查和后续 C++ OMS 状态机衔接；成交事件同时携带本次平仓数量、毛盈亏、手续费分摊、净盈亏和累计已实现盈亏。
- `GET /api/orders/execution_trace?limit=300`: 读取 `logs/execution_trace/decisions.jsonl`，追踪策略源委托、OKX 候选映射、自动提交门禁、可交易性、预估成本、阻断原因和提交结果。
- `GET /api/orders/execution_ledger?limit=300`: 读取 `logs/execution_ledger/events.jsonl`，按 C++ `ExecutionLedgerEvent` 字段返回 OKX 模拟盘提交、确认、成交、撤单、同步和失败事实；该接口只读，不连接 OKX。
- `GET /api/orders/execution_quality?limit=1000`: 只读对比本地虚拟盘成交率/滑点和 OKX 模拟盘审计成交率/滑点，输出校准等级、样本置信度、参数建议和配置补丁预览，为后续执行模型校准提供样本。
- `POST /api/orders/execution_calibration`: 需要 `confirm=APPLY_EXECUTION_CALIBRATION`，只把当前执行校准建议写入本地 `config/default.cfg` 的 `execution.*` 项，并先备份到 `logs/config_backups/`；该接口不连接 OKX，不提交订单。

OKX 私有接口：

- `GET /api/broker/okx/network`: 探测 OKX REST 候选域名，默认大陆访问使用官方 `https://www.okx.com`。
- `GET /api/broker/okx/instruments?instType=SWAP`: 读取当前 OKX 合约白名单的最小数量、数量步长、价格 tick 和 `ctVal`。
- `GET /api/broker/okx/tradeability?instType=SWAP&notional=25`: 只读评估白名单合约的规则状态、ticker 价差、最小下单、WS 五档深度、24h 成交量和估计成本，返回 `pass/warn/block`、半价差成本、深度压力成本和预计 USDT 成本。
- `POST /api/broker/okx/config`: 保存本地 ignored OKX 配置，不回显 secret/passphrase。
- `POST /api/broker/okx/readiness`: 公开/只读私有 API 预检。
- `GET /api/broker/okx/trial_order?instId=BTC-USDT-SWAP&side=buy&notional=5`: 生成一笔小额 SWAP post_only 试挂单并预检，不提交订单。
- `POST /api/broker/okx/order_preflight`: 下单前风控、合约规则和挂单规则检查。
- `POST /api/broker/okx/order`: 仅 OKX simulated trading 下提交 SWAP/FUTURES 的 limit/post_only 模拟挂单。
- `POST /api/broker/okx/cancel_order`: 仅 OKX simulated trading 下撤销模拟单。
- `GET /api/broker/okx/order_detail`: 查询单笔 OKX 订单详情。
- `GET /api/broker/okx/order_sync`: 从本地审计记录同步最近 OKX 订单状态，状态变化会追加 `order_synced` 审计。
- `GET /api/broker/okx/audit`: 读取本地 `logs/broker/okx_audit.jsonl` 审计记录。

虚拟盘执行策略：

- `/paper` runner 默认要求 `PAPER_REQUIRE_OKX_AUTO_SUBMIT=true`，策略生成的合格委托必须挂到 OKX simulated trading。
- 自动提交默认只允许 SWAP/FUTURES、`post_only`/limit，仍受 C++ `okx_policy` 门禁、OKX 可交易性、kill switch、单笔名义、活跃挂单上限 10、行情延迟和引擎耗时保护。
- OKX 可交易性批量读取公开规则、ticker 和内存中的 `books5` WS 深度；`block` 必须阻断，`warn` 默认只展示，也可通过 `okx_auto_block_tradeability_warn` 升级为阻断。预计成本由 maker fee、半价差和深度压力组成，阈值为 `execution.max_expected_cost_bps`。
- 自动提交每次提交、失败或阻断都会追加执行决策轨迹；提交、撤单、订单详情同步和失败还会追加执行事实账本 `logs/execution_ledger/events.jsonl`。两类日志都只写本地 JSONL，不包含 API secret，用于回答“策略为什么没在 OKX 上出现订单”和“这笔 OKX 委托后来发生了什么”。
- 合约基础设施当前只进入影子风控：C++ `validate_okx_derivatives_order` 能校验 SWAP/FUTURES、逐仓/全仓、交易所杠杆、总有效杠杆和交易单元杠杆；C++ `trading_unit_policy` 可独立裁剪 agent 给出的单元杠杆。Python `/paper` 只展示交易单元分配，不向 OKX 提交合约订单。
- 纯本地 paper broker 仅保留为开发诊断路径，需要显式设置 `PAPER_REQUIRE_OKX_AUTO_SUBMIT=false` 或后端调试确认。

## 前端约定

当前前端仍是无构建的 HTML/CSS/JS，保证本地直接打开平台即可用。
继续扩展时可以拆为：

```text
apps/platform/static/
  index.html
  styles.css
  app.js                  # 启动和路由
  ui/
    dashboard.js
    report.js
    data.js
    agent.js
```

前端页面职责：

- `/dashboard`: 总览和入口。
- `/runs`: 运行任务、运行档案、质量门禁和最近两次运行对比。
- `/report`: 持仓、订单、策略贡献、风控复盘。
- `/strategies`: 策略池、市场类型、启用状态。
- `/experiments`: 实验归档、参数扫描、Walk-forward 样本外验证和实验对比。
- `/market`: OKX 实时/历史行情终端、公共 WS 行情流启停、后台回填任务、虚拟盘交易标注、MA/布林带/VWAP 图层和黄金 1m 大窗口图。
- `/crypto`: OKX BTC、ETH、XAUT 行情、K 线指标图层和加密策略回测入口。
- `/paper`: paper runner，负责启动/停止策略轮询、手动 tick、策略集选择、逐笔模式自动准备只读 OKX 行情流、OKX 模拟盘自动提交、陈旧模拟盘挂单自动撤单、实时引擎性能遥测、自动提交性能门禁、权益曲线、持仓摘要、成交流水和交易标注表。
- `/paper` 同时暴露行情数据质量快照，覆盖逐笔缓存、重复成交 ID、时间戳顺序、REST 兜底和数据新鲜度；逐笔模式默认要求新鲜 C++ 行情质量报告，缺失、陈旧或 `block` 都会跳过策略和订单生成。
- `/live`: OKX/欧意连接状态和安全边界；当前平台唯一交易券商为 OKX。
- `/orders`: 只读订单中心，汇总虚拟盘订单、订单状态机、执行决策轨迹、执行事实账本、成交回报、每次平仓盈亏、执行质量校准、挂单/过期记录和 OKX 本地审计。
- `/risk`: kill switch、单笔名义金额上限、敞口限制和订单前风控。
- `/data`: CSV 数据体检。
- `/events`: 统一事件 journal，包括行情流、策略周期、风控、纸面委托和成交摘要。
- `/agent`: 多轮研究助手。

## 当前策略集合

策略模块由 `strategy_catalog()` 和 `make_signal_agents()` 统一管理。
新增策略必须先进入 catalog，再由工厂创建，避免主程序出现分散的策略开关。
策略参数从 `config/default.cfg` 进入 `RuntimeConfig`，再注入策略构造函数。
平台策略页保存配置后，下一次回测会使用这些参数。

趋势市：

- `momentum`: 正收益动量。
- `donchian_breakout`: 唐奇安通道突破。
- `ma_cross`: 快慢均线价差。
- `macd_trend`: MACD 动量。

震荡市：

- `mean_reversion`: 大幅日内波动反向。
- `bollinger_reversion`: 布林带 z-score 反向。
- `rsi_reversion`: RSI 高低位反向。
- `range_fade`: 收盘靠近日内区间边缘时反向。

防御环境：

- `defensive`: 压力环境偏向防御资产。

当前可配置参数：

- `strategy.donchian.lookback`
- `strategy.ma_cross.fast_window`
- `strategy.ma_cross.slow_window`
- `strategy.macd.fast_alpha`
- `strategy.macd.slow_alpha`
- `strategy.macd.signal_alpha`
- `strategy.bollinger.window`
- `strategy.bollinger.band_width`
- `strategy.rsi.window`
- `strategy.rsi.oversold`
- `strategy.rsi.overbought`
- `metrics.drawdown_stride`

Donchian、MA、Bollinger、RSI 指标由 C++ 策略实例维护滚动状态；`metrics.drawdown_stride=1` 默认精确最大回撤，调大后按周期采样回撤以降低大样本运行成本。
