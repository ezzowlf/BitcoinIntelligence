def annualized_basis(spot: float, future: float, days_to_expiry: int) -> float:
    if spot <= 0 or days_to_expiry <= 0:
        raise ValueError("positive spot and days_to_expiry required")
    return (future / spot - 1) * 365 / days_to_expiry

