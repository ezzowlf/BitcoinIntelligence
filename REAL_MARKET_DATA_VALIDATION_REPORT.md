# Bitcoin Intelligence 2.1 – Real Market Data Validation

## Ergebnis

Bitcoin Intelligence 2.1 nutzt erstmals echte externe Marktdaten, ohne fehlende Quellen zu simulieren. Die technische 2.0-Baseline und ihre Gewichte wurden nicht verändert. Automatische Ausführung bleibt deaktiviert.

Stand des validierten Imports: 9. August 2026.

## Provider, Lizenz und Authentifizierung

- Binance USD-M Public Market Data: öffentliche REST-Endpunkte, kein API-Key für die verwendeten Funding-/OI-Abfragen. Nutzung unter den Binance-Nutzungsbedingungen; kein Weiterverkauf der Rohdaten vorgesehen.
- Coin Metrics Community API v4: öffentlicher Community-Endpunkt ohne Schlüssel. Community-Daten sind für die projektinterne Research-Verwendung vorgesehen; Lizenz- und Attributionserfordernisse müssen vor Weiterverteilung separat geprüft werden.
- FRED/ALFRED: API-Key erforderlich. Der Provider fordert Initial-Release-/Vintage-Daten an; da lokal kein Schlüssel vorhanden ist, wurde keine vermeintlich historische Reihe aus aktuellen Revisionen erzeugt.
- MeanPulse: typisierte Importschnittstelle ohne konfigurierte URL oder Credentials. Sie nimmt nur explizit zeitgestempelte Events an und kann keine Orders auslösen.

| Faktor | Quelle | Abdeckung | Status / Verwendung |
|---|---|---:|---|
| Funding 8h | Binance USD-M Futures Public API | 2019-09-10 bis 2026-08-09, 7.575 | Echt, kausal; Kontext und Derivate-Risiko |
| Open Interest USD | Binance USD-M Futures Public API | 2026-07-19 bis 2026-08-08, 500 Stunden | Echt, aber nur kurzes rollendes Fenster; Research |
| MVRV | Coin Metrics Community v4 | 2011-08-18 bis 2026-08-07, 5.469 | Aktueller Snapshot; historisch nicht PIT-beweisbar, daher Research |
| Exchange In/Out/Balance | Coin Metrics Community v4 | je 5.469 Tage | Echt; revisions- und adressattributionsabhängig |
| ETF-Flows | – | – | `UNAVAILABLE`: keine verifizierte PIT-Quelle konfiguriert |
| Makro | FRED/ALFRED Provider implementiert | – | `UNAVAILABLE`: kein `FRED_API_KEY`; keine ersatzweise revidierte Reihe |
| News | MeanPulse-Schnittstelle vorbereitet | – | `UNAVAILABLE`: kein Endpoint konfiguriert |

## Point-in-time-Vertrag

Jeder Datensatz speichert `event_timestamp`, `observed_at`, `available_at`, Provider, Source-ID, Qualität und Revision. Analysen filtern strikt nach `available_at <= as_of`. Binance-Funding wird erst nach dem Settlement sichtbar. Coin-Metrics-Werte ohne historische Statuszeit werden erst zum Abrufzeitpunkt sichtbar und können damit nicht rückwirkend in Backtests gelangen.

## Funding-Validierung

Getestet wurde ein vorab festgelegter konträrer 30-Tage-Funding-Z-Score, ohne Gewichtsoptimierung. Die Zeitreihe wurde chronologisch 70/30 geteilt; OOS beginnt am 11. Juli 2024.

| Horizont | Beobachtungen | Rank-Korrelation gesamt | Rank-Korrelation OOS |
|---:|---:|---:|---:|
| 7 Tage | 2.488 | 0,0133 | 0,0637 |
| 30 Tage | 2.465 | -0,0405 | -0,0545 |
| 90 Tage | 2.405 | -0,0068 | -0,0572 |
| 180 Tage | 2.315 | 0,0126 | 0,0216 |
| 365 Tage | 2.130 | -0,0289 | 0,0344 |

Das Vorzeichen und die Größenordnung sind nicht stabil. Funding ist damit **nicht als eigenständiger Alpha-Faktor validiert**. Es wird nur zur Beschreibung von Überhitzung, Positionierung und kurzfristigem Risiko verwendet. OI besitzt noch keine ausreichende Historie für einen belastbaren OOS-Test.

## Modulbewertung und Ablation

