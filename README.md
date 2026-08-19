# Bitcoin Cycle Analyzer

> Version 2.1 ergänzt echte Binance-Funding/OI- und Coin-Metrics-Community-Daten mit strengem `available_at`-Vertrag. ETF, Makro und News bleiben ohne verifizierte Konfiguration ehrlich `UNAVAILABLE`. Details: `REAL_MARKET_DATA_VALIDATION_REPORT.md`.

Version 2.2 erweitert die OI-Historie über das offizielle Binance-Vision-Archiv bis September 2020, ergänzt ALFRED-Vintage-, ETF- und MeanPulse-Verträge sowie Evidence/Confluence 2.2. Der reale Status und verbleibende Zugangshürden stehen in `BITCOIN_INTELLIGENCE_2_2_VALIDATION_REPORT.md`.

Ein lokales, transparentes Research-System ausschließlich für Bitcoin. Es bewertet historische und zyklische Konstellationen, erzeugt aber **keine Anlageberatung** und kein automatisches Buy/Sell-Signal.

## Schnellstart (Windows / PowerShell)

```powershell
$python = '.\.venv\Scripts\python.exe'
& $python -m pip install -e '.[dev,dashboard,live,research]'
& $python scripts/update_data.py
& $python scripts/seed_golden_events.py
& $python scripts/data_quality_report.py
& $python scripts/run_real_validation.py
& $python scripts/run_intelligence_validation.py
& $python scripts/run_analysis.py
& $python -m streamlit run dashboard/app.py
```

`database/*.db` is intentionally ignored because it contains generated local
market data. A fresh checkout should run `scripts/update_data.py` to rebuild
the public Bitstamp OHLCV baseline and `scripts/seed_golden_events.py` to add
the small source-labelled event fixture. The dashboard and historical tests
then use the same UTC-normalized SQLite schema.

WAVERUN live mode uses public Binance WebSocket streams only:

```powershell
& $python scripts/waverun_live.py --duration 30
```

It writes a local snapshot to `runtime/waverun/latest.json` and predictions to
`database/waverun_predictions.db`. No order or private endpoint exists in this
path; outputs remain `execution: DISABLED`.

WAVERUN historical Binance Vision aggregate trades can be downloaded into the
ignored Parquet lake without credentials:

```powershell
& $python scripts/download_binance_history.py --market spot --symbol BTCUSDT --data-type aggTrades --start 2026-08-18
& $python scripts/download_binance_history.py --market um --symbol BTCUSDT --data-type aggTrades --start 2026-08-18
& $python scripts/data_inventory.py --output WAVERUN_DATA_INVENTORY.json
```

These archives contain trades, not historical L2. The activated 30-day
Vantage/Binance overlap is recorded in `WAVERUN_DATA_ACTIVATION_REPORT.md`.

The holdout-protected precision research is reproducible with:

```powershell
& $python scripts/waverun_data_quality.py
& $python scripts/build_waverun_research_dataset.py
& $python scripts/run_waverun_precision_research.py
& $python scripts/waverun_selected_diagnostics.py
```

The default dataset builder stops at 2026-08-15. It refuses the 2026-08-16/17
final holdout without a frozen candidate, and excludes the previously viewed
2026-08-18 exploration day. Results remain research-only with
`execution: DISABLED`; see `WAVERUN_80_PRECISION_RESEARCH_REPORT.md`.

Tests:

```powershell
& $python -m pytest -q
```

## Architektur

