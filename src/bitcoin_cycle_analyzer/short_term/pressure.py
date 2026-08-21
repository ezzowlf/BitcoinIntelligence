from __future__ import annotations

from dataclasses import dataclass
from math import tanh

import numpy as np
import pandas as pd

BAR_SECONDS = (1, 5, 10, 30, 60, 180, 300, 900)
MACD_SECONDS = (10, 30, 60, 180, 300, 900)
MOMENTUM_SECONDS = (1, 2, 5, 10, 30, 60, 90, 180, 300)


@dataclass(frozen=True)
class MomentumPressureState:
    """Latest causal momentum snapshot; absent evidence stays unavailable."""

    timestamp: pd.Timestamp
    price: float
    returns: dict[int, float | None]
    velocity: dict[int, float | None]
    acceleration: dict[int, float | None]
    jerk: dict[int, float | None]
    realized_volatility: float | None
    range_expansion: float | None
    price_response_efficiency: float | None
    flow_pressure: float | None
    flow_acceleration: float | None
    cvd_velocity: float | None
    l2_imbalance: float | None
    l2_status: str
    derivatives_status: str
    cross_exchange_status: str
    execution: str = "DISABLED"


def _latest(frame: pd.Series, periods: int) -> float | None:
    if len(frame) <= periods or pd.isna(frame.iloc[-1]) or pd.isna(frame.iloc[-periods - 1]):
        return None
    return float(frame.iloc[-1] / frame.iloc[-periods - 1] - 1.0)


def momentum_pressure_state(
    bars: pd.DataFrame,
    *,
    l2_imbalance: float | None = None,
    price_response_efficiency: float | None = None,
    derivatives_available: bool = False,
    cross_exchange_available: bool = False,
) -> MomentumPressureState:
    """Build a point-in-time state from completed, right-labelled bars only."""
    required = {"close", "high", "low", "volume", "buy_volume", "sell_volume", "trades"}
    missing = required.difference(bars.columns)
    if missing or not isinstance(bars.index, pd.DatetimeIndex) or bars.index.tz is None:
        raise ValueError(f"completed bars missing required causal fields: {sorted(missing)}")
    if bars.empty:
        raise ValueError("cannot create momentum state from empty bars")
    close = bars["close"].astype(float)
    returns = {period: _latest(close, period) for period in MOMENTUM_SECONDS}
    velocity = {period: _latest(close.pct_change(), period) for period in MOMENTUM_SECONDS}
    acceleration = {period: _latest(close.pct_change().diff(), period) for period in MOMENTUM_SECONDS}
    jerk = {period: _latest(close.pct_change().diff().diff(), period) for period in MOMENTUM_SECONDS}
    flow = flow_pressure(bars)
    width = (bars["high"] - bars["low"]).astype(float)
    vol = close.pct_change().rolling(60, min_periods=10).std().iloc[-1]
    expansion = width.iloc[-1] / width.rolling(60, min_periods=10).median().iloc[-1] if width.rolling(60, min_periods=10).median().iloc[-1] else None
    return MomentumPressureState(
        timestamp=bars.index[-1], price=float(close.iloc[-1]), returns=returns, velocity=velocity,
        acceleration=acceleration, jerk=jerk, realized_volatility=None if pd.isna(vol) else float(vol),
        range_expansion=None if expansion is None or pd.isna(expansion) else float(expansion),
        price_response_efficiency=price_response_efficiency,
        flow_pressure=None if pd.isna(flow.pressure.iloc[-1]) else float(flow.pressure.iloc[-1]),
        flow_acceleration=None if pd.isna(flow.trade_rate_acceleration.iloc[-1]) else float(flow.trade_rate_acceleration.iloc[-1]),
        cvd_velocity=None if pd.isna(flow.cvd_velocity.iloc[-1]) else float(flow.cvd_velocity.iloc[-1]),
        l2_imbalance=l2_imbalance, l2_status="AVAILABLE" if l2_imbalance is not None else "UNAVAILABLE",
        derivatives_status="AVAILABLE" if derivatives_available else "UNAVAILABLE",
        cross_exchange_status="AVAILABLE" if cross_exchange_available else "UNAVAILABLE",
    )


