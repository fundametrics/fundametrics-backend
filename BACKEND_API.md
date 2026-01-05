# Fundametrics Backend API Documentation

## Base URL
Default: `http://localhost:8000`

## Endpoints

### GET /stocks
Lists all processed symbols.
- **Response**: `{count: number, symbols: string[]}`
- **Notes**: Alphabetical order; read‑only.

### GET /stocks/{symbol}
Company fundamentals and metadata.
- **Response**: `CompanyResponse`
  - `symbol`, `company.name`, `company.sector`
  - `financials.latest` (revenue, profit, margins)
  - `financials.ratios[]` (ROE, ROCE, margins, interest coverage)
  - `signals[]` (observational, non‑advisory)
  - `shareholding` (status, summary, insights)
  - `metadata` (sources, as_of_date, warnings, disclaimer)
  - Optional `ai_summary` (historical-only paragraphs)
  - Optional `coverage` (score, available/missing blocks)

### GET /stocks/{symbol}/market
Delayed market facts.
- **Response**: `MarketFacts`
  - `price.value`, `price.delay_minutes`
  - `market_cap.value`, `market_cap.computed`
  - `range_52_week.high/low`
  - `shares_outstanding.value`
  - `metadata` (source, delay disclaimer)

### GET /search
Search symbols; optional query filter.
- **Query param**: `?q=<string>`
- **Response**: `{query, results[], disclaimer}`
- **Results**: `{symbol, name, sector}`

### GET /coverage
Per‑symbol coverage summary.
- **Response**: `CoverageIndexResponse`
  - `generated_at`, `totals`, `results[]`
  - Each result: `symbol`, `name`, `sector`, `coverage`, `last_processed`, `warnings[]`

## Compliance Notes
- All responses are read‑only and informational.
- No forward‑looking statements or recommendations.
- Market data is labeled “Delayed / Unavailable” when missing.
- Coverage and warnings are factual, not qualitative.

## Error Handling
- **404**: Symbol not processed yet.
- **500**: Internal server error (e.g., file read failure).
- **OPTIONS**: Handled for CORS; returns 200.

## Data Model Highlights
- `CompanyResponse.financials.ratios`: Array of `{name, value, category?, note?}`.
- `MarketFacts.metadata`: Includes `delay_disclaimer` and `source_disclaimer`.
- `CoverageSummary`: `{score, available[], missing[], note}`.

## Extending the API
- Add new routes in `scraper/api/routes.py`.
- Keep responses under the `fundametrics_response` envelope for consistency.
- Update frontend types in `src/types.ts` accordingly.
