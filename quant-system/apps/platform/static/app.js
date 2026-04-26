const $ = (id) => document.getElementById(id);

const configGrid = $("configGrid");
const output = $("commandOutput");
const commandState = $("commandState");
const agentMessages = $("agentMessages");
const agentStatus = $("agentStatus");

const pageMeta = {
  dashboard: ["总览", "净值、收益、回撤和下一步入口"],
  runs: ["运行", "启动回测、检查和定价任务"],
  report: ["报告", "复盘持仓、订单、信号和风控"],
  strategies: ["策略", "查看策略池、市场类型和启用状态"],
  data: ["数据", "检查行情文件和数据质量"],
  events: ["事件", "查看订单、成交和风控流"],
  config: ["配置", "调整本地运行参数"],
  agent: ["研究助手", "多轮对话式研究分析"],
};

let currentConfig = {};
let currentProviders = {};
let currentReport = {};
let currentDataProfile = {};
let currentStrategies = [];
let currentAgentSession = null;

function formatMoney(value) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatPercent(value) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return "-";
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function formatNumber(value, digits = 2) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function setBusy(label) {
  commandState.textContent = label;
}

function routeFromPath() {
  const name = window.location.pathname.replace(/^\/+/, "") || "dashboard";
  return pageMeta[name] ? name : "dashboard";
}

function renderRoute(route) {
  const page = pageMeta[route] ? route : "dashboard";
  document.querySelectorAll(".page").forEach((section) => {
    section.classList.toggle("active", section.dataset.page === page);
  });
  document.querySelectorAll("[data-route]").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === page);
  });
  $("pageTitle").textContent = pageMeta[page][0];
  $("pageSubtitle").textContent = pageMeta[page][1];
  if (page === "agent") {
    ensureAgentReady().catch((error) => {
      agentStatus.textContent = String(error);
    });
  }
}

function navigateTo(route, push = true) {
  const page = pageMeta[route] ? route : "dashboard";
  const path = `/${page}`;
  if (push && window.location.pathname !== path) {
    history.pushState({ page }, "", path);
  }
  renderRoute(page);
}

document.addEventListener("click", (event) => {
  const link = event.target.closest("a[data-route]");
  if (!link) return;
  event.preventDefault();
  navigateTo(link.dataset.route);
});

window.addEventListener("popstate", () => {
  renderRoute(routeFromPath());
});

$("backButton").addEventListener("click", () => {
  if (history.length > 1) {
    history.back();
    return;
  }
  navigateTo("dashboard");
});

function renderConfig(config) {
  currentConfig = { ...config };
  configGrid.innerHTML = "";
  Object.keys(config)
    .sort()
    .forEach((key) => {
      const field = document.createElement("div");
      field.className = "field";
      const label = document.createElement("label");
      label.textContent = key;
      const input = document.createElement("input");
      input.value = config[key];
      input.dataset.key = key;
      field.append(label, input);
      configGrid.appendChild(field);
    });
}

function collectConfig() {
  const values = {};
  configGrid.querySelectorAll("input").forEach((input) => {
    values[input.dataset.key] = input.value;
  });
  return values;
}

function renderProviders(providers) {
  currentProviders = providers || {};
  const parts = Object.entries(currentProviders).map(([, provider]) => {
    const sourceNames = {
      environment: "环境变量",
      "config/api_key.config": "配置文件",
      "local Kimi Code CLI": "本机 CLI",
      "VS Code Kimi Code extension": "VS Code 扩展",
    };
    const source = sourceNames[provider.source] || provider.source || "";
    const state = provider.configured ? `已配置${source ? `（${source}）` : ""}` : `未配置 ${provider.env}`;
    return `${provider.name}: ${state}`;
  });
  $("providerState").textContent = parts.length ? parts.join(" / ") : "未发现服务商";

  const selected = $("providerSelect").value;
  const model = currentProviders[selected]?.default_model || "";
  if (!$("modelInput").value) {
    $("modelInput").value = model;
  }
}

function renderMetrics(summary) {
  $("metricEquity").textContent = formatMoney(summary.final_equity);
  $("metricReturn").textContent = formatPercent(summary.total_return);
  $("metricDrawdown").textContent = formatPercent(summary.max_drawdown);
  $("metricFills").textContent = summary.total_fills ?? "-";
}

