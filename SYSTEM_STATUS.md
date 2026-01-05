# Fundametrics Scraper — Current System Status

_Last updated: 2025-12-22_

## 1. High-level Overview

Fundametrics is an internal analytics platform that ingests fundamentals from external sources, normalises the payloads, and publishes read-only insights via a FastAPI surface and a lightweight dashboard. The current build focuses on observability, deterministic processing, and historical trend analytics rather than large-scale crawling.

```
External HTML sources → Fetcher → Parsing layer → DataPipeline
                    ↓                           ↓
                Trendlyne (optional)        FundametricsResponseBuilder
                                            ↓
                               DataRepository (JSON) ← TrendEngine
                                            ↓
                        FastAPI (REST) ← Dashboard (static HTML/JS)
```

## 2. Scraper & Pipeline Mechanics

| Component | Responsibility | Notes |
| --- | --- | --- |
| `scraper/sources/screener.py` | Async `scrape_stock(symbol)` for core fundamentals | Uses shared `Fetcher` with rate limiting, retries, and structured logging. |
| `scraper/sources/trendlyne.py` | Optional profile enrichment (company info, sector) | Plumbed into main pipeline, but safe if disabled. |
| `scraper/core/fetcher.py` | HTTP orchestration | Respectful back-off, jitter, and proxy support. |
| `scraper/core/data_pipeline.py` | Cleans/validates raw payloads | Produces `clean_data` & validation report consumed downstream. |
| `scraper/core/api_response_builder.py` | Generates canonical Fundametrics response object | Handles table pivoting, shareholding summary, metadata enrichment. |
| `scraper/core/repository.py` | Persists runs under `data/processed/<symbol>/<run_id>.json` | Guarantees deterministic structure for TrendEngine & API. |

Run IDs are UUID4; timestamps are UTC ISO8601 with trailing `Z`. Run payloads include:

```json
{
  "symbol": "MRF",
  "run_id": "...",
  "run_timestamp": "2025-12-21T15:46:00Z",
  "validation": {...},
  "metrics": {...},
  "fundametrics_response": {...},
  "shareholding": {
    "status": "unavailable" | "ok" | "partial",
    "summary": {...},
    "insights": [...]
  }
}
```

## 3. Observability & Error Handling

- **Structured JSON logging** (`scraper/core/observability/logger.py`) with contextual fields: `run_id`, `symbol`, `phase`, `status`, `duration`.
- **Phase timer** helper wraps long-running operations for consistent duration reporting.
- **Error taxonomy** (`scraper/core/errors.py`): `ScrapeError`, `ValidationError`, `SignalError`, `PersistenceError`, etc., each with `as_dict()` for telemetry.
- **Health endpoint** (`GET /health`): reports service uptime, last run timestamp, run/error counts for “today”, and whether signals are enabled.
- **AlertManager** (`scraper/core/observability/alerts.py`): configurable SMTP + Slack hooks (disabled by default in `config/settings.yaml`).

## 4. Historical Analytics

`TrendEngine` (`scraper/core/analytics/trends.py`) examines persisted runs via `DataRepository` and surfaces:

- **Revenue CAGR** (neutral/improving/declining based on ±2% threshold).
- **Promoter Holding Trend** (linear regression slope over promoter % series).
- **Signal Momentum** (direction of severity changes across signals).
- **Stability Score** (1 − avg coefficient of variation across revenue/promoter/institutional).

Errors during trend computation are trapped and logged, returning a safe payload.

## 5. API Surface (FastAPI)

Main entry point: `scraper/api/app.py` with CORS enabled for localhost dashboard access.

| Endpoint | Description |
| --- | --- |
| `GET /health` | Operational heartbeat (status, last run, daily counts, signals flag). |
| `GET /stocks/{symbol}` | Latest sanitised run for a symbol (metadata, fundamentals, signals, shareholding summary). Returns 404 if symbol unknown. |
| `GET /stocks/{symbol}/runs` | Metadata (run_id, timestamp, validation status) for historical runs. |
| `GET /api/v1/symbol/{symbol}/trends?periods=4` | Read-only trend summary from `TrendEngine`. Valid periods: 2–12. |

CORS policy (allow list): `http://localhost`, `http://localhost:8080`, `http://127.0.0.1:8080`.

## 6. Dashboard (Phase 10)

Location: `dashboard/index.html`, `dashboard/app.js`

- **Visual language:** Space Grotesk / Work Sans, gradient background, “instrument cluster” panels.
- **Features:**
  - Symbol search with uppercase normalisation and duplicate-fetch debounce.
  - Run snapshot panel (status chip, run timestamp, top six ratios).
  - Signals panel (severity colour coding, confidence percentage).
  - Shareholding panel (status pill, insights list).
  - Trend engine panel (arrow glyphs for improving / declining / stable).
- **Bootstrap behaviour:** auto-loads `RELIANCE` on init for quick smoke tests.

Serve locally:

```powershell
# Terminal 1 – API
cd C:\Users\Laser cote\.gemini\antigravity\scratch\fundametrics-scraper
py -m uvicorn scraper.api.app:app --host 0.0.0.0 --port 8000

# Terminal 2 – Dashboard
cd C:\Users\Laser cote\.gemini\antigravity\scratch\fundametrics-scraper\dashboard
py -m http.server 8080

# Browser
http://localhost:8080/
```

## 7. Test & Coverage Highlights

- Extensive unit coverage for signal engines (`tests/unit/test_fundamental_signals.py`, `test_ownership_signals.py`) and run delta engine (`test_delta_engine.py`).
- Integration coverage for API signal surface (`tests/integration/test_api_signals.py`) and pipeline persistence (`test_pipeline_signals.py`).
- Manual smoke tests confirm trend endpoint and dashboard behaviour for `RELIANCE` and `MRF`.

## 8. Known Limitations & Next Steps

1. **Metrics density:** Some runs (e.g. `MRF`) lack populated `financials.metrics`, so dashboard cards remain empty even though the pipeline is working. Action: expand parsers or seed richer data.
2. **Signals availability:** Without signal generation for a symbol, the signals panel shows the empty-state copy. Action: enable or backfill signal engines for more tickers.
3. **Shareholding insights:** Many upstream sources mark shareholding as unavailable; consider enabling Trendlyne ingestion or connecting additional data sources.
4. **Deployment:** Current stack is development-friendly. Production rollout would benefit from packaging (Docker/Poetry) and secrets management for alerting.

## 9. Quickstart Checklist

- ✅ Structured logging and Fundametrics error hierarchy
- ✅ Health endpoint with run analytics
- ✅ Alert manager (configurable via YAML)
- ✅ Trend engine + REST endpoint
- ✅ Dashboard consuming API
- ☐ Broader symbol coverage (data quality)
- ☐ Production deployment pipeline

---

For deeper inspection, refer to individual module docstrings or the test suite for examples. This document should serve as the day-zero state of the Fundametrics scraper as of late December 2025.
