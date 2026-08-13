"""Explain & Action Layer (German-language Simple Mode).

Pure presentation/translation layer. Every function here only reshapes
facts that already exist in `decision_intelligence`'s DecisionState,
ExplanationFacts, MACRO 7's Elliott/cycle context, or Auftrag 3's event
data — nothing here computes a new decision, indicator, or Elliott wave.
Internal engine states stay English; this module only builds the German
strings a Simple Mode user reads.
"""
from __future__ import annotations

DECISION_LABELS_DE = {
    "STRONG_BUY": "STARKES KAUFSIGNAL",
    "BUY": "KAUFSIGNAL AKTIV",
    "ACCUMULATE": "AKKUMULATION INTERESSANT",
    "WATCH": "BEOBACHTEN",
    "WAIT": "WARTEN",
    "REDUCE": "REDUZIEREN",
    "TAKE_PROFIT": "GEWINNMITNAHME",
    "HIGH_RISK": "HOHES RISIKO",
    "SELL": "VERKAUFEN",
    "NO_EDGE": "KEIN VORTEIL ERKENNBAR",
}

MACRO_ACTION_LABELS_DE = {"ACCUMULATE": "AKKUMULATION INTERESSANT", "REDUCE": "REDUZIEREN", "HOLD": "HALTEN", "WAIT": "WARTEN"}

TIMING_LABELS_DE = {"CONFIRMED": "BESTÄTIGT", "CONFIRMING": "BESTÄTIGT SICH", "EARLY": "FRÜHE PHASE", "WAIT": "ABWARTEN"}

RISK_LABELS_DE = {"LOW": "NIEDRIG", "CAUTION": "VORSICHT", "NORMAL": "NORMAL", "MODERATE": "MODERAT", "HIGH": "HOCH", "EXTREME": "EXTREM"}

PLAYBOOK_NAME_LABELS_DE = {
    "CYCLE_BOTTOM_ENTRY": "Einstieg am Zyklustief",
    "RECOVERY_ENTRY": "Einstieg nach Erholung",
    "WAVE2_RETRACEMENT_ENTRY": "Einstieg bei Welle-2-Rücksetzer",
    "BREAKOUT_RECLAIM_ENTRY": "Einstieg nach Ausbruch/Rückeroberung",
    "DEEP_VALUE_ACCUMULATION": "Akkumulation im Tiefstwertbereich",
    "MAJOR_SUPPORT_RETEST": "Einstieg bei Test der Hauptunterstützung",
    "POST_CAPITULATION_ENTRY": "Einstieg nach Kapitulation",
}

SCENARIO_STATUS_LABELS_DE = {"ACTIVE": "AKTIV", "WATCH": "BEOBACHTEN", "DORMANT": "INAKTIV", "INVALIDATED": "UNGÜLTIG"}

# Display-only translation of MACRO 7 scenario names. The engine's own scenario["name"] values
# (asserted on directly in tests/test_macro7.py) are never changed - this dict only relabels
# them for the UI.
SCENARIO_NAME_LABELS_DE = {
    "BULL RECOVERY": "BULLISCHE ERHOLUNG",
    "BASE CONSOLIDATION": "BASISKONSOLIDIERUNG",
    "DEEP BEAR": "TIEFER BÄRENMARKT",
    "EXTREME CYCLE": "EXTREMER ZYKLUS",
}

ENTRY_STATUS_LABELS_DE = {
    "CONFIRMED": "Einstieg bestätigt",
    "WAITING_FOR_CONFIRMATION": "Noch kein Einstieg bestätigt",
    "NOT_CONFIRMED": "Nicht bestätigt",
    "NOT_APPLICABLE": "Nicht zutreffend",
}

TRIGGER_LABELS_DE = {
    "weekly_reclaim": "Bitcoin schließt auf Wochenbasis über der Bestätigungsmarke",
    "structure_reclaim": "Der Kurs überwindet den nächsten wichtigen Widerstand",
    "higher_low": "Ein neues, höheres Tief wird bestätigt",
    "momentum_recovery": "Das Momentum dreht (Wochen-RSI erholt sich)",
    "swing_low_confirmed": "Ein bestätigtes Tief liegt vor",
}

ELLIOTT_BASICS_DE = (
    "Ein typischer bullischer Impuls besteht aus fünf Wellen: 1 ↑, 2 ↓, 3 ↑, 4 ↓, 5 ↑. "
    "Danach folgt häufig eine Korrektur aus drei Wellen: A ↓, B ↑, C ↓. "
    "Wichtig: Elliott ist kein sicherer Fahrplan, sondern eine Strukturhypothese, die sich "
    "mit neuen Kursdaten ändern kann."
)

