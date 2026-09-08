"""
pricing_engine.py — Dynamic insurance hedge cost calculator.

Formula
-------
Base Premium   = Cargo Value × Disruption Probability × Base Rate
Weather Mult   = varies by cargo type (humidity/rain/wind sensitivity)
Cargo Mult     = varies by cargo type (fragility, perishability, value density)
Temp Mult      = varies by cargo type (temperature sensitivity)
Hedge Cost (H) = Base × Weather Mult × Cargo Mult × Temp Mult

Also computes before/after rerouting comparison.
"""

from dataclasses import dataclass, field
from typing import Dict

#  Cargo type profiles with actuarial weighting 
# Each cargo type defines:
#   base_rate        – fraction of cargo value × probability → base premium
#   weather_weight   – sensitivity to rain/humidity (monsoon)
#   temp_weight      – sensitivity to temperature extremes
#   fragility_weight – mechanical shock / handling risk
#   perishable_weight– spoilage / time-critical risk
#   value_density    – high-value-per-kg multiplier
#   description      – human-readable label
CARGO_PROFILES = {
    "Standard": {
        "base_rate":         0.08,
        "weather_weight":    1.0,
        "temp_weight":       1.0,
        "fragility_weight":  1.0,
        "perishable_weight": 1.0,
        "value_density":     1.0,
        "description":       "General purpose cargo with standard risk profile",
    },
    "Electronics": {
        "base_rate":         0.10,
        "weather_weight":    1.65,   # very sensitive to humidity/rain
        "temp_weight":       1.25,   # moderate temp sensitivity
        "fragility_weight":  1.55,   # shock-sensitive components
        "perishable_weight": 1.0,
        "value_density":     1.40,   # high value per kg
        "description":       "High-value electronics — sensitive to humidity, shock & ESD",
    },
    "Pharmaceuticals": {
        "base_rate":         0.12,
        "weather_weight":    1.35,   # moderate rain sensitivity
        "temp_weight":       1.80,   # very temperature-critical (cold chain)
        "fragility_weight":  1.20,
        "perishable_weight": 1.70,   # time-critical, expiry risk
        "value_density":     1.50,   # extremely high value density
        "description":       "Cold-chain pharmaceuticals — temperature & time critical",
    },
    "Perishable Goods": {
        "base_rate":         0.11,
        "weather_weight":    1.30,
        "temp_weight":       1.75,   # very temperature sensitive
        "fragility_weight":  1.10,
        "perishable_weight": 1.85,   # highest spoilage risk
        "value_density":     1.10,
        "description":       "Fresh produce & perishables — highest spoilage sensitivity",
    },
    "Heavy Machinery": {
        "base_rate":         0.07,
        "weather_weight":    1.15,   # moderate — wind is the main concern
        "temp_weight":       1.05,
        "fragility_weight":  1.35,   # mechanical alignment risk
        "perishable_weight": 1.0,
        "value_density":     1.20,
        "description":       "Industrial machinery — wind & vibration sensitive, oversize load",
    },
    "Textiles": {
        "base_rate":         0.06,
        "weather_weight":    1.45,   # high moisture sensitivity
        "temp_weight":       1.10,
        "fragility_weight":  1.0,
        "perishable_weight": 1.0,
        "value_density":     0.90,
        "description":       "Fabric & garments — moisture absorption risk",
    },
    "Chemicals": {
        "base_rate":         0.13,
        "weather_weight":    1.25,
        "temp_weight":       1.60,   # reaction risk at high temp
        "fragility_weight":  1.45,   # spill/leak risk
        "perishable_weight": 1.15,
        "value_density":     1.30,
        "description":       "Hazardous chemicals — temperature reaction & spill risk",
    },
    "Automotive Parts": {
        "base_rate":         0.08,
        "weather_weight":    1.20,   # corrosion risk
        "temp_weight":       1.10,
        "fragility_weight":  1.30,   # precision parts
        "perishable_weight": 1.0,
        "value_density":     1.15,
        "description":       "Precision auto components — corrosion & alignment sensitive",
    },
}


