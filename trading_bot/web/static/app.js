/* Educational trading lab — vanilla JS. No build step; read top-to-bottom.
   Two jobs: (1) drive the interactive backtest form/charts, (2) render the math. */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const fmtPct = (x) => (x == null || !isFinite(x)) ? "—" : (x * 100).toFixed(1) + "%";
const fmtNum = (x, d = 2) => (x == null || !isFinite(x)) ? "—" : Number(x).toFixed(d);
const fmtMoney = (x) => (x == null || !isFinite(x)) ? "—" : "$" + Math.round(x).toLocaleString();

// --------------------------------------------------------------- KaTeX rendering
function renderMath(root = document.body) {
  if (window.renderMathInElement) {
    renderMathInElement(root, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "\\(", right: "\\)", display: false },
      ],
      throwOnError: false,
    });
  }
}

// --------------------------------------------------------------- canvas chart
function setupCanvas(canvas, cssHeight) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth || canvas.parentElement.clientWidth;
  canvas.width = w * dpr;
  canvas.height = cssHeight * dpr;
  canvas.style.height = cssHeight + "px";
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  return { ctx, w, h: cssHeight };
}

/* Draw a multi-series line chart on an index-based x-axis.
   opts: { series:[{data, color, width, dash, fill}], markers, thresholds, dates, valueFmt } */
function drawChart(canvas, opts) {
  const PAD = { l: 56, r: 14, t: 12, b: 22 };
  const { ctx, w, h } = setupCanvas(canvas, opts.height || 220);
  ctx.clearRect(0, 0, w, h);
  const plotW = w - PAD.l - PAD.r, plotH = h - PAD.t - PAD.b;

  const allVals = [];
  opts.series.forEach((s) => s.data.forEach((v) => { if (v != null && isFinite(v)) allVals.push(v); }));
  (opts.thresholds || []).forEach((t) => allVals.push(t.y));
  if (!allVals.length) return;
  let lo = Math.min(...allVals), hi = Math.max(...allVals);
  if (lo === hi) { lo -= 1; hi += 1; }
  const pad = (hi - lo) * 0.08; lo -= pad; hi += pad;
  const n = Math.max(...opts.series.map((s) => s.data.length));

  const X = (i) => PAD.l + (n <= 1 ? 0 : (i / (n - 1)) * plotW);
  const Y = (v) => PAD.t + plotH - ((v - lo) / (hi - lo)) * plotH;

  // grid + y labels
  ctx.font = "11px ui-monospace, monospace";
  ctx.textBaseline = "middle";
  for (let g = 0; g <= 4; g++) {
    const v = lo + (g / 4) * (hi - lo);
    const y = Y(v);
    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.beginPath(); ctx.moveTo(PAD.l, y); ctx.lineTo(w - PAD.r, y); ctx.stroke();
    ctx.fillStyle = "#6b7799"; ctx.textAlign = "right";
    ctx.fillText(opts.valueFmt ? opts.valueFmt(v) : v.toFixed(0), PAD.l - 8, y);
  }
  // x date labels
  if (opts.dates && opts.dates.length) {
    ctx.textAlign = "center"; ctx.fillStyle = "#6b7799";
    for (let k = 0; k <= 4; k++) {
      const i = Math.round((k / 4) * (n - 1));
      const d = opts.dates[i]; if (!d) continue;
      ctx.fillText(d.slice(0, 7), X(i), h - 8);
    }
  }
  // threshold lines
  (opts.thresholds || []).forEach((t) => {
    ctx.strokeStyle = t.color || "rgba(154,166,196,0.5)";
    ctx.setLineDash([4, 4]); ctx.beginPath();
    ctx.moveTo(PAD.l, Y(t.y)); ctx.lineTo(w - PAD.r, Y(t.y)); ctx.stroke(); ctx.setLineDash([]);
    if (t.label) { ctx.fillStyle = "#6b7799"; ctx.textAlign = "left"; ctx.fillText(t.label, PAD.l + 4, Y(t.y) - 7); }
  });
  // series
  opts.series.forEach((s) => {
    ctx.lineWidth = s.width || 1.6; ctx.strokeStyle = s.color;
    if (s.dash) ctx.setLineDash(s.dash); else ctx.setLineDash([]);
    ctx.beginPath();
    let started = false;
    s.data.forEach((v, i) => {
      if (v == null || !isFinite(v)) { started = false; return; }
      const x = X(i), y = Y(v);
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    });
    ctx.stroke();
    if (s.fill) {
      ctx.lineTo(X(s.data.length - 1), Y(lo)); ctx.lineTo(X(0), Y(lo)); ctx.closePath();
      ctx.fillStyle = s.fill; ctx.fill();
    }
    ctx.setLineDash([]);
  });
  // markers (buy/short/exit)
  (opts.markers || []).forEach((m) => {
    const base = opts.series[0].data;
    const v = base[m.i]; if (v == null) return;
    const x = X(m.i), y = Y(v);
    const color = m.type === "buy" ? "#38e1b0" : m.type === "short" ? "#ff6b81" : "#9aa6c4";
    ctx.fillStyle = color; ctx.beginPath();
    const up = m.type === "buy";
    ctx.moveTo(x, y + (up ? 9 : -9)); ctx.lineTo(x - 5, y + (up ? 18 : -18)); ctx.lineTo(x + 5, y + (up ? 18 : -18));
    ctx.closePath(); ctx.fill();
  });
}

