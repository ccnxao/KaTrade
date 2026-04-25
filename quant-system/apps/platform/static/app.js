const $ = (id) => document.getElementById(id);

const configGrid = $("configGrid");
const output = $("commandOutput");
const commandState = $("commandState");
const agentOutput = $("agentOutput");

let currentConfig = {};
let currentProviders = {};

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
  const parts = Object.entries(currentProviders).map(([key, provider]) => {
    const sourceNames = {
      environment: "环境变量",
      "config/api_key.config": "配置文件",
    };
    const source = sourceNames[provider.source] || provider.source || "";
    const state = provider.configured ? `已配置${source ? `（${source}）` : ""}` : `未配置 ${provider.env}`;
    return `${provider.name}: ${state}`;
  });
  $("providerState").textContent = parts.length ? parts.join(" | ") : "未发现服务商";

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
  ctx.fillStyle = "#fbfcfa";
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

  ctx.strokeStyle = "#d9ded7";
  ctx.lineWidth = 1;
  for (let i = 0; i < 4; i += 1) {
    const y = padding + (height / 3) * i;
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(canvas.width - padding, y);
    ctx.stroke();
  }

  ctx.strokeStyle = "#2d6f4f";
  ctx.lineWidth = 3;
  ctx.beginPath();
  points.forEach((point, index) => {
    const x = padding + (width * index) / Math.max(points.length - 1, 1);
    const y = padding + height - ((point.equity - min) / range) * height;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.fillStyle = "#1f2520";
  ctx.font = "12px system-ui";
  ctx.fillText(formatMoney(max), padding, 18);
  ctx.fillText(formatMoney(min), padding, canvas.height - 10);
}

function renderRun(payload) {
  output.textContent = payload.output || "";
  renderMetrics(payload.summary || {});
  renderEvents(payload.events || []);
  drawEquityCurve(payload.equity_curve || []);
}

async function loadStatus() {
  const status = await api("/api/status");
  renderConfig(status.config || {});
  renderProviders(status.providers || {});
  renderMetrics(status.summary || {});
  renderEvents(status.events || []);
  drawEquityCurve(status.equity_curve || []);
}

$("runBacktest").addEventListener("click", async () => {
  setBusy("正在运行回测");
  output.textContent = "";
  try {
    const result = await api("/api/backtest", { method: "POST", body: "{}" });
    renderRun(result);
    setBusy(result.ok ? "回测完成" : "回测失败");
  } catch (error) {
    output.textContent = String(error);
    setBusy("回测失败");
  }
});

$("runChecks").addEventListener("click", async () => {
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
  agentOutput.textContent = "正在请求助手...";
  try {
    const result = await api("/api/agent", {
      method: "POST",
      body: JSON.stringify({
        provider: $("providerSelect").value,
        model: $("modelInput").value,
        prompt: $("agentPrompt").value,
      }),
    });
    agentOutput.textContent = result.ok ? result.content : result.error;
  } catch (error) {
    agentOutput.textContent = String(error);
  }
});

loadStatus().catch((error) => {
  output.textContent = String(error);
  setBusy("状态加载失败");
});
