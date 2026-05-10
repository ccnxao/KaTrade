// == Core Utilities ==
// R17: HTML 转义，防止 XSS
const esc = (s) => { const d = document.createElement("span"); d.textContent = String(s||""); return d.innerHTML; };

const $ = (id) => document.getElementById(id);
const setText = (id, text) => { const el = $(id); if (el) el.textContent = text; };

// GAP-029: Toast 通知系统
function showToast(msg, type) {
  const container = document.getElementById("toastContainer") || (()=>{
    const d = document.createElement("div"); d.id="toastContainer";
    d.className = "toast-container";
    document.body.appendChild(d); return d;
  })();
  const el = document.createElement("div");
  el.className = "toast " + (type || "info");
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => { el.style.opacity="0"; el.style.transition="opacity 0.3s"; setTimeout(()=>el.remove(),300); }, 5000);
}

// GAP-028: SSE 实时事件流 (带指数退避重连)
let _sseBackoff = 1;
function connectEventStream() {
  try {
    const src = new EventSource("/api/events/stream");
    src.onopen = () => { _sseBackoff = 1; };  // 连接成功, 重置退避
    src.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data);
        if (d.event && d.event.includes("error")) showToast(d.message||d.event, "error");
        else if (d.event && d.event.includes("warn")) showToast(d.message||d.event, "warn");
        else if (d.event && d.event.includes("fill")) showToast(d.message||d.event, "info");
      } catch(_) {}
    };
    src.onerror = () => { src.close(); const delay = Math.min(_sseBackoff * 2000, 60000); _sseBackoff = Math.min(_sseBackoff * 2, 32); setTimeout(connectEventStream, delay); };
  } catch(_) { const delay = Math.min(_sseBackoff * 2000, 60000); _sseBackoff = Math.min(_sseBackoff * 2, 32); setTimeout(connectEventStream, delay); }
}
const pageMeta = {
  dashboard: ["总览","净值、收益、回撤和市场状态"],
  paper: ["虚拟盘","策略逐笔运行、OKX提交、订单流水"],
  strategies: ["策略","查看策略池和启用状态"],
  agents: ["交易Agent","多智能体资金分配、绩效追踪"],
  market: ["行情","OKX实时行情状态"],
  orders: ["订单","订单生命周期和成交回报"],
  risk: ["风控","Kill switch、订单限制和运行风险"],
  events: ["事件","行情流、策略周期、风控和成交journal"],
  config: ["配置","调整本地运行参数"],
  okx: ["OKX","API密钥、交易环境配置"],
};

function formatMoney(v) { if (v === undefined || v === null || Number.isNaN(Number(v))) return "-"; return Number(v).toLocaleString("zh-CN",{minimumFractionDigits:2,maximumFractionDigits:2}); }
function formatPercent(v) { if (v === undefined || v === null || Number.isNaN(Number(v))) return "-"; return (Number(v)*100).toFixed(2)+"%"; }
function formatNumber(v, d) { d = d || 2; if (v === undefined || v === null || Number.isNaN(Number(v))) return "-"; return Number(v).toLocaleString("zh-CN",{minimumFractionDigits:d,maximumFractionDigits:d}); }
function formatAgeSeconds(v) {
  const n = Number(v);
  if (!Number.isFinite(n) || n < 0) return "-";
  if (n < 60) return Math.round(n) + "秒";
  if (n < 3600) return Math.round(n / 60) + "分";
  if (n < 86400) return (n / 3600).toFixed(1) + "小时";
  return (n / 86400).toFixed(1) + "天";
}
function formatDateTimeText(t) {
  if (!t) return "-";
  try {
    const d = new Date(t);
    if (Number.isNaN(d.getTime())) return String(t);
    return d.toLocaleString("zh-CN",{timeZone:"Asia/Shanghai",hour12:false});
  } catch(_) { return String(t); }
}
function formatClockText(t) {
  if (!t) return "-";
  try {
    const d = new Date(t);
    if (Number.isNaN(d.getTime())) return String(t);
    return d.toLocaleTimeString("zh-CN",{timeZone:"Asia/Shanghai",hour12:false});
  } catch(_) { return String(t); }
}
function listText(v) { return Array.isArray(v) ? v.join(", ") : (v || "-"); }

function setPill(id, text, state) {
  const el = $(id);
  if (!el) return;
  el.textContent = text;
  el.className = "status-pill " + (state || "neutral");
}

function stateFromBool(ok, warnIfUnknown) {
  if (ok === true) return "ok";
  if (ok === false) return "bad";
  return warnIfUnknown ? "warn" : "neutral";
}

// 底部状态栏
function updateStatusBar(text) { const el = document.getElementById("statusBarMid"); if (el && text) el.textContent = text; }
setInterval(() => {
  const cl = document.getElementById("statusBarRight");
  if (cl) cl.textContent = new Date().toLocaleTimeString("zh-CN",{timeZone:"Asia/Shanghai",hour12:false});
}, 1000);

let currentConfig = {}, currentStrategies = [], currentPaperStatus = {}, paperAutoRefreshTimer = null, paperAutoRefreshEnabled = true, paperLastRefreshAt = "";

async function api(path, opts) {
  opts = opts || {};
  const r = await fetch(path, { headers: {"Content-Type":"application/json"}, ...opts });
  const p = await r.json();
  if (!r.ok) throw new Error(p.error || "HTTP "+r.status);
  return p;
}

// == Routing ==
function routeFromPath() { const n = window.location.pathname.replace(/^\/+/,"") || "dashboard"; return pageMeta[n] ? n : "dashboard"; }
function activeRouteName() { return document.querySelector(".page.active")?.dataset.page || routeFromPath(); }

function renderRoute(route) {
  const page = pageMeta[route] ? route : "dashboard";
  document.querySelectorAll(".page").forEach(s => s.classList.toggle("active", s.dataset.page === page));
  document.querySelectorAll("[data-route]").forEach(l => l.classList.toggle("active", l.dataset.route === page));
  $("pageTitle").textContent = pageMeta[page][0];
  $("pageSubtitle").textContent = pageMeta[page][1];
  stopMarketPoll(); clearPaperAutoRefreshTimer();
  if (page === "dashboard" || page === "paper" || page === "market") { startMarketPoll(); }
  if (page === "market") { loadMarketStream().catch(()=>{}); }
  if (page === "paper") { loadPaperStatus().catch(()=>{}); schedulePaperAutoRefresh(3000); }
  if (page === "agents") { loadAgentPage().catch(e=>{ $("agentPageStatus").textContent = String(e); }); }
  if (page === "orders") { loadOrdersCenter().catch(()=>{}); }
  if (page === "risk") {
    loadRiskStatus().catch(()=>{});
    loadBackendEquityWidgets({risk:true}).catch(()=>{});
  }
  if (page === "dashboard") { loadBackendEquityWidgets({dashboard:true}).catch(()=>{}); }
  if (page === "events") { loadEvents().catch(()=>{}); }
  if (page === "okx") { loadOkxConfig().catch(()=>{}); }
}

function navigateTo(route, push) {
  push = push !== false;
  const page = pageMeta[route] ? route : "dashboard";
  if (push && window.location.pathname !== "/"+page) history.pushState({page},"","/"+page);
  renderRoute(page);
}

document.addEventListener("click", e => {
  const link = e.target.closest("a[data-route]");
  if (!link) return;
  e.preventDefault();
  navigateTo(link.dataset.route);
});
window.addEventListener("popstate", () => renderRoute(routeFromPath()));
// backButton 已从 topbar 移除，浏览器自带后退按钮即可

