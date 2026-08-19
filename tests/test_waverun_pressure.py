import numpy as np
import pandas as pd

from bitcoin_cycle_analyzer.short_term.pressure import (
    DirectionalPressureEngine,
    completed_bars,
    efficiency_and_absorption,
    macd_features,
    mean_state,
    price_pressure,
)


def source_frame(periods=1800):
    index = pd.date_range("2026-01-01", periods=periods, freq="1s", tz="UTC")
    price = pd.Series(100 + np.linspace(0, 2, periods) + np.sin(np.arange(periods) / 20), index=index)
    return pd.DataFrame({"price": price, "volume": 1.0, "buy_volume": 0.6, "sell_volume": 0.4})


def test_completed_bars_are_causal_and_right_labelled():
    bars = completed_bars(source_frame(12), 5, asof=pd.Timestamp("2026-01-01T00:00:05Z"))
    assert list(bars.index) == [pd.Timestamp("2026-01-01T00:00:05Z")]
    assert bars.iloc[0].open == 100


def test_macd_slope_acceleration_and_cross_age():
    result = macd_features(source_frame().price)
    assert {"macd", "signal", "histogram", "histogram_slope", "histogram_acceleration", "cross_age"} <= set(result)
    assert result.cross_age.min() == 0


def test_pressure_is_bounded_and_has_derivatives():
    result = price_pressure(completed_bars(source_frame(), 10))
    assert result.pressure.between(-100, 100).all()
    assert {"pressure_velocity", "pressure_acceleration"} <= set(result)


def test_absorption_handles_zero_flow():
    index = pd.date_range("2026-01-01", periods=400, freq="1s", tz="UTC")
    result = efficiency_and_absorption(pd.Series(100.0, index=index), pd.Series(0.0, index=index))
    assert not np.isinf(result.efficiency.fillna(0)).any()


def test_reversion_needs_displacement_exhaustion_and_confirmation():
    bars = completed_bars(source_frame(4000), 10)
    exhaustion = pd.Series(100.0, index=bars.index)
    unconfirmed = mean_state(bars, exhaustion, pd.Series(False, index=bars.index))
    confirmed = mean_state(bars, exhaustion, pd.Series(True, index=bars.index))
    assert not (unconfirmed.reversion_state == "REVERSION_CONFIRMED").any()
    assert set(confirmed.reversion_state) <= {"NOT_EXTENDED", "EXTENDED_BUT_TRENDING", "REVERSION_WATCH", "REVERSION_CONFIRMED"}


def test_directional_engine_preserves_execution_gate_and_origin():
    snap = DirectionalPressureEngine().snapshot(30, 40, 70, 80)
    assert snap.directional_pressure == 55
    assert snap.origin == "SPOT_FUTURES_CONFIRMED"
    assert snap.execution == "DISABLED"
