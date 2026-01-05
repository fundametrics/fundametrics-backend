const API_BASE = "http://localhost:8000";

const form = document.getElementById("symbol-form");
const symbolInput = document.getElementById("symbol-input");
const integrityIndicator = document.getElementById("integrity-indicator");

const snapshotGrid = document.getElementById("snapshot-grid");
const snapshotTimestamp = document.getElementById("snapshot-timestamp");
const snapshotEmpty = document.getElementById("snapshot-empty");

const chartTabs = document.getElementById("chart-tabs");
const priceCanvas = document.getElementById("price-canvas");
const priceConfidence = document.getElementById("price-confidence");
const priceStats = document.getElementById("price-stats");

const growthTiles = document.getElementById("growth-tiles");

const financialTabs = document.getElementById("financial-tabs");
const financialTableWrapper = document.getElementById("financial-table-wrapper");

const ratioColumns = document.getElementById("ratio-columns");
const confidenceLayer = document.getElementById("confidence-layer");
const peerTable = document.getElementById("peer-table");
const notesList = document.getElementById("notes-list");

const state = {
  currentSymbol: null,
  controller: null,
  data: null,
  chartRange: "1Y",
};

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const symbol = symbolInput.value.trim().toUpperCase();
  if (!symbol) {
    return;
  }
  loadSymbol(symbol);
});

symbolInput.addEventListener("input", () => {
  symbolInput.value = symbolInput.value.replace(/\s+/g, "").toUpperCase();
});

async function loadSymbol(symbol) {
  if (state.controller) {
    state.controller.abort();
  }
  const controller = new AbortController();
  state.controller = controller;
  state.currentSymbol = symbol;
  setLoading(true);

  try {
    const payload = await fetchLatest(symbol, controller.signal);
    if (!payload) {
      throw new Error("Symbol not found");
    }
    state.data = payload;
    renderDashboard(payload);
  } catch (error) {
    if (error.name === "AbortError") {
      return;
    }
    displayError(error.message || "Unable to load data");
  } finally {
    setLoading(false);
  }
}

async function fetchLatest(symbol, signal) {
  const response = await fetch(`${API_BASE}/stocks/${symbol}`, { signal });
  if (!response.ok) {
    if (response.status === 404) {
      return null;
    }
    throw new Error(`API error (${response.status})`);
  }
  return response.json();
}

function setLoading(isLoading) {
  form.querySelector("button").disabled = isLoading;
  if (isLoading) {
    integrityIndicator.textContent = "Integrity: Loading";
    snapshotTimestamp.textContent = "Fetching…";
  }
}

function displayError(message) {
  integrityIndicator.textContent = `Integrity: ${message}`;
  snapshotTimestamp.textContent = "--";
  snapshotGrid.innerHTML = "";
  snapshotEmpty.classList.remove("hidden");
  priceConfidence.textContent = "Confidence: --";
  priceStats.innerHTML = renderEmptyBlock("Price data unavailable");
  growthTiles.innerHTML = renderEmptyBlock("Growth metrics unavailable");
  financialTabs.innerHTML = "";
  financialTableWrapper.innerHTML = renderEmptyBlock("Financial tables unavailable");
  ratioColumns.innerHTML = renderEmptyBlock("Ratio data unavailable");
  confidenceLayer.innerHTML = renderEmptyBlock("Confidence factors unavailable");
  peerTable.innerHTML = renderEmptyBlock("Peer comparison unavailable");
  notesList.innerHTML = "";
}

function renderDashboard(data) {
  const integrity = data?.metrics?.integrity || data?.metadata?.integrity || "--";
  integrityIndicator.textContent = `Integrity: ${integrity.toUpperCase?.() || integrity}`;

  const timestamp = data?.metadata?.as_of_date || data?.metadata?.run_timestamp;
  snapshotTimestamp.textContent = timestamp ? `As of ${timestamp}` : "Timestamp unavailable";

  renderSnapshotSection(data);
  renderPriceSection(data);
  renderGrowthTiles(data);
  renderFinancialTables(data);
  renderRatios(data);
  renderConfidenceLayer(data);
  renderPeerComparison(data);
  renderNotes(data);
}

