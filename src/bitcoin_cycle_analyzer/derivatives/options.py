def options_state(iv=None, put_call=None, skew_25d=None, term_structure=None) -> dict:
    values = {"implied_volatility": iv, "put_call_ratio": put_call, "skew_25d": skew_25d, "term_structure": term_structure}
    return {"status": "UNAVAILABLE" if all(value is None for value in values.values()) else "AVAILABLE", **values, "note": "Max pain is descriptive only and never a standalone signal."}