function legend(el, items) {
  el.innerHTML = items.map((i) => `<span class="it"><span class="sw" style="background:${i.color}"></span>${i.name}</span>`).join("");
}

// --------------------------------------------------------------- form + run
let STRATEGIES = [];

function buildForm(meta) {
  const symWrap = $("#symbols"); symWrap.innerHTML = "";
  const labels = meta.num_symbols === 2 ? ["Stock A", "Stock B"] : ["Ticker"];
  for (let i = 0; i < meta.num_symbols; i++) {
    const d = document.createElement("div"); d.className = "field";
    d.innerHTML = `<label>${labels[i]}</label><input class="sym" value="${meta.default_symbols[i] || ""}" />`;
    symWrap.appendChild(d);
  }
  const pWrap = $("#params"); pWrap.innerHTML = "";
  meta.params.forEach((p) => {
    const d = document.createElement("div");
    if (p.kind === "bool") {
      d.className = "field checkbox";
      d.innerHTML = `<input type="checkbox" id="p_${p.name}" ${p.default ? "checked" : ""}/><label for="p_${p.name}" title="${p.help}">${p.label}</label>`;
    } else {
      d.className = "field";
      const step = p.kind === "float" ? "0.1" : "1";
      d.innerHTML = `<label title="${p.help}">${p.label}</label><input id="p_${p.name}" type="number" step="${step}" value="${p.default}"/>`;
    }
    pWrap.appendChild(d);
  });
  $("#strategy-blurb").textContent = meta.blurb;
  const kx = $("#strategy-math"); kx.innerHTML = "\\(" + meta.signal_katex + "\\)"; renderMath(kx);
}

function collectParams(meta) {
  const params = {};
  meta.params.forEach((p) => {
    const el = $("#p_" + p.name);
    params[p.name] = p.kind === "bool" ? el.checked : Number(el.value);
  });
  return params;
}

async function loadStrategies() {
  const r = await fetch("/api/strategies");
  STRATEGIES = (await r.json()).strategies;
  const sel = $("#strategy");
  sel.innerHTML = STRATEGIES.map((s) => `<option value="${s.key}">${s.name}</option>`).join("");
  sel.onchange = () => buildForm(STRATEGIES.find((s) => s.key === sel.value));
  buildForm(STRATEGIES[0]);
}

async function runBacktest() {
  const meta = STRATEGIES.find((s) => s.key === $("#strategy").value);
  const symbols = $$(".sym").map((i) => i.value.trim().toUpperCase()).filter(Boolean);
  const spinner = $("#spinner"), errEl = $("#err");
  errEl.textContent = ""; spinner.classList.add("on");
  $("#run").disabled = true;
  try {
    const body = {
      strategy: meta.key, symbols,
      start: $("#start").value || null, end: $("#end").value || null,
      source: "yahoo", timeframe: "1Day",
      starting_cash: Number($("#cash").value) || 100000,
      commission_pct: Number($("#cost").value) / 10000,
      slippage_pct: Number($("#cost").value) / 10000,
      params: collectParams(meta),
    };
    const r = await fetch("/api/backtest", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail || r.statusText); }
    renderResults(await r.json());
  } catch (e) {
    errEl.textContent = "⚠ " + e.message + "  (free Yahoo data can rate-limit; try again or change tickers/dates)";
  } finally {
    spinner.classList.remove("on"); $("#run").disabled = false;
  }
}

function metricCard(k, v, cls = "") { return `<div class="metric"><div class="k">${k}</div><div class="v ${cls}">${v}</div></div>`; }