// == Table / KeyValues helpers ==
function renderTable(container, columns, rows, emptyText) {
  if (!container) return;
  container.innerHTML = "";
  if (!rows || !rows.length) { container.innerHTML = '<div class="empty-state">'+emptyText+'</div>'; return; }
  const table = document.createElement("table"); table.className = "data-table";
  const thead = document.createElement("thead"), hr = document.createElement("tr");
  columns.forEach(c => { const th = document.createElement("th"); th.textContent = c.label; hr.appendChild(th); });
  thead.appendChild(hr); table.appendChild(thead);
  const tbody = document.createElement("tbody");
  rows.forEach(row => {
    const tr = document.createElement("tr");
    columns.forEach(c => {
      const td = document.createElement("td");
      td.textContent = c.render ? c.render(row) : (row[c.key] ?? "-");
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody); container.appendChild(table);
}

function renderKeyValues(container, items) {
  if (!container) return;
  container.innerHTML = "";
  items.forEach(([label, value]) => {
    const div = document.createElement("div"); div.className = "summary-item";
    const span = document.createElement("span"); span.textContent = label;
    const text = value === undefined || value === null || value === "" ? "-" : String(value);
    const strong = document.createElement("strong"); strong.textContent = text; strong.title = text;
    div.append(span, strong); container.appendChild(div);
  });
}

function renderOpsRibbon(status) {
  const el = $("dashboardOpsRibbon");
  if (!el) return;
  const okx = status.okx || {};
  const paper = status.paper || {};
  const backend = status.backend_core || {};
  const coreStatus = backend.status || {};
  const dataQuality = paper.data_quality || {};
  const cxxRunner = dataQuality.cxx_runner || {};
  const cxxRealtime = dataQuality.cxx_realtime || {};
  const market = status.market_quality || {};
  const backendOnline = Boolean(coreStatus.online || backend.available);
  const cxxRunnerOnline = Boolean(cxxRunner.running || cxxRealtime.ok);
  const cxxOnline = Boolean(backendOnline || cxxRunnerOnline || backend.binary_found);
  const marketOk = market.ok === true || market.status === "ok" || market.summary?.ok === true;
  const cards = [
    {
      label: "OKX",
      value: okx.configured ? (okx.simulated ? "模拟盘已配置" : "实盘配置存在") : "未配置",
      meta: okx.trading_enabled ? "交易权限已启用" : "交易权限未启用",
      state: okx.configured && okx.simulated ? "ok" : stateFromBool(okx.configured, true),
    },
    {
      label: "虚拟盘",
      value: paper.status || "stopped",
      meta: paper.last_success_at ? "最近成功 " + formatClockText(paper.last_success_at) : "等待 tick",
      state: paper.status === "running" ? "ok" : "warn",
    },
    {
      label: "C++ 核心",
      value: backendOnline ? "backendd 在线" : (cxxRunnerOnline ? "行情 runner 在线" : "离线"),
      meta: backendOnline
        ? "C++ 后端服务可用"
        : cxxRunnerOnline
        ? "backendd 未接管，realtime_engine 正在工作"
        : (backend.error || "等待质量报告"),
      state: cxxOnline ? "ok" : "warn",
    },
    {
      label: "行情",
      value: marketOk ? "质量通过" : "需要关注",
      meta: market.source || market.decision?.reason || "-",
      state: marketOk ? "ok" : "warn",
    },
  ];
  el.innerHTML = cards.map(card => (
    '<div class="ops-card '+card.state+'"><span>'+esc(card.label)+'</span><strong>'+esc(card.value)+'</strong><small>'+esc(card.meta)+'</small></div>'
  )).join("");
}

function updateTopbarStatus(status) {
  const okx = status.okx || {};
  const paper = status.paper || {};
  const backend = status.backend_core || {};
  const dataQuality = paper.data_quality || {};
  const cxxRunner = dataQuality.cxx_runner || {};
  const cxxRealtime = dataQuality.cxx_realtime || {};
  const backendOnline = Boolean((backend.status || {}).online || backend.available);
  const cxxRunnerOnline = Boolean(cxxRunner.running || cxxRealtime.ok);
  setPill("topbarOkx", okx.configured ? (okx.simulated ? "OKX 模拟盘" : "OKX 实盘") : "OKX 未配置", okx.configured && okx.simulated ? "ok" : "warn");
  setPill("topbarPaper", "虚拟盘 " + (paper.status || "-"), paper.status === "running" ? "ok" : "neutral");
  setPill(
    "topbarCxx",
    backendOnline ? "C++ backendd 在线" : (cxxRunnerOnline ? "C++ 行情在线" : "C++ 离线"),
    (backendOnline || cxxRunnerOnline) ? "ok" : "warn"
  );
}

// == Metrics ==
function renderMetrics(summary) {
  $("metricEquity").textContent = formatMoney(summary.final_equity);
  $("metricReturn").textContent = formatPercent(summary.total_return);
  $("metricDrawdown").textContent = formatPercent(summary.max_drawdown);
  $("metricFills").textContent = summary.total_fills ?? "-";
  $("metricSharpe").textContent = formatNumber(summary.annualized_sharpe, 3);
  $("metricSignals").textContent = summary.total_signals ?? "-";
  $("metricStrategies").textContent = summary.strategy_count ?? "-";
  $("metricCommission").textContent = "$" + formatNumber(summary.total_commission, 2);
}

// == Broker / OKX ==
function renderBrokerOkx(broker, okx) {
  const stateEl = $("okxPanelState"), summaryEl = $("okxPanelSummary");
  if (!summaryEl) return;
  const items = [];
  if (broker && broker.display_name) {
    items.push(["券商", broker.display_name]);
    items.push(["状态", broker.state || "-"]);
    items.push(["交易", broker.trading_enabled ? "已启用" : "未启用"]);
    items.push(["品种数", String((broker.instruments || []).length)]);
  }
  if (okx) {
    items.push(["API Key", okx.key_configured ? "已配置" : "未配置"]);
    items.push(["Secret", okx.secret_configured ? "已配置" : "未配置"]);
    items.push(["模式", okx.simulated ? "模拟盘" : (okx.configured ? "实盘" : "未配置")]);
  }
  if (stateEl) stateEl.textContent = items.length ? (broker && broker.state || "-") : "等待数据";
  renderKeyValues(summaryEl, items.length ? items : [["状态", "等待数据"]]);
}

// == Data Profile ==
function renderDataProfile(profile) {
  const stateEl = $("dataProfileState"), summaryEl = $("dataProfileSummary");
  if (!summaryEl) return;
  const items = [];
  if (profile && profile.row_count) {
    items.push(["行数", String(profile.row_count)]);
    items.push(["品种", String((profile.symbols || []).length)]);
    items.push(["起始", profile.start || "-"]);
    items.push(["结束", profile.end || "-"]);
    items.push(["模式", profile.history_mode || "local"]);
  }
  if (stateEl) stateEl.textContent = profile && profile.row_count ? profile.row_count + " 行" : "等待数据";
  renderKeyValues(summaryEl, items.length ? items : [["状态", "等待回测数据"]]);
}

// == Regime ==
function renderRegime(regime, regimeByInst) {
  const container = $("regimeByInstrument"), label = $("regimeLabel");
  if (!container) return;
  let items = regimeByInst || {};
  if (!Object.keys(items).length && regime && regime.regime) items = {"ALL": regime};
  if (!Object.keys(items).length) {
    container.innerHTML = '<div class="panel metric"><span>-</span><strong>等待数据</strong></div>';
    if (label) label.textContent = "等待C++质量报告";
    return;
  }
  if (label) label.textContent = Object.keys(items).length + " 个品种";
  let html = "";
  for (let inst in items) {
    const r = items[inst];
    const name = inst.indexOf(".") > 0 ? inst.split(".")[0] : inst;
    const confStr = r.confidence != null ? (r.confidence*100).toFixed(0)+"%" : "";
    const hasProbs = r.tp != null || r.rp != null || r.dp != null;
    const probStr = hasProbs
      ? "趋势"+(r.tp!=null?(r.tp*100).toFixed(0):"?")+"% 反转"+(r.rp!=null?(r.rp*100).toFixed(0):"?")+"% 防御"+(r.dp!=null?(r.dp*100).toFixed(0):"?")+"%"
      : "M"+(r.mw!=null?(r.mw*100).toFixed(0):"?")+"% R"+(r.rw!=null?(r.rw*100).toFixed(0):"?")+"% D"+(r.dw!=null?(r.dw*100).toFixed(0):"?")+"%";
    const weightStr = "策略 M"+(r.mw!=null?(r.mw*100).toFixed(0):"?")+"% R"+(r.rw!=null?(r.rw*100).toFixed(0):"?")+"% D"+(r.dw!=null?(r.dw*100).toFixed(0):"?")+"%";
    html += '<div class="panel metric"><span>'+esc(name)+'</span><strong>'+esc(String(r.regime||"-"))+' <small>'+confStr+'</small></strong><small>'+probStr+'</small><small style="color:#64748b;font-size:11px">'+weightStr+'</small></div>';
  }
  container.innerHTML = html;
}

async function pollMarketQuality() {
  try { const r=await fetch("/api/market/quality"); const m=await r.json(); if(m&&m.ok) renderRegime(m.regime||{},m.regime_by_instrument||{}); } catch(_){}
  try { const pr=await fetch("/api/paper/status?limit=0"); const pd=await pr.json(); if(pd&&pd.paper) renderPositionOverview(pd.paper); } catch(_){}
  if (activeRouteName() === "dashboard") { loadBackendEquityWidgets({dashboard:true}).catch(()=>{}); }
  if (activeRouteName() === "risk") { loadBackendEquityWidgets({risk:true}).catch(()=>{}); }
}
// R18: 改为按页面启停，不再全局轮询
let marketPollTimer = null;
function startMarketPoll() { if (!marketPollTimer) { pollMarketQuality(); marketPollTimer = setInterval(pollMarketQuality, 15000); } }
function stopMarketPoll() { if (marketPollTimer) { clearInterval(marketPollTimer); marketPollTimer = null; } }

// == Position Overview ==
async function renderPositionOverview(paper) {
  const container = $("positionOverviewCards"), label = $("positionOverviewLabel");
  if (!container) return;

  // 仅从 OKX 拉取真实持仓（虚拟盘已直连 OKX，不再本地撮合，paper 账本为冗余中间层）
  let okxPositions = [];
  try { const r=await fetch("/api/okx/positions"); const d=await r.json(); if(d&&d.ok) okxPositions=d.positions||[]; } catch(_){}

  const total = okxPositions.length;
  if (!total) { container.innerHTML='<div class="panel metric"><span>-</span><strong>暂无持仓</strong></div>'; if(label) label.textContent="0 个持仓"; setText("paperPortfolioState","-"); setText("paperPortfolioState2","-"); return; }
  if (label) label.textContent = total + " 个持仓 (OKX)";
  setText("paperPortfolioState", total+" 个");
  setText("paperPortfolioState2", total+" 个");

  let html = "";
  okxPositions.forEach(o => {
    const name = (o.inst_id||"").replace("-SWAP",""),
          side = o.side==="long"?"多头":"空头",
          qty  = parseFloat(o.pos)||0,
          avg  = parseFloat(o.avg_px)||0,
          mark = parseFloat(o.mark_px)||0,
          upl  = parseFloat(o.upl)||0,
          liq  = parseFloat(o.liq_px)||0,
          frate = parseFloat(o.funding_rate)||0;
    const liqWarn = o.liq_warning;
    const liqDist = o.liq_distance_pct;
    const fundingStr = frate ? (' 资金'+(frate*100).toFixed(4)+'%') : '';
    const liqStr = liq>0 ? (' / 强平$'+formatNumber(liq,1)+(liqDist?'('+(liqDist*100).toFixed(1)+'%)':'')) : '';
    const liqStyle = liqWarn ? ' style="color:#f87171;font-weight:600"' : '';
    const warnBadge = liqWarn ? ' <span style="background:#f87171;color:#fff;padding:0 4px;border-radius:2px;font-size:10px">强平预警</span>' : '';
    html += '<div class="panel metric"'+liqStyle+'><span>'+esc(name)+' <small>'+esc(side)+'</small>'+warnBadge+'</span><strong>'+formatNumber(qty,4)+'</strong><small>均价$'+formatNumber(avg,2)+' / 标记$'+formatNumber(mark,2)+liqStr+fundingStr+'</small><small>'+esc(String(o.lever))+'x '+esc(String(o.mgn_mode))+'</small><small class="'+(upl>=0?"positive":"negative")+'">浮动$'+formatNumber(upl,2)+'</small></div>';
  });
  container.innerHTML = html;
}

// == Config ==
function renderConfig(config) {
  currentConfig = {...config};
  $("configGrid").innerHTML = "";
  Object.keys(config).sort().forEach(k => {
    const div = document.createElement("div"); div.className = "field";
    const label = document.createElement("label"); label.textContent = k;
    const input = document.createElement("input"); input.value = config[k]; input.dataset.key = k;
    div.append(label, input); $("configGrid").appendChild(div);
  });
}
function collectConfig() { const v={}; $("configGrid").querySelectorAll("input").forEach(i=>{v[i.dataset.key]=i.value}); return v; }
$("saveConfig").addEventListener("click", async () => { try { await api("/api/config",{method:"POST",body:JSON.stringify({config:collectConfig()})}); alert("已保存"); } catch(e) { alert("保存失败: "+e); } });

// == Strategies ==
function translateStrategyStyle(s) { const m={trend:"趋势",mean_reversion:"反转",defensive:"防御",hybrid:"混合"}; return m[s]||s||"-"; }
function renderStrategies(strategies) {
  currentStrategies = strategies || [];
  $("strategyCatalogState").textContent = currentStrategies.length+" 个策略";
  const grid = $("strategyCatalog"); grid.innerHTML = "";
  currentStrategies.forEach(s => {
    const card = document.createElement("div"); card.className = "strategy-card";
    card.innerHTML = '<h4>'+esc(s.display_name || s.id || "-")+'</h4><span class="badge">'+esc(translateStrategyStyle(s.style))+'</span><p>'+esc(s.description || "")+'</p>';
    grid.appendChild(card);
  });
}

// == Paper Trading ==
function paperStrategyIds() {
  return (currentPaperStatus.settings||{}).strategy_ids || [];
}

function renderPaperStrategyPicker() {
  const container = $("paperStrategyPicker"); if (!container) return;
  const selected = new Set(paperStrategyIds());
  $("paperStrategyState").textContent = currentStrategies.length ? selected.size+"/"+currentStrategies.length+"个已选" : "加载中";
  container.innerHTML = "";
  if (!currentStrategies.length) {
    (async()=>{ try{ const s=await api("/api/status"); if(s.strategies) { currentStrategies=s.strategies; renderPaperStrategyPicker(); } } catch(_){} })();
    container.innerHTML = '<div class="empty-state">策略目录加载中...</div>'; return;
  }
  currentStrategies.forEach(s => {
    const label = document.createElement("label"); label.className = "strategy-chip strategy-chip-"+(s.style||"hybrid");
    const cb = document.createElement("input"); cb.type = "checkbox"; cb.checked = selected.has(s.id); cb.dataset.paperStrategyId = s.id;
    const span = document.createElement("span"); span.textContent = s.display_name||s.id;
    label.append(cb, span); container.appendChild(label);
  });
}

function renderPaperStatus(paper, markersPayload) {
  currentPaperStatus = paper || {};
  const settings = currentPaperStatus.settings || {};
  const summary = currentPaperStatus.summary || {};
  const cycle = currentPaperStatus.latest_cycle || {};
  const okxAuto = currentPaperStatus.okx_auto_submit || {};
  const dataSources = (currentPaperStatus.data_quality||{}).sources || "-";

  $("paperState").textContent = currentPaperStatus.status || "-";
  setText("paperLastTickState", formatClockText(currentPaperStatus.last_success_at));
  setText("paperNextTickState", formatClockText(currentPaperStatus.next_tick_after));
  $("paperOrderState").textContent = String(summary.pending_orders || currentPaperStatus.live?.pending_orders?.length || 0);
  renderPaperRuntime(currentPaperStatus);

  renderPaperPerformance(currentPaperStatus.performance||{});
  renderPaperDataQuality(currentPaperStatus.data_quality||{});
  renderPaperDiagnostics(currentPaperStatus.diagnostics||{});
  renderPaperStrategyPicker();
  renderTable($("paperPortfolioTable"), [
    {label:"合约",render:r=>(r.instrument&&r.instrument.key)||"-"},
    {label:"数量",render:r=>formatNumber(r.quantity,6)},
    {label:"成本",render:r=>formatNumber(r.avg_cost,4)},
    {label:"市价",render:r=>formatNumber(r.market_price,4)},
    {label:"市值",render:r=>formatMoney(r.market_value)},
    {label:"权重",render:r=>formatPercent(r.weight)},
  ], (currentPaperStatus.portfolio||{}).positions||[], "暂无虚拟盘持仓");

  renderPaperOkxAutoSubmit(okxAuto);

  // Order flow (markers)
  const markers = (markersPayload||{}).markers || [];
  const trades = markers.filter(m => ["order","fill","expired"].includes(m.type))
    .map(m => ({...m, event_name: m.type==="fill"?"成交":m.type==="expired"?"过期":"挂单"}))
    .sort((a,b) => (Number(b.t||0)-Number(a.t||0)));
  const counts = trades.reduce((a,r) => { a[r.type]=(a[r.type]||0)+1; return a; }, {});
  $("paperTradeState").textContent = trades.length ? "挂单"+(counts.order||0)+"/成交"+(counts.fill||0)+"/过期"+(counts.expired||0) : "暂无订单";
  renderTable($("paperTradesTable"), [
    {label:"时间",render:r=>formatDateTimeText(r.t)},
    {label:"事件",key:"event_name"},
    {label:"合约",key:"inst_id"},
    {label:"方向",key:"side"},
    {label:"价格",render:r=>formatNumber(r.price,4)},
    {label:"数量",render:r=>formatNumber(r.quantity,6)},
    {label:"均价",render:r=>r.avg_price?formatNumber(r.avg_price,4):"-"},
    {label:"手续费",render:r=>r.commission?("$"+formatNumber(r.commission,4)):"-"},
    {label:"滑点(bp)",render:r=>r.slippage_bps?formatNumber(r.slippage_bps,1):"-"},
    {label:"状态",key:"status"},
    {label:"说明",render:r=>r.reason||r.text||"-"},
  ], trades.slice(0,120), "暂无虚拟盘订单");
}

function renderPaperRuntime(paper) {
  const stateEl = $("paperRuntimeState");
  const summaryEl = $("paperRuntimeSummary");
  if (!summaryEl) return;
  const settings = paper.settings || {};
  const diag = paper.diagnostics || {};
  const latest = paper.latest_cycle || {};
  const strategyIds = settings.strategy_ids || [];
  if (stateEl) stateEl.textContent = paper.tick_running ? "执行中" : (paper.status || "-");
  renderKeyValues(summaryEl, [
    ["模式", settings.mode || "-"],
    ["品种", listText(settings.instruments)],
    ["策略数", String(strategyIds.length || 0)],
    ["轮询间隔", (settings.poll_seconds || "-") + "s"],
    ["最近周期", formatDateTimeText(latest.label || diag.latest_cycle_label)],
    ["Tick 数", String(latest.tick_count ?? diag.latest_cycle_tick_count ?? 0)],
    ["上次原因", paper.last_skip_reason || paper.last_error || "-"],
    ["OKX 自动提交", settings.okx_auto_submit ? "已启用" : "未启用"],
  ]);
}

function renderPaperPerformance(perf) {
  const el = $("paperPerformanceSummary"); if (!el) return;
  renderKeyValues(el, [
    ["总周期", perf.total_cycles||0],
    ["最后耗时", (perf.last_runtime_ms||0)+"ms"],
    ["平均耗时", (perf.avg_runtime_ms||0).toFixed(1)+"ms"],
    ["平均tick/周期", (perf.avg_ticks_per_cycle||0).toFixed(1)],
    ["平均订单/周期", (perf.avg_orders_per_cycle||0).toFixed(1)],
    ["平均成交/周期", (perf.avg_fills_per_cycle||0).toFixed(1)],
  ]);
}

function renderPaperDataQuality(dq) {
  const el = $("paperDataQualitySummary"); if (!el) return;
  const s = dq.summary || {};
  renderKeyValues(el, [
    ["状态", (s.ok?"正常":"需关注")],
    ["就绪", s.ready?"是":"否"],
    ["信息", s.message||"-"],
  ]);
  // C++ 实时引擎状态
  const cxx = dq.cxx_runner || {};
  const cxxState = $("cxxEngineState"), cxxSummary = $("cxxEngineSummary");
  if (cxxState) cxxState.textContent = cxx.running ? ("PID " + (cxx.pid || "?")) : (cxx.returncode != null ? "已退出(" + cxx.returncode + ")" : "未启动");
  if (cxxSummary) renderKeyValues(cxxSummary, [
    ["进程", cxx.running ? "运行中" : "已停止"],
    ["PID", cxx.pid || "-"],
    ["退出码", cxx.returncode != null ? String(cxx.returncode) : "-"],
    ["状态文件", cxx.status_file && cxx.status_file.exists ? "存在" : "不存在"],
    ["质量文件", cxx.quality_file && cxx.quality_file.exists ? "存在" : "不存在"],
  ]);
}

function renderPaperDiagnostics(diag) {
  $("paperDiagnosticsState").textContent = (diag.status||"unknown")==="ok"?"正常":"需关注";
  const risk = diag.risk || {}, orders = diag.orders || {};
  renderKeyValues($("paperDiagnosticsSummary"), [
    ["最近周期", formatDateTimeText(diag.latest_cycle_label)],
    ["风控动作", risk.action||"-"],
    ["风控原因", risk.reason||"-"],
    ["预计换手", formatPercent(risk.expected_turnover)],
    ["订单", (orders.orders_count||0)+"单/"+(orders.reports_count||0)+"回报"],
  ]);
  renderTable($("paperDiagnosticsChecks"), [
    {label:"检查项",key:"name"},{label:"状态",render:r=>r.ok?"通过":"阻断"},{label:"说明",key:"message"},
  ], diag.checks||[], "暂无诊断");
  // 策略诊断详情
  const stratDiag = diag.strategies || [];
  renderTable($("paperStrategyDiagnosticsTable"), [
    {label:"策略",key:"id"},{label:"状态",key:"status"},{label:"信号",render:r=>r.signal_count||"-"},{label:"说明",key:"message"},
  ], stratDiag, "暂无策略诊断");
}

function renderPaperOkxAutoSubmit(auto) {
  const el = $("paperOkxAutoState"), table = $("paperOkxAutoTable"), summary = $("paperOkxAutoSummary");
  if (!el) return;
  const recent = (Array.isArray(auto.recent) ? auto.recent : []).slice(-30).reverse();
  const enabled = Boolean(currentPaperStatus.settings?.okx_auto_submit || auto.enabled);
  const guard = auto.submission_guard || {};
  el.textContent = enabled ? (auto.last_message||"-") : "未启用";
  renderKeyValues(summary, [
    ["门禁状态", guard.ready ? "通过" : "阻断"],
    ["门禁原因", guard.reason||"-"],
    ["已提交OKX", String((auto.submitted_source_order_ids||[]).length)],
    ["活跃OKX单", String(guard.live_order_count||0)],
    ["陈旧OKX单", String(guard.stale_order_count||0)],
    ["最近提交", formatDateTimeText(recent.length?recent[0].at:"")],
  ]);
  renderTable(table, [
    {label:"时间",render:r=>formatDateTimeText(r.at)},
    {label:"源委托",render:r=>r.source_order_id||"-"},
    {label:"状态",key:"status"},
    {label:"说明",render:r=>(r.message||"").slice(0,80)},
  ], recent, "暂无OKX提交记录");
}

// Paper auto-refresh
function clearPaperAutoRefreshTimer() { if(paperAutoRefreshTimer){clearTimeout(paperAutoRefreshTimer);paperAutoRefreshTimer=null;} }
function schedulePaperAutoRefresh(delay) {
  clearPaperAutoRefreshTimer();
  if (!paperAutoRefreshEnabled || activeRouteName()!=="paper"){ $("paperAutoRefreshState").textContent="关闭"; return; }
  $("paperAutoRefreshState").textContent = "下次"+Math.round(delay/1000)+"s";
  paperAutoRefreshTimer = setTimeout(async ()=>{
    if (!paperAutoRefreshEnabled || activeRouteName()!=="paper") return;
    try { await loadPaperStatus(); } catch(_){}
    schedulePaperAutoRefresh(3000);
  }, delay);
}

async function loadPaperStatus() {
  const payload = await api("/api/paper/status?limit=1000");
  renderPaperStatus(payload.paper||{}, payload.markers||{});
  const paper = payload.paper || {};
  setPill("topbarPaper", "虚拟盘 " + (paper.status || "-"), paper.status === "running" ? "ok" : "neutral");
  paperLastRefreshAt = new Date().toLocaleTimeString("zh-CN",{timeZone:"Asia/Shanghai",hour12:false});
}

function collectPaperSettings() {
  return {
    instruments: $("paperInstruments").value,
    bar: "1m",
    mode: $("paperRunMode").value,
    poll_seconds: $("paperPollSeconds").value,
    okx_auto_submit: $("paperOkxAutoSubmit").checked,
    okx_auto_confirm: $("paperOkxAutoSubmit").checked ? "AUTO_OKX_SIMULATED_ONLY" : "",
    strategy_ids: Array.from(document.querySelectorAll("#paperStrategyPicker input:checked")).map(cb=>cb.dataset.paperStrategyId),
  };
}

$("paperStartBtn").addEventListener("click", async ()=>{
  try {
    const settings = collectPaperSettings();
    const r = await api("/api/paper/start", {method:"POST", body:JSON.stringify({...settings, confirm:"PAPER_TRADING_ONLY"})});
    if (r.ok) { renderPaperStatus(r.paper||{}, r.markers||{}); schedulePaperAutoRefresh(3000); }
  } catch(e) { alert("启动失败: "+e); }
});
$("paperStopBtn").addEventListener("click", async ()=>{
  try { await api("/api/paper/stop", {method:"POST", body:JSON.stringify({confirm:"STOP_PAPER_TRADING"})}); } catch(e) { alert("停止失败: "+e); }
});

// == Agent Page (GAP-027: 增强绩效展示) ==
function renderAgentPnlBars(agents) {
  const container = document.getElementById("agentPnlBars");
  if (!container) return;
  container.innerHTML = "";
  if (!agents.length) {
    container.innerHTML = '<div class="empty-state compact">暂无 Agent 盈亏贡献数据</div>';
    return;
  }

  // DOM 条形图比画布更容易审查，也能保持页面结构稳定。
  const pnlOf = (row) => Number(row.close_net_pnl ?? row.cumulative_pnl ?? row.capital_snapshot_pnl ?? 0);
  const maxAbsPnl = Math.max(...agents.map(a => Math.abs(pnlOf(a))), 1);
  agents.forEach(agent => {
    const pnl = pnlOf(agent);
    const width = Math.max(3, Math.min(100, Math.abs(pnl) / maxAbsPnl * 100));
    const row = document.createElement("div");
    row.className = "agent-bar-row";

    const name = document.createElement("span");
    name.className = "agent-bar-name";
    name.textContent = agent.display_name || agent.strategy_id || agent.id || "-";

    const track = document.createElement("div");
    track.className = "agent-bar-track";
    const fill = document.createElement("div");
    fill.className = "agent-bar-fill " + (pnl >= 0 ? "positive-bg" : "negative-bg");
    fill.style.width = width + "%";
    track.appendChild(fill);

    const value = document.createElement("strong");
    value.className = pnl >= 0 ? "positive" : "negative";
    value.textContent = formatMoney(pnl);

    row.append(name, track, value);
    container.appendChild(row);
  });
}

async function loadAgentPage() {
  const [capitalResult, backendResult] = await Promise.allSettled([
    api("/api/agent/capital"),
    api("/api/backend/account/portfolio?limit=20000&recent=50"),
  ]);
  const payload = capitalResult.status === "fulfilled" ? capitalResult.value : {};
  const backendPayload = backendResult.status === "fulfilled" ? backendResult.value : {};
  const backendAccount = backendPayload.backend_account || backendPayload;
  const backendOnline = backendResult.status === "fulfilled" && backendAccount && backendAccount.ok !== false;
  const data = payload.agent_capital || {};
  const attribution = backendOnline
    ? backendAccount
    : (payload.attribution || await api("/api/agent/attribution?limit=20000&recent=50"));
  const agents = data.agents || [];
  const attrRows = (attribution.by_strategy || []).filter(row => row.strategy_id && row.strategy_id !== "unknown");
  const unknownRows = (attribution.by_strategy || []).filter(row => row.strategy_id === "unknown");
  $("agentPageStatus").textContent = attrRows.length
    ? attrRows.length+"个策略有成交归因"
    : agents.length
    ? agents.length+"个活跃Agent，等待成交归因"
    : "等待C++ agent state数据";
  renderKeyValues($("agentCapitalSummary"), [
    ["总权益", formatMoney(data.total_equity)],
    ["活跃Agent", String(agents.length)],
    ["最近周期", String(data.last_cycle||"-")],
  ]);
  renderKeyValues($("agentAttributionSummary"), [
    ["平仓净盈亏", formatMoney(attribution.summary?.total_close_net_pnl)],
    ["已归因盈亏", formatMoney(attribution.summary?.attributed_close_net_pnl)],
    ["未知归因", formatMoney(attribution.summary?.unknown_close_net_pnl)],
    ["平仓成交", String(attribution.summary?.close_fill_count ?? 0)],
  ]);
  renderTable($("agentCapitalTable"), [
    {label:"Agent",key:"id"},
    {label:"分配资金",render:r=>formatMoney(r.allocated_capital)},
    {label:"初始资金",render:r=>formatMoney(r.initial_capital)},
    {label:"活跃周期",render:r=>String(r.cycles_active||0)},
    {label:"活跃",render:r=>r.active?"是":"否"},
  ], agents, "暂无Agent数据");
  renderTable($("agentPerformanceTable"), [
    {label:"策略",render:r=>r.display_name || r.strategy_id},
    {label:"Agent",render:r=>r.agent_id || r.strategy_id},
    {label:"交易单元",render:r=>r.trading_unit_name || r.trading_unit_id || "-"},
    {label:"平仓净盈亏",render:r=>formatMoney(r.close_net_pnl)},
    {label:"平仓数量",render:r=>formatNumber(r.closed_qty,6)},
    {label:"成交贡献",render:r=>formatNumber(r.fill_count,2)},
    {label:"胜率",render:r=>formatPercent(r.win_rate)},
    {label:"归因来源",render:r=>Object.keys(r.attribution_sources||{}).join(",") || "-"},
  ], attrRows.length ? attrRows : unknownRows, "暂无基于成交的策略归因数据");
  const backendSummary = backendAccount.summary || {};
  renderKeyValues($("agentBackendPnlSummary"), [
    ["C++读模型", backendOnline ? "在线" : "离线"],
    ["扫描订单事件", String(backendSummary.order_events_scanned ?? 0)],
    ["成交/平仓", String(backendSummary.fill_count ?? 0) + " / " + String(backendSummary.close_fill_count ?? 0)],
    ["平仓净盈亏", formatMoney(backendSummary.total_close_net_pnl)],
    ["未知归因", formatMoney(backendSummary.unknown_close_net_pnl)],
    ["报告最终权益", formatMoney(backendSummary.reported_final_equity)],
  ]);
  renderTable($("agentBackendPositionsTable"), [
    {label:"品种",key:"inst_id"},
    {label:"方向",key:"side"},
    {label:"净数量",render:r=>formatNumber(r.net_qty,6)},
    {label:"均价",render:r=>formatNumber(r.avg_entry_price,4)},
    {label:"标记价",render:r=>formatNumber(r.mark_price || r.last_fill_price,4)},
    {label:"未实现盈亏",render:r=>formatMoney(r.unrealized_pnl)},
    {label:"名义额",render:r=>formatMoney(r.mark_notional)},
    {label:"已实现净盈亏",render:r=>formatMoney(r.realized_net_pnl)},
    {label:"最近成交",render:r=>formatDateTimeText(r.last_fill_at)},
  ], backendAccount.positions || [], backendOnline ? "暂无C++持仓" : "C++账户读模型不可用");
  renderAgentPnlBars(attrRows.length ? attrRows : agents);
}

// == Market ==
async function loadMarketStream() {
  try {
    const p = await api("/api/market/okx/stream/status");
    const s = p.stream || {};
    $("marketStreamState").textContent = s.status||"-";
    const messages = s.messages||0;
    const events = s.events||0;
    const reconnects = s.reconnects||0;
    renderKeyValues($("marketStreamSummary"), [
      ["状态", s.status||"-"],
      ["品种数", String((s.instruments||[]).length)],
      ["频道", String((s.channels||[]).join(", "))],
      ["消息/事件", messages + " / " + events],
      ["重连次数", String(reconnects)],
      ["最近成交", formatDateTimeText(s.last_trade_at)],
      ["最近 Ticker", formatDateTimeText(s.last_ticker_at)],
    ]);

    // Render tickers from stream snapshot
    const tickers = p.stream?.tickers || {};
    const tickerKeys = Object.keys(tickers);
    if (tickerKeys.length > 0) {
      $("marketTickersState").textContent = tickerKeys.length + " 品种";
      const rows = [];
      for (const [inst, t] of Object.entries(tickers)) {
        const last = t.last || t.close || "";
        const bid = t.bidPx || t.bid || "";
        const ask = t.askPx || t.ask || "";
        const vol = t.vol24h || t.volCcy24h || "";
        rows.push({inst, last: String(last), bid: String(bid), ask: String(ask), vol: String(vol)});
      }
      renderTable($("marketTickersTable"), [
        {label:"品种", key:"inst"},
        {label:"最新价", key:"last"},
        {label:"买一", key:"bid"},
        {label:"卖一", key:"ask"},
        {label:"24h成交量", key:"vol"},
      ], rows, "暂无ticker数据");
    } else {
      $("marketTickersState").textContent = "等待数据...";
    }

    // Render recent trades summary
    const recentCounts = p.stream?.recent_trade_counts || {};
    const totalTrades = p.stream?.recent_trade_count || 0;
    if (totalTrades > 0) {
      $("marketTradesState").textContent = totalTrades + " 笔";
      const rows = [];
      for (const [inst, cnt] of Object.entries(recentCounts)) {
        rows.push({inst, cnt: String(cnt)});
      }
      renderTable($("marketTradesTable"), [
        {label:"品种", key:"inst"},
        {label:"成交笔数", key:"cnt"},
      ], rows, "暂无成交数据");
    } else {
      $("marketTradesState").textContent = "等待数据...";
    }
  } catch(e) { $("marketStreamState").textContent = String(e); }
}

// == Orders ==
async function loadOrdersCenter() {
  try {
    const [paperResult, backendResult] = await Promise.allSettled([
      api("/api/paper/status?limit=300"),
      api("/api/backend/orders/center?limit=180&consistency_limit=2000&issue_limit=80"),
    ]);
    if (paperResult.status === "rejected" && backendResult.status === "rejected") {
      throw paperResult.reason || backendResult.reason;
    }
    const p = paperResult.status === "fulfilled" ? paperResult.value : {};
    const backendPayload = backendResult.status === "fulfilled" ? backendResult.value : {};
    const backend = backendPayload.backend_orders || backendPayload.backend_order_center || backendPayload;
    const orderState = backend.order_state || {};
    const consistency = backend.consistency || {};
    const consistencySummary = consistency.summary || {};
    const issueRows = Array.isArray(consistency.issues) ? consistency.issues : [];
    const lifecycleRows = Array.isArray(orderState.orders) ? orderState.orders : [];
    const okx = (p.paper||{}).okx_auto_submit || {};
    const recent = (okx.recent||[]).slice(-60).reverse();
    const guard = okx.submission_guard || {};
    const terminalSync = okx.last_broker_terminal_sync || {};
    const staleBroker = okx.last_stale_broker_reconcile || {};
    const backendOk = backendResult.status === "fulfilled" && backend && backend.ok !== false;
    $("ordersCenterState").textContent = backendOk
      ? lifecycleRows.length+" 本地单 / "+recent.length+" OKX记录"
      : "C++巡检不可用，显示OKX记录";
    renderKeyValues($("ordersCenterSummary"), [
      ["C++订单核心", backendOk ? "在线" : (backend.error || "离线")],
      ["一致性决策", consistency.decision || "-"],
      ["问题数", String(consistencySummary.issues ?? 0)],
      ["提交门禁", guard.ready ? "通过" : "阻断"],
      ["门禁原因", guard.reason || "-"],
      ["活跃 OKX 单", String(guard.live_order_count || 0)],
      ["陈旧 OKX 单", String(guard.stale_order_count || 0)],
      ["终态回补", (terminalSync.synced || 0) + "/" + (terminalSync.requested || 0)],
      ["陈旧对账", (staleBroker.queried || 0) + " 查 / " + (staleBroker.cancel_succeeded || 0) + " 撤"],
      ["最近提交", formatDateTimeText(recent.length ? recent[0].at : "")],
    ]);
    $("ordersConsistencyState").textContent = backendOk
      ? (consistency.ok ? "通过" : ((consistencySummary.issues || 0) + " 个问题"))
      : "不可用";
    renderKeyValues($("ordersConsistencySummary"), [
      ["活跃本地单", String(consistencySummary.active_local_orders ?? 0)],
      ["陈旧活跃单", String(consistencySummary.stale_active_orders ?? 0)],
      ["缺OKX单号", String(consistencySummary.active_without_broker_identity ?? 0)],
      ["执行未成功", String(consistencySummary.active_without_recent_success_trace ?? 0)],
      ["本地终态/OKX活跃", String(consistencySummary.local_terminal_with_live_broker_audit ?? 0)],
      ["OKX终态/本地活跃", String(consistencySummary.broker_terminal_not_reflected_locally ?? 0)],
    ]);
    renderTable($("ordersConsistencyTable"), [
      {label:"级别",key:"severity"},
      {label:"问题",key:"code"},
      {label:"订单",render:r=>r.order_id || r.order_key || "-"},
      {label:"品种",key:"inst_id"},
      {label:"方向",key:"side"},
      {label:"本地状态",key:"state"},
      {label:"年龄",render:r=>formatAgeSeconds(r.age_seconds)},
      {label:"执行轨迹",render:r=>r.latest_trace_status || "-"},
      {label:"OKX状态",render:r=>r.latest_audit_state || r.broker_state || "-"},
      {label:"建议",render:r=>(r.recommended_action||"-").slice(0,80)},
      {label:"说明",render:r=>(r.message||"").slice(0,100)},
    ], issueRows, "C++一致性巡检未发现问题");
    $("ordersLifecycleState").textContent = lifecycleRows.length ? lifecycleRows.length+" 条" : "暂无";
    renderTable($("ordersLifecycleTable"), [
      {label:"更新时间",render:r=>formatDateTimeText(r.updated_at)},
      {label:"订单",render:r=>r.order_id || r.order_key || "-"},
      {label:"品种",key:"inst_id"},
      {label:"方向",key:"side"},
      {label:"状态",key:"state"},
      {label:"Broker",render:r=>r.broker_status || r.broker_state || "-"},
      {label:"OKX单号",render:r=>r.broker_order_id || r.broker_cl_ord_id || "-"},
      {label:"数量",render:r=>formatNumber(r.quantity,6)},
      {label:"成交",render:r=>formatNumber(r.filled_qty,6)},
      {label:"价格",render:r=>formatNumber(r.limit_price || r.avg_price,4)},
      {label:"平仓净盈亏",render:r=>formatMoney(r.close_net_pnl)},
      {label:"归因",render:r=>r.strategy_id || r.agent_id || r.parent_decision_id || "-"},
    ], lifecycleRows, "暂无C++订单生命周期数据");
    $("ordersOkxState").textContent = recent.length+" 条";
    renderTable($("ordersCenterTable"), [
      {label:"时间",render:r=>formatDateTimeText(r.at)},
      {label:"源委托",render:r=>r.source_order_id||"-"},
      {label:"OKX单号",render:r=>r.okx_order_id||r.order_id||"-"},
      {label:"方向",render:r=>r.side||"-"},
      {label:"数量",render:r=>r.quantity?formatNumber(r.quantity,6):"-"},
      {label:"价格",render:r=>r.price?formatNumber(r.price,4):"-"},
      {label:"手续费",render:r=>r.commission?("$"+formatNumber(r.commission,4)):"-"},
      {label:"状态",key:"status"},
      {label:"说明",render:r=>(r.message||"").slice(0,100)},
    ], recent, "暂无订单记录");
  } catch(e) {
    $("ordersCenterState").textContent = String(e);
    setText("ordersConsistencyState", "加载失败");
    setText("ordersLifecycleState", "加载失败");
    setText("ordersOkxState", "加载失败");
  }
}

// == Risk ==
async function loadRiskStatus() {
  try {
    const p = await api("/api/status");
    const risk = p.risk || {};
    const state = risk.state || {};
    const budget = risk.runtime_budget || {};
    const killActive = state.kill_switch;
    $("riskCenterState").textContent = killActive ? "⛔ Kill Switch" : (risk.status||"正常");
    renderKeyValues($("riskCenterSummary"), [
      ["Kill Switch", killActive?"激活":"未激活"],
      ["风控动作", budget.action||"-"],
      ["风控原因", budget.reason||"-"],
      ["状态", risk.status||"-"],
    ]);
    renderTable($("riskCenterChecks"), [
      {label:"检查项",key:"name"},{label:"状态",render:r=>r.ok?"通过":"阻断"},{label:"级别",key:"severity"},{label:"说明",key:"message"},
    ], risk.checks||[], "暂无风控检查");
  } catch(e) { $("riskCenterState").textContent = String(e); }
}

// == Events ==
async function loadEvents() {
  try {
    const p = await api("/api/events/journal");
    const events = p.events || [];
    $("eventCount").textContent = events.length+" 条";
    const list = $("eventsList"); list.innerHTML = "";
    events.slice(0,60).forEach(e => {
      const div = document.createElement("div");
      let cls = "event-item";
      if (/error|fail|reject/i.test(e.event||"")) cls += " error";
      else if (/warn|halt|violation/i.test(e.event||"")) cls += " warn";
      else if (/fill|trade|execut/i.test(e.event||"")) cls += " fill";
      div.className = cls;
      div.innerHTML = '<span>'+formatDateTimeText(e.ts)+'</span><strong>'+esc(e.event)+'</strong><small>'+esc(e.message)+'</small>';
      list.appendChild(div);
    });
  } catch(e) { $("eventCount").textContent = String(e); }
}

// == Backend Core ==
function renderBackendCore(payload) {
  payload = payload || {};
  const data = payload.status || {};
  $("backendCoreState").textContent = data.online ? "在线": "离线";
  renderKeyValues($("backendCoreSummary"), [
    ["运行状态", data.online?"在线":"离线"],
    ["C++引擎", payload.binary_found?"已编译":"未找到"],
    ["最近质量报告", formatDateTimeText(payload.last_quality_at)],
  ]);
  // 填充详情表
  if (data.migration) {
    renderTable($("backendCoreDetails"), [
      {label:"字段",key:"key"},{label:"值",key:"value"},
    ], [{key:"迁移",value:data.migration},{key:"可用",value:data.available?"是":"否"},{key:"错误",value:data.error||"-"}], "");
  }
}

// == Equity Curve Chart (GAP-025) ==
function pointEquity(point) {
  const value = Number(point?.equity ?? point?.e ?? 0);
  return Number.isFinite(value) ? value : 0;
}

function normalizeEquitySeries(curve, name, color, dash) {
  const points = (Array.isArray(curve) ? curve : []).slice(-300);
  return {name, color, dash: dash || [], points};
}

function renderChartLegend(id, series) {
  const el = $(id);
  if (!el) return;
  const rows = (series || []).filter(s => s.points && s.points.length >= 2);
  el.innerHTML = rows.map(s => (
    '<span><i style="background:'+esc(s.color)+'"></i>'+esc(s.name)+'</span>'
  )).join("");
}

function renderEquitySummary(containerId, account) {
  const container = $(containerId);
  if (!container) return;
  const summary = account?.summary || {};
  renderKeyValues(container, [
    ["来源", summary.primary_source || "-"],
    ["会话", summary.resolved_session || summary.latest_session || "-"],
    ["报告点数", String(summary.report_points ?? 0)],
    ["C++回放点数", String(summary.realized_points ?? 0)],
    ["报告最终权益", formatMoney(summary.report_final_equity)],
    ["C++盯市权益", formatMoney(summary.cpp_mark_to_market_equity)],
    ["C++已实现权益", formatMoney(summary.cpp_realized_final_equity)],
    ["平仓净盈亏", formatMoney(summary.cpp_cumulative_realized_net_pnl)],
    ["未实现盈亏", formatMoney(summary.cpp_open_unrealized_pnl)],
    ["累计手续费", formatMoney(summary.cpp_cumulative_commission)],
  ]);
}

function renderEquityCurve(curve, options) {
  options = options || {};
  const canvas = $(options.canvasId || "equityChart");
  const label = $(options.labelId || "chartState");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const fallback = normalizeEquitySeries(curve, "净值", "#138a72");
  const series = (options.series && options.series.length ? options.series : [fallback])
    .map(s => normalizeEquitySeries(s.points, s.name, s.color || "#138a72", s.dash))
    .filter(s => s.points.length >= 2);
  renderChartLegend(options.legendId || "equityLegend", series);
  if (!series.length) {
    if (label) label.textContent = "暂无数据";
    return;
  }

  const values = series.flatMap(s => s.points.map(pointEquity));
  const min = Math.min(...values), max = Math.max(...values);
  const range = max - min || 1;
  const pad = 34;
  const chartW = w - 2 * pad;
  const chartH = h - 2 * pad;
  const totalPoints = Math.max(...series.map(s => s.points.length));
  if (label) label.textContent = totalPoints + " 个数据点";

  ctx.strokeStyle = "#dde3ea";
  ctx.lineWidth = 0.5;
  ctx.setLineDash([]);
  for (let i = 0; i <= 4; i++) {
    const y = pad + chartH * i / 4;
    ctx.beginPath();
    ctx.moveTo(pad, y);
    ctx.lineTo(w - pad, y);
    ctx.stroke();
  }

  series.forEach(s => {
    ctx.strokeStyle = s.color;
    ctx.lineWidth = 2;
    ctx.setLineDash(s.dash || []);
    ctx.beginPath();
    s.points.forEach((p, i) => {
      const x = pad + chartW * i / Math.max(1, s.points.length - 1);
      const y = pad + chartH * (1 - ((pointEquity(p) - min) / range));
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
  });
  ctx.setLineDash([]);

  ctx.fillStyle = "#687385";
  ctx.font = "10px sans-serif";
  ctx.fillText(formatNumber(max, 0), pad, pad - 7);
  ctx.fillText(formatNumber(min, 0), pad, h - pad + 13);
}

function renderBackendEquity(account, target) {
  if (!account || account.ok === false) {
    setText(target.labelId, "C++数据不可用");
    return;
  }
  const report = account.report_equity_curve || [];
  const realized = account.realized_equity_curve || [];
  const marked = account.cpp_mark_to_market_curve || [];
  const primary = account.equity_curve || [];
  const series = [];
  if (report.length >= 2) {
    series.push({name:"报告净值(含浮盈亏)", points:report, color:"#138a72"});
  }
  if (marked.length >= 2) {
    series.push({name:"C++盯市净值", points:marked, color:"#2f6fed"});
  }
  if (realized.length >= 2) {
    series.push({name:"C++成交回放(仅已实现)", points:realized, color:"#687385", dash:[6, 4]});
  }
  if (!series.length && primary.length >= 2) {
    series.push({name:"净值", points:primary, color:"#138a72"});
  }
  renderEquitySummary(target.summaryId, account);
  renderEquityCurve(primary, {
    canvasId: target.canvasId,
    labelId: target.labelId,
    legendId: target.legendId,
    series,
  });
}

async function loadBackendEquityWidgets(targets) {
  const payload = await api("/api/backend/account/equity?limit=500&order_limit=200000");
  const account = payload.backend_account || payload;
  if (targets.dashboard) {
    renderBackendEquity(account, {
      canvasId: "equityChart",
      labelId: "chartState",
      summaryId: "equitySummary",
      legendId: "equityLegend",
    });
  }
  if (targets.risk) {
    renderBackendEquity(account, {
      canvasId: "riskEquityChart",
      labelId: "riskEquityState",
      summaryId: "riskEquitySummary",
      legendId: "riskEquityLegend",
    });
  }
}

// == OKX Config ==
async function loadOkxConfig() {
  try {
    const s = await api("/api/status");
    const okx = s.okx || {};
    $("okxConfigState").textContent = okx.configured ? "已配置" : "未配置";
    renderKeyValues($("okxConfigSummary"), [
      ["状态", okx.state || "-"],
      ["API Key", okx.key_configured ? "已配置" : "未配置"],
      ["Secret", okx.secret_configured ? "已配置" : "未配置"],
      ["Passphrase", okx.passphrase_configured ? "已配置" : "未配置"],
      ["模式", okx.simulated ? "模拟盘" : "实盘"],
      ["交易", okx.trading_enabled ? "已启用" : "未启用"],
    ]);
    // Fill form from current config
    const cfg = s.config || {};
    $("okxBaseUrl").value = cfg["okx.base_url"] || "https://www.okx.com";
    $("okxSimulated").checked = cfg["okx.simulated"] !== "false";
  } catch(e) { $("okxConfigState").textContent = String(e); }
}
$("saveOkxConfig").addEventListener("click", async () => {
  try {
    const body = {
      "okx_api_key": $("okxApiKey").value.trim(),
      "okx_secret_key": $("okxSecretKey").value.trim(),
      "okx_passphrase": $("okxPassphrase").value.trim(),
    };
    const r = await api("/api/okx/apikey", {method:"POST", body:JSON.stringify(body)});
    // Also save base URL and simulated flag to main config
    try {
      await api("/api/config", {method:"POST", body:JSON.stringify({config:{
        "okx.base_url": $("okxBaseUrl").value.trim(),
        "okx.simulated": $("okxSimulated").checked ? "true" : "false",
      }})});
    } catch(_) {}
    if (r.ok) { alert("OKX 配置已保存，请重启平台生效。"); loadOkxConfig(); }
    else alert("保存失败: " + (r.error || "未知错误"));
  } catch(e) { alert("保存失败: " + e); }
});

// == Main Load ==
async function loadStatus() {
  let status = {};
  try {
    status = await api("/api/status");
    $("providerState").textContent = "已连接";
    $("providerState").className = "ok";
    updateStatusBar("已连接");
    const dot = $("statusDot"); if (dot) dot.classList.add("online");
    $("topbarClock").textContent = new Date().toLocaleTimeString("zh-CN",{timeZone:"Asia/Shanghai",hour12:false});
  } catch(e) {
    console.error("loadStatus failed:", e);
    $("providerState").textContent = "服务器未响应";
    $("providerState").className = "bad";
    updateStatusBar("服务器未响应");
    const dot = $("statusDot"); if (dot) dot.classList.add("offline");
    renderRoute(routeFromPath());
    connectEventStream();
    return;  // 服务器不通，跳过后续渲染
  }

  // 每个渲染段独立 try/catch，一个失败不影响其他
  try { renderMetrics(status.summary || {}); } catch(e) { console.error("renderMetrics:", e); }
  try { renderBrokerOkx(status.broker || {}, status.okx || {}); } catch(e) { console.error("renderBrokerOkx:", e); }
  try { renderDataProfile(status.data_profile || {}); } catch(e) { console.error("renderDataProfile:", e); }
  try { renderConfig(status.config || {}); } catch(e) { console.error("renderConfig:", e); }
  try { renderStrategies(status.strategies || []); } catch(e) { console.error("renderStrategies:", e); }
  try { renderBackendCore(status.backend_core || {}); } catch(e) { console.error("renderBackendCore:", e); }
  try { renderOpsRibbon(status); updateTopbarStatus(status); } catch(e) { console.error("renderOpsRibbon:", e); }

  try {
    const okxStat = (status.market_quality||{}).okx || {};
    $("providerState").textContent = okxStat.simulated ? "OKX 模拟盘" : (okxStat.configured ? "OKX 已连接" : "仅本地模式");
  } catch(e) {}

  try {
    const mq = status.market_quality || {};
    renderRegime(mq.regime || {}, mq.regime_by_instrument || {});
  } catch(e) { console.error("renderRegime:", e); }

  try { renderEquityCurve(status.equity_curve || []); } catch(e) { console.error("renderEquityCurve:", e); }

  try {
    const paper = status.paper || {};
    renderPaperStatus(paper, status.paper_markers || {});
    renderPositionOverview(paper);
  } catch(e) { console.error("renderPaper:", e); }
}

loadStatus().then(() => { renderRoute(routeFromPath()); connectEventStream(); }).catch(e => {
  console.error("loadStatus fatal:", e);
  renderRoute(routeFromPath());
  connectEventStream();
});
