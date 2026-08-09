# Bitcoin Intelligence 2.3 Precision Report

## Baseline

- Ausgangscommit: `bd16251 Bitcoin Intelligence 2.2 macro ETF news validation`
- Branch: `codex/precision-engine`
- Gewichte und externe Faktorstatus wurden nicht optimiert.
- Analysemodus: `CLOSED_CANDLE`; Execution: `DISABLED`.

## Current State

Letzter abgeschlossener Datenpunkt: 7. August 2026 UTC; BTC 64.877,77 USD.

| Dimension | Ergebnis | Status |
|---|---|---|
| Market State | `VALUE_WITHOUT_CONFIRMATION` | regelbasierte Taxonomie |
| System Conclusion | `ATTRACTIVE_VALUE_BUT_NO_CONFIRMED_ENTRY_EDGE` | keine Handlungsempfehlung |
| Value | 70,30 `HIGH_VALUE` | `PARTIALLY_VALIDATED` |
| Value Percentile | 52,4 | PIT-Historie |
| Regime Ensemble | `BEAR` | `RESEARCH` |
| Regime Candidate | `BEAR` | – |
| Regime Stability | `LOW` | Agreement 0,40 |
| Timing | 0 `WAIT`; Next `CONFIRMING` | `RESEARCH` |
| 7D/30D/90D Risk | 37,2 / 43,8 / 48,2 | ordinal, `RESEARCH` |
| Tail Risk | `NORMAL` | nicht kalibriert |
| Capitulation | `NONE` | – |
| Evidence | 60,38 `MODERATE` | analytische Belastbarkeit |
| Confluence | 51,5 `LOW`; 5/8 Gruppen | fehlende Gruppen nicht negativ |
| Data Quality | 76 `MODERATE` | kritische Preisdaten gesund |
| Uncertainty | 57,1 `HIGH` | Regime- und Analogue-Dispersion |

Regime relative support: Bear 40, Accumulation 20, Distribution 20, Transition 20. Das sind relative Supports, keine Wahrscheinlichkeiten. Modelle: Price Structure Bear; Drawdown Transition; Momentum Bear; Cycle Timing Distribution; On-Chain Accumulation.

## Value

Value verwendet ATH-Drawdown, langfristige MA-Relation und Halving-Kontext. H4-Timing, Funding, Intraday-OI und News sind ausgeschlossen. Aktuell: -47,98 % zum ATH, -7,81 % relativ zur 200D-Linie und 27,56 Monate seit Halving. Die feste historische Validierung nutzte Value-Percentile >=75 als Eventdefinition; die aktuelle Value-Engine bleibt `PARTIALLY_VALIDATED`, weil ihr exakter zusammengesetzter Score noch keinen unangetasteten Holdout besitzt.

## Regime

Fünf unabhängige Teilmodelle stimmen nur zu 40 % auf das Top-Regime überein; Support-Margin 20 Punkte, Stability `LOW`. Die historische Konditionierung trennte Outcomes deutlich: High-Value in Bear hatte 30D-Median +1,31 % und 54,55 % Win Rate; im Recovery/Bull-Kontext +21,19 % und 93,33 %. Das ist ökonomisch relevant, aber wegen 20 versus 13 unabhängigen Episoden und bereits eingesehener Resultate nur `RESEARCH`.

## Timing

Harte Bedingungen sind aktuell sämtlich offen: kein bestätigtes Lower Low, Structure Reclaim sowie H4/D1-Bestätigung. Ein hoher Score allein kann `CONFIRMED` nicht erzeugen. Schlechte kritische Daten halten den Zustand als `STATE_HELD_DUE_TO_DATA_QUALITY`.

Eventvalidierung bei High Value:

| State | Episoden | 30D Median | 30D Win Rate | 90D Median | 30D MAE |
|---|---:|---:|---:|---:|---:|
| WAIT | 30 | +11,50 % | 70,00 % | +24,82 % | -4,10 % |
| CONFIRMED-Proxy | 11 | +25,16 % | 72,73 % | +9,84 % | -16,78 % |

`CONFIRMED` verbesserte den 30D-Median, reduzierte aber gerade **nicht** den Drawdown. Sieben von elf Confirmed-Episoden fielen innerhalb von 30 Tagen mindestens 10 %: False Confirmation Rate 63,64 %. Timing wird nicht hochgestuft und bleibt `RESEARCH`; die zentrale Frage „reduziert Timing den Drawdown guter Value-Signale?“ lautet derzeit **nein**.

Confirmation Delay: Median 23 Tage nach dem vorangegangenen lokalen 30-Tage-Tief und 22,45 % über diesem Tief. Das bestätigt den Sicherheits-/Verspätungs-Trade-off, ohne einen optimalen Schwellenwert abzuleiten.

## Drawdown Risk

Risk liefert getrennte 7D/30D/90D-Ordnungswerte, Tail State und Capitulation State. Die MAE-Mediane nach Risk-Bins waren -4,13 % für 40–60, -10,09 % für 60–80 und -6,05 % für 80–100. Die Beziehung ist nicht monoton. Drawdown Risk 2.0 bleibt `RESEARCH` und darf nicht als validiert oder probabilistisch bezeichnet werden.

## Capitulation und Recovery

Die Engine erkennt `NONE`, `STRESS`, `CAPITULATION_CANDIDATE`, `CAPITULATION` und trennt dies von Bottom-/Recovery-Behauptungen. PIT-Replay erkannte den 12. März 2020 und 9. November 2022 als `CAPITULATION`; Timing blieb wegen extremer beziehungsweise hoher Risiken unbestätigt. Ein Stressereignis garantiert keinen Boden.

