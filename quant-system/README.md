# Quant System

一个基于 `cpp_quant_trading_system_architecture.md` 演进的 C++20 加密量化研究与虚拟盘交易平台。

当前最重要的使用交接文档见 [`00-醒来先看-平台状态与继续开发说明.md`](/Users/snlnfy/Documents/量化交易/doc/00-醒来先看-平台状态与继续开发说明.md)，继续开发指导书见 [`03-当前项目审查与改进指导书.md`](/Users/snlnfy/Documents/量化交易/doc/03-当前项目审查与改进指导书.md)。

当前版本定位为本地研究、回测、逐笔虚拟盘和 OKX/欧意模拟盘联调平台；仍不允许真实实盘、市价单、IOC 或 FOK。虚拟盘默认走 OKX simulated trading，策略合格委托会优先映射为 SWAP/FUTURES `post_only` 限价模拟挂单，真实实盘提交必须保持阻断。
它已经具备一个可继续扩展的离线回测内核：

`CSV Replay -> Regime -> Signal Agents -> Portfolio Optimizer -> Risk Agent -> OMS -> Simulated Broker -> PortfolioBook -> Backtest`

同时包含 OKX 公开行情、逐笔 paper runtime、订单审计/对账、风控中心和衍生品定价模块：

`Binomial Option Pricer -> European/American Call/Put -> Pricing Checks`

实时方向已经开始迁入 C++：

`Tick Batch -> MarketDataQualityMonitor -> RealtimeEngine -> TraderEngine -> OMS`

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
当前使用状态、启动方式和上下文压缩后的接续说明见根目录 [`doc/00-醒来先看-平台状态与继续开发说明.md`](/Users/snlnfy/Documents/量化交易/doc/00-醒来先看-平台状态与继续开发说明.md)。
当前审查、已知 Bug 和下一步实施计划见根目录 [`doc/03-当前项目审查与改进指导书.md`](/Users/snlnfy/Documents/量化交易/doc/03-当前项目审查与改进指导书.md)。

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
- `MarketDataQualityMonitor`
- `RealtimeEngine`
- `ExecutionRuntime`
- `MarketTimelineAuditor`
- `RiskBudgetAllocator`
- `apps/realtime_engine`
- `Event log / report writers`
- `replay_check`
- `realtime_engine_check`
- `BinomialOptionPricer`
- `option_demo`
- `pricing_check`
- `Ops readiness model / ops_check`
- `OKX execution policy / execution_policy_check`

## 语言边界

目标边界是：交易核心、策略、风控、执行、订单状态、行情处理、运维门禁和可复现检查使用 Modern C++20；浏览器 UI 使用 HTML/CSS/JS；当前 Python 平台服务只作为过渡期本地 UI/API 壳层，后续新增交易业务逻辑优先落在 `include/qt/`、`src/` 和 `apps/*` 的 C++ 模块中。

OKX 模拟盘下单前策略已经开始迁入 C++：`qt::validate_okx_spot_order` 负责模拟盘、cash 模式、现货白名单、limit/post_only、kill switch 和单笔名义金额门禁；`qt::validate_okx_derivatives_order` 负责 SWAP/FUTURES 影子合约订单、逐仓/全仓、交易所杠杆、总有效杠杆和交易单元杠杆门禁；`qt::decide_trading_unit_leverage` 接收统计/agent 杠杆建议并按步长和预算裁剪；`qt::evaluate_okx_tradeability` 固定 OKX 可交易性的 pass/warn/block 归约规则。C++ 回测成交流已经改为 `TraderEngine -> OrderManagementSystem -> SimulatedBrokerGateway -> ExecutionReport -> PortfolioBook`，低成交量、部分成交和撤单终态由 `apps/execution_model_check` 验收。`traderd` 报告已写入 `dataset_id/data_hash/config_hash/execution_model_version` 等元数据，便于复盘每次结果来自哪份数据和哪套配置。`okx_policy` 和 `trading_unit_policy` 是给本地 HTTP 壳层调用/验证的 C++ CLI，提交路径上如果关键门禁不可用会直接阻断。

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

本机没有全局 CMake 时，可使用项目本地安装的 CMake：