function renderSnapshotSection(data) {
  const metrics = data?.financials?.metrics || {};
  const ratios = data?.financials?.ratios || {};
  const lookup = { ...metrics, ...ratios };

  const desiredOrder = [
    { label: "Market Cap", key: "fundametrics_market_cap", subtext: "Latest" },
    { label: "PE Ratio", key: "pe_ratio", subtext: "Trailing" },
    { label: "PB Ratio", key: "pb_ratio", subtext: "Balance sheet" },
    { label: "ROE", key: "fundametrics_return_on_equity", subtext: "Latest" },
    { label: "Debt / Equity", key: "debt_to_equity", subtext: "Latest" },
    { label: "Revenue CAGR", key: "fundametrics_growth_rate_internal", subtext: "Composite" },
    { label: "Profit Margin", key: "fundametrics_net_margin", subtext: "Net" },
    { label: "Operating Margin", key: "fundametrics_operating_margin", subtext: "Operating" },
    { label: "Interest Coverage", key: "fundametrics_interest_coverage", subtext: "TTM" },
    { label: "Asset Turnover", key: "fundametrics_asset_turnover", subtext: "Capital efficiency" },
    { label: "EPS", key: "fundametrics_eps", subtext: "Diluted" },
    { label: "EV / EBITDA", key: "ev_to_ebitda", subtext: "Valuation" },
  ];

  const cells = desiredOrder
    .map(({ label, key, subtext }) => {
      const metric = lookup[key];
      const value = formatMetric(metric);
      const confidence = formatConfidence(metric?.confidence);
      return `
        <div class="snapshot-cell">
          <span class="snapshot-label">${escapeHtml(label)}</span>
          <span class="snapshot-value">${escapeHtml(value)}</span>
          <span class="snapshot-subtext">${escapeHtml(subtext)}</span>
          <span class="confidence-inline" data-tooltip="${escapeHtml(confidence)}">${escapeHtml(confidence)}</span>
        </div>
      `;
    })
    .join("");

  snapshotGrid.innerHTML = cells;
  if (cells.trim().length === 0) {
    snapshotEmpty.classList.remove("hidden");
  } else {
    snapshotEmpty.classList.add("hidden");
  }
}

function renderPriceSection(data) {
  const incomeStatement = data?.financials?.income_statement || {};
  const revenueSeries = extractSeries(incomeStatement, "revenue");
  const chartData = revenueSeries.length > 1 ? revenueSeries : buildFallbackSeries();

  renderChartTabs();
  drawLineChart(priceCanvas, chartData);

  const stats = computeStatistics(chartData.map((point) => point.value));
  priceStats.innerHTML = [
    { label: "Periods", value: chartData.length },
    { label: "High", value: formatNumber(stats.max) },
    { label: "Low", value: formatNumber(stats.min) },
    { label: "Volatility", value: `${stats.volatility.toFixed(1)}%` },
    { label: "Change", value: `${stats.change.toFixed(1)}%` },
  ]
    .map((item) => `
      <div class="price-stat">
        <span class="snapshot-label">${escapeHtml(item.label)}</span>
        <span class="snapshot-value">${escapeHtml(item.value)}</span>
      </div>
    `)
    .join("");

  const confidenceScores = chartData
    .map((point) => point.confidenceScore)
    .filter((score) => typeof score === "number");
  const avgConfidence = confidenceScores.length
    ? (confidenceScores.reduce((a, b) => a + b, 0) / confidenceScores.length).toFixed(0)
    : "--";
  priceConfidence.textContent = `Confidence: ${avgConfidence}`;
}

function renderChartTabs() {
  const ranges = ["1Y", "3Y", "5Y", "10Y", "Max"];
  chartTabs.innerHTML = ranges
    .map((range) => `
      <button type="button" data-range="${range}" aria-pressed="${state.chartRange === range}" aria-label="Show ${range} price history" role="tab">
        ${range}
      </button>
    `)
    .join("");

  chartTabs.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      state.chartRange = button.dataset.range;
      renderPriceSection(state.data);
    });
  });
}

function renderGrowthTiles(data) {
  const incomeStatement = data?.financials?.income_statement || {};
  const revenueSeries = extractSeries(incomeStatement, "revenue");
  const profitSeries = extractSeries(incomeStatement, "net_income");
  const operatingSeries = extractSeries(incomeStatement, "operating_profit");

  const tiles = [
    {
      title: "Sales CAGR",
      series: revenueSeries,
    },
    {
      title: "Profit CAGR",
      series: profitSeries,
    },
    {
      title: "Operating Margin",
      series: operatingSeries,
      ratio: revenueSeries,
    },
  ].map((tile) => {
    const values = buildGrowthPeriods(tile.series, tile.ratio);
    return `
      <div class="growth-tile">
        <span class="snapshot-label">${escapeHtml(tile.title)}</span>
        <div class="growth-periods">
          ${values
            .map(({ label, value, quality }) => `
              <div>
                <span class="snapshot-subtext">${label}</span>
                <span class="${quality}">${value}</span>
              </div>
            `)
            .join("")}
        </div>
      </div>
    `;
  });

  growthTiles.innerHTML = tiles.join("");
}

