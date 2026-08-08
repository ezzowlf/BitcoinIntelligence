from __future__ import annotations
import numpy as np
import pandas as pd


def performance(equity: pd.Series, initial: float = 1.0) -> dict:
    equity = equity.dropna()
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1 / 365.25)
    drawdown = equity / equity.cummax() - 1
    return {"total_return": float(equity.iloc[-1] / initial - 1), "cagr": float((equity.iloc[-1] / initial) ** (1 / years) - 1), "max_drawdown": float(drawdown.min())}


def run_backtest(frame: pd.DataFrame, scores: pd.Series, threshold: float = 75, dca_days: int = 30, initial_cash: float = 10_000) -> dict:
    """Signals execute on the next bar open, preventing same-bar hindsight."""
    data = frame.loc[scores.index].copy()
    signal = (scores >= threshold) & (scores.shift(1, fill_value=0) < threshold)
    execution = signal.shift(1, fill_value=False)
    units, cash, entries = 0.0, initial_cash, []
    equity = []
    for i, (date, row) in enumerate(data.iterrows()):
        if execution.loc[date] and cash > 0:
            allocation = min(cash, initial_cash * .1)
            units += allocation / row.open
            cash -= allocation
            entries.append((date, float(row.open)))
        equity.append(cash + units * row.close)
    strategy_equity = pd.Series(equity, index=data.index)
    buy_hold = initial_cash * data.close / data.open.iloc[0]
    contributions = pd.Series(0.0, index=data.index)
    contributions.iloc[::max(1, dca_days)] = initial_cash / max(1, len(data.iloc[::max(1, dca_days)]))
    dca_units = (contributions / data.open).cumsum()
    dca_cash = initial_cash - contributions.cumsum()
    dca_equity = dca_cash + dca_units * data.close
    return {"strategy": performance(strategy_equity, initial_cash), "buy_hold": performance(buy_hold, initial_cash), "dca": performance(dca_equity, initial_cash), "signals": len(entries), "average_entry": float(np.mean([p for _, p in entries])) if entries else None, "entries": entries, "equity": strategy_equity}

