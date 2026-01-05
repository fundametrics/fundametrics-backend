from datetime import datetime, timedelta, timezone

from models.boost import PriorityBoost
from models.symbol import MAX_TOTAL_BOOST_WEIGHT, SymbolRecord, list_active_symbols_by_priority
from scraper.boosts.apply import apply_priority_boost, prune_expired_boosts


def make_record(**overrides) -> SymbolRecord:
    payload = {
        "symbol": "TEST",
        "exchange": "NSE",
        "priority": 3,
        "status": "active",
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "metadata": {},
        "boosts": [],
    }
    payload.update(overrides)
    return SymbolRecord.from_dict(payload)


def test_boost_expiry_pruning():
    record = make_record()
    expired_boost = PriorityBoost(
        kind="user_interest",
        weight=1,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        source="test",
    )
    record.boosts.append(expired_boost)
    changed = record.prune_expired_boosts(now=datetime.now(timezone.utc))
    assert changed
    assert record.boosts == []


def test_effective_priority_with_stack_cap():
    now = datetime.now(timezone.utc)
    record = make_record(priority=2)
    for idx in range(5):
        record.add_boost(
            PriorityBoost(
                kind=f"kind{idx}",
                weight=1,
                expires_at=now + timedelta(hours=idx + 1),
                source="test",
            ),
            now=now,
        )
    assert record.active_boost_weight(now=now) == MAX_TOTAL_BOOST_WEIGHT
    assert record.effective_priority(now=now) == record.priority + MAX_TOTAL_BOOST_WEIGHT


def test_apply_priority_boost_integration(tmp_path):
    registry_path = tmp_path / "registry.json"
    record = make_record()
    registry_path.write_text('[{"symbol": "TEST", "exchange": "NSE", "priority": 3}]', encoding="utf-8")

    updated_record, boost = apply_priority_boost(
        "TEST",
        kind="user_interest",
        weight=2,
        ttl_hours=6,
        source="manual",
        registry_path=registry_path,
    )

    assert boost.weight == 2
    assert updated_record.symbol == "TEST"
    assert updated_record.active_boost_weight() >= 1

    registry = {"TEST": updated_record}
    assert not prune_expired_boosts(registry)


def test_effective_priority_label_and_sorting():
    now = datetime.now(timezone.utc)
    high = make_record(symbol="HIGH", priority=5)
    medium = make_record(symbol="MED", priority=3)
    low = make_record(symbol="LOW", priority=2)

    medium.add_boost(
        PriorityBoost(
            kind="user_interest",
            weight=2,
            expires_at=now + timedelta(hours=6),
            source="test",
        ),
        now=now,
    )

    records = {rec.symbol: rec for rec in [high, medium, low]}
    ordered = list_active_symbols_by_priority(records)

    assert ordered[0].symbol == "MED"  # boosted above base HIGH (same base but weight)
    assert medium.effective_priority_label(now=now) == "HIGH+2"