```bash
.tools/cmake-venv/bin/cmake -S . -B build
.tools/cmake-venv/bin/cmake --build build
.tools/cmake-venv/bin/ctest --test-dir build --output-on-failure
```

默认运行会读取 [`config/default.cfg`](/Users/snlnfy/Documents/量化交易/quant-system/config/default.cfg)。

```bash
./traderd config/default.cfg
```

二叉树期权定价 demo：

```bash
./option_demo
```

C++ 实时 tick 引擎本地回放：

```bash
./realtime_engine \
  --ticks data/sample_ticks.csv \
  --status logs/realtime_engine/status.json \
  --event-log logs/realtime_engine/events.jsonl \
  --quality-report logs/market_quality/latest.json
```

读取平台 OKX 公共行情 journal 做 C++ 本地回放：

```bash
./realtime_engine \
  --market-stream-journal logs/market_stream/okx_public.jsonl \
  --max-ticks 1000 \
  --status logs/realtime_engine/status.json \
  --event-log logs/realtime_engine/events.jsonl \
  --quality-report logs/market_quality/latest.json
```

当前 `realtime_engine` 只做本地 tick 文件或本地行情 journal 回放和状态输出，不会连接 OKX 私有 API，也不会提交或撤销订单。

C++ 实时 tick 引擎也支持只读常驻模式，用于持续刷新行情质量门禁：

```bash
./realtime_engine \
  --market-stream-journal logs/market_stream/okx_public.jsonl \
  --watch \
  --status logs/realtime_engine/status.json \
  --event-log logs/realtime_engine/events.jsonl \
  --quality-report logs/market_quality/latest.json
```

