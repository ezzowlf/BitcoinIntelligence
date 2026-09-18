"""Look-ahead and bid/ask-side audits for the production signal path (SS24-25).

A decision taken at T0 must be computable from information timestamped <=T0
only. These tests feed the real feature/signal code a stream that contains
post-T0 data and prove the decision does not change, and that LONG/SHORT are
evaluated on the correct executable side of the Vantage quote.
"""
from datetime import UTC, datetime, timedelta

import pytest

from bitcoin_cycle_analyzer.short_term.causal_features import CausalFeatures
from bitcoin_cycle_analyzer.short_term.events import normalize_binance_message
from bitcoin_cycle_analyzer.short_term.journal import Journal
from bitcoin_cycle_analyzer.short_term.outcome_engine import OutcomeEngine
from bitcoin_cycle_analyzer.short_term.signal_engine import SignalEngine

T = datetime(2026, 1, 1, tzinfo=UTC)


def _drive(features, market, stamp, price, sign):
    event = normalize_binance_message(
        {'e': 'trade', 's': 'BTCUSDT', 'T': int(stamp.timestamp() * 1000),
         'p': str(price), 'q': '0.01', 'm': sign < 0}, stamp, market)
    p = event.payload
    features.trade(market, stamp, p['price'], p['quantity'], p['buyer_is_maker'])


@pytest.mark.parametrize('sign', [1, -1])
def test_features_at_t0_ignore_future_trades(sign):
    """Feeding trades timestamped after T0 must not change the T0 snapshot."""
    baseline = CausalFeatures()
    contaminated = CausalFeatures()
    for seconds in range(10):
        stamp = T + timedelta(seconds=seconds)
        for market in ('spot', 'futures'):
            _drive(baseline, market, stamp, 77000 + sign * seconds, sign)
            _drive(contaminated, market, stamp, 77000 + sign * seconds, sign)
    t0 = T + timedelta(seconds=9)
    # The contaminated engine additionally sees a violent move AFTER T0.
    for seconds in range(10, 40):
        stamp = T + timedelta(seconds=seconds)
        for market in ('spot', 'futures'):
            _drive(contaminated, market, stamp, 77000 - sign * seconds * 50, sign)
    quote = {'bid': 77000.0, 'ask': 77001.0}
    health = {key: 'HEALTHY' for key in ('spot', 'futures', 'l2', 'vantage')}
    a = baseline.snapshot(t0, quote, l2=sign * .8, feed_health=health, storage_ready=True, outcomes_ready=True)
    b = contaminated.snapshot(t0, quote, l2=sign * .8, feed_health=health, storage_ready=True, outcomes_ready=True)
    numeric = [k for k, v in a.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    assert numeric, 'expected numeric features to compare'
    for key in numeric:
        assert a[key] == pytest.approx(b[key]), f'feature {key} leaked post-T0 information'


@pytest.mark.parametrize('sign,direction,side', [(1, 'LONG', 'ASK'), (-1, 'SHORT', 'BID')])
def test_signal_uses_the_correct_executable_side(tmp_path, sign, direction, side):
    """A LONG is entered at the ASK and a SHORT at the BID; the emitted
    transition must state the side the outcome engine will price it on."""
    journal = Journal(tmp_path / 'journal.db')
    engine = SignalEngine(journal, OutcomeEngine(journal))
    features = CausalFeatures()
    health = {key: 'HEALTHY' for key in ('spot', 'futures', 'l2', 'vantage')}
    transitions = []
    start = datetime.now(UTC)
    for seconds in range(7):
        now = start + timedelta(seconds=seconds)
        price = 77000 + sign * seconds * 2
        for market in ('spot', 'futures'):
            for i in range(30):
                stamp = now - timedelta(milliseconds=30 - i)
                _drive(features, market, stamp, price + sign * i * .001, sign)
        snapshot = features.snapshot(now, {'bid': price, 'ask': price + 1}, l2=sign * .8,
                                     feed_health=health, storage_ready=True, outcomes_ready=True,
                                     synthetic=True)
        transition = engine.evaluate(now, snapshot)
        if transition:
            transitions.append(transition)
    assert transitions, 'expected the production engine to emit transitions'
    assert {row['direction'] for row in transitions} == {direction}
    for row in transitions:
        assert row['vantage_executable_side'] == side
        bid, ask = row['entry_zone']
        assert bid < ask, 'entry zone must keep bid below ask'


@pytest.mark.parametrize('sign,direction', [(1, 'LONG'), (-1, 'SHORT')])
def test_outcome_prices_each_direction_on_its_own_side(tmp_path, sign, direction):
    """A favourable move must produce a positive executable outcome for both
    directions - i.e. SHORT is not silently priced like a LONG."""
    journal = Journal(tmp_path / 'journal.db')
    outcomes = OutcomeEngine(journal)
    start = datetime.now(UTC)
    outcomes.quote(start, 77000.0, 77001.0)
    outcomes.register('setup-1', 'LIVE', start, direction, horizons=(60,))
    for seconds in range(1, 120):
        price = 77000 + sign * seconds * 5
        outcomes.quote(start + timedelta(seconds=seconds), price, price + 1)
    results = outcomes.resolve_due(start + timedelta(seconds=130))
    row = next(r for r in results if r['horizon_seconds'] == 60)
    assert row['status'] == 'RESOLVED'
    assert row['entry_side'] == ('ASK' if sign == 1 else 'BID')
    assert row['exit_side'] == ('BID' if sign == 1 else 'ASK')
    assert row['executable_outcome'] > 0, 'favourable move must be a gain for this direction'
