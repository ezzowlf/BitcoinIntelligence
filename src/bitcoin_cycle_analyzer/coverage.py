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


def factor_availability(coverage: pd.DataFrame, now=None) -> pd.DataFrame:
    now=pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    rows=[]
    for row in coverage.itertuples():
        start=pd.Timestamp(row.min_time); end=pd.Timestamp(row.max_time)
        start=start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")
        end=end.tz_localize("UTC") if end.tzinfo is None else end.tz_convert("UTC")
        age=(now-end).total_seconds()/86400
        rows.append({"factor":row.metric,"provider":row.provider,"start":start,"end":end,"rows":int(row.rows),
                     "age_days":round(age,2),"freshness":"LIVE" if age<=1 else "DELAYED" if age<=3 else "STALE",
                     "point_in_time":"YES","status":"AVAILABLE"})
    return pd.DataFrame(rows)
