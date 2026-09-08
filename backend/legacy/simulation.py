"""
simulation.py — Orchestrates the full pipeline every tick.

Pipeline:  CSV sample → preprocess → model → graph → pricing → result dict
"""

import time
import random
import numpy as np
import pandas as pd

from data_loader import load_data
from preprocessing import engineer_features, normalize_features
from model import build_model, score_single
from graph_engine import find_route, HUBS, build_graph
from pricing_engine import compute_hedge


#  Module-level singletons 
_df = None
_model = None
_scaler = None
_feature_cols = None


def _initialize():
    global _df, _model, _scaler, _feature_cols
    if _feature_cols is not None:
        return

    print("[simulation] Initialising pipeline ...")
    raw = load_data()
    temp_df = engineer_features(raw)
    X_scaled, temp_scaler, temp_feature_cols = normalize_features(temp_df)
    temp_model = build_model()
    temp_model.fit(X_scaled)
    
    _model = temp_model
    _scaler = temp_scaler
    _df = temp_df
    _feature_cols = temp_feature_cols
    print("[simulation] Pipeline ready.")


def get_summary_stats() -> dict:
    """KPI summary from the full dataset."""
    _initialize()
    df = _df
    sla_breach_rate = df["sla_breach"].mean() * 100 if "sla_breach" in df.columns else 0
    avg_delay = (df["delay_ratio"].mean() - 1.0) * 100 if "delay_ratio" in df.columns else 0
    total_disruptions = int(df["disruption_flag"].sum()) if "disruption_flag" in df.columns else 0
    avg_hedge = df["hedge_cost_inr"].mean() if "hedge_cost_inr" in df.columns else 0
    return {
        "sla_breach_rate": round(sla_breach_rate, 1),
        "avg_delay_pct": round(avg_delay, 1),
        "total_disruptions": total_disruptions,
        "avg_hedge_cost": round(avg_hedge, 2),
        "total_shipments": len(df),
    }


def run_tick(
    origin: str = "Pune_Hub",
    destination: str = "Mumbai_Hub",
    cargo_value: float = 70_000,
    monsoon: bool = True,
    perishable: bool = True,
    inject_disruption: bool = False,
    anomaly_threshold: float = -0.15,
    cargo_type: str = "Standard",
) -> dict:
    """
    Single simulation tick.  Returns a dict consumed by the dashboard.
    latency target: < 2 s
    """
    _initialize()

    #  1. Sample a random recent shipment (or inject demo row) 
    sample = _df.sample(1).iloc[0].to_dict()

    # Override key fields with user/demo parameters
    sample["origin_hub"] = origin
    sample["destination_hub"] = destination
    sample["cargo_value_inr"] = cargo_value
    sample["monsoon_flag"] = int(monsoon)
    sample["is_perishable"] = int(perishable)

    if inject_disruption:
        # Force extreme delay to trigger anomaly
        sample["delay_ratio"] = random.uniform(2.5, 4.0)
        sample["rolling_delay_mean_6h"] = sample["delay_ratio"]
        sample["weather_severity_index"] = random.uniform(0.7, 1.0)
        sample["temperature_deviation"] = random.uniform(4, 10)

    #  2. Score with Isolation Forest 
    ml_result = score_single(sample, _model, _scaler, _feature_cols)
    disruption_prob = ml_result["disruption_probability"]
    is_disrupted = ml_result["disruption_flag"] == 1

    #  3. Graph rerouting 
    disrupted_edge = None
    if is_disrupted and G_has_direct_edge(origin, destination):
        disrupted_edge = (origin, destination)

    route_info = find_route(origin, destination, disrupted_edge=disrupted_edge)

    #  4. Insurance pricing 
    price = compute_hedge(
        cargo_value=cargo_value,
        disruption_probability=disruption_prob,
        monsoon=monsoon,
        perishable=perishable,
        cargo_type=cargo_type,
    )

    return {
        "origin": origin,
        "destination": destination,
        "anomaly_score": ml_result["anomaly_score"],
        "disruption_probability": disruption_prob,
        "disruption_detected": is_disrupted,
        "route": route_info,
        "pricing": {
            "cargo_value": price.cargo_value,
            "base_premium": price.base_premium,
            "hedge_cost_before": price.hedge_cost,
            "hedge_cost_after": price.hedge_cost_after,
            "savings_inr": price.savings_inr,
            "savings_pct": price.savings_pct,
            "weather_multiplier": price.weather_multiplier,
            "perishable_multiplier": price.perishable_multiplier,
            "cargo_multiplier": price.cargo_multiplier,
            "temp_multiplier": price.temp_multiplier,
            "fragility_multiplier": price.fragility_multiplier,
            "value_density_multiplier": price.value_density_multiplier,
            "cargo_type": price.cargo_type,
            "cargo_profile": price.cargo_profile,
        },
        "flags": {
            "monsoon": monsoon,
            "perishable": perishable,
            "injected": inject_disruption,
        },
        "raw_sample": {
            "delay_ratio": round(sample.get("delay_ratio", 1.0), 3),
            "weather_severity": round(sample.get("weather_severity_index", 0), 3),
        },
    }


def G_has_direct_edge(src: str, dst: str) -> bool:
    from graph_engine import get_graph
    G = get_graph()
    return G.has_edge(src, dst)


if __name__ == "__main__":
    # Quick smoke test — run 3 ticks
    for i in range(3):
        result = run_tick(inject_disruption=(i == 1))
        print(f"\n Tick {i+1} ")
        print(f"  Disruption: {result['disruption_detected']} (p={result['disruption_probability']:.3f})")
        print(f"  Route: {' → '.join(result['route']['path'][:5])} ...")
        print(f"  Hedge before: ₹{result['pricing']['hedge_cost_before']:,.0f}")
        print(f"  Hedge after:  ₹{result['pricing']['hedge_cost_after']:,.0f}")
        print(f"  Savings: {result['pricing']['savings_pct']}%")
        time.sleep(0.5)
