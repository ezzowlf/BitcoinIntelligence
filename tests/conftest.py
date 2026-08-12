import numpy as np
import pandas as pd
import pytest

@pytest.fixture
def ohlcv():
    rng = np.random.default_rng(42)
    index = pd.date_range("2014-01-01", periods=1800, freq="D", tz="UTC")
    close = 500 * np.exp(np.cumsum(rng.normal(.001, .025, len(index))))
    spread = close * rng.uniform(.005, .03, len(index))
    return pd.DataFrame({"open": close * (1 + rng.normal(0, .005, len(index))), "high": close + spread, "low": close - spread, "close": close, "volume": rng.lognormal(10, .5, len(index))}, index=index)
