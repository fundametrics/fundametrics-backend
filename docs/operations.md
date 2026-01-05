# Operations Guide

## Automatic Refresh Pipeline
- GitHub Actions workflow (`.github/workflows/fundametrics-refresh.yml`) runs every six hours and is invokable manually via *workflow_dispatch*.
- The job provisions Python 3.11, installs dependencies from `requirements.txt`, and exports ingestion environment variables from repository secrets.
- Before triggering a refresh, the workflow executes `python -m scraper.jobs.health_check` which calls `/admin/health`. If the reported status is `unhealthy`, the job exits successfully without running a refresh.
- When the pipeline is healthy, the workflow launches `python -m scraper.jobs.refresh`, which now uses the smart refresh allocator introduced in Phase 16C:
  - `scraper.refresh.policy` maps symbol priority (1–5) to minimum refresh intervals (15 minutes to 1 week).
  - `scraper.refresh.cooldown` enforces exponential backoff on repeated failures with a 24-hour cap to avoid hammering unstable sources.
  - `scraper.refresh.decision` evaluates each symbol (`should_refresh`) based on status, cooldown windows, and priority interval staleness, producing explainable log reasons.
  - `scraper.refresh.budget` applies the per-run cap derived from `INGEST_MAX_PER_RUN`, turning the loop into a budget-aware allocator.
- Decision logging is emitted in the format `[refresh] SKIP|RUN SYMBOL (priority=X): <reason>` so operators can understand every action during incident response.
- Phase 16D adds an adaptive boost layer: symbols can carry temporary priority boosts (`models.boost.PriorityBoost`) from user interest, manual overrides, or recovery after failures. The scheduler prunes expired boosts at startup and orders symbols by *effective* priority (base + active boosts).

## Disabling Ingestion Safely
1. Set `INGEST_ENABLED` secret (or environment variable) to `false` before the next scheduler window.
2. Confirm `/admin/health` reflects `system.ingest_enabled = false`.
3. Leave the action in place—the health check will skip refresh runs until ingestion is re-enabled.

## `/admin/health` Status Reference
- `healthy`: No stale symbols, no critical warnings, and last ingestion completed successfully.
- `degraded`: Some stale symbols or non-critical warnings detected; monitor but refresh can proceed.
- `unhealthy`: Refresh is halted. Investigate stale coverage (>30%), critical warnings, or failed ingestions before re-running.

## Operational Logs and State
- Scheduler logs are stored in the GitHub Actions run output (Actions tab).
- Local refresh executions append to `logs/refresh-YYYY-MM-DD.log` and persist the latest ingestion state in `data/system/last_ingestion.json`.
- The symbol registry (`data/system/symbol_registry.json`) now tracks `last_attempt`, `last_refreshed`, `failure_count`, and any active boosts per symbol (`boosts` array with kind/weight/expires_at/source) to explain decision outcomes and cooldown windows.
- For incident reviews, collect the relevant GitHub Actions run URL plus the corresponding local log, symbol registry snapshot, and state file.

## Admin Boost Endpoint
- `/admin/boost` (POST) allows authorised operators to apply temporary priority boosts:
  ```json
  {
    "symbol": "RELIANCE",
    "kind": "user_interest",
    "weight": 1,
    "ttl_hours": 6
  }
  ```
- Requires the admin API key and honours configured weight/TTL caps (max weight = 3, max TTL = 48h).
- Response confirms application and reports the new effective priority label (e.g. `HIGH+1`).
- Boosts expire automatically and never bypass scheduler safeguards (cooldown, budget, or failure backoff).
