from bitcoin_cycle_analyzer.short_term.dashboard import research_dashboard_rows


def test_research_dashboard_uses_oos_rows_only():
    curve = [{"coverage": 0.01, "precision": 0.7, "net_ev": 0.001, "signals": 100}]
    report = {"screening": [{"model": "logistic", "horizon_seconds": 300, "validation": {"coverage_curve": curve}}]}
    diagnostics = {"ablation_walk_forward": [], "by_regime": [{"regime": "EXPANSION"}], "by_utc_hour": []}
    rows = research_dashboard_rows(report, diagnostics)
    assert rows["horizons"] == [{"Horizon": "300s", "Precision": 0.7, "Net EV": 0.001, "Signals": 100}]
    assert rows["coverage"] == curve
    assert rows["regimes"] == [{"regime": "EXPANSION"}]
