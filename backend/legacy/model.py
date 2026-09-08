"""
model.py — Isolation Forest for supply-chain disruption detection.

Params  : n_estimators=200, contamination=0.08, random_state=42
Rule    : anomaly_score < -0.15  →  disruption  (flag = 1)
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from preprocessing import engineer_features, normalize_features


def build_model() -> IsolationForest:
    return IsolationForest(
        n_estimators=200,
        contamination=0.08,
        random_state=42,
        n_jobs=-1,
    )


def train_and_score(df: pd.DataFrame):
    """
    Engineer features, fit Isolation Forest, return enriched DataFrame.

    Added columns
    -------------
    anomaly_score_model   : raw IF decision score (lower = more anomalous)
    disruption_probability: mapped to [0,1] — higher means more disruptive
    disruption_predicted  : 1 if anomaly_score_model < -0.15 else 0
    """
    df = engineer_features(df)
    X_scaled, scaler, feature_cols = normalize_features(df)

    model = build_model()
    model.fit(X_scaled)

    raw_scores = model.decision_function(X_scaled)   # higher = more normal
    df["anomaly_score_model"] = raw_scores

    # Map to disruption probability: invert & normalise to [0,1]
    mn, mx = raw_scores.min(), raw_scores.max()
    df["disruption_probability"] = 1 - (raw_scores - mn) / (mx - mn + 1e-9)

    # Threshold rule
    df["disruption_predicted"] = (df["anomaly_score_model"] < -0.15).astype(int)

    return df, model, scaler, feature_cols


def score_single(row: dict, model: IsolationForest, scaler, feature_cols: list) -> dict:
    """
    Score a single shipment dict.
    Returns dict with anomaly_score, disruption_probability, disruption_flag.
    """
    from sklearn.preprocessing import StandardScaler as _SS
    X = np.array([[row.get(c, 0) for c in feature_cols]])
    X_scaled = scaler.transform(X)
    raw = model.decision_function(X_scaled)[0]
    # Use rough calibration: IsolationForest typical range [-0.5 .. 0.5]
    prob = float(np.clip(((-raw) + 0.15) / 0.5, 0, 1))
    flag = 1 if raw < -0.15 else 0
    return {
        "anomaly_score": round(raw, 4),
        "disruption_probability": round(prob, 4),
        "disruption_flag": flag,
    }
