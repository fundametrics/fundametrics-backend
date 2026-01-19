"""
Centralized Rate Limiting - Multi-source adaptive limiting
=========================================================

Provides shared rate limiter instances to be used across the backend
to ensure all modules (API, Ingestion, Refresh) respect external 
rate limits collectively.
"""

from scraper.utils.rate_limiter import AdaptiveRateLimiter

# Shared limiter for Yahoo Finance
# Used for: Index prices, Stock prices, Market facts
# Configured for efficiency and fast recovery
yahoo_limiter = AdaptiveRateLimiter(
    requests_per_minute=60,
    base_delay=1.0,
    jitter_range=0.3, # Less jitter for predictability
    backoff_factor=2.0,
    recovery_factor=1.2,
    max_delay=15.0 # Never wait more than 15s for the user
)

# Shared limiter for Screener.in
# Used for: Financials, Shareholding
# More conservative than Yahoo
screener_limiter = AdaptiveRateLimiter(
    requests_per_minute=20,
    base_delay=3.0,
    jitter_range=1.0,
    backoff_factor=2.0,
    recovery_factor=1.1,
    max_delay=20.0
)

# Shared limiter for Trendlyne
# Used for: Profiles, Management
trendlyne_limiter = AdaptiveRateLimiter(
    requests_per_minute=20,
    base_delay=3.0,
    jitter_range=1.0,
    backoff_factor=2.0,
    recovery_factor=1.1,
    max_delay=20.0
)
