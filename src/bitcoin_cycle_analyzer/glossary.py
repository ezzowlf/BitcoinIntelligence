"""Plain-language glossary for jargon terms shown in the UI (Simple Mode
tooltips, Teil 49/88 of the UX brief). Static text only — never computed,
never a source of truth for any decision."""

GLOSSARY = {
    "200W": "Durchschnittlicher BTC-Kurs der letzten 200 Wochen. Historisch eine wichtige langfristige Referenz — aber kein automatisches Kaufsignal.",
    "200D": "Durchschnittlicher BTC-Kurs der letzten 200 Tage. Eine kurzfristigere Trendreferenz als 200W.",
    "RSI": "Misst, wie schnell und wie weit sich der Kurs zuletzt bewegt hat. Niedrig = starker Verkaufsdruck zuletzt, hoch = starker Kaufdruck zuletzt. Kein Signal für sich allein.",
    "Drawdown": "Wie weit der aktuelle Kurs unter seinem Allzeithoch liegt, in Prozent.",
    "Cycle": "Eine vollständige Bitcoin-Boom-Bust-Periode, ungefähr begrenzt durch aufeinanderfolgende Halvings und größere Hoch-/Tiefpunkte. Bitcoin hatte bisher nur wenige vollständige Zyklen — Zyklusvergleiche sind beschreibend, nicht statistisch präzise zu verstehen.",
    "Regime": "Der aktuelle grobe Marktcharakter (z. B. Bär, Erholung, Bulle), wie ihn die Engines einordnen.",
    "Elliott": "Ein Wellenzählungs-Framework zur Beschreibung der Kursstruktur. Hier immer eine Hypothese, nie eine Gewissheit — siehe 'Primär'- und 'Alternativ'-Zählungen.",
    "Wave C": "Das letzte Segment einer ABC-Korrektur. Wenn eine Welle C abschließt, könnte die Korrektur sich dem Ende nähern — bestätigt ist das aber erst, wenn der Kurs tatsächlich dreht.",
    "Invalidation": "Der Kursstand, ab dem die aktuelle strukturelle These als widerlegt gilt.",
    "Confirmation": "Was noch passieren muss (z. B. ein Wochenschluss über einer Marke), bevor eine Idee als bestätigt statt nur als interessant gilt.",
    "Reclaim": "Der Kurs schließt wieder über einer zuvor verlorenen Marke — wird oft als Bestätigungssignal genutzt.",
    "Evidence Family": "Eine von 7 unabhängigen Kategorien (Zyklus, Struktur, Bewertung, Momentum, Historie, Makro, Positionierung), die sicherstellt, dass korrelierte Signale (z. B. RSI und Bollinger-Bänder, die Ähnliches messen) nie doppelt als unabhängige Bestätigung gezählt werden.",
    "Confluence": "Mehrere unabhängige Faktoren, die auf denselben Kursbereich hindeuten — je mehr unabhängige Faktoren übereinstimmen, desto stärker die Zone.",
}


def tooltip_span(term: str) -> str:
    text = GLOSSARY.get(term, "")
    safe = text.replace('"', "&quot;")
    return f'<span title="{safe}" style="border-bottom:1px dotted var(--muted);cursor:help">{term}</span>'
