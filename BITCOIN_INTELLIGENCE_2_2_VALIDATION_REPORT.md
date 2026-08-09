# Bitcoin Intelligence 2.2 Validation Report

## Git

- Ausgangsbasis 2.0: `feb8e8c`
- reproduzierbar gesicherte 2.1-Baseline: `9a6da2e Bitcoin Intelligence 2.1 real market data baseline`
- Entwicklungsbranch: `codex/macro-etf-news`
- kein Push, kein 2.2-Abschlusscommit

## Providers

| Quelle | Auth | Start | Ende | Beobachtungen | Status |
|---|---|---:|---:|---:|---|
| Bitstamp BTC/USD | öffentlich | 2011-08-18 | 2026-08-07 | 5.469 Tage | `VALIDATED` Preisbasis |
| Binance Funding REST | öffentlich | 2019-09-10 | 2026-08-09 | 7.576 | `RISK_ONLY` |
| Binance Vision OI Archive | öffentlich, MIT-Dokumentation | 2020-09-01 | 2026-08-08 | 52.010 auswertbare Stunden | `RESEARCH` |
| Coin Metrics Community v4 | öffentlich | 2011-08-18 | 2026-08-08 | 10 × 5.470 | `RESEARCH` |
| FRED/ALFRED | API-Key erforderlich | – | – | 0 | `UNAVAILABLE` |
| Spot-BTC-ETF-Flows | keine lizenzierte PIT-Quelle konfiguriert | – | – | 0 | `UNAVAILABLE` |
| MeanPulse News | kein Endpoint/Export konfiguriert | – | – | 0 | `UNAVAILABLE` |

Rohdatenbanken und generierte JSON-Berichte bleiben lokale Laufartefakte und werden nicht committet.

## Macro

Der ALFRED-Provider besitzt einen vollständigen Initial-Release-Vertrag mit `period_start`, `period_end`, `observation_value`, `release_time`, `available_at`, `revision_id` und Provider. Konfiguriert sind USD-Index, 2Y/10Y/30Y, Fed Funds, Fed-Bilanz, CPI/Core CPI, PCE/Core PCE, Payrolls, Arbeitslosenquote, GDP, M2, Nasdaq, S&P 500, Gold und Öl. Features umfassen 1/3/6-Perioden-ROC, Z-Score, Perzentil, Trend und Beschleunigung.

Es ist kein `FRED_API_KEY` vorhanden. Da FRED diesen Schlüssel verlangt, wurden keine aktuellen Revisionen als historische Vintages missbraucht. Macro bleibt daher real `UNAVAILABLE`; Grundcode `FRED_API_KEY_MISSING_OR_NO_RELEASES`. OOS und Ablation sind nicht ausführbar. Ein dedizierter Release-Store mit Unique Constraint und Indizes auf Serie, Periode und `available_at` sowie Health-Checks für Duplikate ist vorhanden.

## ETF

Die Engine unterstützt Daily-, 5D-, 20D- und kumulierte Flows sowie Beschleunigung und institutionellen Zustand unter strikt gefiltertem `available_at`. Kandidatenprüfung: CoinGlass bietet einen historischen API-Endpunkt, verlangt aber einen kostenpflichtigen API-Zugang; SoSoValue dokumentiert einen API-Endpunkt, ebenfalls ohne vorhandene Lizenz/Access; Farside veröffentlicht Tabellenwerte, dokumentiert jedoch keinen für dieses Projekt freigegebenen stabilen PIT-API- und Revisionsvertrag. Screenshots, Parse-Wrapper und Webseiten-Scraping wurden nicht verwendet. ETF bleibt mit Grundcode `NO_LICENSED_POINT_IN_TIME_PROVIDER` `UNAVAILABLE`; keine OOS-Aussage ist zulässig.

## On-Chain

Das automatische Community-Inventar weist 47 frei katalogisierte BTC-Metrik/Frequenz-Kombinationen aus. Importiert sind MVRV, Exchange Inflows, Exchange Outflows, Exchange Balance, Active Addresses, Transaction Count, Transfer Count, Hash Rate, Fees und Issuance mit je 5.470 Tageswerten. MVRV und die neuen Network-/Mining-Metriken besitzen keine beweisbare historische Statuszeit und bleiben für den Preis-Cutoff sowie historische Backtests unsichtbar. Exchange-Flows erlauben aktuell einen Research-Zustand für Holder Behavior; im Snapshot lautet er `ACCUMULATION`. Premium-Metriken wie SOPR, NUPL oder Realized Cap werden nicht vorgetäuscht.

