from __future__ import annotations
from .funding import analyze_funding
from .open_interest import analyze_open_interest


def analyze_derivatives(as_of, funding=None, open_interest=None, basis=None, liquidations=None, options=None) -> dict:
    modules = {"funding": analyze_funding(funding, as_of), "open_interest": analyze_open_interest(open_interest, as_of), "basis": {"status": "UNAVAILABLE"} if basis is None else basis, "liquidations": {"status": "UNAVAILABLE"} if liquidations is None else liquidations, "options": {"status": "UNAVAILABLE"} if options is None else options}
    available = sum(item.get("status") == "AVAILABLE" for item in modules.values())
    return {"status": "AVAILABLE" if available else "UNAVAILABLE", "score": None, "coverage": available / len(modules), "modules": modules}

