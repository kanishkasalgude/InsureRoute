"""
Dynamic insurance premium calculation.
Base rates per mode × risk loading × cargo multiplier × coverage type.
"""

COVERAGE_MULTIPLIERS = {
    "basic": 1.0,        # Named perils only
    "comprehensive": 1.6, # All perils except war/nuclear
    "all_risk": 2.2      # True all-risk, highest protection
}

CARGO_RISK_MULTIPLIERS = {
    "electronics": 1.4, "pharmaceuticals": 1.6, "automotive": 1.0,
    "fmcg": 1.1, "chemicals": 1.5, "textiles": 0.9, "perishables": 1.8
}

def calculate_dynamic_premium(route_risk_score: float, cargo_type: str, 
                               cargo_value_inr: float, coverage_type: str,
                               transport_modes: list[str]) -> dict:
    # Base rate: weighted average across modes used
    mode_base_rates = {"road": 0.003, "rail": 0.0015, "air": 0.002, "sea": 0.0025}
    if not transport_modes:
        transport_modes = ["road"]
    base_rate = sum(mode_base_rates.get(m, 0.003) for m in transport_modes) / len(transport_modes)
    
    # Risk loading: exponential above threshold
    if route_risk_score < 0.3:
        risk_loading = 1.0
    elif route_risk_score < 0.6:
        risk_loading = 1.0 + (route_risk_score - 0.3) * 2.0
    else:
        risk_loading = 1.6 + (route_risk_score - 0.6) * 4.0  # Steep above 0.6
    
    cargo_multiplier = CARGO_RISK_MULTIPLIERS.get(cargo_type, 1.0)
    coverage_multiplier = COVERAGE_MULTIPLIERS.get(coverage_type, 1.0)
    
    final_rate = base_rate * risk_loading * cargo_multiplier * coverage_multiplier
    premium_inr = cargo_value_inr * final_rate
    
    # Minimum premium floor
    premium_inr = max(premium_inr, 500)
    
    # Risk classification
    if route_risk_score < 0.3: risk_class = "LOW"
    elif route_risk_score < 0.6: risk_class = "MEDIUM"
    elif route_risk_score < 0.8: risk_class = "HIGH"
    else: risk_class = "CRITICAL"
    
    return {
        "base_rate_pct": round(base_rate * 100, 4),
        "risk_loading_factor": round(risk_loading, 3),
        "cargo_multiplier": cargo_multiplier,
        "coverage_multiplier": coverage_multiplier,
        "final_rate_pct": round(final_rate * 100, 4),
        "premium_inr": round(premium_inr, 2),
        "risk_class": risk_class,
        "route_risk_score": route_risk_score,
        "breakdown": {
            "base_premium": round(cargo_value_inr * base_rate, 2),
            "risk_loading_amount": round(cargo_value_inr * base_rate * (risk_loading - 1), 2),
            "cargo_adjustment": round(cargo_value_inr * base_rate * risk_loading * (cargo_multiplier - 1), 2),
            "coverage_adjustment": round(premium_inr - cargo_value_inr * base_rate * risk_loading * cargo_multiplier, 2)
        }
    }