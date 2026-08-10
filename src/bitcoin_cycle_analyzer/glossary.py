"""Plain-language glossary for jargon terms shown in the UI (Simple Mode
tooltips, Teil 49/88 of the UX brief). Static text only — never computed,
never a source of truth for any decision."""

GLOSSARY = {
    "200W": "Average BTC price over the last 200 weeks. Historically an important long-term reference — but not an automatic buy signal.",
    "200D": "Average BTC price over the last 200 days. A shorter-term trend reference than 200W.",
    "RSI": "Measures how fast and how far price has moved recently. Low = heavy recent selling, high = heavy recent buying. Not a signal by itself.",
    "Drawdown": "How far the current price is below its all-time high, in percent.",
    "Cycle": "A full Bitcoin boom-bust period, roughly bounded by consecutive halvings and major tops/bottoms. Bitcoin has had only a handful of complete cycles — treat cycle comparisons as descriptive, not statistically precise.",
    "Regime": "The current broad market character (e.g. bear, recovery, bull) as read by the engines.",
    "Elliott": "A wave-counting framework for describing price structure. Always a hypothesis here, never a certainty — see 'Primary' and 'Alternative' counts.",
    "Wave C": "The final leg of an ABC correction. If a Wave C is completing, the correction may be near its end — but this is not confirmed until price actually reverses.",
    "Invalidation": "The price level at which the current structural thesis is considered wrong.",
    "Confirmation": "What still needs to happen (e.g. a weekly close above a level) before an idea is treated as validated rather than just interesting.",
    "Reclaim": "Price closing back above a level it had previously lost — often used as a confirmation trigger.",
    "Evidence Family": "One of 7 independent categories (Cycle, Structure, Valuation, Momentum, Historical, Macro, Positioning) used so that correlated signals (like RSI and Bollinger Bands, which measure similar things) are never double-counted as independent confirmations.",
    "Confluence": "Multiple independent factors agreeing on the same price area — the more independent factors agree, the stronger the zone.",
}


def tooltip_span(term: str) -> str:
    text = GLOSSARY.get(term, "")
    safe = text.replace('"', "&quot;")
    return f'<span title="{safe}" style="border-bottom:1px dotted var(--muted);cursor:help">{term}</span>'