@dataclass
class PriceResult:
    cargo_value: float
    disruption_probability: float
    base_premium: float
    weather_multiplier: float
    perishable_multiplier: float       # kept for backward compat
    cargo_multiplier: float            # new: composite cargo risk
    temp_multiplier: float             # new: temperature factor
    fragility_multiplier: float        # new: fragility/shock factor
    value_density_multiplier: float    # new: value density factor
    hedge_cost: float
    # After rerouting (lower probability)
    hedge_cost_after: float
    savings_pct: float
    savings_inr: float
    monsoon: bool
    perishable: bool
    cargo_type: str
    cargo_profile: dict = field(default_factory=dict)


def compute_hedge(
    cargo_value: float,
    disruption_probability: float,
    monsoon: bool = False,
    perishable: bool = False,
    cargo_type: str = "Standard",
    post_reroute_prob_reduction: float = 0.65,   # rerouting reduces risk by 65%
) -> PriceResult:
    """
    Compute hedge (insurance) cost before and after rerouting.

    Parameters
    ----------
    cargo_value            : ₹ value of cargo
    disruption_probability : model output in [0, 1]
    monsoon                : True if monsoon season / flag
    perishable             : True if commodity is perishable
    cargo_type             : one of CARGO_PROFILES keys
    post_reroute_prob_reduction : fraction by which disruption prob drops after reroute
    """
    profile = CARGO_PROFILES.get(cargo_type, CARGO_PROFILES["Standard"])

    base_rate = profile["base_rate"]

    #  Weather multiplier (monsoon amplifies the cargo-specific sensitivity) 
    weather_mult = profile["weather_weight"] if monsoon else 1.0

    #  Temperature multiplier (active during monsoon or high-temp season) 
    temp_mult = profile["temp_weight"] if monsoon else 1.0

    #  Perishable / spoilage multiplier 
    perish_mult = profile["perishable_weight"]

    #  Fragility multiplier 
    fragility_mult = profile["fragility_weight"]

    #  Value density multiplier 
    value_density_mult = profile["value_density"]

    #  Composite cargo multiplier (geometric mean of cargo-specific factors) 
    # This blends all cargo-specific risks into a single "cargo risk" factor
    cargo_composite = (
        perish_mult * fragility_mult * value_density_mult
    ) ** (1 / 3)  # geometric mean keeps the scale manageable

    #  Before rerouting 
    base_premium = cargo_value * disruption_probability * base_rate
    hedge_before = base_premium * weather_mult * temp_mult * cargo_composite

    #  After rerouting (probability drops) 
    prob_after = disruption_probability * (1 - post_reroute_prob_reduction)
    base_after = cargo_value * prob_after * base_rate
    hedge_after = base_after * weather_mult * temp_mult * cargo_composite

    savings_inr = max(hedge_before - hedge_after, 0)
    savings_pct = (savings_inr / hedge_before * 100) if hedge_before > 0 else 0

    return PriceResult(
        cargo_value=round(cargo_value, 2),
        disruption_probability=round(disruption_probability, 4),
        base_premium=round(base_premium, 2),
        weather_multiplier=round(weather_mult, 3),
        perishable_multiplier=round(perish_mult, 3),
        cargo_multiplier=round(cargo_composite, 3),
        temp_multiplier=round(temp_mult, 3),
        fragility_multiplier=round(fragility_mult, 3),
        value_density_multiplier=round(value_density_mult, 3),
        hedge_cost=round(hedge_before, 2),
        hedge_cost_after=round(hedge_after, 2),
        savings_pct=round(savings_pct, 1),
        savings_inr=round(savings_inr, 2),
        monsoon=monsoon,
        perishable=perishable,
        cargo_type=cargo_type,
        cargo_profile=profile,
    )


#  Demo scenario (Pune → Mumbai) 
DEMO_SCENARIO = dict(
    cargo_value=70_000,
    disruption_probability=0.78,   # high risk
    monsoon=True,
    perishable=True,
    cargo_type="Perishable Goods",
)


def demo_run() -> PriceResult:
    return compute_hedge(**DEMO_SCENARIO)


if __name__ == "__main__":
    r = demo_run()
    print(f"Hedge BEFORE reroute: ₹{r.hedge_cost:,.2f}")
    print(f"Hedge AFTER  reroute: ₹{r.hedge_cost_after:,.2f}")
    print(f"Savings: ₹{r.savings_inr:,.2f} ({r.savings_pct}%)")
    print(f"Cargo type: {r.cargo_type}")
    print(f"Weather: x{r.weather_multiplier}  Temp: x{r.temp_multiplier}")
    print(f"Cargo composite: x{r.cargo_multiplier}")
