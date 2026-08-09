from __future__ import annotations
import pandas as pd


def availability_matrix(coverage: pd.DataFrame, years=(2012,2016,2020,2024,2026)) -> pd.DataFrame:
    rows={}
    for row in coverage.itertuples():
        start,end=pd.Timestamp(row.min_time),pd.Timestamp(row.max_time)
        rows.setdefault(row.metric,{})
        for year in years:
            rows[row.metric][year] = "YES" if start.year <= year <= end.year else "NO"
    return pd.DataFrame.from_dict(rows,orient="index",columns=years).fillna("NO")


def coverage_windows(coverage: pd.DataFrame) -> dict:
    return {row.metric:{"provider":row.provider,"from":row.min_time,"to":row.max_time,"rows":int(row.rows)} for row in coverage.itertuples()}