平台 `/paper` 的“C++常驻/停止C++”按钮会用同样的方式启动或停止该 runner。逐笔虚拟盘启动和恢复时也会自动准备这个只读 runner；如果 C++ 质量报告缺失、陈旧或判定 `block`，本轮策略不会生成委托，也不会触发 OKX 自动提交。

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
export KATRADE_HISTORY_CACHE_DIR=/path/to/cache
export KATRADE_HISTORY_CACHE_TTL_SECONDS=1800
export OKX_CRYPTO_INSTRUMENTS=BTC-USDT,ETH-USDT,SOL-USDT,XRP-USDT,DOGE-USDT,ADA-USDT,BNB-USDT,OKB-USDT,LTC-USDT,BCH-USDT,LINK-USDT,AVAX-USDT,DOT-USDT,TRX-USDT,TON-USDT,UNI-USDT,AAVE-USDT,PEPE-USDT,SHIB-USDT,SUI-USDT,OP-USDT,ARB-USDT,NEAR-USDT,FIL-USDT,ETC-USDT,ATOM-USDT,APT-USDT,INJ-USDT,WLD-USDT,POL-USDT,CRV-USDT,LDO-USDT,RENDER-USDT,ICP-USDT,SEI-USDT,ENS-USDT,ORDI-USDT,SATS-USDT,JUP-USDT
make historyd
```

historyd 现在也提供 OKX 公开历史行情接口：

```text
GET /api/okx/candles?instId=BTC-USDT&bar=1m&start=...&end=...&width=1200
GET /api/okx/tickers
GET /api/okx/bars.csv?contract=BTC-USDT.OKX&bar=1m
GET /api/okx/series
GET /api/okx/backfill
POST /api/okx/backfill
POST /api/okx/backfill/cancel
```

平台 `/market` 会优先通过 `history.server_url` 访问 historyd；historyd 不可用时才降级为平台直连 OKX。
OKX 大窗口历史数据通过后台回填任务写入按天分片的短期缓存，前端只请求当前视窗需要的聚合 K 线。

平台进程还内置一个只读 OKX 公共 WebSocket 行情泵：

```text
GET  /api/market/okx/stream/status
POST /api/market/okx/stream/start
POST /api/market/okx/stream/stop
GET  /api/market/okx/stream/trades?instId=BTC-USDT&limit=100
```

行情泵订阅 `trades`、`tickers`、`books5`，写入 `logs/market_stream/okx_public.jsonl`，并在内存中保留最近 tick。逐笔虚拟盘会优先消费该 WS 缓冲区；WS 未启动或不新鲜时才回退到 OKX REST 公开成交接口。该通道只读，不会触发下单或撤单。

平台还维护统一的轻量事件 journal：

```text
GET /api/events/journal?limit=200
```

该 journal 写入 `logs/event_journal/events.jsonl`，记录行情流状态、行情摘要、虚拟盘 tick 周期、策略信号、风控、纸面委托、纸面成交和异常摘要。它用于监控、回放索引和后续 C++ 实时内核衔接；原始行情和 OKX 订单审计仍保留在专用日志中。

C++ 实时 tick 引擎状态可以通过只读桥接读取：

```text
GET /api/realtime/status?limit=100
POST /api/realtime/replay
GET /api/realtime/runner
POST /api/realtime/runner/start
POST /api/realtime/runner/stop
```

`GET` 读取 `logs/realtime_engine/status.json`、`logs/realtime_engine/events.jsonl` 和 `logs/market_quality/latest.json`。`POST` 要求 `confirm=RUN_CXX_REALTIME_REPLAY`，可用 `source=csv` 或 `source=market_stream` 运行本地回放并刷新这些文件。两者都不会连接 OKX 私有 API、不会提交或撤销订单。
当 `logs/market_quality/latest.json` 来自平台 OKX 公共行情 journal 且仍然新鲜时，`/paper` 会把 C++ `decision=block` 当作硬门禁，跳过本轮策略和订单生成；过期或本地样本回放报告只展示，不会阻断当前 runner。

订单中心还维护一份 append-only 订单流水：

```text
GET /api/orders/state?limit=300
GET /api/orders/execution_quality?limit=1000
POST /api/orders/execution_calibration
```

该流水写入 `logs/order_journal/orders.jsonl`，把虚拟盘订单的 `order.created`、`order.fill`、`order.expired` 事件按 paper session 和 order id 归约成当前状态，便于 UI 展示、问题排查和后续执行回放。
成交事件会记录本次成交对持仓的影响，包括开仓、加仓、减仓、平仓、反手，以及本次平仓数量、毛盈亏、分摊手续费、净盈亏和成交后的累计已实现盈亏。
执行决策轨迹写入 `logs/execution_trace/decisions.jsonl`，记录策略源委托、OKX 候选单、自动提交门禁、可交易性、预计成本、失败检查、提交结果和本地审计 ID，用来复盘“为什么没有在 OKX 上看到挂单”。
生产运维门禁会读取该轨迹，检查 trace 是否断流、阻断/失败比例是否异常、加权预计成本是否超过 `execution.max_expected_cost_bps`。
OKX 对账流水写入 `logs/reconciliation/okx_reconcile.jsonl`，每次只读对账都会记录基准、虚拟盘净持仓、OKX 模拟盘净持仓、差异数量、订单同步变化和检查分布；`/paper`、`/orders` 和 `/risk` 会共同展示这条链路。
虚拟盘 runner 默认开启陈旧挂单自动撤单：每轮先同步平台已提交的 OKX simulated trading 订单，再按 TTL 撤销超时未终态挂单，默认 180 秒、每轮最多 5 单。该逻辑只针对平台自己提交的 OKX 模拟盘 `post_only` 挂单，撤完后会重新计算自动提交门禁，避免旧挂单长期阻塞新委托。
交易单元基础设施已加入 `/paper`：趋势、均值回归、做市/高频三类交易单元会聚合基础策略信号，按 `execution.trade_unit.base_notional_usdt=1` 作为基础下单单位，读取统计基线或 `logs/agent_sessions/trading_unit_leverage.json` 中的 agent 杠杆建议，再按总有效杠杆、单元杠杆、交易所杠杆和调杠步长裁剪。agent 可读取 `/api/paper/trading_units` 的 `agent_brief`，再向 `/api/paper/trading_units/agent_leverage` 写回建议；交易单元当前有效杠杆写入 `logs/paper_trading/trading_unit_state.json`，只在新策略周期推进，避免刷新页面反复调杠。当前合约默认 `execution.derivatives.enabled=true`，虚拟盘策略订单会优先映射为 OKX SWAP 模拟盘 post-only 限价挂单；自动提交仍只允许 simulated trading，活跃挂单上限固定为 10。
执行质量接口会只读对比虚拟盘成交率、虚拟滑点、OKX 模拟盘审计成交率和审计滑点，并给出校准等级、样本置信度、参数建议和将要写入的 `execution.*` 配置行。`POST /api/orders/execution_calibration` 需要 `confirm=APPLY_EXECUTION_CALIBRATION`，只把建议写入本地 `config/default.cfg` 并在 `logs/config_backups/` 留备份，不会提交或撤销任何 OKX 订单。

券商页还提供 OKX-only 的合约可交易性评估：

```text
GET /api/broker/okx/tradeability?notional=25
```

该接口只读 OKX 公开 ticker/规则和本地 WS books5 缓冲，按规则状态、bid/ask 价差、最小下单数量、五档深度、24h 成交量和估计成本给每个白名单合约打出 `pass/warn/block`，并拆出 maker fee、半价差、深度压力和预计 USDT 成本。它不访问私有订单接口，不提交或撤销订单。

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
strategy.enabled=momentum,mean_reversion,defensive,donchian_breakout,ma_cross,macd_trend,ema_slope_trend,keltner_breakout,volume_spike_momentum,bollinger_reversion,rsi_reversion,zscore_reversion,range_fade
history.mode=local
history.server_url=http://127.0.0.1:8790
history.contracts=AAPL.NASDAQ,MSFT.NASDAQ,GLD.ARCA
history.cache_dir=logs/cache/history
history.cache_ttl_seconds=1800
history.bar=1m
history.start=
history.end=
history.max_pages=40
strategy.donchian.lookback=3
strategy.ma_cross.fast_window=2
strategy.ma_cross.slow_window=4
strategy.macd.fast_alpha=0.55
strategy.macd.slow_alpha=0.30
strategy.macd.signal_alpha=0.45
strategy.ema_slope.alpha=0.35
strategy.ema_slope.min_slope=0.001
strategy.keltner.alpha=0.25
strategy.keltner.multiplier=1.5
strategy.volume_spike.alpha=0.20
strategy.volume_spike.multiplier=1.8
strategy.bollinger.window=4
strategy.bollinger.band_width=1.2
strategy.rsi.window=4
strategy.rsi.oversold=35
strategy.rsi.overbought=65
strategy.zscore.window=8
strategy.zscore.threshold=1.25
print_cycles=true
print_event_stream=true
metrics.drawdown_stride=1
initial_cash=1000000
optimizer.max_single_weight=0.35
optimizer.max_gross=0.90
risk.max_single_weight=0.30
risk.max_gross=0.80
risk.max_order_notional=50000
risk.kill_switch=false
execution.min_rebalance_delta=0.02
execution.max_participation_rate=0.04
execution.maker_offset_bps=2.0
execution.maker_fee_bps=1.0
execution.max_expected_cost_bps=50
execution.pending_order_ttl_bars=1
```

