from datetime import date
from io import BytesIO
from zipfile import ZipFile

import pandas as pd

from bitcoin_cycle_analyzer.short_term.binance_history import BinanceVisionHistory
from bitcoin_cycle_analyzer.short_term.data_lake import ParquetDataLake


def archive(text: str) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as zipped:
        zipped.writestr("BTCUSDT-aggTrades-2026-08-18.csv", text)
    return output.getvalue()


def test_official_url_and_microsecond_normalization():
    assert "spot/daily/aggTrades/BTCUSDT" in BinanceVisionHistory.url("spot", "BTCUSDT", "aggTrades", date(2026, 8, 18))
    frame = BinanceVisionHistory.parse_csv(archive("1,100,2,1,1,1755475200000000,False,True\n"), "spot", "aggTrades")
    assert frame.exchange_timestamp.iloc[0] == pd.Timestamp("2025-08-18T00:00:00Z")
    assert frame.source.iloc[0] == "BINANCE_SPOT"


def test_download_is_idempotent_and_preserves_raw_partition(tmp_path):
    class Response:
        status_code = 200
        content = archive("1,100,2,1,1,1755475200000,False,True\n")

        def raise_for_status(self):
            return None

    class Session:
        def get(self, url, timeout):
            return Response()

    downloader = BinanceVisionHistory(ParquetDataLake(tmp_path))
    first = downloader.download_day("spot", "BTCUSDT", "aggTrades", date(2025, 8, 18), session=Session())
    second = downloader.download_day("spot", "BTCUSDT", "aggTrades", date(2025, 8, 18), session=Session())
    path = tmp_path / "raw" / "binance_spot" / "BTCUSDT" / "2025" / "08" / "2025-08-18.parquet"
    assert first["rows"] == second["rows"] == 1
    assert len(pd.read_parquet(path)) == 1
