"""Incremental bars over the exact last-N-trades window used by the collector."""
from collections import OrderedDict, deque
import math

import pandas as pd

from .pressure import decorate_bars


class RollingTradeBars:
    def __init__(self, maxlen=200_000, intervals=(1, 30)):
        self.maxlen = maxlen
        self.rows = deque()
        self.buckets = {seconds: OrderedDict() for seconds in intervals}
        self._cache = {seconds: {} for seconds in intervals}

    def append(self, row):
        stamp = pd.Timestamp(row[0])
        if stamp.tzinfo is None:
            raise ValueError('trade timestamp must be timezone-aware')
        if self.rows and stamp < pd.Timestamp(self.rows[-1][0]):
            raise ValueError('out-of-order trade')
        self.rows.append(row)
        for seconds, buckets in self.buckets.items():
            key = stamp.value // (seconds * 1_000_000_000)
            buckets.setdefault(key, deque()).append(row)
        if len(self.rows) > self.maxlen:
            old = self.rows.popleft()
            for seconds, buckets in self.buckets.items():
                key = pd.Timestamp(old[0]).value // (seconds * 1_000_000_000)
                buckets[key].popleft()
                if not buckets[key]:
                    del buckets[key]
                    # Evict the matching cache entry here (O(1), on the single
                    # bucket that just left the window) instead of scanning the
                    # whole cache from completed() on every call - and instead
                    # of never pruning it, which would leak memory forever in a
                    # long-running collector.
                    self._cache[seconds].pop(key, None)

    def completed(self, seconds, asof, *, limit=None):
        # Only the trailing window the caller actually needs (2 one-second /
        # 35 thirty-second bars) is walked, newest-first, stopping as soon as
        # `limit` valid bars are found. Iterating every retained bucket on
        # every tick - even with per-bucket OHLC caching - was itself O(total
        # buckets in the window) and made the single causal spot consumer
        # fall behind under live load; this bounds the call to O(limit).
        buckets = self.buckets[seconds]
        bucket_cache = self._cache[seconds]
        values, labels = [], []
        for key in reversed(buckets):
            label = pd.Timestamp((key + 1) * seconds * 1_000_000_000, tz='UTC')
            if label > asof:
                continue
            rows = buckets[key]
            signature = (id(rows[0]), id(rows[-1]), len(rows))
            saved = bucket_cache.get(key)
            if saved is None or saved[0] != signature:
                prices = [r[1] for r in rows]
                value = [prices[0], max(prices), min(prices), prices[-1],
                         math.fsum(r[2] for r in rows), math.fsum(r[3] for r in rows),
                         math.fsum(r[4] for r in rows), len(rows)]
                bucket_cache[key] = (signature, value)
            values.append(bucket_cache[key][1])
            labels.append(label)
            if limit is not None and len(values) >= limit:
                break
        values.reverse()
        labels.reverse()
        frame = pd.DataFrame(values, columns=['open', 'high', 'low', 'close', 'volume',
                                              'buy_volume', 'sell_volume', 'trades'],
                             index=pd.DatetimeIndex(labels, tz='UTC', name='timestamp').as_unit('us'))
        return decorate_bars(frame)
