from __future__ import annotations
import pandas as pd


def ablation_report(full_scores: pd.Series, factor_scores: dict[str, pd.Series], forward_returns: pd.Series) -> dict:
    index = full_scores.index.intersection(forward_returns.index)
    full_rank = full_scores.loc[index].rank(pct=True)
    result = {"full": {"rank_correlation": float(full_rank.corr(forward_returns.loc[index].rank(pct=True)))}}
    for name, factor in factor_scores.items():
        aligned = factor.reindex(index)
        without = full_scores.loc[index] - aligned.fillna(0)
        result[f"without_{name}"] = {"rank_correlation": float(without.rank(pct=True).corr(forward_returns.loc[index].rank(pct=True))), "observations": int(without.notna().sum())}
    return result
