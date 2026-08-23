from types import SimpleNamespace

from bitcoin_cycle_analyzer.live.mt5_provider import MT5MarketDataProvider


class RecoveringMT5:
    TIMEFRAME_H4 = 4
    TIMEFRAME_D1 = 1

    def __init__(self):
        self.initializations = 0

    def initialize(self, **kwargs):
        self.initializations += 1
        return True

    def symbols_get(self):
        return [SimpleNamespace(name="BTCUSD", description="Bitcoin USD", visible=True)]

    def symbol_select(self, *args):
        return True

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(bid=100, ask=101, time=1_787_537_641, time_msc=1_787_537_641_000)

    def copy_rates_from_pos(self, *args):
        return [1]

    def terminal_info(self):
        return SimpleNamespace(connected=True)

    def account_info(self):
        return SimpleNamespace(login=1, server="demo")

    def version(self):
        return (500, 6090, "date")

    def shutdown(self):
        return None


def test_tick_reconnects_after_connection_is_lost():
    backend = RecoveringMT5()
    provider = MT5MarketDataProvider(backend, {"MT5_ENABLED": "true"})
    provider._reconnect_interval_seconds = 0
    assert provider.tick()["status"] == "AVAILABLE"
    provider._initialized = False
    provider.symbol = None
    assert provider.tick()["status"] == "AVAILABLE"
    assert backend.initializations == 2
