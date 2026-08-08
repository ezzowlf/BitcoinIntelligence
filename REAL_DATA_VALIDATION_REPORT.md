# Bitcoin Cycle Analyzer – Real Data Validation Report

Stand: 2026-08-09  
Analyseparameter: `1.0.0`  
Datenversion: `bitstamp-btcusd-v1`

## Kurzfazit

Der Analyzer funktioniert technisch auf realen Mehrzyklusdaten und bleibt zeitkausal. Der Opportunity Score zeigt bei Schwellen 70–80 historisch bessere 365-Tage-Trefferquoten und Mediane als bei 60. Daraus folgt jedoch **kein belastbarer Nachweis eines dauerhaften Mehrwerts**:

- Der Score-75-Ansatz erreichte bei 92 auswertbaren 365-Tage-Fällen 76,1 % positive Returns und einen Median von +124,8 %, aber der mediane weitere Drawdown nach allen 103 Signalen betrug -27,9 % und der schlechteste -74,1 %.
- Buy & Hold erzielte über den vollständigen Testzeitraum die höhere CAGR als die implementierte Score-Portfolio-Simulation.
- Im jüngsten echten Out-of-Sample-Fenster ab 20.04.2024 waren nur 8 von 16 bereits 365 Tage auswertbaren Score-75-Signalen positiv; die Score-Portfolio-CAGR war negativ.
- Weekly RSI < 35 und Drawdown <= -70 % sind konkurrenzfähige einfache Regeln. Deren Samples sind kleiner, weshalb keine Überlegenheit behauptet werden darf.
- Elliott verbessert einige 365-Tage-Aggregate leicht, verschlechtert aber andere Horizonte und den Drawdown. Ein eigenständiger robuster Zusatznutzen ist nicht bewiesen.

Der Opportunity Score ist ein erklärbarer Analyse-Score, **keine kalibrierte Steigwahrscheinlichkeit**.

## Datenbasis

