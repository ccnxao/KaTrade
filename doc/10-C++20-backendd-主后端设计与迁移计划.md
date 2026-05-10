# C++20 backendd 主后端设计与迁移计划

更新时间：2026-05-10

## 1. 这份文档解决什么问题

平台之前的后端状态容易被误解：

- Python `apps/platform/server.py` 还在负责 UI、配置、HTTP API 和部分交易逻辑。
- C++ 已经有 `realtime_engine`、`traderd`、执行模型检查等组件。
- 但计划中的 C++ 主后端 `backendd` 之前没有构建出来，所以 UI 会显示类似“后端服务没构建”。

本次重构把 `backendd` 定义为后续平台主后端，而不是一个为了消除报错的最小工具。

最终目标：

```text
前端 UI
  -> Python platform server
       只做静态文件、配置保存、Kimi/Agent 适配、兼容代理
  -> C++20 backendd
       负责行情、策略、风控、OMS、OKX 模拟盘执行、订单状态、持仓、PnL、审计、恢复
```

## 2. 当前已经实现的 backendd 能力

代码位置：

```text
quant-system/apps/backendd/main.cpp
quant-system/include/qt/backend/
quant-system/src/backend/
```

订单维护相关边界已经开始拆开：

```text
quant-system/include/qt/backend/order/order_maintenance.hpp
quant-system/src/backend/order/order_maintenance.cpp
quant-system/apps/order_maintenance_check/main.cpp
```

其中 `order_maintenance` 负责订单一致性诊断、维护计划筛选和 action/keep 分类；`route_registry.cpp` 只负责读取 journal、调用维护服务、把结果序列化成原有 JSON。`order_maintenance_check` 用合成订单固定核心规则，后续迁移 OKX 查单、撤单和 OMS apply 时，应继续沿这个边界扩展，不要再把交易决策规则塞回路由文件。

账户读模型边界也已经拆开：

```text
quant-system/include/qt/backend/account/account_read_model.hpp
quant-system/src/backend/account/account_read_model.cpp
quant-system/apps/account_read_model_check/main.cpp
```

其中 `account_read_model` 负责从 `order_journal`、`execution_ledger`、OKX 行情流和合约元数据缓存重建持仓、PnL 归因、资金曲线、线性合约保守盯市；`route_registry.cpp` 只负责读取 query 参数并把 read model 序列化为原有 API JSON。`account_read_model_check` 用临时日志固定开仓、部分平仓、策略贡献、线性合约 `ct_val` 折算和 ticker 盯市权益。后续补反向合约估值、资金费率、保证金、Agent 资金快照时，应优先扩展这个模块并同步补测试。

2026-05-10 后续拆分：

```text
quant-system/include/qt/backend/common/route_utils.hpp
quant-system/src/backend/common/route_utils.cpp
quant-system/include/qt/backend/order/order_read_model.hpp
quant-system/src/backend/order/order_read_model.cpp
quant-system/include/qt/backend/account/account_routes.hpp
quant-system/src/backend/account/account_routes.cpp
```

其中 `route_utils` 只放 query 和通用 JSON 工具，`order_read_model` 负责订单 journal / execution trace / OKX audit 的只读归约，`account_routes` 只负责账户 API 注册和 JSON 序列化。多人协作边界见 `doc/12-模块拆分与多人协作边界.md`。

同轮重构还把 C++ 实现文件从 `quant-system/src` 根目录移入模块目录，例如 `src/execution/oms.cpp`、`src/portfolio/portfolio.cpp`、`src/risk/risk.cpp`、`src/engine/trader_engine.cpp`。后续新增业务实现必须先选择模块目录，不能继续在根目录平铺。

已实现：

1. C++20 `backendd` 可执行文件。
2. 命令模式：

```bash
cd /Users/snlnfy/Documents/量化交易/quant-system
./backendd --root . --config config/default.cfg --route /api/backend/summary
```

3. 长驻 HTTP 模式：

```bash
./backendd serve --root . --config config/default.cfg --host 127.0.0.1 --port 8791
```

4. Python 平台会优先访问长驻 `backendd`：

```text
http://127.0.0.1:8791
```

如果 8791 没有服务，才回退到 `subprocess` 命令模式。

5. 一键启动脚本会构建并启动 `backendd`。
6. 一键关闭脚本会停止 `backendd`。
7. `make check` 会构建 `backendd` 并跑一次 `/api/backend/summary` smoke test。
8. `make order_maintenance_check` 会单独验证订单维护决策规则；`make validate` 已包含它。

## 3. 当前 C++ backendd API

已接入的 C++ 路由：