# Generic, textbook "what conventionally follows" — NOT a price prediction, only shown when it
# matches the engine's own cycle bucket classification (never invented independently of it).
_ROADMAP_AFTER_DE = {
    "DEEP_BEAR_BOTTOM_SEARCH": ["Wenn die vermutete C-Welle tatsächlich endet, wäre als Nächstes ein neuer Impuls (Welle 1) denkbar.", "Danach folgt typischerweise ein Rücksetzer (Welle 2).", "Anschließend wäre eine stärkere Bewegung (Welle 3) möglich."],
    "LATE_BEAR": ["Wenn die Korrektur (ABC) ausläuft, wäre ein neuer Aufwärtsimpuls möglich.", "Dieser müsste sich aber erst durch eine bestätigte Strukturänderung zeigen."],
    "EARLY_BULL": ["Nach einer laufenden Welle 1 wäre ein Rücksetzer (Welle 2) typisch.", "Danach oft die stärkere Welle 3."],
    "MID_BULL": ["Nach der aktuell vermuteten Welle 3 wäre ein Rücksetzer (Welle 4) typisch.", "Danach eine abschließende Welle 5."],
    "LATE_BULL_DISTRIBUTION": ["Nach einer möglichen Welle 5 wäre eine größere Korrektur (ABC) typisch.", "Das System beobachtet hierfür Anzeichen einer Erschöpfung."],
    "TRANSITION": ["Die Struktur ist aktuell nicht eindeutig genug für eine Roadmap-Aussage."],
}


def translate_decision(decision: str) -> str:
    return DECISION_LABELS_DE.get(decision, decision)


def translate_macro_action(action: str) -> str:
    return MACRO_ACTION_LABELS_DE.get(action, action)


def translate_timing(timing: str) -> str:
    return TIMING_LABELS_DE.get(timing, timing)


def translate_risk(risk: str) -> str:
    return RISK_LABELS_DE.get(risk, risk)


def translate_scenario_status(status: str) -> str:
    return SCENARIO_STATUS_LABELS_DE.get(status, status)


def translate_scenario_name(name: str) -> str:
    return SCENARIO_NAME_LABELS_DE.get(name, name)


MARKET_PHASE_LABELS_DE = {
    "ACCUMULATION": "AKKUMULATION",
    "CAPITULATION": "KAPITULATION",
    "EARLY_RECOVERY": "FRÜHE ERHOLUNG",
    "BEAR": "BÄRENMARKT",
    "BULL": "BULLENMARKT",
    "EXPANSION": "EXPANSION",
    "TRANSITION": "ÜBERGANG",
}

FRESHNESS_LABELS_DE = {"LIVE": "LIVE", "DELAYED": "VERZÖGERT", "STALE": "VERALTET", "OFFLINE": "OFFLINE"}

# Regex patterns matching the fixed English sentence templates the frozen macro7 engine
# produces in its "why" facts (e.g. macro7/engine.py). We never touch that frozen file -
# these facts are only reworded here, after they leave the engine, for display purposes.
# Any pattern that doesn't match is returned unchanged (safe fallback, never crashes).
import re as _re

_WHY_FACT_PATTERNS = [
    (_re.compile(r"^Macro phase: (.+)$"), lambda m: f"Marktphase: {MARKET_PHASE_LABELS_DE.get(m.group(1), m.group(1))}"),
    (_re.compile(r"^ATH drawdown: (.+)$"), lambda m: f"Rückgang seit dem Allzeithoch: {m.group(1)}"),
    (_re.compile(r"^Distance to 200W: (.+)$"), lambda m: f"Abstand zum 200-Wochen-Durchschnitt: {m.group(1)}"),
    (_re.compile(r"^Weekly RSI: (.+)$"), lambda m: f"Wochen-RSI: {m.group(1)}"),
]


def translate_why_fact(text: str) -> str:
    for pattern, build in _WHY_FACT_PATTERNS:
        m = pattern.match(text)
        if m:
            return build(m)
    return text


def translate_freshness(freshness: str) -> str:
    return FRESHNESS_LABELS_DE.get(freshness, freshness)


def translate_regime(regime: str) -> str:
    return MARKET_PHASE_LABELS_DE.get(regime, regime)


def translate_playbook_name(name: str) -> str:
    return PLAYBOOK_NAME_LABELS_DE.get(name, name.replace("_", " ").title())


def translate_entry_status(status: str) -> str:
    return ENTRY_STATUS_LABELS_DE.get(status, status.replace("_", " "))


def zone_message_de(zone: dict | None) -> str:
    if zone is None or zone.get("lower") is None:
        return "Aktuell keine gültige Kaufzone."
    return f"Interessante Zone: ${zone['lower']:,.0f} – ${zone['upper']:,.0f} ({zone['zone_type'].replace('_',' ').title()})"