Primärquelle ist der öffentliche BTC/USD-Spotmarkt von Bitstamp. Bitstamp dokumentiert den öffentlichen OHLC-Endpunkt und erlaubt API-Nutzung; für kommerzielle Nutzung oder Weiterverteilung nennt Bitstamp eine gesonderte Datenlizenz. Dieses Projekt speichert die Daten nur lokal für Analyse und verteilt die Rohdatenbank nicht. Quelle: [Bitstamp Public API](https://www.bitstamp.net/api/).

Kraken bleibt als zweiter Provider implementiert. Kraken dokumentiert öffentliche OHLC-Daten und stellt zusätzlich herunterladbare historische OHLCVT-Dateien bereit; die REST-Historie ist begrenzt. Quelle: [Kraken historical OHLCVT](https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data).

| Timeframe | Herkunft | Zeitraum UTC | Kerzen |
|---|---|---:|---:|
| 4H | Bitstamp BTC/USD | 2011-08-18 12:00 – 2026-08-08 00:00 | 32.812 |
| 1D | Bitstamp BTC/USD | 2011-08-18 – 2026-08-07 | 5.469 |
| 1W | kausale Aggregation aus 1D | 2011-08-22 – 2026-08-03 | 781 |
| 1M | kausale Aggregation aus 1D | 2011-08-31 – 2026-07-31 | 180 |

Die letzte unvollständige Tages-, Wochen- oder Monatskerze wird nicht als abgeschlossene Aggregation gespeichert. Zeitstempel sind UTC, monoton und je Timeframe eindeutig.

### Canonical Data Layer

Jede Kerze speichert:

- `timestamp`, `open`, `high`, `low`, `close`, `volume`
- `timeframe`, `source`, `provider`
- `import_timestamp`, `data_version`

Der SQLite-Primärschlüssel `(timeframe, timestamp)` verhindert Duplikate. Updates ersetzen denselben kanonischen Zeitpunkt nachvollziehbar, statt eine zweite Kerze anzulegen.

## Datenqualität

Vor dem Backtest wurde der automatische Report `data/reports/data_quality.json` erzeugt. Es wurden keine Reparaturen oder Interpolationen vorgenommen.

| Prüfung | 4H | 1D | 1W | 1M |
|---|---:|---:|---:|---:|
| kritische Fehler | 0 | 0 | 0 | 0 |
| fehlende Perioden | 0 | 0 | 0 | 0 |
| doppelte Zeitstempel | 0 | 0 | 0 | 0 |
| Null-/Negativpreise | 0 | 0 | 0 | 0 |
| High/Low- oder Range-Fehler | 0 | 0 | 0 | 0 |
| Providerwechsel | 0 | 0 | 0 | 0 |

Markierte, nicht reparierte Auffälligkeiten:

- 1D: ein Open-Gap über 35 % am 20.10.2011 (-43,4 %).
- 4H: vier Open-Gaps über 35 % in der sehr illiquiden Frühphase 2011; größtes +241,7 %, danach teilweise Gegenbewegung.
- Keine Volumen-Ausreißer oberhalb der konfigurierten rollierenden 8-Sigma-Grenze.

Diese frühen Marktbedingungen sind ein reales Liquiditäts-/Mikrostrukturproblem und schränken die Übertragbarkeit der frühesten Ergebnisse ein.

## Runtime und OpenSSL

### Fehlerhafte Ausgangsruntime

- Codex-gebündeltes CPython 3.12.13, 64 Bit AMD64
- OpenSSL 3.5.5 vom 27.01.2026
- `requests 2.34.2`, `urllib3 2.7.0`
- `certifi` unter der Bundle-Runtime
- kein virtuelles Environment; `sys.prefix == sys.base_prefix`
- geladen wurden `_ssl.pyd`, `libssl-3-x64.dll` und `libcrypto-3-x64.dll` ausschließlich aus dem Bundle

Der Fehler `OPENSSL_Applink(...): no OPENSSL_Applink` entstand in der nativen Bundle-SSL-Schicht beim TLS-Verbindungsaufbau. Es wurde keine fremde globale OpenSSL-DLL geladen. Eine noch genauere ABI-Ursache wäre ohne Native-Dump spekulativ.

### Saubere Lösung

- offizielles CPython 3.13.15 x64 vom 05.08.2026, ausschließlich unter `.runtime/python313`
- veröffentlichter und lokal bestätigter Installer-SHA-256: `edec09c4853aeae9ac36efb8c9f95b6b8e2fee65eee56d9767a8b7c69c574403`
- projektlokales `.venv`
- OpenSSL 3.0.21 vom 09.06.2026
- Windows-System-Truststore über `truststore 0.10.4`
- Zertifikats- und Hostnamenprüfung bleiben aktiv; kein `verify=False`

Der anschließende Bitstamp-TLS-Test und beide vollständigen Importe waren erfolgreich.

## Zeitkausalität und Tests

`pytest -q`: **18 passed**.

Zusätzlich zur bisherigen Suite wird geprüft:

- kanonische Metadaten und eindeutige Zeitstempel
- Data-Quality-Fehlererkennung ohne stille Reparatur
- nur abgeschlossene Weekly-/Monthly-Kerzen
- Bitstamp-Payload und UTC-Normalisierung
- mindestens 30 Tage Abstand zwischen Similarity-Vergleichsfällen
- vollständige Analyse am historischen Cutoff bleibt trotz extremer Mutation aller Zukunftspreise identisch
- bestätigte Swings/Fibonacci/Elliott nutzen keine späteren Pivots
- Backtest-Ausführung erfolgt erst auf der Folgekerze

Die echte Score-Historie umfasst 5.069 Point-in-Time-Berechnungen vom 21.09.2012 bis 07.08.2026. Für jeden Tag wurden nur bis dahin bestätigte Swings, ATHs, Fibonacci-Anker, Elliott-Szenarien und bereits auswertbare historische Vergleichsfälle verwendet.

## Mehrzyklus-Backtest

Ein Signal ist ein **Schwellenübertritt von unten**. Mehrere erneute Übertritte in derselben Marktphase können vorkommen und sind daher nicht vollständig unabhängige Ereignisse.

| Score | Signale | 365d n | positiv | Median 365d | Mean 365d | schlechtester weiterer DD |
|---:|---:|---:|---:|---:|---:|---:|
| >= 60 | 220 | 214 | 65,9 % | +59,3 % | +223,8 % | -80,9 % |
| >= 70 | 167 | 155 | 71,0 % | +88,8 % | +122,4 % | -75,5 % |
| >= 75 | 103 | 92 | 76,1 % | +124,8 % | +147,3 % | -74,1 % |
| >= 80 | 29 | 29 | 75,9 % | +116,4 % | +124,0 % | -73,1 % |
| >= 85 | 1 | 1 | 100 % | +169,3 % | +169,3 % | -4,3 % |
| >= 90 | 0 | 0 | – | – | – | – |

`>=85` besitzt mit n=1 sehr geringe Evidenz; `>=90` trat nie auf. Diese Schwellen sind historisch nicht bewertbar.

### Score 75 nach Horizont

| Horizont | n | positiv | Median | Mean | Min | Max |
|---:|---:|---:|---:|---:|---:|---:|
| 7 Tage | 103 | 49,5 % | -0,3 % | -1,0 % | -24,5 % | +18,9 % |
| 30 Tage | 103 | 42,7 % | -3,1 % | +0,3 % | -35,9 % | +73,0 % |
| 90 Tage | 102 | 57,8 % | +8,9 % | +10,8 % | -44,6 % | +206,6 % |
| 180 Tage | 102 | 67,6 % | +34,5 % | +64,9 % | -52,3 % | +724,9 % |
| 365 Tage | 92 | 76,1 % | +124,8 % | +147,3 % | -72,8 % | +611,3 % |
| 730 Tage | 80 | 83,8 % | +255,3 % | +543,3 % | -49,3 % | +2.945,6 % |

Die starken Means werden von der extremen Rechtsschiefe früher Bitcoin-Zyklen dominiert. Median, Quantile, Zyklusauswertung und OOS sind deshalb aussagekräftiger als der Mean.

### Drawdown nach Signal

Bei Score >=75:

- medianer maximaler Drawdown innerhalb der folgenden 730 Tage: **-27,9 %**
- schlechtester Drawdown: **-74,1 %**
- kurzfristig war der Median nach 30 Tagen noch negativ

Eine historische Value-Zone war damit häufig keine unmittelbare Bodenbestätigung.

## Portfoliovergleich

Die vorhandene Score-Simulation investiert bei Folgekerzen-Open je Signal 10 % des Anfangskapitals, bis das Kapital investiert ist, und verkauft nicht. Dadurch werden bei Score 75 zwar 103 statistische Schwellenübertritte analysiert, aber nur zehn kapitalisierte Käufe ausgeführt. Die Resultate sind nicht mit einer taktischen All-in/All-out-Strategie gleichzusetzen.

| Ansatz, Gesamtzeitraum | Total Return | CAGR | Max Drawdown |
|---|---:|---:|---:|
| Score >=75 | +29.447 % | 50,7 % | -83,4 % |
| Buy & Hold | +527.791 % | 85,5 % | -84,9 % |
| monatliches DCA | +23.747 % | 48,4 % | -82,8 % |

Buy & Hold war nach CAGR klar überlegen. Der Score senkte den Maximum Drawdown in dieser Ausführung nur geringfügig.

## Einfache Baselines

| Regel | Signale | 365d n | positiv | Median 365d | schlechtester weiterer DD |
|---|---:|---:|---:|---:|---:|
| Weekly RSI < 35 | 17 | 12 | 91,7 % | +56,3 % | -53,6 % |
| Weekly RSI < 30 | 4 | 3 | 100 % | +92,1 % | -17,6 % |
| Drawdown <= -30 % | 33 | 25 | 20,0 % | -56,1 % | -80,6 % |
| Drawdown <= -50 % | 45 | 40 | 52,5 % | +12,4 % | -73,0 % |
| Drawdown <= -70 % | 21 | 21 | 85,7 % | +49,7 % | -54,9 % |

Weekly RSI <30 ist wegen n=3 auswertbaren 365-Tage-Fällen nicht belastbar. Drawdown <=-70 % und Weekly RSI <35 zeigen jedoch, dass einfache Regeln einen erheblichen Teil der historischen Information erfassen. Der komplexe Score ist nicht eindeutig überlegen.

## Marktzyklen

Nachvollziehbare Grenzen wurden an Bitcoin-Halving-/Regimezeitpunkten und dem 2021er Hoch gesetzt:

- early Bitcoin: bis 27.11.2012
- 2013/2014: 28.11.2012–08.07.2016
- 2017/2018: 09.07.2016–10.05.2020
- 2020/2021: 11.05.2020–09.11.2021
- 2021/2022: 10.11.2021–19.04.2024
- current cycle: ab 20.04.2024

Score-75-Signale je Segment: 26, 16, 17, 17 und 27; im frühen Segment trat Score 75 nicht auf. Das Signal kommt über mehrere Zyklen vor, seine Performance ist aber nicht stabil gleich.

## Walk-Forward / Out-of-Sample

Parameter und Schwelle 75 blieben in allen Folds unverändert.

| Fold | Trainingsende | Testzeitraum | OOS Signale | 365d n | positiv | Median 365d | medianer weiterer DD | Score-CAGR | Buy&Hold-CAGR |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 08.07.2016 | 09.07.2016–10.05.2020 | 16 | 16 | 87,5 % | +320,7 % | -53,0 % | 69,4 % | 95,8 % |
| 2 | 10.05.2020 | 11.05.2020–19.04.2024 | 34 | 34 | 76,5 % | +143,2 % | -10,1 % | 62,2 % | 65,6 % |
| 3 | 19.04.2024 | 20.04.2024–07.08.2026 | 27 | 16 | 50,0 % | +16,4 % | -43,2 % | -2,6 % | +0,7 % |

Der deutliche Leistungsabfall im jüngsten OOS-Fenster ist der stärkste Gegenbeleg gegen eine robuste universelle Score-Wirkung. Für 11 der 27 aktuellen Signale ist der 365-Tage-Horizont noch nicht vollständig beobachtbar.

## Score-Komponenten

Jede Komponente wurde isoliert bei 75 % ihres eigenen Maximalbeitrags betrachtet. Das ist eine Diagnose, keine Parameteroptimierung.

| Komponente | Signale | 365d n | positiv | Median 365d | schlechtester DD |
|---|---:|---:|---:|---:|---:|
| Trend | 58 | 54 | 63,0 % | +90,6 % | -71,2 % |
| Similarity | 197 | 180 | 66,1 % | +39,7 % | -76,2 % |
| Fibonacci | 140 | 128 | 69,5 % | +71,1 % | -75,9 % |
| Elliott/ABC | 115 | 105 | 66,7 % | +54,4 % | -84,4 % |
| Momentum/RSI | 171 | 151 | 57,6 % | +38,6 % | -78,4 % |
| Volumen | 472 | 444 | 73,0 % | +85,2 % | -85,1 % |
| Support/Resistance | 0 | 0 | – | – | – |
| Risk/Reward | 0 | 0 | – | – | – |

Support/Resistance und Risk/Reward sind im V1-Score diskret bzw. konstant und erreichen isoliert die 75-%-Schwelle nie. Das zeigt geringe diagnostische Trennschärfe. Der Volumenbefund ist wegen 472 häufigen Übertritten und starker Zyklusabhängigkeit nicht als unabhängiger Alpha-Nachweis zu lesen.

## Elliott mit und ohne Komponente

| Variante | Signale | 365d n | positiv | Median 365d | medianer DD | schlechtester DD |
|---|---:|---:|---:|---:|---:|---:|
| vollständiger Score | 103 | 92 | 76,1 % | +124,8 % | -27,9 % | -74,1 % |
| ohne Elliott, auf 100 skaliert | 90 | 86 | 73,3 % | +106,2 % | -20,0 % | -74,1 % |

Mit Elliott sind 365-Tage-Trefferquote und Median etwas höher, aber der mediane Drawdown schlechter. Auf 90 und 180 Tage war die Variante ohne Elliott teilweise besser. Die Confidence-Verteilung ist außerdem grob und häufig bei 61,1 %, 65 % oder 100 %, also nicht statistisch kalibriert. Ein robuster Elliott-Zusatznutzen ist nicht bewiesen.

## Historical Similarity und Sample Size

Vergleichsfälle werden nach Distanz sortiert, müssen jetzt aber mindestens 30 Tage auseinanderliegen. Dadurch zählen aufeinanderfolgende Tage desselben Crashs nicht mehr als unabhängige Beobachtungen. Die Ausgabe enthält Similarity und Rohdistanz.

Evidenzkennzeichnung:

- n < 5: sehr geringe Evidenz
- n 5–9: geringe Evidenz
- n 10–19: moderate Evidenz
- n >= 20: höhere historische Evidenz

Am letzten abgeschlossenen Datenpunkt 07.08.2026 fand der Analyzer n=30 geclusterte historische Fälle. 26 von 30 waren nach 365 Tagen positiv; das ist eine historische Trefferquote, **keine 86,7-%-Prognose**. Der schlechteste anschließende Drawdown dieser Fälle betrug -76,2 %.

## Aktueller Analyse-Snapshot

- letzter abgeschlossener Daily-Datenpunkt: 07.08.2026 UTC
- BTC/USD Close: 64.877,77 USD
- Opportunity Score: 72,51 / 100 – interessante Kaufzone
- Value: MEDIUM
- Confirmation: LOW
- Risk: MEDIUM
- primäres Regelszenario: mögliche Impuls-/Wave-4-Struktur
- Elliott-Confidence: 100 % innerhalb der regelbasierten Szenariomenge; **nicht** als Marktwahrscheinlichkeit interpretieren
- Invalidierung des Szenarios: Bruch des strukturellen Extrempunkts 57.734,63 USD

## Bekannte Schwächen

1. Die frühe Bitstamp-Historie ist extrem illiquide und erzeugt sehr große langfristige Returns und Gaps.
2. Schwellenübertritte sind zeitlich korreliert und nicht vollständig unabhängige Stichproben.
3. Das Portfolio-Modell verkauft nicht und investiert maximal zehn Tranchen; es ist primär ein Vergleichs-Smoke, keine fertige Handelsstrategie.
4. Gebühren, Slippage, Steuern und Liquiditätsrestriktionen fehlen.
5. Der Score enthält diskrete oder konstante V1-Komponenten; er ist nicht probabilistisch kalibriert.
6. Elliott-Confidence ist regelbasiert und teilweise überkonzentriert bei 100 %.
7. Der aktuelle OOS-Zyklus zeigt keine robuste Überlegenheit.
8. Bitstamp ist eine einzelne Exchange-Historie. Kraken ist als zweiter Provider vorhanden, aber es wurde kein synthetisches Exchange-Splicing vorgenommen, um Quellenwechsel zu vermeiden.
9. Bei wenigen Fällen können Trefferquoten stark schwanken; deshalb wird Sample Size immer separat angezeigt.

## Schlussfolgerung

Der Bitcoin Cycle Analyzer besitzt **deskriptiven Informationswert**: Er bündelt Trend, historische Bewertung, Fibonacci, Similarity und Risikokontext nachvollziehbar und identifiziert über mehrere Zyklen häufig langfristig positive Value-Phasen. Er liefert jedoch aktuell **keinen robusten Beweis für einen eigenständigen, stabilen Prognose- oder Renditevorteil** gegenüber Buy & Hold und einfachen Regeln.

Besonders wichtig: Ein hoher Score war historisch mit erheblichen weiteren Drawdowns vereinbar. Der Analyzer eignet sich in Version 1.0.0 daher als transparentes Research- und Risikokontextwerkzeug, nicht als alleinige Kaufbestätigung und nicht als Anlageberatung.
