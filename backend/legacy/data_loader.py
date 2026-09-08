"""
data_loader.py — Loads and validates the SmartSupplyChain CSV dataset.
"""

import pandas as pd
import numpy as np
import os


_FILENAME = "SmartSupplyChain_Dataset_30000.csv"
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Search order: data/ subfolder → root directory
_CANDIDATES = [
    os.path.join(_ROOT, "data", _FILENAME),
    os.path.join(_ROOT, _FILENAME),
    os.path.join(os.path.dirname(_ROOT), "data", _FILENAME),
]
DATA_PATH = next((p for p in _CANDIDATES if os.path.exists(p)), _CANDIDATES[2])


def load_data(filepath: str = DATA_PATH) -> pd.DataFrame:
    """
    Load the supply chain CSV dataset.
    Returns a cleaned DataFrame ready for feature engineering.
    """
    df = pd.read_csv(filepath)

    print(f"[data_loader] Loaded {len(df):,} rows | {df.shape[1]} columns")
    print(f"[data_loader] Columns: {df.columns.tolist()}")

    # Parse timestamp
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # Fill critical numeric nulls with column medians
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        if df[col].isnull().sum() > 0:
            df[col] = df[col].fillna(df[col].median())

    # Fill object nulls with "unknown"
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].fillna("unknown")

    print(f"[data_loader] Nulls after fill: {df.isnull().sum().sum()}")
    return df


def get_hubs(df: pd.DataFrame) -> list:
    """Return all unique hubs from origin + destination columns."""
    origins = df["origin_hub"].unique().tolist() if "origin_hub" in df.columns else []
    dests = df["destination_hub"].unique().tolist() if "destination_hub" in df.columns else []
    return sorted(list(set(origins + dests)))


if __name__ == "__main__":
    df = load_data()
    print(df.dtypes)
    print(df.head(3))