def what_must_happen_de(confirmation: dict) -> dict:
    missing = [TRIGGER_LABELS_DE.get(name, t["description"]) for name, t in confirmation["triggers"].items() if not t["met"]]
    met = [TRIGGER_LABELS_DE.get(name, t["description"]) for name, t in confirmation["triggers"].items() if t["met"]]
    return {
        "missing": missing,
        "met": met,
        "closing": "Wenn das passiert, kann das System auf ein Kaufsignal wechseln." if missing else "Alle beobachteten Bestätigungen liegen bereits vor.",
    }


def why_text_de(decision_intel: dict, decision_explanation: dict) -> str:
    """3–5 sentence German narrative built entirely from canonical facts already
    in DecisionState/ExplanationFacts — no new computation, only translation."""
    d = decision_intel
    bucket = d["cycle_bucket"].replace("_", " ").lower()
    zone = d.get("active_zone")
    supporting = d["evidence_agreement"]["supporting_count"]
    contradicting = d["evidence_agreement"]["contradicting_count"]
    sentences = [f"Bitcoin befindet sich aktuell in einer Phase, die das System als '{bucket}' einordnet."]
    if zone is not None and zone.get("lower") is not None:
        sentences.append(f"Der Kurs liegt in einer Zone, die historisch als interessant gilt (${zone['lower']:,.0f} – ${zone['upper']:,.0f}).")
    else:
        sentences.append("Der Kurs liegt aktuell in keiner besonders hervorgehobenen Zone.")
    sentences.append(f"{supporting} unabhängige Faktoren sprechen aktuell dafür" + (f", {contradicting} dagegen." if contradicting else "."))
    if d["entry_status"] == "WAITING_FOR_CONFIRMATION":
        sentences.append("Für einen bestätigten Einstieg fehlt aber noch eine klare Bestätigung der Preisstruktur.")
    elif d["entry_status"] == "CONFIRMED":
        sentences.append("Die nötigen Bestätigungen liegen bereits vor.")
    sentences.append(f"Deshalb lautet die aktuelle Entscheidung: {translate_decision(d['decision'])}.")
    return " ".join(sentences)


def why_not_now_de(decision_intel: dict) -> str:
    d = decision_intel
    zone = d.get("active_zone")
    if zone is None:
        return "Weil aktuell keine besonders interessante Zone vorliegt, sucht das System bewusst nach besseren Bedingungen."
    return "Weil die Zone zwar interessant ist, aber noch keine bestätigte Umkehr der Kursstruktur vorliegt. Ein Einstieg jetzt wäre ein früher, unbestätigter Trade."


def buy_playbook_de(decision_intel: dict) -> dict:
    d = decision_intel
    zone = d.get("active_zone") or {}
    targets = d.get("targets", [])
    reasons = [f"{fam} unterstützt" for fam in d["evidence_agreement"]["supporting_families"]]
    return {
        "entry_type": (translate_playbook_name(d["playbooks_matched"][0]["name"]) if d.get("playbooks_matched") else "Bestätigter Einstieg"),
        "entry_zone": f"${zone.get('lower', 0):,.0f} – ${zone.get('upper', 0):,.0f}" if zone.get("lower") is not None else "—",
        "why": reasons or ["Ausreichende Bestätigung liegt vor"],
        "invalidation": f"${d['invalidation_level']:,.0f}" if d.get("invalidation_level") is not None else "—",
        "first_target": f"${targets[0]['price']:,.0f}" if targets else "—",
        "risk": translate_risk(d.get("risk_state", "—")),
        "dont_chase_above": f"${zone.get('upper', 0):,.0f}" if zone.get("upper") is not None else "—",
    }


def elliott_roadmap_de(elliott_ctx: dict) -> dict:
    bucket = elliott_ctx["cycle_bucket"]
    return {
        "current_hypothesis": elliott_ctx["engine_primary"] or "Unbestätigt",
        "consistency_note": ("Die Elliott-Hypothese passt zur aktuellen Zyklusphase." if elliott_ctx["consistency"] == "CONSISTENT" else "Die Elliott-Hypothese passt aktuell NICHT eindeutig zur Zyklusphase — als Konflikt markiert."),
        "possible_next_steps": _ROADMAP_AFTER_DE.get(bucket, _ROADMAP_AFTER_DE["TRANSITION"]),
        "limitation": "Hinweis: Das System unterscheidet aktuell nur zwischen wenigen Strukturhypothesen (z.B. ABC-Korrektur vs. Wellen-4-Erholung). Eine vollständige Wellen-1-bis-5-Erkennung ist (noch) nicht möglich.",
    }


def event_relevance_de(recent_events, decision_changes: bool = False) -> str:
    if recent_events is None or len(recent_events) == 0:
        return "Aktuell gibt es keine relevanten Event-Daten, die die Entscheidung verändern."
    return "Diese Ereignisse sind Kontext, ändern aber die aktuelle Entscheidung nicht." if not decision_changes else "Diese Ereignisse werden aktuell berücksichtigt."
