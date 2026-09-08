"""
preprocessing.py — Feature engineering and normalization.

Builds / validates these features from the CSV:
  delay_ratio, rolling_delay_mean, rolling_delay_std,
  temperature_deviation, weather_severity_index,
  route_utilisation_ratio, monsoon_flag, cargo_value, commodity_type
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add / confirm feature columns needed for anomaly detection.
    If a column already exists it is kept; if missing it is simulated.
    """
    df = df.copy()

    #  1. delay_ratio 
    if "delay_ratio" not in df.columns:
        if {"actual_transit_hrs", "scheduled_transit_hrs"}.issubset(df.columns):
            df["delay_ratio"] = df["actual_transit_hrs"] / df["scheduled_transit_hrs"].replace(0, np.nan)
            df["delay_ratio"] = df["delay_ratio"].fillna(1.0)
        else:
            df["delay_ratio"] = np.random.uniform(0.9, 1.5, len(df))

    #  2. rolling_delay_mean_6h & rolling_delay_std_6h 
    if "rolling_delay_mean_6h" not in df.columns:
        df["rolling_delay_mean_6h"] = (
            df["delay_ratio"].rolling(window=6, min_periods=1).mean()
        )
    if "rolling_delay_std_6h" not in df.columns:
        df["rolling_delay_std_6h"] = (
            df["delay_ratio"].rolling(window=6, min_periods=1).std().fillna(0)
        )

    #  3. temperature_deviation 
    if "temp_deviation_c" in df.columns:
        df["temperature_deviation"] = df["temp_deviation_c"].abs()
    elif "temperature_deviation" not in df.columns:
        df["temperature_deviation"] = np.random.uniform(0, 3, len(df))

    #  4. weather_severity_index 
    if "weather_severity_index" not in df.columns:
        df["weather_severity_index"] = np.random.uniform(0, 1, len(df))

    #  5. route_utilisation_ratio 
    if "route_utilisation_ratio" not in df.columns and "route_utilization_ratio" not in df.columns:
        df["route_utilisation_ratio"] = np.random.uniform(0.3, 1.0, len(df))
    elif "route_utilization_ratio" in df.columns:
        df["route_utilisation_ratio"] = df["route_utilization_ratio"]

    #  6. monsoon_flag 
    if "monsoon_flag" not in df.columns:
        df["monsoon_flag"] = np.random.randint(0, 2, len(df))

    #  7. cargo_value_inr 
    if "cargo_value_inr" not in df.columns:
        df["cargo_value_inr"] = np.random.uniform(10000, 500000, len(df))

    #  8. commodity_type encoding 
    if "commodity_type" in df.columns:
        df["is_perishable"] = (df["commodity_type"] == "perishable").astype(int)
    elif "cold_chain_active" in df.columns:
        df["is_perishable"] = df["cold_chain_active"].astype(int)
    else:
        df["is_perishable"] = 0

    return df


FEATURE_COLS = [
    "delay_ratio",
    "rolling_delay_mean_6h",
    "rolling_delay_std_6h",
    "temperature_deviation",
    "weather_severity_index",
    "route_utilisation_ratio",
    "monsoon_flag",
]


def normalize_features(df: pd.DataFrame, scaler: StandardScaler = None):
    """
    Normalize FEATURE_COLS using StandardScaler.
    Returns (X_scaled, scaler).
    """
    # Only keep cols that exist
    available = [c for c in FEATURE_COLS if c in df.columns]
    X = df[available].copy().fillna(0)
    if scaler is None:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
    else:
        X_scaled = scaler.transform(X)
    return X_scaled, scaler, available