function renderFinancialTables(data) {
  const bundles = [
    { id: "income", label: "Annual Financials", data: data?.financials?.income_statement || {} },
    { id: "balance", label: "Balance Sheet", data: data?.financials?.balance_sheet || {} },
    { id: "cash", label: "Cash Flow", data: data?.financials?.cash_flow || {} },
  ].filter((bundle) => Object.keys(bundle.data).length);

  if (bundles.length === 0) {
    financialTabs.innerHTML = "";
    financialTableWrapper.innerHTML = renderEmptyBlock("Financial table data unavailable");
    return;
  }

  const activeId = state.activeFinancialTab || bundles[0].id;
  state.activeFinancialTab = activeId;

  financialTabs.innerHTML = bundles
    .map(
      (bundle) => `
        <button
          type="button"
          data-table="${bundle.id}"
          aria-pressed="${bundle.id === activeId}"
          aria-label="Show ${bundle.label} table"
          role="tab"
        >
          ${escapeHtml(bundle.label)}
        </button>
      `,
    )
    .join("");

  financialTabs.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeFinancialTab = button.dataset.table;
      renderFinancialTables(state.data);
    });
  });

  const activeBundle = bundles.find((bundle) => bundle.id === activeId) || bundles[0];
  financialTableWrapper.innerHTML = buildFinancialTable(activeBundle.data);
}

function renderRatios(data) {
  const ratios = data?.financials?.ratios || {};
  const grouped = {
    Profitability: ["fundametrics_operating_margin", "fundametrics_net_margin", "return_on_equity", "gross_margin"],
    Liquidity: ["current_ratio", "quick_ratio", "cash_ratio"],
    Leverage: ["debt_to_equity", "interest_coverage", "debt_service_coverage"],
    Efficiency: ["fundametrics_asset_turnover", "inventory_turnover", "receivables_turnover"],
  };

  ratioColumns.innerHTML = Object.entries(grouped)
    .map(([group, keys]) => {
      const rows = keys
        .map((key) => {
          const metric = ratios[key];
          if (!metric) {
            return "";
          }
          const trend = determineTrend(metric);
          return `
            <div class="ratio-row">
              <span class="snapshot-label">${escapeHtml(formatMetricName(key))}</span>
              <span class="snapshot-value">${escapeHtml(formatMetric(metric))}</span>
              <span class="ratio-trend" data-trend="${trend}" data-trend-tooltip="${escapeHtml(trendTooltip(trend))}">${trendIndicator(trend)}</span>
            </div>
          `;
        })
        .join("");
      if (!rows) {
        return "";
      }
      return `
        <div class="ratio-group">
          <div class="ratio-row" style="background:#eef2f7; font-weight:600;">
            <span>${escapeHtml(group)}</span>
            <span></span>
            <span></span>
          </div>
          ${rows}
        </div>
      `;
    })
    .join("");

  if (!ratioColumns.textContent.trim()) {
    ratioColumns.innerHTML = renderEmptyBlock("Ratio data unavailable");
  }
}

function renderConfidenceLayer(data) {
  const metrics = data?.financials?.metrics || {};
  const ratios = data?.financials?.ratios || {};
  const combined = Object.entries({ ...metrics, ...ratios })
    .map(([key, metric]) => ({ key, metric }))
    .filter((entry) => entry.metric?.confidence)
    .sort((a, b) => (a.metric.confidence.score || 0) - (b.metric.confidence.score || 0))
    .slice(0, 6);

  if (combined.length === 0) {
    confidenceLayer.innerHTML = renderEmptyBlock("Confidence details unavailable");
    return;
  }

  confidenceLayer.innerHTML = combined
    .map(({ key, metric }) => {
      const conf = metric.confidence;
      const factors = conf.factors || {};
      return `
        <div class="confidence-card">
          <span class="snapshot-label">${escapeHtml(formatMetricName(key))}</span>
          <span class="snapshot-value">${escapeHtml(conf.score ?? "--")}/100 · ${escapeHtml(conf.grade || "none")}</span>
          <div class="confidence-breakdown">
            ${Object.entries(factors)
              .map(([factor, score]) => `${escapeHtml(formatFactorName(factor))}: ${escapeHtml(String(score))}`)
              .join("<br />")}
          </div>
        </div>
      `;
    })
    .join("");
}