- `data_provider.py`: validierte OHLCV-Schnittstelle, Kraken-Adapter, SQLite-Upsert, Resampling
- `indicators.py`: RSI, EMA 20/50/100/200, SMA 200, ATR, Volumen, ATH-Drawdown
- `swing_detection.py`: timeframe-parametrisierte, erst nach rechtsseitiger Bestätigung bekannte Pivots
- `market_structure.py`: HH/HL/LH/LL, Trend, Support und Widerstand
- `fibonacci.py`: Retracements, Extensions und Cluster/Confluence
- `elliott_wave.py`: mehrere regelbasierte, probabilistische Szenarien mit Invalidierung
- `similarity.py`: stichtagsbezogene Features, historische Nachbarn und Forward-Return-Verteilungen
- `opportunity_score.py`: zentral gewichteter 0–100-Score mit Einzelbeiträgen
- `backtesting.py`: Ausführung auf der nächsten Kerze, Vergleich mit Buy & Hold und DCA
- `walk_forward.py`: getrennte Train/Test-Fenster und Out-of-Sample-Auswertung
- `zones.py`: gestaffelte Zonen mit Risiko und Invalidierung
- `audit.py`: versionierte JSON-Snapshots jeder Analyse
- `dashboard/app.py`: lokales Streamlit-/Plotly-Dashboard

## Market Intelligence 2.0

Die bestehende technische Engine wird durch neue, getrennte Ebenen ergänzt:

- `core/`: Halving-/ATH-Zyklus, probabilistische Regimes und Market State Matrix
- `seasonality/`: Monate, Wochentage, Quartale, Monatswechsel und Feiertagsfenster
- `onchain/`, `derivatives/`, `flows/`, `macro/`, `news/`: zeitkausale Provider-Schnittstellen
- `scoring/evidence.py`: Belastbarkeit getrennt vom Opportunity Score
- `scoring/confluence.py`: unabhängige Faktoren ohne Doppelzählung korrelierter Inputs
- `validation/ablation.py`: inkrementeller Informationswert einzelner Faktoren
- `alerts.py`: Watch-Alerts ohne Orderausführung

Nicht konfigurierte externe Feeds liefern ausdrücklich `UNAVAILABLE`; sie werden weder neutral gesetzt noch geschätzt. Architektur und Faktorgrenzen stehen in `BITCOIN_INTELLIGENCE_ARCHITECTURE.md` und `MARKET_FACTORS.md`. Die echte Seasonality-/OOS-Auswertung steht in `BITCOIN_INTELLIGENCE_VALIDATION_REPORT.md`.

## Zeitkausalität

Ein Pivot bei `pivot_time` ist erst bei `confirmed_at` verwendbar. Indikatoren sind rückwärtsgerichtet; Similarity schneidet Daten am `as_of`-Zeitpunkt ab; Backtest-Signale werden erst zum Open der folgenden Kerze ausgeführt. Tests mutieren gezielt zukünftige Daten und prüfen, dass historische Ergebnisse unverändert bleiben.

## Datenquellen und Grenzen

Primär wird die öffentliche Bitstamp-BTC/USD-OHLC-API ab 2011 verwendet. Kraken bleibt als zweiter Provider verfügbar. Alle Kerzen werden mit Provider, Quelle, Importzeitpunkt und Datenversion in SQLite gespeichert; 1W und 1M entstehen ausschließlich aus abgeschlossenen kanonischen Daily-Kerzen. Lizenz- und Nutzungsgrenzen sowie die echte Mehrzyklusvalidierung stehen in `REAL_DATA_VALIDATION_REPORT.md`.

Elliott-Wellen bleiben subjektiv: Die Engine liefert nur plausible regelbasierte Szenarien, Confidence und Invalidierungen. On-chain-Daten, Derivate, ETF-Flows und Makrodaten sind Erweiterungspunkte, aber nicht Teil dieses MVP.

## Backtest-Interpretation

Der echte Mehrzykluslauf liegt lokal unter `data/reports/` und ist in `REAL_DATA_VALIDATION_REPORT.md` vollständig zusammengefasst. Die Resultate zeigen deskriptiven Wert, aber keinen robusten Beweis einer stabilen Überlegenheit gegenüber Buy & Hold oder einfachen Regeln.
Externe Daten aktualisieren und validieren:

```powershell
.\.venv\Scripts\python.exe scripts\update_external_data.py
.\.venv\Scripts\python.exe scripts\run_market_data_validation.py
```
