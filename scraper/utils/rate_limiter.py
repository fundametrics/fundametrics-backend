"""
Rate Limiter - Token Bucket Algorithm
======================================

Production-grade rate limiting for web scraping with:
- Token bucket algorithm
- Configurable rates
- Random jitter to mimic human behavior
- Thread-safe implementation
"""

import asyncio
import random
import time
from datetime import datetime, timedelta
from typing import Optional
from scraper.utils.logger import get_logger

log = get_logger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter with jitter
    
    Implements a token bucket algorithm to control request rate:
    - Tokens are added at a constant rate
    - Each request consumes one token
    - If no tokens available, request waits
    - Random jitter added to mimic human behavior
    
    Example:
        >>> limiter = RateLimiter(requests_per_minute=10, base_delay=6.0)
        >>> await limiter.acquire()  # Wait if necessary, then proceed
    """
    
    def __init__(
        self,
        requests_per_minute: int = 10,
        base_delay: float = 6.0,
        jitter_range: float = 2.0,
        burst_size: Optional[int] = None
    ):
        """
        Initialize rate limiter
        
        Args:
            requests_per_minute: Maximum requests allowed per minute
            base_delay: Base delay between requests in seconds
            jitter_range: Random jitter range (±seconds) to add to base delay
            burst_size: Maximum burst size (default: requests_per_minute)
        """
        self.requests_per_minute = requests_per_minute
        self.base_delay = base_delay
        self.jitter_range = jitter_range
        self.burst_size = burst_size or requests_per_minute
        
        # Token bucket state
        self.tokens = float(self.burst_size)
        self.max_tokens = float(self.burst_size)
        self.refill_rate = requests_per_minute / 60.0  # tokens per second
        self.last_refill = time.time()
        
        # Last request time for delay calculation
        self.last_request = None
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        log.info(
            f"RateLimiter initialized: {requests_per_minute} req/min, "
            f"{base_delay}s base delay, ±{jitter_range}s jitter"
        )
    
    def _refill_tokens(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.max_tokens, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def _calculate_delay(self) -> float:
        """
        Calculate delay with random jitter
        
        Returns:
            Delay in seconds
        """
        # Base delay with random jitter
        jitter = random.uniform(-self.jitter_range, self.jitter_range)
        delay = max(0, self.base_delay + jitter)
        
        return delay
    
    async def acquire(self):
        """
        Acquire permission to make a request
        
        This method will:
        1. Wait for minimum delay since last request (with jitter)
        2. Wait for token availability
        3. Consume one token
        
        Example:
            >>> await limiter.acquire()
            >>> # Now safe to make request
        """
        async with self._lock:
            # Refill tokens
            self._refill_tokens()
            
            # Wait for minimum delay since last request
            if self.last_request is not None:
                elapsed = time.time() - self.last_request
                delay = self._calculate_delay()
                
                if elapsed < delay:
                    wait_time = delay - elapsed
                    log.debug(f"Waiting {wait_time:.2f}s for rate limit")
                    await asyncio.sleep(wait_time)
            
            # Wait for token availability
            while self.tokens < 1.0:
                # Calculate how long to wait for next token
                wait_time = (1.0 - self.tokens) / self.refill_rate
                log.debug(f"No tokens available, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                self._refill_tokens()
            
            # Consume token
            self.tokens -= 1.0
            self.last_request = time.time()
            
            log.debug(f"Token acquired, {self.tokens:.2f} tokens remaining")
    
    def get_stats(self) -> dict:
        """
        Get rate limiter statistics
        
        Returns:
            Dictionary with current state
        """
        self._refill_tokens()
        
        return {
            'tokens_available': round(self.tokens, 2),
            'max_tokens': self.max_tokens,
            'requests_per_minute': self.requests_per_minute,
            'base_delay': self.base_delay,
            'jitter_range': self.jitter_range,
            'last_request': self.last_request
        }


class AdaptiveRateLimiter(RateLimiter):
    """
    Adaptive rate limiter that adjusts based on server responses
    
    Automatically slows down on 429 (Too Many Requests) errors
    and gradually speeds up when requests succeed.
    
    Example:
        >>> limiter = AdaptiveRateLimiter(requests_per_minute=10)
        >>> await limiter.acquire()
        >>> # After 429 error:
        >>> limiter.on_rate_limit_error()
    """
    
    def __init__(
        self,
        requests_per_minute: int = 10,
        base_delay: float = 6.0,
        jitter_range: float = 2.0,
        burst_size: Optional[int] = None,
        backoff_factor: float = 2.0,
        recovery_factor: float = 1.1
    ):
        """
        Initialize adaptive rate limiter
        
        Args:
            requests_per_minute: Initial maximum requests per minute
            base_delay: Initial base delay
            jitter_range: Random jitter range
            burst_size: Maximum burst size
            backoff_factor: Multiply delay by this on rate limit (default: 2.0)
            recovery_factor: Divide delay by this on success (default: 1.1)
        """
        super().__init__(requests_per_minute, base_delay, jitter_range, burst_size)
        
        self.initial_delay = base_delay
        self.backoff_factor = backoff_factor
        self.recovery_factor = recovery_factor
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        
        log.info(
            f"AdaptiveRateLimiter initialized with backoff={backoff_factor}, "
            f"recovery={recovery_factor}"
        )
    
    def on_rate_limit_error(self):
        """
        Call this when receiving a 429 (Too Many Requests) error
        
        Increases delay to back off from the server
        """
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        
        # Increase delay
        old_delay = self.base_delay
        self.base_delay *= self.backoff_factor
        
        # Cap at 60 seconds
        self.base_delay = min(60.0, self.base_delay)
        
        log.warning(
            f"Rate limit hit! Increasing delay from {old_delay:.2f}s to "
            f"{self.base_delay:.2f}s (failure #{self.consecutive_failures})"
        )
    
    def on_success(self):
        """
        Call this when a request succeeds
        
        Gradually reduces delay to recover to normal rate
        """
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        
        # Only recover after multiple successes
        if self.consecutive_successes >= 5 and self.base_delay > self.initial_delay:
            old_delay = self.base_delay
            self.base_delay /= self.recovery_factor
            
            # Don't go below initial delay
            self.base_delay = max(self.initial_delay, self.base_delay)
            
            log.info(
                f"Recovering rate limit: {old_delay:.2f}s → {self.base_delay:.2f}s "
                f"(success #{self.consecutive_successes})"
            )
            
            # Reset counter
            self.consecutive_successes = 0
    
    def reset(self):
        """Reset to initial delay"""
        self.base_delay = self.initial_delay
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        log.info(f"Rate limiter reset to initial delay: {self.initial_delay}s")


# Synchronous version for non-async code
class SyncRateLimiter:
    """
    Synchronous rate limiter (blocking)
    
    Use this for synchronous code that doesn't use asyncio.
    For async code, use RateLimiter instead.
    
    Example:
        >>> limiter = SyncRateLimiter(requests_per_minute=10)
        >>> limiter.acquire()  # Blocks until ready
    """
    
    def __init__(
        self,
        requests_per_minute: int = 10,
        base_delay: float = 6.0,
        jitter_range: float = 2.0
    ):
        self.requests_per_minute = requests_per_minute
        self.base_delay = base_delay
        self.jitter_range = jitter_range
        self.last_request = None
        
        log.info(
            f"SyncRateLimiter initialized: {requests_per_minute} req/min, "
            f"{base_delay}s base delay"
        )
    
    def acquire(self):
        """Acquire permission to make a request (blocking)"""
        if self.last_request is not None:
            elapsed = time.time() - self.last_request
            jitter = random.uniform(-self.jitter_range, self.jitter_range)
            delay = max(0, self.base_delay + jitter)
            
            if elapsed < delay:
                wait_time = delay - elapsed
                log.debug(f"Waiting {wait_time:.2f}s for rate limit")
                time.sleep(wait_time)
        
        self.last_request = time.time()


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    async def test_rate_limiter():
        """Test rate limiter functionality"""
        print("Testing RateLimiter...")
        limiter = RateLimiter(requests_per_minute=10, base_delay=2.0, jitter_range=0.5)
        
        # Make 5 requests
        for i in range(5):
            start = time.time()
            await limiter.acquire()
            elapsed = time.time() - start
            print(f"Request {i+1}: waited {elapsed:.2f}s")
            print(f"Stats: {limiter.get_stats()}")
        
        print("\nTesting AdaptiveRateLimiter...")
        adaptive = AdaptiveRateLimiter(requests_per_minute=10, base_delay=2.0)
        
        # Simulate rate limit error
        adaptive.on_rate_limit_error()
        print(f"After rate limit error, delay: {adaptive.base_delay:.2f}s")
        
        # Simulate successes
        for _ in range(10):
            adaptive.on_success()
        print(f"After 10 successes, delay: {adaptive.base_delay:.2f}s")
    
    # Run test
    asyncio.run(test_rate_limiter())