默认策略分组：

- 趋势市：`momentum`、`donchian_breakout`、`ma_cross`、`macd_trend`、`ema_slope_trend`、`keltner_breakout`、`volume_spike_momentum`
- 震荡市：`mean_reversion`、`bollinger_reversion`、`rsi_reversion`、`zscore_reversion`、`range_fade`
- 防御/压力环境：`defensive`

历史数据模式：

- `history.mode=local`：直接读取 `replay_path`。
- `history.mode=remote`：从 `history.server_url` 按 `history.contracts` 拉取数据。
- 本地只保存短期缓存，缓存目录为 `history.cache_dir`。
- `history.cache_ttl_seconds=1800` 表示合约数据半小时不用就会在下一次拉数前删除。
- OKX 行情由独立 historyd 分页拉取并缓存，平台前端按当前时间窗口请求聚合后的 K 线。
- `history.bar`、`history.start`、`history.end`、`history.max_pages` 用于远端 OKX 加密回测窗口。
- `/market` 页面可启动 OKX 历史回填任务；例如 BTC-USDT 1m 两年数据会在 historyd 后台慢速拉取，页面持续轮询进度，任务可取消。

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
- 在 `/runs` 查看运行质量门禁，检查回测状态、周期数、最终权益、回撤、敞口、成本和事件流，并对比最近两次运行的核心指标变化
- 保存每次回测实验到 `logs/experiments/`，包含配置、代码版本、数据指纹、指标和完整报告
- 在实验页运行单参数扫描，每个取值会生成独立实验，运行结束后自动恢复原配置
- 在实验页运行 Walk-forward 验证，按本地 CSV 时间窗先训练选参，再记录样本外测试实验
- 勾选多个实验，对比收益、回撤、Sharpe、换手、成本和敞口
- 在加密页用 OKX 现货品种、K 线周期和窗口一键运行 C++ 加密回测，并写入实验档案
- 在虚拟盘页选择 OKX 现货品种、K 线周期和策略集，启动逐笔 paper runner 或手动运行一次 tick；逐笔模式优先消费 OKX 公共 WS 成交流，REST 仅作兜底
- 逐笔 runner 默认要求新鲜 C++ 行情质量报告；若报告缺失、陈旧，或 C++ 对当前 OKX 公共行情 journal 判定 `block`，本轮不会生成策略委托，也不会触发 OKX 自动提交
- 查看虚拟盘权益曲线、现金曲线、敞口柱、纸面持仓、成交流水和 K 线交易标注
- 在事件页查看统一事件 journal，追踪行情流、策略周期、风控、纸面委托和成交摘要
- 在订单中心只读汇总虚拟盘订单、成交、每次平仓盈亏、挂单/过期记录、订单状态机、OKX 对账流水、执行质量校准和 OKX 本地审计，不触发下单或撤单
- 虚拟盘默认要求挂到 OKX simulated trading，策略新生成的合格委托会按风控、OKX 可交易性、行情延迟、引擎耗时、活跃挂单数和单笔 USDT 上限门禁自动提交为 SWAP `post_only` 模拟挂单；候选计划仍可用于审查映射和预检结果
- OKX 合约规则会缓存到 `logs/okx_reference/instruments_*.json`；启动/恢复虚拟盘时会按缓存过滤没有有效 SWAP/FUTURES `state/minSz/lotSz/tickSz/ctVal` 的品种，避免静态标的池把不可下单合约送入自动提交链路
- 合约候选单会用缓存的 `minSz/lotSz/tickSz/ctVal` 做数量折算，1 USDT 基础策略单元在模拟盘执行侧可抬升到交易所最小合法张数，并把抬升前后名义金额写入候选计划
- OKX 提交/撤单/设置杠杆失败会在本地审计和执行轨迹中保留 `sCode/sMsg`、OKX `code/msg`、request id、base URL 和 fallback 错误，避免只看到 `All operations failed`
- 在虚拟盘页保存 OKX 对账基准，后续手动对账会比较虚拟盘与 OKX 模拟盘从基准之后的持仓净变化，同步最近订单状态，并把结果追加到本地对账流水
- 在 `/market` 和 `/crypto` K 线图上标注虚拟盘信号、委托、成交、滑点、风控和持仓相关指标，并叠加 MA、布林带、VWAP 指标线
- 在风控页查看 kill switch、单笔名义金额上限、敞口限制、最近回撤、自动化冻结、自动化运行门禁、OKX 对账健康和运维告警；kill switch 会阻断新的 OKX 模拟盘订单，自动化冻结会阻断新的策略 tick 和自动提交
- 查看黄金两年 1 分钟 K 线，支持滚轮缩放和拖拽平移，后端按视窗聚合避免前端卡顿
- 查看 OKX/欧意连接状态；非 OKX 券商适配器已从产品路径删除
- 调用 Kimi 或 DeepSeek 作为研究 Agent；当前默认优先走 Kimi，DeepSeek 和 Kimi Coding Plan 只作为手动备选