```text
/api/health
/api/backend/summary
/api/backend/orders/summary
/api/backend/orders/state
/api/backend/orders/center
/api/backend/orders/consistency
/api/backend/orders/local_repair_plan
/api/backend/orders/broker_terminal_sync_plan
/api/backend/orders/stale_broker_reconcile_plan
/api/backend/execution/trace_summary
/api/backend/execution/trace
/api/backend/market/quality
```

这些路由现在主要读取本地 journal 和状态文件，形成 C++ read model。

重要说明：

- `orders`：已经由 C++ 从 `logs/order_journal/orders.jsonl` 聚合订单状态。
- `execution_trace`：已经由 C++ 从 `logs/execution_trace/decisions.jsonl` 汇总提交、阻断、失败。
- `market_quality`：已经由 C++ 读取 `logs/market_quality/latest.json`。
- `okx_audit` 和 `execution_ledger`：已经在 `/api/backend/summary` 和 `/api/backend/orders/center` 里汇总。
- `local_repair_plan`：已经由 C++ 基于订单状态、执行轨迹和 OKX 审计生成本地陈旧订单 dry-run 修复计划；它不会直接写 journal，也不会撤 OKX 单。
- `broker_terminal_sync_plan`：已经由 C++ 找出 OKX 审计已终态但本地订单仍活跃的回补候选；C++ 仍只输出 dry-run 计划，Python `/api/paper/broker_terminal_sync` 负责受控写入本地 `order.broker_sync`。
- `stale_broker_reconcile_plan`：已经由 C++ 找出本地活跃、已有 OKX 单号、超过陈旧阈值、且尚无终态审计的订单；C++ 仍只输出 dry-run 计划，Python `/api/paper/stale_broker_reconcile` 负责受控查单、同步终态或撤模拟盘挂单。
- `account/equity`：已经由 C++ `account_read_model` 输出资金曲线读模型。主曲线优先使用 `latest_report.equity_curve`，同时返回 `order.fill` 重放的 realized-only 曲线和保守 ticker mark-to-market 曲线；默认 `session=latest`，排查历史时可用 `session=all`。
- UI 已接入 `/api/backend/account/equity`：总览页和风控页都展示报告净值曲线、C++ 盯市曲线、C++ realized-only 成交回放曲线和对应摘要，便于区分“含浮盈亏报告口径”、“C++ 基于 OKX ticker 的盯市口径”和“C++ 从真实成交回放出来的已实现口径”。

## 4. 还没有迁移的能力

目前仍在 Python 或其他 C++ app 中：

1. 策略实时决策。
2. Paper runner 主循环。
3. OMS 委托状态机的唯一真源。
4. OKX 模拟盘提交、撤单、查单。
5. 合约元数据刷新和下单数量折算。
6. 持仓、资金曲线和 PnL 归因的主状态仍未完全脱离 Python 文件；C++ 已有 read model，但还没有实时 mark-to-market 主状态。
7. 自动撤单、超时重试、订单上限的执行闭环。

所以现在的阶段叫：

```text
C++ backendd 第一阶段：主后端骨架 + 只读 read model 接管
```

不是最终完成态。

## 5. 迁移原则

### 5.1 Python 只做壳

Python 允许保留：

- 静态 UI 文件。
- 本地配置表单。
- OKX key 保存。
- Kimi / Agent HTTP 适配。
- 对 C++ backendd 的兼容代理。

Python 不应该长期保留：

- 策略决策。
- 风控判定。
- OMS 状态机。
- OKX 下单撤单。
- PnL/持仓主账本。

### 5.2 C++ 是交易状态真源

后续交易相关状态以 `backendd` 为准：

```text
Tick -> StrategyEngine -> Risk -> OMS -> OKX Gateway -> ExecutionReport
                                      -> PositionBook -> PnL -> Journal/Snapshot
```

UI 只能读状态，不直接改交易核心。

### 5.3 所有自动交易必须可恢复

任何自动化交易都必须满足：

- 订单写入 append-only journal。
- 关键状态定期 snapshot。
- 重启后能恢复 open orders、positions、risk state。
- 本地状态和 OKX 模拟盘状态能 reconcile。

## 6. 下一阶段具体任务

### 阶段 2：C++ OMS Read Model 完整化

目标：C++ 对订单中心展示的解释能力超过 Python。

已完成：

1. 给 `OrderReadModel` 增加：
   - strategy_id
   - trading_unit_id
   - agent_id
   - parent_decision_id
   - broker_state
   - source_order_id
   - close_gross_pnl
   - close_fee
   - close_net_pnl
2. `/api/backend/orders/consistency` 增加：
   - stale order 列表，而不只是数量。
   - broker identity 缺失列表。
   - OKX audit 中 live 但本地 terminal 的订单。
   - 本地 pending 但 OKX audit 已 filled/canceled 的订单。