function renderKeyValues(container, items) {
  container.innerHTML = "";
  items.forEach(([label, value]) => {
    const item = document.createElement("div");
    item.className = "summary-item";
    const key = document.createElement("span");
    key.textContent = label;
    const val = document.createElement("strong");
    val.textContent = value;
    item.append(key, val);
    container.appendChild(item);
  });
}

function renderTable(container, columns, rows, emptyText) {
  container.innerHTML = "";
  if (!rows || rows.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = emptyText;
    container.appendChild(empty);
    return;
  }
  const table = document.createElement("table");
  table.className = "data-table";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  columns.forEach((column) => {
    const th = document.createElement("th");
    th.textContent = column.label;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  const tbody = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    columns.forEach((column) => {
      const td = document.createElement("td");
      td.textContent = column.render ? column.render(row) : row[column.key] ?? "-";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.append(thead, tbody);
  container.appendChild(table);
}

function translateEventType(type) {
  const names = {
    cycle_started: "周期开始",
    regime_detected: "市场状态",
    risk_reviewed: "风控评审",
    order_submitted: "订单提交",
    order_filled: "订单成交",
    cycle_completed: "周期完成",
  };
  return names[type] || type;
}

function translateRegime(regime) {
  const names = {
    Trending: "趋势",
    Uncertain: "不确定",
    MeanReverting: "均值回归",
    Defensive: "防御",
  };
  return names[regime] || regime || "-";
}

function translateOrderStatus(status) {
  const names = {
    Filled: "全部成交",
    PartiallyFilled: "部分成交",
    Rejected: "已拒绝",
    Submitted: "已提交",
    Cancelled: "已撤销",
  };
  return names[status] || status || "-";
}

function translateRiskAction(action) {
  const names = {
    Reduce: "降低风险",
    Keep: "保持",
    Reject: "拒绝",
  };
  return names[action] || action || "-";
}

function translateStrategyStyle(style) {
  const names = {
    trend: "趋势",
    mean_reversion: "震荡/均值回归",
    defensive: "防御",
    hybrid: "混合",
  };
  return names[style] || style || "-";
}

function translateReason(reason) {
  const names = {
    "risk-adjusted portfolio": "风控调整后的组合",
  };
  return names[reason] || reason || "-";
}

function formatEventMessage(event) {
  switch (event.type) {
    case "cycle_started":
      return `第 ${event.cycle_index} 轮开始：${event.label}，标的 ${event.instrument_count} 个`;
    case "regime_detected":
      return `第 ${event.cycle_index} 轮市场状态：${translateRegime(event.regime)}，置信度 ${formatPercent(event.confidence)}`;
    case "risk_reviewed":
      return `第 ${event.cycle_index} 轮风控：${translateRiskAction(event.risk_action)}（${translateReason(event.reason)}）`;
    case "order_submitted":
      return `第 ${event.cycle_index} 轮提交订单：${event.order_id} ${event.instrument}`;
    case "order_filled":
      return `第 ${event.cycle_index} 轮成交：${event.order_id}，数量 ${event.fill_qty}，状态 ${translateOrderStatus(event.status)}`;
    case "cycle_completed":
      return `第 ${event.cycle_index} 轮完成：${event.label}，提交 ${event.submitted_orders} 单，成交 ${event.fill_count} 笔`;
    default:
      return event.message || "";
  }
}

function renderEvents(events) {
  $("eventCount").textContent = `${events.length} 条事件`;
  const list = $("eventsList");
  list.innerHTML = "";
  events.slice().reverse().forEach((event) => {
    const row = document.createElement("div");
    row.className = "event-row";
    const sequence = document.createElement("span");
    sequence.textContent = `#${event.sequence}`;
    const type = document.createElement("strong");
    type.textContent = translateEventType(event.type);
    const message = document.createElement("div");
    message.textContent = formatEventMessage(event);
    row.append(sequence, type, message);
    list.appendChild(row);
  });
}

function drawEquityCurve(points) {
  const canvas = $("equityChart");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#f8fafb";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  if (!points || points.length === 0) {
    $("chartState").textContent = "未加载运行结果";
    return;
  }
  $("chartState").textContent = `${points.length} 个数据点`;

  const padding = 36;
  const width = canvas.width - padding * 2;
  const height = canvas.height - padding * 2;
  const values = points.map((p) => Number(p.equity));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);

  ctx.strokeStyle = "#d7dde2";
  ctx.lineWidth = 1;
  for (let i = 0; i < 4; i += 1) {
    const y = padding + (height / 3) * i;
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(canvas.width - padding, y);
    ctx.stroke();
  }

  ctx.strokeStyle = "#246b5f";
  ctx.lineWidth = 3;
  ctx.beginPath();
  points.forEach((point, index) => {
    const x = padding + (width * index) / Math.max(points.length - 1, 1);
    const y = padding + height - ((point.equity - min) / range) * height;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.fillStyle = "#1e2528";
  ctx.font = "12px system-ui";
  ctx.fillText(formatMoney(max), padding, 18);
  ctx.fillText(formatMoney(min), padding, canvas.height - 10);
}

function renderRun(payload) {
  output.textContent = payload.output || "";
  renderMetrics(payload.summary || {});
  renderEvents(payload.events || []);
  drawEquityCurve(payload.equity_curve || []);
  renderReport(payload.report || currentReport || {});
  loadRuns().catch(() => {});
}

function latestCycle(report) {
  const cycles = report?.cycles || [];
  return cycles.length ? cycles[cycles.length - 1] : null;
}

function renderReport(report) {
  currentReport = report || {};
  const summary = currentReport.summary || {};
  const cycle = latestCycle(currentReport);
  const portfolio = cycle?.post_trade_portfolio || {};
  const positions = portfolio.positions || [];
  const reports = (cycle?.reports || []).filter((item) => Number(item.last_fill_qty) > 0);
  const cycles = currentReport.cycles || [];

  $("portfolioState").textContent = cycle ? `截至 ${cycle.label}` : "等待报告";
  $("ordersState").textContent = cycle ? `${reports.length} 条成交回报` : "等待报告";
  $("riskState").textContent = cycles.length ? `${cycles.length} 个周期` : "等待报告";

  renderKeyValues($("portfolioSummary"), [
    ["最终权益", formatMoney(summary.final_equity)],
    ["现金", formatMoney(portfolio.cash)],
    ["现金权重", formatPercent(portfolio.cash_weight)],
    ["总敞口", formatPercent(portfolio.gross_exposure)],
    ["已实现盈亏", formatMoney(portfolio.realized_pnl)],
    ["未实现盈亏", formatMoney(portfolio.unrealized_pnl)],
  ]);

  renderTable(
    $("positionsTable"),
    [
      { label: "标的", render: (row) => row.instrument?.key || "-" },
      { label: "数量", render: (row) => formatNumber(row.quantity, 3) },
      { label: "成本", render: (row) => formatNumber(row.avg_cost, 2) },
      { label: "市价", render: (row) => formatNumber(row.market_price, 2) },
      { label: "市值", render: (row) => formatMoney(row.market_value) },
      { label: "权重", render: (row) => formatPercent(row.weight) },
    ],
    positions,
    "暂无持仓"
  );

  renderTable(
    $("ordersTable"),
    [
      { label: "订单", key: "order_id" },
      { label: "标的", render: (row) => row.instrument?.key || "-" },
      { label: "方向", key: "side" },
      { label: "成交数量", render: (row) => formatNumber(row.last_fill_qty, 3) },
      { label: "成交价", render: (row) => formatNumber(row.last_fill_price, 2) },
      { label: "均价", render: (row) => formatNumber(row.avg_price, 2) },
      { label: "滑点(bps)", render: (row) => formatNumber(row.slippage_bps, 2) },
      { label: "状态", key: "status" },
    ],
    reports,
    "暂无成交"
  );

  const strategyStats = {};
  cycles.forEach((item) => {
    (item.signals || []).forEach((signal) => {
      const key = signal.strategy_id || "unknown";
      if (!strategyStats[key]) {
        strategyStats[key] = {
          strategy_id: key,
          signal_count: 0,
          abs_score: 0,
          net_score: 0,
          confidence_sum: 0,
        };
      }
      strategyStats[key].signal_count += 1;
      strategyStats[key].abs_score += Math.abs(Number(signal.score || 0));
      strategyStats[key].net_score += Number(signal.score || 0);
      strategyStats[key].confidence_sum += Number(signal.confidence || 0);
    });
  });
  const strategyRows = Object.values(strategyStats).sort((a, b) => b.abs_score - a.abs_score);
  renderTable(
    $("strategyContribution"),
    [
      { label: "策略", key: "strategy_id" },
      { label: "信号数", render: (row) => String(row.signal_count) },
      { label: "净分数", render: (row) => formatNumber(row.net_score, 3) },
      { label: "绝对分数", render: (row) => formatNumber(row.abs_score, 3) },
      { label: "平均置信度", render: (row) => formatPercent(row.confidence_sum / Math.max(row.signal_count, 1)) },
    ],
    strategyRows,
    "暂无策略信号"
  );

  renderTable(
    $("riskTimeline"),
    [
      { label: "周期", key: "label" },
      { label: "市场状态", render: (row) => row.regime?.regime || "-" },
      { label: "置信度", render: (row) => formatPercent(row.regime?.confidence) },
      { label: "风控", render: (row) => row.risk_decision?.action || "-" },
      { label: "目标敞口", render: (row) => formatPercent(row.risk_decision?.adjusted_portfolio?.gross_exposure) },
      { label: "信号数", render: (row) => String((row.signals || []).length) },
      { label: "原因", render: (row) => row.risk_decision?.reason || "-" },
    ],
    cycles,
    "暂无周期报告"
  );
}

function renderStrategies(strategies, config) {
  currentStrategies = strategies || [];
  const enabled = new Set(
    String(config?.["strategy.enabled"] || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
  );
  const enabledCount = currentStrategies.filter((strategy) => enabled.has(strategy.id)).length;
  $("strategyCatalogState").textContent = `${currentStrategies.length} 个策略，已启用 ${enabledCount} 个`;

  const container = $("strategyCatalog");
  container.innerHTML = "";
  if (!currentStrategies.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "暂无策略目录";
    container.appendChild(empty);
    return;
  }

  currentStrategies.forEach((strategy) => {
    const card = document.createElement("article");
    card.className = "strategy-card";

    const head = document.createElement("div");
    head.className = "strategy-card-head";
    const title = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = strategy.display_name || strategy.id;
    const id = document.createElement("span");
    id.textContent = strategy.id;
    title.append(name, id);

    const toggle = document.createElement("label");
    toggle.className = "strategy-toggle";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = enabled.has(strategy.id);
    checkbox.dataset.strategyEnabled = strategy.id;
    toggle.append(checkbox, document.createTextNode("启用"));
    head.append(title, toggle);

    const meta = document.createElement("div");
    meta.className = "strategy-meta";
    meta.textContent = `${translateStrategyStyle(strategy.style)} · ${strategy.horizon || "-"}`;

    const desc = document.createElement("p");
    desc.textContent = strategy.description || "";

    const params = document.createElement("div");
    params.className = "strategy-params";
    (strategy.params || []).forEach((param) => {
      const field = document.createElement("label");
      field.className = "strategy-param";
      const label = document.createElement("span");
      label.textContent = param.label || param.key;
      const input = document.createElement("input");
      input.inputMode = "decimal";
      input.value = config?.[param.key] ?? param.default ?? "";
      input.dataset.strategyParam = param.key;
      input.dataset.paramKind = param.kind || "text";
      field.append(label, input);
      params.appendChild(field);
    });

    card.append(head, meta, desc);
    if ((strategy.params || []).length) {
      card.appendChild(params);
    }
    container.appendChild(card);
  });
}

function collectStrategyConfig() {
  const values = { ...currentConfig };
  const enabled = [];
  $("strategyCatalog")
    .querySelectorAll("input[data-strategy-enabled]")
    .forEach((input) => {
      if (input.checked) enabled.push(input.dataset.strategyEnabled);
    });
  values["strategy.enabled"] = enabled.join(",");

  $("strategyCatalog")
    .querySelectorAll("input[data-strategy-param]")
    .forEach((input) => {
      values[input.dataset.strategyParam] = input.value.trim();
    });
  return values;
}

async function saveStrategyConfig() {
  const result = await api("/api/config", {
    method: "POST",
    body: JSON.stringify({ config: collectStrategyConfig() }),
  });
  renderConfig(result.config || {});
  renderStrategies(currentStrategies, result.config || {});
  return result.config || {};
}

function renderDataProfile(profile) {
  currentDataProfile = profile || {};
  const isRemote = currentDataProfile.history_mode === "remote";
  if (isRemote) {
    const server = currentDataProfile.history_server || {};
    $("dataState").textContent = server.ok
      ? `远端历史服务可用，${server.contract_count || 0} 个合约`
      : "远端历史服务不可用";
  } else {
    $("dataState").textContent = currentDataProfile.exists
      ? `${currentDataProfile.row_count || 0} 行，${(currentDataProfile.symbols || []).length} 个标的`
      : "数据文件不存在";
  }

  const cache = currentDataProfile.history_cache || {};
  renderKeyValues($("dataProfile"), [
    ["数据模式", isRemote ? "远端历史服务" : "本地 CSV"],
    ["路径", currentDataProfile.path || "-"],
    ["缓存目录", cache.path || "-"],
    ["缓存 TTL", cache.ttl_seconds !== undefined ? `${cache.ttl_seconds} 秒` : "-"],
    ["缓存文件数", cache.file_count !== undefined ? String(cache.file_count) : "-"],
    ["时间范围", currentDataProfile.start && currentDataProfile.end ? `${currentDataProfile.start} 到 ${currentDataProfile.end}` : "-"],
    ["行数", String(currentDataProfile.row_count || 0)],
    ["标的", ((isRemote ? currentDataProfile.history_contracts : currentDataProfile.symbols) || []).join(", ") || "-"],
    ["坏行", String(currentDataProfile.bad_rows || 0)],
    ["总成交量", formatNumber(currentDataProfile.total_volume, 0)],
  ]);

  const warningList = $("dataWarnings");
  warningList.innerHTML = "";
  const warnings = currentDataProfile.warnings || [];
  if (!warnings.length) {
    const ok = document.createElement("div");
    ok.className = "ok-line";
    ok.textContent = "基础字段和数值校验通过。";
    warningList.appendChild(ok);
  } else {
    warnings.forEach((warning) => {
      const item = document.createElement("div");
      item.className = "warning-line";
      item.textContent = warning;
      warningList.appendChild(item);
    });
  }

  renderTable(
    $("dataPreview"),
    [
      { label: "日期", key: "timestamp" },
      { label: "标的", render: (row) => `${row.symbol || ""}.${row.exchange || ""}` },
      { label: "开盘", key: "open" },
      { label: "最高", key: "high" },
      { label: "最低", key: "low" },
      { label: "收盘", key: "close" },
      { label: "成交量", key: "volume" },
    ],
    currentDataProfile.preview || [],
    "暂无数据预览"
  );
}

function renderRunHistory(runs) {
  $("runCount").textContent = `${runs.length} 次运行`;
  const container = $("runHistory");
  container.innerHTML = "";
  if (!runs.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "暂无运行档案";
    container.appendChild(empty);
    return;
  }
  const table = document.createElement("table");
  table.className = "data-table";
  table.innerHTML = "<thead><tr><th>运行 ID</th><th>时间</th><th>状态</th><th>最终权益</th><th>收益率</th><th>回撤</th><th>操作</th></tr></thead>";
  const tbody = document.createElement("tbody");
  runs.forEach((run) => {
    const tr = document.createElement("tr");
    const cells = [
      run.id,
      run.created_at,
      run.ok ? "成功" : "失败",
      formatMoney(run.summary?.final_equity),
      formatPercent(run.summary?.total_return),
      formatPercent(run.summary?.max_drawdown),
    ];
    cells.forEach((value) => {
      const td = document.createElement("td");
      td.textContent = value || "-";
      tr.appendChild(td);
    });
    const action = document.createElement("td");
    const button = document.createElement("button");
    button.className = "secondary compact";
    button.dataset.runId = run.id;
    button.textContent = "查看";
    action.appendChild(button);
    tr.appendChild(action);
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  container.appendChild(table);
}

async function loadRuns() {
  const payload = await api("/api/runs");
  renderRunHistory(payload.runs || []);
}

$("runHistory").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-run-id]");
  if (!button) return;
  setBusy("正在加载运行档案");
  try {
    const payload = await api(`/api/run?id=${encodeURIComponent(button.dataset.runId)}`);
    const run = payload.run || {};
    output.textContent = run.output || "";
    renderReport(run.report || {});
    renderEvents(run.events || []);
    if (run.report?.summary) {
      renderMetrics(run.report.summary);
    }
    if (run.report?.equity_curve) {
      drawEquityCurve(run.report.equity_curve);
    }
    navigateTo("report");
    setBusy("运行档案已加载");
  } catch (error) {
    output.textContent = String(error);
    setBusy("运行档案加载失败");
  }
});

function renderAgentSessions(sessions) {
  const list = $("agentSessions");
  list.innerHTML = "";
  if (!sessions.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "暂无会话";
    list.appendChild(empty);
    return;
  }
  sessions.forEach((session) => {
    const button = document.createElement("button");
    button.className = "session-item";
    button.dataset.sessionId = session.id;
    button.classList.toggle("active", currentAgentSession?.id === session.id);
    const title = document.createElement("strong");
    title.textContent = session.title || "新的研究会话";
    const meta = document.createElement("span");
    meta.textContent = `${session.provider || "agent"} · ${session.message_count || 0} 条`;
    button.append(title, meta);
    list.appendChild(button);
  });
}

function renderAgentMessages(messages) {
  agentMessages.innerHTML = "";
  if (!messages || messages.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "开始一个问题，后续回答会保留在这个会话里。";
    agentMessages.appendChild(empty);
    return;
  }
  messages.forEach((message) => {
    const row = document.createElement("div");
    row.className = `chat-message ${message.role === "user" ? "user" : "assistant"}`;
    const role = document.createElement("span");
    role.textContent = message.role === "user" ? "你" : "助手";
    const content = document.createElement("div");
    content.textContent = message.content || "";
    row.append(role, content);
    agentMessages.appendChild(row);
  });
  agentMessages.scrollTop = agentMessages.scrollHeight;
}

function applyAgentSession(session) {
  currentAgentSession = session;
  localStorage.setItem("katrade_agent_session_id", session.id);
  $("providerSelect").value = session.provider || "kimi_coding";
  $("modelInput").value = session.model || currentProviders[$("providerSelect").value]?.default_model || "";
  renderAgentMessages(session.messages || []);
}

async function loadAgentSession(sessionId) {
  const payload = await api(`/api/agent/session?id=${encodeURIComponent(sessionId)}`);
  applyAgentSession(payload.session);
  await loadAgentSessions();
}

async function loadAgentSessions() {
  const payload = await api("/api/agent/sessions");
  renderAgentSessions(payload.sessions || []);
  return payload.sessions || [];
}

async function newAgentSession() {
  const provider = $("providerSelect").value || "kimi_coding";
  const model = $("modelInput").value || currentProviders[provider]?.default_model || "";
  const payload = await api("/api/agent/session", {
    method: "POST",
    body: JSON.stringify({ provider, model }),
  });
  applyAgentSession(payload.session);
  await loadAgentSessions();
}

async function ensureAgentReady() {
  const sessions = await loadAgentSessions();
  if (currentAgentSession) return;
  const saved = localStorage.getItem("katrade_agent_session_id");
  const candidate = sessions.find((session) => session.id === saved) || sessions[0];
  if (candidate) {
    await loadAgentSession(candidate.id);
    return;
  }
  await newAgentSession();
}

async function loadStatus() {
  const status = await api("/api/status");
  renderConfig(status.config || {});
  renderProviders(status.providers || {});
  renderMetrics(status.summary || {});
  renderEvents(status.events || []);
  drawEquityCurve(status.equity_curve || []);
  renderReport(status.report || {});
  renderDataProfile(status.data_profile || {});
  renderStrategies(status.strategies || [], status.config || {});
  renderRunHistory(status.runs || []);
}

async function runBacktestJob() {
  navigateTo("runs");
  setBusy("正在运行回测");
  output.textContent = "";
  const result = await api("/api/backtest", { method: "POST", body: "{}" });
  renderRun(result);
  setBusy(result.ok ? "回测完成" : "回测失败");
  return result;
}

$("agentSessions").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-session-id]");
  if (!button) return;
  agentStatus.textContent = "正在加载会话";
  try {
    await loadAgentSession(button.dataset.sessionId);
    agentStatus.textContent = "只读模式：Agent 不会直接修改项目文件。";
  } catch (error) {
    agentStatus.textContent = String(error);
  }
});

$("newAgentSession").addEventListener("click", async () => {
  agentStatus.textContent = "正在创建会话";
  try {
    await newAgentSession();
    agentStatus.textContent = "新会话已创建";
  } catch (error) {
    agentStatus.textContent = String(error);
  }
});

$("runBacktest").addEventListener("click", async () => {
  try {
    await runBacktestJob();
  } catch (error) {
    output.textContent = String(error);
    setBusy("回测失败");
  }
});

$("saveStrategies").addEventListener("click", async () => {
  setBusy("正在保存策略配置");
  try {
    await saveStrategyConfig();
    setBusy("策略配置已保存");
  } catch (error) {
    output.textContent = String(error);
    setBusy("策略配置保存失败");
  }
});

$("runStrategyBacktest").addEventListener("click", async () => {
  setBusy("正在保存策略配置");
  try {
    await saveStrategyConfig();
    await runBacktestJob();
  } catch (error) {
    output.textContent = String(error);
    setBusy("策略回测失败");
  }
});

$("runChecks").addEventListener("click", async () => {
  navigateTo("runs");
  setBusy("正在运行检查");
  output.textContent = "";
  try {
    const result = await api("/api/check", { method: "POST", body: "{}" });
    output.textContent = result.output || "";
    setBusy(result.ok ? "检查通过" : "检查失败");
  } catch (error) {
    output.textContent = String(error);
    setBusy("检查失败");
  }
});

$("runPricing").addEventListener("click", async () => {
  navigateTo("runs");
  setBusy("正在运行期权定价");
  output.textContent = "";
  try {
    const result = await api("/api/pricing", { method: "POST", body: "{}" });
    output.textContent = result.output || "";
    setBusy(result.ok ? "期权定价完成" : "期权定价失败");
  } catch (error) {
    output.textContent = String(error);
    setBusy("期权定价失败");
  }
});

$("saveConfig").addEventListener("click", async () => {
  setBusy("正在保存配置");
  try {
    const result = await api("/api/config", {
      method: "POST",
      body: JSON.stringify({ config: collectConfig() }),
    });
    renderConfig(result.config || {});
    renderStrategies(currentStrategies, result.config || {});
    setBusy("配置已保存");
  } catch (error) {
    output.textContent = String(error);
    setBusy("配置保存失败");
  }
});

$("providerSelect").addEventListener("change", () => {
  const selected = $("providerSelect").value;
  $("modelInput").value = currentProviders[selected]?.default_model || "";
});

$("askAgent").addEventListener("click", async () => {
  const prompt = $("agentPrompt").value.trim();
  if (!prompt) {
    agentStatus.textContent = "请输入问题";
    return;
  }
  $("askAgent").disabled = true;
  agentStatus.textContent = "正在请求助手";
  try {
    const result = await api("/api/agent/message", {
      method: "POST",
      body: JSON.stringify({
        session_id: currentAgentSession?.id || "",
        provider: $("providerSelect").value,
        model: $("modelInput").value,
        prompt,
      }),
    });
    applyAgentSession(result.session);
    await loadAgentSessions();
    agentStatus.textContent = result.ok ? "回答完成" : result.error || "调用失败";
  } catch (error) {
    agentStatus.textContent = String(error);
  } finally {
    $("askAgent").disabled = false;
  }
});

loadStatus()
  .then(() => {
    renderRoute(routeFromPath());
  })
  .catch((error) => {
    output.textContent = String(error);
    setBusy("状态加载失败");
    renderRoute(routeFromPath());
  });
