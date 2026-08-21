# WAVERUN V5.3 MACD winner/loser forensics

## Ergebnis

Die bestehende deterministische 30-s-MACD-SHORT-Discovery-Population wurde unverändert verwendet: Q1-2025-Top-20%-Schwellen, keine Zukunftsdaten, 180-s-Declustering, Holdout 16./17.08.2026 geschlossen. Es wurden 47 Kandidaten gefunden: 26 `STRONG_WINNER` (MFE >= $500), 6 `MODERATE_WINNER` (>= $300), 9 `LATE_WINNER` (>= $100) und 6 `ABSORBED` (< $100 MFE bei > $100 adverse excursion). `FAILED_CONTINUATION` war in dieser Population nicht vorhanden.

Damit sind die Rohquoten 41/47 = 87.2% für >= $100, 32/47 = 68.1% für >= $300 und 26/47 = 55.3% für >= $500. Diese Zahlen sind Discovery/in-sample und keine OOS-Precision; Wilson-Intervalle und die fehlende Loser-Basis verhindern eine belastbare Modellbehauptung.

Der stärkste beobachtete Unterschied zwischen Gewinnern und Absorptionen war niedrigere Volatilität bei Gewinnern (Median 69.11 vs. 95.02) und weniger Absorption (`flow_price_absorption` -36.29 vs. -73.25). Die MACD-Beschleunigung war bei Gewinnern weniger extrem (-12.43 vs. -19.61), was gegen „je extremer, desto besser“ spricht. Spot/Futures-Agreement war in beiden Gruppen 1.0 und trennt diese Stichprobe nicht.

Der aktuelle Tier beweist weder L2-Mechanik noch Vantage-Bid/Ask-Kostenpfad: historische Vantage- und L2-Tickdaten sind nicht verfügbar. Flow, CVD, Depletion, Pulling/Stacking, Replenishment, Microprice, Lead/Lag, News und echte Spreadkosten sind daher nicht als kausale Gewinnerbedingungen messbar.

## Schlussfolgerung

MACD-Extreme liefern in dieser Discovery-Stichprobe viele große Moves, aber die Auswahl ist nicht validiert und möglicherweise stark regime-/samplegetrieben. Es gibt keine ehrliche Grundlage für eine freigegebene 70-%-, 80-%- oder 90-%-Klasse bei 3 Signalen/Tag. `execution: DISABLED` bleibt erhalten.

Machine-readable Detail: `waverun_v5_3_macd_forensics/forensics.json`.
