const $ = (id) => document.getElementById(id);

const configGrid = $("configGrid");
const output = $("commandOutput");
const commandState = $("commandState");
const agentOutput = $("agentOutput");

let currentConfig = {};
let currentProviders = {};

function formatMoney(value) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString(undefined, {
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
    const state = provider.configured ? "ready" : provider.env;
    return `${provider.name}: ${state}`;
  });
  $("providerState").textContent = parts.length ? parts.join(" | ") : "No providers";

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

function renderEvents(events) {
  $("eventCount").textContent = `${events.length} events`;
  const list = $("eventsList");
  list.innerHTML = "";
  events.slice().reverse().forEach((event) => {
    const row = document.createElement("div");
    row.className = "event-row";
    row.innerHTML = `<span>#${event.sequence}</span><strong>${event.type}</strong><div>${event.message}</div>`;
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
    $("chartState").textContent = "No run loaded";
    return;
  }
  $("chartState").textContent = `${points.length} points`;

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
  setBusy("Running backtest");
  output.textContent = "";
  try {
    const result = await api("/api/backtest", { method: "POST", body: "{}" });
    renderRun(result);
    setBusy(result.ok ? "Backtest complete" : "Backtest failed");
  } catch (error) {
    output.textContent = String(error);
    setBusy("Backtest failed");
  }
});

$("runChecks").addEventListener("click", async () => {
  setBusy("Running checks");
  output.textContent = "";
  try {
    const result = await api("/api/check", { method: "POST", body: "{}" });
    output.textContent = result.output || "";
    setBusy(result.ok ? "Checks passed" : "Checks failed");
  } catch (error) {
    output.textContent = String(error);
    setBusy("Checks failed");
  }
});

$("runPricing").addEventListener("click", async () => {
  setBusy("Running pricing demo");
  output.textContent = "";
  try {
    const result = await api("/api/pricing", { method: "POST", body: "{}" });
    output.textContent = result.output || "";
    setBusy(result.ok ? "Pricing complete" : "Pricing failed");
  } catch (error) {
    output.textContent = String(error);
    setBusy("Pricing failed");
  }
});

$("saveConfig").addEventListener("click", async () => {
  setBusy("Saving config");
  try {
    const result = await api("/api/config", {
      method: "POST",
      body: JSON.stringify({ config: collectConfig() }),
    });
    renderConfig(result.config || {});
    setBusy("Config saved");
  } catch (error) {
    output.textContent = String(error);
    setBusy("Config save failed");
  }
});

$("providerSelect").addEventListener("change", () => {
  const selected = $("providerSelect").value;
  $("modelInput").value = currentProviders[selected]?.default_model || "";
});

$("askAgent").addEventListener("click", async () => {
  agentOutput.textContent = "Working...";
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
  setBusy("Status load failed");
});