策略页可以直接保存 `strategy.enabled` 和策略参数。保存后运行回测时，
C++ 策略工厂会使用配置文件中的参数创建策略实例。

性能相关说明：趋势/震荡策略里的 Donchian、MA、Bollinger、RSI 指标在 C++ 核心中维护滚动状态，不在每根 K 线上重复扫描历史窗口。`metrics.drawdown_stride=1` 表示最大回撤精确计算；高吞吐回测或虚拟盘监控时可以调大该值，对最大回撤做采样近似。

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

# 可选：真实黄金 1m CSV，字段为 timestamp,open,high,low,close,volume。
# 不配置时，黄金行情页不会生成或展示模拟 K 线。
KATRADE_GOLD_1M_PATH=/path/to/gold_1m.csv

# 当前唯一交易券商是 OKX/欧意；非 OKX 适配器不再保留在产品路径中。

# OKX / 欧意：公开行情不需要 key，私有账户/订单需要 key。
OKX_BASE_URL=https://www.okx.com
OKX_BASE_URLS=https://www.okx.com
OKX_REQUEST_TIMEOUT_SECONDS=4
OKX_API_KEY=your_okx_key
OKX_SECRET_KEY=your_okx_secret
OKX_PASSPHRASE=your_okx_passphrase
OKX_SIMULATED_TRADING=true
OKX_TRADING_ENABLED=false
OKX_CRYPTO_INSTRUMENTS=BTC-USDT,ETH-USDT,SOL-USDT,XRP-USDT,DOGE-USDT,ADA-USDT,BNB-USDT,OKB-USDT,LTC-USDT,BCH-USDT,LINK-USDT,AVAX-USDT,DOT-USDT,TRX-USDT,TON-USDT,UNI-USDT,AAVE-USDT,PEPE-USDT,SHIB-USDT,SUI-USDT,OP-USDT,ARB-USDT,NEAR-USDT,FIL-USDT,ETC-USDT,ATOM-USDT,APT-USDT,INJ-USDT,WLD-USDT,POL-USDT,CRV-USDT,LDO-USDT,RENDER-USDT,ICP-USDT,SEI-USDT,ENS-USDT,ORDI-USDT,SATS-USDT,JUP-USDT
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