function renderPeerComparison(data) {
  const peers = data?.peer_comparison;
  if (!peers || !Array.isArray(peers) || peers.length === 0) {
    peerTable.innerHTML = renderEmptyBlock("Peer comparison unavailable");
    return;
  }

  const columns = ["symbol", "market_cap", "pe_ratio", "roe", "revenue_cagr", "net_margin"];
  const header = columns.map((col) => `<th>${escapeHtml(formatMetricName(col))}</th>`).join("");
  const rows = peers
    .map((peer) => {
      const isCurrent = peer.symbol === state.currentSymbol;
      return `
        <tr${isCurrent ? ' style="background: rgba(15,123,159,0.08);"' : ""}>
          ${columns
            .map((col) => `<td>${escapeHtml(formatNumber(peer[col], { fallback: "--" }))}</td>`)
            .join("")}
        </tr>
      `;
    })
    .join("");

  peerTable.innerHTML = `
    <table role="table" aria-label="Peer comparison matrix" tabindex="0">
      <thead><tr>${header}</tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderNotes(data) {
  const warnings = data?.metadata?.warnings || [];
  const notes = warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`);
  notesList.innerHTML = notes.join("");
}

function buildFinancialTable(bundle) {
  const periods = sortPeriods(Object.keys(bundle));
  const metrics = new Set();
  periods.forEach((period) => {
    const row = bundle[period] || {};
    Object.keys(row).forEach((metric) => metrics.add(metric));
  });

  const highlightSet = new Set([
    "revenue",
    "net_income",
    "operating_profit",
    "operating_cash_flow",
    "profit_before_tax",
  ]);

  const rows = Array.from(metrics)
    .map((metricKey) => {
      const rowCells = periods
        .map((period) => {
          const metric = bundle[period]?.[metricKey];
          if (!metric) {
            return `<td>--</td>`;
          }
          const display = formatMetric(metric);
          const confidence = formatConfidence(metric.confidence);
          return `<td title="${escapeHtml(confidence)}">${escapeHtml(display)}</td>`;
        })
        .join("");

      return `
        <tr data-highlight="${highlightSet.has(metricKey)}">
          <th>${escapeHtml(formatMetricName(metricKey))}</th>
          ${rowCells}
        </tr>
      `;
    })
    .join("");

  const header = periods.map((period) => `<th>${escapeHtml(period)}</th>`).join("");

  return `
    <table role="table" aria-label="Financial data" tabindex="0">
      <thead>
        <tr>
          <th>Metric</th>
          ${header}
        </tr>
      </thead>
      <tbody>
        ${rows}
      </tbody>
    </table>
  `;
}

function extractSeries(bundle, key) {
  const periods = sortPeriods(Object.keys(bundle || {}));
  return periods
    .map((period) => {
      const metric = bundle?.[period]?.[key];
      if (!metric || typeof metric.value !== "number") {
        return null;
      }
      return {
        period,
        value: metric.value,
        confidenceScore: metric?.confidence?.score,
      };
    })
    .filter(Boolean);
}

function buildGrowthPeriods(series, ratioSeries) {
  const periods = [
    { label: "3Y", years: 3 },
    { label: "5Y", years: 5 },
    { label: "10Y", years: 10 },
  ];

  return periods.map(({ label, years }) => {
    const growth = calculateCAGR(series, years, ratioSeries);
    return {
      label,
      value: growth.display,
      quality: growth.quality,
    };
  });
}

function calculateCAGR(series, years, ratioSeries) {
  if (!Array.isArray(series) || series.length < 2) {
    return { display: "--", quality: "" };
  }
  const span = Math.min(series.length - 1, years - 1);
  if (span <= 0) {
    return { display: "--", quality: "" };
  }
  const latest = series[series.length - 1];
  const earliest = series[series.length - 1 - span];
  if (!earliest || earliest.value <= 0) {
    return { display: "--", quality: "" };
  }
  const cagr = ((latest.value / earliest.value) ** (1 / span) - 1) * 100;
  if (!Number.isFinite(cagr)) {
    return { display: "--", quality: "" };
  }
  const display = `${cagr.toFixed(1)}%`;
  const quality = cagr >= 15 ? "strong" : cagr < 5 ? "weak" : "";
  return { display, quality };
}

function determineTrend(metric) {
  const grade = metric?.confidence?.grade;
  if (grade === "high" || grade === "medium") {
    return "up";
  }
  if (metric?.value === null) {
    return "down";
  }
  return "steady";
}

