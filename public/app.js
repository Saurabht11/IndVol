const state = {
  symbol: "NIFTY",
  date: null,
  optionType: "ALL",
  ivCap: 1.2,
  moneyBand: 0.28,
  activeTab: "raw",
  minDte: 5,
  minVolume: 100,
  minOi: 25000,
  ivFloor: 0.1,
  ivCeiling: 0.45,
  smoothPasses: 2,
  dates: [],
  history: [],
  rawPoints: [],
  points: [],
  mode: "3d",
  playTimer: null,
};

const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8010" : "";

const el = {
  status: document.querySelector("#status"),
  symbol: document.querySelector("#symbol"),
  date: document.querySelector("#date"),
  optionType: document.querySelector("#optionType"),
  ivCap: document.querySelector("#ivCap"),
  ivCapLabel: document.querySelector("#ivCapLabel"),
  moneyBand: document.querySelector("#moneyBand"),
  moneyBandLabel: document.querySelector("#moneyBandLabel"),
  refresh: document.querySelector("#refresh"),
  tabRaw: document.querySelector("#tabRaw"),
  tabTrader: document.querySelector("#tabTrader"),
  traderControls: document.querySelector("#traderControls"),
  minDte: document.querySelector("#minDte"),
  minDteLabel: document.querySelector("#minDteLabel"),
  minVolume: document.querySelector("#minVolume"),
  minVolumeLabel: document.querySelector("#minVolumeLabel"),
  minOi: document.querySelector("#minOi"),
  minOiLabel: document.querySelector("#minOiLabel"),
  ivBand: document.querySelector("#ivBand"),
  ivBandLabel: document.querySelector("#ivBandLabel"),
  smoothPasses: document.querySelector("#smoothPasses"),
  smoothPassesLabel: document.querySelector("#smoothPassesLabel"),
  prevDate: document.querySelector("#prevDate"),
  nextDate: document.querySelector("#nextDate"),
  play: document.querySelector("#play"),
  dateSlider: document.querySelector("#dateSlider"),
  dateReadout: document.querySelector("#dateReadout"),
  coverageReadout: document.querySelector("#coverageReadout"),
  mode3d: document.querySelector("#mode3d"),
  modeHeatmap: document.querySelector("#modeHeatmap"),
  surfaceChart: document.querySelector("#surfaceChart"),
  heatmapCanvas: document.querySelector("#heatmapCanvas"),
  smileCanvas: document.querySelector("#smileCanvas"),
  termCanvas: document.querySelector("#termCanvas"),
  historyCanvas: document.querySelector("#historyCanvas"),
  expiry: document.querySelector("#expiry"),
  pointCount: document.querySelector("#pointCount"),
  spot: document.querySelector("#spot"),
  atmIv: document.querySelector("#atmIv"),
  termSlope: document.querySelector("#termSlope"),
  ivRvSpread: document.querySelector("#ivRvSpread"),
  regimeNeedle: document.querySelector("#regimeNeedle"),
  regimeLabel: document.querySelector("#regimeLabel"),
  historyMeta: document.querySelector("#historyMeta"),
  table: document.querySelector("#surfaceTable"),
  tableMeta: document.querySelector("#tableMeta"),
  surfaceTitle: document.querySelector("#surfaceTitle"),
  surfaceSubtitle: document.querySelector("#surfaceSubtitle"),
  surfaceQuality: document.querySelector("#surfaceQuality"),
};

function fmtPct(value) {
  if (!Number.isFinite(value)) return "-";
  return `${(value * 100).toFixed(1)}%`;
}

