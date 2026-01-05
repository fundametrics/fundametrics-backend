"""Moneycontrol parser is intentionally disabled for compliance."""


class MoneycontrolParser:  # pragma: no cover - should never be instantiated
    """Placeholder parser that prevents accidental usage."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: D401
        raise RuntimeError("Moneycontrol parser disabled by design")