function trendIndicator(trend) {
  if (trend === "up") {
    return "▲";
  }
  if (trend === "down") {
    return "▼";
  }
  return "▶";
}

function drawLineChart(canvas, dataPoints) {
  const ctx = canvas.getContext("2d");
  const width = canvas.width = canvas.clientWidth;
  const height = canvas.height = canvas.clientHeight;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  if (!dataPoints.length) {
    ctx.fillStyle = "#5b6374";
    ctx.font = "12px var(--sans)";
    ctx.fillText("No data", 12, 24);
    return;
  }

  const values = dataPoints.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const padding = 20;

  ctx.strokeStyle = "#d9dde5";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(padding, height - padding);
  ctx.lineTo(width - padding, height - padding);
  ctx.moveTo(padding, padding);
  ctx.lineTo(padding, height - padding);
  ctx.stroke();

  ctx.strokeStyle = "#0f7b9f";
  ctx.lineWidth = 2;
  ctx.beginPath();
  dataPoints.forEach((point, index) => {
    const x = padding + (index / Math.max(1, dataPoints.length - 1)) * (width - padding * 2);
    const y = height - padding - ((point.value - min) / Math.max(1, max - min)) * (height - padding * 2);
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();
}

function computeStatistics(values) {
  if (!values.length) {
    return { max: 0, min: 0, change: 0, volatility: 0 };
  }
  const max = Math.max(...values);
  const min = Math.min(...values);
  const change = ((values[values.length - 1] - values[0]) / Math.max(values[0], 1)) * 100;
  const mean = values.reduce((acc, val) => acc + val, 0) / values.length;
  const variance = values
    .map((value) => (value - mean) ** 2)
    .reduce((acc, val) => acc + val, 0) / values.length;
  const volatility = Math.sqrt(variance) / Math.max(mean, 1) * 100;
  return { max, min, change, volatility };
}

function renderEmptyBlock(message) {
  return `<div style="padding:16px; font-size:12px; color:#5b6374;">${escapeHtml(message)}</div>`;
}

function formatMetric(metric) {
  if (!metric) {
    return "--";
  }
  if (metric.value === null || metric.value === undefined) {
    return metric.reason ? `— (${metric.reason})` : "—";
  }
  const unit = metric.unit && metric.unit !== "" ? metric.unit : "";
  const value = formatNumber(metric.value);
  return unit ? `${value} ${unit}` : value;
}

function formatNumber(value, options = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return options.fallback ?? "--";
  }
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000_000) {
    return `${(value / 1_000_000_000_000).toFixed(2)}T`;
  }
  if (abs >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toFixed(2)}B`;
  }
  if (abs >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(2)}M`;
  }
  if (abs >= 1_000) {
    return `${(value / 1_000).toFixed(1)}k`;
  }
  if (Number.isInteger(value)) {
    return value.toLocaleString();
  }
  return value.toFixed(2);
}

function formatConfidence(confidence) {
  if (!confidence) {
    return "Confidence --";
  }
  const score = confidence.score != null ? confidence.score : "--";
  const grade = confidence.grade || "none";
  return `Confidence ${score} (${grade})`;
}

function buildFallbackSeries() {
  return Array.from({ length: 6 }).map((_, index) => ({
    period: `P${index + 1}`,
    value: 100 + index * 10,
    confidenceScore: 50,
  }));
}

function sortPeriods(periods) {
  return periods.slice().sort((a, b) => {
    const aTime = Date.parse(a) || a;
    const bTime = Date.parse(b) || b;
    if (aTime < bTime) return -1;
    if (aTime > bTime) return 1;
    return 0;
  });
}

function formatMetricName(name) {
  return name
    .replace(/fundametrics_/g, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatFactorName(name) {
  return name
    .replace(/_/g, " ")
    .replace(/\bfreshness\b/i, "Freshness")
    .replace(/\bsource\b/i, "Source")
    .replace(/\bstatement\b/i, "Statement")
    .replace(/\bcompleteness\b/i, "Completeness")
    .replace(/\bstability\b/i, "Stability")
    .replace(/\bfactors\b/i, "Factors")
    .replace(/\bmatch\b/i, "Match")
    .replace(/\bfactor\b/i, "Factor")
    .replace(/\b([a-z])/g, (_, char) => char.toUpperCase());
}

function escapeHtml(value) {
  if (value == null) {
    return "";
  }
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

(async function init() {
  const defaultSymbol = "RELIANCE";
  symbolInput.value = defaultSymbol;
  await loadSymbol(defaultSymbol);
})();