## Derivatives

- Funding: neutral; vorheriger OOS-Test ohne stabilen Alpha-Wert, deshalb `RISK_ONLY`.
- OI: offizielle Binance-Vision-Tagesarchive, fünfminütige Rohdaten auf echte Stundenwerte gesampelt; Verfügbarkeit Messzeit plus fünf Minuten.
- OI-OOS: 7D 0,0124; 30D 0,0481; 90D -0,0479; 180D -0,0093; 365D 0,1039 Rank-Korrelation im finalen 30-%-Zeitblock. Richtung und Stärke sind nicht stabil, daher `RESEARCH`.
- Basis, Liquidationen und Optionen: `UNAVAILABLE`; keine geschätzten Werte oder Heatmap-Scrapes.

## News

Der standardisierte MeanPulse-JSONL-Vertrag verarbeitet Event-ID, Event-Zeit, `available_at`, Kategorie, Severity, Market Scope, Risk Direction, BTC Direction, Confidence und Quelle. Zusätzlich existiert ein read-only SQLite-Adapter für die vorhandene MeanPulseNews-Datenbank; Story-Versionen bilden Update Chains und werden nicht überschrieben. Die Produktionsdatenbank enthält 0 reale Stories/Assessments. Die Staging-Datenbank enthält 6 klar gekennzeichnete Teststories und wurde nicht als Evidenz importiert. Kategorienaliase, zentral konfigurierbare Half-Lives und ein `CONTEXT_ONLY` Transmission State sind implementiert. Zukünftige Events erhalten Gewicht null. News bleibt mit Grundcode `NO_REAL_MEANPULSE_EVENTS` `UNAVAILABLE`.

## Confluence und Evidence

Confluence 2.2 unterstützt acht Gruppen: Price/Technical, Cycle, On-Chain, Derivatives, ETF, Macro, News und Seasonality. Identische Source-/Event-Paare werden nur einmal gezählt. Jede Gruppe liefert Status, Score, Confidence, Data Quality, Coverage und OOS Value.

Evidence 2.2 berücksichtigt unabhängige Gruppen, Datenqualität, historische Coverage, Sample Size, OOS Value, Provider Agreement, PIT-Qualität und Regime Coverage. Fehlende Gruppen werden nicht als neutrales Signal gewertet. Die alte Score-Gewichtung wurde nicht auf dem aktuellen OOS-Fold optimiert.

## Walk-forward, Matrix und Ablation

Der maschinenlesbare Bericht `data/reports/intelligence_22_validation.json` enthält die chronologische 70/30-Teilung mit unangetastetem OOS ab 29. Oktober 2024 sowie alle OI-Horizonte. `CORE + DERIVATIVES` ist getestet. Macro, ETF und News bleiben in der Matrix explizit `UNAVAILABLE`; eine erfundene Ablation mit Nullwerten wäre methodisch falsch. Der Ablationsplan umfasst nur tatsächlich verfügbare Gruppen.

Episode-Clustering bleibt aktiv und trennt Threshold Crossings von unabhängigen Episoden. Ohne echten neuen Signalstatus werden keine künstlichen Episodenzahlen ausgegeben.

## Current Snapshot

Letzter abgeschlossener Preiszeitpunkt: 7. August 2026 UTC.

- Cycle: `TRANSITION`
- Long-Term Value: 72,51/100
- Entry Timing: `WAIT`; Execution `DISABLED`
- Drawdown Risk: 73,6/100, `HIGH`
- Funding: `NEUTRAL`
- OI: rund 6,80 Mrd. USD; 24h -1,76 %, 7D -1,47 %, historisches Perzentil 77,9 %, `RESEARCH`
- On-Chain Holder Behavior: `ACCUMULATION`, sonst partiell
- Macro: `UNAVAILABLE`
- ETF: `UNAVAILABLE`
- News: `UNAVAILABLE`
- Confluence bleibt niedrig; fehlende Gruppen werden nicht aufgefüllt.

