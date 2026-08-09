from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import zipfile
import pandas as pd
import requests
from ..data_contracts import MarketDataRecord


class BinanceVisionOIProvider:
    name="binance-vision-public-archive"
    template="https://data.binance.vision/data/futures/um/daily/metrics/{symbol}/{symbol}-metrics-{date}.zip"

    def __init__(self,symbol="BTCUSDT",timeout=20,workers=12): self.symbol,self.timeout,self.workers=symbol,timeout,workers

    def _day(self,date) -> list[MarketDataRecord]:
        day=pd.Timestamp(date).date().isoformat(); url=self.template.format(symbol=self.symbol,date=day)
        response=requests.get(url,timeout=self.timeout)
        if response.status_code==404: return []
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            frame=pd.read_csv(archive.open(archive.namelist()[0]))
        frame["create_time"]=pd.to_datetime(frame.create_time,utc=True)
        frame=frame.set_index("create_time").resample("1h").last().dropna(subset=["sum_open_interest_value"])
        return [MarketDataRecord("open_interest_usd",float(row.sum_open_interest_value),event,event,event+pd.Timedelta(minutes=5),
                                 self.name,f"{self.symbol}:{event.isoformat()}","HIGH","initial") for event,row in frame.iterrows()]

    def history(self,start="2020-08-01",end=None) -> list[MarketDataRecord]:
        end=pd.Timestamp.now(tz="UTC").normalize()-pd.Timedelta(days=1) if end is None else pd.Timestamp(end)
        start=pd.Timestamp(start)
        start=start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")
        end=end.tz_localize("UTC") if end.tzinfo is None else end.tz_convert("UTC")
        days=pd.date_range(start,end,freq="D"); records=[]
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures=[pool.submit(self._day,day) for day in days]
            for future in as_completed(futures): records.extend(future.result())
        return sorted(records,key=lambda record:record.event_timestamp)
