# Phase 20 – Fundametrics High-Density UI Blueprint

## Overview
Phase 20 delivers a Screener/Trendlyne-inspired desktop experience optimised for
power users. The design emphasises high information density, structured visual
hierarchy, and Fundametrics-exclusive metadata (confidence, explainability, provenance).

The layout flows top-to-bottom:
1. Executive Snapshot Grid
2. Price & Performance Strip
3. Growth Summary Tiles
4. Financial Tables (Annual / Quarterly / Cash Flow)
5. Ratios & Efficiency Tables
6. Confidence & Data Quality Layer
7. Peer Comparison Matrix
8. Notes, Flags & Interpretations

### Core Design Principles
- Tight spacing (4/8 px increments), 12–14 px typography, no card shadows.
- Neutral base palette (warm grey background, deep grey text), Fundametrics teal accent.
- Confidence and explainability embedded inline; tooltips expose detail.
- Desktop-first (min width 1280px); tablet mode collapses to two columns.
- All tabular content supports keyboard navigation, hover metadata, export.

## Section Specifications

### 1. Executive Snapshot Grid
Dense 6×2 grid summarising headline metrics.
- **Metrics**: Market Cap, PE, PB, ROE, Debt/Equity, Revenue CAGR, Profit CAGR,
  FCF Yield, Operating Margin, Interest Coverage, EV/EBITDA, Dividend Yield.
- **Cell anatomy**:
  - Label: 11 px, muted (Gray 500).
  - Value: 18 px, semibold.
  - Subtext: 10 px micro-copy (YoY change, 5Y avg, vs sector).
  - Confidence: inline dot scale (●●●○) or numeric (e.g. 82).
- No backgrounds; use 1 px separators forming the grid.

### 2. Price & Performance Strip
Two-column section comparable to Screener charts.
- **Left**: lightweight line chart; tabs for 1Y / 3Y / 5Y / Max.
  - Thin axes (0.5 px), minimal grid.
  - Tooltip: {Date, Price, Confidence score}.
- **Right**: stacked price stats (52W high/low, Volatility %, Drawdown).
  - Each stat follows snapshot cell style.
- Height ~260 px; width split 60/40 chart/stats.

### 3. Growth Summary Tiles
Row of 4–6 tiles focusing on temporal growth performance.
- Each tile: label + row of period values (3Y / 5Y / 10Y).
- Values colour-coded: >15% teal, 5–15% gray, <5% muted red.
- Confidence sparkline: thin micro chart or dot row referencing factor.

### 4. Financial Tables
Primary data block with multiple tabs.
- Sticky first column containing metric names; horizontal scroll for periods.
- Font 12 px; header row uses period labels (FY15 … FY24).
- Light zebra striping; key rows (Revenue, EBITDA, Net Profit, Operating Cash
  Flow) tinted with 5% accent background.
- Row suffix: confidence badge, available/unavailable icon, explainability link.
- Tabs: Annual (10Y), Quarterly (12 quarters), Cash Flow (operating, investing,
  financing).

### 5. Ratios & Efficiency Tables
Grouped two-column layout.
- Categories: Profitability, Liquidity, Leverage, Efficiency.
- Each row: ratio name, latest value, 3-period sparkline, trend arrow (↑/↓),
  confidence dot.
- Category headers left aligned with subtle underline.

### 6. Confidence & Data Quality Layer
Expose Fundametrics confidence model visually.
- Inline badge next to metric value showing score (0–100).
- Hover reveals tooltip with factors (freshness, completeness, source) and their
  contributions, plus explanation/blocked reasons.
- “Why this confidence?” link opens right-side drawer summarising inputs used,
  blocked because, provenance info.

### 7. Peer Comparison Matrix
Table comparing current company vs peers.
- Columns: same metrics as snapshot, plus revenue & profit CAGR.
- Rows: peer tickers, sorted by market cap by default.
- Highlight current company row with subtle background.
- Confidence shown via dot scale per cell; allow column sorting.

### 8. Notes, Flags & Interpretations
Fact-based insights section.
- Title: “Data Notes & Interpretations”.
- Bulleted list with tags (e.g., `volatility`, `scope_change`).
- Sentences stay observational: “Revenue volatility increased post FY21 due to
  scope change.”
- Link to source statement IDs or audit logs if clicked.

## Data & Integration Requirements
- Each metric payload must include value, unit, confidence score, explainability
  strings (why_available/unavailable, inputs used, blocked reason), provenance
  metadata.
- Confidence tooltips fetch factors from Phase 17A model.
- Explainability drawer uses Phase 17B objects.
- Financial table exports use consistent schema (CSV/Excel) with confidence.

## Deployment & Testing
- Build as responsive web components using existing Fundametrics design system.
- Storybook scenarios covering each section and states (verified/partial/blocked).
- Regression tests ensuring confidence badges render for every metric row.
- Accessibility audit (keyboard nav, screen reader labels referencing confidence).

## Next Steps
1. Implement React (or equivalent) components per section in `dashboard/`.
2. Extend API response to supply explainability/provenance blocks.
3. Wire data pipeline for peer comparisons and growth period calculations.
4. Add CI checks for confidence/explainability presence before release.