def completed_bars(frame: pd.DataFrame, seconds: int, *, asof: pd.Timestamp | None = None) -> pd.DataFrame:
    """Build right-labelled bars; a timestamp is available only after its interval closes."""
    if seconds not in BAR_SECONDS:
        raise ValueError(f"unsupported bar size: {seconds}")
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise ValueError("frame requires a timezone-aware DatetimeIndex")
    rule = f"{seconds}s"
    bars = frame.resample(rule, label="right", closed="left").agg(
        open=("price", "first"), high=("price", "max"), low=("price", "min"), close=("price", "last"),
        volume=("volume", "sum"), buy_volume=("buy_volume", "sum"), sell_volume=("sell_volume", "sum"),
        trades=("price", "count"),
    ).dropna(subset=["open", "high", "low", "close"])
    if asof is not None:
        asof = pd.Timestamp(asof)
        if asof.tzinfo is None:
            raise ValueError("asof must be timezone-aware")
        bars = bars.loc[bars.index <= asof]
    width = (bars.high - bars.low).replace(0, np.nan)
    bars["body_ratio"] = (bars.close - bars.open) / width
    bars["upper_wick_ratio"] = (bars.high - bars[["open", "close"]].max(axis=1)) / width
    bars["lower_wick_ratio"] = (bars[["open", "close"]].min(axis=1) - bars.low) / width
    bars["close_location"] = (bars.close - bars.low) / width
    bars["range_expansion"] = width / width.rolling(20, min_periods=5).median()
    return bars


