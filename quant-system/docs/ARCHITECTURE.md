# KaTrade Architecture

KaTrade 的当前定位是本地量化研究与纸面交易平台。系统默认只运行离线回测，
不连接实盘券商，也不会自动发出真实交易指令。

更完整的项目级设计、路线图和验收标准见
[`PROJECT_DESIGN.md`](/Users/snlnfy/Documents/量化交易/quant-system/docs/PROJECT_DESIGN.md)。

## 目录结构

```text
quant-system/
  apps/
    traderd/              # C++ 回测主程序
    replay_check/         # golden replay 回归检查
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
- `execution.hpp` / `oms.hpp`: 纸面执行和订单生命周期。
- `report_io.hpp`: 事件、摘要和结构化 JSON 报告输出。
- `runtime_config.hpp`: `config/default.cfg` 的结构化读取。

## 历史数据服务

历史数据服务独立放在 `apps/historyd/server.py`，可以运行在另一台 Mac 上。
交易系统和历史服务之间只通过 HTTP 通信，不共享进程内状态。

服务端接口：

- `GET /api/health`: 服务健康、数据行数、合约数量。
- `GET /api/contracts`: 可用合约列表。
- `GET /api/bars.csv?contract=AAPL.NASDAQ`: 单合约 CSV。
- `GET /api/replay.csv?contracts=AAPL.NASDAQ,MSFT.NASDAQ`: 多合约 CSV。

客户端配置：

```text
history.mode=remote
history.server_url=http://192.168.1.20:8790
history.contracts=AAPL.NASDAQ,MSFT.NASDAQ,GLD.ARCA
history.cache_dir=logs/cache/history
history.cache_ttl_seconds=1800
```

缓存约束：

- 本地只缓存远端返回的合约 CSV，不作为长期数据仓库。
- 缓存按合约拆分，文件放在 `history.cache_dir` 下。
- 每次使用缓存都会刷新文件时间。
- 超过 `history.cache_ttl_seconds` 未使用的合约文件会在下一次拉数前删除。
- `history.cache_ttl_seconds=1800` 表示半小时，可按需要修改。

## 策略放置约定

新增策略时按市场状态放置：

- 趋势市策略放在 `src/strategies/trend.cpp`
- 震荡/均值回归策略放在 `src/strategies/mean_reversion.cpp`
- 防御、现金管理、压力环境策略暂放在 `src/agents.cpp`
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
    agent_sessions.py     # Agent 会话和上下文
    providers.py          # Kimi/DeepSeek/Kimi CLI 适配
```

后端约束：

- 不输出真实 API key。
- 只写 `logs/`、`config/default.cfg` 等明确的本地工作文件。
- Agent 默认只读，不直接修改项目文件。
- 删除、上传、外部提交等动作必须单独确认。

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
- `/runs`: 运行任务和运行档案。
- `/report`: 持仓、订单、策略贡献、风控复盘。
- `/strategies`: 策略池、市场类型、启用状态。
- `/data`: CSV 数据体检。
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