function renderResults(d) {
  $("#results").style.display = "block";
  const m = d.metrics, t = m.trades || {};
  const cls = (x) => (x > 0 ? "good" : x < 0 ? "bad" : "");
  $("#metrics").innerHTML =
    metricCard("Total return", fmtPct(m.total_return), cls(m.total_return)) +
    metricCard("CAGR", fmtPct(m.cagr), cls(m.cagr)) +
    metricCard("Sharpe (ann.)", fmtNum(m.sharpe_ratio), cls(m.sharpe_ratio)) +
    metricCard("Sortino (ann.)", fmtNum(m.sortino_ratio), cls(m.sortino_ratio)) +
    metricCard("Max drawdown", fmtPct(m.max_drawdown), "bad") +
    metricCard("Volatility (ann.)", fmtPct(m.annualized_volatility)) +
    metricCard("Trades", t.num_trades ?? "—") +
    metricCard("Win rate", fmtPct(t.win_rate)) +
    metricCard("Profit factor", fmtNum(t.profit_factor)) +
    metricCard("Expectancy / trade", fmtMoney(t.expectancy));

  // ADF note for pairs
  const adf = d.extra && d.extra.adf_pvalue != null;
  $("#adf-note").innerHTML = adf
    ? `<div class="callout callout-key"><div class="h">Cointegration check (ADF)</div><p>ADF statistic <b>${fmtNum(d.extra.adf_stat)}</b>, p-value <b>${fmtNum(d.extra.adf_pvalue, 3)}</b>. A small p-value (≲ 0.05) is evidence the spread is stationary — the precondition for pairs trading to make sense.</p></div>`
    : "";

  // Price + overlays + markers
  const priceSeries = [{ data: d.prices[d.primary], color: "#5b9dff", width: 1.8, name: d.primary }];
  const colors = ["#38e1b0", "#ffb454", "#ff6b81", "#b07bff"];
  let ci = 0;
  for (const [name, arr] of Object.entries(d.overlays || {})) {
    priceSeries.push({ data: arr, color: colors[ci % colors.length], width: 1.3, name });
    ci++;
  }
  // for pairs (no overlays) show the second leg too
  if (d.symbols.length === 2) priceSeries.push({ data: d.prices[d.symbols[1]], color: "#ffb454", width: 1.4, name: d.symbols[1] });
  drawChart($("#chart-price"), { series: priceSeries, markers: d.markers, dates: d.dates, height: 250, valueFmt: (v) => v.toFixed(0) });
  legend($("#legend-price"), priceSeries.map((s) => ({ name: s.name, color: s.color }))
    .concat([{ name: "▲ buy", color: "#38e1b0" }, { name: "▼ short", color: "#ff6b81" }, { name: "exit", color: "#9aa6c4" }]));

  // Equity vs buy & hold
  const eq = [
    { data: d.equity, color: "#38e1b0", width: 2, name: "Strategy" },
    { data: d.buy_hold_equity, color: "#6b7799", width: 1.5, dash: [5, 4], name: "Buy & hold " + d.primary },
  ];
  drawChart($("#chart-equity"), { series: eq, dates: d.dates, height: 230, valueFmt: (v) => "$" + (v / 1000).toFixed(0) + "k" });
  legend($("#legend-equity"), eq.map((s) => ({ name: s.name, color: s.color })));

  // Drawdown
  drawChart($("#chart-dd"), {
    series: [{ data: d.drawdown, color: "#ff6b81", width: 1.4, fill: "rgba(255,107,129,0.14)" }],
    dates: d.dates, height: 150, valueFmt: (v) => (v * 100).toFixed(0) + "%",
  });

  // Signal panel (RSI / z-score)
  const sp = d.signal_panel;
  const spCard = $("#chart-signal-card");
  if (sp) {
    spCard.style.display = "block";
    $("#signal-title").textContent = sp.name;
    drawChart($("#chart-signal"), {
      series: [{ data: sp.values, color: "#b07bff", width: 1.6 }],
      thresholds: sp.thresholds.map((th) => ({ y: th.y, label: th.label })),
      dates: d.dates, height: 170, valueFmt: (v) => v.toFixed(1),
    });
  } else { spCard.style.display = "none"; }

  $("#results").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// --------------------------------------------------------------- init
window.addEventListener("DOMContentLoaded", async () => {
  renderMath();
  // sensible default dates: ~3 years
  const today = new Date(), past = new Date(); past.setFullYear(today.getFullYear() - 3);
  $("#end").value = today.toISOString().slice(0, 10);
  $("#start").value = past.toISOString().slice(0, 10);
  await loadStrategies();
  $("#run").onclick = runBacktest;
  $$(".scroll-run").forEach((b) => b.onclick = () => $("#lab").scrollIntoView({ behavior: "smooth" }));
});
