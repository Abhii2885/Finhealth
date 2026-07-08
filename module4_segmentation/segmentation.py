"""
Core segmentation logic: turns Module 2's per-borrower dimension
availability into a per-borrower weight vector, an eligibility flag, and a
human-readable segment label.
"""

import pandas as pd
from config import BASE_DIMENSION_WEIGHTS, INSUFFICIENT_DATA_WEIGHT_MULTIPLIER, MIN_DIMENSIONS_FOR_SCORING

DIMENSIONS = list(BASE_DIMENSION_WEIGHTS.keys())


def _raw_weight(status, base_weight):
    if status == "available":
        return base_weight
    if status == "insufficient_data":
        return base_weight * INSUFFICIENT_DATA_WEIGHT_MULTIPLIER
    # not_applicable, not_computable_in_prototype -> excluded
    return 0.0


def _segment_label(row):
    included = [d for d in DIMENSIONS if row[f"{d}_effective_weight"] > 0]
    discounted = [d for d in DIMENSIONS if row[f"{d}_status"] == "insufficient_data"]

    if not row["scorable"]:
        return "Insufficient data for scoring"

    n = len(included)
    if discounted:
        return f"Partial confidence — {n} dimensions ({len(discounted)} discounted for thin data)"
    if n >= 5:
        return f"Full — {n} dimensions available"
    return f"Reduced — {n} dimensions available (structurally unavailable, not a data gap)"


def build_segmentation(dim_avail_df):
    rows = []
    for _, r in dim_avail_df.iterrows():
        row = {"borrower_id": r["borrower_id"]}
        raw_weights = {}
        for dim, base_w in BASE_DIMENSION_WEIGHTS.items():
            status = r[dim]
            row[f"{dim}_status"] = status
            raw_weights[dim] = _raw_weight(status, base_w)

        total_raw = sum(raw_weights.values())
        n_included = sum(1 for w in raw_weights.values() if w > 0)
        scorable = n_included >= MIN_DIMENSIONS_FOR_SCORING and total_raw > 0

        for dim in DIMENSIONS:
            if scorable and total_raw > 0:
                row[f"{dim}_effective_weight"] = round(raw_weights[dim] / total_raw, 4)
            else:
                row[f"{dim}_effective_weight"] = 0.0

        row["n_dimensions_included"] = n_included
        row["scorable"] = scorable
        rows.append(row)

    out = pd.DataFrame(rows)
    out["segment_label"] = out.apply(_segment_label, axis=1)
    return out