Exakte Engine-Ausgabe: BTC 64.877,77 USD; Cycle `TRANSITION` mit relativer Regelkonfidenz 15,6; Confluence 51,5/100 (`LOW`) aus 5/8 verfügbaren Gruppen; Evidence 2.2 60,38/100 (`MODERATE`). Der regelbasierte Haupttreiber ist Long-Term Value; Hauptbelastung ist historisches Drawdown-Risiko. Für `WAIT → CONFIRMING` verlangt die Engine Price-Structure-Reclaim und mindestens mittlere Bestätigung. Verschlechterung: Verlust des Weekly Supports oder anhaltend hohes Drawdown-Risiko. Execution bleibt `DISABLED`.

## Tests und Smokes

- 49 Tests bestanden, einschließlich Release-Time, Makro-Vintage-Store, ETF-Missing-Days, News-Ingestion/Decay/Availability/Update-Chains, Provider-Ausfall, Evidence 2.2, Confluence ohne Fehlgruppenstrafe, Current-State-Erklärung, Validation Matrix und Ablationsplan.
- Dashboard-Smoke: HTTP 200 auf lokalem Streamlit-Testserver.
- Vollständiger Compile und `git diff --check` werden im Abschlusslauf erneut ausgeführt.

## Limitations

## Finaler Faktorstatus

- `VALIDATED`: Bitstamp Price/Cycle-Basis und bestehender technischer Core.
- `RISK_ONLY`: Funding; Derivate-Gesamtgruppe bleibt Risiko-/Positionierungskontext.
- `TIMING_ONLY`: keine neue externe Gruppe.
- `RESEARCH`: OI, Coin-Metrics Exchange-/Network-/Mining-Daten, On-Chain Holder Behavior.
- `REJECTED`: Funding als Richtungs-Alpha; Seasonality als produktiver Mehrwert beziehungsweise `RESEARCH_LOW_VALUE` im UI.
- `UNAVAILABLE`: Macro, ETF, reale News, Futures Basis, Liquidationen, Optionen sowie Premium-On-Chain-Metriken.

## OOS, Ablation und Multiple Testing

OI-Richtungs-OOS bleibt instabil: 7D 0,0124; 30D 0,0481; 90D -0,0479; 180D -0,0093; 365D 0,1039. Extreme OI-/Funding-Beobachtungen hatten im festen Test keine höhere 30D-MAE oder Volatilität als die neutrale Vergleichsgruppe (MAE -7,38 % vs. -9,57 %; Volatilität 4,80 % vs. 6,21 %). Daraus folgt **kein robuster zusätzlicher OI-Risk-Uplift**; OI bleibt `RESEARCH`. Funding behält seinen zuvor festgelegten `RISK_ONLY`-Status, nicht wegen einer nachträglichen Kombination.

Getestet wurden zwei Derivatefaktoren über fünf Richtungshorizonte sowie zwei Risikodiagnostiken; zusätzlich existieren die früheren Funding- und Seasonality-Tests. Es wurde keine beste Kombination ausgewählt, kein Gewicht angepasst und daher keine einzelne Zufallsentdeckung produktiv übernommen. Formale FDR-Selektion war nicht erforderlich, weil kein Kandidat den Validierungsstatus erreichte.

`CORE + DERIVATIVES` wurde real ausgeführt. On-Chain ist wegen fehlender historischer `available_at`-Beweise nur aktuell partiell und nicht fair ablatierbar. Macro, ETF und News bleiben aus den Ablationen ausgeschlossen statt als künstliche Nullserie einzugehen.

## Secrets und verbleibende Zugänge

`.env` ist nicht vorhanden und wird ignoriert. `.env.example` enthält ausschließlich leere Platzhalter. Weiterhin benötigt werden: `FRED_API_KEY`; optional ein lizenzierter `ETF_DATA_API_KEY` für CoinGlass/SoSoValue oder einen gleichwertigen PIT-Provider; reale MeanPulse-Produktionsereignisse über die vorhandene SQLite-Datenbank, `MEANPULSE_NEWS_FILE` oder `MEANPULSE_NEWS_URL`.

## Limitations

Die externe Gruppenanzahl bleibt 5/8 verfügbar. Das entspricht Definition-of-Done-Variante B: Interfaces und Fehlergründe sind vollständig, keine Ersatzdaten wurden erfunden, und Provider-Ausfälle beeinträchtigen den Core nicht. Es wurden keine Trades, Orders, Positionsgrößen oder automatischen Käufe implementiert.