- 默认研究助手：Kimi `kimi-k2.6`
- Kimi Coding Plan: `kimi-code/kimi-for-coding`
- DeepSeek: `deepseek-v4-flash`

OKX / 欧意的订单接口也默认安全关闭：

- `/crypto` 的加密行情是 OKX 公开接口，不需要 API key。
- 中国大陆网络下仍优先使用 OKX 官方 REST `https://www.okx.com`；官方已停止 `aws.okx.com`，不要配置 AWS 旧域名。
- `OKX_BASE_URLS` 支持逗号分隔候选域名，只读 GET 请求会快速回退；下单 POST 不跨域自动重试，避免重复下单。
- `OKX_REQUEST_TIMEOUT_SECONDS` 控制单次 OKX 请求超时，默认 4 秒，避免 API 预检长时间卡住。
- `/live` 的 OKX 余额和订单读取需要 `OKX_API_KEY`、`OKX_SECRET_KEY`、`OKX_PASSPHRASE`。
- 如果只读预检提示 `APIKey does not match current environment`，说明 API key 与 `OKX_SIMULATED_TRADING` 不匹配；实盘 key 应关闭 simulated header，只读可用但平台仍拒绝实盘下单。
- `/live` 的 OKX `API预检` 会先检查本地配置、模拟盘 header、kill switch、合约白名单、公开行情和 SWAP 交易规则；只有用户确认后才会发送只读私有签名请求读取账户配置、余额和当前委托。
- `/live` 的 OKX `生成试挂单` 会按当前盘口生成小额 SWAP `post_only` 工单并预检；生成和填入都不会提交订单。
- `/live` 的 OKX `下单前检查` 只做本地风控、名义金额、合约白名单、isolated/cross 模式、limit/post_only 挂单、最小数量、数量步长和价格 tick 检查，不提交订单。
- `/live` 可把 OKX key 保存到本地 ignored 的 `config/api_key.config`；保存接口不会回显 secret/passphrase。
- OKX 模拟单提交后会写入 `logs/broker/okx_audit.jsonl`，并尝试立即读取订单详情，便于核对挂单/撤单结果。
- `/live` 的 OKX `同步订单状态` 会从本地审计记录查询最近订单详情，状态变化会写入 `order_synced` 审计。
- OKX 执行层在虚拟盘默认走 SWAP 合约模拟盘，杠杆受本地交易单元上限控制；市价、IOC、FOK 仍禁用，平台生成的虚拟盘委托默认使用 `post_only` 限价挂单。
- OKX 下单/撤单只允许 `OKX_SIMULATED_TRADING=true` 的模拟盘，并且还需要 `OKX_TRADING_ENABLED=true`、模拟盘 key 环境检查通过和后端确认字段；虚拟盘自动提交使用专门的后端确认常量和多重门禁，runner 内置陈旧挂单自动撤单，其他手动撤单仍要求单独确认。
- `/paper` 虚拟盘默认要求挂到 OKX simulated trading：runner 启动/恢复时会强制 `okx_auto_submit=true`，策略新生成的合格委托会按 C++ 执行策略、OKX 可交易性、单笔名义、活跃挂单数、行情延迟和引擎耗时门禁自动提交为 SWAP `post_only` 限价模拟单，活跃挂单上限固定为 10。
- 首次接入 API 时建议保持 `OKX_TRADING_ENABLED=false`，先跑 API 预检、读取余额和当前委托；确认无误后再临时打开模拟盘下单开关。