| Modul | In-Sample / Forward | OOS / Walk-forward | Ablation | Einstufung |
|---|---|---|---|---|
| Funding | 7/30/90/180/365-Tage-Returns getestet | 30-%-Zeitblock getestet | Kein stabil positiver Beitrag | `REJECTED` als Alpha, `RESEARCH` als Risiko-Kontext |
| Open Interest | Kurzes 500h-Fenster | Nicht ausreichend | Nicht belastbar | `RESEARCH` |
| On-chain Exchange-Daten | Reale Historie vorhanden | Revisions-/Adressattributionsrisiko verhindert derzeit eine faire PIT-Ablation | Nicht in Score aufgenommen | `RESEARCH` |
| MVRV | Snapshot vorhanden | Historische Verfügbarkeit nicht beweisbar | Aus Backtests ausgeschlossen | `RESEARCH` aktuell, historisch `REJECTED` |
| ETF | Keine Daten | Nicht möglich | Faktor fehlt vollständig | `UNAVAILABLE` |
| Makro | Provider implementiert | Ohne Key nicht möglich | Faktor fehlt vollständig | `UNAVAILABLE` |
| News | Event-, Kategorie- und Decay-Modell getestet | Ohne reale Events nicht möglich | Faktor fehlt vollständig | `UNAVAILABLE` |

Fehlende Faktoren werden bei Ablationen nicht als Nullsignal interpretiert, sondern aus Nenner und Confluence ausgeschlossen. Dadurch kann Abwesenheit keinen künstlichen Nutzen oder Schaden erzeugen.

## Data Health und Provider-Abweichungen

Funding ist bis zum letzten abgeschlossenen 8h-Settlement verfügbar. OI besitzt wegen des Binance-Limits eine deutliche historische Lücke vor Juli 2026. Coin Metrics endet einen abgeschlossenen UTC-Tag hinter dem Intraday-Markt. Der Store protokolliert Freshness und Coverage je Provider. Das Datenmodell unterstützt parallele Provider und reduziert bei Überschreitung einer relativen 5-%-Abweichung die Konfidenz um 50 %; aktuell ist für diese externen Kennzahlen jedoch jeweils nur ein Provider eingebunden, sodass kein echter Konsens behauptet wird.

Basis, Liquidationen und Optionsdaten sind sauber `UNAVAILABLE`. ETF-Flow-Analyse produziert ohne Datensatz ebenfalls keinen Score. Das Makromodul kann erst nach Vintage-Abruf release-time-kausal getestet werden. News-Decay ist kategorienabhängig; Events mit künftigem `available_at` erhalten Gewicht null.

## Aktueller Zustand

- Funding: neutral, 8h-Wert 0,0058 %, 7-Tage-Mittel 0,0050 %, historisches Perzentil 38,2 %.
- Open Interest: rund 6,96 Mrd. USD; +0,36 % in 24 Stunden und +2,24 % in sieben Tagen; Perzentil im kurzen verfügbaren Fenster 91,2 %.
- Derivate-Abdeckung: 2 von 5 Modulen (Funding und OI), Konfidenz 0,40. Basis, Liquidationen und Optionen bleiben `UNAVAILABLE`.
- Drawdown-Risk im vollständigen Engine-Smoke-Test: 73,6/100 (`HIGH`), ausdrücklich keine kalibrierte Wahrscheinlichkeit.
- Entry Timing: `WAIT`; automatische Ausführung `DISABLED`.

## Qualitätssicherung

39 Tests bestehen. Sie decken die bestehende 2.0-Logik sowie PIT-Ausschluss, Provider-Abweichung, Funding-Regime, OI-Änderungen, Store-Cutoffs, Episode-Clustering, News-Decay, Confluence-Deduplizierung und deaktivierte Ausführung ab. Der Engine-Smoke-Test lief mit dem realen externen Store erfolgreich.

Maschinenlesbare Resultate stehen in `data/reports/real_market_data_validation.json`; Datenquellenstatus und Abdeckung in `data/reports/external_data_health.json`. Diese Dateien sind lokale Laufartefakte und nicht Teil des Git-Snapshots.

## Grenzen

Die Resultate sind Research-Ausgaben, keine Anlageberatung und keine Eintrittswahrscheinlichkeiten. Ein einzelner Provider ist kein Konsens. Exchange-Metriken können sich durch Adressklassifikation ändern. Neue Quellen dürfen erst nach Lizenz-, Zeitstempel-, Revisions- und OOS-Prüfung Scores beeinflussen.