function fmtNum(value, digits = 2) {
  if (!Number.isFinite(value)) return "-";
  return value.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

async function getJson(url) {
  const primary = `${API_BASE}${url}`;
  try {
    const response = await fetch(primary);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.json();
  } catch (error) {
    const fallback = staticDataUrl(url);
    if (!fallback) throw error;
    const response = await fetch(fallback);
    if (!response.ok) throw error;
    const payload = await response.json();
    return filterStaticPayload(url, payload);
  }
}

function staticDataUrl(url) {
  const parsed = new URL(url, window.location.href);
  const symbol = (parsed.searchParams.get("symbol") || state.symbol).toUpperCase();
  if (parsed.pathname === "/api/surface-dates") return `data/${symbol}/dates.json`;
  if (parsed.pathname === "/api/surface-history") return `data/${symbol}/history.json`;
  if (parsed.pathname === "/api/surface") {
    const day = parsed.searchParams.get("date") || state.date;
    return day ? `data/${symbol}/${day}.json` : null;
  }
  return null;
}

function filterStaticPayload(url, payload) {
  const parsed = new URL(url, window.location.href);
  const optionType = (parsed.searchParams.get("option_type") || "ALL").toUpperCase();
  if (parsed.pathname === "/api/surface" && optionType !== "ALL") {
    return { ...payload, points: payload.points.filter((point) => point.option_type === optionType) };
  }
  return payload;
}

async function loadDates() {
  el.status.textContent = "Loading dates";
  const payload = await getJson(`/api/surface-dates?symbol=${state.symbol}`);
  state.dates = payload.dates;
  el.date.innerHTML = "";
  state.dates.forEach((row) => {
    const option = document.createElement("option");
    option.value = row.date;
    option.textContent = `${row.date} (${row.points.toLocaleString("en-IN")})`;
    el.date.appendChild(option);
  });
  const latest = state.dates[state.dates.length - 1];
  state.date = state.date && state.dates.some((row) => row.date === state.date) ? state.date : latest?.date;
  syncDateControls();
}

async function loadHistory() {
  el.status.textContent = "Loading history";
  const params = new URLSearchParams({ symbol: state.symbol, option_type: state.optionType });
  const payload = await getJson(`/api/surface-history?${params}`);
  state.history = payload.history;
  renderHistory();
}

async function loadSurface() {
  el.status.textContent = "Loading surface";
  const params = new URLSearchParams({
    symbol: state.symbol,
    date: state.date,
    option_type: state.optionType,
  });
  const payload = await getJson(`/api/surface?${params}`);
  state.rawPoints = payload.points;
  state.points = currentDisplayPoints();
  renderAll();
  el.status.textContent = "Ready";
}

function currentDisplayPoints() {
  const base = state.rawPoints.filter(
    (point) =>
      point.implied_vol > 0 &&
      point.implied_vol <= state.ivCap &&
      point.moneyness >= 1 - state.moneyBand &&
      point.moneyness <= 1 + state.moneyBand,
  );
  if (state.activeTab === "raw") return base;
  return base.filter(
    (point) =>
      point.days_to_expiry >= state.minDte &&
      point.implied_vol >= state.ivFloor &&
      point.implied_vol <= state.ivCeiling &&
      Number(point.volume || 0) >= state.minVolume &&
      Number(point.open_interest || 0) >= state.minOi,
  );
}

function syncDateControls() {
  const idx = currentDateIndex();
  el.date.value = state.date || "";
  el.dateSlider.max = Math.max(0, state.dates.length - 1);
  el.dateSlider.value = Math.max(0, idx);
  el.dateReadout.textContent = state.date || "-";
  const row = state.dates[idx];
  el.coverageReadout.textContent = row ? `${row.points.toLocaleString("en-IN")} raw IV points` : "-";
}

function currentDateIndex() {
  return Math.max(0, state.dates.findIndex((row) => row.date === state.date));
}

function setDateByIndex(idx) {
  const bounded = Math.max(0, Math.min(state.dates.length - 1, idx));
  state.date = state.dates[bounded]?.date || state.date;
  syncDateControls();
  return loadSurface();
}

function groupByExpiry(points) {
  const groups = new Map();
  points.forEach((point) => {
    if (!groups.has(point.expiry)) groups.set(point.expiry, []);
    groups.get(point.expiry).push(point);
  });
  return groups;
}

function median(values) {
  const clean = values.filter(Number.isFinite);
  if (!clean.length) return NaN;
  const sorted = [...clean].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function percentileRank(rows, value, key) {
  const values = rows.map((row) => row[key]).filter(Number.isFinite).sort((a, b) => a - b);
  if (!values.length || !Number.isFinite(value)) return NaN;
  const below = values.filter((item) => item <= value).length;
  return below / values.length;
}

function nearestAtm(points) {
  if (!points.length) return null;
  return [...points].sort((a, b) => Math.abs(a.moneyness - 1) - Math.abs(b.moneyness - 1))[0];
}

function currentHistoryRow() {
  return state.history.find((row) => row.date === state.date) || null;
}

function renderMetrics() {
  const points = state.points;
  const atm = nearestAtm(points);
  const history = currentHistoryRow();
  const expiries = [...groupByExpiry(points).entries()]
    .map(([expiry, rows]) => ({ expiry, dte: median(rows.map((row) => row.days_to_expiry)), atm: nearestAtm(rows) }))
    .filter((row) => row.atm)
    .sort((a, b) => a.dte - b.dte);
  const slope = expiries.length >= 2 ? expiries[expiries.length - 1].atm.implied_vol - expiries[0].atm.implied_vol : history?.term_slope;
  const rvSpread = history?.realized_vol_30d && atm ? atm.implied_vol - history.realized_vol_30d : NaN;
  const rank = percentileRank(state.history, history?.atm_iv, "atm_iv");

  el.pointCount.textContent = points.length.toLocaleString("en-IN");
  el.spot.textContent = atm ? fmtNum(atm.spot, 2) : "-";
  el.atmIv.textContent = atm ? fmtPct(atm.implied_vol) : "-";
  el.termSlope.textContent = Number.isFinite(slope) ? `${slope >= 0 ? "+" : ""}${fmtPct(slope)}` : "-";
  el.ivRvSpread.textContent = Number.isFinite(rvSpread) ? `${rvSpread >= 0 ? "+" : ""}${fmtPct(rvSpread)}` : "-";
  el.regimeNeedle.style.left = `${Math.max(0, Math.min(1, rank || 0)) * 100}%`;
  el.regimeLabel.textContent = Number.isFinite(rank) ? `${Math.round(rank * 100)}th pct` : "-";
}

function buildSurfaceGrid(points) {
  const xBuckets = [...new Set(points.map((point) => Number(point.moneyness.toFixed(3))))].sort((a, b) => a - b);
  const yBuckets = [...new Set(points.map((point) => point.days_to_expiry))].sort((a, b) => a - b);
  const values = new Map();
  points.forEach((point) => {
    const x = Number(point.moneyness.toFixed(3));
    const key = `${point.days_to_expiry}|${x}`;
    if (!values.has(key)) values.set(key, []);
    values.get(key).push(point.implied_vol);
  });
  const z = yBuckets.map((dte) =>
    xBuckets.map((moneyness) => {
      const bucket = values.get(`${dte}|${moneyness}`) || [];
      return bucket.length ? median(bucket) * 100 : null;
    }),
  );
  return { x: xBuckets, y: yBuckets, z };
}

function smoothGrid(grid, passes) {
  if (!passes) return grid;
  let z = grid.z.map((row) => [...row]);
  for (let pass = 0; pass < passes; pass += 1) {
    z = z.map((row, yi) =>
      row.map((value, xi) => {
        if (!Number.isFinite(value)) return value;
        const neighbors = [];
        for (let y = yi - 1; y <= yi + 1; y += 1) {
          for (let x = xi - 1; x <= xi + 1; x += 1) {
            const candidate = z[y]?.[x];
            if (Number.isFinite(candidate)) neighbors.push(candidate);
          }
        }
        return neighbors.length ? median(neighbors) : value;
      }),
    );
  }
  return { ...grid, z };
}

function activeSurfaceGrid() {
  const grid = buildSurfaceGrid(state.points);
  return state.activeTab === "trader" ? smoothGrid(grid, state.smoothPasses) : grid;
}

function renderSurface3d() {
  if (!window.Plotly) {
    state.mode = "heatmap";
    toggleMode();
    renderHeatmap();
    return;
  }
  const grid = activeSurfaceGrid();
  Plotly.react(
    el.surfaceChart,
    [
      {
        type: "surface",
        x: grid.x,
        y: grid.y,
        z: grid.z,
        colorscale: [
          [0, "#0f766e"],
          [0.42, "#b48616"],
          [1, "#b33a2e"],
        ],
        lighting: { ambient: 0.58, diffuse: 0.72, roughness: 0.84, specular: 0.15 },
        contours: { z: { show: true, usecolormap: true, project: { z: true } } },
        colorbar: { title: "IV %" },
        hovertemplate: "Moneyness %{x}<br>DTE %{y}<br>IV %{z:.2f}%<extra></extra>",
      },
    ],
    {
      margin: { l: 0, r: 0, b: 0, t: 0 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      scene: {
        xaxis: { title: "Moneyness", gridcolor: "#d3dce2", zerolinecolor: "#94a3ad" },
        yaxis: { title: "Days to Expiry", gridcolor: "#d3dce2", zerolinecolor: "#94a3ad" },
        zaxis: { title: "IV %", gridcolor: "#d3dce2", zerolinecolor: "#94a3ad" },
        camera: { eye: { x: 1.45, y: -1.6, z: 0.9 } },
      },
    },
    { displayModeBar: true, responsive: true },
  );
}

function colorFor(value, min, max) {
  const t = Math.max(0, Math.min(1, (value - min) / (max - min || 1)));
  const stops = [
    [15, 118, 110],
    [180, 134, 22],
    [179, 58, 46],
  ];
  const left = t < 0.5 ? stops[0] : stops[1];
  const right = t < 0.5 ? stops[1] : stops[2];
  const local = t < 0.5 ? t * 2 : (t - 0.5) * 2;
  const rgb = left.map((channel, idx) => Math.round(channel + (right[idx] - channel) * local));
  return `rgb(${rgb.join(",")})`;
}

function renderHeatmap() {
  const canvas = el.heatmapCanvas;
  const ctx = canvas.getContext("2d");
  const grid = buildSurfaceGrid(state.points);
  drawHeatmap(ctx, canvas.width, canvas.height, state.activeTab === "trader" ? smoothGrid(grid, state.smoothPasses) : grid);
}

function drawHeatmap(ctx, width, height, grid) {
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#fbfcfd";
  ctx.fillRect(0, 0, width, height);
  const pad = { left: 82, right: 28, top: 24, bottom: 58 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const flat = grid.z.flat().filter(Number.isFinite);
  if (!flat.length) return;
  const min = Math.min(...flat);
  const max = Math.min(state.ivCap * 100, Math.max(...flat));
  grid.y.forEach((dte, yi) => {
    grid.x.forEach((money, xi) => {
      const value = grid.z[yi][xi];
      if (!Number.isFinite(value)) return;
      const x = pad.left + (xi / grid.x.length) * plotW;
      const y = pad.top + (yi / grid.y.length) * plotH;
      ctx.fillStyle = colorFor(value, min, max);
      ctx.fillRect(x, y, Math.ceil(plotW / grid.x.length) + 1, Math.ceil(plotH / grid.y.length) + 1);
    });
  });
  drawAxes(ctx, width, height, pad, "Moneyness", "Days to Expiry");
}

function drawLineChart(canvas, rows, xAccessor, ySeries, xLabel, yLabel) {
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const pad = { left: 58, right: 18, top: 18, bottom: 44 };
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#fbfcfd";
  ctx.fillRect(0, 0, width, height);
  drawAxes(ctx, width, height, pad, xLabel, yLabel);
  if (!rows.length) return;

  const xs = rows.map((row, idx) => xAccessor(row, idx));
  const allY = ySeries.flatMap((series) => rows.map(series.accessor)).filter(Number.isFinite);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...allY);
  const maxY = Math.max(...allY);
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const xScale = (x) => pad.left + ((x - minX) / (maxX - minX || 1)) * plotW;
  const yScale = (y) => pad.top + plotH - ((y - minY) / (maxY - minY || 1)) * plotH;

  ySeries.forEach((series) => {
    ctx.strokeStyle = series.color;
    ctx.lineWidth = series.width || 3;
    ctx.beginPath();
    rows.forEach((row, idx) => {
      const value = series.accessor(row);
      if (!Number.isFinite(value)) return;
      const x = xScale(xAccessor(row, idx));
      const y = yScale(value);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  });
}

function drawAxes(ctx, width, height, pad, xLabel, yLabel) {
  ctx.strokeStyle = "#b8c4cb";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, height - pad.bottom);
  ctx.lineTo(width - pad.right, height - pad.bottom);
  ctx.stroke();
  ctx.fillStyle = "#5a6670";
  ctx.font = "22px system-ui";
  ctx.fillText(xLabel, width / 2 - 52, height - 15);
  ctx.save();
  ctx.translate(22, height / 2 + 52);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText(yLabel, 0, 0);
  ctx.restore();
}

function renderSmile() {
  const groups = groupByExpiry(state.points);
  const expiries = [...groups.keys()].sort();
  const previous = el.expiry.value;
  el.expiry.innerHTML = "";
  expiries.forEach((expiry) => {
    const option = document.createElement("option");
    option.value = expiry;
    option.textContent = expiry;
    el.expiry.appendChild(option);
  });
  const chosen = expiries.includes(previous) ? previous : expiries[0];
  el.expiry.value = chosen || "";
  const rows = (groups.get(chosen) || [])
    .filter((row) => row.moneyness >= 1 - state.moneyBand && row.moneyness <= 1 + state.moneyBand)
    .sort((a, b) => a.moneyness - b.moneyness);
  drawLineChart(
    el.smileCanvas,
    rows,
    (row) => row.moneyness,
    [{ accessor: (row) => row.implied_vol * 100, color: "#0f766e" }],
    "Moneyness",
    "IV %",
  );
}

function renderTermStructure() {
  const rows = [...groupByExpiry(state.points).entries()]
    .map(([expiry, points]) => {
      const atm = nearestAtm(points);
      return atm ? { expiry, days_to_expiry: atm.days_to_expiry, implied_vol: atm.implied_vol } : null;
    })
    .filter(Boolean)
    .sort((a, b) => a.days_to_expiry - b.days_to_expiry);
  drawLineChart(
    el.termCanvas,
    rows,
    (row) => row.days_to_expiry,
    [{ accessor: (row) => row.implied_vol * 100, color: "#b33a2e" }],
    "Days",
    "ATM IV %",
  );
}

function renderHistory() {
  const rows = state.history;
  const canvas = el.historyCanvas;
  const activeIdx = rows.findIndex((row) => row.date === state.date);
  drawLineChart(
    canvas,
    rows,
    (_, idx) => idx,
    [
      { accessor: (row) => row.atm_iv * 100, color: "#0f766e", width: 3 },
      { accessor: (row) => row.realized_vol_30d * 100, color: "#285a9c", width: 2 },
      { accessor: (row) => row.term_slope * 100, color: "#b33a2e", width: 2 },
    ],
    "Trading Dates",
    "Vol %",
  );
  const ctx = canvas.getContext("2d");
  if (activeIdx >= 0 && rows.length > 1) {
    const x = 58 + (activeIdx / (rows.length - 1)) * (canvas.width - 76);
    ctx.strokeStyle = "#172026";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x, 18);
    ctx.lineTo(x, canvas.height - 44);
    ctx.stroke();
  }
  el.historyMeta.textContent = "Green ATM IV · Blue 30D realized vol · Red term slope";
}

function renderTable() {
  const rows = [...state.points]
    .sort((a, b) => a.days_to_expiry - b.days_to_expiry || Math.abs(a.moneyness - 1) - Math.abs(b.moneyness - 1))
    .slice(0, 250);
  el.table.innerHTML = rows
    .map(
      (row) => `<tr>
        <td>${row.expiry}</td>
        <td>${row.days_to_expiry}</td>
        <td>${fmtNum(row.strike, 0)}</td>
        <td>${row.option_type}</td>
        <td>${row.moneyness.toFixed(3)}</td>
        <td>${fmtNum(row.option_price, 2)}</td>
        <td>${fmtPct(row.implied_vol)}</td>
      </tr>`,
    )
    .join("");
  el.tableMeta.textContent = `Showing ${rows.length.toLocaleString("en-IN")} of ${state.points.length.toLocaleString("en-IN")} filtered points`;
  const retained = state.rawPoints.length ? state.points.length / state.rawPoints.length : 0;
  el.surfaceTitle.textContent = state.activeTab === "trader" ? "Clean Trader Surface" : "Raw Surface";
  el.surfaceSubtitle.textContent =
    state.activeTab === "trader"
      ? "DTE, liquidity, IV-band, moneyness, and smoothing filters applied"
      : "Raw contract-implied volatility points from NSE EOD bhavcopy";
  el.surfaceQuality.textContent =
    state.activeTab === "trader"
      ? `Trader filters retained ${Math.round(retained * 100)}% of raw points: DTE ≥ ${state.minDte}, volume ≥ ${state.minVolume}, OI ≥ ${state.minOi.toLocaleString("en-IN")}`
      : "Use Trader View to remove near-expiry, illiquid, and extreme-IV noise.";
}

function toggleMode() {
  const is3d = state.mode === "3d";
  el.mode3d.classList.toggle("active", is3d);
  el.modeHeatmap.classList.toggle("active", !is3d);
  el.surfaceChart.classList.toggle("hidden", !is3d);
  el.heatmapCanvas.classList.toggle("hidden", is3d);
}

function toggleTab(tab) {
  state.activeTab = tab;
  el.tabRaw.classList.toggle("active", tab === "raw");
  el.tabTrader.classList.toggle("active", tab === "trader");
  el.traderControls.classList.toggle("hidden", tab !== "trader");
  state.points = currentDisplayPoints();
  renderAll();
}

function renderAll() {
  syncDateControls();
  renderMetrics();
  toggleMode();
  if (state.mode === "3d") renderSurface3d();
  else renderHeatmap();
  renderSmile();
  renderTermStructure();
  renderHistory();
  renderTable();
}

async function refreshAll() {
  try {
    await loadSurface();
  } catch (error) {
    el.status.textContent = "Error";
    console.error(error);
  }
}

async function reloadForSymbolOrSide() {
  await loadDates();
  await loadHistory();
  await refreshAll();
}

function togglePlayback() {
  if (state.playTimer) {
    clearInterval(state.playTimer);
    state.playTimer = null;
    el.play.textContent = "Play";
    return;
  }
  el.play.textContent = "Pause";
  state.playTimer = setInterval(() => {
    const next = currentDateIndex() + 1;
    setDateByIndex(next >= state.dates.length ? 0 : next);
  }, 900);
}

function wireEvents() {
  el.symbol.addEventListener("change", async () => {
    state.symbol = el.symbol.value;
    state.date = null;
    await reloadForSymbolOrSide();
  });
  el.date.addEventListener("change", () => {
    state.date = el.date.value;
    syncDateControls();
    refreshAll();
  });
  el.dateSlider.addEventListener("input", () => setDateByIndex(Number(el.dateSlider.value)));
  el.prevDate.addEventListener("click", () => setDateByIndex(currentDateIndex() - 1));
  el.nextDate.addEventListener("click", () => setDateByIndex(currentDateIndex() + 1));
  el.play.addEventListener("click", togglePlayback);
  el.optionType.addEventListener("change", async () => {
    state.optionType = el.optionType.value;
    await loadHistory();
    await refreshAll();
  });
  el.ivCap.addEventListener("input", () => {
    state.ivCap = Number(el.ivCap.value) / 100;
    el.ivCapLabel.textContent = `${el.ivCap.value}%`;
    state.points = currentDisplayPoints();
    renderAll();
  });
  el.moneyBand.addEventListener("input", () => {
    state.moneyBand = Number(el.moneyBand.value) / 100;
    el.moneyBandLabel.textContent = `±${el.moneyBand.value}%`;
    state.points = currentDisplayPoints();
    renderAll();
  });
  el.tabRaw.addEventListener("click", () => toggleTab("raw"));
  el.tabTrader.addEventListener("click", () => toggleTab("trader"));
  el.minDte.addEventListener("input", () => {
    state.minDte = Number(el.minDte.value);
    el.minDteLabel.textContent = `${state.minDte} days`;
    state.points = currentDisplayPoints();
    renderAll();
  });
  el.minVolume.addEventListener("input", () => {
    state.minVolume = Number(el.minVolume.value);
    el.minVolumeLabel.textContent = state.minVolume.toLocaleString("en-IN");
    state.points = currentDisplayPoints();
    renderAll();
  });
  el.minOi.addEventListener("input", () => {
    state.minOi = Number(el.minOi.value);
    el.minOiLabel.textContent = state.minOi.toLocaleString("en-IN");
    state.points = currentDisplayPoints();
    renderAll();
  });
  el.ivBand.addEventListener("input", () => {
    state.ivCeiling = Number(el.ivBand.value) / 100;
    el.ivBandLabel.textContent = `10-${el.ivBand.value}%`;
    state.points = currentDisplayPoints();
    renderAll();
  });
  el.smoothPasses.addEventListener("input", () => {
    state.smoothPasses = Number(el.smoothPasses.value);
    el.smoothPassesLabel.textContent = `${state.smoothPasses} pass${state.smoothPasses === 1 ? "" : "es"}`;
    renderAll();
  });
  el.refresh.addEventListener("click", refreshAll);
  el.mode3d.addEventListener("click", () => {
    state.mode = "3d";
    renderAll();
  });
  el.modeHeatmap.addEventListener("click", () => {
    state.mode = "heatmap";
    renderAll();
  });
  el.expiry.addEventListener("change", renderSmile);
  el.historyCanvas.addEventListener("click", (event) => {
    const rect = el.historyCanvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const idx = Math.round((x / rect.width) * (state.dates.length - 1));
    setDateByIndex(idx);
  });
}

async function init() {
  wireEvents();
  registerServiceWorker();
  await reloadForSymbolOrSide();
}

init();

function registerServiceWorker() {
  if (!("serviceWorker" in navigator) || window.location.protocol === "file:") return;
  navigator.serviceWorker.register("service-worker.js").catch((error) => {
    console.warn("Service worker registration failed", error);
  });
}