def macd_features(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    if not 1 <= fast < slow or signal < 1:
        raise ValueError("MACD requires 1 <= fast < slow and signal >= 1")
    line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    signal_line = line.ewm(span=signal, adjust=False).mean()
    histogram = line - signal_line
    result = pd.DataFrame({"macd": line, "signal": signal_line, "histogram": histogram})
    result["macd_slope"] = line.diff()
    result["macd_acceleration"] = result.macd_slope.diff()
    result["histogram_slope"] = histogram.diff()
    result["histogram_acceleration"] = result.histogram_slope.diff()
    result["distance_signal"] = line - signal_line
    result["distance_zero"] = line
    cross = np.sign(result.distance_signal).diff().fillna(0)
    result["cross_direction"] = np.sign(cross)
    groups = result.cross_direction.ne(0).cumsum()
    result["cross_age"] = result.groupby(groups).cumcount()
    return result


def robust_score(values: pd.Series, window: int = 300) -> pd.Series:
    median = values.rolling(window, min_periods=max(10, window // 10)).median()
    mad = (values - median).abs().rolling(window, min_periods=max(10, window // 10)).median()
    z = (values - median) / (1.4826 * mad).replace(0, np.nan)
    return z.clip(-5, 5).fillna(0).map(lambda value: 100 * tanh(value / 2))


def price_pressure(bars: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(index=bars.index)
    result["return"] = bars.close.pct_change()
    result["velocity"] = result["return"]
    result["acceleration"] = result.velocity.diff()
    result["normalized_velocity"] = robust_score(result.velocity)
    result["normalized_acceleration"] = robust_score(result.acceleration)
    result["pressure"] = (0.6 * result.normalized_velocity + 0.4 * result.normalized_acceleration).clip(-100, 100)
    result["pressure_velocity"] = result.pressure.diff()
    result["pressure_acceleration"] = result.pressure_velocity.diff()
    return result


def flow_pressure(bars: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(index=bars.index)
    total = (bars.buy_volume + bars.sell_volume).replace(0, np.nan)
    result["delta"] = bars.buy_volume - bars.sell_volume
    result["normalized_delta"] = (result.delta / total).fillna(0)
    result["cvd"] = result.delta.cumsum()
    result["cvd_velocity"] = result.cvd.diff()
    result["cvd_acceleration"] = result.cvd_velocity.diff()
    result["trade_rate"] = bars.trades
    result["trade_rate_acceleration"] = bars.trades.diff().diff()
    result["pressure"] = (100 * result.normalized_delta).clip(-100, 100)
    return result


def efficiency_and_absorption(price: pd.Series, flow: pd.Series) -> pd.DataFrame:
    price_move = price.pct_change()
    normalized_flow = robust_score(flow) / 100
    efficiency = price_move / normalized_flow.replace(0, np.nan)
    flow_extreme = normalized_flow.abs() >= 0.5
    inefficient = efficiency.abs() <= efficiency.abs().rolling(300, min_periods=30).quantile(0.25)
    absorbed = flow_extreme & inefficient
    state = np.where(absorbed & (normalized_flow > 0), "BUY_PRESSURE_ABSORBED",
                     np.where(absorbed, "SELL_PRESSURE_ABSORBED",
                              np.where(normalized_flow >= 0, "BUY_PRESSURE_EFFECTIVE", "SELL_PRESSURE_EFFECTIVE")))
    return pd.DataFrame({"price_change": price_move, "normalized_flow": normalized_flow,
                         "efficiency": efficiency.replace([np.inf, -np.inf], np.nan),
                         "absorption_score": np.where(absorbed, normalized_flow.abs() * 100, 0), "absorption_state": state}, index=price.index)


def mean_state(bars: pd.DataFrame, exhaustion: pd.Series, confirmation: pd.Series) -> pd.DataFrame:
    close = bars.close
    rolling_mean = close.rolling(60, min_periods=20).mean()
    rolling_std = close.rolling(60, min_periods=20).std().replace(0, np.nan)
    ema = close.ewm(span=60, adjust=False).mean()
    typical = (bars.high + bars.low + bars.close) / 3
    vwap = (typical * bars.volume).rolling(60, min_periods=20).sum() / bars.volume.rolling(60, min_periods=20).sum().replace(0, np.nan)
    zscore = (close - rolling_mean) / rolling_std
    displacement = robust_score(zscore.abs()).clip(0, 100)
    extended = displacement >= 70
    confirmed = extended & (exhaustion >= 60) & confirmation.astype(bool)
    state = np.where(confirmed, "REVERSION_CONFIRMED", np.where(extended & (exhaustion >= 60), "REVERSION_WATCH",
             np.where(extended, "EXTENDED_BUT_TRENDING", "NOT_EXTENDED")))
    return pd.DataFrame({"rolling_mean": rolling_mean, "ema": ema, "vwap": vwap, "zscore": zscore,
                         "mean_displacement": displacement, "reversion_state": state}, index=bars.index)


@dataclass(frozen=True)
class PressureSnapshot:
    price_pressure: float
    macd_pressure: float
    spot_pressure: float
    futures_pressure: float
    directional_pressure: float
    origin: str
    execution: str = "DISABLED"


class DirectionalPressureEngine:
    """Transparent source snapshot; combination weights are fixed baselines, not fitted parameters."""

    def snapshot(self, price: float, macd: float, spot: float, futures: float) -> PressureSnapshot:
        values = np.clip([price, macd, spot, futures], -100, 100)
        combined = float(np.mean(values))
        source = {"VANTAGE_LED": abs(values[0]), "SPOT_LED": abs(values[2]), "FUTURES_LED": abs(values[3])}
        ordered = sorted(source.items(), key=lambda item: item[1], reverse=True)
        same_direction = np.sign(values[2]) == np.sign(values[3]) and abs(values[2]) >= 20 and abs(values[3]) >= 20
        origin = "SPOT_FUTURES_CONFIRMED" if same_direction else (ordered[0][0] if ordered[0][1] >= 20 else "UNCLEAR")
        return PressureSnapshot(*map(float, values), combined, origin)