平台页面：

- `/dashboard`: 总览和净值曲线
- `/runs`: 运行回测、检查、期权定价，并查看运行档案
- `/runs` 质量门禁只读取本地运行档案，不连接交易所，适合在接入模拟盘前检查策略或配置退化
- `/report`: 结构化复盘持仓、成交、信号和风控
- `/strategies`: 策略池和参数
- `/experiments`: 回测实验归档、核心指标、单参数扫描、Walk-forward 验证和实验对比
- `/market`: OKX 现货实时行情终端，支持 K 线缩放、拖拽、十字光标、公共 WebSocket 行情流启停、逐笔成交、自动刷新、虚拟盘标注和 MA/布林带/VWAP 图层；黄金视图只读取真实 CSV，未配置时不展示模拟 K 线
- `/crypto`: OKX 现货行情、K 线指标图层和加密策略回测入口
- `/paper`: 策略虚拟盘，支持策略集选择、启动/停止后台轮询、手动 tick、逐笔模式自动准备只读 OKX 行情流、实时引擎性能遥测、OKX 模拟盘自动提交门禁、权益曲线、成交流水、持仓查看和 K 线交易标注
- `/paper` 的行情数据质量面板会检查逐笔缓存、重复成交 ID、时间戳顺序、REST 兜底和数据新鲜度，为后续自动交易门禁提供依据
- `/paper` 的 OKX 候选执行用于审查最近周期如何映射到 OKX 模拟盘；自动提交流水会记录每个源委托的 OKX 订单号、同步状态和失败原因；OKX 对账可保存本地基准、只读同步余额和订单状态，并写入 `logs/reconciliation/okx_reconcile.jsonl`
- `/live`: OKX/欧意连接状态、安全边界、合约规则、可交易性评估和模拟盘工作台
- `/orders`: 只读订单中心，汇总虚拟盘订单生命周期、订单状态机、成交回报、挂单/过期记录、OKX 对账流水和 OKX 本地审计
- `/risk`: kill switch、单笔名义金额上限、敞口限制、订单前风控、自动化冻结、自动化运行门禁、OKX 对账健康和运维告警
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
- [`pricing.cpp`](/Users/snlnfy/Documents/量化交易/quant-system/src/pricing/pricing.cpp)
- [`option_demo`](/Users/snlnfy/Documents/量化交易/quant-system/apps/option_demo/main.cpp)
- [`pricing_check`](/Users/snlnfy/Documents/量化交易/quant-system/apps/pricing_check/main.cpp)

## 下一步扩展

1. 继续压缩高频状态接口和前端轮询路径，保证逐笔 runner 长时间运行时 UI 不被大对象拖慢。
2. 完成数据质量 job 和自动化门禁告警。
3. 模块化成本、滑点、队列成交和延迟模型，并用 OKX 模拟盘审计样本校准。
4. 继续把 OMS 状态恢复、挂单超时处理、撤单原因和部分成交解释迁入 C++ 常驻执行 runtime。
5. 补 Walk-forward 多参数组合、样本外图表，以及 Black-Scholes Greeks / Monte Carlo pricer。
