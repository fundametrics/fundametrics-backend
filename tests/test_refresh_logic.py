from datetime import datetime, timedelta, timezone

from models.symbol import SymbolRecord
from scraper.refresh.budget import RefreshBudget
from scraper.refresh.cooldown import is_in_cooldown, next_allowed_time
from scraper.refresh.decision import RefreshState, evaluate_refresh
from scraper.refresh.policy import get_priority_interval


def make_symbol(**overrides):
    data = {
        "symbol": "TEST",
        "exchange": "NSE",
        "company_name": "Test Ltd",
        "priority": 3,
        "status": "active",
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "last_refreshed": (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat(),
        "last_attempt": None,
        "failure_count": 0,
    }
    data.update(overrides)
    return SymbolRecord.from_dict(data)


def test_priority_interval_default():
    assert get_priority_interval(99) == get_priority_interval(2)


def test_cooldown_backoff_caps():
    last_attempt = datetime.now(timezone.utc).timestamp()
    next_time = next_allowed_time(10, last_attempt)
    assert next_time - last_attempt <= 24 * 60 * 60


def test_evaluate_refresh_runs_when_stale():
    symbol = make_symbol(priority=3, last_refreshed=(datetime.now(timezone.utc) - timedelta(hours=8)).isoformat())
    state = RefreshState(failures=0, last_attempt=None)
    result = evaluate_refresh(symbol, state, now=datetime.now(timezone.utc))
    assert result.should_run
    assert "stale" in result.reason


def test_evaluate_refresh_skips_during_cooldown():
    now = datetime.now(timezone.utc)
    last_attempt_ts = (now - timedelta(minutes=1)).isoformat()
    symbol = make_symbol(last_refreshed=(now - timedelta(hours=8)).isoformat())
    state = RefreshState(failures=2, last_attempt=last_attempt_ts)
    result = evaluate_refresh(symbol, state, now=now)
    assert not result.should_run
    assert "cooldown" in result.reason
    last_attempt_float = state.last_attempt_timestamp()
    assert is_in_cooldown(failures=state.failures, last_attempt_ts=last_attempt_float, now_ts=now.timestamp())


def test_evaluate_refresh_skips_when_fresh():
    now = datetime.now(timezone.utc)
    symbol = make_symbol(priority=4, last_refreshed=(now - timedelta(minutes=10)).isoformat())
    state = RefreshState()
    result = evaluate_refresh(symbol, state, now=now)
    assert not result.should_run
    assert "fresh" in result.reason


def test_refresh_budget_consumption():
    budget = RefreshBudget(2)
    assert budget.allow()
    budget.consume()
    assert budget.allow()
    budget.consume()
    assert not budget.allow()
