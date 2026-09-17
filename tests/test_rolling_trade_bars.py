from collections import deque

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from bitcoin_cycle_analyzer.short_term.pressure import completed_bars, macd_features
from bitcoin_cycle_analyzer.short_term.rolling_bars import RollingTradeBars


def test_exact_trade_window_boundaries_gaps_and_macd():
    rng = np.random.default_rng(17)
    rolling = RollingTradeBars(maxlen=137)
    reference = deque(maxlen=137)
    stamp = pd.Timestamp('2026-01-01', tz='UTC')
    for i in range(900):
        stamp += pd.Timedelta(milliseconds=int(rng.choice([0, 100, 999, 1000, 31000])))
        price = 77000 + float(rng.normal())
        quantity = float(rng.random())
        buy = quantity if i % 2 else 0.0
        row = (stamp, price, quantity, buy, quantity - buy)
        rolling.append(row)
        reference.append(row)
        if i % 37:
            continue
        raw = pd.DataFrame(reference, columns=['timestamp', 'price', 'volume', 'buy_volume', 'sell_volume']).set_index('timestamp')
        for seconds in (1, 30):
            expected = completed_bars(raw, seconds, asof=stamp)
            actual = rolling.completed(seconds, stamp)
            assert_frame_equal(actual, expected, check_freq=False, check_dtype=False, rtol=1e-12, atol=1e-12)
            assert_frame_equal(macd_features(actual.close), macd_features(expected.close), check_freq=False)
