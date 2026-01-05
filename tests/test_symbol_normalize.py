from scraper.symbols.normalize import build_symbol_key, normalise_exchange, normalise_symbol


def test_normalise_symbol_strips_suffix():
    assert normalise_symbol("RELIANCE-EQ") == "RELIANCE"
    assert normalise_symbol("   tcs.ns   ") == "TCS"


def test_normalise_symbol_rejects_empty():
    try:
        normalise_symbol("@@")
    except ValueError:
        assert True
    else:
        assert False, "Expected ValueError"


def test_normalise_exchange_aliases():
    assert normalise_exchange("nsei") == "NSE"
    assert normalise_exchange("Bombay") == "BSE"


def test_build_symbol_key():
    assert build_symbol_key("tcs", "nse") == "TCS:NSE"
