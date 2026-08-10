"""Decision Intelligence layer for BitcoinElliot.

This package NEVER recomputes price analysis. It is a pure consumer of the
existing frozen/research engines (CONTROL 3, SPECIALIST 5, FUSION 6, MACRO 7,
FullHistoryElliottEngine, HistoricalEntryQuality, cycle history) and turns
their already-computed fields into one coherent, explainable causal chain:

    CYCLE -> REGIME -> ELLIOTT CONTEXT -> STRUCTURAL ZONE -> EVIDENCE
    -> ENTRY PLAYBOOK -> CONFIRMATION -> INVALIDATION -> TARGET -> DECISION

Nothing here is a shadow engine: every fact traces back to a field already
produced by `analyze_intelligence(...)`. See RULE_REGISTRY in rules.py for
the auditable list of decision rules this package adds.
"""
from .evidence import assess_evidence_families, EVIDENCE_FAMILIES
from .cycle_elliott_context import classify_cycle_bucket, elliott_cycle_context
from .zones import build_structural_zones
from .confirmation import evaluate_confirmation
from .playbooks import match_playbooks, ENTRY_PLAYBOOKS
from .decision_engine import build_decision_state
from .explanation import build_explanation_facts
from .rules import RULE_REGISTRY

__all__ = [
    "assess_evidence_families", "EVIDENCE_FAMILIES",
    "classify_cycle_bucket", "elliott_cycle_context",
    "build_structural_zones",
    "evaluate_confirmation",
    "match_playbooks", "ENTRY_PLAYBOOKS",
    "build_decision_state",
    "build_explanation_facts",
    "RULE_REGISTRY",
]
