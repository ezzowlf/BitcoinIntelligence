from __future__ import annotations

MODELS=("CORE","CORE + MACRO","CORE + ETF","CORE + ONCHAIN","CORE + DERIVATIVES","CORE + NEWS","CORE + ALL AVAILABLE")
HORIZONS=(7,30,90,180,365)


def empty_validation_matrix() -> dict:
    return {model:{"status":"UNAVAILABLE","horizons":{str(h):None for h in HORIZONS},"drawdown":None,
                   "entry_timing":None,"cycle_classification":None,"independent_episodes":0} for model in MODELS}


def ablation_plan(available: set[str]) -> list[str]:
    return ["FULL"]+[f"FULL - {name}" for name in ("MACRO","ETF","ONCHAIN","DERIVATIVES","NEWS") if name in available]