## Similarity

Die neue Sequenzanalyse vergleicht normierte 90-Tage-Pfade und erzwingt 120 Tage Abstand zwischen Analogues. Aktuell: 12 unabhängige Episoden. Die 365D-Ergebnisdispersion ist mit 5,36 extrem hoch, unter anderem wegen früher Bitcoin-Eras. Similarity bleibt `RESEARCH`; der Dispersion-Cap reduziert indirekt die Sicherheit.

## Cross-Factor

- Value High + Risk High: 16 unabhängige Episoden, 30D-Median +26,96 %, MAE -7,99 %.
- Value High + Risk niedriger: 22 Episoden, 30D-Median +6,39 %, MAE -4,42 %.
- Value + CONFIRMED zeigte höhere Rendite, aber deutlich schlechtere MAE.
- Regime konditionierte Value-Ergebnisse stärker als der aktuelle Risk-Score.

Es wurden drei Faktoren, sechs plausible Konditionen und zwei primäre Horizonte geprüft. Es fand keine Best-of-Auswahl, Gewichtsanpassung oder Brute-Force-Kombinationssuche statt.

## Walk Forward, Structural Breaks und Holdout

Anchored Jahresausgaben reichen 2018–2026. Die Episodenzahl schwankt stark: 2018 zwei, 2019 vier, 2020 vier, 2022 eine, 2023 zwölf; 2021 und 2024–2026 keine neuen unabhängigen High-Value-Episoden. Era-Diagnostik für Early Bitcoin, Derivatives Era und ETF Era ist `RESEARCH`; Era-Tags verändern keine Modellgewichte.

Die bisherigen Zeitfenster einschließlich OOS ab 29. Oktober 2024 sind `USED_FOR_RESEARCH`. Ein neuer echter finaler Holdout existiert noch nicht und erfordert zukünftige Beobachtungen. Kein bekanntes Fenster wird als unangetastet bezeichnet.

## Evidence und Data Quality

Evidence bleibt von Richtung und Data Quality getrennt. Uncertainty berücksichtigt Regime-Agreement, fehlende Gruppen, Analogue-Dispersion, Evidence und Gruppen-Coverage. Stale kritische Daten verhindern neue Confirmed-Zustände. Value wird durch Provider-Ausfall nicht künstlich reduziert; stattdessen sinken Data Quality/Evidence und Timing hält fail-closed.

## Replay, Snapshots und Ledger

Dashboard-PIT-Replay akzeptiert historische Daten und schneidet alle Preis-/Feed-Inputs bei `available_at <= as_of` ab. Navigation unterstützt Previous/Next Day sowie +7/+30 Tage. Snapshot-Store speichert Engine-Version 2.3, Config-Hash, Code-Commit, Drivers und Data Health. Research Registry, Experiment Ledger und Transition History besitzen deduplizierte SQLite-Schemata.

## State Changes und Szenarien

WAIT → CONFIRMING benötigt aktuell: kein bestätigtes Lower Low, Structure Reclaim und H4/D1-Bestätigung; extremes Risiko oder schlechte kritische Daten blockieren. Bullish/Base/Bearish-Szenarien zeigen nur Bedingungen, Invalidierungen und Faktoranzahl, keine Kursziele oder Wahrscheinlichkeiten. Alerts werden nur bei Zustands- oder erheblichen Risk-Änderungen erzeugt, enthalten Erklärung/Invalidierung und bleiben `DISABLED`.

## Failures

- Der Timing-Proxy reduziert MAE nicht und hat 63,64 % False Confirmations.
- Risk-Bins sind nicht monoton.
- Analogue-Dispersion ist hoch.
- Regime Agreement ist aktuell niedrig.
- Macro, ETF und reale News bleiben unavailable; On-Chain ist PIT-partiell.
- Confirmation Delay ist mit elf Episoden messbar, aber für Kalibrierung zu klein und bereits `USED_FOR_RESEARCH`.
- Fibonacci Reaction, Elliott Incremental Value und Zone-Failure-Historie wurden nicht hochgestuft; sie bleiben bestehende Research-Komponenten.

## Engine Status

| Engine | Status |
|---|---|
| Price/Core | `VALIDATED` aus 2.2 |
| Value 2.3 | `PARTIALLY_VALIDATED` |
| Regime Ensemble | `RESEARCH` |
| Timing State Machine | `RESEARCH` |
| Drawdown Risk 2.0 | `RESEARCH` |
| Capitulation/Recovery | `RESEARCH` |
| Sequence Similarity | `RESEARCH` |
| Fibonacci | `RESEARCH` |
| Elliott | `RESEARCH_ONLY` |
| On-Chain | `RESEARCH/PARTIAL` |
| Derivatives | Funding `RISK_ONLY`, OI `RESEARCH` |

Die aktuelle belastbare Schlussfolgerung lautet: langfristig attraktiver Value-Kontext, aber kein bestätigter Entry Edge und hohe Unsicherheit.

## Abschlusschecks

- 60 Tests einschließlich aller 49 Baseline-Tests.
- Python Compile und `git diff --check` grün.
- Dashboard-Smoke HTTP 200.
- Historical Precision Validation und anchored Jahresauswertung ausgeführt.
- Execution bleibt in Engine, Timing, Alerts und Snapshots `DISABLED`.