3. UI 订单中心优先展示 C++ consistency 结果。
4. `/api/backend/orders/local_repair_plan` 已生成本地-only 陈旧订单修复计划。
5. Python `/api/paper/local_order_repair_plan` 已优先读取 C++ 计划，只有 C++ 不可用时回退旧逻辑。
6. `/api/backend/orders/broker_terminal_sync_plan` 已生成 broker 终态回补计划。
7. `/api/paper/broker_terminal_sync_plan` 已代理 C++ 计划，`/api/paper/broker_terminal_sync` 已能把 `broker_terminal_not_reflected_locally` 安全转换成本地 `order.broker_sync`。
8. `/api/backend/orders/stale_broker_reconcile_plan` 已生成有 OKX 单号的陈旧挂单主动查单/撤单计划，Python `/api/paper/stale_broker_reconcile` 已能受控执行查单、终态同步和模拟盘撤单。
9. 订单维护计划的 C++ 决策规则已经从 `route_registry.cpp` 抽到 `order_maintenance` 模块，后续 C++ apply/OMS/gateway 可以复用同一套一致性模型。
10. `order_maintenance_check` 已接入 Makefile 和 CMake/CTest，保护本地修复、broker 终态同步、陈旧 broker 对账和 action 上限逻辑。

仍未完成：

1. 有 OKX 单号但缺少终态审计的陈旧订单已经有 C++ plan + Python apply；后续要把 OKX 查单、撤单、回补也迁入 C++ broker gateway。
2. broker 终态 apply 和陈旧 broker apply 目前仍由 Python 写本地 journal，后续要把受控 apply 和 OMS 状态机迁到 C++。
3. 订单状态机唯一真源仍未完全从 Python 迁到 C++。

验收：

```bash
make backendd
make order_maintenance_check
./backendd --root . --route /api/backend/orders/center | python3 -m json.tool
./backendd --root . --route '/api/backend/account/equity?limit=20' | python3 -m json.tool
./backendd --root . --route '/api/backend/orders/local_repair_plan?min_age_seconds=300&max_orders=5' | python3 -m json.tool
./backendd --root . --route '/api/backend/orders/broker_terminal_sync_plan?max_orders=5' | python3 -m json.tool
```

能看到每笔订单当前状态、最后更新时间、是否陈旧、是否缺 broker identity。
本地修复计划里，带 OKX `ordId/clOrdId` 或最新 trace 为 `submitted` 的订单必须是 `keep`，不能被本地伪过期。

### 阶段 3：C++ 持仓、PnL 和资金曲线

目标：用户问“盈亏是谁带来的”时，C++ 能直接回答。

已完成的初版：

- `backendd` 已从 `logs/order_journal/orders.jsonl` 重放 `order.fill`。
- 已按 `source_order_id` 连接 `logs/execution_ledger/events.jsonl`。
- 已输出当前净持仓、均价、名义敞口、平仓净盈亏、手续费。
- 已按策略、Agent、交易单元输出贡献归因。
- 已把 `/agents` 页面改成优先读取 C++ 账户读模型。
- 已把账户/持仓/归因/资金曲线 read model 从 `route_registry.cpp` 拆到 `account_read_model`，路由层不再承载账户计算主逻辑。
- 已把账户 API 序列化从 `route_registry.cpp` 拆到 `account_routes`，把订单日志归约拆到 `order_read_model`，把 query/JSON 通用工具拆到 `route_utils`，为多人并行开发提供更小的修改边界。
- 已新增 `account_read_model_check`，用合成日志回归验证账户 read model 的核心 PnL 和盯市口径。

已新增 API：

```text
/api/backend/account/positions
/api/backend/account/pnl
/api/backend/account/attribution
/api/backend/account/portfolio
/api/backend/account/equity
```

仍未完成：

1. 从 `order.fill` 和 `execution_ledger` 重建：
   - unrealized_pnl：线性合约已经能用 OKX ticker + `ct_val` 做保守盯市；反向合约估值、资金费率和保证金占用还没迁入 C++。
   - equity_curve：已新增 C++ 端点 `/api/backend/account/equity`，并把资金曲线、持仓、PnL 归因和保守 mark-to-market 拆入独立 `account_read_model`；下一步要补齐反向合约估值、资金费率、保证金占用和可落盘 capital snapshots。
   - capital snapshots：Agent 资金状态仍由 Python 文件产生，C++ 还没统一接管。
2. UI 订单页继续改读 C++ PnL 细节；`/dashboard`、`/risk` 和 `/agents` 已开始使用 C++ 账户读模型。

验收：

