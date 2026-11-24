"""Which SIP code a symbol's official close is read under (shadow/sources.py)."""
import pytest

from quantt.broker.alpaca import UnmappedExchange
from shadow import sources

SIP = {"N": "New York Stock Exchange", "P": "NYSE Arca", "F": "Texas Stock Exchange",
       "Q": "NASDAQ Global Select", "Z": "Cboe BZX"}


class FakeClient:
    def __init__(self, exchange):
        self.exchange = exchange

    def asset(self, symbol):
        return {"symbol": symbol, "exchange": self.exchange}


def code(symbol, exchange):
    d = sources.ReadOnlyData.__new__(sources.ReadOnlyData)
    d._ReadOnlyData__client, d._ReadOnlyData__exchanges = FakeClient(exchange), dict(SIP)
    return d._primary_code(symbol)


def test_a_txse_asset_is_read_under_the_texas_code():
    """The VM's 2026-11-13 07:20 run stopped here: Alpaca's record for ET read 'TXSE' on
    that one read and the map had no entry. FAILS on 935bc31 for a symbol outside
    SYMBOL_PRIMARY_SIP_NAME (CFR), which raised UnmappedExchange."""
    assert code("CFR", "TXSE") == "F"


@pytest.mark.parametrize("exchange", ["NYSE", "TXSE"])
def test_the_four_measured_units_read_texas_whichever_exchange_the_record_names(exchange):
    for s in ("ET", "SUN", "SUNC", "USAC"):
        assert code(s, exchange) == "F"


def test_arca_and_an_unmeasured_exchange():
    assert code("SPY", "ARCA") == "P"
    with pytest.raises(UnmappedExchange, match="BATS"):
        code("XYZ", "BATS")
