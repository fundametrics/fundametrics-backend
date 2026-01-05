# Fundametrics Scraper - Hardening & Scaling Checklist

## 1. Request Fingerprinting (Completed)
- [x] **User-Agent Rotation**: Randomized pool of modern browser UAs.
- [x] **Header Fingerprinting**: Rotating `Accept-Language`, `Sec-Fetch-*`, and `Sec-Ch-Ua` headers to match real browsers.
- [x] **Direct Jitter**: Randomized delays between 1-5s before each scrape and within the Token Bucket rate limiter.

## 2. IP Protection (Ready)
- [x] **Proxy Support**: `Fetcher` now supports a `proxies` list and picks a random one on startup.
- [x] **Auto-Rotation**: `Fetcher` automatically rotates to the next available proxy if a `403 Forbidden` block is detected.
- [ ] **External Proxy Provider**: (Action Required) Plug in your rotating proxy URLs in `settings.yaml` or `.env`.

## 3. Scaling to 5,000+ Companies (Completed)
- [x] **Async Concurrency**: `ScraperEngine` uses `asyncio.Semaphore` to process symbols in parallel.
- [x] **Resource Limiting**: Default `max_concurrency` set to 5-10 to stay within host CPU/RAM limits.
- [x] **Incremental Scrape**: Use the cron scheduler to spread load across hours rather than a single burst.

## 4. Source Management
- [x] **Feature Flags**: Sources can be enabled/disabled via `sources_config` in `ScraperEngine`.
- [x] **Backup Sources**: `Trendlyne` and `Screener` are now independent; failure in one doesn't stop the other unless critical ratios are missing.

---

### Best Practices for Production
1. **Proxy Health**: Monitor your proxy provider's failure rate. If you see high 403s in `scrape_logs`, your proxies are likely burnt.
2. **Headless Browser (Future)**: If Trendlyne or Screener move to heavy JS-only rendering (e.g. Cloudflare Turnstile), consider integrating `Playwright` into the `Fetcher`.
3. **Database Indexing**: As you hit 5,000+ companies, ensure `symbol` and `sector` columns have B-Tree indexes (implemented in `schema.sql`).
4. **Monitoring**: Watch the `scrape_logs` table daily during the first week to fine-tune `max_concurrency`.