- 每次平仓能看到 `close_net_pnl`。
- 能按策略、品种、交易单元拆贡献。
- `/api/backend/account/equity?limit=500` 能返回主资金曲线、报告曲线、C++ realized-only 曲线和 C++ mark-to-market 曲线；`session=latest` 是默认值，`session=all` 用于历史排查。
- 历史没有真实 `strategy_attribution` 的成交必须显示为 `unknown`，不能把 `tick-maker-rebalance` 这类调仓标签伪装成策略贡献。

### 阶段 4：C++ 策略实时引擎

目标：逐笔行情驱动策略，不再由 Python runner 主导。

任务：

1. 新增 `MarketDataService`：
   - 读取 OKX public stream journal。
   - 维护 tick ring buffer。
   - 维护 orderbook snapshot。
2. 新增 `StrategyEngine`：
   - 每个策略实例独立状态。
   - 每个 tick 或 book 更新触发策略。
   - 策略只输出 `OrderIntent`，不直接下单。
3. 新增 `StrategyInstanceConfig`：
   - 策略定义和策略配置分离。
   - 支持多个品种和多个参数实例。

验收：

- 同一条 tick 进入 C++ 后能生成可追踪 signal。
- signal、risk、order intent 都写入 execution trace。

### 阶段 5：C++ 风控和 OMS 接管

目标：所有委托必须经过 C++ 风控和 C++ OMS。

任务：

1. C++ pre-trade risk：
   - max active orders = 10。
   - only OKX。
   - simulated trading only。
   - post_only / limit 优先。
   - 禁止 market / IOC / FOK 默认自动提交。
2. C++ OMS：
   - new / submitted / live / partially_filled / filled / canceled / expired / rejected。
   - TTL 自动撤单。
   - stale order reconcile。
   - 本地和 OKX 状态差异告警。
3. API：

```text
/api/backend/risk/status
/api/backend/risk/pretrade
/api/backend/oms/state
/api/backend/oms/reconcile
```

验收：

- 昨天挂的模拟盘单不会长期留着不撤。
- 每笔没有成交的单都有明确原因：未触价、已撤、被风控阻断、交易所拒绝。

### 阶段 6：C++ OKX Gateway

目标：OKX 模拟盘下单、撤单、查单由 C++ 接管。

任务：

1. C++ OKX REST signer。
2. OKX simulated header。
3. instruments cache：

```text
logs/okx_reference/instruments_SWAP.json
logs/okx_reference/instruments_FUTURES.json
```

4. 合约数量折算：

```text
target_notional_usdt = base_notional_usdt * effective_leverage
contract_notional = px * ctVal
raw_contracts = target_notional_usdt / contract_notional
sz = ceil_to_step(max(raw_contracts, minSz), lotSz)
actual_notional = sz * ctVal * px
```

5. 如果 `actual_notional` 超过预算，必须 block。
6. OKX 原始错误码写入：
   - `logs/broker/okx_audit.jsonl`
   - `logs/execution_trace/decisions.jsonl`
   - `logs/execution_ledger/events.jsonl`

验收：

- BTC/ETH/SOL/XRP/DOGE SWAP 都能生成合法 trial order。
- `All operations failed`、`51010`、`minSz`、`ctVal missing` 有明确分类。

## 7. 当前已知问题

1. 当前 C++ `backendd` 仍然从 JSONL 读取 read model，没有自己的内存状态和 snapshot。
2. `/api/backend/orders/consistency` 现在只给聚合数量，下一步要返回具体订单列表。
3. Python paper runner 还会继续写本地订单 journal。
4. C++ backendd 还没有接管 OKX 下单。
5. 如果日志非常大，深度 API 仍可能需要分页和缓存；健康检查已经避免全文件扫描。

## 8. 开发者继续时的第一步

如果下一个 Codex 接手，先运行：

```bash
cd /Users/snlnfy/Documents/量化交易/quant-system
make backendd
./backendd --root . --config config/default.cfg --route /api/backend/summary | python3 -m json.tool
./backendd --root . --config config/default.cfg --route /api/backend/orders/center | python3 -m json.tool
```

如果要启动整个平台：

```bash
cd /Users/snlnfy/Documents/量化交易
./启动交易平台.command
```

然后看：

```text
http://127.0.0.1:8787/api/backend/summary
http://127.0.0.1:8787/orders
```

## 9. 当前任务优先级

下一次继续时，按这个顺序：

1. 完善 C++ `OrderReadModel` 字段。
2. 让 `/api/backend/orders/consistency` 返回具体问题订单列表。
3. 把 UI 订单中心的“陈旧单/缺 broker identity/OKX 不一致”显式展示出来。
4. 新增 C++ PnL/position read model。
5. 再开始迁 C++ 策略实时引擎。
